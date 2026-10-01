/* Source Demo_Sa bridge and En_Owl outside Kokiri. Owl has no drops. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "story_route.h"
#include "actor_mesh.h"
#include "actor_sys.h"
#include "cutscene.h"
#include "demo.h"
#include "gameplay.h"
#include "game_mode.h"
#include "save_state.h"
#include "scene_flow.h"
#include "kokiri_sgl.h"
#include "kokiri_camera.h"
#include "music_songs.h"
#include "npc_pose.h"
#include "collide.h"
#include "action_audio.h"
static actor_mesh_t *saria[4], *owl[2];
static unsigned generation, uploaded, owl_phase, owl_frame, clock_phase;
static int32_t owl_x,owl_y,owl_z,owl_speed,owl_vy;
static uint16_t owl_yaw,owl_goal;
static actor_handle_t owl_handle;
static unsigned talk_started,talk_camera_step;
static int32_t talk_eye[3],talk_at[3];
static const actor_profile_t owl_profile={0x14d,ACTORCAT_NPC,ACTOR_FLAG_TARGETABLE,0,0,0,0};
void story_route_free(void)
{
    unsigned i;
    for(i=0;i<4;++i){actor_mesh_free(saria[i]);saria[i]=0;}
    for(i=0;i<2;++i){actor_mesh_free(owl[i]);owl[i]=0;}
    actor_kill(actor_resolve(owl_handle));owl_handle=0;
    uploaded=owl_phase=owl_frame=clock_phase=0;
}
bool story_route_load(unsigned scene)
{
    unsigned i;
    if(scene==SAVE_SCENE_LOST_WOODS && !save_get_event_chk_inf(EVENTCHKINF_FAIRY_OCARINA_RECEIVED)) {
        static const char *const files[]={"NPC19.BIN","NPC20.BIN","NPC21.BIN","NPC22.BIN"};
        for(i=0;i<4;++i)if(!(saria[i]=actor_mesh_load(files[i])))return false;
    }
    if(scene==SAVE_SCENE_HYRULE_FIELD && !save_get_switch(scene,12)) {
        owl[0]=actor_mesh_load_animated("OWLPERCH.BIN");
        owl[1]=actor_mesh_load_animated("OWLFLY.BIN");
        if(!owl[0] || !owl[1])return false;
        owl_x=4284*256;owl_y=182*256;owl_z=7877*256;owl_yaw=0;owl_speed=owl_vy=0;
        owl_phase=1;
    }
    return true;
}
void story_route_arrive(unsigned spawn)
{
    if(save_state.scene_id==SAVE_SCENE_LOST_WOODS && spawn==9 &&
       save_check_quest_item(QUEST_KOKIRI_EMERALD) &&
       !save_get_event_chk_inf(EVENTCHKINF_FAIRY_OCARINA_RECEIVED)) {
        if(!saria[0] || !cutscene_start_in_scene(CUTSCENE_SARIA_BRIDGE))
            jo_core_error("Saria bridge cutscene load failed");
    } else if(save_state.scene_id==SAVE_SCENE_HYRULE_FIELD &&
              !save_get_event_chk_inf(EVENTCHKINF_FIELD_INTRO_SEEN)) {
        if(!cutscene_start_in_scene(CUTSCENE_FIELD_INTRO))jo_core_error("Field intro load failed");
    }
}
void story_route_finish(void)
{
    if(cutscene_id()==CUTSCENE_SARIA_BRIDGE) {
        save_state.fairy_ocarina=1;
        save_set_event_chk_inf(EVENTCHKINF_FAIRY_OCARINA_RECEIVED);
    } else if(cutscene_id()==CUTSCENE_FIELD_INTRO)
        save_set_event_chk_inf(EVENTCHKINF_FIELD_INTRO_SEEN);
}
bool story_owl_talking(void){return owl_phase==2;}
void story_route_step(void)
{
    actor_t *a;
    int32_t dx,dz,s,c;
    if(save_state.scene_id!=SAVE_SCENE_HYRULE_FIELD || !owl_phase)return;
    a=actor_resolve(owl_handle);
    if(!a && owl_phase==1) {
        a=actor_spawn(&owl_profile,SAVE_SCENE_HYRULE_FIELD,ACTOR_ROOM_NONE,4284,182,7877,0,0x4c);
        if(a){owl_handle=actor_handle(a);a->attention=ATTN_POI;a->range=ATTN_RANGE_6;a->focus[1]=110;}
    }
    dx=demo_link.x-owl_x/256;dz=demo_link.z-owl_z/256;
    if(owl_phase==1 && !gameplay_blocks_world() && !cutscene_is_playing() &&
       dx>-360 && dx<360 && dz>-360 && dz<360 && dx*dx+dz*dz<360*360) {
        if(gameplay_actor_message(0x2064)) {
            save_set_event_chk_inf(EVENTCHKINF_MET_FIELD_OWL);
            owl_phase=2;music_play(NA_BGM_OWL);talk_started=demo_clock();talk_camera_step=~0u;
            talk_eye[0]=demo_camera.x;talk_eye[1]=demo_camera.y;talk_eye[2]=demo_camera.z;
            talk_at[0]=owl_x/256;talk_at[1]=owl_y/256+80;talk_at[2]=owl_z/256;

        }
    } else if(owl_phase==2 && !gameplay_is_talking()) {
        save_set_switch(SAVE_SCENE_HYRULE_FIELD,12);
        owl_phase=3;owl_frame=0;
        if(a)a->flags&=~ACTOR_FLAG_TARGETABLE;
    }
    /* Same 20 Hz update rate as En_Owl; world callbacks are 30 Hz. */
    clock_phase+=2;if(clock_phase<3)return;clock_phase-=3;
    if(owl_phase<=2)return;
    ++owl_frame;
    if((owl_phase==4 && (owl_frame==2 || owl_frame==9 || owl_frame==23 || owl_frame==40)) ||
       (owl_phase==5 && owl_frame%15==4))action_audio_owl_flap();
    if(owl_phase==3 && owl_frame>=15){owl_phase=4;owl_frame=0;owl_vy=2*256;owl_goal=owl_yaw-0x4000;}
    if(owl_phase==4) {
        if(owl_frame>10)npc_smooth_step((int16_t*)&owl_yaw,(int16_t)owl_goal,2,0x400,0x40);
        if(owl_frame>45){owl_vy=2*256;owl_speed=8*256;}
        else if(owl_frame>17){owl_vy=6*256;owl_speed=4*256;}
        if(owl_frame>=60){owl_phase=5;owl_frame=0;owl_goal-=0x2000;}
    } else if(owl_phase==5) {
        npc_smooth_step((int16_t*)&owl_yaw,(int16_t)owl_goal,2,0x80,0x40);
        if(owl_speed<16*256)owl_speed+=128;
        if(owl_y>1182*256){if(owl_vy>0)owl_vy-=102;}
        else if(owl_vy<4*256)owl_vy+=51;
        if(dx>6000 || dx<-6000 || dz>6000 || dz<-6000){actor_kill(a);owl_handle=0;owl_phase=0;return;}
    }
    kokiri_camera_sincos(owl_yaw,&s,&c);
    owl_x+=(s/256)*owl_speed/256;owl_z+=(c/256)*owl_speed/256;owl_y+=owl_vy;
    if(a){a->x=owl_x/256;a->y=owl_y/256;a->z=owl_z/256;}
}
void story_route_draw(unsigned tick)
{
    unsigned g=kokiri_actor_bank_generation(),n,frame;
    int32_t focus[3];
    if(g!=generation){generation=g;uploaded=0;}
    if(cutscene_is_playing() && cutscene_id()==CUTSCENE_SARIA_BRIDGE) {
        unsigned cue=cutscene_actor_channel_cue(1),f=cutscene_frame();
        if(cue==4 || f<65)return;
        n=cue==13?1:cue==14?(f<339?2:3):0;
        frame=n==2?(f-320):n==3?(f-339):f;
        if(!(uploaded&(1u<<n))){if(!actor_mesh_upload(saria[n]))return;uploaded|=1u<<n;}
        actor_mesh_draw(saria[n],frame,-1156,-220,1683,0xB1C7,0,0,focus);
    }
    if(save_state.scene_id==SAVE_SCENE_HYRULE_FIELD && owl_phase) {
        n=owl_phase<=2?0:1;
        frame=!n?tick/3%20:owl_phase==3?owl_frame:owl_phase==4?15+owl_frame:75+owl_frame%15;
        if(!(uploaded&(16u<<n))){if(!actor_mesh_upload(owl[n]))return;uploaded|=16u<<n;}
        actor_mesh_draw(owl[n],frame,owl_x/256,owl_y/256,owl_z/256,owl_yaw,0,0,focus);
    }
}

