/* En_St hanging Skulltulas. US 1.2 damage table 2 and random drop table 14.
 * Native 20 Hz timers, Q8 vertical motion, source front/back hit masks. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "skulltula.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_collision.h"
#include "save_state.h"
#include "player_items.h"
#include "world_props.h"
#include "item_drop.h"
#include "dungeon_enemy_data.h"
#include <string.h>
enum {CEILING,DROP,LAND,WAIT,RISE,DEAD,FADE,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t body,legs,attack;
    int32_t yq,vy,floor;
    uint16_t frame,turn,stun,invuln,spin,sway,timer,roll;
    uint8_t spawn,state,health,phase,bounces,clip;
    item_drop_t drop;
} skull_state;
static skull_state *skulls;
static int resident_room=-1;
static int32_t player[3];
static uint32_t random_state=0x26A3891u;
static const uint8_t damage[32]={16,2,1,2,16,2,2,2,1,2,4,4,4,4,0,0,0,4,3,0,0,0,1,2,4,2,4,8,0,0,0,0};
static const actor_profile_t profile={0x37,ACTORCAT_ENEMY,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static int32_t abs32(int32_t v){return v<0?-v:v;}
static bool close_to_link(const skull_state *s,const actor_t *a) {
    int32_t dx=player[0]-a->x,dz=player[2]-a->z,dy=a->y-player[1];
    return !s->spin && abs32(dx)<=160 && abs32(dz)<=160 && dx*dx+dz*dz<=25600 && dy>=0 && dy<=400 && player[1]>=s->floor;
}
static void clip(skull_state *s,unsigned index) {s->clip=index;s->frame=0;}
static void drop_start(skull_state *s) {s->state=DROP;s->vy=-10*256;clip(s,1);}
static void rise_start(skull_state *s) {s->state=RISE;clip(s,0);}
void skulltula_reset(void) {
    if(!skulls)return;
    unsigned i;for(i=0;i<SKULLTULA_MAX;++i)actor_kill(actor_resolve(skulls[i].handle));
    memset(skulls,0,sizeof(*skulls)*SKULLTULA_MAX);resident_room=-1;
}
bool skulltula_init(void *storage,unsigned bytes) {
    if(!storage || bytes<sizeof(*skulls)*SKULLTULA_MAX)return false;
    skulls=storage;memset(skulls,0,sizeof(*skulls)*SKULLTULA_MAX);resident_room=-1;return true;
}
bool skulltula_room(unsigned room) {
    unsigned i;for(i=0;i<SKULL_SPAWN_COUNT;++i)if(skull_spawns[i].room==(int)room)return true;
    return false;
}
static void spawn(unsigned index,unsigned slot) {
    skull_state *s=&skulls[slot];const skull_spawn *p=&skull_spawns[index];
    actor_t *a=actor_spawn(&profile,SAVE_SCENE_DEKU_TREE,p->room,p->x,p->y,p->z,p->yaw,p->params);
    bg_vec_t probe={p->x,p->y,p->z};unsigned size=p->params==1?140:100;
    if(!a)return;
    memset(s,0,sizeof(*s));s->handle=actor_handle(a);s->spawn=index;s->health=2;s->turn=60;s->yq=p->y*256;
    s->floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);s->state=CEILING;
    if(s->floor!=BG_Y_MIN && p->y<=s->floor+(int32_t)(32*size/100))s->state=WAIT;
    a->attention=ATTN_ENEMY;a->range=ATTN_RANGE_2;a->focus[1]=0;a->navi_text=p->params==1?0x605:0x604;
    s->body.actor=s->legs.actor=s->attack.actor=a;
    s->body.shape=s->legs.shape=COLSHAPE_CYLINDER;
    s->body.radius=s->legs.radius=32*size/100;
    s->body.height=s->legs.height=50*size/100;
    s->body.y_shift=s->legs.y_shift=-(int)(24*size/100);
    s->body.ac_type=s->legs.ac_type=AC_TYPE_PLAYER;
    s->body.damage_table=s->legs.damage_table=damage;
    s->body.tag=0x7300+slot*3;s->legs.tag=s->body.tag+1;
    s->body.ac_bumper=DMG_DEKU_NUT|DMG_EXPLOSIVE|DMG_BOOMERANG|DMG_ARROW_NORMAL|DMG_HAMMER_SWING|DMG_HOOKSHOT;
    s->attack.shape=COLSHAPE_CYLINDER;s->attack.radius=28*size/100;s->attack.height=56*size/100;s->attack.y_shift=-(int)(28*size/100);
    s->attack.at_type=AT_TYPE_ENEMY;s->attack.at_dmg=DMG_DEFAULT;s->attack.at_damage=8;s->attack.tag=s->body.tag+2;
    s->attack.oc_flags1=OC1_ON|OC1_TYPE_ALL;s->attack.oc_flags2=OC2_TYPE_1;s->attack.mass=MASS_IMMOVABLE;
}
static void tick(skull_state *s,actor_t *a) {
    const skull_spawn *p=&skull_spawns[s->spawn];int32_t target=s->floor+(p->params==1?44:32);
    bool close=close_to_link(s,a);unsigned speed=s->state==RISE?4:s->state==DROP?8:1;
    if(s->invuln)--s->invuln;
    if(s->stun){--s->stun;return;}
    if(s->sway)--s->sway;
    if(s->spin)--s->spin;
    s->frame=(s->frame+speed)%skull_clips[s->clip][1];
    switch(s->state) {
    case CEILING:if(close)drop_start(s);break;
    case DROP:
        if(!close)rise_start(s);
        else if(a->y+s->vy*3/512<=target){s->yq=target*256;s->vy=0;s->state=LAND;s->timer=skull_clips[1][1];clip(s,1);}
        break;
    case LAND:if(!--s->timer){s->state=WAIT;clip(s,0);}break;
    case WAIT:if(!close)rise_start(s);break;
    case RISE:
        s->vy=4*256*s->frame/(skull_clips[0][1]-1);
        if(close)drop_start(s);
        else if(a->y>=p->y){s->state=CEILING;s->yq=p->y*256;s->vy=0;clip(s,0);}
        break;
    case DEAD:
        s->vy-=256;s->roll+=0x800;
        if(a->y+s->vy*3/512<=s->floor && s->vy<0) {
            s->yq=s->floor*256;s->vy=6*256/(4-s->bounces);
            if(!--s->bounces){s->state=FADE;s->timer=8;s->vy=0;}
        }
        break;
    case FADE:
        if(s->timer)--s->timer;
        if(!s->timer && world_props_enemy_drop(a->x,a->y,a->z,s->drop.item,s->drop.count)) {
            actor_kill(a);s->handle=0;s->state=GONE;
        }
        return;
    default:break;
    }
    s->yq+=s->vy*3/2;a->y=s->yq/256;
    if(s->state<DEAD && !s->sway) {
        uint16_t target_yaw=p->yaw;int16_t delta;
        if(s->spin){a->yaw+=0x2000;return;}
        if(s->state==WAIT) {
            if(!s->turn)s->turn=60;--s->turn;
            target_yaw=collide_heading(player[0]-a->x,player[2]-a->z)+(s->turn<30?0x8000:0);
        } else s->turn=60;
        delta=(int16_t)(target_yaw-a->yaw);
        if(abs32(delta)>0x4000)a->yaw+=0x2000;
        else {int step=delta/4;if(!step && delta)step=delta>0?1:-1;a->yaw+=step;}
    }
}
void skulltula_step(const gameplay_input_t *in) {
    unsigned i,n=0;
    if(!skulls)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE){if(resident_room>=0)skulltula_reset();return;}
    if(resident_room!=in->room) {
        skulltula_reset();resident_room=in->room;
        for(i=0;i<SKULL_SPAWN_COUNT && n<SKULLTULA_MAX;++i)
            if(skull_spawns[i].room==resident_room)spawn(i,n++);
    }
    player[0]=in->x;player[1]=in->y;player[2]=in->z;
    for(i=0;i<SKULLTULA_MAX;++i) {
        skull_state *s=&skulls[i];actor_t *a=actor_resolve(s->handle);
        if(!a)continue;s->phase+=2;if(s->phase>=3){s->phase-=3;tick(s,a);}
    }
}
void skulltula_register(void) {
    if(!skulls)return;
    unsigned i;for(i=0;i<SKULLTULA_MAX;++i) {
        skull_state *s=&skulls[i];actor_t *a=actor_resolve(s->handle);int16_t angle;uint32_t body;
        if(!a || s->state>=DEAD)continue;
        body=DMG_DEKU_NUT|DMG_EXPLOSIVE|DMG_BOOMERANG|DMG_ARROW_NORMAL|DMG_HAMMER_SWING|DMG_HOOKSHOT;
        if(player_items_burning())body|=DMG_DEKU_STICK;
        s->body.ac_bumper=body;s->legs.ac_bumper=DMG_DEFAULT&~body;
        angle=(int16_t)(collide_heading(player[0]-a->x,player[2]-a->z)-a->yaw);
        s->legs.ac_flags=abs32(angle)<0x3FFC?COL_AC_HARD:0;
        s->body.invincible=s->legs.invincible=s->invuln!=0;
        collide_set_ac(&s->body);collide_set_ac(&s->legs);
        s->attack.result&=~(COL_RES_AT_HIT|COL_RES_AT_BOUNCED);
        if(!s->stun && !s->spin)collide_set_at(&s->attack);
        collide_set_oc(&s->attack);
    }
}
void skulltula_collect(void) {
    if(!skulls)return;
    unsigned i;for(i=0;i<SKULLTULA_MAX;++i) {
        skull_state *s=&skulls[i];actor_t *a=actor_resolve(s->handle);collider_t *c;
        if(!a || s->state>=DEAD)continue;
        if(s->attack.result&COL_RES_AT_HIT)s->spin=30;
        if(s->legs.result&COL_RES_AC_BOUNCED){s->invuln=8;s->sway=60;continue;}
        c=s->body.result&COL_RES_AC_HIT?&s->body:s->legs.result&COL_RES_AC_HIT?&s->legs:0;
        if(!c)continue;s->invuln=8;
        if(c->ac_effect==1){if(!s->stun){s->stun=120;gameplay.world_sfx|=1u<<GP_SFX_FREEZE;actor_hit_filter(a,true,200,120);}continue;}
        if(!c->ac_damage)continue;
        actor_hit_filter(a,false,200,skull_clips[0][1]);
        gameplay.world_sfx|=1u<<(c->ac_damage<s->health?GP_SFX_SKULL_HIT:GP_SFX_SKULL_DEAD);
        if(c->ac_damage<s->health){s->health-=c->ac_damage;s->spin=skull_clips[0][1];s->stun=0;continue;}
        s->health=0;s->state=DEAD;s->bounces=3;s->vy=0;s->stun=0;a->flags&=~ACTOR_FLAG_TARGETABLE;
        random_state^=random_state<<13;random_state^=random_state>>17;random_state^=random_state<<5;
        s->drop=item_drop_random(14,random_state);
    }
}
bool skulltula_body(unsigned i,int32_t p[3],uint16_t *yaw,uint16_t *roll,unsigned *frame,bool *big) {
    skull_state *s;actor_t *a;if(!skulls || i>=SKULLTULA_MAX)return false;s=&skulls[i];a=actor_resolve(s->handle);if(!a)return false;
    p[0]=a->x;p[1]=a->y;p[2]=a->z;*yaw=a->yaw;*roll=s->roll;
    *frame=skull_clips[s->clip][0]+s->frame;*big=a->params==1;return true;
}

unsigned skulltula_filter(unsigned i){return skulls && i<SKULLTULA_MAX?actor_filter_level(actor_resolve(skulls[i].handle)):0;}
