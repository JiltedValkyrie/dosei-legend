#ifndef PLAYER_AIR_H
# define PLAYER_AIR_H
# include <stdbool.h>
# include <stdint.h>

/*
** Leaving the ground: z_player.c func_8083AA10 (ground departure) and
** func_8083A4A8 (the automatic jump). Pure integer rules, host tested; the
** caller owns position, velocity and animation.
**
** Units: speed is Q8 world units per 30 Hz step, which equals the source's
** speedXZ value (TRAVERSAL_TIMING.md: velocity keeps its value). Distances
** are world units. Yaws are binang.
*/

/* SurfaceType floorProperty values the departure rules test. */
# define PLAYER_FLOOR_PROPERTY_6    6   /* no auto-jump, no fall damage */
# define PLAYER_FLOOR_PROPERTY_7    7   /* cannot leave: position reverts, speed 0 */
# define PLAYER_FLOOR_PROPERTY_8    8   /* cannot leave: X/Z revert */
# define PLAYER_FLOOR_PROPERTY_9    9   /* no auto-jump */
# define PLAYER_FLOOR_PROPERTY_11   11  /* run-jump into water (M1k) */

/* Child ageProperties->unk_34 (sAgeProperties): 70 * 11 / 17. Walking off a
** drop no deeper than this is an ordinary fall, never a hang. */
# define PLAYER_CHILD_HANG_DROP     45

typedef struct
{
    bool        ground_leave;       /* BGCHECKFLAG_GROUND_LEAVE this step */
    bool        swinging;           /* meleeWeaponState != 0 */
    uint8_t     prev_floor_property;/* sPrevFloorProperty */
    int32_t     y_dist_to_floor;    /* sYDistToFloor: feet - floor below */
    int32_t     speed_q8;           /* speedXZ */
    int16_t     yaw_diff;           /* this->yaw - shape.rot.y */
}           player_leave_t;

typedef enum
{
    PLAYER_LEAVE_FALL = 0,      /* ordinary fall (landing_wait loop) */
    PLAYER_LEAVE_REVERT_XZ,     /* floor property 8: undo this step's X/Z */
    PLAYER_LEAVE_REVERT_STOP,   /* property 7 or swinging: undo move, speed 0 */
    PLAYER_LEAVE_JUMP,          /* auto-jump, gPlayerAnim_link_normal_jump */
    PLAYER_LEAVE_RUN_JUMP,      /* auto-jump, gPlayerAnim_link_normal_run_jump */
    PLAYER_LEAVE_HANG           /* deep drop: func_8083A6AC decides (M1d) */
}           player_leave_action_t;

/* Decide what leaving the ground does. For JUMP / RUN_JUMP *velocity_q8 is
** the launch velocity (func_8083A4A8, child Kokiri-boot registers). HANG is
** only a request: until the ledge-hang check exists the caller falls. */
player_leave_action_t   player_leave_ground(const player_leave_t *in,
                                            int32_t *velocity_q8);

#endif
