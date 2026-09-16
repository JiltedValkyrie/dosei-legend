/*
** Link's locomotion state machine.
**
** Animation is driven from motion that already happened, not from buttons:
** `speed` is the distance collision actually moved him this step. That is what
** keeps the walk cycle honest when a wall or a ledge constraint stops him --
** pressing forward into a tree leaves him idle, not running on the spot -- and
** it means the clips never need root motion, because translation is already
** owned by the collision code.
**
** Landing follows OoT (z_player.c, the landing branch around line 9632),
** checked against the ntsc-1.2 source rather than recalled:
**   fallDistance <= 80                      -> short landing
**   fallDistance < 800 and stick forward     -> Player_SetupRoll
**   otherwise                                -> ordinary landing
** The roll is conditional on landing, not an automatic mid-air roll. A ground
** roll the player starts deliberately is the separate manual case below.
*/

#include "link_anim_state.h"
#include "link_clips.h"

/* Thresholds in this file are world units per 30 Hz step, matching the
** movement constants in kokiri_camera.h rather than OoT's own speeds. */
#define WALK_SPEED_MIN      1       /* below this he is standing still */
#define RUN_SPEED_MIN       4       /* 5.5 units/step, allowing integer rounding */

/* Fall distances, straight from OoT.
**
** z_player.c:5831 computes fallDistance as fallStartHeight - world.pos.y, a
** WORLD-space distance, and this project keeps the scene's native collision
** coordinates without a scale conversion. So 80 and 800 transfer directly.
**
** An earlier revision rescaled these to 4 and 40 on the theory that they were
** model units. They are not, and the 11 that rescale was derived from is
** ACTOR_GROUND_FOLLOW_DROP -- a downhill floor-following tolerance, not a
** measured fall. */
#define SHORT_LANDING_FALL  80
#define ROLL_LANDING_FALL   800

static link_state_t     state = LINK_STATE_IDLE;
static unsigned int     frame;
static unsigned int     phase_ninths;
static bool             was_grounded = true;
/* Diagnostics only; see the declarations in link_anim_state.h. */
static int32_t          last_fall;
static unsigned int     landings;

/* Clip frame counts, so a one-shot knows when it has finished. Kept in step
** with CLIPS in build_link_model.py through link_clips[]. */
static unsigned int     clip_length(unsigned int clip)
{
    return clip < LINK_CLIP_COUNT ? link_clips[clip].count : 1;
}

static unsigned int     clip_for_state(link_state_t s)
{
    switch (s)
    {
        case LINK_STATE_WALK:    return LINK_CLIP_WALK;
        case LINK_STATE_RUN:     return LINK_CLIP_RUN;
        case LINK_STATE_FALL:    return LINK_CLIP_FALL;
        case LINK_STATE_LANDING: return LINK_CLIP_LANDING;
        case LINK_STATE_ROLL:    return LINK_CLIP_ROLL;
        case LINK_STATE_IDLE:
        default:                 return LINK_CLIP_IDLE;
    }
}

/* Landing and roll play once and hand back to locomotion; everything else
** loops. Keeping this in one place is what stops a one-shot from looping
** forever and locking control. */
static bool             is_one_shot(link_state_t s)
{
    return s == LINK_STATE_LANDING || s == LINK_STATE_ROLL;
}

/* Deliberately slower slice cadence: 20 source frames/s at 30 Hz.
 * Fall stores every third source frame, so advance it one third as fast.
 * This is a presentation tuning, not OoT's action-specific playback model. */
static void             advance(void)
{
    unsigned int length = clip_length(clip_for_state(state));
    phase_ninths += state == LINK_STATE_FALL ? 2 : 6;
    if (state == LINK_STATE_FALL && phase_ninths >= (length - 1) * 9)
        phase_ninths = (length - 1) * 9;
    else if (!is_one_shot(state) && phase_ninths >= length * 9)
        phase_ninths %= length * 9;
    frame = phase_ninths / 9;
}

static void             enter(link_state_t next)
{
    if (state == next)
        return;
    state = next;
    frame = 0;
    phase_ninths = 0;
}

void                    link_anim_update(int32_t speed, bool grounded,
                                         int32_t fall_units, bool roll_pressed)
{
    bool    landed = grounded && !was_grounded;

    was_grounded = grounded;
    if (landed)
    {
        last_fall = fall_units;
        ++landings;
    }

    /* A one-shot owns Link until it finishes, so a landing or roll is not cut
    ** off by the first step of movement. It still yields immediately if he
    ** leaves the ground again, which is what makes rolling off a ledge fall. */
    if (is_one_shot(state) && grounded)
    {
        advance();
        if (frame < clip_length(clip_for_state(state)))
            return;
        /* Finished: fall through and pick a locomotion state this step. */
        state = LINK_STATE_IDLE;
        frame = 0;
        phase_ninths = 0;
    }

    /* kokiri_collision_move_actor() snaps y onto the floor plane when it
    ** follows ground downhill, so ordinary slope motion keeps the grounded
    ** flag. An ungrounded step is a real departure and needs no debouncing. */
    if (!grounded)
    {
        enter(LINK_STATE_FALL);
        advance();
        return;
    }

    if (landed)
    {
        /* OoT's landing choice, verified against z_player.c. The forward-stick
        ** condition becomes "he is still moving forward", which is the closest
        ** thing the digital d-pad offers. */
        if (fall_units > SHORT_LANDING_FALL)
        {
            if (fall_units < ROLL_LANDING_FALL && speed >= WALK_SPEED_MIN)
                enter(LINK_STATE_ROLL);
            else
                enter(LINK_STATE_LANDING);
            return;
        }
        enter(LINK_STATE_LANDING);
        return;
    }

    /* A deliberate ground roll, distinct from the landing roll above. */
    if (roll_pressed && speed >= WALK_SPEED_MIN)
    {
        enter(LINK_STATE_ROLL);
        return;
    }

    if (speed >= RUN_SPEED_MIN)
        enter(LINK_STATE_RUN);
    else if (speed >= WALK_SPEED_MIN)
        enter(LINK_STATE_WALK);
    else
        enter(LINK_STATE_IDLE);

    advance();
}

link_state_t            link_anim_state(void)
{
    return state;
}

unsigned int            link_anim_clip(void)
{
    return clip_for_state(state);
}

unsigned int            link_anim_frame(void)
{
    return frame;
}

unsigned int            link_anim_fraction(void)
{
    return (phase_ninths % 9) * 256 / 9;
}

/* Reset the locomotion state, not just the posed frame.
**
** link_anim_reset() in link_anim.c only clears the cached POINT table. Without
** this, `state`, `frame` and `was_grounded` survive a return to the title, so
** Link can re-enter gameplay part-way through a one-shot clip -- and a one-shot
** only advances while grounded, so a spawn that begins airborne leaves it stuck
** until he next touches the floor. */
void                    link_anim_reset_state(void)
{
    state = LINK_STATE_IDLE;
    frame = 0;
    phase_ninths = 0;
    last_fall = 0;
    landings = 0;
    /* Spawning is a fall onto the floor; that first contact is a real landing
    ** and should read as one rather than being swallowed. */
    was_grounded = false;
}

bool                    link_anim_is_locked(void)
{
    return is_one_shot(state);
}

int32_t                 link_anim_last_fall(void)
{
    return last_fall;
}

unsigned int            link_anim_landings(void)
{
    return landings;
}

bool                    link_anim_last_grounded(void)
{
    return was_grounded;
}
