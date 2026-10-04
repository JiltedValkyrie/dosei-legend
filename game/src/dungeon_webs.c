/* Bg_Ydan_Sp floor webs. Original collision/model/placements, source 750-unit
 * fall threshold and central radius 80. No collectible drop in this actor.
 * Edge-pinned vertex deformation and particles remain presentation follow-ups. */
#include "dungeon_webs.h"
#include "kokiri_collision.h"
#include "kokiri_camera.h"
#include "save_state.h"
#include "dungeon_web_data.h"
#include "dungeon_wall_data.h"
static const bg_mesh_t mesh={dungeon_web_triangles,sizeof(dungeon_web_triangles)/sizeof(dungeon_web_triangles[0]),0,0,0,0,0,0,0,0,0};
static uint8_t slots[DUNGEON_WEB_COUNT],timers[DUNGEON_WEB_COUNT],phases[DUNGEON_WEB_COUNT];
static int16_t offsets[DUNGEON_WEB_COUNT];
static bool burning[DUNGEON_WEB_COUNT];
static int loaded_room=-1;
static bool ready;
static uint8_t wall_slots[DUNGEON_WALL_COUNT],wall_timers[DUNGEON_WALL_COUNT],wall_phases[DUNGEON_WALL_COUNT];
unsigned dungeon_walls_count(void) {return DUNGEON_WALL_COUNT;}
unsigned dungeon_walls_room_mask(unsigned room) {
    unsigned i,mask=0;for(i=0;i<DUNGEON_WALL_COUNT;++i)
        if(dungeon_walls[i].room==(int)room)mask|=1u<<i;
    return mask;
}
unsigned dungeon_webs_count(void) {return DUNGEON_WEB_COUNT;}
void dungeon_webs_reset(void) {
    unsigned i;
    for(i=0;i<DUNGEON_WALL_COUNT;++i) {
        if(ready && wall_slots[i]<BG_DYNA_MAX)bg_dyna_remove(wall_slots[i]);
        wall_slots[i]=BG_NONE;wall_timers[i]=wall_phases[i]=0;
    }
    for(i=0;i<DUNGEON_WEB_COUNT;++i) {
        if(ready && slots[i]<BG_DYNA_MAX) bg_dyna_remove(slots[i]);
        slots[i]=BG_NONE;timers[i]=phases[i]=0;offsets[i]=0;
        burning[i]=false;
    }
    ready=true;loaded_room=-1;
}
bool dungeon_webs_step(unsigned scene,unsigned room) {
    unsigned i;
    if(scene!=SAVE_SCENE_DEKU_TREE) {if(loaded_room>=0)dungeon_webs_reset();return true;}
    if(loaded_room!=(int)room) {
        if(!ready)dungeon_webs_reset();
        loaded_room=room;
        for(i=0;i<DUNGEON_WALL_COUNT;++i) {
            const dungeon_wall_spawn *w=&dungeon_walls[i];bg_vec_t pos={w->x,w->y,w->z};
            if(w->room!=(int)room && wall_slots[i]<BG_DYNA_MAX) {
                bg_dyna_remove(wall_slots[i]);wall_slots[i]=BG_NONE;wall_timers[i]=0;
            }
            if(w->room!=(int)room || wall_slots[i]<BG_DYNA_MAX || save_get_switch(scene,w->flag))continue;
            wall_slots[i]=bg_dyna_register(&wall_meshes[i],BG_DYNA_POS);
            if(wall_slots[i]>=BG_DYNA_MAX) {dungeon_webs_reset();return false;}
            bg_dyna_set(wall_slots[i],&pos,0,65536);
        }
        for(i=0;i<DUNGEON_WEB_COUNT;++i) {
            /* Source changes a breaking web to room -1: finish the break
             * and persist its flag even while Link streams the basement. */
            if(dungeon_webs[i].room!=(int)room && !timers[i] && slots[i]<BG_DYNA_MAX) {
                bg_dyna_remove(slots[i]);slots[i]=BG_NONE;
            }
        }
        for(i=0;i<DUNGEON_WEB_COUNT;++i) {
            const dungeon_web_spawn *w=&dungeon_webs[i];bg_vec_t pos={w->x,w->y,w->z};
            if(w->room!=(int)room || slots[i]<BG_DYNA_MAX || save_get_switch(scene,w->flag)) continue;
            slots[i]=bg_dyna_register(&mesh,BG_DYNA_POS);
            if(slots[i]>=BG_DYNA_MAX) {dungeon_webs_reset();return false;}
            bg_dyna_set(slots[i],&pos,w->yaw,6554);
        }
    }
    for(i=0;i<DUNGEON_WALL_COUNT;++i) if(wall_slots[i]<BG_DYNA_MAX) {
        const dungeon_wall_spawn *w=&dungeon_walls[i];
        if(!wall_timers[i] && save_get_switch(scene,w->burn)) {
            save_set_switch(scene,w->flag);wall_timers[i]=30;
        }
        if(wall_timers[i]) {
            wall_phases[i]+=2;
            if(wall_phases[i]>=3) {wall_phases[i]-=3;--wall_timers[i];}
            if(!wall_timers[i]) {bg_dyna_remove(wall_slots[i]);wall_slots[i]=BG_NONE;}
        }
    }
    for(i=0;i<DUNGEON_WEB_COUNT;++i) if(timers[i] && slots[i]<BG_DYNA_MAX) {
        const dungeon_web_spawn *w=&dungeon_webs[i];int32_t sn,cs;
        phases[i]+=2;while(phases[i]>=3) {phases[i]-=3;if(timers[i])--timers[i];}
        if(burning[i]) {
            if(!timers[i]) {bg_dyna_remove(slots[i]);slots[i]=BG_NONE;}
            continue;
        }
        kokiri_camera_sincos((uint16_t)(timers[i]*32768u/20u),&sn,&cs);
        offsets[i]=(int16_t)(200*sn/65536);
        if(offsets[i]<-190) {
            save_set_switch(scene,w->flag);bg_dyna_remove(slots[i]);slots[i]=BG_NONE;timers[i]=0;
        } else {bg_vec_t pos={w->x,w->y+offsets[i],w->z};bg_dyna_set(slots[i],&pos,w->yaw,6554);}
    }
    return true;
}
bool dungeon_webs_burn(const int32_t tip[3]) {
    unsigned i;bool changed=false;
    if(!ready)return false;
    for(i=0;i<DUNGEON_WALL_COUNT;++i) {
        const dungeon_wall_spawn *w=&dungeon_walls[i];int32_t sn,cs,x,z;
        int32_t dx=tip[0]-w->x,dz=tip[2]-w->z;
        if(wall_slots[i]>=BG_DYNA_MAX || wall_timers[i])continue;
        kokiri_camera_sincos(w->yaw,&sn,&cs);
        x=(int32_t)(((int64_t)dx*cs-(int64_t)dz*sn)>>16);
        z=(int32_t)(((int64_t)dx*sn+(int64_t)dz*cs)>>16);
        /* BgYdanSp_WallWebIdle uses Actor_WorldToActorCoords (yaw only). */
        if(x>-100 && x<100 && z<1 && tip[1]-w->y<200) {
            wall_timers[i]=30;wall_phases[i]=0;
            save_set_switch(SAVE_SCENE_DEKU_TREE,w->flag);changed=true;
        }
    }
    for(i=0;i<DUNGEON_WEB_COUNT;++i) {
        const dungeon_web_spawn *w=&dungeon_webs[i];
        int32_t dx=tip[0]-w->x,dz=tip[2]-w->z,dy=tip[1]-w->y;
        if(slots[i]>=BG_DYNA_MAX || timers[i] || dx<-70 || dx>70 || dz<-70 || dz>70)continue;
        /* Player_IsBurningStickInRange at web Y-50, range 70 / height 50. */
        if(dx*dx+dz*dz<=70*70 && dy>=-50 && dy<=0) {
            burning[i]=true;timers[i]=30;phases[i]=0;
            save_set_switch(SAVE_SCENE_DEKU_TREE,w->flag);changed=true;
        }
    }
    return changed;
}
bool dungeon_webs_land(int32_t x,int32_t y,int32_t z,int32_t fall) {
    unsigned i;bg_vec_t probe={x,y+2,z};bg_hit_t hit;int32_t floor;
    if(!ready || fall<=750)return false;
    floor=bg_floor(&probe,BG_IGNORE_ENTITY,&hit);
    if(floor==BG_Y_MIN || floor<y-2)return false;
    for(i=0;i<DUNGEON_WEB_COUNT;++i) {
        const dungeon_web_spawn *w=&dungeon_webs[i];int32_t dx=x-w->x,dz=z-w->z;
        if(slots[i]<BG_DYNA_MAX && dx>-80 && dx<80 && dz>-80 && dz<80 &&
           dx*dx+dz*dz<80*80 && hit.bg_id==slots[i]) {
            if(!timers[i])timers[i]=40;return true;
        }
    }
    return false;
}
bool dungeon_webs_body(unsigned i,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw) {
    if(i>=DUNGEON_WEB_COUNT || !ready || slots[i]>=BG_DYNA_MAX)return false;
    *x=dungeon_webs[i].x;*y=dungeon_webs[i].y+offsets[i];*z=dungeon_webs[i].z;*yaw=dungeon_webs[i].yaw;return true;
}
bool dungeon_walls_body(unsigned i,int32_t *x,int32_t *y,int32_t *z) {
    if(i>=DUNGEON_WALL_COUNT || !ready || wall_slots[i]>=BG_DYNA_MAX)return false;
    *x=dungeon_walls[i].x;*y=dungeon_walls[i].y;*z=dungeon_walls[i].z;return true;
}
