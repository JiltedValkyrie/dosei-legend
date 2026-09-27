/* z_player.c: 80846050 attach at frame 4, 80846408 failed bush lift,
 * 80846578 throw at frame 3, 808464B0 put down at frame 4. */
#include "player_lift.h"
#include "link_anim_state.h"
#include "link_clips.h"

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
        link_anim_push_play(p->phase==LIFT_THROW?LINK_CLIP_CARRY_THROW:LINK_CLIP_CARRY_PUT);
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
        p->phase=LIFT_HOLD;
        link_anim_push_play(LINK_CLIP_CARRY_WAIT); break;
    case LIFT_HOLD:
        link_anim_push_play(LINK_CLIP_CARRY_WAIT); break;
    default:
        player_lift_cancel(p); break;
    }
}
