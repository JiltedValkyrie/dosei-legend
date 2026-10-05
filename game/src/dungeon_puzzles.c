#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/* Source Obj_Switch, Bg_Ydan_Hasi, Bg_Ydan_Maruta, Obj_Lift.
 * Native placements; all four source actors have no collectible drops.
 * Source timers run at 20 Hz; positions are integer/Q8 world units. */
#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include "dungeon_puzzles.h"
#include "kokiri_collision.h"
#include "kokiri_camera.h"
#include "save_state.h"
#include "collide.h"
#include "push_block.h"
#include "dungeon_puzzle_data.h"
#include <string.h>
typedef struct {
    int32_t x,y,z,velocity;
    uint16_t timer,roll;
    uint8_t slot,state,frame;
} puzzle_state;
static puzzle_state states[DUNGEON_PUZZLE_COUNT];
static int loaded_room=-1;
static unsigned phase,clock20;
static bool ready;
static collider_t spike;
static actor_handle_t block;
static unsigned flag(const dungeon_puzzle_spawn *p) {
    if(p->kind==6)return p->params&63;
    if(p->kind==7)return (p->params>>2)&63;
    return (p->params>>8)&63;
}
static unsigned model(unsigned i) {
    const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];puzzle_state *s=&states[i];
    switch(p->kind) {
    case 0:return s->frame;
    case 1:return 4+(s->frame>2?2:s->frame);
    case 2:return 7;
    case 3:return 9;
    case 4:return 8;
    case 5:return 11;
    case 6:return 10;
    default:return 12;
    }
}
static bool place(unsigned i,bool replace) {
    const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];puzzle_state *s=&states[i];
    const bg_mesh_t *mesh=&puzzle_meshes[model(i)];bg_vec_t pos={s->x,s->y/256,s->z};
    if(replace && s->slot<BG_DYNA_MAX) {bg_dyna_remove(s->slot);s->slot=BG_NONE;}
    if(!mesh->triangle_count)return true;
    /* Floor-switch mesh replacement starts a fresh transform history at origin.
     * It depresses in place, so must not carry its rider by the world position. */
    if(s->slot>=BG_DYNA_MAX)s->slot=bg_dyna_register(mesh,(p->kind==0 || p->kind==6)?0:BG_DYNA_POS);
    if(s->slot>=BG_DYNA_MAX)return false;
    bg_dyna_set(s->slot,&pos,p->yaw,65536);return true;
}
void dungeon_puzzles_reset(void) {
    unsigned i;
    actor_kill(actor_resolve(block));block=ACTOR_HANDLE_NONE;
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i) {
        if(ready && states[i].slot<BG_DYNA_MAX)bg_dyna_remove(states[i].slot);
        memset(&states[i],0,sizeof(states[i]));states[i].slot=BG_NONE;
    }
    bg_water_reset_surface(1);memset(&spike,0,sizeof(spike));
    loaded_room=-1;phase=clock20=0;ready=true;
}
bool dungeon_puzzles_sync(unsigned scene,unsigned room) {
    unsigned i;
    if(scene!=SAVE_SCENE_DEKU_TREE) {if(loaded_room>=0)dungeon_puzzles_reset();return true;}
    if(loaded_room==(int)room)return true;
    dungeon_puzzles_reset();loaded_room=room;
    if(room==3 || room==5) {
        bool solved=room==3 && save_get_switch(scene,16);
        bg_vec_t p={room==5?-1365:(solved?-365:-605),room==5?-880:(solved?-905:-820),room==5?1200:-290};
        actor_t *a;
        if(!push_block_set_mesh(&puzzle_meshes[13]))return false;
        a=push_block_spawn(scene,room,p,0,0xFFC0);
        if(!a)return false;
        block=actor_handle(a);if(solved)push_block_lock(a);
    }
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i) {
        const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];puzzle_state *s=&states[i];
        bool on=save_get_switch(scene,flag(p));
        if(p->room!=loaded_room)continue;
        s->x=p->x;s->y=p->y*256;s->z=p->z;
        if(p->kind<=1)s->frame=on?3:0;
        if(p->kind==6 && on){s->y-=280*256;s->state=3;}
        if(p->kind==7 && on){s->state=3;continue;}
        if(p->kind==3){s->y-=5*256;bg_water_set_surface(1,s->y/256);}
        if(!place(i,false)){dungeon_puzzles_reset();return false;}
    }
    return true;
}
static bool on_top(const gameplay_input_t *in,unsigned slot) {
    bg_vec_t feet={in->x,in->y+2,in->z};bg_hit_t hit;int32_t y;
    if(!in->grounded || slot>=BG_DYNA_MAX)return false;
    y=bg_floor(&feet,BG_IGNORE_ENTITY,&hit);
    return y!=BG_Y_MIN && hit.bg_id==slot && in->y-y<=3;
}
static int32_t approach(int32_t value,int32_t target,int32_t step) {
    if(value<target)return target-value<step?target:value+step;
    return value-target<step?target:value-step;
}
void dungeon_puzzles_step(const gameplay_input_t *in) {
    unsigned i;int32_t sn,cs;
    if(loaded_room<0)return;
    if(loaded_room==3) {
        actor_t *a=actor_resolve(block);
        if(a && a->x==-365 && a->y==-905 && a->z==-290) {
            save_set_switch(SAVE_SCENE_DEKU_TREE,16);push_block_lock(a);
        }
    }
    phase+=2;if(phase<3)return;phase-=3;++clock20;
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i) {
        const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];puzzle_state *s=&states[i];
        bool on;unsigned old=s->frame;
        if(p->room!=loaded_room)continue;
        on=save_get_switch(SAVE_SCENE_DEKU_TREE,flag(p));
        switch(p->kind) {
        case 0:
            if(!on && on_top(in,s->slot)) {gameplay.world_sfx|=1u<<((((p->params>>4)&7)==0 || ((p->params>>4)&7)==4)?GP_SFX_CORRECT:GP_SFX_APPEAR);save_set_switch(SAVE_SCENE_DEKU_TREE,flag(p));on=true;}
            if(on && s->frame<3)++s->frame;
            if(!on && s->frame)--s->frame;
            break;
        case 1:
            if(on && s->frame<3)++s->frame;
            if(!on && s->frame)--s->frame;
            break;
        case 2: {
            int32_t water,offset,bob;
            kokiri_camera_sincos((uint16_t)(clock20*256),&sn,&cs);offset=165*sn/65536;
            kokiri_camera_sincos((uint16_t)((50-clock20%50)*65536/50),&sn,&cs);bob=2*sn/65536;
            kokiri_camera_sincos(p->yaw,&sn,&cs);
            s->x=p->x+offset*sn/65536;s->z=p->z+offset*cs/65536;
            if(bg_water_surface(p->x,p->z,loaded_room,&water,0))s->y=(water+20+bob)*256;
            break;
        }
        case 3:
            if(!s->state && on){s->timer=600;s->state=1;}
            if(s->state==1) {
                int32_t target=(p->y-5-(s->timer?47:0))*256;
                s->y=approach(s->y,target,s->timer?128:256);
                if(s->y==target) {
                    if(s->timer)s->state=2;
                    else {s->state=0;save_unset_switch(SAVE_SCENE_DEKU_TREE,flag(p));}
                }
            } else if(s->state==2 && !--s->timer)s->state=1;
            bg_water_set_surface(1,s->y/256);
            break;
        case 4:
            if(!s->state && on){s->timer=260;s->state=1;}
            if(s->state) {
                if(s->timer)--s->timer;
                s->y=approach(s->y,(p->y+(s->timer?120:0))*256,3*256);
                if(!s->timer && s->y==p->y*256){s->state=0;save_unset_switch(SAVE_SCENE_DEKU_TREE,flag(p));}
            }
            break;
        case 5:s->roll+=0x360;break;
        case 6:
            if(!s->state && on){s->state=1;s->timer=20;}
            if(s->state==1) {
                int32_t shake=(s->timer%4)-2;shake=shake==-2?0:shake*2;
                kokiri_camera_sincos(p->yaw,&sn,&cs);
                s->x=p->x+shake*cs/65536;s->z=p->z+shake*sn/65536;
                if(!--s->timer){s->state=2;s->x=p->x;s->z=p->z;}
            } else if(s->state==2) {
                s->velocity+=256;s->y=approach(s->y,(p->y-280)*256,s->velocity);
                if(s->y==(p->y-280)*256)s->state=3;
            }
            break;
        case 7:
            if(s->state==3)continue;
            if(!s->state && on_top(in,s->slot)){s->state=1;s->timer=20;}
            if(s->state==1) {
                kokiri_camera_sincos((uint16_t)(clock20*18000),&sn,&cs);
                s->x=p->x+3*sn/65536;s->z=p->z+3*cs/65536;
                if(!--s->timer){s->state=2;s->x=p->x;s->z=p->z;}
            } else if(s->state==2) {
                bg_vec_t probe={s->x,s->y/256-18,s->z};int32_t floor;
                s->velocity-=154;if(s->velocity<-15*256)s->velocity=-15*256;
                s->y+=s->velocity*3/2;
                bg_dyna_enable(s->slot,false);floor=bg_floor(&probe,BG_IGNORE_ENTITY,0);bg_dyna_enable(s->slot,true);
                if(floor!=BG_Y_MIN && floor-s->y/256>=-18) {
                    save_set_switch(SAVE_SCENE_DEKU_TREE,flag(p));bg_dyna_remove(s->slot);s->slot=BG_NONE;s->state=3;continue;
                }
            }
            break;
        }
        if(p->kind<=1 && ((old<3 && s->frame==3) || (old>0 && s->frame==0)))
            gameplay.world_sfx|=1u<<GP_SFX_FOOT_SWITCH;
        place(i,p->kind==0 && old!=s->frame);
    }
}
/* Swept source eye diamond / ladder rectangle. Only seed callers use this.
 * World walls clip the segment first, so targets behind walls cannot activate. */
