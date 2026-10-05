#pragma GCC optimize("Os") /* state logic, not draw loops: size over speed (work RAM) */
/* Door_Shutter: original side-dependent clear/switch rules. No actor drops.
 * One resident room swaps beyond the raised door plane. Camera/Link opening
 * choreography remains a presentation follow-up, not an unlocked-door bypass. */
#include <jo/jo.h>
#include "kokiri_scene.h"
#include "dungeon_doors.h"
#include "save_state.h"
#include "scene_flow.h"
#include "kokiri_camera.h"
#include "oot_core_host.h"
#include <string.h>
static uint8_t lift[KOKIRI_PORTAL_COUNT],hold[KOKIRI_PORTAL_COUNT];
static int32_t previous_x,previous_z;
static int current_room=-1, current_scene=-1;
static bool prompt;
bool dungeon_doors_prompt(void) { return prompt; }
void dungeon_doors_reset(void) {
    memset(lift,0,sizeof(lift));memset(hold,0,sizeof(hold));current_room=-1;current_scene=-1;prompt=false;
}
unsigned dungeon_door_height(unsigned i) {return i<KOKIRI_PORTAL_COUNT ? lift[i] : 0;}
bool dungeon_door_open(unsigned i) {return dungeon_door_height(i)>=100;}
static bool relevant(const kokiri_portal *p) {
    return p->scene==scene_flow_scene() && p->kind>=8 &&
        (!p->layers || (oot_core_scene_layer()<32 && (p->layers&(1u<<oot_core_scene_layer())))) &&
        (p->front==current_room || p->back==current_room);
}
bool dungeon_door_active(unsigned i) {
    return i<KOKIRI_PORTAL_COUNT && relevant(&kokiri_portals[i]);
}
static void local(const kokiri_portal *p,int32_t x,int32_t z,int *side,int *depth) {
    int32_t sn,cs;kokiri_camera_sincos(p->yaw,&sn,&cs);
    x-=p->x;z-=p->z;
    /* Q8 trig is plenty for a door aperture. Source positions are s16;
     * clamp far positions before products so all work stays 32 bit. */
    if(x>65535)x=65535;if(x< -65535)x= -65535;
    if(z>65535)z=65535;if(z< -65535)z= -65535;
    sn/=256;cs/=256;
    *side=(x*cs-z*sn)/256;
    *depth=(x*sn+z*cs)/256;
}
static int gate(const kokiri_portal *p,bool commit,int depth) {
    unsigned type=p->kind-8;
    bool front=current_room==p->front;
    if(p->front==p->back && depth>0) front=false;
#ifdef DOSEI_OOT_CORE
    if(oot_core_is_playing()) return oot_core_door_action(p->kind,p->flag,front,commit);
#else
    (void)commit;
#endif
    if(p->kind>=24) {
        type=p->kind-24;
        if(type==5) return (p->flag&63)==0x29 && !save_get_event_chk_inf(0x14) ? 0 : 0x200+(p->flag&63);
        if(type==1) return save_get_switch(save_state.scene_id,p->flag&63) ? 0 : 0x203;
        if(type==6) return 0x200+(p->flag&63);
        return type<8 ? 0 : 0xFF00;
    }
    if(type==4 || type==6 || type==8 || type==9 || type==10 || type>11)return 0xFF00;
    /* DoorShutter_SetupDoor: front room downgrades all ordinary gates;
     * type 7 instead waits for that side's room clear. */
    if(front && type!=11) type=type==7 ? 1 : type==5 ? 3 : 0;
    if(type==1) return save_get_clear(save_state.scene_id,current_room) ? 0 : 0xFF00;
    if(type==2 || type==7) return save_get_switch(save_state.scene_id,p->flag) ? 0 : 0xFF00;
    if(type==11) return save_get_switch(save_state.scene_id,p->flag) ? 0 : 0x203;
    return type==0 ? 0 : 0xFF00;
}
unsigned dungeon_doors_step(const gameplay_input_t *in) {
    unsigned i,consumed=0;
    if(current_scene!=(int)scene_flow_scene()) {
        dungeon_doors_reset();current_scene=scene_flow_scene();
    }
    prompt=false;
    current_room=in->room;previous_x=in->x;previous_z=in->z;
    for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];int side,depth,dy;
        if(!relevant(p)) {lift[i]=hold[i]=0;continue;}
        local(p,in->x,in->z,&side,&depth);dy=in->y-p->y;
        if(side>-50 && side<50 && dy>=-10 && dy<100 && depth>-65 && depth<65) {
            int16_t facing=(int16_t)(in->yaw-p->yaw-(depth>0 ? 0x8000 : 0));
            bool usable=in->grounded && !in->shield && !gameplay.attack_phase &&
                facing>-0x3000 && facing<0x3000;
            int refusal=gate(p,false,depth);
            if(usable && !dungeon_door_open(i)) prompt=refusal==0 || p->kind>=24;
            if(in->interact && usable) {
                if(!refusal && !gate(p,true,depth)) {hold[i]=90;consumed=1;}
                else {consumed=2;if(refusal!=0xFF00)gameplay_actor_message((uint16_t)refusal);}
            }
            /* Do not lower onto Link, including after changing rooms. */
            if(lift[i]>=100) hold[i]=30;
        }
        if(hold[i]) {--hold[i];if(lift[i]<120){if(!lift[i])gameplay.world_sfx|=1u<<GP_SFX_DOOR_OPEN;lift[i]+=5;}}
        else if(lift[i]) {lift[i]-=5;if(!lift[i])gameplay.world_sfx|=1u<<GP_SFX_DOOR_CLOSE;}
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
            *x += (wanted-depth)*(sn/256)/256;
            *z += (wanted-depth)*(cs/256)/256;
        }
    }
}
bool dungeon_doors_exit_allowed(int32_t x,int32_t y,int32_t z) {
    unsigned i;
    for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];int side,depth;
        if(!relevant(p) || p->kind<24 || y<p->y-20 || y>p->y+120) continue;
        local(p,x,z,&side,&depth);
        if(side>-100 && side<100 && depth>-150 && depth<150 && !dungeon_door_open(i)) return false;
    }
    return true;
}
