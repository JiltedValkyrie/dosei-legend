/* z_player.c: Handler_5, 8084B78C/8084B898/8084B9E4. Source roots are visual;
 * a dynamic block's motion carries the hands, never duplicate root movement. */
#include "player_push.h"
#include "push_block.h"
#include "link_anim_state.h"
#include "link_clips.h"
#include "kokiri_camera.h"
enum { OFF,WAIT,START,MOVE,END,RELEASE };

void player_push_cancel(player_push_t *p)
{
    if (p->phase) link_anim_move_end();
    p->phase=OFF;
}

bool player_push_start(player_push_t *p,const player_bg_t *bg,bool held,uint16_t *facing)
{
    actor_t *a;
    if (!held || !bg->interact || bg->shape_yaw_to_wall>=0x3000 ||
        !(bg->touched_flags&BG_WALL_FLAG_6) || bg->y_dist_to_ledge<39) return false;
    if (bg->wall_hit.bg_id!=BG_SCENE && !push_block_from_bg(bg->wall_hit.bg_id)) return false;
    p->bg_id=bg->wall_hit.bg_id;
    p->phase=WAIT; p->direction=0;
    *facing=(uint16_t)(bg->wall_yaw+0x8000);
    a=push_block_from_bg(p->bg_id);
    p->block_x=a?a->x:0; p->block_z=a?a->z:0;
    link_anim_push_play(LINK_CLIP_PUSH_WAIT);
    return true;
}

void player_push_update(player_push_t *p,bool held,int32_t speed_q8,
                         uint16_t heading,bg_vec_t *feet,uint16_t facing)
{
    actor_t *a;
    bg_vec_t from,to,at;
    bg_hit_t hit;
    int32_t sn,cs,delta[3],cosine;
    int direction;
    bool finished,contact;
    if (!p->phase) return;
    if (p->phase==RELEASE) {
        if (link_anim_move_step(30,delta)) player_push_cancel(p);
        return;
    }
    a=push_block_from_bg(p->bg_id);
    if (a) {
        feet->x+=a->x-p->block_x; feet->z+=a->z-p->block_z;
        p->block_x=a->x; p->block_z=a->z;
    }
    kokiri_camera_sincos(facing,&sn,&cs);
    from=*feet; from.y+=26;
    to=from; to.x+=30*sn/65536; to.z+=30*cs/65536;
    contact=bg_line(&from,&to,&at,BG_CHECK_WALL|BG_CHECK_ONE_FACE,BG_IGNORE_ENTITY,&hit)
        && hit.bg_id==p->bg_id;
    if (!contact || (!held && !push_block_moving(a))) {
        p->phase=RELEASE;
        link_anim_push_play(LINK_CLIP_PUSH_RELEASE);
        return;
    }
    feet->x=at.x-19*sn/65536;
    feet->z=at.z-19*cs/65536;
    kokiri_camera_sincos((uint16_t)(heading-facing),&sn,&cosine);
    direction=speed_q8<=0 || !cosine ? 0 : cosine>0 ? 1 : -1;
    if (direction<0) {
        /* Source pull checks for an obstruction behind Link before force. */
        kokiri_camera_sincos(facing,&sn,&cs);
        from=*feet; from.y+=26;
        to=from; to.x-=40*sn/65536; to.z-=40*cs/65536;
        if (bg_line(&from,&to,&at,BG_CHECK_WALL|BG_CHECK_ONE_FACE,BG_IGNORE_ENTITY,&hit))
            direction=0;
    }
    finished=link_anim_move_step(30,delta);
    if (p->phase==WAIT || p->phase==END) {
        if (finished && direction) {
            p->direction=direction; p->phase=START;
            link_anim_push_play(direction>0?LINK_CLIP_PUSH_START:LINK_CLIP_PULL_START);
        }
    } else if (finished) {
        if (!direction) {
            p->phase=END;
            link_anim_push_play(p->direction>0?LINK_CLIP_PUSH_END:LINK_CLIP_PULL_END);
        } else {
            p->direction=direction; p->phase=MOVE;
            link_anim_push_play(direction>0?LINK_CLIP_PUSHING:LINK_CLIP_PULLING);
        }
    }
    if ((p->phase==START || p->phase==MOVE) && direction==p->direction && a)
        push_block_request(a,facing,direction,0);
}
