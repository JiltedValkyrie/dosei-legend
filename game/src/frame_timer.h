#ifndef FRAME_TIMER_H
#define FRAME_TIMER_H
#include <stdint.h>

/*
** Per-phase frame timing on the SH-2 Free Running Timer.
**
** The FRT is a 16-bit counter on the on-chip register block at 0xFFFFFE00.
** Two things make a naive reading wrong, and both cost real debugging time:
**
**  1. WRAPPING. At the /8 prescaler the counter wraps every 18.3 ms, so a
**     125 ms frame (8 FPS) wraps several times and a 16-bit difference silently
**     reports the remainder. The largest raw number could be the smallest
**     real cost. This file sets the prescaler to /128 explicitly -- 293 ms per
**     wrap at NTSC 320 clocks -- and extends the
**     counter to 32 bits by accumulating wraps on every read.
**
**  2. COVERAGE. Timing only the phases we suspect cannot explain a frame:
**     whatever is left over is invisible. frame_timer_frame() measures the
**     whole callback and frame_timer_other() reports what none of the named
**     phases accounted for, so the unmeasured remainder is always on screen.
**
** Reads MUST be less than one wrap apart. Longer stalls are not measured
** reliably. frame_timer_frame_begin() reads once per callback, and each
** measured phase also reads. Do not interpret initial loading stalls as valid.
**
** Units are microseconds at the /128 prescaler, so the figures are directly
** comparable with the 16.7 ms frame budget.
*/

typedef enum
{
    FRAME_PHASE_MOVEMENT = 0,   /* demo_update: input, collision, gravity */
    FRAME_PHASE_SKINNING,       /* link_anim_pose */
    FRAME_PHASE_SCENE,          /* forest culling and submission */
    FRAME_PHASE_LINK,           /* Link submission */
    FRAME_PHASE_SYNC,           /* waiting for VDP1/VBlank */
    FRAME_PHASE_PREP,           /* forest CPU culling/fog before SGL */
    FRAME_PHASE_DEPTH,
    FRAME_PHASE_PARTITION,
    FRAME_PHASE_FOG,
    FRAME_PHASE_COUNT
}               frame_phase_t;

void            frame_timer_init(void);
void            frame_timer_frame_begin(void);
void            frame_timer_frame_end(void);
void            frame_timer_begin(frame_phase_t phase);
void            frame_timer_end(frame_phase_t phase);

/* All in microseconds, smoothed. */
unsigned int    frame_timer_cost(frame_phase_t phase);
unsigned int    frame_timer_frame(void);
/* Callback minus disjoint outer phases (not nested skin/prep or sync). */
unsigned int    frame_timer_other(void);

#endif