/* OnePoint 8700 left-hand path: first player-relative shot, then owl-relative
 * conversation shot (0x2222 / 0x4343). Integer 0.2 approach at source 20 Hz. */
void story_owl_camera(void)
{
    int32_t eye[3],at[3],s,c,dx,dz;
    unsigned elapsed=(demo_clock()-talk_started)/3,i;
    int ex,ez,ax,az;
    if(!story_owl_talking())return;
    if(elapsed<30) {
        ex=-30;ez=-20;ax=50;az=140;kokiri_camera_sincos(demo_link_yaw,&s,&c);
        eye[0]=at[0]=demo_link.x;eye[2]=at[2]=demo_link.z;
        eye[1]=demo_link.y-DEMO_LINK_EYE_HEIGHT+10;at[1]=demo_link.y-DEMO_LINK_EYE_HEIGHT+100;
    } else {
        ex=20;ez=120;ax=-10;az=10;kokiri_camera_sincos(owl_yaw,&s,&c);
        eye[0]=at[0]=owl_x/256;eye[2]=at[2]=owl_z/256;
        eye[1]=owl_y/256+20;at[1]=owl_y/256+80;
    }
    eye[0]+=(ex*c+ez*s)/65536;eye[2]+=(ez*c-ex*s)/65536;
    at[0]+=(ax*c+az*s)/65536;at[2]+=(az*c-ax*s)/65536;
    if(elapsed!=talk_camera_step) {
        talk_camera_step=elapsed;
        for(i=0;i<3;++i){talk_eye[i]+=(eye[i]-talk_eye[i])/5;talk_at[i]+=(at[i]-talk_at[i])/5;}
    }
    demo_camera.x=talk_eye[0];demo_camera.y=talk_eye[1];demo_camera.z=talk_eye[2];
    dx=talk_at[0]-talk_eye[0];dz=talk_at[2]-talk_eye[2];
    demo_yaw=collide_heading(dx,dz);
    demo_pitch=-(int16_t)collide_heading(talk_at[1]-talk_eye[1],collide_isqrt((uint32_t)(dx*dx+dz*dz)));
}
unsigned story_owl_screen_distance(void){return (demo_clock()-talk_started)/3<30?120:257;}
