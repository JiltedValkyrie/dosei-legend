#ifndef FRAME_PROBE_H
#define FRAME_PROBE_H
#include <stdint.h>
/* Starts the FRT-based per-segment timing shown on row 1-2 of the probe
 * display. Call once at startup, before the first frame_probe_stage() call
 * that should be timed. See docs/perf/HITLIST.md item 0. */
void frame_probe_time_init(void);
void frame_probe_stage(uint8_t stage);
/* Shared 4x6 hex glyph writer: `row` steps 12 pixels down the NBG0 bitmap.
 * Exposed so perf_bench can draw its report without duplicating the glyphs. */
void frame_probe_hex(uint16_t value, unsigned x, unsigned digits, unsigned row);
/* Renderer capacity refusals, shown on row 0 so they are visible in the
 * normal build too - these replaced asserts that vanished with DEBUG off. */
void frame_probe_overflow(uint16_t commands, uint16_t tiles);
void frame_probe_tick(void);
void frame_probe_complete(void);
#endif
