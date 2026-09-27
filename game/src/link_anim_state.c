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
#include "gameplay.h"
#include "kokiri_camera.h"

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
/* Source floor of 3.0 against a regular run of about 9.0 units per source
** frame: one third of the slice's run speed. */
#define ROLL_MIN_SPEED_Q8   (LINK_RUN_SPEED_Q8 / 3)
/* Math_StepToF(&speedXZ, target, ...) equivalent: the target is approached,
** not snapped to, in whichever direction it lies. */
#define ROLL_SPEED_STEP_Q8  128

#define SHORT_LANDING_FALL  80
#define ROLL_LANDING_FALL   800

static link_state_t     state = LINK_STATE_IDLE;
static unsigned int     frame;
static unsigned int     phase_ninths;
static bool             was_grounded = true;
/* Diagnostics only; see the declarations in link_anim_state.h. */
static int32_t          last_fall;
static unsigned int     landings;
static unsigned int     combat_clip, combat_frame, guard_steps;
static bool             combat_active;
static uint32_t         motion_events;
/* Roll travel, in Q8 world units per step, and whether the pad still asks for
** forward. Held across the clip rather than recomputed from motion, because
** during a roll the motion IS this value. */
static int32_t          roll_speed_q8;
static int32_t          bonk_speed_q8;
/* What locomotion would be giving right now, and whether it points forward.
** Pushed every step, so the target can rise again as well as fall. */
static int32_t          roll_input_speed_q8;
static bool             roll_forward_held;
/* Automatic jump: which clip, and whether the descent has started. */
static bool             jump_run;
static unsigned int     jump_clip = LINK_CLIP_JUMP;
/* Evasion (PLAYER_STATE2_19): its clip holds through the flight and lands
** on its own _end clip. */
static bool             jump_evade;
static unsigned int     landing_clip = LINK_CLIP_RUN_JUMP_END;
static bool             air_falling;
/* Ledge climbs (Player_Action_80845668). LinkAnimation_PlayOnceSetSpeed
** 1.3: curFrame += 1.3 * R_UPDATE_RATE * 0.5 per 20 Hz update, i.e. 1.3
** frames per 30 Hz step. Phase in 30ths of a frame: +39 per step. */
#define CLIMB_RATE_30THS        39
#define CLIMB_INTERRUPT_FRAMES  4   /* Player_TryActionInterrupt(..., 4.0f) */
#define CLIMB_OFFSET_STEP_Q8    256 /* Math_StepToF(yOffset, 0, 150) x 2/3 */
static unsigned int     climb_clip = LINK_CLIP_STEP100;
static unsigned int     climb_phase;
/* Hang: the clip playing, actionVar1 (0 until the grab frame, 1 after a
** walk-off, -1 after a mid-air grab), and the pull-up's result. */
static unsigned int     hang_clip = LINK_CLIP_CLIMB_HOLD;
static int              hang_var;
static bool             pull_up_done;
/* AnimMovement play: direction, prevTransl, ADJUST_STARTING_POS, and the
** phase before the last step (for OnFrame). */
static bool             move_reverse;
static int32_t          move_prev[3];
static bool             move_adjust;
static unsigned int     move_before;
static int32_t          move_kept[3];
#define HANG_RATE_30THS         30  /* LinkAnimation_PlayOnce / PlayLoop: 1.0 */
#define PULL_UP_RATE_30THS      39  /* func_8083A9B8: 1.3 */

/* The per-frame tables: host arrays, or LINKANIM.BIN in cart RAM. */
#ifdef LINK_FRAMES_FROM_DISC
extern const int16_t    (*link_root)[3];
extern const int16_t    (*link_rotations)[LINK_LIMB_COUNT * 3];
#endif
static int32_t          climb_offset_q8;
static bool             jump250_launch;

uint32_t link_anim_motion_events(void) { return motion_events; }

