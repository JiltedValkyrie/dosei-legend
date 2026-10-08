/* OAP1: fixed-address SH-2 code, bound to the exact resident core binary.
 * All disk words are big endian. Offsets are relative to link_base; profile
 * entries and constructor words contain already-linked absolute addresses. */
#ifndef OOT_ACTOR_PACK_H
#define OOT_ACTOR_PACK_H

#define OOT_ACTOR_PACK_MAGIC 0x4f415031u
#define OOT_ACTOR_PACK_VERSION 1u
#define OOT_ACTOR_PACK_HEADER_BYTES 80u
#define OOT_ACTOR_PACK_TEST 1u

typedef struct OotActorPackHeader {
    unsigned int magic, version, header_bytes, core_crc;
    unsigned int link_base, file_bytes, memory_bytes, bss_offset, bss_bytes;
    unsigned int ctors_offset, ctor_count, actors_offset, actor_count;
    unsigned int effects_offset, effect_count, crc;
    unsigned int text_offset, text_bytes, scene, flags;
} OotActorPackHeader;

typedef struct OotActorPackProfile {
    unsigned int id, profile;
} OotActorPackProfile;

/* Subtractions avoid overflow on untrusted disk sizes. */
static inline int OotActorPack_Range(unsigned int offset, unsigned int count,
                                   unsigned int stride, unsigned int end) {
    return stride != 0 && offset <= end && count <= (end - offset) / stride;
}

static inline int OotActorPack_HeaderValid(const OotActorPackHeader* h,
                                          unsigned int file_bytes,
                                          unsigned int carve_base,
                                          unsigned int carve_bytes,
                                          unsigned int used,
                                          unsigned int core_crc) {
    if (!h || h->magic != OOT_ACTOR_PACK_MAGIC || h->version != OOT_ACTOR_PACK_VERSION ||
        h->header_bytes != OOT_ACTOR_PACK_HEADER_BYTES || h->core_crc != core_crc ||
        h->file_bytes != file_bytes || file_bytes < h->header_bytes ||
        h->memory_bytes < file_bytes || h->memory_bytes > carve_bytes ||
        used > carve_bytes - h->memory_bytes || (h->memory_bytes & 15u) ||
        h->link_base != carve_base + (carve_bytes - h->memory_bytes) ||
        h->bss_offset != file_bytes || h->bss_bytes > h->memory_bytes - file_bytes ||
        h->text_offset < h->header_bytes || (h->text_offset & 3u) ||
        !OotActorPack_Range(h->text_offset, h->text_bytes, 1, file_bytes) ||
        !h->text_bytes || (h->flags & ~OOT_ACTOR_PACK_TEST)) return 0;
    if ((h->ctors_offset | h->actors_offset | h->effects_offset) & 3u) return 0;
    if (h->ctors_offset < h->header_bytes || h->actors_offset < h->header_bytes ||
        h->effects_offset < h->header_bytes) return 0;
    return h->ctors_offset >= h->text_offset + h->text_bytes &&
        h->actors_offset >= h->ctors_offset && h->effects_offset >= h->actors_offset &&
        OotActorPack_Range(h->ctors_offset, h->ctor_count, 4, h->actors_offset) &&
        OotActorPack_Range(h->actors_offset, h->actor_count, 8, h->effects_offset) &&
        OotActorPack_Range(h->ctors_offset, h->ctor_count, 4, file_bytes) &&
        OotActorPack_Range(h->actors_offset, h->actor_count, 8, file_bytes) &&
        OotActorPack_Range(h->effects_offset, h->effect_count, 8, file_bytes);
}

/* CRC32/IEEE. skip_crc treats the pack header's crc word as zero. */
static inline unsigned int OotActorPack_Crc(const void* data, unsigned int bytes,
                                          int skip_crc) {
    const unsigned char* p = (const unsigned char*)data;
    unsigned int crc = ~0u, i, bit;
    for (i = 0; i < bytes; ++i) {
        crc ^= (skip_crc && i >= 60u && i < 64u) ? 0u : p[i];
        for (bit = 0; bit < 8; ++bit) crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
    }
    return ~crc;
}
#endif
