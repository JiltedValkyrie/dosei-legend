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
    /* recomp_update outside the step loop: before it, after skinning;
     * inside pr: webs/puzzles/doors; inside dp: world_props_displace */
    PS_R0, PS_R1, PS_PRD, PS_DPW,
    PS_COUNT
};
extern unsigned int perf_sub[PS_COUNT];
extern unsigned int perf_sub_last[PS_COUNT];
#define PS_T0() unsigned int ps_t0 = frame_timer_ticks()
#define PS_RESET() (ps_t0 = frame_timer_ticks())
#define PS_ADD(i) do { unsigned int ps_t1 = frame_timer_ticks(); \
    perf_sub[i] += frame_timer_ticks_to_us(ps_t1 - ps_t0); ps_t0 = ps_t1; } while (0)
void perf_sub_latch(void);
#endif