void link_anim_combat(bool attacking, unsigned int clip, unsigned int frame,
                      bool shielding)
{
    combat_active = attacking || shielding;
    if (attacking) {
        /* gameplay.c owns the attack timeline; the pose is its clip/frame. */
        combat_clip = clip;
        combat_frame = frame;
        /* Crouch stab ends back on defense_wait, not the raise. */
        guard_steps = shielding ? 2 : 0;
    } else if (shielding) {
        combat_clip = guard_steps < 2 ? LINK_CLIP_GUARD : LINK_CLIP_GUARD_WAIT;
        combat_frame = guard_steps < 2 ? guard_steps :
            (guard_steps - 2) % link_clips[LINK_CLIP_GUARD_WAIT].count;
        if (guard_steps < 1000) ++guard_steps;
        else guard_steps = 2;
    } else guard_steps = 0;
}

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
        case LINK_STATE_JUMP:    return jump_clip;
        case LINK_STATE_JUMP_LANDING: return landing_clip;
        case LINK_STATE_STEP_UP: return climb_clip;
        case LINK_STATE_JUMP_START: return LINK_CLIP_JUMP250;
        case LINK_STATE_HANG:    return hang_clip;
        case LINK_STATE_PULL_UP: return climb_clip;
        case LINK_STATE_CLIMB:   return climb_clip;
        case LINK_STATE_CRAWL:   return LINK_CLIP_TUNNEL_START;
        case LINK_STATE_TURN:    return LINK_CLIP_TURN45;
        case LINK_STATE_BONK:    return LINK_CLIP_HIP_DOWN;
        case LINK_STATE_PUSH:
        case LINK_STATE_SWIM:    return climb_clip;
        case LINK_STATE_SLIDE:
        case LINK_STATE_SLIDE_END: return climb_clip;
        case LINK_STATE_IDLE:
        default:                 return LINK_CLIP_IDLE;
    }
}

/* Landing and roll play once and hand back to locomotion; everything else
** loops. Keeping this in one place is what stops a one-shot from looping
** forever and locking control. */
static bool             is_one_shot(link_state_t s)
{
    return s == LINK_STATE_LANDING || s == LINK_STATE_ROLL ||
           s == LINK_STATE_JUMP_LANDING || s == LINK_STATE_BONK || s == LINK_STATE_SLIDE_END;
}

/* Deliberately slower slice cadence: 20 source frames/s at 30 Hz.
 * Fall stores every third source frame, so advance it one third as fast.
 * This is a presentation tuning, not OoT's action-specific playback model. */
static void             advance(void)
{
    unsigned int length = clip_length(clip_for_state(state));
    unsigned int previous_frame = frame;
    phase_ninths += state == LINK_STATE_FALL ? 2 :
                    (state == LINK_STATE_TURN || state == LINK_STATE_BONK ||
                     state == LINK_STATE_SLIDE || state == LINK_STATE_SLIDE_END) ? 9 : 6;
    if ((state == LINK_STATE_FALL || state == LINK_STATE_JUMP) &&
        phase_ninths >= (length - 1) * 9)
        phase_ninths = (length - 1) * 9;   /* ANIMMODE_ONCE: hold the end */
    else if (!is_one_shot(state) && phase_ninths >= length * 9)
        phase_ninths %= length * 9;
    frame = phase_ninths / 9;
    if (state == LINK_STATE_WALK || state == LINK_STATE_RUN) {
        unsigned int contact = length / 2;
        if ((previous_frame < contact && frame >= contact) || frame < previous_frame)
            motion_events |= GP_EVENT_FOOTSTEP;
    } else if (state == LINK_STATE_ROLL) {
        /* OoT sRollAnimSfxList: voice at frame 1, body/floor sound at 6. */
        if (previous_frame < 1 && frame >= 1) motion_events |= GP_EVENT_ROLL_VOICE;
        if (previous_frame < 6 && frame >= 6) motion_events |= GP_EVENT_ROLL;
    }
}

static void             enter(link_state_t next)
{
    if (state == next)
        return;
    state = next;
    frame = 0;
    phase_ninths = 0;
    if (next != LINK_STATE_ROLL)
        roll_speed_q8 = 0;
}

/* The source's speedTarget: 1.5x the locomotion speed for the current input,
** dropped to the floor when it is below it OR when the input is not forward. */
static int32_t          roll_target_q8(int32_t locomotion_speed_q8, bool forward)
{
    int32_t target = locomotion_speed_q8 * 3 / 2;
    if (!forward || target < ROLL_MIN_SPEED_Q8)
        return ROLL_MIN_SPEED_Q8;
    return target;
}

/* Enter a roll at the source's target speed. `speed` is integer world units
** actually travelled on the step that just ran, so it is shifted into Q8. */
static void             enter_roll(int32_t speed)
{
    enter(LINK_STATE_ROLL);
    roll_speed_q8 = roll_target_q8(speed * 256, true);
}

