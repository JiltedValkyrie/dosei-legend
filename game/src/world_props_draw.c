#ifdef __GNUC__
#pragma GCC optimize ("Os")
#endif
#include <jo/jo.h>
#include "world_props_draw.h"
#include "perf_sub.h"
#include "npc_sprite.h"
#include "world_props.h"
#include "world_signs.h"
#include "item_drop.h"
#include "actor_mesh.h"
#include "kokiri_actors.h"
#include "kokiri_sgl.h"
#include "save_state.h"
#include "recomp.h"
#include "scene_flow.h"
#include "world_prop_assets.h"
#include "kokiri_scene.h"
#include "dungeon_doors.h"
#include "dungeon_webs.h"
#include "dungeon_torches.h"
#include "dungeon_puzzles.h"
#include "skulltula.h"
#include "wall_skull.h"
#include "dekubaba.h"
#include "hintnuts.h"
#include "gohma_larva.h"
#include "gohma.h"
#include "tree_mouth.h"
#include "oot_core_host.h"
#include "kokiri_camera.h"
static actor_mesh_t *door,*handle_door,*web,*tree_mouth;
static actor_mesh_t *torches[3];
static actor_mesh_t *walls[5];
static actor_mesh_t *puzzles[14];
static actor_mesh_t *skull;
static actor_mesh_t *gold_skull,*skull_token;
static actor_mesh_t *baba_head;
static actor_mesh_t *hint,*hint_flower,*hint_ball;
static actor_mesh_t *goma,*goma_egg;
static actor_mesh_t *gohma;
static actor_mesh_t *boss_heart,*blue_warp;
static actor_mesh_t *rock, *pot, *chest, *bush, *gossip;
static actor_mesh_t *sign_intact, *sign_hot, *sign_fade;
static bool sign_hot_dirty;
/* One original intact sign: 14 points/19 faces, including source materials.
 * Reused by every sign instance; no per-frame cart table copies. */
