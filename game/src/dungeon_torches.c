#pragma GCC optimize("Os") /* small logic: size over speed (work RAM) */
/* ObjSyokudai_Update: native torch params/timers and stick-tip interaction.
 * No collectible drops in the source actor. 20 Hz timers on 30 Hz steps. */
#include "dungeon_torches.h"
#include "dungeon_torch_data.h"
#include "kokiri_collision.h"
#include "player_items.h"
#include "save_state.h"
#include <string.h>
static int16_t timers[DUNGEON_TORCH_COUNT];
static int room_loaded=-1;
static unsigned phase;
unsigned dungeon_torches_count(void) { return DUNGEON_TORCH_COUNT; }
unsigned dungeon_torches_room_models(unsigned room) {
    unsigned i,mask=0;for(i=0;i<DUNGEON_TORCH_COUNT;++i)
        if(dungeon_torches[i].room==(int)room)mask|=1u<<(dungeon_torches[i].params>>12);
    return mask;
}
void dungeon_torches_reset(void) { memset(timers,0,sizeof(timers));room_loaded=-1;phase=0; }
void dungeon_torches_step(unsigned scene,unsigned room,const int32_t *tip) {
    unsigned i;bool tick;
    if(scene!=SAVE_SCENE_DEKU_TREE) {dungeon_torches_reset();return;}
    if(room_loaded!=(int)room) {
        dungeon_torches_reset();room_loaded=room;
        for(i=0;i<DUNGEON_TORCH_COUNT;++i) {
            const dungeon_torch_spawn *t=&dungeon_torches[i];
            if(t->room==(int)room && ((t->params&0x400) ||
               ((t->params>>12)!=2 && save_get_switch(scene,t->params&63)))) timers[i]=-1;
        }
    }
    phase+=2;tick=phase>=3;if(tick)phase-=3;
    for(i=0;i<DUNGEON_TORCH_COUNT;++i) {
        const dungeon_torch_spawn *t=&dungeon_torches[i];
        unsigned type=t->params>>12,count=(t->params>>6)&15,flag=t->params&63;
        int32_t water;bool submerged;
        if(t->room!=(int)room)continue;
        submerged=bg_water_surface(t->x,t->z,room,&water,0) && water-t->y>52;
        if(submerged) {
            timers[i]=0;
            if(type==1)save_unset_switch(scene,flag);
            continue;
        }
        if(t->params&0x400)timers[i]=-1;
        if(count) {
            if(save_get_switch(scene,flag))timers[i]=-1;
            else if(timers[i]<0)timers[i]=20;
        }
        if(tip && player_items_stick()) {
            int32_t dx=tip[0]-t->x,dy=tip[1]-t->y-67,dz=tip[2]-t->z;
            if(dx>-20 && dx<20 && dy>-20 && dy<20 && dz>-20 && dz<20 &&
               dx*dx+dy*dy+dz*dz<400) {
                if(timers[i]) {
                    player_items_ignite();
                    if(type && timers[i]>=0 && timers[i]<(int)(50*count+100))timers[i]=50*count+100;
                } else if(type && player_items_burning()) {
                    unsigned j,lit=1;
                    player_items_ignite();
                    if(!count) {
                        timers[i]=-1;
                        if(type!=2)save_set_switch(scene,flag);
                    } else {
                        for(j=0;j<DUNGEON_TORCH_COUNT;++j)
                            if(j!=i && dungeon_torches[j].room==(int)room && timers[j] &&
                               ((dungeon_torches[j].params>>6)&15) &&
                               (dungeon_torches[j].params&63)==flag)++lit;
                        if(lit>=(count==10 ? 24 : count)) {save_set_switch(scene,flag);timers[i]=-1;}
                        else timers[i]=50*count+110;
                    }
                }
            }
        }
        if(tick && timers[i]>0)--timers[i];
    }
}
unsigned dungeon_torches_body(unsigned i,int32_t *x,int32_t *y,int32_t *z,uint16_t *yaw,bool *lit) {
    const dungeon_torch_spawn *t;
    if(i>=DUNGEON_TORCH_COUNT || room_loaded<0)return 0;
    t=&dungeon_torches[i];if(t->room!=room_loaded)return 0;
    *x=t->x;*y=t->y;*z=t->z;*yaw=t->yaw;*lit=timers[i]!=0;
    return (t->params>>12)+1;
}
