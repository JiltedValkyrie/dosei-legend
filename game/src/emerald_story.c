/* Original Demo_Effect actors, driven by the source creation story cues. */
#pragma GCC optimize("Os")
#include <jo/jo.h>
#include "emerald_story.h"
#include "actor_mesh.h"
#include "cutscene.h"
#include "kokiri_sgl.h"
#include "demo.h"
static actor_mesh_t *body,*aura,*triforce,*jewel,*ganon,*horse;
static unsigned part,uploaded,generation;
void emerald_story_free(void)
{
    actor_mesh_free(body);actor_mesh_free(aura);actor_mesh_free(triforce);actor_mesh_free(jewel);
    actor_mesh_free(ganon);actor_mesh_free(horse);
    body=aura=triforce=jewel=ganon=horse=0;uploaded=0;
}
bool emerald_story_load(unsigned p)
{
    emerald_story_free();part=p;
    if(p==2) {
        ganon=actor_mesh_load_animated("GANON.BIN");horse=actor_mesh_load_animated("HGANON.BIN");
        return ganon && horse;
    }
    if(p>=3 && p<=8){body=actor_mesh_load_static("GODBODY.BIN");aura=actor_mesh_load_static("GODAURA.BIN");if(!body || !aura)return false;}
    if(p==8){triforce=actor_mesh_load_static("TRIFORCE.BIN");return triforce!=0;}
    if(p==9){jewel=actor_mesh_load_static("EMERALD.BIN");return jewel!=0;}
    return true;
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
    int32_t focus[3];
    if(!cutscene_is_playing() || cutscene_id()<CUTSCENE_EMERALD1)return;
    if(g!=generation){generation=g;uploaded=0;}
    if(part==2 && cutscene_actor_channel_visible(1)) {
        int x=cutscene_actor_channel_x(1),y=cutscene_actor_channel_y(1),z=cutscene_actor_channel_z(1);
        unsigned yaw=cutscene_actor_channel_yaw(1);
        if(upload(ganon,1))actor_mesh_draw(ganon,f,x,y-6,z,yaw,0,0,focus);
        if(upload(horse,2))actor_mesh_draw(horse,f,x,y,z,yaw,0,0,focus);
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
