/* Sound CPU bootstrap and video-clock scheduler for the live SCSP score. */
#include <yaul.h>
#include <smpc/smc.h>
#include "title_music.h"
#include "title_player.h"

static unsigned _phase;
static unsigned _refresh;

static void
_audio_vblank(void *work __unused)
{
        _phase += 60;
        while (_phase >= _refresh) {
                _phase -= _refresh;
                title_player_update();
        }
}

void
title_music_init(void)
{
        smpc_smc_call(SMPC_SMC_SNDOFF);
        smpc_smc_wait(0);

        volatile uint16_t *regs = (volatile uint16_t *)0x25B00000UL;
        regs[0x400 / 2] = 0x0200; /* 512 KiB mode, muted */
        regs[0x41E / 2] = 0;      /* no sound-CPU interrupts */
        regs[0x42A / 2] = 0;      /* no main-CPU interrupts */
        for (unsigned i = 0; i < 0x400 / 2; i++) {
                regs[i] = 0;
        }
        for (unsigned i = 0; i < 32; i++) {
                regs[i * 16 + 6] = 255;
                regs[i * 16 + 5] = 31;
        }
        regs[0] = 0x1000;         /* execute key-off for all 32 slots */

        volatile uint16_t *ram = (volatile uint16_t *)0x25A00000UL;
        /* All exception vectors point to the same idle routine. The stack
         * stays below the sample area, and interrupts remain masked.
         * Restart promptly: SEGA bulletin 51 limits SNDOFF to 0.5 seconds. */
        for (unsigned i = 0; i < 0x400 / 2; i += 2) {
                ram[i] = 0;
                ram[i + 1] = 0x0400;
        }
        ram[1] = 0x0FF0;          /* reset stack pointer = 0x00000FF0 */
        ram[0x400 / 2] = 0x46FC;  /* move.w #0x2700,sr */
        ram[0x402 / 2] = 0x2700;
        ram[0x404 / 2] = 0x60FE;  /* bra.s . */
        smpc_smc_call(SMPC_SMC_SNDON);
        smpc_smc_wait(0);

        title_player_init();
        _phase = 0;
        _refresh = (vdp2_tvmd_tv_standard_get() == VDP2_TVMD_TV_STANDARD_PAL) ? 50 : 60;
        regs[0x400 / 2] = 0x020F;
        vdp_sync_vblank_in_set(_audio_vblank, NULL);
}
