#pragma GCC optimize("Os") /* actor/state logic, not draw loops: size over speed (work RAM) */
/* Boss_Goma combat state machine, source 20 Hz timings. Geometry-derived
 * spheres come from GOHMAPOS.BIN; world rotation matches the rendered pose.
 * Boss rewards are owned by the separate heart/warp progression flow. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "gohma.h"
#include "gohma_larva.h"
#include "gohma_data.h"
#include "actor_sys.h"
#include "collide.h"
#include "kokiri_camera.h"
#include "kokiri_collision.h"
#include "save_state.h"
#include <string.h>
enum {WAIT,EYE_ROLL,INTRO_RUN,INTRO_FALL,INTRO_LAND,INTRO_STAND,
      FLOOR,IDLE,POSTURE,PREPARE,ATTACK,REST,RECOVER,HURT,STUN,
      CLIMB,CEILING,CEILING_IDLE,EGG_PREPARE,EGGS,FALL,STRUCK,LAND,CRASH,DEATH,GONE};
typedef struct {
    actor_handle_t handle;
    collider_t spheres[13];
    int32_t speed,vy,yq;
    uint16_t timer,patience,stun,age,anim,clock,invuln,eye_closed,retreat;
    int16_t pitch,room;
    uint8_t state,phase,health,children,ground,wall,noticed;
    int32_t heart[3],warp[3];
    uint16_t reward_age,warp_ticks;
    uint8_t rewards;
} gohma_state;
static gohma_state *boss;
static const uint8_t *positions;
static uint32_t rng=0x6095u;
static const actor_profile_t profile={0x28,ACTORCAT_BOSS,ACTOR_FLAG_TARGETABLE|ACTOR_FLAG_HOSTILE,0,0,0,0};
static unsigned random16(void){rng=rng*1664525u+1013904223u;return rng>>16;}
static int approach(int value,int target,int divisor,int limit){int d=(target-value)/divisor;if(d>limit)d=limit;if(d<-limit)d=-limit;return value+d;}
static uint16_t turn(uint16_t yaw,uint16_t target,int divisor,int limit){return yaw+approach(0,(int16_t)(target-yaw),divisor,limit);}
static unsigned clip(unsigned s){static const uint8_t clips[]={1,15,2,14,14,0,18,17,12,4,4,5,6,10,13,9,2,1,3,16,8,7,8,7,11,11};return clips[s];}
static unsigned frame(void){return gohma_clips[clip(boss->state)][0]+boss->anim;}
static void state(unsigned s,unsigned timer){boss->state=s;boss->timer=timer;boss->anim=boss->age=0;}
static void floor_main(void){state(FLOOR,70+random16()%110);}
bool gohma_init(void *memory,unsigned bytes){if(!memory||bytes<sizeof(*boss))return false;boss=memory;memset(boss,0,sizeof(*boss));boss->room=-1;return true;}
bool gohma_bind(const uint8_t *p,unsigned bytes){positions=bytes==GOHMA_POSE_BYTES?p:0;return positions!=0;}
void gohma_reset(void){if(!boss)return;actor_kill(actor_resolve(boss->handle));memset(boss,0,sizeof(*boss));boss->room=-1;}
bool gohma_cinematic(void){return boss&&actor_resolve(boss->handle)&&((boss->state>=EYE_ROLL&&boss->state<=INTRO_STAND)||boss->state==DEATH);}
unsigned gohma_shot_key(void){return gohma_cinematic()?0x4700u+boss->state:0;}
bool gohma_defeated(void){return save_get_clear(SAVE_SCENE_DEKU_TREE_BOSS,1);}
bool gohma_warp_active(void){return boss && boss->warp_ticks && save_state.scene_id==SAVE_SCENE_DEKU_TREE_BOSS;}
bool gohma_warp_ready(void){return gohma_warp_active() && boss->warp_ticks>101;}
bool gohma_reward_body(unsigned kind,int32_t p[3],uint16_t *yaw){
    int32_t sn,cs;unsigned i;
    if(!boss||!boss->rewards||kind>1||save_state.scene_id!=SAVE_SCENE_DEKU_TREE_BOSS)return false;
    if(!kind&&save_get_collectible(SAVE_SCENE_DEKU_TREE_BOSS,0x1f))return false;
    for(i=0;i<3;++i)p[i]=kind?boss->warp[i]:boss->heart[i];
    *yaw=boss->reward_age*0x400;
    if(!kind){kokiri_camera_sincos(boss->reward_age*0x60c,&sn,&cs);p[1]+=20+(sn*5/65536);}
    return true;
}
/* Item_B_Heart and Door_Warp1 have no random drops. Their persistent flag and
 * Emerald grant are independent: leaving the optional heart never grants it. */
