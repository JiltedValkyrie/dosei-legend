#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* En_Goma eggs and larvae. Eggs break without a drop. Hatched larvae use
 * source random table 3, including the same inventory/health filtering. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "gohma_larva.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_camera.h"
#include "kokiri_collision.h"
#include "save_state.h"
#include "item_drop.h"
#include "world_props.h"
#include "dungeon_enemy_data.h"
#include <string.h>
enum {EGG,FALL,HATCH,STAND,CHASE,PREPARE,JUMP,LAND,HURT,FLEE,STUN,DIE,DEAD,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t attack,body;
    int32_t yq,speed,vy,scale;
    uint16_t timer,age,anim,move_yaw,toward,stun;
    int16_t egg_offset;
    uint8_t state,phase,health,hurt,invuln,detect,hatch,ground;
    item_drop_t drop;
} goma_state;
static goma_state *larvae;
static int loaded_scene=-1,loaded_room=-1;
static uint32_t random_state=0x881303u;
static const actor_profile_t profile={0x2B,ACTORCAT_ENEMY,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static unsigned random16(void){random_state=random_state*1664525u+1013904223u;return random_state>>16;}
static int abs32(int n){return n<0?-n:n;}
static int approach(int value,int target,int fraction,int maximum){int d=(target-value)/fraction;if(d>maximum)d=maximum;if(d<-maximum)d=-maximum;return value+d;}
static uint16_t turn(uint16_t value,uint16_t target,unsigned fraction,int maximum){return value+approach(0,(int16_t)(target-value),fraction,maximum);}
static unsigned clip(unsigned state){static const uint8_t c[]={0,0,3,0,1,2,3,4,5,1,0,6,7,0};return c[state];}
static void state(goma_state *s,unsigned mode,unsigned timer){s->state=mode;s->timer=timer;s->age=s->anim=0;}
bool gohma_larva_init(void *memory,unsigned bytes) {
    if(!memory || bytes<sizeof(*larvae)*GOHMA_LARVA_MAX)return false;
    larvae=memory;memset(larvae,0,sizeof(*larvae)*GOHMA_LARVA_MAX);loaded_scene=loaded_room=-1;return true;
}
void gohma_larva_reset(void) {
    unsigned i;if(!larvae)return;
    for(i=0;i<GOHMA_LARVA_MAX;++i)actor_kill(actor_resolve(larvae[i].handle));
    memset(larvae,0,sizeof(*larvae)*GOHMA_LARVA_MAX);loaded_scene=loaded_room=-1;
}
bool gohma_larva_room(unsigned scene,unsigned room) {
    unsigned i;if(scene==SAVE_SCENE_DEKU_TREE_BOSS)return true;if(scene!=SAVE_SCENE_DEKU_TREE)return false;
    for(i=0;i<GOMA_LARVA_COUNT;++i)if(goma_spawns[i].room==(int)room)return true;return false;
}
static bool spawn(unsigned slot,unsigned scene,int room,int32_t x,int32_t y,int32_t z,uint16_t yaw,unsigned params) {
    goma_state *s=&larvae[slot];actor_t *a=actor_spawn(&profile,scene,room,x,y,z,yaw,params);if(!a)return false;
    memset(s,0,sizeof(*s));s->handle=actor_handle(a);s->health=2;s->scale=65536;s->yq=y*256;s->move_yaw=yaw;
    s->egg_offset=params>=8?-15:15;state(s,params<3?FALL:EGG,50);s->invuln=params<3?10:0;s->speed=params<3?384:0;
    a->focus[1]=20;a->range=ATTN_RANGE_3;a->attention=ATTN_ENEMY;a->navi_text=0x602;
    s->attack.actor=a;s->attack.shape=COLSHAPE_CYLINDER;s->attack.radius=15;s->attack.height=30;s->attack.y_shift=10;
    s->attack.at_type=AT_TYPE_ENEMY;s->attack.at_dmg=0xFFCFFFFFu;s->attack.at_damage=8;s->attack.mass=MASS_HEAVY;
    s->attack.oc_flags1=OC1_ON|OC1_TYPE_ALL;s->attack.oc_flags2=OC2_TYPE_1;s->attack.tag=0x7800+slot*2;
    s->body=s->attack;s->body.at_type=0;s->body.ac_type=AC_TYPE_PLAYER;s->body.ac_bumper=0xFFDFFFFFu;s->body.oc_flags1=0;s->body.tag++;
    return true;
}
bool gohma_larva_alive(unsigned slot){return larvae && slot<GOHMA_LARVA_MAX && actor_resolve(larvae[slot].handle)!=0;}
bool gohma_larva_spawn(unsigned slot,int32_t x,int32_t y,int32_t z,uint16_t yaw) {
    if(!larvae || slot>=GOHMA_LARVA_MAX || gohma_larva_alive(slot) || save_state.scene_id!=SAVE_SCENE_DEKU_TREE_BOSS)return false;
    return spawn(slot,SAVE_SCENE_DEKU_TREE_BOSS,loaded_room,x,y,z,yaw,slot);
}
static void hatch(goma_state *s,actor_t *a){state(s,HATCH,5);s->scale=32768;s->speed=0;a->yaw=s->move_yaw=s->toward;a->navi_text=0x603;}
static void tick(goma_state *s,actor_t *a,const gameplay_input_t *in) {
    int dx=in->x-a->x,dz=in->z-a->z;int32_t sn,cs;unsigned length=goma_clips[clip(s->state)][1];
    s->toward=collide_heading(dx,dz);if(s->timer)--s->timer;if(s->hurt)--s->hurt;if(s->invuln)--s->invuln;++s->age;
    if(s->state!=STUN || s->timer)s->anim=(s->anim+(s->state==FLEE?2:1))%length;
    switch(s->state) {
    case EGG:
        if(abs32(dx)<100 && abs32(dz)<100){if(++s->detect>9)state(s,FALL,50);}else s->detect=0;
        break;
    case FALL:
        s->egg_offset=approach(s->egg_offset,15,1,2);
        if(s->ground) {
            if(a->params>5)hatch(s,a);
            else if(!s->hatch){s->hatch=1;s->timer=3;}
            s->speed=approach(s->speed,0,5,13);
        }
        if(a->params<3 && s->hatch && !s->timer) {
            if(s->hatch==1){s->hatch=2;s->timer=3;s->vy=5*256;s->speed=512;}
            else if(s->hatch==2){s->hatch=3;s->timer=80;}
            else hatch(s,a);
        }break;
    case HATCH:if(!s->timer)state(s,STAND,10+random16()%30);break;
    case STAND:
        s->speed=approach(s->speed,0,2,512);a->yaw=turn(a->yaw,s->toward,2,3000);
        if(!s->timer)state(s,CHASE,70+random16()%110);break;
    case CHASE:
        s->speed=approach(s->speed,2560/3,2,512);s->move_yaw=turn(s->move_yaw,s->toward,3,2000);a->yaw=turn(a->yaw,s->move_yaw,2,3000);
        if(abs32(dx)<=150 && abs32(dz)<=150 && dx*dx+dz*dz<=22500)state(s,PREPARE,30);break;
    case PREPARE:
        s->speed=approach(s->speed,0,2,512);s->move_yaw=turn(s->move_yaw,s->toward,2,4000);a->yaw=turn(a->yaw,s->toward,2,3000);
        if(!s->timer){state(s,JUMP,0);s->vy=8*256;s->ground=0;}break;
    case JUMP:
        s->speed=approach(s->speed,2560,2,1280);
        if(s->vy<=0 && s->ground)state(s,LAND,10);break;
    case LAND:case HURT:case DIE:
        if(s->ground)s->speed=approach(s->speed,0,1,512);
        if(!s->timer) {
            if(s->state==LAND)state(s,STAND,10+random16()%30);
            else if(s->state==DIE)state(s,DEAD,3);
            else if(s->health)state(s,FLEE,20);
            else {state(s,DIE,30);s->invuln=100;a->flags=0;}
        }break;
    case FLEE:
        s->speed=approach(s->speed,5120/3,2,512);s->move_yaw=turn(s->move_yaw,s->toward+0x8000,3,2000);a->yaw=turn(a->yaw,s->move_yaw,2,3000);
        if(!s->timer)state(s,STAND,10+random16()%30);break;
    case STUN:
        if(s->ground)s->speed=approach(s->speed,0,2,512);
        if(s->stun)--s->stun;else state(s,STAND,10+random16()%30);break;
    case DEAD:
        s->speed=approach(s->speed,0,1,512);
        if(!s->timer) {
            s->scale=approach(s->scale,0,2,14746);
            if(s->scale<=6554 && world_props_enemy_drop(a->x,a->y,a->z,s->drop.item,s->drop.count)) {
                actor_kill(a);s->handle=0;s->state=GONE;return;
            }
        }break;
    default:break;
    }
    if(s->state!=EGG) {
        bg_vec_t probe;int32_t floor;
        kokiri_camera_sincos(s->move_yaw,&sn,&cs);
        collide_world_push(a,(int32_t)((int64_t)s->speed*sn>>24),(int32_t)((int64_t)s->speed*cs>>24));
        probe.x=a->x;probe.y=a->y+50;probe.z=a->z;floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);
        s->vy-=333;if(s->vy<-20*256)s->vy=-20*256;s->yq+=s->vy;a->y=s->yq/256;s->ground=0;
        if(floor!=BG_Y_MIN && a->y<=floor && s->vy<=0){a->y=floor;s->yq=floor*256;s->vy=0;s->ground=1;}
    }
    if(s->state!=DEAD)s->scale=approach(s->scale,65536,2,4915);
}
void gohma_larva_step(const gameplay_input_t *in) {
    unsigned i,slot=0;if(!larvae)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE && save_state.scene_id!=SAVE_SCENE_DEKU_TREE_BOSS){if(loaded_scene>=0)gohma_larva_reset();return;}
    if(loaded_scene!=save_state.scene_id || loaded_room!=in->room) {
        gohma_larva_reset();loaded_scene=save_state.scene_id;loaded_room=in->room;
        if(loaded_scene==SAVE_SCENE_DEKU_TREE)for(i=0;i<GOMA_LARVA_COUNT && slot<GOHMA_LARVA_MAX;++i) {
            const skull_spawn *p=&goma_spawns[i];if(p->room==in->room)spawn(slot++,loaded_scene,in->room,p->x,p->y,p->z,p->yaw,p->params);
        }
    }
    for(i=0;i<GOHMA_LARVA_MAX;++i) {
        goma_state *s=&larvae[i];actor_t *a=actor_resolve(s->handle);if(!a)continue;
        s->phase+=2;if(s->phase>=3){s->phase-=3;tick(s,a,in);}
    }
}
void gohma_larva_register(void) {
    unsigned i;if(!larvae)return;
    for(i=0;i<GOHMA_LARVA_MAX;++i) {
        goma_state *s=&larvae[i];if(!actor_resolve(s->handle))continue;
        s->attack.result=s->body.result=0;if(s->invuln || s->state>=DIE)continue;
        s->body.radius=gameplay.attack_phase?35:15;s->body.height=gameplay.attack_phase?35:30;s->body.y_shift=gameplay.attack_phase?0:10;
        if(!s->hurt)collide_set_ac(&s->body);collide_set_at(&s->attack);collide_set_oc(&s->attack);
    }
}
void gohma_larva_collect(void) {
    unsigned i;if(!larvae)return;
    for(i=0;i<GOHMA_LARVA_MAX;++i) {
        goma_state *s=&larvae[i];actor_t *a=actor_resolve(s->handle);uint32_t dmg;unsigned damage;
        if(!a)continue;
        if((s->attack.result&COL_RES_AT_HIT) && s->state==JUMP){state(s,LAND,10);s->speed=s->vy=0;}
        if(!(s->body.result&COL_RES_AC_HIT) || s->hurt || !s->health)continue;
        dmg=s->body.ac_hit?s->body.ac_hit->at_dmg:0;
        if(s->state==EGG || s->state==FALL){actor_kill(a);s->handle=0;s->state=GONE;continue;}
        if(dmg&DMG_DEKU_NUT){if(s->state!=STUN){gameplay.world_sfx|=1u<<GP_SFX_FREEZE;actor_hit_filter(a,true,180,100);state(s,STUN,3+random16()%15);s->stun=100;s->hurt=8;}continue;}
        damage=(dmg&DMG_JUMP_GIANT)?8:(dmg&(DMG_JUMP_MASTER|DMG_SPIN_GIANT|DMG_SLASH_GIANT))?4:
               (dmg&(DMG_JUMP_KOKIRI|DMG_SPIN_MASTER|DMG_SLASH_MASTER))?2:1;
        actor_hit_filter(a,false,255,5);
        gameplay.world_sfx|=1u<<(s->health>damage?GP_SFX_LARVA_HIT:GP_SFX_LARVA_DEAD);
        s->health=s->health>damage?s->health-damage:0;s->hurt=13;s->speed=20*256;s->move_yaw=s->toward+0x8000;
        state(s,HURT,s->health?10:5);if(!s->health)s->drop=item_drop_random(3,random16());
    }
}
unsigned gohma_larva_body(unsigned i,int32_t p[3],uint16_t *yaw,unsigned *frame,int32_t *scale) {
    goma_state *s;actor_t *a;if(!larvae || i>=GOHMA_LARVA_MAX)return 0;s=&larvae[i];a=actor_resolve(s->handle);if(!a)return 0;
    p[0]=a->x;p[1]=a->y;p[2]=a->z;*yaw=a->yaw;*scale=s->scale;*frame=goma_clips[clip(s->state)][0]+s->anim;
    if(s->state==EGG || s->state==FALL){p[1]+=s->egg_offset;return 1;}return 2;
}

unsigned gohma_larva_filter(unsigned i){return larvae && i<GOHMA_LARVA_MAX?actor_filter_level(actor_resolve(larvae[i].handle)):0;}