/* One step of Math_StepToF toward the target the pad currently asks for, up or
** down: letting go slows the roll to the floor, and pressing forward again
** brings it back up. */
static void             advance_roll_speed(void)
{
    int32_t target = roll_target_q8(roll_input_speed_q8, roll_forward_held);
    if (roll_speed_q8 > target) {
        roll_speed_q8 -= ROLL_SPEED_STEP_Q8;
        if (roll_speed_q8 < target)
            roll_speed_q8 = target;
    } else if (roll_speed_q8 < target) {
        roll_speed_q8 += ROLL_SPEED_STEP_Q8;
        if (roll_speed_q8 > target)
            roll_speed_q8 = target;
    }
}

static bool             is_climb(link_state_t s)
{
    return s == LINK_STATE_STEP_UP || s == LINK_STATE_JUMP_START ||
           s == LINK_STATE_HANG || s == LINK_STATE_PULL_UP ||
           s == LINK_STATE_CLIMB || s == LINK_STATE_CRAWL || s == LINK_STATE_PUSH ||
           s == LINK_STATE_SWIM;
}

/* Source frames a stored clip spans: sampled every `stride`, last kept. */
static unsigned int     source_length(unsigned int clip)
{
    return (link_clips[clip].count - 1) * link_clip_stride[clip] + 1;
}

/* Stored row of the frame `phase` (30ths of a source frame) is on. */
static unsigned int     stored_row(unsigned int clip, unsigned int phase)
{
    unsigned int index = phase / (30 * link_clip_stride[clip]);
    if (index >= link_clips[clip].count)
        index = link_clips[clip].count - 1;
    return link_clips[clip].first + index;
}

/* Model units -> Q8 world units at the drawn scale. */
static int32_t          model_q8(int32_t v)
{
    return v * LINK_ANIM_SCALE_Q16 / 256;
}

/* LinkAnimation_OnFrame: `frame` passed on this step's advance. */
static bool             crossed(unsigned int before, unsigned int after,
                                unsigned int mark)
{
    return before < mark * 30 && mark * 30 <= after;
}

/* One step of Player_Action_80845668. True once the action is over and
** locomotion takes this step. */
static bool             climb_step(void)
{
    unsigned int length = clip_length(clip_for_state(state));
    unsigned int end = (length - 1) * 30;
    unsigned int before = climb_phase;
    /* LinkAnimation_Once reports done on the update that starts at the end. */
    bool finished = climb_phase >= end;

    if (!finished) {
        climb_phase += CLIMB_RATE_30THS;
        if (climb_phase > end)
            climb_phase = end;
    }
    if (state == LINK_STATE_JUMP_START) {
        /* speedXZ 1.0 until frame 8, then func_80838940 jumps; the clip plays
        ** on as the jump's animation (it passes no new one). */
        if (crossed(before, climb_phase, 8)) {
            jump250_launch = true;
            state = LINK_STATE_JUMP;
            jump_clip = LINK_CLIP_JUMP250;
            jump_run = false;
    jump_evade = false;
    landing_clip = LINK_CLIP_RUN_JUMP_END;
            air_falling = false;
            phase_ninths = climb_phase * 9 / 30;
            frame = phase_ninths / 9;
        }
        return false;
    }
    /* Player_TryActionInterrupt: the last 4 frames yield to movement. */
    if (finished || (climb_phase + CLIMB_INTERRUPT_FRAMES * 30 >= end &&
                     roll_input_speed_q8 > 0)) {
        climb_offset_q8 = 0;
        return true;
    }
    if (crossed(before, climb_phase, climb_clip == LINK_CLIP_STEP150 ? 30 : 16))
        motion_events |= GP_EVENT_CLIMB_END;
    if (climb_clip == LINK_CLIP_STEP100 || climb_phase > 5 * 30) {
        if (climb_offset_q8 > CLIMB_OFFSET_STEP_Q8) climb_offset_q8 -= CLIMB_OFFSET_STEP_Q8;
        else if (climb_offset_q8 < -CLIMB_OFFSET_STEP_Q8) climb_offset_q8 += CLIMB_OFFSET_STEP_Q8;
        else climb_offset_q8 = 0;
    }
    return false;
}

