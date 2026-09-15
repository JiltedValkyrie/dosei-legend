/* Fixed-pose frame profiler. See perf_bench.h for the design constraints. */
#include "perf_bench.h"

#ifdef PERF_BENCH

#include <yaul.h>
#include <cpu/frt.h>
#include "frame_probe.h"

/* Frames discarded before measuring, then frames measured. */
#define PERF_WARMUP_FRAMES 30
#define PERF_WINDOW_FRAMES 120
/* A single span longer than this is treated as invalid rather than kept. The
 * whole frame is ~26000 counts at 8 FPS, so anything approaching the 16-bit
 * wrap is a missed rollover or a hang, not a timing. */
#define PERF_SANITY_COUNTS 60000u
#define PERF_OVERHEAD_ITERATIONS 64

static uint16_t frt_last;
static uint32_t frt_high;

static uint32_t span_start[PERF_SPAN_COUNT];
static uint32_t span_frame[PERF_SPAN_COUNT];
static uint32_t span_sum[PERF_SPAN_COUNT];
static uint16_t span_min[PERF_SPAN_COUNT];
static uint16_t span_max[PERF_SPAN_COUNT];

static uint32_t count_frame[PERF_COUNT_COUNT];
static uint32_t count_sum[PERF_COUNT_COUNT];
static uint16_t count_max[PERF_COUNT_COUNT];

static uint16_t warmup_left = PERF_WARMUP_FRAMES;
static uint16_t frames_measured;
static uint16_t invalid_samples;
static uint16_t overhead_per_pair;
static bool done;

/* Extend the 16-bit FRT to 32 bits. Called at least twice per span and many
 * times per frame, so the gap between reads is far below the ~312 ms wrap;
 * a single rollover between two reads is therefore always detectable. */
static uint32_t perf_now(void)
{
        const uint16_t now = cpu_frt_count_get();
        if (now < frt_last) frt_high += 0x10000u;
        frt_last = now;
        return frt_high | now;
}

void perf_span_begin(unsigned id)
{
        if (done) return;
        span_start[id] = perf_now();
}

void perf_span_end(unsigned id)
{
        if (done) return;
        const uint32_t delta = perf_now() - span_start[id];
        if (delta > PERF_SANITY_COUNTS) {
                invalid_samples++;
                return;
        }
        span_frame[id] += delta;
}

void perf_count_add(unsigned id, uint32_t n)
{
        if (done) return;
        count_frame[id] += n;
}

static void perf_measure_overhead(void)
{
        const uint32_t begin = perf_now();
        for (unsigned i = 0; i < PERF_OVERHEAD_ITERATIONS; i++) {
                perf_span_begin(PERF_SPAN_SCRATCH);
                perf_span_end(PERF_SPAN_SCRATCH);
        }
        const uint32_t elapsed = perf_now() - begin;
        overhead_per_pair = (uint16_t)(elapsed / PERF_OVERHEAD_ITERATIONS);
        span_frame[PERF_SPAN_SCRATCH] = 0;
}

void perf_bench_init(void)
{
        /* Independent of frame_probe_time_init; double init is harmless. */
        cpu_frt_init(CPU_FRT_CLOCK_DIV_128);
        frt_last = cpu_frt_count_get();
        for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) span_min[i] = 0xFFFF;
        perf_measure_overhead();
}

static void perf_report(void)
{
        const uint16_t frames = frames_measured ? frames_measured : 1;
        /* Rows 1..PERF_SPAN_DISPLAYED: min, mean, max per span, 4 hex digits
         * each. Span order is the enum order in perf_bench.h. */
        for (unsigned i = 0; i < PERF_SPAN_DISPLAYED; i++) {
                const uint32_t mean = span_sum[i] / frames;
                frame_probe_hex(span_min[i] == 0xFFFF ? 0 : span_min[i], 4, 4, i + 1);
                frame_probe_hex(mean > 0xFFFF ? 0xFFFF : (uint16_t)mean, 44, 4, i + 1);
                frame_probe_hex(span_max[i], 84, 4, i + 1);
        }
        /* Next row: frames measured, invalid samples, overhead per span pair. */
        const unsigned status_row = PERF_SPAN_DISPLAYED + 1;
        frame_probe_hex(frames_measured, 4, 4, status_row);
        frame_probe_hex(invalid_samples, 44, 4, status_row);
        frame_probe_hex(overhead_per_pair, 84, 4, status_row);
        /* Counter rows: mean then max, in enum order, two counters per row. */
        for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) {
                const uint32_t mean = count_sum[i] / frames;
                const unsigned row = status_row + 1 + i / 2;
                const unsigned x = (i & 1) ? 168 : 4;
                frame_probe_hex(mean > 0xFFFF ? 0xFFFF : (uint16_t)mean, x, 4, row);
                frame_probe_hex(count_max[i], x + 40, 4, row);
        }
}

void perf_frame_end(void)
{
        if (done) return;
        if (warmup_left) {
                warmup_left--;
        } else {
                for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) {
                        const uint32_t v = span_frame[i];
                        span_sum[i] += v;
                        const uint16_t c = v > 0xFFFF ? 0xFFFF : (uint16_t)v;
                        if (c < span_min[i]) span_min[i] = c;
                        if (c > span_max[i]) span_max[i] = c;
                }
                for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) {
                        const uint32_t v = count_frame[i];
                        count_sum[i] += v;
                        const uint16_t c = v > 0xFFFF ? 0xFFFF : (uint16_t)v;
                        if (c > count_max[i]) count_max[i] = c;
                }
                frames_measured++;
        }
        for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) span_frame[i] = 0;
        for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) count_frame[i] = 0;
        if (frames_measured >= PERF_WINDOW_FRAMES) {
                /* Draw once, then freeze: no further timing or drawing. */
                done = true;
                perf_report();
        }
}

#endif
