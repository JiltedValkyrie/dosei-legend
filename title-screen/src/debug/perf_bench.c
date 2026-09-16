/* Fixed-pose frame profiler. See perf_bench.h for the validity argument. */
#include "perf_bench.h"

#ifdef PERF_BENCH

#include <yaul.h>
#include <cpu/frt.h>
#include "frame_probe.h"

/* Frames discarded before measuring, then valid frames required. */
#define PERF_WARMUP_FRAMES 30
#define PERF_WINDOW_FRAMES 120
/* Give up rather than spin forever if frames keep being rejected. */
#define PERF_MAX_ATTEMPTS  600
/* Reject runs with a span/frame above ~571 ms. This is a chosen benchmark
 * limit, not a claim about expected performance or proof of clock validity. */
#define PERF_SANITY_COUNTS 120000u
#define PERF_OVERHEAD_ITERATIONS 64

/* High word of the extended clock, advanced only by the FRT overflow
 * interrupt. volatile: read in normal code, written in interrupt context. */
static volatile uint32_t frt_high;

static uint32_t span_start[PERF_SPAN_COUNT];
static uint32_t span_frame[PERF_SPAN_COUNT];
static uint32_t span_sum[PERF_SPAN_COUNT];
static uint32_t span_min[PERF_SPAN_COUNT];
static uint32_t span_max[PERF_SPAN_COUNT];

static uint32_t count_frame[PERF_COUNT_COUNT];
static uint32_t count_sum[PERF_COUNT_COUNT];
static uint16_t count_max[PERF_COUNT_COUNT];
static uint32_t overflow_total[2];
static uint32_t overflow_max[2];

static uint32_t prev_boundary;
static bool have_boundary;

/* Field measurement, all written from the VBlank-in callback. The first
 * interval after arming is partial (arming happens mid-field), so it is
 * discarded rather than averaged in. */
static volatile uint32_t field_prev;
static volatile bool field_have_prev;
static volatile bool field_armed;
static volatile uint32_t field_sum;
static volatile uint32_t field_min;
static volatile uint32_t field_max;
static volatile uint32_t field_samples;
/* Events seen since the last frame boundary, and their aggregates. */
static volatile uint32_t field_events;
static uint32_t frame_events_sum;
static uint32_t frame_events_min;
static uint32_t frame_events_max;
/* Aggregate elapsed counts spanned by the counted field events, so the
 * integer and ratio views can be reconciled against the same window. */
static uint32_t field_window_counts;
static uint32_t field_window_events;
/* Field events falling in REJECTED attempts. Frame aggregates exclude
 * rejected frames, so counting their callbacks into the same field window
 * would compare two different populations. Reported separately; must be zero
 * for an accepted run, which is implied by frames_rejected == 0. */
static uint32_t field_events_rejected;
/* Persistent calibration diagnostics. A dropped or zero period must never be
 * silently discarded: without usable samples the ratio is meaningless, so
 * these also gate acceptance. */
static volatile uint32_t field_oversized;
static volatile uint32_t field_zero;
/* Field statistics frozen at the closing boundary, so the report cannot
 * include callbacks that arrive after the window closed. */
static uint32_t field_sum_final;
static uint32_t field_min_final;
static uint32_t field_max_final;
static uint32_t field_samples_final;
static uint16_t warmup_left = PERF_WARMUP_FRAMES;
static uint16_t frames_valid;
static uint16_t frames_rejected;
static uint16_t attempts;
static uint16_t invalid_spans;
static uint16_t negative_unaccounted;
static uint16_t overhead_per_pair;
static bool frame_invalid;
static bool run_failed;
static bool done;

static void perf_frt_ovi(void)
{
        frt_high += 0x10000u;
}

/* Register hooks let host tests inject carries at individual bus reads. */
#ifndef PERF_FRT_HIGH
#define PERF_FRT_HIGH() (((volatile cpu_ioregs_t *)CPU_IOREG_BASE)->frch)
#define PERF_FRT_LOW() (((volatile cpu_ioregs_t *)CPU_IOREG_BASE)->frcl)
#define PERF_FRT_STATUS() (((volatile cpu_ioregs_t *)CPU_IOREG_BASE)->ftcsr)
#endif