bool dungeon_puzzles_shot(const int32_t from[3],int32_t to[3]) {
    unsigned i;bool hit=false;
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i) {
        const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];puzzle_state *s=&states[i];
        int32_t sn,cs,az,bz,ax,bx,x,y,plane;int64_t t;
        if(p->room!=loaded_room || (p->kind!=1 && p->kind!=6) || (p->kind==6 && s->state))continue;
        kokiri_camera_sincos(p->yaw,&sn,&cs);
        az=(int32_t)(((int64_t)(from[0]-s->x)*sn+(int64_t)(from[2]-s->z)*cs)>>16);
        bz=(int32_t)(((int64_t)(to[0]-s->x)*sn+(int64_t)(to[2]-s->z)*cs)>>16);
        plane=p->kind==1?8:0;
        if(az==bz || (az<plane && bz<plane) || (az>plane && bz>plane))continue;
        if(p->kind==1) {
            int16_t angle=(int16_t)(collide_heading(to[0]-from[0],to[2]-from[2])-p->yaw);
            if(angle>=-0x5000 && angle<=0x5000)continue;
        }
        t=(int64_t)(plane-az)*65536/(bz-az);
        ax=(int32_t)(((int64_t)(from[0]-s->x)*cs-(int64_t)(from[2]-s->z)*sn)>>16);
        bx=(int32_t)(((int64_t)(to[0]-s->x)*cs-(int64_t)(to[2]-s->z)*sn)>>16);
        x=ax+(int32_t)((bx-ax)*t/65536);y=from[1]-s->y/256+(int32_t)((to[1]-from[1])*t/65536);
        if(p->kind==1) {if((x<0?-x:x)+(y<0?-y:y)>23)continue;}
        else if(x<-16 || x>16 || y<0 || y>135)continue;
        if(p->kind==1)gameplay.world_sfx|=1u<<((((p->params>>4)&7)==0 || ((p->params>>4)&7)==4)?GP_SFX_CORRECT:GP_SFX_APPEAR);
        if(p->kind==1 && save_get_switch(SAVE_SCENE_DEKU_TREE,flag(p)))save_unset_switch(SAVE_SCENE_DEKU_TREE,flag(p));
        else save_set_switch(SAVE_SCENE_DEKU_TREE,flag(p));
        to[0]=from[0]+(int32_t)((to[0]-from[0])*t/65536);
        to[1]=from[1]+(int32_t)((to[1]-from[1])*t/65536);
        to[2]=from[2]+(int32_t)((to[2]-from[2])*t/65536);hit=true;
    }
    return hit;
}
unsigned dungeon_puzzles_count(void){return DUNGEON_PUZZLE_COUNT+1;}
uint32_t dungeon_puzzles_models(unsigned room) {
    unsigned i;uint32_t mask=0;
    static const uint32_t masks[]={1,112,1u<<7,1u<<9,1u<<8,1u<<11,1u<<10,1u<<12};
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i)
        if(dungeon_puzzles[i].room==(int)room)mask|=masks[dungeon_puzzles[i].kind];
    if(room==3 || room==5)mask|=1u<<13;
    return mask;
}
unsigned dungeon_puzzles_body(unsigned i,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw,uint16_t *roll) {
    const dungeon_puzzle_spawn *p;puzzle_state *s;
    if(i==DUNGEON_PUZZLE_COUNT) {
        actor_t *a=actor_resolve(block);if(!a)return 0;
        *x=a->x;*y=a->y;*z=a->z;*yaw=a->yaw;*roll=0;return 14;
    }
    if(i>=DUNGEON_PUZZLE_COUNT)return 0;p=&dungeon_puzzles[i];s=&states[i];
    if(p->room!=loaded_room || (p->kind==4 && !s->state) || (p->kind==7 && s->state==3))return 0;
    *x=s->x;*y=s->y/256;*z=s->z;*yaw=p->yaw;*roll=s->roll;return model(i)+1;
}
void dungeon_puzzles_register(void) {
    unsigned i;
    for(i=0;i<DUNGEON_PUZZLE_COUNT;++i) {
        const dungeon_puzzle_spawn *p=&dungeon_puzzles[i];int32_t sn,cs;
        if(p->room!=loaded_room || p->kind!=5)continue;
        kokiri_camera_sincos(p->yaw,&sn,&cs);
        spike.shape=COLSHAPE_CAPSULE;spike.radius=10;
        spike.ax=p->x-220*cs/65536;spike.bx=p->x+220*cs/65536;
        spike.ay=spike.by=p->y;spike.az=p->z+220*sn/65536;spike.bz=p->z-220*sn/65536;
        spike.at_type=AT_TYPE_ENEMY;spike.at_dmg=DMG_UNBLOCKABLE;spike.at_damage=4;
        spike.ac_flags=COL_OUTSIDE_ACTOR;spike.tag=0x7200;collide_set_at(&spike);
    }
}
