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
 * Clock validity. The 16-bit FRT is extended to 32 bits by the FRT overflow
 * interrupt, not by comparing successive reads. Comparing reads cannot detect
 * a full wrap: reading 70000 counts after 1000 yields a raw 5464, which is
 * greater than 1000, so no wrap is inferred and the span is reported as 4464 -
 * a plausible value that no range check rejects. cpu_frt_init sets the FRT
 * interrupt priority to 15, so the overflow handler runs within one wrap
 * period (~312 ms at DIV_128) provided interrupt service is not blocked for
 * that long. This is a required runtime assumption, not proven by host tests.
 * Snapshots briefly mask interrupts, retry high/low/high byte reads, and retry
 * if the hardware overflow flag changes. One pending overflow is added locally;
 * its ISR still owns updating the stored high word after mask restoration.
 *
 * Frame validity. Reject the whole frame for an invalid duration, capacity
 * refusal or negative unaccounted time. Acceptance requires 120 valid frames,
 * zero measured-frame rejections, zero invalid spans/accounting errors, and no
 * capacity refusal (including warmup). Overflow totals survive frame rejection.
 * Timings and report fields are 32-bit; no accepted timing is clamped to 16 bits.
 *
 * Accounting. PERF_SPAN_FRAME is measured between consecutive frame
 * boundaries, so it is the true frame period. PERF_SPAN_UNACCOUNTED is that
 * period minus every non-nested span, which exposes the cost this instrument
 * does not attribute. FRUSTUM and TEXTURE are nested inside CLIPEMIT and are
 * therefore excluded from the accounted sum.
 *
 * Deliberately deferred: splitting the vertex loop into transform, outcode and
 * projection. Per-vertex timer pairs would add ~2,500 clock reads per frame
 * and dominate what they measure. Attribute that split with controlled build
 * variants once this coarse baseline names the next target.
 *
 * Residual known limitation: spans still include interrupt time (audio in
 * VBlank-in, controller in VBlank-out). That cannot be removed without
 * changing the behaviour under test.
 *
 * Field measurement. perf_field_tick() is called from the existing
 * frame_probe_tick() hook in the VBlank-in handler, before any audio work, so
 * audio keeps ownership of that callback. What it measures is the
 * CALLBACK-ENTRY TO CALLBACK-ENTRY period, not the VBlank-in to VBlank-out
 * swap/release latency - the out-edge hook is deliberately deferred until we
 * need that latency. The period is field-periodic either way.
 *
 * Two figures are reported because they answer different questions:
 *  - integer VBlank events counted between frame boundaries, which is what
 *    the field gate actually imposes;
 *  - the frame-period / field-period ratio, which is fractional.
 * A divergence between them is NOT by itself evidence of a bad clock: both
 * derive from the same FRT, and endpoint phase, callback latency and sampling
 * alignment all produce differences. Compare aggregate elapsed counts against
 * aggregate field events before suspecting the clock.
 *
 * Window populations, stated explicitly because they are not identical.
 * Frame aggregates cover ACCEPTED frames only; rejected attempts are excluded.
 * Field callbacks are counted from the moment of arming, which spans accepted
 * and rejected attempts alike. Rather than silently averaging two different
 * populations, callbacks landing in rejected attempts are accumulated
 * separately and reported; a nonzero value fails the run, so an accepted
 * report always has the two populations aligned. Partial endpoint intervals
 * are excluded deliberately. Statistics are frozen at the closing boundary,
 * inside the same critical section that closes the window, so callbacks
 * arriving afterwards cannot alter the report.
 *
 * Calibration must succeed to be believed: zero usable samples, any zero
 * period, or any oversized period fails the run rather than producing an
 * unbacked ratio next to an accepted verdict.
 *
 * Raw FRT counts are primary. This establishes a RATIO only. Converting to
 * milliseconds or to any "FPS headroom remaining" figure additionally requires
 * a verified field frequency, which this instrument does not supply and which
 * the emulator's own reported FPS is not.
 */

enum {
        PERF_SPAN_FRAME = 0,    /* whole frame, boundary to boundary */
        PERF_SPAN_VERTEX,       /* per-vertex transform, outcode, projection */
        PERF_SPAN_FACECULL,     /* face visibility and far-cull pass */
        PERF_SPAN_SORT,         /* sort_faces */
        PERF_SPAN_CLIPEMIT,     /* whole clip + command emit loop */
        PERF_SPAN_FRUSTUM,      /* nested in CLIPEMIT: kokiri_clip_frustum */
        PERF_SPAN_TEXTURE,      /* nested in CLIPEMIT: kokiri_clip_texture */
        PERF_SPAN_UPLOAD,       /* vdp1_sync_cmdt_list_put */
        PERF_SPAN_RENDER,       /* vdp1_sync_render issue */
        PERF_SPAN_VDP1WAIT,     /* vdp1_sync + vdp1_sync_wait */
        PERF_SPAN_VBLANK,       /* vdp2_sync + vdp2_sync_wait */
        PERF_SPAN_UNACCOUNTED,  /* derived: frame minus the non-nested spans */
        PERF_SPAN_DISPLAYED,
        PERF_SPAN_SCRATCH = PERF_SPAN_DISPLAYED, /* overhead probe, not shown */
        PERF_SPAN_COUNT
};

enum {
        PERF_COUNT_VISIBLE = 0,      /* faces surviving cull */
        PERF_COUNT_COMMANDS,         /* drawable commands (setup pair excluded) */
        PERF_COUNT_TILES,            /* scratch tiles resampled */
        PERF_COUNT_PROJECTED,        /* vertices that took the project path */
        PERF_COUNT_FRUSTUM_CALLS,    /* kokiri_clip_frustum invocations */
        PERF_COUNT_OVF_COMMANDS,     /* command-capacity refusals - fails run */
        PERF_COUNT_OVF_TILES,        /* scratch-tile fallbacks - fails run */
        PERF_COUNT_COUNT
};

#ifdef PERF_BENCH

void perf_bench_init(void);
/* Call from the VBlank-in path only (via frame_probe_tick). */
void perf_field_tick(void);
void perf_span_begin(unsigned id);
void perf_span_end(unsigned id);
void perf_count_add(unsigned id, uint32_t n);
void perf_frame_end(void);

#define PERF_SPAN_BEGIN(id)  perf_span_begin(id)
#define PERF_SPAN_END(id)    perf_span_end(id)
#define PERF_COUNT_ADD(id,n) perf_count_add((id),(n))
#define PERF_FRAME_END()     perf_frame_end()
#define PERF_BENCH_INIT()    perf_bench_init()
#define PERF_FIELD_TICK()    perf_field_tick()

#else

#define PERF_SPAN_BEGIN(id)  ((void)0)
#define PERF_SPAN_END(id)    ((void)0)
#define PERF_COUNT_ADD(id,n) ((void)0)
#define PERF_FRAME_END()     ((void)0)
#define PERF_BENCH_INIT()    ((void)0)
#define PERF_FIELD_TICK()    ((void)0)

#endif
#endif
