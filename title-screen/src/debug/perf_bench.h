#ifndef PERF_BENCH_H
#define PERF_BENCH_H
#include <stdint.h>

/*
 * Fixed-pose frame profiler, enabled by building with PERF_BENCH=1 (see the
 * Makefile - it also redirects objects and the disc image to build-perf/ so
 * this configuration can never reuse the normal build's objects).
 *
 * Independent of DEBUG on purpose. DEBUG gates libyaul assertions; this gates
 * measurement. They must not be entangled again.
 *
 * Design constraints this satisfies, from docs/perf/PLAN.md:
 *  - No drawing inside the measured window. frame_probe's per-marker VRAM
 *    writes are compiled out under PERF_BENCH; results are drawn once, after
 *    the window closes, and then the display is frozen. A screenshot taken
 *    afterwards therefore cannot mix values from adjacent frames.
 *  - Counters are plain increments into RAM, never a draw or a timer read.
 *  - The 16-bit FRT is extended to 32 bits by software rollover detection, so
 *    a span is not silently wrong when the counter wraps (~312 ms at DIV_128).
 *    A span longer than PERF_SANITY_COUNTS is reported as invalid, not kept.
 *  - Timer-read overhead is measured at init and reported, so the reader can
 *    judge how much the instrument perturbs what it measures.
 *
 * Residual known limitation: spans still include interrupt time (audio in
 * VBlank-in, controller in VBlank-out). That cannot be removed without
 * changing the behaviour under test.
 */

enum {
        PERF_SPAN_VERTEX = 0,   /* per-vertex transform, outcode, projection */
        PERF_SPAN_FACECULL,     /* face visibility and far-cull pass */
        PERF_SPAN_SORT,         /* sort_faces */
        PERF_SPAN_CLIPEMIT,     /* whole clip + command emit loop */
        PERF_SPAN_FRUSTUM,      /* accumulated: kokiri_clip_frustum only */
        PERF_SPAN_TEXTURE,      /* accumulated: kokiri_clip_texture only */
        PERF_SPAN_UPLOAD,       /* vdp1_sync_cmdt_list_put */
        PERF_SPAN_RENDER,       /* vdp1_sync_render issue */
        PERF_SPAN_VDP1WAIT,     /* vdp1_sync + vdp1_sync_wait */
        PERF_SPAN_DISPLAYED,    /* count of spans shown; keep last but one */
        PERF_SPAN_SCRATCH = PERF_SPAN_DISPLAYED, /* overhead probe, not shown */
        PERF_SPAN_COUNT
};

enum {
        PERF_COUNT_VISIBLE = 0,      /* faces surviving cull */
        PERF_COUNT_COMMANDS,         /* VDP1 commands emitted */
        PERF_COUNT_TILES,            /* scratch tiles resampled */
        PERF_COUNT_PROJECTED,        /* vertices that took the project path */
        PERF_COUNT_FRUSTUM_CALLS,    /* kokiri_clip_frustum invocations */
        PERF_COUNT_OVF_COMMANDS,     /* command-capacity refusals */
        PERF_COUNT_OVF_TILES,        /* scratch-tile-capacity fallbacks */
        PERF_COUNT_COUNT
};

#ifdef PERF_BENCH

void perf_bench_init(void);
void perf_span_begin(unsigned id);
void perf_span_end(unsigned id);
void perf_count_add(unsigned id, uint32_t n);
void perf_frame_end(void);

#define PERF_SPAN_BEGIN(id)  perf_span_begin(id)
#define PERF_SPAN_END(id)    perf_span_end(id)
#define PERF_COUNT_ADD(id,n) perf_count_add((id),(n))
#define PERF_FRAME_END()     perf_frame_end()
#define PERF_BENCH_INIT()    perf_bench_init()

#else

#define PERF_SPAN_BEGIN(id)  ((void)0)
#define PERF_SPAN_END(id)    ((void)0)
#define PERF_COUNT_ADD(id,n) ((void)0)
#define PERF_FRAME_END()     ((void)0)
#define PERF_BENCH_INIT()    ((void)0)

#endif
#endif
