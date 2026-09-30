/* Door_Shutter: original side-dependent clear/switch rules. No actor drops.
 * One resident room swaps beyond the raised door plane. Camera/Link opening
 * choreography remains a presentation follow-up, not an unlocked-door bypass. */
#include <jo/jo.h>
#include "kokiri_scene.h"
#include "dungeon_doors.h"
#include "save_state.h"
#include "kokiri_camera.h"
#include <string.h>
static uint8_t lift[KOKIRI_PORTAL_COUNT],hold[KOKIRI_PORTAL_COUNT];
static int32_t previous_x,previous_z;
static int current_room=-1;
void dungeon_doors_reset(void) {
    memset(lift,0,sizeof(lift));memset(hold,0,sizeof(hold));current_room=-1;
}
unsigned dungeon_door_height(unsigned i) {return i<KOKIRI_PORTAL_COUNT ? lift[i] : 0;}
bool dungeon_door_open(unsigned i) {return dungeon_door_height(i)>=100;}
static bool relevant(const kokiri_portal *p) {
    return save_state.scene_id==SAVE_SCENE_DEKU_TREE && p->kind>=8 &&
        (p->front==current_room || p->back==current_room);
}
static void local(const kokiri_portal *p,int32_t x,int32_t z,int *side,int *depth) {
    int32_t sn,cs;kokiri_camera_sincos(p->yaw,&sn,&cs);
    x-=p->x;z-=p->z;
    *side=(int)(((int64_t)x*cs-(int64_t)z*sn)>>16);
    *depth=(int)(((int64_t)x*sn+(int64_t)z*cs)>>16);
}
static bool allowed(const kokiri_portal *p) {
    unsigned type=p->kind-8;
    /* DoorShutter_SetupDoor: front room downgrades all ordinary gates;
     * type 7 instead waits for that side's room clear. */
    if(current_room==p->front) type=type==7 ? 1 : 0;
    if(type==1) return save_get_clear(save_state.scene_id,current_room);
    if(type==2 || type==7) return save_get_switch(save_state.scene_id,p->flag);
    return type==0;
}
bool dungeon_doors_step(const gameplay_input_t *in) {
    unsigned i;bool consumed=false;
    current_room=in->room;previous_x=in->x;previous_z=in->z;
    for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];int side,depth,dy;
        if(!relevant(p)) {lift[i]=hold[i]=0;continue;}
        local(p,in->x,in->z,&side,&depth);dy=in->y-p->y;
        if(side>-50 && side<50 && dy>=-10 && dy<100 && depth>-65 && depth<65) {
            int16_t facing=(int16_t)(in->yaw-p->yaw-(depth>0 ? 0x8000 : 0));
            if(in->interact && in->grounded && facing>-0x3000 && facing<0x3000) {
                consumed=true;
                if(allowed(p)) hold[i]=90;
                else gameplay.events|=GP_EVENT_DENIED;
            }
            /* Do not lower onto Link, including after changing rooms. */
            if(lift[i]>=100) hold[i]=30;
        }
        if(hold[i]) {--hold[i];if(lift[i]<120) lift[i]+=5;}
        else if(lift[i]) lift[i]-=5;
    }
    return consumed;
}
void dungeon_doors_constrain(int32_t *x,int32_t *z,int32_t y) {
    unsigned i;
    for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];int side,depth,old_side,old_depth;
        if(!relevant(p) || dungeon_door_open(i) || y<p->y-20 || y>p->y+125) continue;
        local(p,*x,*z,&side,&depth);local(p,previous_x,previous_z,&old_side,&old_depth);
        if(side>-65 && side<65 &&
           ((depth>-22 && depth<22) || ((depth<0)!=(old_depth<0)))) {
            int32_t sn,cs;int wanted=old_depth<0 ? -22 : 22;
            kokiri_camera_sincos(p->yaw,&sn,&cs);
            *x += (int32_t)((int64_t)(wanted-depth)*sn/65536);
            *z += (int32_t)((int64_t)(wanted-depth)*cs/65536);
        }
    }
}
