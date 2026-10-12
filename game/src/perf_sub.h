#ifndef PERF_SUB_H
#define PERF_SUB_H
/* Debug overlay rows 10-12 (docs/DEBUG_OVERLAY.md): named sub-timers, us
 * summed over one frame, latched by perf_sub_latch() at frame end. Each
 * section costs two FRT reads; no FPU, 32-bit only. */
#include "frame_timer.h"

enum {
    /* gameplay_step (C gameplay) */
    PS_NC, PS_WP, PS_EN, PS_AT, PS_BB, PS_TK, PS_IT, PS_RC,
    /* recomp.c PLAYER_SOURCE step, outside gameplay_step/core/camera */
    PS_PRE, PS_POST, PS_AC, PS_DP, PS_NV,
    /* main.c frame: scene update, prop draws, actor draws, text/HUD */
    PS_KS, PS_DGR, PS_DAC, PS_DUI, PS_RU,
    /* inside PS_DAC: nut+babas, npc_draw (incl. world props), core
     * sprites/tools/effects/meshes, C world props, fairies */
    PS_DNB, PS_DNPC, PS_DWC, PS_DWP, PS_DFY,
    /* inside PS_DNPC (2026-10-12 coverage fix): the rest of world_props_draw
     * after pots/rocks/bushes (drops, signs, bosses, Gohma, babas, chests...)
     * and npc_draw's own sprite-actor loop (shopkeeper + NPCs) */
    PS_DWR, PS_DPPL,
    /* recomp_update outside the step loop: before it, after skinning;
     * inside pr: webs/puzzles/doors; inside dp: world_props_displace */
    PS_R0, PS_R1, PS_PRD, PS_DPW,
    /* Second SH-2 (rows 16-17): master waits for the slave (scene prepare,
     * Link skin, core join, SGL queue drain), then the slave's own job
     * times (prepare, core update, skin), slave FRT at /128. */
    PS_WPREP, PS_WSKIN, PS_WJOIN, PS_WDRAIN, PS_SPREP, PS_SCORE, PS_SSKIN,
    /* Row 18: scene prepare phases (either CPU), fog tiles rewritten (a
     * count: 16 VDP1 palette writes each), NPC/prop cel uploads to VDP1
     * VRAM (time, then bytes). */
    PS_PDEPTH, PS_PPART, PS_PFOG, PS_FOGN, PS_CEL, PS_CELB, PS_SUBMIT,
    /* Row 19: sprite actors (npc_sprite_draw_styled): shadow lookup+submit,
     * slPutSprite, sprites drawn (a count), then host floor queries made by
     * shadows after the core join (kokiri_shadow_resolve) and their time. */
    PS_SSHADOW, PS_SPUT, PS_SCOUNT, PS_SRESOLVE,
    /* Row 19 tail: inside PS_DWR, the signs block and the chest loop; inside
     * PS_DPPL, time spent in npc_sprite_draw calls themselves. */
    PS_DSIGN, PS_DCHEST, PS_NDRAW,
    PS_VPACK, PS_VUSED, PS_VTOTAL, PS_MPREP,
    /* Row 22: inside PS_R1, minimap_layer_flags prompt/state queries,
     * health/magic composition and upload, map/button/pause visibility. */
    PS_HQUERY, PS_HHEALTH, PS_HVIS,
    /* Row 23: candidate envelope builds (x100, so the mean is percent of
     * frames), build pass time, and why the old envelope was left: camera
     * position, yaw/pitch, other (FOV, roll, LOD, FAR), each x100. */
    PS_EBUILD, PS_EBTIME, PS_EXPOS, PS_EXANG, PS_EXOTH,
    PS_COUNT
};
extern unsigned int perf_sub[PS_COUNT];
#ifdef __sh__
#include "ram_low.h"
typedef char perf_sub_history_fits[2u * PS_COUNT * sizeof(unsigned int)
                                   <= RAM_LOW_PERF_HISTORY_BYTES ? 1 : -1];
#define perf_sub_avg ((unsigned int *)RAM_LOW(RAM_LOW_PERF_HISTORY_OFFSET))
#else
/* Per-frame average of perf_sub over the overlay's last refresh window. */
extern unsigned int perf_sub_avg[PS_COUNT];
#endif
#define PS_T0() unsigned int ps_t0 = frame_timer_ticks()
#define PS_RESET() (ps_t0 = frame_timer_ticks())
#define PS_ADD(i) do { unsigned int ps_t1 = frame_timer_ticks(); \
    perf_sub[i] += frame_timer_ticks_to_us(ps_t1 - ps_t0); ps_t0 = ps_t1; } while (0)
/* Add microseconds from code outside the PS_T0 pattern (slave joins). */
#define PS_ACC(i, us) (perf_sub[i] += (us))
void perf_sub_latch(void);
#endif
