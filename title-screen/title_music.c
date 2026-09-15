/*
 * Boots the Ponesound driver on the SCSP and hands off to title_player for
 * the actual note-by-note sequencing of NA_BGM_TITLE (see title_player.c).
 */

#include "title_music.h"
#include "ponesound.h"
#include "title_player.h"

extern uint8_t asset_sound_driver[];
extern uint8_t asset_sound_driver_end[];

/* Frames to let the sound CPU boot before issuing driver commands. Boot-time
 * only, so erring generous costs nothing. */
#define PONESOUND_BOOT_FRAMES 30

void
title_music_init(void)
{
        ponesound_load_driver(asset_sound_driver,
            asset_sound_driver_end - asset_sound_driver, ADX_MASTER_768);

        /*
         * The sound CPU needs time to boot after SNDON before we touch its
         * command table. m68k_com->pcmCtrl is a POINTER that the M68K driver
         * fills in from its own side, so writing pcmCtrl[n] too early
         * scribbles through an uninitialised pointer: the driver then
         * accepts nothing, and playback is silent apart from a single
         * chunk's worth of pop. The stock libyaul example gets away without
         * this wait; we do not, so don't remove it.
         */
        for (uint32_t i = 0; i < PONESOUND_BOOT_FRAMES; i++) {
                vdp2_sync();
                vdp2_sync_wait();
        }

        ponesound_set_master_volume(0xF);

        /* The driver's scheduler is pumped from vblank-in. */
        vdp_sync_vblank_in_set(ponesound_vblank_rq, NULL);

        title_player_init();
}
