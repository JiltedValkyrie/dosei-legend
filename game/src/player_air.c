#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
/*
** Ground departure and the automatic jump. Contract in player_air.h.
**
** Source: ovl_player_actor/z_player.c func_8083AA10, func_8083A4A8, with the
** child Kokiri-boot registers from z_player_lib.c sBootData
** (PLAYER_BOOTS_KOKIRI_CHILD): IREG(66) 540, IREG(67) 750, IREG(68) 125,
** IREG(69) 400.
*/

#include "player_air.h"

/* speedXZ > IREG(66) / 100 = 5.4 selects the fixed launch speed. */
#define LAUNCH_FAST_SPEED_Q8    1382            /* 5.4 * 256, rounded down */
#define LAUNCH_FAST_Q8          (750 * 256 / 100)   /* IREG(67): 7.5 */
#define LAUNCH_BASE_Q8          (125 * 256 / 100)   /* IREG(68): 1.25 */
/* + IREG(69) * speedXZ / 1000 = 0.4 * speed */
#define LAUNCH_PER_SPEED_NUM    400
#define LAUNCH_PER_SPEED_DEN    1000

static int32_t  magnitude(int32_t v)
{
    return v < 0 ? -v : v;
}

player_leave_action_t   player_leave_ground(const player_leave_t *in,
                                            int32_t *velocity_q8)
{
    /* Checked in source order. */
    if (in->prev_floor_property == PLAYER_FLOOR_PROPERTY_8)
        return (PLAYER_LEAVE_REVERT_XZ);
    if (in->prev_floor_property == PLAYER_FLOOR_PROPERTY_7 || in->swinging)
        return (PLAYER_LEAVE_REVERT_STOP);
    if (in->ground_leave &&
        in->prev_floor_property != PLAYER_FLOOR_PROPERTY_6 &&
        in->prev_floor_property != PLAYER_FLOOR_PROPERTY_9 &&
        in->y_dist_to_floor > 20 &&
        magnitude(in->yaw_diff) < 0x2000 &&
        in->speed_q8 > 3 * 256) {
        /* Floor property 11 first tries a run-jump into water more than 50
        ** below (func_808396F4 + the water surface); water is M1k, so that
        ** case takes the ordinary auto-jump for now. */
        if (in->speed_q8 > LAUNCH_FAST_SPEED_Q8)
            *velocity_q8 = LAUNCH_FAST_Q8;
        else
            *velocity_q8 = LAUNCH_BASE_Q8 +
                in->speed_q8 * LAUNCH_PER_SPEED_NUM / LAUNCH_PER_SPEED_DEN;
        return ((magnitude(in->yaw_diff) < 0x1000 && in->speed_q8 > 4 * 256)
                ? PLAYER_LEAVE_RUN_JUMP : PLAYER_LEAVE_JUMP);
    }
    if (in->prev_floor_property == PLAYER_FLOOR_PROPERTY_9 ||
        in->y_dist_to_floor <= PLAYER_CHILD_HANG_DROP)
        return (PLAYER_LEAVE_FALL);
    return (PLAYER_LEAVE_HANG);
}