/* Player_Action_8084BBE4's animation half: the grab clip once, then its
** wait loop; the grab frame (11 of normal_fall, 1 of jump_climb_hold) sets
** actionVar1 and plays the floor sound. */
static void             hang_step(void)
{
    unsigned int length = source_length(hang_clip) * 30;
    unsigned int before = climb_phase;

    if (hang_clip == LINK_CLIP_HANG_FALL || hang_clip == LINK_CLIP_CLIMB_HOLD) {
        if (climb_phase >= length - 30) {
            hang_clip = hang_var > 0 ? LINK_CLIP_FALL_WAIT : LINK_CLIP_CLIMB_WAIT;
            climb_phase = 0;
            return;
        }
        climb_phase += HANG_RATE_30THS;
        if (climb_phase > length - 30)
            climb_phase = length - 30;
        if (hang_var == 0 &&
            crossed(before, climb_phase, hang_clip == LINK_CLIP_HANG_FALL ? 11 : 1)) {
            hang_var = hang_clip == LINK_CLIP_HANG_FALL ? 1 : -1;
            motion_events |= GP_EVENT_FOOTSTEP;   /* NA_SE_PL_WALK_GROUND */
        }
        return;
    }
    climb_phase = (climb_phase + HANG_RATE_30THS) % length;
}

/* Player_Action_8084BDFC. True once the clip has ended. */
static bool             pull_up_step(void)
{
    unsigned int end = (source_length(climb_clip) - 1) * 30;
    unsigned int before = climb_phase;

    if (climb_phase >= end)
        return true;
    climb_phase += PULL_UP_RATE_30THS;
    if (climb_phase > end)
        climb_phase = end;
    if (crossed(before, climb_phase, end / 30 - 6))
        motion_events |= GP_EVENT_FOOTSTEP;       /* Player_PlayLandingSfx */
    else if (crossed(before, climb_phase, end / 30 - 34))
        motion_events |= GP_EVENT_CLIMB_END;      /* CLIMB_CLIFF + CLIMB_END */
    return false;
}

