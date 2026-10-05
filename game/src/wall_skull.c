#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/* En_Sw / En_Si. Normal wall spiders: damage table 14, random drop table 3.
 * Gold variants spawn a persistent token, never a random collectible. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "wall_skull.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_collision.h"
#include "save_state.h"
#include "world_props.h"
#include "item_drop.h"
#include "dungeon_enemy_data.h"
#include <string.h>
enum {IDLE,WARN,CHARGE,RETURNING,DYING,TOKEN,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t body;
    int32_t target[3],yq,vy;
    uint16_t timer,invuln,roll,frame;
    uint8_t spawn,state,health,phase,bounces;
    item_drop_t drop;
} wall_state;
static wall_state *spiders;
static int room_loaded=-1;
static uint32_t random_state=0xCAF2341u;
static const uint8_t damage[32]={1,2,1,2,1,2,2,2,1,2,4,4,4,4,0,0,0,4,0,0,0,0,1,2,4,2,4,8,0,0,0,0};
static const actor_profile_t normal_profile={0x95,ACTORCAT_ENEMY,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static const actor_profile_t gold_profile={0x95,ACTORCAT_NPC,0,0,0,0,0};
static unsigned group(const skull_spawn *p){return (((uint16_t)p->params>>8)-1)&31;}
static bool gold(const skull_spawn *p){return ((uint16_t)p->params&0xE000)!=0;}
static int abs32(int x){return x<0?-x:x;}
bool wall_skull_init(void *storage,unsigned bytes) {
    if(!storage || bytes<sizeof(*spiders)*WALL_SKULL_MAX)return false;
    spiders=storage;memset(spiders,0,sizeof(*spiders)*WALL_SKULL_MAX);room_loaded=-1;return true;
}
void wall_skull_reset(void) {
    unsigned i;if(!spiders)return;
    for(i=0;i<WALL_SKULL_MAX;++i)actor_kill(actor_resolve(spiders[i].handle));
    memset(spiders,0,sizeof(*spiders)*WALL_SKULL_MAX);room_loaded=-1;
}
unsigned wall_skull_models(unsigned room) {
    unsigned i,mask=0;for(i=0;i<WALL_SKULL_COUNT;++i)if(wall_spawns[i].room==(int)room)mask|=gold(&wall_spawns[i])?6:1;
    return mask;
}
static void spawn(unsigned index,unsigned slot) {
    wall_state *s=&spiders[slot];const skull_spawn *p=&wall_spawns[index];bool is_gold=gold(p);actor_t *a;
    if(is_gold && save_skull_collected(group(p),p->params&255)){s->state=GONE;return;}
    a=actor_spawn(is_gold?&gold_profile:&normal_profile,SAVE_SCENE_DEKU_TREE,p->room,p->x,p->y,p->z,p->yaw,p->params);
    if(!a)return;
    s->handle=actor_handle(a);s->spawn=index;s->health=is_gold?2:1;s->timer=20;
    a->attention=is_gold?ATTN_NONE:ATTN_ENEMY;a->range=ATTN_RANGE_2;a->navi_text=is_gold?0x620:0x61F;
    s->body.actor=a;s->body.shape=COLSHAPE_CAPSULE;s->body.radius=21;s->body.mass=MASS_IMMOVABLE;
    s->body.ac_type=AC_TYPE_PLAYER;s->body.ac_bumper=0xFFC3FFFEu;s->body.damage_table=damage;
    s->body.at_type=AT_TYPE_ENEMY;s->body.at_dmg=DMG_DEFAULT;s->body.at_damage=is_gold?16:8;
    s->body.oc_flags1=OC1_ON|OC1_TYPE_ALL;s->body.oc_flags2=OC2_TYPE_1;
    s->body.tag=0x7400+slot;
}
static bool near_climbing(const gameplay_input_t *in,const actor_t *a) {
    int32_t dx=in->x-a->x,dy=in->y-a->y,dz=in->z-a->z;bg_vec_t from={a->x,a->y,a->z},to={in->x,in->y,in->z},hit;
    return in->climbing && abs32(dx)<130 && abs32(dy)<130 && abs32(dz)<130 && dx*dx+dy*dy+dz*dz<16900 &&
           !bg_line(&from,&to,&hit,BG_CHECK_WALL|BG_CHECK_ONE_FACE,BG_IGNORE_ENTITY,0);
}
static bool move_to(wall_state *s,actor_t *a,int speed) {
    int32_t dx=s->target[0]-a->x,dy=s->target[1]-a->y,dz=s->target[2]-a->z;
    unsigned distance=collide_isqrt(dx*dx+dy*dy+dz*dz);
    if(distance<=(unsigned)speed){a->x=s->target[0];a->y=s->target[1];a->z=s->target[2];return true;}
    a->x+=dx*speed/(int)distance;a->y+=dy*speed/(int)distance;a->z+=dz*speed/(int)distance;return false;
}
static void tick(wall_state *s,actor_t *a,const gameplay_input_t *in) {
    const skull_spawn *p=&wall_spawns[s->spawn];bool is_gold=gold(p);
    if(s->invuln)--s->invuln;
    s->frame=(s->frame+(s->state==CHARGE?8:1))%32;
    if(s->state==DYING) {
        s->roll+=0x1000;
        if(is_gold) {
            if(s->timer && !--s->timer){s->state=TOKEN;s->roll=0;a->y+=10;}
        } else {
            bg_vec_t probe={a->x,a->y+1,a->z};int32_t floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);
            s->vy-=256;s->yq+=s->vy*3/2;a->y=s->yq/256;
            if(floor!=BG_Y_MIN && a->y<=floor) {
                a->y=floor;s->yq=floor*256;
                if(s->bounces){s->vy=s->bounces*4*256;--s->bounces;}
                else if(s->timer)--s->timer;
                else if(world_props_enemy_drop(a->x,a->y,a->z,s->drop.item,s->drop.count)){actor_kill(a);s->handle=0;s->state=GONE;}
            }
        }
        return;
    }
    if(s->state==TOKEN) {
        int dx=in->x-a->x,dz=in->z-a->z,dy=in->y-a->y;a->yaw+=0x400;
        if(abs32(dx)<32 && abs32(dz)<32 && dx*dx+dz*dz<32*32 && dy<18 && dy>-44 && gameplay_token_message()) {
            save_collect_skull(group(p),p->params&255);actor_kill(a);s->handle=0;s->state=GONE;
        }
        return;
    }
    if(is_gold){if(!s->invuln)s->roll+=0x400;return;}
    switch(s->state) {
    case IDLE:
        if(near_climbing(in,a)){s->state=WARN;s->timer=20;}
        break;
    case WARN:
        if(!near_climbing(in,a)){s->state=IDLE;break;}
        s->target[0]=in->x;s->target[1]=in->y+30;s->target[2]=in->z;
        if(!--s->timer)s->state=CHARGE;
        break;
    case CHARGE:
        if(move_to(s,a,8) || s->body.result&COL_RES_AT_HIT) {
            s->state=RETURNING;s->timer=20;s->target[0]=p->x;s->target[1]=p->y;s->target[2]=p->z;
        }
        break;
    case RETURNING:
        if(s->timer)--s->timer;
        else if(move_to(s,a,2))s->state=IDLE;
        break;
    default:break;
    }
}
void wall_skull_step(const gameplay_input_t *in) {
    unsigned i,n=0;if(!spiders)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE){if(room_loaded>=0)wall_skull_reset();return;}
    if(room_loaded!=in->room) {
        wall_skull_reset();room_loaded=in->room;
        for(i=0;i<WALL_SKULL_COUNT && n<WALL_SKULL_MAX;++i)if(wall_spawns[i].room==room_loaded)spawn(i,n++);
    }
    for(i=0;i<WALL_SKULL_MAX;++i) {
        wall_state *s=&spiders[i];actor_t *a=actor_resolve(s->handle);if(!a)continue;
        s->phase+=2;if(s->phase>=3){s->phase-=3;tick(s,a,in);}
    }
}
void wall_skull_register(void) {
    unsigned i;if(!spiders)return;
    for(i=0;i<WALL_SKULL_MAX;++i) {
        wall_state *s=&spiders[i];actor_t *a=actor_resolve(s->handle);if(!a || s->state>=DYING)continue;
        s->body.ax=s->body.bx=a->x;s->body.ay=s->body.by=a->y-6;s->body.az=s->body.bz=a->z;
        s->body.invincible=s->invuln!=0;collide_set_ac(&s->body);collide_set_at(&s->body);collide_set_oc(&s->body);
    }
}
void wall_skull_collect(void) {
    unsigned i;if(!spiders)return;
    for(i=0;i<WALL_SKULL_MAX;++i) {
        wall_state *s=&spiders[i];actor_t *a=actor_resolve(s->handle);
        if(!a || s->state>=DYING || !(s->body.result&COL_RES_AC_HIT) || !s->body.ac_damage)continue;
        s->invuln=16;actor_hit_filter(a,false,200,16);
        gameplay.world_sfx|=1u<<(s->health>s->body.ac_damage?GP_SFX_SKULL_HIT:GP_SFX_SKULL_DEAD);
        if(s->health>s->body.ac_damage){s->health-=s->body.ac_damage;continue;}
        s->health=0;s->state=DYING;s->timer=gold(&wall_spawns[s->spawn])?26:10;s->bounces=2;s->yq=a->y*256;s->vy=0;
        a->flags&=~ACTOR_FLAG_TARGETABLE;
        random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;
        s->drop=item_drop_random(3,random_state);
    }
}
unsigned wall_skull_body(unsigned i,int32_t p[3],uint16_t *yaw,uint16_t *roll,unsigned *frame) {
    wall_state *s;actor_t *a;if(!spiders || i>=WALL_SKULL_MAX)return 0;s=&spiders[i];a=actor_resolve(s->handle);if(!a)return 0;
    p[0]=a->x;p[1]=a->y;p[2]=a->z;*yaw=a->yaw;*roll=s->roll;*frame=s->frame;
    return s->state==TOKEN?3:gold(&wall_spawns[s->spawn])?2:1;
}

unsigned wall_skull_filter(unsigned i){return spiders && i<WALL_SKULL_MAX?actor_filter_level(actor_resolve(spiders[i].handle)):0;}
