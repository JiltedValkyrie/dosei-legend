/* Bg_Treemouth: source meeting/choice flags, moving mouth and collision.
 * Original actor has no item drop. Original opening travels 1/100 per 20 Hz tick. */
#pragma GCC optimize ("Os")
#include "tree_mouth.h"
#include "kokiri_collision.h"
#include <jo/jo.h>
#include "kokiri_sgl.h"
#include "demo.h"
#include "gameplay.h"
#include "save_state.h"
#include "cutscene.h"
#include "actor_sys.h"
#include "collide.h"
#include "action_audio.h"
#include "tree_mouth_data.h"
static const bg_mesh_t mesh={tree_mouth_triangles,sizeof(tree_mouth_triangles)/sizeof(tree_mouth_triangles[0]),0,0,0,0,0,0,0,0,0};
static actor_handle_t handle;
static uint8_t slot=BG_NONE;
static unsigned progress,last_tick,phase;
static bool opening;
static const actor_profile_t profile={0x3e,ACTORCAT_BG,0,0,0,0,0};
void tree_mouth_position(int32_t *x,int32_t *y,int32_t *z) {
    *x=4029-(int)(160*progress/100);*y=136-(int)(399*progress/100);*z=-1255+(int)(92*progress/100);
}
void tree_mouth_reset(void) {
    if(slot<BG_DYNA_MAX)bg_dyna_remove(slot);
    actor_kill(actor_resolve(handle));handle=0;slot=BG_NONE;opening=false;
}
void tree_mouth_step(void) {
    actor_t *a;bg_vec_t p;unsigned tick=demo_clock(),delta=tick-last_tick;last_tick=tick;
    if(cutscene_is_playing() && !cutscene_is_in_scene())return;
    if(save_state.scene_id!=SAVE_SCENE_KOKIRI_FOREST || kokiri_scene_room()!=1) {
        if(handle)tree_mouth_reset();return;
    }
    a=actor_resolve(handle);
    if(!a) {
        a=actor_spawn(&profile,SAVE_SCENE_KOKIRI_FOREST,1,4029,136,-1255,0,0);
        if(!a)return;
        handle=actor_handle(a);a->focus[1]=50;a->attention=ATTN_POI;a->range=ATTN_RANGE_5;
        progress=save_get_event_chk_inf(EVENTCHKINF_DEKU_TREE_MOUTH_OPEN)?100:0;
        phase=0;opening=false;
        slot=bg_dyna_register(&mesh,BG_DYNA_POS);
        if(slot>=BG_DYNA_MAX)jo_core_error("Tree mouth collision pool exhausted");
    }
    if(cutscene_is_playing() && cutscene_id()==CUTSCENE_TREE_MEETING) {
        demo_link.x=cutscene_link_x();demo_link.y=cutscene_link_y()+DEMO_LINK_EYE_HEIGHT;
        demo_link.z=cutscene_link_z();demo_link_yaw=cutscene_link_yaw();
    }
    if(cutscene_is_playing() && cutscene_id()==CUTSCENE_TREE_OPEN) {
        if(cutscene_frame()<20)progress=0;
        else if(!opening) {opening=true;progress=0;phase=0;delta=0;action_audio_tree_open();}
    }
    if(opening && progress<100) {
        if(delta>6)delta=6;
        phase+=delta;
        while(phase>=3 && progress<100) {phase-=3;++progress;}
    }
    tree_mouth_position(&p.x,&p.y,&p.z);a->x=p.x;a->y=p.y;a->z=p.z;
    if(slot<BG_DYNA_MAX)bg_dyna_set(slot,&p,0,65536);
    if(cutscene_is_playing() || gameplay_blocks_world())return;
    if(save_get_event_chk_inf(EVENTCHKINF_DEKU_TREE_MOUTH_OPEN)) {a->flags&=~ACTOR_FLAG_TARGETABLE;return;}
    {
        int32_t dx=demo_link.x-a->x,dy=demo_link.y-DEMO_LINK_EYE_HEIGHT-a->y,dz=demo_link.z-a->z;
        int turn=(int16_t)collide_heading(dx,dz);
        bool met=save_get_event_chk_inf(EVENTCHKINF_MET_DEKU_TREE);
        if(turn<0)turn=-turn;
        if(dx>1658 || dx<-1658 || dy>1658 || dy<-1658 || dz>1658 || dz<-1658 ||
           dx*dx+dy*dy+dz*dz>=1658*1658 || turn>=(met?0x7530:0x4E20))return;
        if(met) {a->flags|=ACTOR_FLAG_TARGETABLE;if(gameplay.target!=handle)return;}
        if(cutscene_start_in_scene(met?CUTSCENE_TREE_CHOICE:CUTSCENE_TREE_MEETING)) {
            save_set_event_chk_inf(EVENTCHKINF_MET_DEKU_TREE);a->flags&=~ACTOR_FLAG_TARGETABLE;
        }
    }
}

/* BgTreemouth's close-range reposition before either answer's script. */
void tree_mouth_prepare_choice(void) {
    int32_t x,y,z,dx,dy,dz;int turn;
    tree_mouth_position(&x,&y,&z);
    dx=demo_link.x-x;dy=demo_link.y-DEMO_LINK_EYE_HEIGHT-y;dz=demo_link.z-z;
    if(dx<-350 || dx>350 || dy<-350 || dy>350 || dz<-350 || dz>350)return;
    turn=(int16_t)collide_heading(dx,dz);if(turn<0)turn=-turn;
    if(dx*dx+dy*dy+dz*dz<350*350 && turn<0x7530) {
        demo_link.x=3827;demo_link.y=-161+DEMO_LINK_EYE_HEIGHT;demo_link.z=-1142;
    }
}
