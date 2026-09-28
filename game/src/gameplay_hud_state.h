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

/* Match existing A-handler prompt precedence; never advertise an unbound action. */
static inline unsigned int gameplay_hud_action(bool enter, bool chest, bool talk)
{
    return enter ? 3u : chest ? 2u : talk ? 1u : 0u;
}
#endif
