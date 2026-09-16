#include "frame_timer.h"

/* Exponentially smoothed so a single slow frame does not dominate the
** readout, and so the figures are stable enough to read off screen. */
static uint16_t     started[FRAME_PHASE_COUNT];
static unsigned int smoothed[FRAME_PHASE_COUNT];

void            frame_timer_begin(frame_phase_t phase)
{
    started[phase] = FRT_COUNTER;
}

void            frame_timer_end(frame_phase_t phase)
{
    /* 16-bit subtraction, so one wrap between begin and end is still right. */
    unsigned int elapsed = (uint16_t)(FRT_COUNTER - started[phase]);

    smoothed[phase] += (int)(elapsed - smoothed[phase]) >> 3;
}

unsigned int    frame_timer_cost(frame_phase_t phase)
{
    return smoothed[phase];
}
