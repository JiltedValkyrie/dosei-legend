#pragma GCC optimize("Os") /* per-step logic, small: size over speed (work RAM) */
/* z_player.c: 80846050 attach at frame 4, 80846408 failed bush lift,
 * 80846578 throw at frame 3, 808464B0 put down at frame 4. */
#include "player_lift.h"
#include "link_anim_state.h"
#include "link_clips.h"

/*
** Carrying is NOT its own animation state.
**
** z_player.c keeps Link in Player_Action_80840450 (idle/walk/run) the whole
** time he holds something; func_80835688 only installs the upper action
** Player_UpperAction_CarryActor, which loops carryB_wait on a second skelanime
** whose UPPER..TORSO limbs Player_UpdateUpperBody copies over the main joint
** table. There is no carry-walk clip, so holding the wait clip in PUSH state
** froze the legs. LIFT_HOLD therefore releases the animation state back to
** locomotion and drives the overlay instead; the one-shot lift, throw and put
** clips stay full-body.
*/
/* Same cadence as link_anim_state.c's advance(): six ninths of a source frame
** per step, with the remainder handed to the pose as a 0..255 fraction. The
** arms would otherwise run half again too fast, and without the fraction they
** would step instead of interpolating like the legs. */
#define CARRY_WAIT_NINTHS   6
static unsigned int carry_wait_phase;   /* ninths of a source frame */

void player_lift_begin(player_lift_t *p,bool bush,unsigned strength,bool throw_only)
{
    p->phase=bush && !strength ? LIFT_FAIL_START : LIFT_START;
    p->timer=0; p->attached=false; p->throw_only=throw_only; p->events=0;
    p->release_speed_q8=p->release_y_q8=0;
    link_anim_push_play(p->phase==LIFT_FAIL_START?LINK_CLIP_LIFT_FAIL:LINK_CLIP_LIFT);
}

void player_lift_cancel(player_lift_t *p)
{
    p->events=p->attached?LIFT_RELEASE:0;
    p->attached=false;
    p->release_speed_q8=p->release_y_q8=0;
    if (p->phase) link_anim_move_end();
    link_anim_upper_clear();
    p->phase=LIFT_NONE;
}

void player_lift_update(player_lift_t *p,bool action,int32_t speed_q8)
{
    int32_t delta[3];
    bool finished;
    p->events=0;
    if (!p->phase) return;
    if (p->phase==LIFT_HOLD && action) {
        p->phase=p->throw_only || speed_q8>=282 ? LIFT_THROW : LIFT_PUT;
        link_anim_upper_clear();    /* throw and put are full-body one-shots */
        link_anim_push_play(p->phase==LIFT_THROW?LINK_CLIP_CARRY_THROW:LINK_CLIP_CARRY_PUT);
    }
    if (p->phase==LIFT_HOLD) {
        /* Player_UpperAction_CarryActor: loop carryB_wait on the upper body
        ** only. Locomotion owns the legs, so Link walks while he carries. */
        carry_wait_phase=(carry_wait_phase+CARRY_WAIT_NINTHS)%
                         (LINK_FRAMES_CARRY_WAIT*9u);
        link_anim_upper_overlay(LINK_CLIP_CARRY_WAIT,carry_wait_phase/9u,
                                (carry_wait_phase%9u)*256u/9u);
        return;
    }
    finished=link_anim_move_step(30,delta);
    if (p->phase==LIFT_START && link_anim_move_crossed(4)) {
        p->attached=true;
        p->events=LIFT_ATTACH;
    }
    if (p->phase==LIFT_THROW && p->attached && link_anim_move_crossed(3)) {
        p->attached=false; p->events=LIFT_RELEASE;
        p->release_speed_q8=speed_q8+8*256; p->release_y_q8=12*256;
    }
    if (p->phase==LIFT_PUT && p->attached && link_anim_move_crossed(4)) {
        p->attached=false; p->events=LIFT_RELEASE;
        p->release_speed_q8=p->release_y_q8=0;
    }
    if (p->phase==LIFT_FAIL_WAIT) {
        if (--p->timer==0) {
            p->phase=LIFT_FAIL_END;
            link_anim_push_play(LINK_CLIP_LIFT_FAIL_END);
        } else if (finished) link_anim_push_play(LINK_CLIP_LIFT_FAIL_WAIT);
        return;
    }
    if (!finished) return;
    switch (p->phase) {
    case LIFT_FAIL_START:
        p->phase=LIFT_FAIL_WAIT; p->timer=23; /* 15 source ticks, round up */
        link_anim_push_play(LINK_CLIP_LIFT_FAIL_WAIT); break;
    case LIFT_START:
        /* func_80835688: the lift clip ends, the main skeleton returns to
        ** locomotion and only the upper action keeps carryB_wait. */
        p->phase=LIFT_HOLD;
        carry_wait_phase=0;
        link_anim_move_end();
        link_anim_upper_overlay(LINK_CLIP_CARRY_WAIT,0,0); break;
    default:
        player_lift_cancel(p); break;
    }
}
