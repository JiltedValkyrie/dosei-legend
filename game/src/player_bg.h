#ifndef PLAYER_BG_H
# define PLAYER_BG_H
# include <stdbool.h>
# include <stdint.h>
# include "kokiri_collision.h"

/*
** Link's wall contact and ledge probe, and the ground ledge climb it feeds:
** z_player.c Player_ProcessSceneCollision (the BGCHECKFLAG_WALL block),
** Player_PosVsWallLineTest and Player_ActionHandler_12. Integer, feet space,
** host tested; the caller owns position, velocity and animation.
**
** Units: world units; normals Q14 (the source's are Q15 -- thresholds are
** converted where they appear); yaws binang; speed Q8 per 30 Hz step. Timers
** count 30 Hz steps (TRAVERSAL_TIMING.md: 20 Hz frames x 3/2, rounded up).
*/

/* Child sAgeProperties. */
# define PLAYER_LEDGE_CHECK_HEIGHT  71  /* unk_0C: probe start above the feet */
# define PLAYER_LEDGE_JUMP_MIN      47  /* unk_14: 250 jump */
# define PLAYER_LEDGE_STEP150_MIN   39  /* unk_18: 150 step up */
# define PLAYER_LEDGE_STEP100_MIN   27  /* unk_1C: 100 step up; below = hop */
# define PLAYER_LEDGE_MIN           18  /* lower "ledges" are not ledges */
# define PLAYER_WALL_RADIUS         14  /* wallCheckRadius */
/* LEDGE_DIST_MAX is 399.96; every threshold compared against it gives the
** same answer for 399. */
# define PLAYER_LEDGE_DIST_MAX      399
/* ledgeClimbDelayTimer: 3 and 6 source frames; cap 100. */
# define PLAYER_LEDGE_HOP_STEPS     5
# define PLAYER_LEDGE_CLIMB_STEPS   9
# define PLAYER_LEDGE_TIMER_MAX     150

typedef enum
{
    PLAYER_LEDGE_NONE = 0,
    PLAYER_LEDGE_CLIMB_1,       /* hop */
    PLAYER_LEDGE_CLIMB_2,       /* 100 step up */
    PLAYER_LEDGE_CLIMB_3,       /* 150 step up */
    PLAYER_LEDGE_CLIMB_4        /* 250 jump */
}           player_ledge_type_t;

typedef struct
{
    bool        wall;               /* BGCHECKFLAG_WALL */
    bool        interact;           /* BGCHECKFLAG_PLAYER_WALL_INTERACT */
    bg_hit_t    wall_hit;           /* actor.wallPoly / wallBgId */
    uint16_t    wall_yaw;           /* actor.wallYaw: yaw of the normal */
    uint32_t    touched_flags;      /* sTouchedWallFlags */
    uint16_t    shape_yaw_to_wall;  /* sShapeYawToTouchedWall */
    uint16_t    world_yaw_to_wall;  /* sWorldYawToTouchedWall */
    int32_t     dist_to_wall;       /* distToInteractWall */
    int32_t     y_dist_to_ledge;    /* yDistToLedge */
    uint8_t     ledge_type;         /* ledgeClimbType */
    uint8_t     delay_timer;        /* ledgeClimbDelayTimer, in steps */
}           player_bg_t;

void        player_bg_reset(player_bg_t *bg);

/* Once per step after collision. `wall` / `wall_hit` = this step's
** BGCHECKFLAG_WALL and wall poly (kokiri_collision_actor_wall). `feet` is
** Link's position; `shape_yaw` his facing, `world_yaw` his movement yaw,
** `speed_q8` speedXZ (commanded, not travelled). */
void        player_bg_update(player_bg_t *bg, bool wall, const bg_hit_t *wall_hit,
                             const bg_vec_t *feet, uint16_t shape_yaw,
                             uint16_t world_yaw, int32_t speed_q8);