/* Briefly exclude the overflow ISR while snapshotting its high word. A
 * pending overflow contributes one wrap without consuming the flag: the ISR
 * will account for it when the original interrupt mask is restored. Byte and
 * status retries handle carries during the snapshot. Requires overflow service
 * at least once per 312 ms; this function never waits for interrupt service. */
/* Clock read for callers that already hold interrupts masked. Splitting this
 * out lets a boundary take its timestamp and its event snapshot inside ONE
 * critical section: with two sections, a callback landing between them is
 * counted against the earlier timestamp. */
static uint32_t perf_now_locked(void)
{
        const uint32_t high = frt_high;
        uint8_t before, after, hi, lo, hi_after;
        do {
                before = PERF_FRT_STATUS() & 2;
                do {
                        hi = PERF_FRT_HIGH();
                        lo = PERF_FRT_LOW();
                        hi_after = PERF_FRT_HIGH();
                } while (hi != hi_after);
                after = PERF_FRT_STATUS() & 2;
        } while (before != after);
        return high + (after ? 0x10000u : 0) + ((uint32_t)hi << 8) + lo;
}

static uint32_t perf_now(void)
{
        const uint8_t mask = cpu_intc_mask_get();
        cpu_intc_mask_set(15);
        const uint32_t result = perf_now_locked();
        cpu_intc_mask_set(mask);
        return result;
}

/* VBlank-in callback entry. Measures callback-entry to callback-entry, which
 * is the field period; it is not the VBlank-in to VBlank-out swap latency. */
void perf_field_tick(void)
{
        if (done || !field_armed) return;
        const uint32_t now = perf_now();
        field_events++;
        if (field_have_prev) {
                const uint32_t period = now - field_prev;
                if (period == 0) {
                        field_zero++;
                } else if (period > PERF_SANITY_COUNTS) {
                        field_oversized++;
                } else {
                        field_sum += period;
                        field_samples++;
                        if (period < field_min) field_min = period;
                        if (period > field_max) field_max = period;
                }
        } else {
                /* Discard the first, partial interval. */
                field_have_prev = true;
        }
        field_prev = now;
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
                /* Reject the whole frame, not just this span: a frame with one
                 * bad span has an unknown total and must not enter the mean. */
                invalid_spans++;
                frame_invalid = true;
                return;
        }
        span_frame[id] += delta;
}

void perf_count_add(unsigned id, uint32_t n)
{
        if (done) return;
        count_frame[id] += n;
        if (n && (id == PERF_COUNT_OVF_COMMANDS || id == PERF_COUNT_OVF_TILES)) {
                /* A capacity refusal changes the geometry actually drawn, so
                 * this frame is not comparable and neither is the run. */
                frame_invalid = true;
                run_failed = true;
                const unsigned index = id - PERF_COUNT_OVF_COMMANDS;
                overflow_total[index] += n;
                if (count_frame[id] > overflow_max[index])
                        overflow_max[index] = count_frame[id];
        }
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
        /* Independent of frame_probe_time_init; re-init is harmless. */
        cpu_frt_init(CPU_FRT_CLOCK_DIV_128);
        cpu_frt_ovi_set(perf_frt_ovi);
        for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) span_min[i] = UINT32_MAX;
        field_min = UINT32_MAX;
        perf_measure_overhead();
}

static uint16_t clamp16(uint32_t v)
{
        return v > 0xFFFF ? 0xFFFF : (uint16_t)v;
}

static void report32(uint32_t value, unsigned x, unsigned row)
{
        frame_probe_hex((uint16_t)(value >> 16), x, 4, row);
        frame_probe_hex((uint16_t)value, x + 32, 4, row);
}

