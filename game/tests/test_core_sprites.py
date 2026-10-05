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

    def test_low_ram_draw_cache_boot_then_repeated_cleanup(self):
        source = HOST.read_text()
        storage = source[source.index('#define CORE_MESHES_MAX'):
                         source.index('#define ENTRY')]
        self.run_c(r'''
#include <stdint.h>
#include <string.h>
#include <assert.h>
''' + '#include "' + API + '"\n'
            + '#include "' + (ROOT / 'src/npc_sprite.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/oot_core_host.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/ram_low.h').as_posix() + '"\n'
            + '#include "' + (ROOT / 'src/collide.h').as_posix() + '"\n' + r'''
static unsigned int low[RAM_LOW_BYTES / sizeof(unsigned int)];
#undef RAM_LOW
#define RAM_LOW(offset) ((void *)((unsigned char *)low + (offset)))
#define __sh__ 1
#define CORE_SPRITE_ROWS 128
#define CORE_SPRITE_SLOTS 8
typedef int actor_mesh_t;
static unsigned frees;
static void jo_free(void *p) { assert(p); ++frees; }
''' + storage + function(HOST, 'static void sprites_reset(') + r'''
int main(void) {
    unsigned i;
    unsigned char *bytes = (unsigned char *)low;
    memset(low, 0xa5, sizeof(low));
    core_draw_init();
    for (i = 0; i < sizeof *CORE_DRAW; ++i)
        assert(bytes[RAM_LOW_OOTDRAW_OFFSET + i] == 0);
    sprites_reset(); assert(!frees);
    core_sprite[0] = bytes;
    core_sprite_tried[0] = 1;
    sprites_reset(); sprites_reset();
    assert(frees == 1 && !core_sprite[0] && !core_sprite_tried[0]);
    for (i = 0; i < RAM_LOW_OOTDRAW_OFFSET; ++i) assert(bytes[i] == 0xa5);
    for (i = RAM_LOW_OOTDRAW_OFFSET + sizeof *CORE_DRAW; i < sizeof(low); ++i)
        assert(bytes[i] == 0xa5);
    return 0;
}
''')

    def test_cull_rejects_hidden_sprites_without_wide_math(self):
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <math.h>
static struct { int x,y,z; } demo_camera;
static uint16_t demo_yaw,demo_pitch;
static int distance=277, calls, last_depth;
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
static bool loaded=true, playing, interior, paused;
static unsigned inputs;
static bool gameplay_is_paused(void) { return paused; }
static unsigned play_scene=0xffff,step_phase,update_us;
static int meshes_room=-1;
static unsigned scene=14,room,updates,loads,spawns;
static int source_room=-1, init_room=-1;
static struct { int x,y,z; } demo_link;
static int demo_link_yaw,demo_yaw;
static const void *scene_objects[1]; static unsigned scene_object_count;
static struct { int oot_scene; } entry;
static unsigned scene_flow_scene(void) { return scene; }
static void *scene_flow_entry(void) { return &entry; }
#define scene_flow_entry() (&entry)
static unsigned kokiri_bank_room(void) { return room; }
static bool scene_flow_is_interior(void) { return interior; }
static bool load_scene_blob(unsigned s) { return true; }
static void mirror_save(void) {}
static void sync_player(void) {}
static void send_input(const gameplay_input_t *in) { ++inputs; }
static bool gameplay_blade_points(int32_t *a,int32_t *b) { return false; }
static bool gameplay_sword_active(void) { return false; }
static unsigned frame_timer_ticks(void) { return 10; }
static unsigned frame_timer_ticks_to_us(unsigned t) { return t; }
static void load_meshes(void) { assert(spawns); ++loads; }
static void sprites_reset(void) {}
static bool sprites_refresh(void) { return false; }
static void npc_draw_reupload(void) {}
static int init(void *a,unsigned b,int c,const void *d,int r,short x,short y,short z,short yaw) {
    init_room=r; spawns=0; return 1;
}
static void objects(const void *const *o,unsigned n) {}
static void flags(unsigned f) { assert(f==OOT_CORE_FLAG_NPC_SPRITES); }
static void camera(short y) {}
static void set_room(int r) { source_room=r; }
static void sword(int active,const int *base,const int *tip) {}
static void update(void) { ++updates; spawns=1; }
static void push(int *x,int *z) { *x=*z=0; }
static int tool(unsigned c,int *io) { return 0; }
static void tools_free(void) {}
static bool gameplay_link_point(unsigned l,int32_t *o) { return false; }
static struct { unsigned tool_bits; int tool_pull[6]; } core_draw;
#define CORE_DRAW (&core_draw)
static OotCoreEntry api={.play_init=init,.set_objects=objects,.set_flags=flags,
    .set_camera=camera,.set_room=set_room,.set_sword=sword,.update=update,.player_push=push,.tool=tool};
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
    ++scene; interior=true; room=10; /* Ranch panorama artwork bank */
    oot_core_frame(&in); assert(init_room==0 && source_room==0);
    oot_core_frame(&in); assert(meshes_room==0 && loads==4);
    room=0; /* C-Up switches to the fixed JPEG; actor room must stay put */
    oot_core_frame(&in); assert(source_room==0 && meshes_room==0 && loads==4);
    unsigned old_updates=updates,old_phase=step_phase,old_inputs=inputs;
    paused=true;
    for(unsigned i=0;i<8;++i)oot_core_frame(&in);
    assert(updates==old_updates && step_phase==old_phase && inputs==old_inputs);
    paused=false;oot_core_frame(&in);assert(inputs==old_inputs+1);
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
#define CORE_SPRITE_ROWS 3
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
    core_sprite_rows[3]={{0xc0,19,0x1234,4},{0xe0,18,0x4567,5},{0xc0,19,0x9999,6}};