typedef enum
{
    PLAYER_LEDGE_ACT_NONE = 0,
    PLAYER_LEDGE_ACT_HOP,       /* func_808389E8: jump clip, *velocity_q8 */
    PLAYER_LEDGE_ACT_STEP100,   /* gPlayerAnim_link_normal_100step_up */
    PLAYER_LEDGE_ACT_STEP150,   /* gPlayerAnim_link_normal_150step_up */
    PLAYER_LEDGE_ACT_JUMP250    /* gPlayerAnim_link_normal_250jump_start */
}           player_ledge_act_t;

/* Player_ActionHandler_12, from the walk/run/target action lists. Not
** carrying, not swimming (neither exists yet). `a_pressed` = an A press
** nothing else claimed. HOP writes the launch velocity. */
player_ledge_act_t  player_ledge_action(const player_bg_t *bg, bool grounded,
                                        bool a_pressed, int32_t *velocity_q8);

/* Frame 8 of the 250 jump start (Player_Action_80845668, child, dry):
** min(yDistToLedge, 71) * 0.072 + 1.0. */
int32_t     player_ledge_jump250_velocity_q8(int32_t y_dist_to_ledge);

/* Where the step-up puts him (Player_ActionHandler_12): distToInteractWall
** + 0.5 into the wall along its normal, yDistToLedge up, facing the wall. */
void        player_ledge_step_target(const player_bg_t *bg, bg_vec_t *feet,
                                     uint16_t *facing);

/*
** Ledge hang (M1d). func_8083A6AC: walking off a drop deeper than 45 looks
** back for the face just left; Player_Action_8084411C: a descending jump or
** fall grabs a ledge ahead; func_8083A5C4 puts him there.
*/

/* Child 70 * 11 / 17 = 45.29: the ledge must be this far above the floor
** under him for a mid-air grab. Integer >: 46 and up. */
# define PLAYER_HANG_GRAB_MIN       46
/* Player_Action_8084411C: at 150 and above a forward stick climbs the wall
** instead (func_8083EC18, M1e). */
# define PLAYER_HANG_CLIMB_WALL     150
/* The departure step's drop before func_8083A6AC's line test: a grounded
** player carries velocity.y -4 (UPDBGCHECKINFO_FLAG_3), and the first
** airborne step adds gravity, -4.67 at 30 Hz (TRAVERSAL_TIMING). */
# define PLAYER_HANG_LINE_DROP      5

typedef enum
{
    PLAYER_HANG_NONE = 0,
    PLAYER_HANG_LEDGE,          /* hang, gPlayerAnim_link_normal_fall */
    PLAYER_HANG_CLIMB           /* floor property 6 / WALL_FLAG_3: vine or
                                ** ladder climb start (M1e) */
}           player_hang_t;

/* func_8083A6AC. `pos` = feet this step (already PLAYER_HANG_LINE_DROP
** below the departure height), `prev` = feet last step. depth_in_water =
** water surface - feet, or BG_Y_MIN with no water. Writes the face and
** distToInteractWall-style plane distance on a hit. */
player_hang_t   player_hang_walk_off(const bg_vec_t *pos, const bg_vec_t *prev,
                                     int32_t depth_in_water,
                                     uint8_t prev_floor_property,
                                     bg_hit_t *wall, int32_t *dist);

/* The mid-air grab test of Player_Action_8084411C, once descending. `speed_q8`
** = speedXZ; `floor_y` = floor below the feet (actor.floorHeight). */
bool            player_hang_grab(const player_bg_t *bg, int32_t speed_q8,
                                 int32_t feet_y, int32_t floor_y);

/* func_8083A5C4: (dist + 1) into the wall along its normal; facing = the
** normal's yaw, turned to face the wall for a mid-air grab. */
void            player_hang_place(const bg_hit_t *wall, int32_t dist, bg_vec_t *feet,
                                  uint16_t *facing, bool face_wall);

#endif
