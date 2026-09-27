#ifndef PLAYER_CLIMB_H
# define PLAYER_CLIMB_H
# include <stdbool.h>
# include <stdint.h>
# include "kokiri_collision.h"
# include "player_bg.h"

/*
** Ladder and vine climbing (M1e): z_player.c func_8083EC18 (start),
** Player_Action_8084BF1C (climb), Player_Action_8084C5F8 (ladder ends),
** func_8083FBC0 / func_8083FB7C (let go). The climb clips are AnimMovement
** clips: their root motion moves Link (link_anim_move_*), at actor scale 0.01.
** Feet space, integer; the caller owns velocity, audio and the camera.
*/

/* func_8083EC18: yDistToLedge at least 79 (nothing to stand on within the
** ledge probe) and a climbable wall. */
# define PLAYER_CLIMB_MIN_WALL      79
/* Player_Action_8084BF1C: a jump descending past a wall this tall with the
** stick forward grabs it (from Player_Action_8084411C). */
# define PLAYER_CLIMB_AIR_WALL      150

typedef enum
{
    PLAYER_CLIMB_NONE = 0,
    PLAYER_CLIMB_ON,            /* climbing (8084BF1C) */
    PLAYER_CLIMB_ENDING,        /* ladder top/bottom step-off (8084C5F8) */
    PLAYER_CLIMB_DONE,          /* the ending finished: locomotion again */
    PLAYER_CLIMB_VINE_TOP,      /* vine top: caller hangs + pulls up */
    PLAYER_CLIMB_LET_GO         /* func_8083FB7C: fall, speedXZ -0.4 */
}           player_climb_phase_t;

typedef struct
{
    player_climb_phase_t phase;
    int8_t      var1;           /* actionVar1: 0 ladder, 2 vine (1: walk-off vine) */
    int8_t      var2;           /* actionVar2: < 0 while starting, else 0/1 hand */
    bool        interact;       /* BGCHECKFLAG_PLAYER_WALL_INTERACT this step */
    bg_hit_t    wall;           /* actor.wallPoly while climbing */
    uint32_t    events;         /* GP_EVENT_* this step (footsteps, voice) */
}           player_climb_t;

typedef struct
{
    /* sControlInput->rel.stick_x / stick_y: the raw N64 scale (full push
    ** about 80), right and up positive. Not camera-relative. */
    int32_t     stick_x, stick_y;
    bool        a_pressed;
    bool        stick_pushed;   /* player_input_stick_pushed: interrupts */
}           player_climb_input_t;

/* func_8083EC18. Needs the probe's interact wall (the caller checked
** WALL_INTERACT, shape yaw < 0x3000 and speedXZ > 0). On success moves *feet,
** sets *facing and starts the clip (link_anim_move_play). */
bool        player_climb_start(player_climb_t *climb, const player_bg_t *bg,
                               bg_vec_t *feet, uint16_t *facing, bool grounded);

/* func_8083A6AC's vine branch: already placed by player_hang_place; faces
** the wall and slides down onto it (Fclimb_startB, actionVar1 = 1). */
void        player_climb_start_walk_off(player_climb_t *climb, const bg_hit_t *wall,
                                        uint16_t *facing);

/* One 30 Hz step of the climb. Moves *feet by the clip's root motion and the
** wall snap; may turn *facing. */
void        player_climb_update(player_climb_t *climb, const player_climb_input_t *in,
                                bg_vec_t *feet, uint16_t *facing);

#endif
