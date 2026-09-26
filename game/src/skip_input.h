#ifndef DOSEI_SKIP_INPUT_H
#define DOSEI_SKIP_INPUT_H
#include "input_edge.h"

/* Sample at VBlank so two taps survive a slow rendered frame. Clock is 60 Hz
 * on both PAL and NTSC. Producer owns timing; consumer owns consumed count. */
typedef struct {
    input_edge_t request;
    volatile bool armed;
    volatile unsigned int request_shot;
    bool held;
    unsigned int first_tick, shot;
} skip_input_t;

static inline void skip_input_sample(skip_input_t *s, bool enabled, bool held,
                                     unsigned int tick, unsigned int shot)
{
    if (!enabled || shot != s->shot) s->armed = false;
    s->shot = shot;
    if (s->armed && tick - s->first_tick > 120u) s->armed = false;
    if (enabled && held && !s->held) {
        if (s->armed) {
            s->request_shot = shot;
            ++s->request.produced;
            s->armed = false;
        } else {
            s->first_tick = tick;
            s->armed = true;
        }
    }
    s->held = held;
}
#endif
