/*
 * Multi-region oot-core loader (Player migration, isolated: NOT in the
 * makefile SRCS until the region link replaces oot-core.ld).
 *
 * The core is one statically linked ELF spread over five resident regions
 * (tools/partition_core_regions.py). Its payload file is:
 *   'ORG1', u16 version (1), u16 count,
 *   u32 bss_start, u32 bss_end,
 *   count x { u32 address, u32 bytes, u32 file_offset },
 *   region images.
 * Every region must sit wholly inside one allowed span (the design table
 * below), be 4-aligned and not overlap another. The whole table is validated
 * before any byte is copied, so a bad file leaves memory untouched; BSS must
 * lie inside the main core span. Regions are loaded once at boot and stay
 * resident (no CD reads during play). The caller runs the ctor table and
 * reads the entry at the main carve base afterwards.
 */
#include <stdint.h>
#include <string.h>

#include "oot_core_regions.h"

/* Cached addresses and sizes: core carve, two Low RAM gaps, retired cart
 * MUSICTRG and FAIRY reservations (PLAYER_MIGRATION.md placement design). */
const oot_region_span_t oot_region_spans[OOT_REGION_SPANS] = {
    { 0x02760000u, 655360u },
    { 0x0021D800u, 40960u },
    { 0x002FA000u, 24576u },
    { 0x026EC800u, 20480u },
    { 0x02683800u, 4096u },
};

static uint32_t be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3];
}

static int span_of(uint32_t address, uint32_t bytes, const oot_region_span_t *spans, int count)
{
    int i;

    for (i = 0; i < count; i++) {
        if (address >= spans[i].address && bytes <= spans[i].bytes &&
            address - spans[i].address <= spans[i].bytes - bytes)
            return i;
    }
    return -1;
}

int oot_core_regions_validate(const uint8_t *file, uint32_t length,
                              const oot_region_span_t *spans, int span_count)
{
    uint32_t count, i, j, bss_start, bss_end;

    if (length < 16 || memcmp(file, "ORG1", 4) != 0 || ((file[4] << 8) | file[5]) != 1)
        return OOT_REGIONS_BAD_HEADER;
    count = (uint32_t)((file[6] << 8) | file[7]);
    if (count == 0 || count > OOT_REGION_SPANS || 16 + count * 12 > length)
        return OOT_REGIONS_BAD_HEADER;
    bss_start = be32(file + 8);
    bss_end = be32(file + 12);
    if (bss_end < bss_start || span_of(bss_start, bss_end - bss_start, spans, 1) != 0)
        return OOT_REGIONS_BAD_BSS;
    for (i = 0; i < count; i++) {
        const uint8_t *e = file + 16 + i * 12;
        uint32_t address = be32(e), bytes = be32(e + 4), offset = be32(e + 8);

        if ((address & 3) || offset > length || bytes > length - offset)
            return OOT_REGIONS_BAD_RANGE;
        if (span_of(address, bytes, spans, span_count) < 0)
            return OOT_REGIONS_OUTSIDE;
        for (j = 0; j < i; j++) {
            const uint8_t *o = file + 16 + j * 12;
            uint32_t a = be32(o), b = be32(o + 4);
            if (address < a + b && a < address + bytes)
                return OOT_REGIONS_OVERLAP;
        }
        /* BSS lives after the main image; images must not cover it. */
        if (address < bss_end && bss_start < address + bytes)
            return OOT_REGIONS_OVERLAP;
    }
    return (int)count;
}

int oot_core_regions_load(const uint8_t *file, uint32_t length,
                          const oot_region_span_t *spans, int span_count,
                          uint8_t *(*to_pointer)(uint32_t address))
{
    int count = oot_core_regions_validate(file, length, spans, span_count);
    int i;

    if (count < 0)
        return count;
    for (i = 0; i < count; i++) {
        const uint8_t *e = file + 16 + i * 12;
        memcpy(to_pointer(be32(e)), file + be32(e + 8), be32(e + 4));
    }
    memset(to_pointer(be32(file + 8)), 0, be32(file + 12) - be32(file + 8));
    return count;
}