void                    link_anim_update(int32_t speed, bool grounded,
                                         int32_t fall_units, bool roll_pressed)
{
    bool    landed = grounded && !was_grounded;

    motion_events = 0;
    jump250_launch = false;

    if (state == LINK_STATE_SLIDE && grounded) {
        was_grounded=true;
        advance();
        return;
    }
    if (state == LINK_STATE_TURN && grounded && speed == 0 && !roll_pressed)
    {
        was_grounded = true;
        advance();
        return;
    }
    if (state == LINK_STATE_HANG)
    {
        was_grounded = grounded;
        hang_step();
        return;
    }
    if (state == LINK_STATE_CLIMB || state == LINK_STATE_CRAWL || state == LINK_STATE_PUSH ||
        state == LINK_STATE_SWIM)
    {
        /* Driven by link_anim_move_step from the climbing action. */
        was_grounded = grounded;
        return;
    }
    if (state == LINK_STATE_PULL_UP)
    {
        was_grounded = grounded;
        if (!pull_up_step())
            return;
        pull_up_done = true;
        state = LINK_STATE_IDLE;
        frame = 0;
        phase_ninths = 0;
        landed = false;
    }
    else if (is_climb(state) && grounded)
    {
        was_grounded = true;
        if (!climb_step())
            return;
        state = LINK_STATE_IDLE;
        frame = 0;
        phase_ninths = 0;
        landed = false;
    }
    else if (is_climb(state))
    {
        climb_offset_q8 = 0;
        state = LINK_STATE_IDLE;
    }

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
        if (state == LINK_STATE_ROLL)
            advance_roll_speed();
        if (state == LINK_STATE_BONK) {
            bonk_speed_q8 += 341;
            if (bonk_speed_q8 > 0) bonk_speed_q8 = 0;
            if (roll_input_speed_q8 > 0 &&
                frame >= clip_length(LINK_CLIP_HIP_DOWN) - 1 - 5)
                phase_ninths = clip_length(LINK_CLIP_HIP_DOWN) * 9;
        }
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
        /* The jump clip plays until the descent passes the departure height;
        ** then the ordinary falling pose takes over, as the source swaps to
        ** its landing-ready animation there. */
        if (state != LINK_STATE_JUMP || (air_falling && !jump_evade))
            enter(LINK_STATE_FALL);
        advance();
        return;
    }

    if (landed && state == LINK_STATE_JUMP && (jump_run || jump_evade))
    {
        jump_evade = false;
        /* Player_Action_8084411C: a run jump lands with run_jump_end ahead
        ** of the short-landing and roll choices. */
        enter(LINK_STATE_JUMP_LANDING);
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
                enter_roll(speed);
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
        enter_roll(speed);
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

int32_t                 link_anim_roll_speed_q8(void)
{
    return state == LINK_STATE_ROLL ? roll_speed_q8 : 0;
}

void link_anim_turn(bool requested, uint16_t target, uint16_t *facing)
{
    int32_t delta = (int16_t)(uint16_t)(target - *facing);
    if (!requested) {
        if (state == LINK_STATE_TURN) enter(LINK_STATE_IDLE);
        return;
    }
    if (state != LINK_STATE_IDLE && state != LINK_STATE_TURN &&
        state != LINK_STATE_WALK && state != LINK_STATE_RUN) return;
    if (delta > 800 || delta < -800) {
        enter(LINK_STATE_TURN);
        *facing = (uint16_t)(*facing + (delta > 0 ? 800 : -800));
    } else {
        if (state == LINK_STATE_TURN) *facing = target;
        enter(LINK_STATE_IDLE);
    }
}

bool link_anim_bonk(bool wall_interact, uint16_t wall_angle)
{
    if (state != LINK_STATE_ROLL || roll_speed_q8 < 7 * 256 ||
        !wall_interact || wall_angle >= 0x2000) return false;
    bonk_speed_q8 = -roll_speed_q8;
    enter(LINK_STATE_BONK);
    return true;
}

int32_t link_anim_bonk_speed_q8(void)
{
    return state == LINK_STATE_BONK ? bonk_speed_q8 : 0;
}

void link_anim_slide(bool face_up)
{
    enter(LINK_STATE_SLIDE);
    climb_clip=face_up?LINK_CLIP_SLIDE_UP:LINK_CLIP_SLIDE_DOWN;
}
void link_anim_slide_end(bool face_up)
{
    enter(LINK_STATE_SLIDE_END);
    climb_clip=face_up?LINK_CLIP_SLIDE_UP_END:LINK_CLIP_SLIDE_DOWN_END;
}
void link_anim_slide_cancel(void)
{
    if(state==LINK_STATE_SLIDE || state==LINK_STATE_SLIDE_END)enter(LINK_STATE_IDLE);
}

void                    link_anim_roll_input(int32_t locomotion_speed_q8,
                                             bool forward)
{
    roll_input_speed_q8 = locomotion_speed_q8;
    roll_forward_held = forward;
}

void                    link_anim_auto_jump(bool run)
{
    link_anim_cancel_roll();
    jump_run = run;
    jump_evade = false;
    landing_clip = LINK_CLIP_RUN_JUMP_END;
    jump_clip = run ? LINK_CLIP_RUN_JUMP : LINK_CLIP_JUMP;
    air_falling = false;
    state = LINK_STATE_JUMP;
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
}

void                    link_anim_hop(void)
{
    link_anim_auto_jump(false);
}

void                    link_anim_evade(unsigned int clip, unsigned int end_clip)
{
    link_anim_auto_jump(false);
    jump_evade = true;
    jump_clip = clip;
    landing_clip = end_clip;
}

void                    link_anim_step_up(bool tall, int32_t y_dist)
{
    link_anim_cancel_roll();
    state = LINK_STATE_STEP_UP;
    climb_clip = tall ? LINK_CLIP_STEP150 : LINK_CLIP_STEP100;
    climb_phase = 0;
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
    /* shape.yOffset -= (yDistToLedge - rise) : start where he stood. */
    climb_offset_q8 = (tall ? LINK_STEP150_RISE_Q8 : LINK_STEP100_RISE_Q8) -
                      y_dist * 256;
}

void                    link_anim_jump_start(void)
{
    link_anim_cancel_roll();
    state = LINK_STATE_JUMP_START;
    climb_phase = 0;
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
    climb_offset_q8 = 0;
}

void                    link_anim_hang(bool walk_off)
{
    link_anim_cancel_roll();
    state = LINK_STATE_HANG;
    hang_clip = walk_off ? LINK_CLIP_HANG_FALL : LINK_CLIP_CLIMB_HOLD;
    hang_var = 0;
    climb_phase = 0;
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
    climb_offset_q8 = 0;
    pull_up_done = false;
}

bool                    link_anim_hang_ready(void)
{
    return state == LINK_STATE_HANG && hang_var != 0;
}

void                    link_anim_pull_up(void)
{
    if (state != LINK_STATE_HANG)
        return;
    /* Player_Action_8084BBE4: fall_up after a walk-off, else jump_climb_up. */
    link_anim_pull_up_clip(hang_var > 0 ? LINK_CLIP_FALL_UP : LINK_CLIP_CLIMB_UP);
}

void                    link_anim_pull_up_clip(unsigned int clip)
{
    link_anim_cancel_roll();
    climb_clip = clip;
    state = LINK_STATE_PULL_UP;
    climb_phase = 0;
    climb_offset_q8 = 0;
    pull_up_done = false;
}

/* Root of any clip at a time in thirds of a frame (attack root motion). */
void                    link_anim_clip_root(unsigned int clip, unsigned int thirds,
                                            int32_t out[3])
{
    unsigned int base = link_clips[clip].first;
    unsigned int last = link_clips[clip].count - 1;
    unsigned int index = thirds / 3, fraction = thirds % 3, next, k;

    if (index >= last) { index = last; fraction = 0; }
    next = index < last ? index + 1 : index;
    for (k = 0; k < 3; ++k)
        out[k] = link_root[base + index][k] +
            (link_root[base + next][k] - link_root[base + index][k]) *
            (int32_t)fraction / 3;
}

/* Root at a phase of the current play, interpolated like the pose. */
static void             move_root(unsigned int phase, int32_t out[3])
{
    unsigned int base = link_clips[climb_clip].first;
    unsigned int last = link_clips[climb_clip].count - 1;
    unsigned int index = phase / 30, fraction = phase % 30, next, k;

    if (index >= last) { index = last; fraction = 0; }
    next = index < last ? index + 1 : index;
    for (k = 0; k < 3; ++k)
        out[k] = link_root[base + index][k] +
            (link_root[base + next][k] - link_root[base + index][k]) *
            (int32_t)fraction / 30;
}

void                    link_anim_move_play(unsigned int clip, bool reverse,
                                            bool adjust_start)
{
    link_anim_cancel_roll();
    state = LINK_STATE_CLIMB;
    climb_clip = clip;
    move_reverse = reverse;
    climb_phase = reverse ? (source_length(clip) - 1) * 30 : 0;
    move_before = climb_phase;
    move_adjust = adjust_start;
    move_kept[0] = move_prev[0];
    move_kept[1] = move_prev[1];
    move_kept[2] = move_prev[2];
    move_root(climb_phase, move_prev);
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
    climb_offset_q8 = 0;
}

void link_anim_push_play(unsigned int clip)
{
    link_anim_move_play(clip,false,false);
    state=LINK_STATE_PUSH;
}

void link_anim_swim_play(unsigned int clip)
{
    link_anim_move_play(clip, false, false);
    state = LINK_STATE_SWIM;
}

bool                    link_anim_move_step(unsigned int speed_30ths, int32_t delta[3])
{
    unsigned int end = (source_length(climb_clip) - 1) * 30;
    int32_t now[3];
    unsigned int k;

    delta[0] = delta[1] = delta[2] = 0;
    move_before = climb_phase;
    if (move_reverse ? climb_phase == 0 : climb_phase >= end)
        return true;
    if (move_reverse)
        climb_phase = climb_phase > speed_30ths ? climb_phase - speed_30ths : 0;
    else {
        climb_phase += speed_30ths;
        if (climb_phase > end)
            climb_phase = end;
    }
    move_root(climb_phase, now);
    for (k = 0; k < 3; ++k) {
        if (!move_adjust)
            delta[k] = now[k] - move_prev[k];
        move_prev[k] = now[k];
    }
    move_adjust = false;
    return false;
}

unsigned int            link_anim_move_clip(void)
{
    return climb_clip;
}

bool                    link_anim_move_crossed(unsigned int mark)
{
    if (move_reverse)
        return climb_phase <= mark * 30 && mark * 30 < move_before;
    return crossed(move_before, climb_phase, mark);
}

void                    link_anim_fall(void)
{
    link_anim_cancel_roll();
    state = LINK_STATE_FALL;
    frame = 0;
    phase_ninths = 0;
    air_falling = true;
    was_grounded = false;
    climb_offset_q8 = 0;
}

void                    link_anim_crawl_hold(void)
{
    state = LINK_STATE_CRAWL;
    climb_clip = LINK_CLIP_TUNNEL_START;
    climb_phase = (source_length(climb_clip) - 1) * 30;
}

void                    link_anim_move_keep_prev(void)
{
    move_prev[0] = move_kept[0];
    move_prev[1] = move_kept[1];
    move_prev[2] = move_kept[2];
}

unsigned int            link_anim_move_phase(void)
{
    return climb_phase;
}

bool                    link_anim_move_reversed(void)
{
    return move_reverse;
}

void                    link_anim_move_end(void)
{
    if (state != LINK_STATE_CLIMB && state != LINK_STATE_PUSH && state != LINK_STATE_SWIM)
        return;
    state = LINK_STATE_IDLE;
    frame = 0;
    phase_ninths = 0;
}

bool                    link_anim_pull_up_done(int32_t *local_x_q8, int32_t *local_z_q8,
                                               uint16_t *yaw)
{
    unsigned int row;

    if (!pull_up_done)
        return false;
    pull_up_done = false;
    row = link_clips[climb_clip].first + link_clips[climb_clip].count - 1;
    /* Measured from sSkeletonBaseTransl (x0.64: these clips are stored
    ** child-adjusted). */
    *local_x_q8 = model_q8(link_root[row][0] - LINK_PINNED_ROOT_X);
    *local_z_q8 = model_q8(link_root[row][2] - LINK_PINNED_ROOT_Z);
    *yaw = (uint16_t)link_rotations[row][1];
    return true;
}

void                    link_anim_let_go(int32_t *local_x_q8, int32_t *y_q8,
                                         int32_t *local_z_q8)
{
    unsigned int row = stored_row(hang_clip, climb_phase);

    /* Player_ApplyAnimMovementScaledByAge measures from baseTransl. */
    *local_x_q8 = model_q8(link_root[row][0] - LINK_PINNED_ROOT_X);
    *y_q8 = model_q8(link_root[row][1] - LINK_PINNED_ROOT_Y);
    *local_z_q8 = model_q8(link_root[row][2] - LINK_PINNED_ROOT_Z);
    /* func_80837B9C: Player_Action_8084411C falling. */
    state = LINK_STATE_FALL;
    frame = 0;
    phase_ninths = 0;
    air_falling = true;
    was_grounded = false;
}

bool                    link_anim_jump250_launch(void)
{
    return jump250_launch;
}

int32_t                 link_anim_y_offset_q8(void)
{
    return state == LINK_STATE_STEP_UP ? climb_offset_q8 : 0;
}

void                    link_anim_set_air(bool falling_below_start)
{
    air_falling = falling_below_start;
}

void                    link_anim_cancel_roll(void)
{
    if (state != LINK_STATE_ROLL && state != LINK_STATE_BONK)
        return;
    state = LINK_STATE_IDLE;
    frame = 0;
    phase_ninths = 0;
    roll_speed_q8 = 0;
    bonk_speed_q8 = 0;
}

link_state_t            link_anim_state(void)
{
    return state;
}

unsigned int            link_anim_clip(void)
{
    if (combat_active) return combat_clip;
    return clip_for_state(state);
}

unsigned int            link_anim_frame(void)
{
    if (combat_active) return combat_frame;
    if (is_climb(state))
        return stored_row(clip_for_state(state), climb_phase) -
               link_clips[clip_for_state(state)].first;
    return frame;
}

unsigned int            link_anim_fraction(void)
{
    unsigned int span;

    if (combat_active) return 0;
    if (is_climb(state)) {
        span = 30 * link_clip_stride[clip_for_state(state)];
        return (climb_phase % span) * 256 / span;
    }
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
    bonk_speed_q8 = 0;
    state = LINK_STATE_IDLE;
    frame = 0;
    phase_ninths = 0;
    last_fall = 0;
    landings = 0;
    combat_active = false;
    motion_events = 0;
    guard_steps = 0;
    roll_speed_q8 = 0;
    roll_input_speed_q8 = 0;
    roll_forward_held = false;
    jump_run = false;
    jump_clip = LINK_CLIP_JUMP;
    air_falling = false;
    climb_phase = 0;
    climb_offset_q8 = 0;
    jump250_launch = false;
    hang_var = 0;
    pull_up_done = false;
    /* Spawning is a fall onto the floor; that first contact is a real landing
    ** and should read as one rather than being swallowed. */
    was_grounded = false;
}

bool                    link_anim_is_locked(void)
{
    return is_one_shot(state) || is_climb(state);
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
