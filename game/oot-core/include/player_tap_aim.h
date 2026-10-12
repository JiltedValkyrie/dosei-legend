#ifndef DOSEI_PLAYER_TAP_AIM_H
#define DOSEI_PLAYER_TAP_AIM_H

/* Saturn tap-to-ready / tap-to-fire translated into source Player holds.
 * Run once per source update, never per host/render step. Source Player still
 * owns ready animation, admission, projectile spawn, release and ammo. */
typedef struct {
    unsigned short button;
    unsigned char release, saw_ready, entered;
} PlayerTapAim;

static inline void PlayerTapAim_Step(PlayerTapAim* state, unsigned short* held,
                                    unsigned short* press, unsigned short requested,
                                    int first_person, int ready, int can_rearm, int blocked) {
    if (blocked || (*press & 0xC010u) || (*held & 0x2000u) ||
        (state->entered && !first_person)) {
        state->button = 0;
        state->release = state->saw_ready = state->entered = 0;
        return;
    }
    if (requested && requested != state->button) {
        state->button = requested;
        state->release = state->saw_ready = state->entered = 0;
    } else if (requested && !state->release) {
        state->release = 1;
        state->saw_ready = ready != 0;
    }
    if (!state->button) return;
    if (first_person) state->entered = 1;
    if (state->release == 1) {
        if (ready) state->saw_ready = 1;
        if (state->saw_ready && !ready) state->release = 2;
        else {
            *held &= (unsigned short)~state->button;
            *press &= (unsigned short)~state->button;
            return;
        }
    }
    /* Never synthesize a C press during hook flight: ArmsHook_Shoot treats
     * it as retract. Wait for source ownership to return to Player. */
    if (state->release == 2) {
        if (ready) state->release = 0;
        else if (can_rearm) *press |= state->button;
    }
    *held |= state->button;
}
#endif
