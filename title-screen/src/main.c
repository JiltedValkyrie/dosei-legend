/*
 * Dosei Legend - title screen.
 *
 * Renders the real OoT (ntsc-1.1) title-screen composition - shield/sword
 * logo, "The Legend of Zelda / Ocarina of Time" wordmark, 1998 copyright -
 * as a single VDP2 normal bitmap. The bitmap itself is generated host-side
 * by tools/make_title_bitmap.py from textures extracted by the zeldaret/oot
 * decomp build (see that script for the exact source coordinates); this
 * file only has to get it on screen, same pattern as the libyaul
 * vdp2-normal-bitmap example.
 */

#include <yaul.h>

#include <tga.h>

#include <assert.h>

#include "kokiri_scene.h"
#include "title_music.h"
#include "frame_probe.h"
#include "crash_probe.h"
#include "perf_bench.h"

static volatile bool input_enabled;
static volatile uint16_t input_buttons, input_rising;

static bool __attribute__((noinline))
title_input_update(uint16_t rising)
{
        static bool visible = true;
        if (rising & PERIPHERAL_DIGITAL_START) {
                visible = !visible;
                const vdp2_scrn_disp_t layers = visible
                    ? VDP2_SCRN_DISPTP_NBG0 | VDP2_SCRN_DISPTP_NBG1
                    : VDP2_SCRN_DISPTP_NBG1;
                vdp2_scrn_display_set(layers);
        }
        return visible;
}

extern uint8_t asset_title_tga[];
extern uint8_t asset_press_start_raw[];
extern uint8_t asset_forest_bg_tga[];

/*
 * "PRESS START" blink. The original (z_en_mag.c EnMag_DrawInner) pulses this
 * text's alpha via a ~52-frame triangle wave rather than a hard on/off blink;
 * we approximate that as a plain on/off toggle here; same idea, simpler
 * mechanism, since VDP2 alpha blending would just be more code for a
 * cosmetic-only difference at this stage.
 *
 * The patch is composited (assets/PRESS_START.RAW, see
 * tools/make_title_bitmap.py) at the same coordinates EnMag_DrawInner draws
 * it at (YREG(7)=119 etc, with a 1px margin), so it can be blitted directly
 * into the TITLE.TGA bitmap's own VRAM rather than needing a second VDP2
 * scroll layer just to toggle a small patch of pixels.
 */
#define PRESS_START_PATCH_X 118
#define PRESS_START_PATCH_Y 173
#define PRESS_START_PATCH_W 84
#define PRESS_START_PATCH_H 14
#define BITMAP_STRIDE_PX    512
#define PRESS_START_BLINK_FRAMES 30

static void
_vblank_out_handler(void *work __unused)
{
        if (!input_enabled) return;
        /* Consume the previous collection before requesting another. VBlank
         * out masks the lower-priority SMPC interrupt during the SDK parse;
         * the slow renderer must never parse that shared buffer itself. */
        smpc_peripheral_process();
        smpc_peripheral_digital_t pad = { 0 };
        smpc_peripheral_digital_port(1, &pad);
        uint16_t buttons = pad.connected ? pad.pressed.raw : 0;
        input_rising |= buttons & (uint16_t)~input_buttons;
        input_buttons = buttons;
        smpc_peripheral_intback_issue();
}

static void __unused
press_start_blit(bool visible)
{
        uint16_t * const vram = (uint16_t *)VDP2_VRAM_ADDR(0, 0x00000);
        const uint16_t *src = (const uint16_t *)asset_press_start_raw;

        for (uint32_t row = 0; row < PRESS_START_PATCH_H; row++) {
                uint16_t * const dst_row =
                    vram + (PRESS_START_PATCH_Y + row) * BITMAP_STRIDE_PX + PRESS_START_PATCH_X;

                for (uint32_t col = 0; col < PRESS_START_PATCH_W; col++) {
                        /* 0x0000 (not opaque black 0x8000) so the "off"
                         * state is colorkey-transparent too, consistent
                         * with the rest of the background - see the
                         * tga_options transparency setup in main(). */
                        dst_row[col] = visible ? src[row * PRESS_START_PATCH_W + col] : 0x0000;
                }
        }
}

/* Initialize CD access and controller polling before main. */
void
user_init(void)
{
        crash_probe_init();
        frame_probe_time_init();
        PERF_BENCH_INIT();
        cd_block_init();
        smpc_peripheral_init();

        vdp_sync_vblank_out_set(_vblank_out_handler, NULL);
}

