#ifndef FRAME_TIMER_H
#define FRAME_TIMER_H
#include <stdint.h>

/*
** Per-phase frame timing, for attributing a low VDP1 rate to real work.
**
** The SH-2's Free Running Timer is a 16-bit counter on the on-chip register
** block at 0xFFFFFE00 (the same block jo/serial.h uses). It counts continuously
** and is not tied to VBlank, so unlike the vblank tick it can resolve phases
** inside a single frame. It wraps often; every reading here is a 16-bit
** difference, which stays correct across one wrap.
**
** Units are raw FRT counts, not milliseconds: the prescaler is whatever the
** SDK left set, so these are only meaningful RELATIVE to each other. Comparing
** phases against each other is the entire point; do not report them as ms.
*/

#define FRT_COUNTER (*(volatile uint16_t *)0xFFFFFE12)

typedef enum
{
    FRAME_PHASE_MOVEMENT = 0,   /* demo_update: input, collision, gravity */
    FRAME_PHASE_SKINNING,       /* link_anim_pose */
    FRAME_PHASE_SCENE,          /* forest culling and submission */
    FRAME_PHASE_LINK,           /* Link submission */
    FRAME_PHASE_COUNT
}               frame_phase_t;

void            frame_timer_begin(frame_phase_t phase);
void            frame_timer_end(frame_phase_t phase);
/* Smoothed cost of one phase, in raw FRT counts. */
unsigned int    frame_timer_cost(frame_phase_t phase);

#endif
