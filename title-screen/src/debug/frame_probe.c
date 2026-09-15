/* Temporary freeze probe: direct bitmap writes, no allocation or VDP sync waits.
 * Row 0 (y pixels 2-11): stage / completed frames / vblank ticks / VDP1 EDSR /
 * VDP1 COPR. All numbers are hexadecimal. Keep the title visible for this
 * diagnostic.
 *
 * Rows 1-2 (y pixels 14-23, 26-35): per-segment FRT tick counts between
 * consecutive frame_probe_stage() calls, one 4-digit hex column per segment,
 * in call order. See docs/perf/HITLIST.md item 0 for what each segment
 * covers; the stage id pairs are, in display order:
 *   row 1: 10-20 20-30 30-40 40-48 48-50
 *   row 2: 50-60 60-70 70-78 78-80 80-10 (wraps to next frame's 0x10)
 * Values are raw CPU_FRT_CLOCK_DIV_128 counts. CPU_FRT_NTSC_320_128_COUNT_1MS
 * (0x00D2 = 210) converts a count to milliseconds: ms = count / 210.
 * frame_probe_time_init() must run once before these are meaningful; until
 * then the segment row stays blank. */
#include <yaul.h>
#include <cpu/frt.h>
#include "frame_probe.h"

static uint8_t frames __unused, ticks __unused;
static const uint16_t glyphs[16] = {
    0x7B6F,0x2492,0x73E7,0x73CF,0x5BC9,0x79CF,0x79EF,0x7249,
    0x7BEF,0x7BCF,0x7BED,0x6BAE,0x7927,0x6B6E,0x79E7,0x79E4
};

void frame_probe_hex(uint16_t value, unsigned x, unsigned digits, unsigned row)
{
        volatile uint16_t *pixels = (volatile uint16_t *)VDP2_VRAM_ADDR(0,0);
        for (unsigned digit = 0; digit < digits; digit++) {
                uint16_t bits = glyphs[(value >> ((digits-digit-1)*4)) & 15];
                for (unsigned y = 0; y < 10; y++) for (unsigned col = 0; col < 8; col++) {
                        bool on = col < 6 && (bits & (1 << (14-(y/2)*3-col/2)));
                        pixels[(y+2+row*12)*512+x+digit*8+col] = on ? 0x83FF : 0x8000;
                }
        }
}

/* The old per-marker timing path. Compiled out under PERF_BENCH, which does
 * its own timing without drawing inside the measured window. */
#ifndef PERF_BENCH
/* Ring of stage ids frame_probe_stage() is timed against, in the order they
 * fire each frame (see main.c / kokiri_scene.c call sites). Segment i is the
 * span from time_stages[i] to time_stages[(i+1) % TIME_STAGE_COUNT]; the
 * last segment wraps from 0x80 back to the next frame's 0x10, which folds in
 * the vdp2_sync/vdp2_sync_wait vblank wait between frames. */
#define TIME_STAGE_COUNT 10
static const uint8_t time_stages[TIME_STAGE_COUNT] = {
    0x10, 0x20, 0x30, 0x40, 0x48, 0x50, 0x60, 0x70, 0x78, 0x80
};
#define TIME_COLUMN_WIDTH 36
#define TIME_ROW_COUNT 5
static bool time_enabled;
static uint16_t time_last_count;
static uint8_t time_last_index = 0xFF;

void frame_probe_time_init(void)
{
        cpu_frt_init(CPU_FRT_CLOCK_DIV_128);
        time_enabled = true;
        time_last_index = 0xFF;
}

static void frame_probe_time_mark(uint8_t stage)
{
        if (!time_enabled) return;
        uint8_t index = 0xFF;
        for (uint8_t i = 0; i < TIME_STAGE_COUNT; i++) {
                if (time_stages[i] == stage) { index = i; break; }
        }
        if (index == 0xFF) return;
        const uint16_t now = cpu_frt_count_get();
        if (time_last_index != 0xFF) {
                /* Unsigned wraparound handles the FRT's 16-bit rollover
                 * (~312ms at DIV_128) as long as no single segment itself
                 * exceeds that span, which a single frame never does. */
                const uint16_t delta = (uint16_t)(now - time_last_count);
                const unsigned x = 4 + (time_last_index % TIME_ROW_COUNT) * TIME_COLUMN_WIDTH;
                const unsigned row = 1 + (time_last_index / TIME_ROW_COUNT);
                frame_probe_hex(delta, x, 4, row);
        }
        time_last_count = now;
        time_last_index = index;
}
#else
void frame_probe_time_init(void) { }
#endif

/* Under PERF_BENCH these draw nothing and time nothing: their VRAM writes
 * would land inside perf_bench's measured spans, which is one of the defects
 * that invalidated the first round of readings. perf_bench draws its own
 * report after its window closes. */
#ifdef PERF_BENCH
void frame_probe_stage(uint8_t stage __unused) { }
void frame_probe_complete(void) { }
void frame_probe_tick(void) { }
void frame_probe_overflow(uint16_t commands __unused, uint16_t tiles __unused) { }
#else
void frame_probe_stage(uint8_t stage) { frame_probe_hex(stage,4,2,0); frame_probe_time_mark(stage); }
void frame_probe_complete(void) { frame_probe_hex(++frames,28,2,0); }
void frame_probe_tick(void)
{
        volatile vdp1_ioregs_t *vdp1 = (volatile vdp1_ioregs_t *)VDP1_IOREG_BASE;
        frame_probe_hex(++ticks,52,2,0);
        frame_probe_hex(vdp1->edsr,76,2,0);
        frame_probe_hex(vdp1->copr,100,4,0);
}
void frame_probe_overflow(uint16_t commands, uint16_t tiles)
{
        frame_probe_hex(commands,140,4,0);
        frame_probe_hex(tiles,176,4,0);
}
#endif
