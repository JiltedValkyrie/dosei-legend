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
    FRAME_PHASE_MOVEMENT = 0,   /* recomp_update: input, collision, gravity */
    FRAME_PHASE_SKINNING,       /* link_anim_pose */
    FRAME_PHASE_SCENE,          /* forest culling and submission */
    FRAME_PHASE_LINK,           /* Link submission */
    FRAME_PHASE_SYNC,           /* waiting for VDP1/VBlank */
    FRAME_PHASE_VDP1,           /* VDP1 still drawing when we came back */
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

/*
** Sample whether VDP1's command address MOVED between two adjacent reads.
**
** This is deliberately NOT called "busy". It cannot distinguish busy from
** idle, for three reasons:
**   - Two adjacent reads can both land inside one long-running command, so
**     COPR unchanged does not mean the draw finished.
**   - The sample happens AFTER the sync wait, so any draw that actually
**     delayed sync may already have completed by the time it is read.
**   - Even a positive reading proves only that some command advanced, not how
**     much of the wait was spent blocked on VDP1.
**
** Answering "CPU or fill?" needs completion measured DURING the wait and tied
** to the specific submitted list -- EDSR's CEF reports draw-end fetched, which
** is the right signal. Until that exists this number is reported as
** "COPR changed", and no CPU-versus-fill verdict is drawn from it.
*/
void            frame_timer_sample_vdp1(void);

/* Raw extended tick count and conversion, for one-off benchmarks (oot-core
** Phase 0). Same wrap rule: reads must be under 293 ms apart. */
unsigned int    frame_timer_ticks(void);
unsigned int    frame_timer_ticks_to_us(unsigned int ticks);
unsigned int    frame_timer_copr_changed(void);

/*
** Raw 16-bit FRC of the CALLING CPU (each SH-2 has its own FRT; slave-safe).
**
** The FRT is an 8-bit module: read FRCH (which latches FRCL into TEMP), then
** FRCL. Never read 0xFFFFFE12 as a word. Mednafen returns only FRC >> 8 for a
** word read, which made the extended count jump 293 ms at every wrap of that
** byte and fired the slave prepare watchdog (2026-10-12). An interrupt that
** reads FRCH between our two bytes re-latches TEMP, so re-read FRCH and retry
** if the high byte moved.
*/
static inline uint16_t frame_timer_frc(void)
{
    volatile uint8_t *frch = (volatile uint8_t *)0xFFFFFE12;
    volatile uint8_t *frcl = (volatile uint8_t *)0xFFFFFE13;
    for (;;) {
        uint8_t high = *frch, low = *frcl, again = *frch;
        (void)*frcl;
        if (high == again) return (uint16_t)((high << 8) | low);
    }
}

/*
** Slave FRT prescaler. SGL never sets the slave's TCR, so it counts at clock/8
** and wraps every 18.3 ms; longer slave jobs lost whole wraps. Call at the
** start of each slave job: selects /128 (293 ms wrap, same units as the
** master). Keeps IEDG (bit 7): SGL wakes the slave by FRT input capture.
*/
static inline void frame_timer_slave_prescale(void)
{
    volatile uint8_t *tcr = (volatile uint8_t *)0xFFFFFE16;
    uint8_t value = *tcr;
    if ((value & 3u) != 2u) *tcr = (uint8_t)((value & ~3u) | 2u);
}

#endif
