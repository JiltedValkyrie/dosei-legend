"""Execute production scene teardown before next-scene heap allocations."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics


ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'src/oot_core_host.c'
FLOW = ROOT / 'src/scene_flow.c'


class SceneResourceLifetime(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def run_lifetime(self, body):
        source = HOST.read_text()
        storage = source[source.index('#define CORE_MESHES_MAX'):source.index('#define ENTRY')]
        headers = '\n'.join('#include "%s"' % path.as_posix() for path in (
            ROOT / 'oot-core/include/oot_core_api.h', ROOT / 'src/npc_sprite.h',
            ROOT / 'src/collide.h', ROOT.parent / 'shared/lib/collision/kokiri_collision.h'))
        functions = '\n'.join(graphics.function(HOST, marker) for marker in (
            'static void sprites_reset(', 'static void tools_free(',
            'static void core_dyna_drop(', 'static void core_dyna_reset(',
            'static void meshes_free(', 'void oot_core_scene_restart(',
            'void oot_core_scene_unload(', 'void oot_core_clock_reset(',
            'void oot_core_session_reset('))
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
''' + headers + r'''
#define CORE_SPRITE_ROWS 7
#define CORE_SPRITE_SLOTS 16
typedef struct { unsigned actors,missing,fallback,slots; } oot_core_sprite_stats_t;
typedef struct { unsigned payload; } actor_mesh_t;
''' + storage + r'''
static bool loaded,playing,scene_load_failed;
void bg_water_bind(const bg_waterbox_t *water,unsigned count) { assert(!water && !count); }
static unsigned play_scene,step_phase;
static int meshes_room;
static const void *const *scene_objects;
static unsigned scene_object_count;
static unsigned short core_skybox_time;
static unsigned char core_skybox_reset;
static const void *objects[2];
static OotCoreSave old_mirror;
static const OotCoreSave *attached_save;
static unsigned selected_save,destructors,destroy_calls,release_calls,detach_calls;
static unsigned heap_live,free_calls,mesh_frees,remove_calls;
static bool play_live,pack_live,expect_detached;
typedef struct { void *ptr; unsigned bytes; bool live; } allocation_t;
static allocation_t blocks[64];
static unsigned blocks_count;
static void *dyna_registry[OOT_CORE_DYNA_VIEWS_MAX];

static void *allocate(unsigned bytes) {
    void *p=malloc(bytes);
    assert(p && blocks_count<64);
    memset(p,0x5a,bytes);
    blocks[blocks_count++]=(allocation_t){p,bytes,true};
    heap_live+=bytes;
    return p;
}
static void jo_free(void *p) {
    assert(p && !play_live && pack_live);
    for(unsigned i=0;i<OOT_CORE_DYNA_VIEWS_MAX;++i)
        assert(dyna_registry[i]!=p); /* no query may keep freed collision */
    for(unsigned i=0;i<blocks_count;++i) if(blocks[i].ptr==p && blocks[i].live) {
        blocks[i].live=false;
        heap_live-=blocks[i].bytes;
        ++free_calls;
        free(p);
        return;
    }
    assert(0); /* unknown pointer or double free */
}
void bg_dyna_remove(uint32_t id) {
    assert(!play_live && pack_live && id<OOT_CORE_DYNA_VIEWS_MAX);
    dyna_registry[id]=0;
    ++remove_calls;
}
static void actor_mesh_free(actor_mesh_t *mesh) {
    ++mesh_frees;
    jo_free(mesh);
}
static void set_save(const OotCoreSave *save) {
    assert(!save && !destructors && !free_calls && pack_live);
    attached_save=save;
    ++detach_calls;
}
static void destroy(void) {
    ++destroy_calls;
    if(!play_live)return; /* source destroy is itself idempotent */
    assert(pack_live && heap_live && !free_calls);
    assert(scene_objects==objects && scene_object_count==2);
    for(unsigned i=0;i<blocks_count;++i)assert(blocks[i].live);
    if(expect_detached)assert(!attached_save && detach_calls==1);
    else assert(attached_save==&old_mirror);
    /* This models the old scene flag copy-out: a new save must be detached. */
    if(attached_save)selected_save=0x55;
    play_live=false;
    ++destructors;
}
static int release(void) {
    assert(!play_live && !heap_live && !core_mesh_count);
    for(unsigned i=0;i<OOT_CORE_DYNA_VIEWS_MAX;++i)assert(!dyna_registry[i]);
    pack_live=false;
    ++release_calls;
    return 1;
}
static OotCoreEntry api={.play_destroy=destroy,.pack_release=release,.set_save=set_save};
#define ENTRY (&api)
''' + functions + r'''
static void old_scene(void) {
    core_draw_init();
    loaded=playing=play_live=pack_live=scene_load_failed=true;
    play_scene=12;meshes_room=3;step_phase=2;
    scene_objects=objects;scene_object_count=2;
    attached_save=&old_mirror;selected_save=0x1234;
    for(unsigned i=0;i<CORE_SPRITE_ROWS;++i) {
        core_sprite[i]=allocate(8192+i*16);
        core_sprite_tried[i]=1;
    }
    core_sprite_reserved=CORE_SPRITE_SLOTS;
    memset(&sprite_stats,0x55,sizeof sprite_stats);
    for(unsigned i=0;i<TOOL_COUNT;++i) {
        CORE_DRAW->tool_sheet[i]=allocate(1024);
        CORE_DRAW->tool_tried[i]=1;
    }
    CORE_DRAW->tool_bits=~0u;
    for(unsigned i=0;i<2;++i) {
        core_dyna[i].key=0x100+i;
        core_dyna[i].id=i;
        core_dyna[i].tri=allocate(128);
        dyna_registry[i]=core_dyna[i].tri;
    }
    for(unsigned i=0;i<3;++i) {
        core_mesh[i]=allocate(sizeof(actor_mesh_t));
        core_mesh_ready[i]=1;
    }
    core_mesh_count=3;
}
static void empty_scene(void) {
    assert(!playing && !scene_load_failed && play_scene==~0u && meshes_room==-1);
    assert(!scene_objects && !scene_object_count && !heap_live);
    assert(!core_mesh_count && !core_sprite_reserved && !CORE_DRAW->tool_bits);
    for(unsigned i=0;i<CORE_SPRITE_ROWS;++i)
        assert(!core_sprite[i] && !core_sprite_tried[i]);
    for(unsigned i=0;i<TOOL_COUNT;++i)
        assert(!CORE_DRAW->tool_sheet[i] && !CORE_DRAW->tool_tried[i]);
    for(unsigned i=0;i<OOT_CORE_DYNA_VIEWS_MAX;++i)
        assert(!core_dyna[i].key && !core_dyna[i].tri && !dyna_registry[i]);
    for(unsigned i=0;i<3;++i)assert(!core_mesh[i] && !core_mesh_ready[i]);
    oot_core_sprite_stats_t zero={0};
    assert(!memcmp(&sprite_stats,&zero,sizeof zero));
}
int main(void) {
''' + body + '\nreturn 0;\n}\n')

    def test_destroy_keeps_objects_and_pack_alive_until_every_resource_is_released(self):
        self.run_lifetime(r'''
    old_scene();
    oot_core_scene_unload();
    empty_scene();
    assert(destructors==1 && destroy_calls==1 && release_calls==1);
    assert(free_calls==CORE_SPRITE_ROWS+TOOL_COUNT+2+3);
    assert(mesh_frees==3 && remove_calls==2 && !detach_calls);
    assert(selected_save==0x55); /* normal doorway still persists old flags */
    unsigned freed=free_calls;
    oot_core_scene_unload();
    oot_core_scene_unload();
    empty_scene();
    assert(free_calls==freed && destructors==1 && mesh_frees==3 && remove_calls==2);
''')

    def test_session_detaches_selected_save_before_destroy_and_releases_all_resources(self):
        self.run_lifetime(r'''
    old_scene();
    expect_detached=true;
    oot_core_session_reset(0x8123);
    empty_scene();
    assert(selected_save==0x1234 && detach_calls==1 && destructors==1);
    assert(core_skybox_time==0x8123 && core_skybox_reset==2);
    assert(free_calls==CORE_SPRITE_ROWS+TOOL_COUNT+2+3 && release_calls==1);
''')

    def test_partial_play_and_cold_core_teardown_are_safe(self):
        self.run_lifetime(r'''
    /* Frontend can reset before boot; no core entry is callable then. */
    oot_core_session_reset(0x3456);
    empty_scene();
    assert(!destroy_calls && !release_calls && !detach_calls && !free_calls);
    assert(core_skybox_time==0x3456 && core_skybox_reset==2);
    old_scene();
    playing=false; /* failed Play_Init still owns destructible source state */
    oot_core_scene_unload();
    empty_scene();
    assert(destructors==1 && release_calls==1);
''')

    def test_scene_loader_tears_down_after_collision_commit_before_room_and_npc_allocations(self):
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define SCENE_COUNT 3
#define SCENE_KOKIRI_SHOP 1
#define STORY_BANK_PANORAMA 255
typedef struct { unsigned rooms,image,panorama,sfx_bank,save_scene; } scene_entry_t;
typedef struct { unsigned room; } scene_spawn_t;
static scene_entry_t scene_entries[3]={{1,0,255,0,0},{1,1,255,1,1},{1,1,0,2,2}};
static scene_spawn_t spawn_record;
static struct { unsigned link_age; }save_state;
static unsigned current_scene;
static bool loaded,door_armed;
static bool old_resources,collision_published;
static unsigned failure,unloads,trims,room_loads,npc_loads,story_loads,restarts,errors;
static const scene_spawn_t *scene_flow_spawn(unsigned s,unsigned spawn) { return &spawn_record; }
static void story_route_free(void) {}
static void npc_draw_free(void) {}
static bool kokiri_link_set_age(bool adult) { return failure!=1; }
static void oot_follow_set_adult(bool adult) {}
static bool collision_load(unsigned scene) {
    assert(old_resources && !unloads);
    if(failure==2)return false;
    collision_published=true;
    return true;
}
static void oot_core_scene_unload(void) {
    assert(collision_published && old_resources && !room_loads && !npc_loads && !story_loads);
    old_resources=false;
    ++unloads;
}
static void music_area_trim(void) {
    assert(!old_resources && unloads==1 && !room_loads && !npc_loads && !story_loads);
    ++trims;
}
static bool room_allocate(void) {
    /* Retained Ranch archives would consume the next scene's model budget. */
    assert(!old_resources && unloads==1 && trims==1 && collision_published);
    ++room_loads;
    return failure!=3;
}
static bool kokiri_scene_load_backdrop(unsigned s,unsigned r) { return room_allocate(); }
static bool kokiri_scene_load_bank(unsigned s,unsigned r) { return room_allocate(); }
#define SCENE_SPOT00 10
static void action_audio_set_field(bool field) { assert(!old_resources && room_loads); }
static bool action_audio_set_area(unsigned bank) { assert(!old_resources && room_loads); return true; }
static void minimap_scene(unsigned s) {}
static bool story_route_load(unsigned s) {
    assert(!old_resources && room_loads && unloads==1);
    ++story_loads;
    return failure!=4;
}
static bool npc_draw_load(unsigned s) {
    assert(!old_resources && room_loads && unloads==1);
    ++npc_loads;
    return failure!=5;
}
static void oot_core_scene_restart(void) { assert(!old_resources && npc_loads); ++restarts; }
static void jo_core_error(const char *message,...) { ++errors; }
''' + graphics.function(FLOW, 'bool __attribute__((optimize("Os"))) scene_flow_load(') + r'''
static void reset(void) {
    old_resources=true;collision_published=false;
    unloads=trims=room_loads=npc_loads=story_loads=restarts=errors=0;
    loaded=false;door_armed=true;spawn_record.room=0;
}
int main(void) {
    for(unsigned scene=0;scene<SCENE_COUNT;++scene) {
        for(failure=0;failure<=5;++failure) {
            reset();
            bool ok=scene_flow_load(scene,0);
            assert(ok==(failure==0));
            if(failure==1 || failure==2) {
                assert(old_resources && !unloads && !trims && !room_loads && !restarts);
            } else {
                assert(!old_resources && unloads==1 && room_loads==1);
                if(!failure)assert(loaded && !door_armed && current_scene==scene && restarts==1);
                else assert(!restarts);
            }
        }
    }
    reset();failure=0;
    assert(!scene_flow_load(SCENE_COUNT,0));
    assert(old_resources && !unloads);
    spawn_record.room=1;
    assert(!scene_flow_load(0,0));
    assert(old_resources && !unloads);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