int
main(void)
{
        const vdp2_scrn_bitmap_format_t format = {
                .scroll_screen = VDP2_SCRN_NBG0,
                .ccc           = VDP2_SCRN_CCC_RGB_32768,
                .bitmap_size   = VDP2_SCRN_BITMAP_SIZE_512X256,
                .palette_base  = 0x00000000,
                .bitmap_base   = VDP2_VRAM_ADDR(0, 0x00000)
        };

        vdp2_scrn_bitmap_format_set(&format);
        vdp2_scrn_priority_set(VDP2_SCRN_NBG0, 7);

        /*
         * NBG1 carries the Kokiri Forest backdrop (tools/make_forest_backdrop.py)
         * as the backmost layer - below the room geometry (VDP1
         * priority 3) and below NBG0's logo (priority 7). A 512x256 16bpp
         * bitmap is 256KB, i.e. two full VRAM banks: NBG0's own bitmap
         * already fills banks 0+1, so this one goes in banks 2+3. It's
         * opaque and covers the whole visible area, so the old solid
         * back_color fallback (which lived in bank 3) is removed rather
         * than kept pointlessly unreachable.
         */
        const vdp2_scrn_bitmap_format_t backdrop_format = {
                .scroll_screen = VDP2_SCRN_NBG1,
                .ccc           = VDP2_SCRN_CCC_RGB_32768,
                .bitmap_size   = VDP2_SCRN_BITMAP_SIZE_512X256,
                .palette_base  = 0x00000000,
                .bitmap_base   = VDP2_VRAM_ADDR(2, 0x00000)
        };

        vdp2_scrn_bitmap_format_set(&backdrop_format);
        vdp2_scrn_priority_set(VDP2_SCRN_NBG1, 1);

        /* DISPTP, not DISP: both enable a layer, but VDP2_SCRN_DISP_NBG0
         * (0x0101) also sets bit 8 - VDP2's N0TPON "transparent-code
         * display" bit - which forces transparency-coded pixels to be drawn
         * opaque, hiding everything behind the layer. DISPTP (0x0001/0x0002)
         * leaves it clear so NBG0's keyed-out black background lets NBG1
         * (and VDP1) show through. NBG1 itself is fully opaque so its own
         * DISPTP/DISP choice doesn't matter, but DISPTP is used for both to
         * keep the two consistent. */
        vdp2_scrn_display_set(VDP2_SCRN_DISPTP_NBG0 | VDP2_SCRN_DISPTP_NBG1);

        const vdp2_vram_cycp_t vram_cycp = {
                .pt[0].t0 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[0].t1 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[0].t2 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[0].t3 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[0].t4 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[0].t5 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[0].t6 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[0].t7 = VDP2_VRAM_CYCP_NO_ACCESS,

                .pt[1].t0 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[1].t1 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[1].t2 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[1].t3 = VDP2_VRAM_CYCP_CHPNDR_NBG0,
                .pt[1].t4 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[1].t5 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[1].t6 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[1].t7 = VDP2_VRAM_CYCP_NO_ACCESS,

                .pt[2].t0 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[2].t1 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[2].t2 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[2].t3 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[2].t4 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[2].t5 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[2].t6 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[2].t7 = VDP2_VRAM_CYCP_NO_ACCESS,

                .pt[3].t0 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[3].t1 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[3].t2 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[3].t3 = VDP2_VRAM_CYCP_CHPNDR_NBG1,
                .pt[3].t4 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[3].t5 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[3].t6 = VDP2_VRAM_CYCP_NO_ACCESS,
                .pt[3].t7 = VDP2_VRAM_CYCP_NO_ACCESS
        };

        vdp2_vram_cycp_set(&vram_cycp);

        tga_t tga;
        int ret __unused;
        ret = tga_read(&tga, asset_title_tga);
        assert(ret == TGA_FILE_OK);

        /* Key the bitmap's black background out to hardware-transparent
         * (RGB555 0x0000) so the Kokiri Forest scene, drawn on VDP1 at a
         * lower sprite priority than this NBG0 layer, shows through behind
         * the logo/text instead of being fully occluded by an opaque black
         * background.
         *
         * NB: libtga's ".msb" is misleadingly named - per tga.c, a matching
         * pixel becomes (msb ? 0x8000 : 0x0000). 0x8000 is opaque black, not
         * transparent, so it must be false here to actually get 0x0000
         * (Saturn's hardware-transparent value for RGB555 layers). */
        tga.tga_options.transparent_pixel = 0x0000;
        tga.tga_options.msb = false;

        tga_image_decode(&tga, (void *)VDP2_VRAM_ADDR(0, 0x00000));

        /* Backdrop is fully opaque - no colorkey transparency setup needed. */
        tga_t backdrop_tga;
        ret = tga_read(&backdrop_tga, asset_forest_bg_tga);
        assert(ret == TGA_FILE_OK);
        tga_image_decode(&backdrop_tga, (void *)VDP2_VRAM_ADDR(2, 0x00000));

        vdp2_tvmd_display_res_set(VDP2_TVMD_INTERLACE_NONE, VDP2_TVMD_HORZ_NORMAL_A,
            VDP2_TVMD_VERT_240);
        vdp2_tvmd_display_set();

        kokiri_scene_init();
        title_music_init();
        /* Sound bootstrap also uses SMPC commands; begin polling afterward. */
        input_enabled = true;

        vdp2_sync();
        vdp2_sync_wait();

        uint32_t frame = 0;
        bool press_start_visible __unused = true;

        while (true) {
                frame_probe_stage(0x10);
                smpc_peripheral_digital_t pad = { 0 };
                const uint8_t interrupt_mask = cpu_intc_mask_get();
                cpu_intc_mask_set(15);
                pad.pressed.raw = input_buttons;
                const uint16_t rising = input_rising;
                input_rising = 0;
                cpu_intc_mask_set(interrupt_mask);
                const bool title_visible = title_input_update(rising);
#ifndef PERF_BENCH
                if ((frame % PRESS_START_BLINK_FRAMES) == 0) {
                        press_start_visible = !press_start_visible;
                        press_start_blit(press_start_visible);
                }
#endif

                frame_probe_stage(0x20);
                /* PERF_BENCH holds a fixed pose: the camera keeps the
                 * collision-validated spawn position with yaw and pitch at
                 * zero, and automatic rotation never runs. Every measured
                 * frame therefore renders identical geometry, which is what
                 * makes before/after comparison meaningful. The blink above
                 * is also suppressed so no frame carries an extra blit. */
#ifndef PERF_BENCH
                kokiri_scene_camera_update(&pad, title_visible);
#else
                (void)pad; (void)title_visible;
#endif
                kokiri_scene_update_and_draw();

                frame_probe_stage(0x80);
                vdp2_sync();
                vdp2_sync_wait();
                frame_probe_complete();
                PERF_FRAME_END();

                frame++;
        }

        return 0;
}
