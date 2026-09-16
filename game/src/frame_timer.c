#include <jo/jo.h>
#include "frame_timer.h"

/* SH-2 on-chip FRT. TCR selects the prescaler; FRC is the counter. */
#define FRT_TIER    (*(volatile uint8_t *)0xFFFFFE10)
#define FRT_FTCSR   (*(volatile uint8_t *)0xFFFFFE11)
#define FRT_FRC     (*(volatile uint16_t *)0xFFFFFE12)
#define FRT_TCR     (*(volatile uint8_t *)0xFFFFFE16)

/* CKS1:0 = 10 selects peripheral clock / 128. At ~14.3 MHz that is 111.9 kHz,
** one tick per 8.94 us, wrapping every 586 ms. A frame at 8 FPS is 125 ms, so
** a single wrap can no longer hide inside one measurement. */
#define FRT_PRESCALER_128   0x02
#define TICKS_PER_US_NUM    894     /* 8.94 us per tick, as 100ths */
#define TICKS_PER_US_DEN    100

static uint16_t     previous_count;
static uint32_t     extended;       /* 32-bit tick count, wraps accounted for */

static uint32_t     started[FRAME_PHASE_COUNT];
static unsigned int smoothed[FRAME_PHASE_COUNT];
static uint32_t     frame_started;
static unsigned int frame_smoothed;

/* Extend the 16-bit counter. Every wrap seen between calls adds 65536, which
** is why this must be called at least once per frame. */
static uint32_t     read_ticks(void)
{
    uint16_t now = FRT_FRC;

    if (now < previous_count)
        extended += 0x10000u;
    previous_count = now;
    return extended + now;
}

static unsigned int to_microseconds(uint32_t ticks)
{
    return (unsigned int)((ticks * TICKS_PER_US_NUM) / TICKS_PER_US_DEN);
}

void            frame_timer_init(void)
{
    FRT_TCR = FRT_PRESCALER_128;
    previous_count = FRT_FRC;
    extended = 0;
}

void            frame_timer_frame_begin(void)
{
    frame_started = read_ticks();
}

void            frame_timer_frame_end(void)
{
    unsigned int elapsed = to_microseconds(read_ticks() - frame_started);

    frame_smoothed += (int)(elapsed - frame_smoothed) >> 3;
}

void            frame_timer_begin(frame_phase_t phase)
{
    started[phase] = read_ticks();
}

void            frame_timer_end(frame_phase_t phase)
{
    unsigned int elapsed = to_microseconds(read_ticks() - started[phase]);

    smoothed[phase] += (int)(elapsed - smoothed[phase]) >> 3;
}

unsigned int    frame_timer_cost(frame_phase_t phase)
{
    return smoothed[phase];
}

unsigned int    frame_timer_frame(void)
{
    return frame_smoothed;
}

unsigned int    frame_timer_other(void)
{
    unsigned int named = 0, i;

    for (i = 0; i < FRAME_PHASE_COUNT; ++i)
        named += smoothed[i];
    /* Nested phases would make this negative; clamp rather than print a huge
    ** unsigned number, and treat 0 as "everything is accounted for". */
    return frame_smoothed > named ? frame_smoothed - named : 0;
}
