#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include <jo/jo.h>
#include "world_props_draw.h"
#include "world_props.h"
#include "world_signs.h"
#include "item_drop.h"
#include "actor_mesh.h"
#include "kokiri_actors.h"
#include "kokiri_sgl.h"
#include "save_state.h"
#include "demo.h"
#include "scene_flow.h"
#include "world_prop_assets.h"
#include "kokiri_scene.h"
#include "dungeon_doors.h"
#include "dungeon_webs.h"
static actor_mesh_t *door,*web;
static actor_mesh_t *rock, *pot, *chest, *bush, *gossip, *sign[11];
static uint16_t chest_age[KOKIRI_CHEST_COUNT];
static unsigned int last_tick;
/* Diagnostic draw mask — readable/writable from the Kronos debugger.
 * Bit 0: skip pots (0x111) and rocks (0x14E, 0x14F param&3==1).
 * Bit 1: skip signs.  Bit 2: skip gossip stones (0x1B9).
 * Bit 3: skip bushes (0x14F param&3==2).  Bit 4: skip chests.
 * Skipping a draw also frees SGL work space, so a triangle that disappears
 * identifies a suspect path, not a proven cause.
 * Default 0 = draw everything.  Spawn, load, and texture uploads are unaffected. */
volatile int dosei_draw_mask = 0;
void world_props_draw_free(void)
{
    unsigned int i;for(i=0;i<11;++i) { actor_mesh_free(sign[i]);sign[i]=0; }
    actor_mesh_free(rock);actor_mesh_free(pot);actor_mesh_free(chest);
    actor_mesh_free(bush);actor_mesh_free(gossip);
    actor_mesh_free(door);door=0;actor_mesh_free(web);web=0;
    dungeon_doors_reset();dungeon_webs_reset();
    rock=pot=chest=bush=gossip=0;
}
bool world_props_draw_load(unsigned int scene)
{
    unsigned int i; bool rocks=false,pots=false,chests=false;
    world_props_draw_free();
    for(i=0;i<KOKIRI_WORLD_PROP_COUNT;++i) {
        const kokiri_world_prop_t *p=&kokiri_world_props[i];
        if(p->scene!=scene) continue;
        rocks |= p->id==0x14E || (p->id==0x14F && (p->param&3)==1); pots |= p->id==0x111;
    }
    for(i=0;i<KOKIRI_CHEST_COUNT;++i) {
        chests |= kokiri_chests[i].scene==scene;
        chest_age[i]=gameplay_chest_opened(i) ? WORLD_CHEST_FRAMES*3 : 0;
    }
    if(rocks && !(rock=actor_mesh_load_static("ROCK.BIN"))) return false;
    if(pots && !(pot=actor_mesh_load_static("POT.BIN"))) return false;
    if(chests && !(chest=actor_mesh_load_animated("CHEST.BIN"))) return false;
    if(scene==SAVE_SCENE_KOKIRI_FOREST) {
        if(!(bush=actor_mesh_load_static("BUSH.BIN")) || !(gossip=actor_mesh_load_static("GOSSIP.BIN"))) return false;
        for(i=0;i<11;++i) { char name[16];sprintf(name,"SIGN%u.BIN",i);
            if(!(sign[i]=actor_mesh_load_static(name))) return false;
        }
    }
    if(scene==SAVE_SCENE_DEKU_TREE && (!(door=actor_mesh_load_static("DTDOOR.BIN")) ||
       !(web=actor_mesh_load_static("DTWEB.BIN")))) return false;
    last_tick=demo_world_clock();return true;
}
bool world_props_draw_upload(void)
{
    unsigned int i;for(i=0;i<11;++i) if(sign[i] && !actor_mesh_upload(sign[i])) return false;
    return (!web || actor_mesh_upload(web)) && (!door || actor_mesh_upload(door)) && (!rock || actor_mesh_upload(rock)) && (!pot || actor_mesh_upload(pot)) &&
           (!chest || actor_mesh_upload(chest)) && (!bush || actor_mesh_upload(bush)) &&
           (!gossip || actor_mesh_upload(gossip));
}
static void draw_sign(unsigned int mask,int x,int y,int z,uint16_t yaw,bool fallen)
{
    unsigned int i;
    jo_3d_push_matrix();jo_3d_translate_matrix(x,-y,z);slRotY(yaw);
    if(fallen) slRotX(0x4000);
    for(i=0;i<11;++i) if(mask&(1u<<i)) actor_mesh_draw_static(sign[i],0,0,-1,0);
    jo_3d_pop_matrix();
}
void world_props_draw(unsigned int tick)
{
    actor_t *a=0; unsigned int i,delta=tick-last_tick;last_tick=tick;
    if(delta>12) delta=12;
    while((a=actor_sys_find(WORLD_PROP_ID,a))) {
        if(a->scene!=save_state.scene_id || (a->room!=ACTOR_ROOM_NONE && a->room!=(int)(scene_flow_is_interior()?0:kokiri_scene_room()))) continue;
        {
            const kokiri_world_prop_t *p=&kokiri_world_props[a->data[0]];
            bool is_bush=p->id==0x14F && (p->param&3)==2;
            /* Bit 0: pots and rocks.  Bit 2: gossip stones.  Bit 3: bushes. */
            if((dosei_draw_mask & 1) && (p->id==0x111 || p->id==0x14E ||
                                         (p->id==0x14F && !is_bush))) continue;
            if((dosei_draw_mask & 4) && p->id==0x1B9) continue;
            if((dosei_draw_mask & 8) && is_bush) continue;
            actor_mesh_t *mesh=p->id==0x111 ? pot : p->id==0x1B9 ? gossip :
                is_bush ? bush : rock;
            jo_3d_push_matrix();jo_3d_translate_matrix(a->x,-a->y,a->z);
            if(p->id==0x1B9 && a->data[6]) {
                int wave=(a->data[6]&7)-4;slScale(65536+wave*2048,65536-wave*4096,65536+wave*2048);
            }
            actor_mesh_draw_static(mesh,0,p->id==0x14F && (p->param&3)==1 ? 6 : 0,0,a->yaw);
            jo_3d_pop_matrix();
        }
    }
    while((a=actor_sys_find(DROP_ACTOR_ID,a))) {
        int y=a->y;
        if(a->scene!=save_state.scene_id || (a->room!=ACTOR_ROOM_NONE && a->room!=(int)(scene_flow_is_interior()?0:kokiri_scene_room()))) continue;
        if(a->data[0]>0 && a->data[0]<60 && (tick&4)) continue;
        if(a->data[1]<GP_DROP_DELAY) y += a->data[1]*(GP_DROP_DELAY-a->data[1])/2;
        kokiri_drop_draw(a->params,a->x,y+14,a->z,tick);
    }
    if(sign[0] && !(dosei_draw_mask & 2)) {
        for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
            const kokiri_prop_t *s=&kokiri_signs[i];
            int dx=s->x-demo_link.x,dz=s->z-demo_link.z;
            if(s->room==kokiri_scene_room() && dx>-1000 && dx<1000 && dz>-1000 && dz<1000)
                draw_sign(world_signs_parts(i),s->x,s->y,s->z,kokiri_sign_yaws[i],false);
        }
        a=0;while((a=actor_sys_find(SIGN_PIECE_ID,a)))
            if(a->scene==save_state.scene_id && a->room==kokiri_scene_room())
                draw_sign(a->params,a->x,a->y,a->z,a->yaw,a->data[3]!=0);
    }
    for(i=0;web && i<dungeon_webs_count();++i) {
        int32_t x,y,z;uint16_t yaw;
        if(dungeon_webs_body(i,&x,&y,&z,&yaw)) actor_mesh_draw_static(web,x,y,z,yaw);
    }
    for(i=0;door && i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];
        if(p->kind<8 || (p->front!=kokiri_scene_room() && p->back!=kokiri_scene_room())) continue;
        actor_mesh_draw_static(door,p->x,p->y+dungeon_door_height(i),p->z,p->yaw);
    }
    for(i=0;chest && i<KOKIRI_CHEST_COUNT;++i) {
        const kokiri_chest_t *c=&kokiri_chests[i];
        unsigned int frame;int32_t focus[3];
        if(c->scene!=save_state.scene_id || c->room!=(scene_flow_is_interior() ? 0 : kokiri_scene_room())) continue;
        if(gameplay_chest_opened(i) && chest_age[i]<WORLD_CHEST_FRAMES*3)
            chest_age[i]=(uint16_t)(chest_age[i]+delta);
        frame=chest_age[i]/3;
        if(frame>=WORLD_CHEST_FRAMES) frame=WORLD_CHEST_FRAMES-1;
        if(dosei_draw_mask & 16) continue; /* age still advances above */
        jo_3d_push_matrix();jo_3d_translate_matrix(c->x,-c->y,c->z);
        if((c->param>>12)==5) slScale(32768,32768,32768);
        actor_mesh_draw(chest,frame,0,0,0,c->yaw,0,0,focus);
        jo_3d_pop_matrix();
    }
}
