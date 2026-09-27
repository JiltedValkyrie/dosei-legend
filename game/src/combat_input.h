#ifndef COMBAT_INPUT_H
#define COMBAT_INPUT_H
#include "link_anim_state.h"

/* One authoritative X latch from rendered input samples to fixed simulation.
 * Like input_edge, multiple same-kind edges coalesce between simulation steps.
 * A quick tap preserves BOTH edges. This is not a combo-window queue. */
typedef struct { bool pressed, held, released; } combat_buttons_t;
typedef struct { combat_buttons_t pending; bool rearm; } combat_input_t;

static inline void combat_input_cancel(combat_input_t *input)
{
    input->rearm = input->pending.held;
    input->pending.pressed = input->pending.released = false;
}

static inline void combat_input_feed(combat_input_t *input, bool pressed,
                                    bool held, bool released, bool blocked)
{
    input->pending.held = held;
    if (blocked) { combat_input_cancel(input); return; }
    if (input->rearm) {
        if (held && !released) return;
        input->rearm = false;
        released = false; /* release of the cancelled hold cannot spin */
    }
    input->pending.pressed |= pressed;
    input->pending.released |= released;
}

static inline combat_buttons_t combat_input_take(combat_input_t *input)
{
    combat_buttons_t result = input->pending;
    if (input->rearm) result = (combat_buttons_t){0};
    input->pending.pressed = input->pending.released = false;
    return result;
}

/* M1 action owns its movement/pose until it explicitly yields. Combat must
 * not overlay a sword/guard pose on that action. SWIM routes X to a stroke. */
static inline bool combat_input_land_allowed(link_state_t state)
{
    switch (state) {
    case LINK_STATE_STEP_UP: case LINK_STATE_JUMP_START:
    case LINK_STATE_HANG: case LINK_STATE_PULL_UP: case LINK_STATE_CLIMB:
    case LINK_STATE_CRAWL: case LINK_STATE_PUSH: case LINK_STATE_SWIM:
    case LINK_STATE_BONK: case LINK_STATE_SLIDE: case LINK_STATE_SLIDE_END:
        return false;
    default: return true;
    }
}
#endif
