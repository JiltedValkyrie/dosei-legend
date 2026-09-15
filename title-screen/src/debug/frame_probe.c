/* Temporary freeze probe: direct bitmap writes, no allocation or VDP sync waits.
 * Top row: stage / completed frames / vblank ticks / VDP1 EDSR / VDP1 COPR.
 * All numbers are hexadecimal. Keep the title visible for this diagnostic. */
#include <yaul.h>
#include "frame_probe.h"

static uint8_t frames, ticks;
static const uint16_t glyphs[16] = {
    0x7B6F,0x2492,0x73E7,0x73CF,0x5BC9,0x79CF,0x79EF,0x7249,
    0x7BEF,0x7BCF,0x7BED,0x6BAE,0x7927,0x6B6E,0x79E7,0x79E4
};

static void hex(uint16_t value, unsigned x, unsigned digits)
{
        volatile uint16_t *pixels = (volatile uint16_t *)VDP2_VRAM_ADDR(0,0);
        for (unsigned digit = 0; digit < digits; digit++) {
                uint16_t bits = glyphs[(value >> ((digits-digit-1)*4)) & 15];
                for (unsigned y = 0; y < 10; y++) for (unsigned col = 0; col < 8; col++) {
                        bool on = col < 6 && (bits & (1 << (14-(y/2)*3-col/2)));
                        pixels[(y+2)*512+x+digit*8+col] = on ? 0x83FF : 0x8000;
                }
        }
}

void frame_probe_stage(uint8_t stage) { hex(stage,4,2); }
void frame_probe_complete(void) { hex(++frames,28,2); }
void frame_probe_tick(void)
{
        volatile vdp1_ioregs_t *vdp1 = (volatile vdp1_ioregs_t *)VDP1_IOREG_BASE;
        hex(++ticks,52,2);
        hex(vdp1->edsr,76,2);
        hex(vdp1->copr,100,4);
}