static unsigned char *core_sprite[3];
static unsigned char core_sprite_tried[3];
static unsigned core_sprite_reserved;
static struct { unsigned actors,missing,fallback,slots; } sprite_stats;
static npc_sprite_inst_t core_sprite_inst[8];
static actor_mesh_t *core_mesh[1],*core_skin[1];
static OotCoreMeshKey core_mesh_key[1];
static unsigned char core_mesh_ready[1],core_skin_ready[1];
static unsigned core_mesh_count,core_skin_count;
static bool playing=true;
#define TOOL_COUNT 1
static struct { unsigned char *tool_sheet[1]; npc_sprite_inst_t tool_inst[1]; } core_draw;
#define CORE_DRAW (&core_draw)
static void tools_load(void) {}
static OotCoreNpcView views[3];
static int count;
static unsigned reads,alloc_bytes,reuploads,uploads,draws;
static unsigned opens,fail_file,fail_alloc,fail_read,invalid_packet,live;
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
static int jo_fs_open(jo_file *p,const char *s) { ++opens; p->size=64; return !fail_file; }
static void jo_fs_close(jo_file *p) {}
static void jo_free(void *p) { assert(p && live); --live; free(p); }
static void *jo_malloc(unsigned n) { alloc_bytes=n; if(fail_alloc)return 0; ++live; return malloc(n); }
static unsigned jo_memory_usage_percent(void) { return 50; }
static void *jo_fs_read_file_ptr(const char *s,void *p,int *n) {
    /* Jo's documented NUL write must fit; old length-only allocation fails. */
    assert(alloc_bytes>=65);
    assert(!strcmp(s,"G0C004.SPR") || !strcmp(s,"G0E005.SPR") || !strcmp(s,"G0C006.SPR"));
    memset(p,0,65); ((unsigned char*)p)[5]=48; ((unsigned char*)p)[7]=56;
    *n=64; ++reads; return fail_read ? 0 : p;
}
static int npc_sprite_valid(const unsigned char *s,unsigned n) { return !invalid_packet; }
static int npc_sprite_upload(const unsigned char *s,npc_sprite_inst_t *p) {
    p->slot=uploads++; return 1;
}
static int npc_sprite_visible(const unsigned char *s,int x,int y,int z) { return z>=0; }
static void npc_sprite_draw(const unsigned char *s,npc_sprite_inst_t *p,unsigned f,
                           int x,int y,int z,uint16_t yaw) {
    assert(p->slot==0 && s==core_sprite[0]); ++draws;
}
''' + function(HOST, 'static void sprites_reset(')
            + function(HOST, 'static bool sprites_refresh(')
            + function(HOST, 'static void load_meshes(')
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
    views[1]=views[0]; views[0].z=-100; count=2;
    sprites_draw(); assert(draws==4); /* hidden actor cannot consume visible actor's slot */
    views[0].z=0; count=1;
    assert(!sprites_refresh() && sprite_stats.fallback==1 && !core_sprite[2]);
    /* Later same-room spawns discover a new object without freeing old sheets. */
    unsigned char *original=core_sprite[0];
    views[1]=views[0]; views[1].object=0xe0; views[1].limbs=19;
    views[1].anim=0x06004567; count=2;
    assert(sprites_refresh() && reads==2 && core_sprite[0]==original && live==2);
    uploads=0; oot_core_meshes_upload(); assert(uploads==2 && sprite_stats.slots==2);
    assert(!sprites_refresh() && reads==2 && sprite_stats.actors==2 && !sprite_stats.missing);
    /* More instances of an existing object need slots, never new CD reads. */
    views[2]=views[1]; count=3;
    assert(sprites_refresh() && reads==2);
    count=1; assert(!sprites_refresh()); /* disappearance preserves capacity */
    count=0; load_meshes(); assert(!core_sprite[0] && !live && reads==2);
    /* Each unavailable file is attempted once per room; next room retries. */
    count=1; fail_file=1; unsigned before=opens;
    assert(!sprites_refresh() && sprite_stats.missing==1 && opens==before+2);
    assert(!sprites_refresh() && opens==before+2);
    sprites_reset(); fail_file=0; fail_alloc=1;
    assert(!sprites_refresh() && !live && sprite_stats.missing==1);
    sprites_reset(); fail_alloc=0; fail_read=1;
    assert(!sprites_refresh() && !live);
    sprites_reset(); fail_read=0; invalid_packet=1;
    assert(!sprites_refresh() && !live);
    sprites_reset(); invalid_packet=0;
    assert(sprites_refresh() && live==1);
    sprites_reset(); sprites_reset(); assert(!live);
    return 0;
}
''')

    def test_sprite_packets_validate_before_generic_upload(self):
        self.run_c(r'''
#include <assert.h>
#include <string.h>
#define U16(s,o) ((unsigned)((s)[o]<<8 | (s)[(o)+1]))
#define CELS(s) (0x34u + ((U16(s,0x0c)*2u+3u)&~3u))
''' + function(ROOT / 'src/npc_sprite.c', 'int npc_sprite_valid(') + r'''
int main(void) {
    unsigned char sheet[76]={0};
    memcpy(sheet,"SPR1",4); sheet[5]=8; sheet[7]=1; sheet[9]=5;
    sheet[11]=1; sheet[13]=1; sheet[17]=1;
    assert(npc_sprite_valid(sheet,sizeof sheet));
    assert(!npc_sprite_valid(0,76) && !npc_sprite_valid(sheet,75));
    sheet[0]='X'; assert(!npc_sprite_valid(sheet,76)); sheet[0]='S';
    sheet[0x35]=1; assert(!npc_sprite_valid(sheet,76)); sheet[0x35]=0;
    sheet[5]=7; assert(!npc_sprite_valid(sheet,76)); sheet[5]=8;
    sheet[12]=0xff; sheet[13]=0xff; assert(!npc_sprite_valid(sheet,76));
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