static uint32_t sign_hot_storage[256];
/* Only a descriptor and 19 immutable mesh-mode attributes; geometry is shared. */
static uint32_t sign_fade_storage[80];
static unsigned sign_radius;
/* Diagnostic: bit 0 disables culling. Sliced-sign rendering is retired. */
volatile unsigned dosei_sign_slow = 0;
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
    sign_hot = sign_fade = 0; /* borrowed storage, not a Jo allocation */
    sign_hot_dirty = false;
    actor_mesh_free(sign_intact); sign_intact = 0;
    sign_radius = 0;
    actor_mesh_free(tree_mouth);tree_mouth=0;tree_mouth_reset();
    unsigned int i;
    actor_mesh_free(rock);actor_mesh_free(pot);actor_mesh_free(chest);
    actor_mesh_free(bush);actor_mesh_free(gossip);
    actor_mesh_free(door);door=0;actor_mesh_free(web);web=0;
    actor_mesh_free(handle_door);handle_door=0;
    /* Shutter state survives adjacent room asset reloads. */
    dungeon_webs_reset();
    dungeon_torches_reset();
    dungeon_puzzles_reset();
    skulltula_reset();actor_mesh_free(skull);skull=0;
    wall_skull_reset();actor_mesh_free(gold_skull);actor_mesh_free(skull_token);gold_skull=skull_token=0;
    dekubaba_reset();actor_mesh_free(baba_head);baba_head=0;
    hintnuts_reset();actor_mesh_free(hint);actor_mesh_free(hint_flower);actor_mesh_free(hint_ball);hint=hint_flower=hint_ball=0;
    gohma_larva_reset();actor_mesh_free(goma);actor_mesh_free(goma_egg);goma=goma_egg=0;
    gohma_reset();actor_mesh_free(gohma);gohma=0;
    actor_mesh_free(boss_heart);actor_mesh_free(blue_warp);boss_heart=blue_warp=0;
    for(i=0;i<14;++i) {actor_mesh_free(puzzles[i]);puzzles[i]=0;}
    for(i=0;i<3;++i) {actor_mesh_free(torches[i]);torches[i]=0;}
    for(i=0;i<5;++i) {actor_mesh_free(walls[i]);walls[i]=0;}
    rock=pot=chest=bush=gossip=0;
}
bool world_props_draw_load(unsigned int scene)
{
    unsigned int i; bool rocks=false,pots=false,chests=false;
    world_props_draw_free();
    save_reset_temp_switches(scene);
    if(scene==SAVE_SCENE_KOKIRI_FOREST && !(tree_mouth=actor_mesh_load_static("TREEMTH.BIN")))return false;
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
        if(!(sign_intact = actor_mesh_load_static("SIGNALL.BIN"))) return false;
        sign_radius = actor_mesh_origin_radius(sign_intact) + 1u;
    }
    if((scene==SAVE_SCENE_DEKU_TREE || scene==SAVE_SCENE_DEKU_TREE_BOSS) &&
       !(door=actor_mesh_load_static("DTDOOR.BIN"))) return false;
    for(i=0;i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];
        if(scene_entries[p->scene].save_scene==scene && p->kind>=24 && p->kind<32) {
            handle_door=actor_mesh_load_static("ENDOOR.BIN");
            if(!handle_door)return false;
            break;
        }
    }
    if(scene==SAVE_SCENE_DEKU_TREE && !(web=actor_mesh_load_static("DTWEB.BIN"))) return false;
    if(scene==SAVE_SCENE_DEKU_TREE) for(i=0;i<3;++i) {
        char file[]="DTTORCH0.BIN";file[7]='0'+i;
        if(!(torches[i]=actor_mesh_load_static(file)))return false;
    }
    if(scene==SAVE_SCENE_DEKU_TREE) {
        if(!(skull=actor_mesh_load_animated("SKULL.BIN")))return false;
        if(!(gold_skull=actor_mesh_load_animated("GOLDSK.BIN")) || !(skull_token=actor_mesh_load_static("SKTOKEN.BIN")))return false;
        if(!(baba_head=actor_mesh_load_animated("DHEAD.BIN")))return false;
        if(!(hint=actor_mesh_load_animated("HINTNUT.BIN")) || !(hint_flower=actor_mesh_load_static("HINTFLOW.BIN")) || !(hint_ball=actor_mesh_load_static("HINTBALL.BIN")))return false;
        for(i=0;i<14;++i) {
            if(i>0 && i<4)continue; /* Floor switch shares its up-pose artwork. */
            char file[16];sprintf(file,"DTPZ%02u.BIN",i);
            if(!(puzzles[i]=actor_mesh_load_static(file)))return false;
        }
        if(dungeon_walls_count()>5)return false;
        for(i=0;i<dungeon_walls_count();++i) {
            char file[]="DTWALL0.BIN";file[6]='0'+i;
            if(!(walls[i]=actor_mesh_load_static(file)))return false;
        }
    }
    if(scene==SAVE_SCENE_DEKU_TREE || scene==SAVE_SCENE_DEKU_TREE_BOSS)
        if(!(goma=actor_mesh_load_animated("GOMALAR.BIN")) || !(goma_egg=actor_mesh_load_static("GOMAEGG.BIN")))return false;
    if(scene==SAVE_SCENE_DEKU_TREE_BOSS && !(gohma=actor_mesh_load_animated("GOHMA.BIN")))return false;
    if(scene==SAVE_SCENE_DEKU_TREE_BOSS &&
       (!(boss_heart=actor_mesh_load_static("BOSSHRT.BIN")) ||
        !(blue_warp=actor_mesh_load_static("BLUEWARP.BIN"))))return false;
    last_tick=recomp_world_clock();return true;
}
bool world_props_draw_upload(void)
{
    if(tree_mouth && kokiri_scene_room()==1 && !actor_mesh_upload(tree_mouth))return false;
    unsigned wall_models=wall_skull_models(kokiri_scene_room());
    if(gohma && kokiri_scene_room()==1 && !actor_mesh_upload(gohma))return false;
    if(boss_heart && kokiri_scene_room()==1 &&
       (!actor_mesh_upload(boss_heart)||!actor_mesh_upload(blue_warp)))return false;
    if(goma && gohma_larva_room(save_state.scene_id,kokiri_scene_room()) && (!actor_mesh_upload(goma) || !actor_mesh_upload(goma_egg)))return false;
    if(hint && hintnuts_room(kokiri_scene_room()) && (!actor_mesh_upload(hint) || !actor_mesh_upload(hint_flower) || !actor_mesh_upload(hint_ball)))return false;
    if(baba_head && dekubaba_room(kokiri_scene_room()) && !actor_mesh_upload(baba_head))return false;
    if(skull && (skulltula_room(kokiri_scene_room()) || (wall_models&1)) && !actor_mesh_upload(skull))return false;
    if(gold_skull && (wall_models&2) && !actor_mesh_upload(gold_skull))return false;
    if(skull_token && (wall_models&4) && !actor_mesh_upload(skull_token))return false;
    unsigned int i;
    sign_hot = sign_fade = 0;
    sign_hot_dirty = false;
    if (sign_intact) {
        if (!actor_mesh_upload(sign_intact)) return false;
#ifndef DOSEI_NO_SLAVE_JOBS
        sign_hot = actor_mesh_cache_static(sign_intact, sign_hot_storage, sizeof(sign_hot_storage));
        sign_hot_dirty = sign_hot != 0;
#endif
        sign_fade = actor_mesh_cache_fade(sign_hot ? sign_hot : sign_intact,
                                        sign_fade_storage, sizeof(sign_fade_storage));
        if (!sign_fade) return false;
        sign_hot_dirty = true;
    }
    for(i=0;i<3;++i)if(torches[i] && (dungeon_torches_room_models(kokiri_scene_room())&(1u<<i)) && !actor_mesh_upload(torches[i]))return false;
    for(i=0;i<5;++i)if(walls[i] && (dungeon_walls_room_mask(kokiri_scene_room())&(1u<<i)) && !actor_mesh_upload(walls[i]))return false;
    for(i=0;i<14;++i)if(puzzles[i] && (dungeon_puzzles_models(kokiri_scene_room())&(1u<<i)) && !actor_mesh_upload(puzzles[i]))return false;
    return (!web || actor_mesh_upload(web)) && (!door || actor_mesh_upload(door)) && (!handle_door || actor_mesh_upload(handle_door)) && (!rock || actor_mesh_upload(rock)) && (!pot || actor_mesh_upload(pot)) &&
           (!chest || actor_mesh_upload(chest)) && (!bush || actor_mesh_upload(bush)) &&
           (!gossip || actor_mesh_upload(gossip));
}
static void sign_cache_purge(void *arg)
{
    (void)arg;
    slCashPurge();
}
static void draw_sign(unsigned int visual,int x,int y,int z,uint16_t yaw)
{
    if (!visual || !sign_intact || (!(dosei_sign_slow & 1u) &&
        !npc_sprite_in_view(x,y,z,sign_radius))) return;
    jo_3d_push_matrix();jo_3d_translate_matrix(x,-y,z);slRotY(yaw);
    if (sign_hot_dirty) {
        /* Both material variants stay immutable until the next bank upload.
         * FIFO orders the purge before any slave read of those new tables. */
        slSlaveFunc(sign_cache_purge, 0);
        sign_hot_dirty = false;
    }
    actor_mesh_draw_static(visual <= OOT_SIGN_MESH_TICKS ? sign_fade :
                           sign_hot ? sign_hot : sign_intact,0,0,-1,0);
    jo_3d_pop_matrix();
}
void world_props_draw(unsigned int tick)
{
    actor_t *a=0; unsigned int i,delta=tick-last_tick;last_tick=tick;
    PS_T0();
#ifdef DOSEI_OOT_CORE
    oot_core_meshes_draw();
#endif
    PS_ADD(PS_DWC);
    if(delta>12) delta=12;
    if(tree_mouth && kokiri_scene_room()==1) {
        int32_t x,y,z;tree_mouth_position(&x,&y,&z);actor_mesh_draw_static(tree_mouth,x,y,z,0);
    }
    while((a=actor_sys_find(WORLD_PROP_ID,a))) {
        if(a->scene!=save_state.scene_id || (a->room!=ACTOR_ROOM_NONE && a->room!=(int)(scene_flow_is_interior()?0:kokiri_scene_room()))) continue;
        {
            const kokiri_world_prop_t *p=&kokiri_world_props[a->data[0]];
            bool is_bush=p->id==0x14F && (p->param&3)==2;
            /* 2026-10-09 speed: off-screen props were transformed by SGL
             * every frame (all of Kokiri's pots, rocks, bushes, stones). */
            if(!npc_sprite_in_view(a->x,a->y+20,a->z,80)) continue;
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
    PS_ADD(PS_DWP);
    while((a=actor_sys_find(DROP_ACTOR_ID,a))) {
        int y=a->y;
        if(a->scene!=save_state.scene_id || (a->room!=ACTOR_ROOM_NONE && a->room!=(int)(scene_flow_is_interior()?0:kokiri_scene_room()))) continue;
        if(a->data[0]>0 && a->data[0]<60 && (tick&4)) continue;
        if(a->data[1]<GP_DROP_DELAY) y += a->data[1]*(GP_DROP_DELAY-a->data[1])/2;
        kokiri_drop_draw(a->params,a->x,y+14,a->z,tick);
    }
    {
    unsigned int sign_t0 = frame_timer_ticks();
    if(sign_intact && !(dosei_draw_mask & 2)) {
        for(i=0;i<KOKIRI_SIGN_COUNT;++i) {
            const kokiri_prop_t *s=&kokiri_signs[i];
            int dx=s->x-recomp_link.x,dz=s->z-recomp_link.z;
            if(s->room==kokiri_scene_room() && dx>-1000 && dx<1000 && dz>-1000 && dz<1000)
                draw_sign(world_signs_visual(i),s->x,s->y,s->z,kokiri_sign_yaws[i]);
        }
    }
    PS_ACC(PS_DSIGN, frame_timer_ticks_to_us(frame_timer_ticks() - sign_t0));
    }
    if(boss_heart){int32_t p[3];uint16_t yaw;
        if(gameplay.get_item==GP_GET_CONTAINER)
            actor_mesh_draw_static(boss_heart,recomp_link.x,recomp_link.y-RECOMP_LINK_EYE_HEIGHT+70,recomp_link.z,(uint16_t)(tick*512));
        else if(gohma_reward_body(0,p,&yaw))actor_mesh_draw_static(boss_heart,p[0],p[1],p[2],yaw);
        if(gohma_reward_body(1,p,&yaw))actor_mesh_draw_static(blue_warp,p[0],p[1]+1,p[2],0);
    }
    if(gohma){int32_t p[3];uint16_t yaw;int16_t pitch;unsigned frame;
        if(gohma_body(p,&yaw,&pitch,&frame)){
            jo_3d_push_matrix();jo_3d_translate_matrix(p[0],-p[1],p[2]);slRotY(yaw);slRotX((uint16_t)-pitch);
            kokiri_hit_filter(gohma_filter());
            actor_mesh_draw(gohma,frame,0,0,0,0,0,0,0);kokiri_hit_filter(0);jo_3d_pop_matrix();
        }
    }
    for(i=0;goma && i<GOHMA_LARVA_MAX;++i) {
        int32_t p[3],scale;uint16_t yaw;unsigned frame,kind=gohma_larva_body(i,p,&yaw,&frame,&scale);
        if(!kind)continue;
        jo_3d_push_matrix();jo_3d_translate_matrix(p[0],-p[1],p[2]);slScale(scale,scale,scale);
        kokiri_hit_filter(gohma_larva_filter(i));
        if(kind==1)actor_mesh_draw_static(goma_egg,0,0,0,yaw);
        else actor_mesh_draw(goma,frame,0,0,0,yaw,0,0,0);
        kokiri_hit_filter(0);
        jo_3d_pop_matrix();
    }
    for(i=0;hint && i<HINTNUTS_MAX;++i) {
        int32_t p[3];uint16_t yaw;unsigned frame;
        if(hintnuts_flower(i,p,&yaw))actor_mesh_draw_static(hint_flower,p[0],p[1],p[2],yaw);
        if(hintnuts_body(i,p,&yaw,&frame)){kokiri_hit_filter(hintnuts_filter(i));actor_mesh_draw(hint,frame,p[0],p[1],p[2],yaw,0,0,0);kokiri_hit_filter(0);}
    }
    for(i=0;hint_ball && i<HINTNUTS_BALLS;++i) {
        int32_t p[3];uint16_t roll;if(!hintnuts_ball(i,p,&roll))continue;
        jo_3d_push_matrix();jo_3d_translate_matrix(p[0],-p[1],p[2]);slRotY(recomp_yaw);slRotZ(roll);
        actor_mesh_draw_static(hint_ball,0,0,0,0);jo_3d_pop_matrix();
    }
    for(i=0;baba_head && i<DEKUBABA_MAX;++i) {
        const dekubaba_view *v=dekubaba_body(i);if(!v)continue;
        kokiri_hit_filter(dekubaba_filter(i));
        kokiri_dekubaba_stem(v);
        if(!v->stick) {
            jo_3d_push_matrix();jo_3d_translate_matrix(v->head[0],-v->head[1],v->head[2]);slRotY(v->yaw);slRotX((uint16_t)-v->pitch);
            slScale(v->scale,v->scale,v->scale);
            actor_mesh_draw(baba_head,v->frame,0,0,0,0,0,0,0);jo_3d_pop_matrix();
        }
    }
    kokiri_hit_filter(0);
    for(i=0;skull && i<WALL_SKULL_MAX;++i) {
        int32_t p[3];uint16_t yaw,roll;unsigned frame,kind=wall_skull_body(i,p,&yaw,&roll,&frame);
        if(kind) {
            jo_3d_push_matrix();jo_3d_translate_matrix(p[0],-p[1],p[2]);slRotY(yaw);slRotZ(roll);
            if(kind==3)actor_mesh_draw_static(skull_token,0,0,0,0);
            else {
                if(kind==1)slScale(32768,32768,32768);
                kokiri_hit_filter(wall_skull_filter(i));
                actor_mesh_draw(kind==1?skull:gold_skull,frame,0,0,0,0,0,0,0);kokiri_hit_filter(0);
            }
            jo_3d_pop_matrix();
        }
    }
    for(i=0;skull && i<SKULLTULA_MAX;++i) {
        int32_t p[3];uint16_t yaw,roll;unsigned frame;bool big;
        if(skulltula_body(i,p,&yaw,&roll,&frame,&big)) {
            jo_3d_push_matrix();jo_3d_translate_matrix(p[0],-p[1],p[2]);slRotY(yaw);slRotX(roll);
            if(big)slScale(91750,91750,91750);
            kokiri_hit_filter(skulltula_filter(i));
            actor_mesh_draw(skull,frame,0,0,0,0,0,0,0);kokiri_hit_filter(0);jo_3d_pop_matrix();
        }
    }
    for(i=0;puzzles[0] && i<dungeon_puzzles_count();++i) {
        int32_t x,y,z;uint16_t yaw,roll;unsigned model=dungeon_puzzles_body(i,&x,&y,&z,&yaw,&roll);
        if(model) {
            jo_3d_push_matrix();jo_3d_translate_matrix(x,-y,z);slRotY(yaw);slRotX(roll);
            if(model<=4) {
                static const int32_t heights[]={65536,45875,26214,6554};
                slScale(65536,heights[model-1],65536);model=1;
            }
            actor_mesh_draw_static(puzzles[model-1],0,0,0,0);jo_3d_pop_matrix();
        }
    }
    for(i=0;web && i<dungeon_webs_count();++i) {
        int32_t x,y,z;uint16_t yaw;
        if(dungeon_webs_body(i,&x,&y,&z,&yaw)) actor_mesh_draw_static(web,x,y,z,yaw);
    }
    for(i=0;i<5;++i) {
        int32_t x,y,z;
        if(walls[i] && dungeon_walls_body(i,&x,&y,&z))actor_mesh_draw_static(walls[i],x,y,z,0);
    }
    for(i=0;torches[0] && i<dungeon_torches_count();++i) {
        int32_t x,y,z;uint16_t yaw;bool lit;
        unsigned type=dungeon_torches_body(i,&x,&y,&z,&yaw,&lit);
        if(type) {
            actor_mesh_draw_static(torches[type-1],x,y,z,yaw);
            if(lit)kokiri_flame_draw(x,y+67,z,tick);
        }
    }
    for(i=0;door && i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];
        if(p->scene!=scene_flow_scene() || p->kind<8 || p->kind>=24 || !dungeon_door_active(i) ||
           (p->front!=kokiri_scene_room() && p->back!=kokiri_scene_room())) continue;
        actor_mesh_draw_static(door,p->x,p->y+dungeon_door_height(i),p->z,p->yaw);
    }
    for(i=0;handle_door && i<KOKIRI_PORTAL_COUNT;++i) {
        const kokiri_portal *p=&kokiri_portals[i];
        int32_t sn,cs;int open,hinge;
        if(p->kind<24 || p->kind>=32 || !dungeon_door_active(i))continue;
        open=(int)dungeon_door_height(i)*0x4000/120;
        kokiri_camera_sincos(p->yaw,&sn,&cs);
        /* Source idle skeleton offsets its leaf -2700 at scale .01.
         * Double-door actors additionally shift their centres by 30 units. */
        hinge=(p->flag&64) ? 57 : 27;
        actor_mesh_draw_static(handle_door,p->x-hinge*(cs/256)/256,p->y,
                               p->z+hinge*(sn/256)/256,(uint16_t)(p->yaw-open));
        if(p->flag&64)actor_mesh_draw_static(handle_door,p->x+hinge*(cs/256)/256,p->y,
                                            p->z-hinge*(sn/256)/256,(uint16_t)(p->yaw+0x8000+open));
    }
    unsigned int chest_t0 = frame_timer_ticks();
    for(i=0;chest && i<KOKIRI_CHEST_COUNT;++i) {
        const kokiri_chest_t *c=&kokiri_chests[i];
        unsigned int frame;int32_t focus[3];
        if(c->scene!=save_state.scene_id || c->room!=(scene_flow_is_interior() ? 0 : kokiri_scene_room())) continue;
        if(recomp_chest_index()==(int)i)chest_age[i]=(uint16_t)(recomp_chest_frame()*9/2);
        else if(gameplay_chest_opened(i) && chest_age[i]<WORLD_CHEST_FRAMES*3)
            chest_age[i]=(uint16_t)(chest_age[i]+delta);
        frame=chest_age[i]/3;
        if(frame>=WORLD_CHEST_FRAMES) frame=WORLD_CHEST_FRAMES-1;
        if(dosei_draw_mask & 16) continue; /* age still advances above */
        jo_3d_push_matrix();jo_3d_translate_matrix(c->x,-c->y,c->z);
        if((c->param>>12)==5) slScale(32768,32768,32768);
        actor_mesh_draw(chest,frame,0,0,0,c->yaw,0,0,focus);
        jo_3d_pop_matrix();
    }
    PS_ACC(PS_DCHEST, frame_timer_ticks_to_us(frame_timer_ticks() - chest_t0));
    PS_ADD(PS_DWR);   /* everything after PS_DWP; no early return above */
}
