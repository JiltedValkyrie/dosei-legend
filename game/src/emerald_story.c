/* Original Demo_Effect actors, driven by the source creation story cues. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "emerald_story.h"
#include "actor_mesh.h"
#include "npc_sprite.h"
#include "cutscene.h"
#include "kokiri_sgl.h"
#include "demo.h"
static actor_mesh_t *body,*aura,*triforce,*jewel;
static unsigned char *ganon,*horse;
static npc_sprite_inst_t ganon_inst,horse_inst;
static unsigned part,uploaded,generation;
void emerald_story_free(void)
{
    actor_mesh_free(body);actor_mesh_free(aura);actor_mesh_free(triforce);actor_mesh_free(jewel);
    if(ganon)jo_free(ganon);
    if(horse)jo_free(horse);
    body=aura=triforce=jewel=0;ganon=horse=0;uploaded=0;
}
bool emerald_story_load(unsigned p)
{
    emerald_story_free();part=p;
    if(p==2) {
        ganon=npc_sprite_load("GANON.SPR");horse=npc_sprite_load("HGANON.SPR");
        if(!ganon || !horse)goto failed;
    }
    if(p>=3 && p<=8){body=actor_mesh_load_static("GODBODY.BIN");aura=actor_mesh_load_static("GODAURA.BIN");if(!body || !aura)goto failed;}
    if(p==8){triforce=actor_mesh_load_static("TRIFORCE.BIN");if(!triforce)goto failed;}
    if(p==9){jewel=actor_mesh_load_static("EMERALD.BIN");if(!jewel)goto failed;}
    return true;
failed:
    emerald_story_free();
    return false;
}
static bool upload(actor_mesh_t *mesh,unsigned bit)
{
    if(!mesh)return false;
    if(uploaded&bit)return true;
    if(!actor_mesh_upload(mesh)) {jo_core_error("Emerald actor texture budget exceeded");return false;}
    uploaded|=bit;return true;
}
void emerald_story_draw(void)
{
    unsigned ch,f=cutscene_frame(),g=kokiri_actor_bank_generation();
    if(!cutscene_is_playing() || cutscene_id()<CUTSCENE_EMERALD1)return;
    if(g!=generation){generation=g;uploaded=0;}
    if(part==2 && cutscene_actor_channel_visible(1)) {
        int x=cutscene_actor_channel_x(1),y=cutscene_actor_channel_y(1),z=cutscene_actor_channel_z(1);
        unsigned yaw=cutscene_actor_channel_yaw(1);
        if (!(uploaded&1) && ganon && npc_sprite_upload(ganon,&ganon_inst)) uploaded|=1;
        if (!(uploaded&2) && horse && npc_sprite_upload(horse,&horse_inst)) uploaded|=2;
        if(uploaded&1)npc_sprite_draw(ganon,&ganon_inst,f,x,y-6,z,yaw);
        if(uploaded&2)npc_sprite_draw(horse,&horse_inst,f,x,y,z,yaw);
    }
    for(ch=0;ch<3 && body;++ch) {
        unsigned cue=cutscene_actor_channel_cue(ch);
        int x,y,z,scale=part==6?10*65536:part==7?24*65536:65536;
        if(!cutscene_actor_channel_visible(ch) || cue==2)continue;
        x=cutscene_actor_channel_x(ch);y=cutscene_actor_channel_y(ch);z=cutscene_actor_channel_z(ch);
        if(upload(aura,2))actor_mesh_draw_transform(aura,x,y,z,cutscene_actor_channel_yaw(ch),0,0,scale);
        if(upload(body,1))actor_mesh_draw_transform(body,x,y-14*scale/65536,z,
            cutscene_actor_channel_yaw(ch),0x4000,(f%120)*65536/120,scale);
    }
    if(triforce && cutscene_actor_channel_visible(3) && cutscene_actor_channel_cue(3)!=1 && upload(triforce,4))
        actor_mesh_draw_transform(triforce,cutscene_actor_channel_x(3),cutscene_actor_channel_y(3),
            cutscene_actor_channel_z(3),f*0x3c,0,0,13107);
    if(jewel && cutscene_actor_channel_visible(1) && cutscene_actor_channel_cue(1)!=1 && upload(jewel,8))
        actor_mesh_draw_transform(jewel,cutscene_actor_channel_x(1),cutscene_actor_channel_y(1),
            cutscene_actor_channel_z(1),f*0x400,0x4000,0,65536);
}
