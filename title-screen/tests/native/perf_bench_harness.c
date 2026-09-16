/* Exercise the actual profiler with controlled register/interrupt reads. Each
 * scenario runs in a new process, just like a fresh console boot. */
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <stdio.h>

static uint32_t timer;
static uint8_t mask;
static bool pending;
static unsigned reads, inject_at;
static uint32_t inject_ticks;
static void (*overflow_handler)(void);
static uint16_t drawn[20][320];
static unsigned draw_calls;
static uint8_t read_register(unsigned kind);
#define PERF_BENCH 1
#define PERF_FRT_HIGH() read_register(0)
#define PERF_FRT_LOW() read_register(1)
#define PERF_FRT_STATUS() read_register(2)
#include "../../src/debug/perf_bench.c"

uint8_t cpu_intc_mask_get(void) { return mask; }
void cpu_intc_mask_set(uint8_t value)
{
        mask = value;
        if (pending && mask < 15 && overflow_handler) {
                pending = false;
                overflow_handler();
        }
}
void cpu_frt_init(uint8_t divisor) { assert(divisor == 2); timer = 0; }
void cpu_frt_ovi_set(void (*handler)(void)) { overflow_handler = handler; }
static void advance(uint32_t ticks)
{
        const uint32_t wraps = ((timer & 65535u) + ticks) >> 16;
        timer += ticks;
        for (uint32_t i = 0; i < wraps; i++) {
                if (mask < 15 && overflow_handler) overflow_handler();
                else pending = true;
        }
}
static uint8_t read_register(unsigned kind)
{
        assert(mask == 15); /* ISR cannot run between snapshot register reads. */
        if (++reads == inject_at) advance(inject_ticks);
        if (kind == 0) return (uint8_t)(timer >> 8);
        if (kind == 1) return (uint8_t)timer;
        return pending ? 2 : 0;
}
void frame_probe_hex(uint16_t value, unsigned x, unsigned digits, unsigned row)
{
        assert(digits == 4 && row < 20 && x + digits * 8 <= 320);
        drawn[row][x] = value;
        draw_calls++;
}
static uint32_t report_value(unsigned row, unsigned x)
{
        return ((uint32_t)drawn[row][x] << 16) | drawn[row][x + 32];
}
static void begin_window(void)
{
        warmup_left = 0;
        have_boundary = true;
        prev_boundary = perf_now();
        /* Arm the field window as the last warmup boundary would, and seed a
         * predecessor so the first measured interval is not the discarded
         * partial one. Scenarios that deliver no callbacks at all are
         * expected to fail acceptance - see field_absent. */
        field_armed = true;
        field_have_prev = false;
}
static void frame(uint32_t ticks)
{
        advance(ticks);
        perf_frame_end();
}
/* VBlank-in callback arrival. */
static void tick(uint32_t ticks)
{
        advance(ticks);
        perf_field_tick();
}
/* A frame of `ticks` with `n` evenly spaced field callbacks inside it. */
static void frame_with_ticks(uint32_t ticks, unsigned n)
{
        for (unsigned i = 0; i < n; i++) tick(ticks / (n + 1));
        frame(ticks - (ticks / (n + 1)) * n);
}
/* Warmup that also delivers callbacks, so arming has a real predecessor. */
static void warmup_with_ticks(uint32_t ticks, unsigned n)
{
        for (unsigned i = 0; i < 30; i++) frame_with_ticks(ticks, n);
}
int main(int argc, char **argv)
{
        assert(argc == 2);
        perf_bench_init();
        reads = 0;
        if (!strcmp(argv[1], "byte_carry")) {
                timer = 0x12FF;
                inject_at = 3; inject_ticks = 1;
                assert(perf_now() == 0x1300);
                assert(frt_high == 0 && mask == 0);
        } else if (!strcmp(argv[1], "full_carry")) {
                timer = 65535;
                inject_at = 3; inject_ticks = 1;
                assert(perf_now() == 65536);
                assert(frt_high == 65536 && !pending);
                assert(perf_now() == 65536); /* no double count after ISR */
        } else if (!strcmp(argv[1], "pending")) {
                mask = 15; advance(65540);
                assert(perf_now() == 65540 && frt_high == 0 && mask == 15);
                cpu_intc_mask_set(0);
                assert(perf_now() == 65540 && frt_high == 65536);
        } else if (!strcmp(argv[1], "status_carry")) {
                timer = 65535;
                inject_at = 5; inject_ticks = 1;
                assert(perf_now() == 65536);
        } else if (!strcmp(argv[1], "multiple_wraps")) {
                advance(200000);
                assert(perf_now() == 200000 && frt_high == 196608);
        } else if (!strcmp(argv[1], "wide_report")) {
                begin_window();
                tick(0);
                for (unsigned i = 0; i < 120; i++) frame_with_ticks(70000, 1);
                assert(done && !run_failed && frames_valid == 120);
                assert(report_value(1,4) == 70000);
                assert(report_value(1,76) == 70000);
                assert(report_value(1,148) == 70000);
                unsigned calls = draw_calls;
                frame_with_ticks(70000, 1);
                assert(draw_calls == calls);
        } else if (!strcmp(argv[1], "nested")) {
                begin_window();
                perf_span_begin(PERF_SPAN_CLIPEMIT);
                advance(100);
                perf_span_begin(PERF_SPAN_TEXTURE);
                advance(200);
                perf_span_end(PERF_SPAN_TEXTURE);
                advance(100);
                perf_span_end(PERF_SPAN_CLIPEMIT);
                frame(600);
                assert(span_sum[PERF_SPAN_FRAME] == 1000);
                assert(span_sum[PERF_SPAN_CLIPEMIT] == 400);
                assert(span_sum[PERF_SPAN_TEXTURE] == 200);
                assert(span_sum[PERF_SPAN_UNACCOUNTED] == 600);
        } else if (!strcmp(argv[1], "invalid_span")) {
                begin_window();
                perf_span_begin(PERF_SPAN_VERTEX);
                advance(130000);
                perf_span_end(PERF_SPAN_VERTEX);
                perf_frame_end();
                assert(frames_valid == 0 && frames_rejected == 1 && invalid_spans);
                for (unsigned i = 0; i < 120; i++) frame(1000);
                assert(done && run_failed && span_sum[PERF_SPAN_FRAME] == 120000);
        } else if (!strcmp(argv[1], "negative")) {
                begin_window();
                span_frame[PERF_SPAN_VERTEX] = 2000;
                frame(1000);
                assert(negative_unaccounted == 1 && frames_rejected == 1 && !frames_valid);
                for (unsigned i = 0; i < 120; i++) frame(1000);
                assert(run_failed);
        } else if (!strcmp(argv[1], "attempt_cap")) {
                begin_window();
                for (unsigned i = 0; i < 600; i++) frame(130000);
                assert(done && run_failed && frames_valid == 0 && frames_rejected == 600);
                assert(drawn[14][124] == 65535);
        } else if (!strcmp(argv[1], "overflow")) {
                begin_window();
                perf_count_add(PERF_COUNT_OVF_COMMANDS,1);
                perf_count_add(PERF_COUNT_OVF_TILES,3);
                frame(1000);
                assert(frames_rejected == 1 && overflow_total[0] == 1 && overflow_total[1] == 3);
                for (unsigned i = 0; i < 120; i++) frame(1000);
                assert(done && run_failed);
                assert(report_value(17,168) == 1 && report_value(17,240) == 1);
                assert(report_value(18,4) == 3 && report_value(18,76) == 3);
        } else if (!strcmp(argv[1], "warmup")) {
                for (unsigned i = 0; i < 30; i++) frame_with_ticks(1000, 1);
                assert(!warmup_left && !frames_valid && !frames_rejected && !draw_calls);
                assert(field_armed); /* armed on the last warmup boundary */
                for (unsigned i = 0; i < 120; i++) frame_with_ticks(2000, 1);
                assert(done && !run_failed && span_sum[PERF_SPAN_FRAME] == 240000);
        } else if (!strcmp(argv[1], "field_boundary_pending")) {
                /* A callback pending across the boundary snapshot must be
                 * attributed to exactly one frame, never double counted nor
                 * credited against the earlier timestamp. */
                warmup_with_ticks(3000, 2);
                assert(field_armed);
                tick(1000); /* first post-arm callback: seeds, records nothing */
                assert(field_have_prev && field_samples == 0);
                const uint32_t before = field_events;
                tick(500);
                assert(field_events == before + 1);
                frame(500);
                assert(field_events == 0); /* cleared in the same section */
                for (unsigned i = 0; i < 119; i++) frame_with_ticks(3000, 2);
                assert(done && frames_valid == 120);
                assert(field_events_rejected == 0);
        } else if (!strcmp(argv[1], "field_arm_and_close")) {
                /* Arming happens on the last warmup frame; the window closes
                 * at the final boundary and later callbacks cannot alter it. */
                for (unsigned i = 0; i < 29; i++) frame_with_ticks(3000, 2);
                assert(!field_armed);
                frame_with_ticks(3000, 2);
                assert(field_armed);
                for (unsigned i = 0; i < 120; i++) frame_with_ticks(3000, 2);
                assert(done && !field_armed);
                const uint32_t frozen_samples = field_samples_final;
                const uint32_t frozen_sum = field_sum_final;
                tick(1000); tick(1000);
                assert(field_samples_final == frozen_samples);
                assert(field_sum_final == frozen_sum);
        } else if (!strcmp(argv[1], "field_partial_and_wrap")) {
                /* First interval after arming is discarded; a wrap inside a
                 * field period is measured correctly, not truncated. */
                warmup_with_ticks(3000, 1);
                assert(field_armed);
                const uint32_t samples = field_samples;
                tick(1000);
                assert(field_samples == samples); /* first post-arm is discarded */
                tick(70000);                      /* spans a 16-bit wrap */
                assert(field_samples == samples + 1);
                assert(field_max == 70000);
                assert(field_oversized == 0 && field_zero == 0);
        } else if (!strcmp(argv[1], "field_bad_periods")) {
                /* Zero and oversized periods are counted, not dropped, and
                 * each one fails the run. */
                warmup_with_ticks(3000, 1);
                assert(field_armed);
                tick(1000); /* seed predecessor after arming */
                tick(1000);
                tick(0);
                assert(field_zero == 1);
                tick(130000);
                assert(field_oversized == 1);
                /* The bad periods also reject the frame they land in, so the
                 * window needs more than 120 attempts to close. */
                for (unsigned i = 0; i < 130 && !done; i++) frame_with_ticks(3000, 1);
                assert(done && run_failed);
                assert(field_zero == 1 && field_oversized == 1);
        } else if (!strcmp(argv[1], "field_absent")) {
                /* No callbacks at all: zero samples must fail, not silently
                 * report an unbacked ratio beside an accepted verdict. */
                for (unsigned i = 0; i < 30; i++) frame(1000);
                for (unsigned i = 0; i < 120; i++) frame(1000);
                assert(done && frames_valid == 120);
                assert(field_samples_final == 0);
                assert(run_failed);
        } else if (!strcmp(argv[1], "field_rejected_population")) {
                /* Callbacks landing in a rejected attempt belong to a
                 * different population than the frame aggregates and must be
                 * reported separately, not averaged in. */
                warmup_with_ticks(3000, 1);
                tick(1000); /* seed predecessor after arming */
                span_frame[PERF_SPAN_VERTEX] = 99999;
                frame_with_ticks(3000, 1);
                /* Two, not one: the seeding tick above and this frame's own
                 * callback both fall inside the rejected attempt. The point is
                 * that they are attributed to the rejected population at all,
                 * not averaged into the accepted frame aggregates. */
                assert(frames_rejected == 1 && field_events_rejected == 2);
                for (unsigned i = 0; i < 130 && !done; i++) frame_with_ticks(3000, 1);
                assert(done && run_failed); /* rejected population is nonzero */
                assert(field_window_events >= 100);
        } else return 2;
        puts(argv[1]);
        return 0;
}