static void reward_tick(const gameplay_input_t *in){
    int32_t p[3];uint16_t yaw;int dx,dz,dy;
    ++boss->reward_age;
    if(boss->warp_ticks){if(boss->warp_ticks<=101)++boss->warp_ticks;return;}
    if(gameplay.dead||gameplay.talking||gameplay.paused||!in->grounded||gameplay.attack_phase)return;
    if(gohma_reward_body(0,p,&yaw)){
        dx=in->x-p[0];dz=in->z-p[2];dy=in->y-p[1];
        if(dx>-30&&dx<30&&dz>-30&&dz<30&&dx*dx+dz*dz<900&&dy>-40&&dy<40&&gameplay_boss_heart())return;
    }
    dx=in->x-boss->warp[0];dz=in->z-boss->warp[2];dy=in->y-boss->warp[1];
    if(boss->reward_age>=79&&dx>-60&&dx<60&&dz>-60&&dz<60&&dx*dx+dz*dz<3600&&dy>-20&&dy<20)
        boss->warp_ticks=1;
}
static void spawn(unsigned room){
    unsigned i;actor_t *a;
    boss->room=room;
    if(room!=1)return;
    if(gohma_defeated()){
        boss->rewards=1;boss->heart[0]=141;boss->heart[1]=boss->warp[1]=-640;boss->heart[2]=-84;
        return;
    }
    a=actor_spawn(&profile,SAVE_SCENE_DEKU_TREE_BOSS,room,-160,-280,-371,0,0xffff);
    if(!a)return;
    boss->handle=actor_handle(a);boss->health=10;boss->yq=a->y*256;boss->pitch=-32768;
    boss->patience=200;state(WAIT,0);a->navi_text=0x600;a->range=ATTN_RANGE_5;a->attention=ATTN_ENEMY;
    a->focus[1]=0;
    for(i=0;i<13;++i){collider_t *c=&boss->spheres[i];c->actor=a;c->shape=COLSHAPE_CAPSULE;c->radius=gohma_radii[i];
        c->at_type=AT_TYPE_ENEMY;c->at_dmg=0xFFCFFFFFu;c->at_damage=8;c->ac_type=AC_TYPE_PLAYER;c->ac_bumper=0xFFCFFFFFu;
        c->ac_flags=COL_AC_ELEMENT|(i?COL_AC_HARD:0);c->tag=0x7900+i;c->mass=MASS_IMMOVABLE;}
    if(save_get_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE)){boss->noticed=1;state(INTRO_FALL,0);}
}
static int be16(const uint8_t *p){return (int16_t)((p[0]<<8)|p[1]);}
static void pose(actor_t *a){
    int32_t sy,cy,sx,cx;unsigned i;
    const uint8_t *p=positions+frame()*13*6;
    kokiri_camera_sincos(a->yaw,&sy,&cy);kokiri_camera_sincos((uint16_t)boss->pitch,&sx,&cx);
    for(i=0;i<13;++i,p+=6){collider_t *c=&boss->spheres[i];int x=be16(p),y=be16(p+2),z=be16(p+4);
        int ry=(int)(((int64_t)y*cx-(int64_t)z*sx)>>16),rz=(int)(((int64_t)y*sx+(int64_t)z*cx)>>16);
        c->ax=c->bx=a->x+(int)(((int64_t)x*cy+(int64_t)rz*sy)>>16);
        c->ay=c->by=a->y+ry;c->az=c->bz=a->z+(int)(((int64_t)rz*cy-(int64_t)x*sy)>>16);
    }
    a->focus[0]=boss->spheres[0].ax-a->x;a->focus[1]=boss->spheres[0].ay-a->y;a->focus[2]=boss->spheres[0].az-a->z;
}
void gohma_notice(int32_t x,int32_t y,int32_t z,uint16_t yaw,int16_t pitch){
    actor_t *a;int dx,dz,dy;uint16_t wanted;int distance;
    if(!boss||boss->state!=WAIT||!(a=actor_resolve(boss->handle)))return;
    dx=a->x+a->focus[0]-x;dz=a->z+a->focus[2]-z;dy=a->y+a->focus[1]-y;
    wanted=collide_heading(dx,dz);
    if((int16_t)(wanted-yaw)<-3000||(int16_t)(wanted-yaw)>3000)return;
    distance=collide_isqrt((uint32_t)((int64_t)dx*dx+(int64_t)dz*dz));
    wanted=collide_heading(dy,distance);
    if((int16_t)(wanted+pitch)>-3000&&(int16_t)(wanted+pitch)<3000)boss->noticed=1;
}
static void tick(actor_t *a,const gameplay_input_t *in){
    unsigned s=boss->state,length=gohma_clips[clip(s)][1],i;int dx=in->x-a->x,dz=in->z-a->z;
    uint16_t toward=collide_heading(dx,dz);bool loop=s==WAIT||s==FLOOR||s==IDLE||s==REST||s==STUN||s==CLIMB||s==CEILING||s==CEILING_IDLE||s==EGG_PREPARE||s==EGGS;
    ++boss->age;++boss->clock;if(boss->timer)--boss->timer;if(boss->stun)--boss->stun;if(boss->retreat)--boss->retreat;if(boss->invuln)--boss->invuln;
    if(boss->anim+1u<length)++boss->anim;else if(loop)boss->anim=0;
    if(boss->eye_closed)--boss->eye_closed;
    if(s==FLOOR && !(boss->clock&15)&&random16()%10<3)boss->eye_closed=7;
    for(i=0;i<3;++i)if(gohma_larva_alive(i))boss->eye_closed=7;
    switch(s){
    case WAIT:if(boss->noticed)state(EYE_ROLL,gohma_clips[15][1]);break;
    case EYE_ROLL:if(!boss->timer)state(INTRO_RUN,30);break;
    case INTRO_RUN:boss->speed=approach(boss->speed,-1920,2,512);if(!boss->timer){state(INTRO_FALL,0);boss->speed=boss->vy=0;}break;
    case INTRO_FALL:case FALL:case STRUCK:
        boss->pitch=turn(boss->pitch,0,2,3000);a->yaw=turn(a->yaw,toward,2,2000);
        if(boss->ground){state(s==STRUCK?CRASH:s==INTRO_FALL?INTRO_LAND:LAND,gohma_clips[s==STRUCK?7:s==INTRO_FALL?14:8][1]);boss->vy=0;}break;
    case INTRO_LAND:
        if(boss->anim==40)save_set_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE);
        if(!boss->timer)state(INTRO_STAND,50);break;
    case INTRO_STAND:if(!boss->timer){boss->patience=200;floor_main();}break;
    case FLOOR:
        if(boss->anim!=1&&boss->anim!=15&&boss->anim!=16){
            if(boss->patience){--boss->patience;boss->speed=approach(boss->speed,2560/3,2,512);a->yaw=turn(a->yaw,toward,5,1000);
                if((int64_t)dx*dx+(int64_t)dz*dz<22500)state(POSTURE,gohma_clips[12][1]);}
            else {boss->speed=approach(boss->speed,boss->retreat?-2560:5120/3,2,512);a->yaw=turn(a->yaw,toward+(boss->retreat?0:0x8000),3,2500);}
        }
        if(boss->wall){state(CLIMB,0);boss->speed=boss->vy=0;}
        else if(!boss->timer&&boss->patience)state(IDLE,20+random16()%30);break;
    case IDLE:boss->speed=approach(boss->speed,0,2,512);if(!boss->timer)floor_main();break;
    case POSTURE:boss->speed=approach(boss->speed,0,2,512);a->yaw=turn(a->yaw,toward,3,2000);if(!boss->timer)state(PREPARE,1);break;
    case PREPARE:if(!boss->timer)state(ATTACK,gohma_clips[4][1]);break;
    case ATTACK:if(!boss->timer)state(REST,30+random16()%30);break;
    case REST:if(!boss->timer)state(RECOVER,gohma_clips[6][1]);break;
    case RECOVER:if(!boss->timer)state(IDLE,20+random16()%30);break;
    case HURT:if(!boss->timer){state(STUN,0);boss->patience=0;}break;
    case STUN:boss->speed=approach(boss->speed,0,2,256);if(!boss->stun){floor_main();if(!boss->patience&&(int64_t)dx*dx+(int64_t)dz*dz<16900)boss->retreat=20;}break;
    case CLIMB:
        boss->pitch=turn(boss->pitch,0xc000,2,2000);boss->vy=approach(boss->vy,1280,2,512);
        if(a->y>-320){state(CEILING,30+random16()%60);boss->vy=0;boss->children=0;}break;
    case CEILING:
        boss->pitch=turn(boss->pitch,0x8000,3,1000);boss->speed=approach(boss->speed,-1280,2,512);
        a->yaw=turn(a->yaw,collide_heading(-150-a->x,-350-a->z)+0x8000,3,1000);
        if(!boss->timer&&a->x>-250&&a->x<-50&&a->z>-450&&a->z<-250)state(CEILING_IDLE,20+random16()%30);break;
    case CEILING_IDLE:
        boss->speed=approach(boss->speed,0,2,512);
        if(!boss->timer){if(boss->children==7){if(!gohma_larva_alive(0)&&!gohma_larva_alive(1)&&!gohma_larva_alive(2))state(FALL,0);}
            else state(EGG_PREPARE,70);}break;
    case EGG_PREPARE:if(!boss->timer)state(EGGS,0);break;
    case EGGS:
        boss->speed=approach(boss->speed,0,2,512);
        if(boss->age==56||boss->age==88||boss->age==120){i=(boss->age-56)/32;
            collider_t *tail=&boss->spheres[1];if(gohma_larva_spawn(i,tail->ax,tail->ay,tail->az,random16()))boss->children|=1u<<i;}
        if(boss->age>=128)state(CEILING,30+random16()%60);break;
    case LAND:if(!boss->timer){boss->patience=200;state(IDLE,20+random16()%30);}break;
    case CRASH:if(!boss->timer){boss->patience=0;boss->stun=150;state(STUN,0);}break;
    case DEATH:
        boss->speed=0;boss->pitch=turn(boss->pitch,0,2,3000);
        if(!boss->timer){
            boss->heart[0]=a->x;boss->heart[1]=a->y;boss->heart[2]=a->z;
            boss->warp[0]=-150;boss->warp[1]=a->y;boss->warp[2]=-350;
            /* BossGoma_Defeated: keep the portal clear of Link and the heart. */
            for(i=0;i<10000;++i){
                int px=boss->warp[0]-in->x,pz=boss->warp[2]-in->z;
                int hx=boss->warp[0]-a->x,hz=boss->warp[2]-a->z;
                if(!(px>-100&&px<100&&pz>-100&&pz<100)&&!(hx>-150&&hx<150&&hz>-150&&hz<150))break;
                boss->warp[0]=(int)(random16()%400)-350;boss->warp[2]=(int)(random16()%400)-550;
            }
            boss->rewards=1;boss->reward_age=0;
            save_set_clear(SAVE_SCENE_DEKU_TREE_BOSS,1);actor_kill(a);boss->handle=0;state(GONE,0);return;
        }break;
    default:break;
    }
    if(boss->state!=WAIT&&boss->state!=EYE_ROLL){
        int32_t sn,cs;int oldx=a->x,oldz=a->z,move_x,move_z;bg_vec_t p;int floor;
        kokiri_camera_sincos(a->yaw,&sn,&cs);move_x=(int)((int64_t)boss->speed*sn>>24);move_z=(int)((int64_t)boss->speed*cs>>24);
        collide_world_push(a,move_x,move_z);boss->wall=(a->x-oldx!=move_x||a->z-oldz!=move_z);
        s=boss->state;
        if(s==CLIMB)boss->yq+=boss->vy;
        else if(s!=CEILING&&s!=CEILING_IDLE&&s!=EGG_PREPARE&&s!=EGGS&&s!=INTRO_RUN){boss->vy-=512;if(boss->vy<-5120)boss->vy=-5120;boss->yq+=boss->vy;}
        a->y=boss->yq/256;p.x=a->x;p.y=a->y+60;p.z=a->z;floor=bg_floor(&p,BG_IGNORE_ENTITY,0);boss->ground=0;
        if(floor!=BG_Y_MIN&&a->y<=floor&&boss->vy<=0){a->y=floor;boss->yq=floor*256;boss->vy=0;boss->ground=1;}
    }
}
void gohma_step(const gameplay_input_t *in){
    actor_t *a;if(!boss)return;
    if(save_state.scene_id!=SAVE_SCENE_DEKU_TREE_BOSS){if(boss->room>=0)gohma_reset();return;}
    if(boss->room!=in->room){gohma_reset();spawn(in->room);}
    if(boss->rewards){boss->phase+=2;if(boss->phase>=3){boss->phase-=3;reward_tick(in);}return;}
    if(!positions||!(a=actor_resolve(boss->handle)))return;
    boss->phase+=2;if(boss->phase>=3){boss->phase-=3;tick(a,in);}
    if(actor_resolve(boss->handle))pose(a);
}
void gohma_register(void){
    unsigned i;if(!boss||!actor_resolve(boss->handle)||boss->state<=INTRO_STAND||boss->state>=DEATH)return;
    for(i=0;i<13;++i){collider_t *c=&boss->spheres[i];c->result=0;
        if(!boss->invuln)collide_set_ac(c);collide_set_at(c);}
}
void gohma_collect(void){
    collider_t *c;uint32_t dmg;unsigned damage;actor_t *a;
    if(!boss||!(a=actor_resolve(boss->handle)))return;c=&boss->spheres[0];
    if(!(c->result&COL_RES_AC_HIT)||boss->invuln||boss->eye_closed||boss->state==EGGS||!c->ac_hit)return;
    dmg=c->ac_hit->at_dmg;c->result=0;
    if(boss->state==CEILING||boss->state==CEILING_IDLE||boss->state==EGG_PREPARE){state(STRUCK,0);boss->speed=boss->vy=0;}
    else if(boss->state==STUN&&(dmg&(DMG_SLASH_KOKIRI|DMG_SPIN_KOKIRI|DMG_JUMP_KOKIRI|DMG_SLASH_MASTER|DMG_SPIN_MASTER|DMG_JUMP_MASTER|DMG_SLASH_GIANT|DMG_SPIN_GIANT|DMG_JUMP_GIANT))){
        damage=(dmg&DMG_JUMP_GIANT)?8:(dmg&(DMG_JUMP_MASTER|DMG_SPIN_GIANT|DMG_SLASH_GIANT))?4:(dmg&(DMG_JUMP_KOKIRI|DMG_SPIN_MASTER|DMG_SLASH_MASTER))?2:1;
        boss->health=boss->health>damage?boss->health-damage:0;boss->invuln=10;
        actor_hit_filter(a,false,255,10);
        gameplay.world_sfx|=1u<<(boss->health?GP_SFX_GOHMA_HIT:GP_SFX_GOHMA_DEAD);
        state(boss->health?HURT:DEATH,boss->health?gohma_clips[10][1]:270);
        if(!boss->health)a->flags=0;
    }else if(boss->state!=STUN&&boss->patience&&(dmg&(DMG_SLINGSHOT|DMG_DEKU_NUT))){
        boss->invuln=10;boss->stun=dmg&DMG_DEKU_NUT?40:90;state(STUN,0);
    }
}
bool gohma_body(int32_t p[3],uint16_t *yaw,int16_t *pitch,unsigned *f){actor_t *a;if(!boss||!(a=actor_resolve(boss->handle)))return false;p[0]=a->x;p[1]=a->y;p[2]=a->z;*yaw=a->yaw;*pitch=boss->pitch;*f=frame();return true;}
void gohma_skip_shot(void){
    actor_t *a;if(!gohma_cinematic()||!(a=actor_resolve(boss->handle)))return;
    if(boss->state==INTRO_FALL){a->y=-640;boss->yq=-640*256;boss->pitch=0;boss->speed=boss->vy=0;boss->ground=1;}
    else {if(boss->state==INTRO_LAND)save_set_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE);boss->timer=0;}
}
bool gohma_camera(int32_t eye[3],int32_t at[3]){
    actor_t *a;int32_t sn,cs;if(!gohma_cinematic()||!(a=actor_resolve(boss->handle)))return false;
    at[0]=a->x+a->focus[0];at[1]=a->y+a->focus[1];at[2]=a->z+a->focus[2];
    if(boss->state==DEATH){kokiri_camera_sincos((uint16_t)(a->yaw+boss->age*80),&sn,&cs);eye[0]=a->x+sn*250/65536;eye[1]=a->y+100;eye[2]=a->z+cs*250/65536;}
    else {eye[0]=a->x+98;eye[1]=boss->state==EYE_ROLL?a->y-60:-610;eye[2]=a->z+85;}
    return true;
}

unsigned gohma_filter(void){return boss?actor_filter_level(actor_resolve(boss->handle)):0;}
