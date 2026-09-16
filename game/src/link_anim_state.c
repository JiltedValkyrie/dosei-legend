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
#define RUN_SPEED_MIN       10      /* digital d-pad: full tilt is a run */

/* Fall distances, in this world's units.
**
** OoT gates its landing choice at 80 and 800, but those are model units on
** Player's own scale and do NOT transfer: here an ordinary drop off a ledge
** measures about 11 units, so an 80-unit gate meant no fall ever registered as
** a landing at all. These keep OoT's shape -- a short landing for small drops,
** a roll for a real but survivable fall -- rescaled to the 11-unit baseline the
** collision actually produces.
**
** SHORT_LANDING_FALL doubles as the "is this a landing at all" test, because
** ground following drops the grounded flag for a step at a time on slopes. */
#define SHORT_LANDING_FALL  4
#define ROLL_LANDING_FALL   40

/* Consecutive ungrounded 30 Hz steps before the fall clip takes over. Ground
** following drops the grounded flag for a step at a time on slopes and stairs,
** so a fall has to outlast that to be real. Four steps is about an eighth of a
** second -- shorter than any drop worth animating, longer than any blip. */
#define FALL_STATE_STEPS    4

static link_state_t     state = LINK_STATE_IDLE;
static unsigned int     frame;
static bool             was_grounded = true;
static unsigned int     airborne;

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

static void             enter(link_state_t next)
{
    if (state == next)
        return;
    state = next;
    frame = 0;
}

void                    link_anim_update(int32_t speed, bool grounded,
                                         int32_t fall_units, bool roll_pressed)
{
    bool    landed = grounded && !was_grounded;

    was_grounded = grounded;

    /* A one-shot owns Link until it finishes, so a landing or roll is not cut
    ** off by the first step of movement. It still yields immediately if he
    ** leaves the ground again, which is what makes rolling off a ledge fall. */
    if (is_one_shot(state) && grounded)
    {
        if (++frame < clip_length(clip_for_state(state)))
            return;
        /* Finished: fall through and pick a locomotion state this step. */
        state = LINK_STATE_IDLE;
        frame = 0;
    }

    /* Same blip problem as the landing test below: a single ungrounded step is
    ** ordinary ground following, not a fall. Only switch to the fall clip once
    ** he has been off the floor long enough to really be dropping. */
    if (!grounded)
    {
        if (airborne < FALL_STATE_STEPS)
        {
            ++airborne;
            ++frame;
            return;
        }
        enter(LINK_STATE_FALL);
        ++frame;
        return;
    }
    airborne = 0;

    /* Only a real drop counts as a landing.
    **
    ** kokiri_collision_fall() reports "grounded" only when Link sits exactly on
    ** the floor plane, so walking across sloped or stepped ground drops that
    ** flag for single steps at a time. Treating every such blip as a landing
    ** made him land -- and, with any movement, roll -- continuously while just
    ** walking. A landing therefore needs a fall worth animating, which is the
    ** same fallDistance test OoT already gates its landing choice on. */
    if (landed && fall_units > SHORT_LANDING_FALL)
    {
        /* OoT's landing choice, verified above. The forward-stick condition
        ** becomes "he is still moving forward", which is the closest thing the
        ** digital d-pad offers. */
        if (fall_units < ROLL_LANDING_FALL && speed >= WALK_SPEED_MIN)
            enter(LINK_STATE_ROLL);
        else
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

    ++frame;
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

bool                    link_anim_is_locked(void)
{
    return is_one_shot(state);
}
