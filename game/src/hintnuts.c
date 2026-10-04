/* En_Hintnuts and its En_Nutsball projectiles. Source puzzle params 1,2,3
 * correspond to the spoken spatial order 2,3,1. Leaving spawns ITEM00_HEART;
 * reflected balls themselves never drop items. All actor timing is 20 Hz. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "hintnuts.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_camera.h"
#include "save_state.h"
#include "world_props.h"
#include "dungeon_enemy_data.h"
#include <string.h>
enum {WAIT,UP,LOOK,STAND,SPIT,BURROW,UNBURROW,RUN,TALK,LEAVE,FREEZE,SINK,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t body;
    uint16_t age,timer,anim;
    int16_t move_yaw;
    uint8_t spawn,state,phase,friendly,post_spit,resetting;
} hint_state;
typedef struct {
    collider_t body;
    int32_t pos[3];
    int16_t timer,vy;
    uint16_t yaw,roll;
    uint8_t live,reflected,phase,wall;
} nut_state;
typedef struct {hint_state hints[HINTNUTS_MAX];nut_state balls[HINTNUTS_BALLS];} hint_storage;
static hint_storage *storage;
static int loaded_room=-1,puzzle;
static const actor_profile_t profile={0x192,ACTORCAT_ENEMY,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static const actor_profile_t friendly_profile={0x192,ACTORCAT_BG,ACTOR_FLAG_TARGETABLE,0,0,0,0};
static int abs32(int n){return n<0?-n:n;}
static unsigned clip(unsigned state) {
    static const uint8_t clips[]={0,0,1,2,3,4,5,6,7,6,8,8,0};return clips[state];
}
static void set_state(hint_state *s,unsigned state,unsigned timer){s->state=state;s->age=0;s->anim=0;s->timer=timer;
    if(state==BURROW)gameplay.world_sfx|=1u<<GP_SFX_SCRUB_DOWN;
    if(state==UNBURROW)gameplay.world_sfx|=1u<<GP_SFX_SCRUB_HIT;
    if(state==FREEZE || state==LEAVE)gameplay.world_sfx|=1u<<GP_SFX_SCRUB_FAINT;
}
static void turn(uint16_t *yaw,uint16_t target,int max){int16_t d=target-*yaw;int step=d/2;if(step>max)step=max;if(step<-max)step=-max;*yaw+=step;}
bool hintnuts_init(void *memory,unsigned bytes) {
    if(!memory || bytes<sizeof(*storage))return false;
    storage=memory;memset(storage,0,sizeof(*storage));loaded_room=-1;puzzle=0;return true;
}
void hintnuts_reset(void) {
    unsigned i;if(!storage)return;
    for(i=0;i<HINTNUTS_MAX;++i)actor_kill(actor_resolve(storage->hints[i].handle));
    memset(storage,0,sizeof(*storage));loaded_room=-1;puzzle=0;
}
bool hintnuts_room(unsigned room) {
    unsigned i;for(i=0;i<HINT_NUTS_COUNT;++i)if(hint_spawns[i].room==(int)room)return true;return false;
}
static void spawn(unsigned index,unsigned slot) {
    hint_state *s=&storage->hints[slot];const skull_spawn *p=&hint_spawns[index];actor_t *a;
    s->spawn=index;s->state=GONE;
    if(save_get_clear(SAVE_SCENE_DEKU_TREE,p->room) || ((uint16_t)p->params==0x9B00 && save_get_clear(SAVE_SCENE_DEKU_TREE,9)))return;
    a=actor_spawn(&profile,SAVE_SCENE_DEKU_TREE,p->room,p->x,p->y,p->z,p->yaw,p->params&255);if(!a)return;
    s->handle=actor_handle(a);set_state(s,WAIT,100+index*7%50);
    a->attention=ATTN_ENEMY;a->range=ATTN_RANGE_3;a->navi_text=0x60A;a->focus[1]=20;a->arrow_y=26;
    s->body.actor=a;s->body.shape=COLSHAPE_CYLINDER;s->body.radius=18;s->body.height=5;s->body.mass=MASS_HEAVY;
    s->body.ac_type=AC_TYPE_PLAYER;s->body.ac_bumper=0xFFCFFFFFu;s->body.tag=0x7600+slot;
    s->body.oc_flags1=OC1_ON|OC1_TYPE_ALL;s->body.oc_flags2=OC2_TYPE_1;
}
static void fire(actor_t *a) {
    unsigned i;int32_t sn,cs;
    gameplay.world_sfx|=1u<<GP_SFX_SCRUB_THROW;
    for(i=0;i<HINTNUTS_BALLS;++i)if(!storage->balls[i].live) {
        nut_state *n=&storage->balls[i];memset(n,0,sizeof(*n));n->live=1;n->timer=30;n->yaw=a->yaw;
        kokiri_camera_sincos(n->yaw,&sn,&cs);n->pos[0]=a->x+23*sn/65536;n->pos[1]=a->y+12;n->pos[2]=a->z+23*cs/65536;
        n->body.shape=COLSHAPE_CYLINDER;n->body.radius=13;n->body.height=13;n->body.at_damage=8;
        n->body.ac_type=AC_TYPE_PLAYER;n->body.ac_bumper=0xFFCFFFFFu;n->body.ac_flags=COL_OUTSIDE_ACTOR;n->body.tag=0x7700+i;
        return;
    }
}
static void tick_ball(nut_state *n,const gameplay_input_t *in) {
    int32_t sn,cs;unsigned r=n->body.result;
    if(n->wall || (r&(COL_RES_AT_HIT|COL_RES_AC_HIT))) {
        if(!n->reflected && (gameplay.equipped&GP_SHIELD) && (r&COL_RES_AT_HIT) && (r&COL_RES_AT_BOUNCED)) {
            n->reflected=1;n->yaw=in->yaw;n->timer=30;n->wall=0;n->body.result=0;return;
        }
        n->live=0;gameplay.events|=GP_EVENT_NUT_BREAK;return;
    }
    if(--n->timer<=-300){n->live=0;return;}
    if(n->timer<=0 && n->vy>-20)--n->vy;
    kokiri_camera_sincos(n->yaw,&sn,&cs);
    n->wall=gameplay_ball_move(n->pos,10*sn/65536,n->vy,10*cs/65536);n->roll+=0x2AA8;
}
static void reset_wait(hint_state *s,actor_t *a) {
    const skull_spawn *p=&hint_spawns[s->spawn];set_state(s,WAIT,100+s->spawn*7%50);
    a->x=p->x;a->y=p->y;a->z=p->z;a->flags=profile.flags;a->profile=&profile;a->attention=ATTN_ENEMY;
    s->friendly=s->post_spit=0;s->body.height=5;
}
static void tick(hint_state *s,actor_t *a,const gameplay_input_t *in) {
    const skull_spawn *p=&hint_spawns[s->spawn];int dx=in->x-a->x,dz=in->z-a->z;
    unsigned distance=collide_isqrt(dx*dx+dz*dz),length=hint_clips[clip(s->state)][1];
    uint16_t toward=collide_heading(dx,dz);bool end;
    if(s->state==WAIT) {
        if(s->timer)--s->timer;
        if(distance>160 && abs32(in->y-a->y)<120 && (!s->timer || distance<480))set_state(s,UP,s->timer);
        return;
    }
    ++s->age;s->anim=(s->anim+1)%length;end=s->anim==0;
    switch(s->state) {
    case UP:
        if(s->age==8)gameplay.world_sfx|=1u<<GP_SFX_SCRUB_UP;
        s->body.height=5+(s->age>9?(s->age<12?s->age-9:3)*9:0);
        if(distance<120)set_state(s,BURROW,0);
        else if(end)set_state(s,!s->timer && distance>320?LOOK:STAND,!s->timer && distance>320?2:1);
        break;
    case LOOK:
        if(end && s->timer)--s->timer;
        if(distance<120 || !s->timer)set_state(s,BURROW,0);break;
    case STAND:
        if(!s->post_spit)turn(&a->yaw,toward,0xE38);
        if(end && s->timer)--s->timer;
        if(distance<120 || (!s->timer && s->post_spit)){s->post_spit=0;set_state(s,BURROW,0);}
        else if(!s->timer)set_state(s,SPIT,0);break;
    case SPIT:
        turn(&a->yaw,toward,0xE38);
        if(distance<120)set_state(s,BURROW,0);
        else if(end){s->post_spit=1;set_state(s,STAND,2);}
        else if(s->age==6)fire(a);break;
    case BURROW:
        s->body.height=5+(s->age<3?(3-s->age)*12:0);
        collide_world_push(a,(p->x-a->x)/2,(p->z-a->z)/2);
        if(end)reset_wait(s,a);break;
    case UNBURROW:
        turn(&a->yaw,toward,0xE38);
        if(end) {
            if(s->friendly){s->move_yaw=toward+0x8000;set_state(s,RUN,5);}
            else {set_state(s,FREEZE,0);a->flags=0;if(puzzle==-3){puzzle=-4;gameplay.events|=GP_EVENT_DENIED;}}
        }break;
    case RUN: {
        if((s->age%4)==0)gameplay.world_sfx|=1u<<GP_SFX_SCRUB_WALK;
        int32_t sn,cs;uint16_t move=(uint16_t)s->move_yaw;unsigned speed=s->age<5?3+s->age:7;
        if(end && s->timer)--s->timer;
        turn(&move,s->timer?toward+0x8000:collide_heading(p->x-a->x,p->z-a->z),0xE38);s->move_yaw=move;
        a->yaw=move+0x8000;kokiri_camera_sincos(move,&sn,&cs);collide_world_push(a,speed*sn/65536,speed*cs/65536);
        if(distance<130 && (in->interact || distance<36 || gameplay.target==s->handle) && gameplay_actor_message(0x1000|((uint16_t)p->params>>8)))set_state(s,TALK,0);
        else if(!s->timer && abs32(a->x-p->x)<20 && abs32(a->z-p->z)<20)set_state(s,BURROW,0);
        break;}
    case TALK:
        if(!gameplay.talking && world_props_enemy_drop(a->x,a->y,a->z,3,1))set_state(s,LEAVE,100);
        break;
    case LEAVE: {
        int32_t sn,cs;turn(&a->yaw,toward+0x8000,0x800);kokiri_camera_sincos(a->yaw,&sn,&cs);collide_world_push(a,3*sn/65536,3*cs/65536);
        if(s->timer && !--s->timer) {
            if(a->params==3){save_set_clear(SAVE_SCENE_DEKU_TREE,p->room);puzzle=3;}
            actor_kill(a);s->handle=0;s->state=GONE;
        }break;}
    case FREEZE:
        if(puzzle==3 || puzzle==-4){s->resetting=puzzle==-4;set_state(s,SINK,0);}break;
    case SINK:
        a->y-=7;
        if(a->y<=p->y-35) {
            if(s->resetting)reset_wait(s,a);
            else {actor_kill(a);s->handle=0;s->state=GONE;}
        }break;
    default:break;
    }
}
void hintnuts_step(const gameplay_input_t *in) {
    unsigned i,slot=0;if(!storage)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE){if(loaded_room>=0)hintnuts_reset();return;}
    if(loaded_room!=in->room) {
        hintnuts_reset();loaded_room=in->room;
        for(i=0;i<HINT_NUTS_COUNT && slot<HINTNUTS_MAX;++i)if(hint_spawns[i].room==in->room)spawn(i,slot++);
    }
    for(i=0;i<HINTNUTS_MAX;++i) {
        hint_state *s=&storage->hints[i];actor_t *a=actor_resolve(s->handle);if(!a)continue;
        s->phase+=2;if(s->phase>=3){s->phase-=3;tick(s,a,in);}
    }
    for(i=0;i<HINTNUTS_BALLS;++i) {
        nut_state *n=&storage->balls[i];if(!n->live)continue;
        /* Consume contact before registration can erase it on the skipped 20 Hz tick. */
        if(n->body.result&(COL_RES_AT_HIT|COL_RES_AC_HIT)){tick_ball(n,in);n->phase=0;continue;}
        n->phase+=2;if(n->phase>=3){n->phase-=3;tick_ball(n,in);}
    }
}
void hintnuts_register(void) {
    unsigned i;if(!storage)return;
    for(i=0;i<HINTNUTS_MAX;++i) {
        hint_state *s=&storage->hints[i];if(!actor_resolve(s->handle))continue;
        s->body.result=0;
        if((s->state==UP && s->age>=9) || s->state==LOOK || s->state==STAND || s->state==SPIT || (s->state==BURROW && s->age<4))collide_set_ac(&s->body);
        if(s->state!=LEAVE)collide_set_oc(&s->body);
    }
    for(i=0;i<HINTNUTS_BALLS;++i) {
        nut_state *n=&storage->balls[i];collider_t *c=&n->body;if(!n->live)continue;
        c->x=n->pos[0];c->y=n->pos[1];c->z=n->pos[2];c->at_type=n->reflected?AT_TYPE_PLAYER:AT_TYPE_ENEMY;c->at_dmg=n->reflected?DMG_DEKU_STICK:0xFFCFFFFFu;
        collide_set_at(c);collide_set_ac(c);
    }
}
void hintnuts_collect(void) {
    unsigned i;if(!storage)return;
    for(i=0;i<HINTNUTS_MAX;++i) {
        hint_state *s=&storage->hints[i];actor_t *a=actor_resolve(s->handle);const skull_spawn *p;
        if(!a || !(s->body.result&COL_RES_AC_HIT))continue;
        s->body.result&=~COL_RES_AC_HIT;
        if(!s->body.ac_hit || s->body.ac_hit->tag<0x7700 || s->body.ac_hit->tag>=0x7700+HINTNUTS_BALLS){set_state(s,BURROW,0);continue;}
        p=&hint_spawns[s->spawn];
        if(((uint16_t)p->params>>8) && (a->params==0 || puzzle==2)) {
            s->friendly=1;a->flags=ACTOR_FLAG_TARGETABLE;a->profile=&friendly_profile;a->attention=ATTN_NPC;
            if(a->params==0)save_set_clear(SAVE_SCENE_DEKU_TREE,p->room);
        }
        if(a->params>0 && a->params<4 && !s->friendly) {
            if(puzzle==-4)puzzle=0;
            if(a->params==puzzle+1)++puzzle;
            else {if(puzzle>0)puzzle=-puzzle;--puzzle;}
        }
        actor_hit_filter(a,true,255,100);
        s->body.height=37;set_state(s,UNBURROW,0);
    }
}
bool hintnuts_body(unsigned i,int32_t p[3],uint16_t *yaw,unsigned *frame) {
    hint_state *s;actor_t *a;if(!storage || i>=HINTNUTS_MAX)return false;
    s=&storage->hints[i];a=actor_resolve(s->handle);if(!a)return false;
    p[0]=a->x;p[1]=a->y;p[2]=a->z;*yaw=a->yaw;*frame=hint_clips[clip(s->state)][0]+s->anim;return true;
}
bool hintnuts_flower(unsigned i,int32_t p[3],uint16_t *yaw) {
    unsigned n=0,j;if(loaded_room<0)return false;
    for(j=0;j<HINT_NUTS_COUNT;++j)if(hint_spawns[j].room==loaded_room && n++==i) {
        p[0]=hint_spawns[j].x;p[1]=hint_spawns[j].y;p[2]=hint_spawns[j].z;*yaw=hint_spawns[j].yaw;return true;
    }return false;
}
bool hintnuts_ball(unsigned i,int32_t p[3],uint16_t *roll) {
    nut_state *n;if(!storage || i>=HINTNUTS_BALLS || !storage->balls[i].live)return false;
    n=&storage->balls[i];memcpy(p,n->pos,sizeof(n->pos));*roll=n->roll;return true;
}

unsigned hintnuts_filter(unsigned i){return storage && i<HINTNUTS_MAX?actor_filter_level(actor_resolve(storage->hints[i].handle)):0;}
