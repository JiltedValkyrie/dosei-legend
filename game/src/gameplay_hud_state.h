#ifndef GAMEPLAY_HUD_STATE_H
#define GAMEPLAY_HUD_STATE_H
#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t last_tick, phase;
    bool calling, eligible;
} gameplay_hud_blink_t;

/* OoT's ten 20 Hz interface updates = thirty 60 Hz ticks per half-cycle.
 * Freeze while the interface is suppressed; never depend on draw rate. */
static inline bool gameplay_hud_blink(gameplay_hud_blink_t *s, uint32_t tick,
                                     bool calling, bool eligible)
{
    if (!calling || !s->calling) s->phase = 0;
    else if (eligible && s->eligible) s->phase = (s->phase + tick - s->last_tick) % 60u;
    s->last_tick = tick;
    s->calling = calling;
    s->eligible = eligible;
    return calling && eligible && s->phase < 30u;
}

/* Match OoT A-handler prompt precedence (gameplay.c:2820-2853); never advertise
 * an unbound action.  Index mapping: 0=none, 1=talk, 2=open/chest, 3=enter,
 * 4=check/sign, 5=grab, 6=drop (carrying), 7=throw (carrying+speed). */
static inline unsigned int gameplay_hud_action(bool enter, bool chest, bool talk,
                                               bool sign, bool grab,
                                               bool carrying, bool throw_ready)
{
    return enter ? 3u : chest ? 2u :
           carrying ? (throw_ready ? 7u : 6u) :
           grab ? 5u : sign ? 4u : talk ? 1u : 0u;
}
#endif
