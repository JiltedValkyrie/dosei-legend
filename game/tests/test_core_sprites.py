"""Run the actual C host lifecycle/renderer against deferred decomp actors."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

function = graphics.function

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / 'src/oot_core_host.c'
API = (ROOT / 'oot-core/include/oot_core_api.h').as_posix()


class CoreSprites(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_cull_rejects_hidden_sprites_without_wide_math(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <math.h>
static struct { int x,y,z; } demo_camera;
static uint16_t demo_yaw,demo_pitch;
static int distance=277, calls;
static int demo_screen_distance(void) { return distance; }
static void kokiri_camera_sincos(uint16_t angle,int32_t *s,int32_t *c) {
    *s=(int32_t)(sin(angle*6.283185307179586/65536)*65536);
    *c=(int32_t)(cos(angle*6.283185307179586/65536)*65536); ++calls;
}
''' + function(ROOT / 'src/npc_sprite.c', 'int npc_sprite_in_view(') + r'''
int main(void) {
    assert(npc_sprite_in_view(0,0,100,10));
    assert(!npc_sprite_in_view(0,0,-100,10));
    assert(!npc_sprite_in_view(1000,0,100,10));
    assert(npc_sprite_in_view(85,0,100,20)); /* partly on screen */
    assert(calls==2); /* shared view, including fairies: trig computed once */
    demo_yaw=16384;
    assert(npc_sprite_in_view(100,0,0,10));
    assert(!npc_sprite_in_view(-100,0,0,10));
    demo_pitch=16384;
    assert(npc_sprite_in_view(0,100,0,10));
    assert(!npc_sprite_in_view(0,-100,0,10));
    assert(npc_sprite_in_view(32768,0,0,10)); /* out-of-range guard */
    distance=5000; assert(npc_sprite_in_view(-100,0,0,10));
    return 0;
}
''')

    def test_full_bank_returns_failure_after_narrowing_slot(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#define NPC_SPRITE_SLOT_NONE UINT16_MAX
#define KOKIRI_TILE_NONE UINT32_MAX
#define U16(s,o) ((unsigned)((s)[o]<<8 | (s)[(o)+1]))
#define CELS(s) (0x34u + ((U16(s,0x0c)*2u+3u)&~3u))
typedef struct { const unsigned char *sheet; uint16_t slot,colno,shown; } npc_sprite_inst_t;
static unsigned next_slot=KOKIRI_TILE_NONE;
static unsigned kokiri_bank_tile_upload(const void *a,const void *b,unsigned w,unsigned h,unsigned *col) {
    *col=16; return next_slot;
}
''' + function(ROOT / 'src/npc_sprite.c', 'int npc_sprite_upload(') + r'''
int main(void) {
    unsigned char sheet[64]={0}; npc_sprite_inst_t inst={0};
    assert(!npc_sprite_upload(sheet,&inst));
    assert(inst.slot==NPC_SPRITE_SLOT_NONE);
    next_slot=42; assert(npc_sprite_upload(sheet,&inst));
    assert(inst.slot==42 && inst.sheet==sheet);
    return 0;
}
''')

    def test_assets_follow_first_actor_step_and_room_change(self):
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
''' + '#include "' + API + '"\n' + r'''
#define CORE_SPRITES 1
#define RAM_LOW_OOTPLAY_OFFSET 0
#define RAM_LOW_OOTPLAY_BYTES 1
#define RAM_LOW(x) ((void*)0)
#define OOT_SCENECOL_ADDR 0
#define DEMO_LINK_EYE_HEIGHT 16
typedef struct { int unused; } gameplay_input_t;
static bool loaded=true, playing;
static unsigned play_scene=0xffff,step_phase,update_us;
static int meshes_room=-1;
static unsigned scene=14,room,updates,loads,spawns;
static struct { int x,y,z; } demo_link;
static int demo_link_yaw,demo_yaw;
static const void *scene_objects[1]; static unsigned scene_object_count;
static struct { int oot_scene; } entry;
static unsigned scene_flow_scene(void) { return scene; }
static void *scene_flow_entry(void) { return &entry; }
#define scene_flow_entry() (&entry)
static unsigned kokiri_bank_room(void) { return room; }
static bool load_scene_blob(unsigned s) { return true; }
static void mirror_save(void) {}
static void sync_player(void) {}
static void send_input(const gameplay_input_t *in) {}
static bool gameplay_blade_points(int32_t *a,int32_t *b) { return false; }
static bool gameplay_sword_active(void) { return false; }
static unsigned frame_timer_ticks(void) { return 10; }
static unsigned frame_timer_ticks_to_us(unsigned t) { return t; }
static void load_meshes(void) { assert(spawns); ++loads; }
static int init(void *a,unsigned b,int c,const void *d,int r,short x,short y,short z,short yaw) {
    spawns=0; return 1;
}
static void objects(const void *const *o,unsigned n) {}
static void flags(unsigned f) { assert(f==OOT_CORE_FLAG_NPC_SPRITES); }
static void camera(short y) {}
static void set_room(int r) {}
static void sword(int active,const int *base,const int *tip) {}
static void update(void) { ++updates; spawns=1; }
static void push(int *x,int *z) { *x=*z=0; }
static OotCoreEntry api={.play_init=init,.set_objects=objects,.set_flags=flags,
    .set_camera=camera,.set_room=set_room,.set_sword=sword,.update=update,.player_push=push};
#define ENTRY (&api)
''' + function(HOST, 'void oot_core_frame(') + r'''
int main(void) {
    gameplay_input_t in={0};
    oot_core_frame(&in); assert(!updates && !loads); /* skipped 20 Hz step */
    oot_core_frame(&in); assert(updates==1 && loads==1);
    oot_core_frame(&in); assert(updates==2 && loads==1);
    room=1; spawns=0;
    oot_core_frame(&in); assert(updates==2 && loads==1); /* no premature room load */
    oot_core_frame(&in); assert(updates==3 && loads==2);
    oot_core_frame(&in); assert(updates==4 && loads==2); /* no repeated CD reads */
    ++scene;
    oot_core_frame(&in); assert(updates==4 && loads==2);
    oot_core_frame(&in); assert(updates==5 && loads==3);
    return 0;
}
''')

    def test_spawned_sheets_root_joint_and_vram_instance_count(self):
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <stdlib.h>
#include <string.h>
''' + '#include "' + API + '"\n' + r'''
#define CORE_SPRITES 1
#define CORE_SPRITE_ROWS 2
#define CORE_SPRITE_SLOTS 8
#define CORE_SPRITE_HEAP_PERCENT 85
#define CORE_MESHES_MAX 1
#define KOKIRI_TILE_NONE 0xffff
#define NPC_SPRITE_SLOT_NONE 0xffff
typedef char Sint8;
typedef int actor_mesh_t;
typedef struct { unsigned size; } jo_file;
typedef struct { const unsigned char *sheet; unsigned short slot,colno,shown; } npc_sprite_inst_t;
static const struct { unsigned short object; unsigned char limbs; unsigned anim,file; }
    core_sprite_rows[2]={{0xc0,19,0x1234,4},{0xe0,18,0x4567,5}};
static unsigned char *core_sprite[2];
static npc_sprite_inst_t core_sprite_inst[8];
static actor_mesh_t *core_mesh[1],*core_skin[1];
static OotCoreMeshKey core_mesh_key[1];
static unsigned char core_mesh_ready[1],core_skin_ready[1];
static unsigned core_mesh_count,core_skin_count;
static bool playing=true;
static OotCoreNpcView views[3];
static int count;
static unsigned reads,alloc_bytes,reuploads,uploads,draws;
static struct { int x,z; } demo_camera;
static int mesh_list(const OotCoreMeshKey **p) { return 0; }
static int npc_view(const OotCoreNpcView **p) { *p=views; return count; }
static OotCoreEntry api={.mesh_list=mesh_list,.npc_view=npc_view};
#define ENTRY (&api)
static int oot_core_npcs(const OotCoreNpcView **p) { return npc_view(p); }
static void actor_mesh_free(actor_mesh_t *m) {}
static actor_mesh_t *actor_mesh_load_static(const char *s) { return 0; }
static int actor_mesh_upload(actor_mesh_t *m) { return 1; }
static void npc_draw_reupload(void) { ++reuploads; }
static int GFS_NameToId(Sint8 *s) { return 1; }
static int jo_fs_open(jo_file *p,const char *s) { p->size=64; return 1; }
static void jo_fs_close(jo_file *p) {}
static void jo_free(void *p) { free(p); }
static void *jo_malloc(unsigned n) { alloc_bytes=n; return malloc(n); }
static unsigned jo_memory_usage_percent(void) { return 50; }
static void *jo_fs_read_file_ptr(const char *s,void *p,int *n) {
    /* Jo's documented NUL write must fit; old length-only allocation fails. */
    assert(alloc_bytes>=65); assert(!strcmp(s,"G0C004.SPR"));
    memset(p,0,65); ((unsigned char*)p)[5]=48; ((unsigned char*)p)[7]=56;
    *n=64; ++reads; return p;
}
static int npc_sprite_upload(const unsigned char *s,npc_sprite_inst_t *p) {
    p->slot=uploads++; return 1;
}
static void npc_sprite_draw(const unsigned char *s,npc_sprite_inst_t *p,unsigned f,
                           int x,int y,int z,uint16_t yaw) {
    assert(p->slot==0 && s==core_sprite[0]); ++draws;
}
''' + function(HOST, 'static void load_meshes(')
            + function(HOST, 'void oot_core_meshes_upload(')
            + function(HOST, 'static void sprites_draw(') + r'''
int main(void) {
    /* Spawned Ingo: skeleton has 19 limbs, SkelAnime includes translation. */
    count=1; views[0].object=0xc0; views[0].limbs=20;
    views[0].anim=0x06001234; views[0].flags=OOT_CORE_VIEW_DRAWN;
    load_meshes(); assert(reads==1 && core_sprite[0] && !core_sprite[1]);
    oot_core_meshes_upload(); assert(uploads==1);
    for(unsigned i=1;i<8;++i) assert(core_sprite_inst[i].slot==KOKIRI_TILE_NONE);
    sprites_draw(); assert(draws==1);
    views[0].limbs=19; sprites_draw(); assert(draws==1); /* wrong skeleton rejected */
    views[0].limbs=0; sprites_draw(); assert(draws==2); /* clock-only Malon: no skeleton header read */
    views[0].limbs=20; views[0].anim=0x06009999;
    sprites_draw(); assert(draws==3); /* missing pose keeps a compatible sprite visible */
    count=0; load_meshes(); assert(!core_sprite[0] && reads==1);
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
