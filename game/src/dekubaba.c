#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* En_Dekubaba normal variant, original three-section stem and damage/drop
 * rules. No random replacement for the source nut or pruned stick reward. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "dekubaba.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_collision.h"
#include "kokiri_camera.h"
#include "save_state.h"
#include "world_props.h"
#include "dungeon_enemy_data.h"
#include <string.h>
enum {WAIT,GROW,PREPARE,LUNGE,PULLBACK,DECIDE,RETRACT,HIT,STUN,SWAY,PRUNED,SHRINK,STICK,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t head,stem[3];
    dekubaba_view view;
    int32_t vy,yq;
    uint16_t timer,anim,invuln;
    uint8_t spawn,state,phase,health,reaction;
} baba_state;
static baba_state *babas;
static int loaded_room=-1;
static const uint8_t damage[32]={16,2,1,2,0xE2,2,2,2,0xF1,0xF2,0xF4,0x24,2,2,2,2,2,0x24,0,0,0,0,0xF1,0xF4,0xF2,0xF2,0xF8,0xF4,0,0,4,0};
static const actor_profile_t profile={0x55,ACTORCAT_ENEMY,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static int abs32(int n){return n<0?-n:n;}
static bool angle(int16_t *v,int target,int speed) {
    int d=target-*v;if(d>speed)d=speed;if(d<-speed)d=-speed;*v+=d;return *v==target;
}
static void face(baba_state *s,const gameplay_input_t *in,int rate) {
    int16_t d=(int16_t)(collide_heading(in->x-s->view.home[0],in->z-s->view.home[2])-s->view.yaw);
    int step=d/2;if(step>rate)step=rate;if(step<-rate)step=-rate;s->view.yaw+=step;
}
static void head_position(baba_state *s,actor_t *a) {
    int32_t sn,cs,h=0,v=0;unsigned i;
    for(i=0;i<3;++i){kokiri_camera_sincos(s->view.stem[i],&sn,&cs);h+=20*cs;v-=20*sn;}
    kokiri_camera_sincos(s->view.yaw,&sn,&cs);
    a->x=s->view.home[0]+(int32_t)((int64_t)sn*h>>32);a->z=s->view.home[2]+(int32_t)((int64_t)cs*h>>32);a->y=s->view.home[1]+v/65536;
}
static void focus_from(actor_t *a,int32_t x,int32_t y,int32_t z){a->focus[0]=(int16_t)(x-a->x);a->focus[1]=(int16_t)(y-a->y);a->focus[2]=(int16_t)(z-a->z);}
static void state(baba_state *s,unsigned mode,unsigned timer) {
    s->state=mode;s->timer=timer;s->anim=0;
}
bool dekubaba_init(void *storage,unsigned bytes) {
    if(!storage || bytes<sizeof(*babas)*DEKUBABA_MAX)return false;
    babas=storage;memset(babas,0,sizeof(*babas)*DEKUBABA_MAX);loaded_room=-1;return true;
}
void dekubaba_reset(void) {
    unsigned i;if(!babas)return;
    for(i=0;i<DEKUBABA_MAX;++i)actor_kill(actor_resolve(babas[i].handle));
    memset(babas,0,sizeof(*babas)*DEKUBABA_MAX);loaded_room=-1;
}
bool dekubaba_room(unsigned room) {
    unsigned i;for(i=0;i<DEKU_BABA_COUNT;++i)if(baba_spawns[i].room==(int)room)return true;return false;
}
static void spawn(unsigned index,unsigned slot) {
    baba_state *s=&babas[slot];const skull_spawn *p=&baba_spawns[index];unsigned i;
    actor_t *a=actor_spawn(&profile,SAVE_SCENE_DEKU_TREE,p->room,p->x,p->y+14,p->z,p->yaw,0);if(!a)return;
    s->handle=actor_handle(a);s->spawn=index;s->health=2;state(s,WAIT,45);
    s->view.head[0]=a->x;s->view.head[1]=a->y;s->view.head[2]=a->z;
    s->view.home[0]=p->x;s->view.home[1]=p->y;s->view.home[2]=p->z;s->view.yaw=p->yaw;s->view.pitch=-0x4000;s->view.scale=32768;
    for(i=0;i<3;++i)s->view.stem[i]=-0x4000;
    a->attention=ATTN_ENEMY;a->range=ATTN_RANGE_1;a->navi_text=0x607;
    s->head.actor=a;s->head.shape=COLSHAPE_CAPSULE;s->head.radius=15;s->head.ac_type=AC_TYPE_PLAYER;
    s->head.ac_bumper=DMG_DEFAULT;s->head.damage_table=damage;s->head.ac_flags=COL_AC_ELEMENT;
    s->head.at_type=AT_TYPE_ENEMY;s->head.at_dmg=DMG_DEFAULT;s->head.at_damage=8;s->head.mass=MASS_IMMOVABLE;
    s->head.oc_flags1=OC1_ON|OC1_TYPE_ALL;s->head.oc_flags2=OC2_TYPE_1;s->head.tag=0x7500+slot*4;
    for(i=0;i<3;++i){s->stem[i]=s->head;s->stem[i].at_type=0;s->stem[i].radius=8;s->stem[i].tag+=i+1;}
}
static void tick(baba_state *s,actor_t *a,const gameplay_input_t *in) {
    dekubaba_view *v=&s->view;unsigned i;bool done=true;
    int dx=in->x-v->home[0],dz=in->z-v->home[2];bool near=abs32(dx)<240 && abs32(dz)<240 && dx*dx+dz*dz<240*240;
    if(s->invuln)--s->invuln;
    ++s->anim;
    switch(s->state) {
    case WAIT:
        if(s->timer)--s->timer;a->x=v->home[0];a->y=v->home[1]+14;a->z=v->home[2];
        if(!s->timer && near && dx*dx+dz*dz<200*200 && abs32(in->y-a->y)<30)state(s,GROW,15);
        break;
    case GROW:
        --s->timer;v->scale=32768+(15-s->timer)*32768/15;
        angle(&v->pitch,0x1800,0x800);face(s,in,0xE38);
        angle(&v->stem[0],-0xAAA,0x38E);angle(&v->stem[1],-0x31C7,0x222);angle(&v->stem[2],-0x5555,0x222);head_position(s,a);
        if(!s->timer)state(s,near?PREPARE:RETRACT,near?8:15);break;
    case PREPARE:
        angle(&v->pitch,0x1800,0xE38);face(s,in,0xE38);
        angle(&v->stem[0],0xAAA,0x444);angle(&v->stem[1],-0x4718,0x888);angle(&v->stem[2],-0x6AA4,0x888);head_position(s,a);
        if(!--s->timer)state(s,LUNGE,0);break;
    case LUNGE:
        angle(&v->pitch,0,0x222);
        for(i=0;i<3;++i)done&=angle(&v->stem[i],-0xE38,s->anim*10+(0x38E<<i));
        if(done || s->timer){if(++s->timer>10)state(s,PULLBACK,0);}
        head_position(s,a);break;
    case PULLBACK:
        angle(&v->pitch,-0x93E,0x38E);
        for(i=0;i<3;++i)done&=angle(&v->stem[i],s->timer<11?-0x888:(i==0?-0x1555:i==1?-0x38E3:-0x5C71),s->timer<11?0x16C:0x444);
        if(done || s->timer)++s->timer;
        head_position(s,a);if(s->timer>30)state(s,DECIDE,46);break;
    case DECIDE:
        face(s,in,(s->timer%5)*0x222);head_position(s,a);
        if(!near)state(s,RETRACT,15);else if(!s->timer || !--s->timer)state(s,PREPARE,8);break;
    case RETRACT:
        if(s->timer)--s->timer;v->scale=32768+s->timer*32768/15;
        for(i=0;i<3;++i)angle(&v->stem[i],-0x4000,0xE38);
        angle(&v->pitch,-0x4000,0xE38);a->y=v->home[1]+14+(int)s->timer*3;
        a->x=v->home[0];a->z=v->home[2];if(!s->timer)state(s,WAIT,45);break;
    case HIT:
        done=angle(&v->pitch,-0x4000,0xE38);
        for(i=0;i<3;++i)done&=angle(&v->stem[i],-0x4000,0xE38);
        head_position(s,a);
        if(done)state(s,!s->health?SHRINK:s->reaction?STUN:PREPARE,!s->health?10:s->reaction==2?60:s->reaction?40:8);
        break;
    case STUN:if(!--s->timer)state(s,PREPARE,8);break;
    case SWAY:
        for(i=0;i<3;++i)angle(&v->stem[i],-0x4000,0x444);head_position(s,a);
        if(!--s->timer)state(s,PREPARE,8);break;
    case PRUNED: {
        int32_t sn,cs;bg_vec_t probe={a->x,a->y+1,a->z};int32_t floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);
        s->vy-=205;s->yq+=s->vy*3/2;a->y=s->yq/256;
        kokiri_camera_sincos(v->yaw,&sn,&cs);a->x-=3*sn/65536;a->z-=3*cs/65536;v->pitch-=0x800;
        if(s->vy<0 && floor!=BG_Y_MIN && a->y<=floor){a->y=floor;state(s,STICK,200);v->stick=1;v->scale=3*65536;}
        break;
    }
    case SHRINK:
        v->scale-=6554;if(v->scale<6554)v->scale=6554;
        if(a->y>v->home[1])a->y-=5;
        if(v->scale==6554 && world_props_enemy_drop(a->x,a->y,a->z,12,1)){actor_kill(a);s->handle=0;s->state=GONE;}
        break;
    case STICK:
        if(s->timer)--s->timer;
        dx=in->x-a->x;dz=in->z-a->z;
        if(in->grounded && !gameplay.talking && abs32(dx)<50 && abs32(dz)<50 && dx*dx+dz*dz<2500 && abs32(in->y-a->y)<10) {
            bool first=!save_state.stick_owned;save_item_give(SAVE_ITEM_DEKU_STICK);
            if(first)gameplay_drop_message(13);s->timer=0;
        }
        if(!s->timer){actor_kill(a);s->handle=0;s->state=GONE;}break;
    default:break;
    }
    v->head[0]=a->x;v->head[1]=a->y;v->head[2]=a->z;a->yaw=v->yaw;
    /* z_en_dekubaba.c:1227 (DrawStemExtended, i == 0): the matrix starts at
     * actor.world.pos (the head) and the first 20-unit step moves back toward
     * the stem base. Sway focus = home + (0, 40*size, 0). Wait draws the
     * retracted stem, which leaves focus at its init value (the actor). */
    if(s->state==SWAY)focus_from(a,v->home[0],v->home[1]+40,v->home[2]);
    else if(s->state==WAIT)a->focus[0]=a->focus[1]=a->focus[2]=0;
    else {
        int32_t sn,cs,ys,yc,h;
        kokiri_camera_sincos(v->stem[0],&sn,&cs);h=20*cs;
        kokiri_camera_sincos(v->yaw,&ys,&yc);
        a->focus[0]=(int16_t)-(int32_t)((int64_t)ys*h>>32);
        a->focus[1]=(int16_t)(20*sn/65536);
        a->focus[2]=(int16_t)-(int32_t)((int64_t)yc*h>>32);
    }
    a->arrow_y=15;                      /* lockOnArrowOffset 1500 * scale 0.01 */
    v->frame=(s->state==LUNGE || s->state==PULLBACK || s->state==HIT)?baba_clips[1][0]+s->anim%baba_clips[1][1]:s->anim%baba_clips[0][1];
}
void dekubaba_step(const gameplay_input_t *in) {
    unsigned i,n=0;if(!babas)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE){if(loaded_room>=0)dekubaba_reset();return;}
    if(loaded_room!=in->room){dekubaba_reset();loaded_room=in->room;for(i=0;i<DEKU_BABA_COUNT && n<DEKUBABA_MAX;++i)if(baba_spawns[i].room==loaded_room)spawn(i,n++);}
    for(i=0;i<DEKUBABA_MAX;++i){baba_state *s=&babas[i];actor_t *a=actor_resolve(s->handle);if(!a)continue;s->phase+=2;if(s->phase>=3){s->phase-=3;tick(s,a,in);}}
}
void dekubaba_register(void) {
    unsigned i,j;if(!babas)return;
    for(i=0;i<DEKUBABA_MAX;++i) {
        baba_state *s=&babas[i];actor_t *a=actor_resolve(s->handle);int32_t x,y,z,sn,cs;
        if(!a || s->state>=PRUNED)continue;
        s->head.ax=s->head.bx=a->x;s->head.ay=s->head.by=a->y;s->head.az=s->head.bz=a->z;
        s->head.ac_flags=COL_AC_ELEMENT|(s->state==WAIT?COL_AC_HARD:0);s->head.invincible=s->invuln!=0;
        s->head.result=0;
        if(s->state!=HIT && s->state!=SWAY)collide_set_ac(&s->head);
        if(s->state!=STUN && s->state!=HIT && s->state!=SWAY)collide_set_at(&s->head);
        collide_set_oc(&s->head);x=a->x;y=a->y;z=a->z;
        for(j=0;j<3;++j) {
            collider_t *c=&s->stem[j];int32_t h;
            c->ax=x;c->ay=y;c->az=z;
            kokiri_camera_sincos(s->view.stem[j],&sn,&cs);y+=20*sn/65536;h=20*cs/65536;
            kokiri_camera_sincos(s->view.yaw,&sn,&cs);x-=h*sn/65536;z-=h*cs/65536;
            c->bx=x;c->by=y;c->bz=z;c->result=0;c->invincible=s->invuln!=0;
            if(s->state==STUN)collide_set_ac(c);
            if(s->state!=WAIT)collide_set_oc(c);
        }
    }
}
void dekubaba_collect(void) {
    unsigned i,j;if(!babas)return;
    for(i=0;i<DEKUBABA_MAX;++i) {
        baba_state *s=&babas[i];actor_t *a=actor_resolve(s->handle);collider_t *hit=0;int health;
        if(!a || s->state>=PRUNED || s->state==WAIT)continue;
        if(s->head.result&COL_RES_AC_HIT)hit=&s->head;
        for(j=0;j<3 && !hit;++j)if(s->stem[j].result&COL_RES_AC_HIT)hit=&s->stem[j];
        if(!hit || (!hit->ac_damage && !hit->ac_effect))continue;
        health=s->health-hit->ac_damage;s->view.scale=65536;
        if(s->state==STUN && (hit->ac_effect==15 || hit->ac_effect==14)) {
            s->reaction=0;
            if(health>0)state(s,SWAY,35);
            else {state(s,PRUNED,0);s->view.pruned=1;s->vy=4*256;s->yq=a->y*256;}
        } else {
            if(s->state==STUN && hit->ac_effect==1)continue;
            s->reaction=(hit->ac_effect==1 || hit->ac_effect==14)?2:s->state==PULLBACK?1:0;
            if(hit->ac_effect==14)health=s->health;
            if(s->state==PULLBACK && health<=0)health=1;
            state(s,HIT,0);
        }
        actor_hit_filter(a,s->reaction==2, s->reaction==2?155:255,s->state==SWAY?35:s->reaction==2?62:42);
        gameplay.world_sfx|=1u<<(health>0?GP_SFX_DEKU_HIT:GP_SFX_DEKU_DEAD);
        s->health=health>0?health:0;if(!s->health)a->flags&=~ACTOR_FLAG_TARGETABLE;
    }
}
const dekubaba_view *dekubaba_body(unsigned i) {
    if(!babas || i>=DEKUBABA_MAX || !actor_resolve(babas[i].handle))return 0;
    if(babas[i].state==STICK && babas[i].timer<=40 && !(babas[i].timer&1))return 0;
    return &babas[i].view;
}

unsigned dekubaba_filter(unsigned i){return babas && i<DEKUBABA_MAX?actor_filter_level(actor_resolve(babas[i].handle)):0;}