static void perf_report(void)
{
        const uint16_t frames = frames_valid ? frames_valid : 1;
        /* Rows 1..PERF_SPAN_DISPLAYED: min, mean, max per span. */
        for (unsigned i = 0; i < PERF_SPAN_DISPLAYED; i++) {
                report32(frames_valid ? span_min[i] : 0, 4, i + 1);
                report32(span_sum[i] / frames, 76, i + 1);
                report32(span_max[i], 148, i + 1);
        }
        const unsigned status = PERF_SPAN_DISPLAYED + 1;
        /* Acceptance row: valid frames, rejected frames, invalid spans. */
        frame_probe_hex(frames_valid, 4, 4, status);
        frame_probe_hex(frames_rejected, 44, 4, status);
        frame_probe_hex(invalid_spans, 84, 4, status);
        /* Diagnostics row: overhead per span pair, clock wraps observed,
         * negative-unaccounted frames, and the run verdict (0 = accepted). */
        frame_probe_hex(overhead_per_pair, 4, 4, status + 1);
        frame_probe_hex(clamp16(frt_high >> 16), 44, 4, status + 1);
        frame_probe_hex(negative_unaccounted, 84, 4, status + 1);
        frame_probe_hex(run_failed ? 0xFFFF : 0, 124, 4, status + 1);
        /* Field rows. Raw FRT counts are primary; the ratio is reported as
         * a fixed-point x256 integer so no millisecond conversion is implied.
         * Row A: field period min / mean / max (callback entry to entry).
         * Row B: field samples, integer VBlank events per frame min/mean/max.
         * Row C: aggregate elapsed counts and aggregate field events over the
         *        same window, then frame/field ratio x256. Reconcile the
         *        integer and ratio views against these aggregates before
         *        suspecting the clock - both come from the same FRT, and
         *        endpoint phase, callback latency and sampling alignment all
         *        shift them relative to each other. */
        /* Placed in the right-hand column beside the span rows rather than
         * appended below: 21 stacked rows would need a 10px pitch, and at a
         * 10px glyph height the rows would touch, which makes transcribing
         * digits off a screenshot harder than it already is. */
        const unsigned field_row = 1;
        const unsigned fx = 232;
        const uint32_t fsamples = field_samples_final;
        report32(fsamples ? field_min_final : 0, fx, field_row);
        report32(fsamples ? field_sum_final / fsamples : 0, fx, field_row + 1);
        report32(field_max_final, fx, field_row + 2);
        report32(fsamples, fx, field_row + 3);
        frame_probe_hex(clamp16(frames_valid ? frame_events_min : 0), fx, 4, field_row + 4);
        frame_probe_hex(clamp16(frames_valid ? frame_events_sum / frames : 0), fx + 40, 4, field_row + 4);
        frame_probe_hex(clamp16(frame_events_max), fx, 4, field_row + 5);
        report32(field_window_counts, fx, field_row + 6);
        report32(field_window_events, fx, field_row + 7);
        {
                const uint32_t mean_field = fsamples ? field_sum_final / fsamples : 0;
                const uint32_t mean_frame = frames_valid ? span_sum[PERF_SPAN_FRAME] / frames : 0;
                report32(mean_field ? (mean_frame * 256u) / mean_field : 0, fx, field_row + 8);
        }
        /* Field diagnostics row: oversized periods, zero periods, and field
         * events that fell in rejected attempts. All must read zero. */
        report32(field_oversized, fx, field_row + 9);
        report32(field_zero, fx, field_row + 10);
        report32(field_events_rejected, fx, field_row + 11);
        /* Workload counters: valid-frame mean/max. Overflow diagnostics:
         * run-wide total/max, including warmup and rejected frames. */
        for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) {
                const unsigned row = status + 2 + i / 2;
                const unsigned x = (i & 1) ? 168 : 4;
                if (i >= PERF_COUNT_OVF_COMMANDS) {
                        const unsigned index = i - PERF_COUNT_OVF_COMMANDS;
                        report32(overflow_total[index], x, row);
                        report32(overflow_max[index], x + 72, row);
                } else {
                        frame_probe_hex(clamp16(count_sum[i] / frames), x, 4, row);
                        frame_probe_hex(count_max[i], x + 40, 4, row);
                }
        }
}

void perf_frame_end(void)
{
        if (done) return;

        /* One critical section: timestamp, event snapshot and the arm/close
         * transition must agree about which callbacks belong to this frame. */
        uint32_t boundary;
        uint32_t events_this_frame;
        const bool arming_now = warmup_left == 1;
        const bool closing_now =
            (frames_valid + 1 >= PERF_WINDOW_FRAMES) || (attempts + 1 >= PERF_MAX_ATTEMPTS);
        {
                const uint8_t mask = cpu_intc_mask_get();
                cpu_intc_mask_set(15);
                boundary = perf_now_locked();
                events_this_frame = field_events;
                field_events = 0;
                if (arming_now) {
                        /* Arm inside the section so no callback is attributed
                         * to a window it precedes. */
                        field_have_prev = false;
                        field_armed = true;
                }
                if (closing_now) {
                        field_armed = false;
                        field_sum_final = field_sum;
                        field_min_final = field_min;
                        field_max_final = field_max;
                        field_samples_final = field_samples;
                }
                cpu_intc_mask_set(mask);
        }
        if (have_boundary) {
                const uint32_t period = boundary - prev_boundary;
                if (period > PERF_SANITY_COUNTS) {
                        invalid_spans++;
                        frame_invalid = true;
                } else {
                        span_frame[PERF_SPAN_FRAME] = period;
                }
        } else {
                /* No previous boundary yet, so this frame has no period. */
                frame_invalid = true;
                have_boundary = true;
        }
        prev_boundary = boundary;

        if (!warmup_left && !frame_invalid) {
                const uint32_t accounted =
                    span_frame[PERF_SPAN_VERTEX] + span_frame[PERF_SPAN_FACECULL] +
                    span_frame[PERF_SPAN_SORT] + span_frame[PERF_SPAN_CLIPEMIT] +
                    span_frame[PERF_SPAN_UPLOAD] + span_frame[PERF_SPAN_RENDER] +
                    span_frame[PERF_SPAN_VDP1WAIT] + span_frame[PERF_SPAN_VBLANK];
                if (span_frame[PERF_SPAN_FRAME] < accounted) {
                        negative_unaccounted++;
                        frame_invalid = true;
                } else {
                        span_frame[PERF_SPAN_UNACCOUNTED] =
                            span_frame[PERF_SPAN_FRAME] - accounted;
                }
        }
        if (warmup_left) {
                warmup_left--;
        } else if (frame_invalid) {
                frames_rejected++;
                field_events_rejected += events_this_frame;
                attempts++;
        } else {
                for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) {
                        const uint32_t v = span_frame[i];
                        span_sum[i] += v;
                        if (v < span_min[i]) span_min[i] = v;
                        if (v > span_max[i]) span_max[i] = v;
                }
                for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) {
                        const uint32_t v = count_frame[i];
                        count_sum[i] += v;
                        const uint16_t c = clamp16(v);
                        if (c > count_max[i]) count_max[i] = c;
                }
                if (!frames_valid || events_this_frame < frame_events_min)
                        frame_events_min = events_this_frame;
                if (events_this_frame > frame_events_max)
                        frame_events_max = events_this_frame;
                frame_events_sum += events_this_frame;
                field_window_counts += span_frame[PERF_SPAN_FRAME];
                field_window_events += events_this_frame;
                frames_valid++;
                attempts++;
        }

        frame_invalid = false;
        for (unsigned i = 0; i < PERF_SPAN_COUNT; i++) span_frame[i] = 0;
        for (unsigned i = 0; i < PERF_COUNT_COUNT; i++) count_frame[i] = 0;

        if (frames_valid >= PERF_WINDOW_FRAMES || attempts >= PERF_MAX_ATTEMPTS) {
                run_failed |= frames_valid != PERF_WINDOW_FRAMES ||
                    frames_rejected != 0 || invalid_spans != 0 ||
                    negative_unaccounted != 0;
                /* Calibration must actually have produced usable samples.
                 * Zero samples previously passed silently, which made the
                 * ratio unbacked while the verdict still read accepted. */
                run_failed |= field_samples_final == 0 ||
                    field_oversized != 0 || field_zero != 0 ||
                    field_events_rejected != 0;
                /* Draw once, then stop timing and stop drawing. Rendering
                 * continues in main; only this instrument goes quiet, so the
                 * report stays readable. */
                done = true;
                perf_report();
        }
}

#endif
