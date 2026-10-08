"""OAP wire validation, actual registry/constructors and scene load failures."""
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_actor_packs as packs
import test_graphics_backend as graphics
function = graphics.function


def image(**changes):
    fields = dict(magic=packs.MAGIC, version=1, header_bytes=80, core_crc=123,
                  link_base=0x02770000 - 128, file_bytes=124, memory_bytes=128,
                  bss_offset=124, bss_bytes=4, ctors_offset=120, ctor_count=1,
                  actors_offset=124, actor_count=0, effects_offset=124, effect_count=0,
                  crc=0, text_offset=80, text_bytes=36, scene=1, flags=0)
    fields.update(changes)
    data = bytearray(124)
    struct.pack_into('>20I', data, 0, *(fields[n] for n in packs.FIELDS))
    struct.pack_into('>I', data, 120, fields['link_base'] + 80)
    struct.pack_into('>I', data, 60, zlib.crc32(data))
    return data


class ActorPackFormat(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_teardown_keeps_old_scene_owner_and_preserves_host_transition_state(self):
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
typedef int s32;
typedef struct { unsigned long chest,swch,clear,collect; } Flags;
typedef struct { Flags flags; } ActorContext;
typedef struct { ActorContext actorCtx; int colChkCtx; } PlayState;
typedef struct { unsigned long* scene_flags; } Mirror;
static Mirror* sHostSave;
static PlayState* gOotCorePlay;
static void* sScene;
static int table[2], stage;
static struct { int* table; int tableSize; } sEffectSsInfo;
static void func_80031C3C(ActorContext* actor, PlayState* play) {
    assert(stage==0 && play==gOotCorePlay && sEffectSsInfo.table==table);
    actor->flags.swch=0x55; stage=1;
}
static void EffectSs_Delete(int* row) { assert(stage==1 && row>=table && row<table+2); }
static void EffectSs_ClearAll(PlayState* play) {
    assert(stage==1 && play==gOotCorePlay); sEffectSsInfo.table=0; sEffectSsInfo.tableSize=0; stage=2;
}
static void Effect_DeleteAll(PlayState* play) { assert(stage==2); stage=3; }
static void CollisionCheck_ClearContext(PlayState* play, int* context) { assert(stage==3); stage=4; }
static void OotCore_ToolReset(void) { assert(stage==4); stage=5; }
static void OotCore_OcarinaReset(void) { assert(stage==5); stage=6; }
static void OotCore_GfxReset(void) { assert(stage==6); stage=7; }
static void ZeldaArena_Cleanup(void) { assert(stage==7); stage=8; }
static void save_copy_out(PlayState* play) { assert(0); } /* forbidden stale global copy */
''' + function(ROOT / 'oot-core/src/oot_core_api.cpp', 'static void oot_core_play_destroy(') + r'''
int main(void) {
    unsigned long previous[4]={1,2,3,4}, next[4]={8,9,10,11};
    Mirror mirror={previous}; PlayState play={{{1,2,3,4}},0};
    sHostSave=&mirror; gOotCorePlay=&play; sScene=&play;
    sEffectSsInfo.table=table; sEffectSsInfo.tableSize=2;
    oot_core_play_destroy();
    assert(stage==8 && previous[1]==0x55 && next[1]==9);
    assert(!gOotCorePlay && !sScene && !sEffectSsInfo.table);
    oot_core_play_destroy(); assert(stage==8); /* idempotent */
    /* New selected save is already installed: detached mirror stays untouched. */
    stage=0; sHostSave=0; gOotCorePlay=&play;
    sEffectSsInfo.table=table; sEffectSsInfo.tableSize=2;
    oot_core_play_destroy(); assert(next[0]==8 && next[1]==9);
    return 0;
}
''')

    def test_new_session_detaches_mirror_before_destroy(self):
        host = ROOT / 'src/oot_core_host.c'
        self.run_c(r'''
#include <assert.h>
#include <stddef.h>
#include <stdbool.h>
static bool loaded=true,playing=true,scene_load_failed=true;
static unsigned int play_scene=1;
static unsigned short core_skybox_time;
static unsigned char core_skybox_reset;
static int stage,resource_resets;
static const void *const *scene_objects;
static unsigned scene_object_count;
static int meshes_room=2;
static void bg_water_bind(const void* water, unsigned count) { assert(!water && !count); }
static void set_save(const void* mirror) { assert(!mirror && stage==0); stage=1; }
static void destroy(void) { assert(stage==1 && !playing); stage=2; }
static void resource_reset(void) { if(loaded) { assert(stage==2); ++resource_resets; } }
static void sprites_reset(void) { resource_reset(); }
static void tools_free(void) { resource_reset(); }
static void core_dyna_reset(void) { resource_reset(); }
static void meshes_free(void) { resource_reset(); }
static int release(void) { assert(stage==2 && resource_resets==4); stage=3; return 1; }
static struct { void (*set_save)(const void*); void (*play_destroy)(void); int (*pack_release)(void); }
entry={set_save,destroy,release};
#define ENTRY (&entry)
''' + function(host, 'void oot_core_scene_restart(') + '\n' +
            function(host, 'void oot_core_scene_unload(') + '\n' +
            function(host, 'void oot_core_clock_reset(') + '\n' +
            function(host, 'void oot_core_session_reset(') + r'''
int main(void) {
    oot_core_session_reset(0x2345);
    assert(stage==3 && !playing && !scene_load_failed && play_scene==~0u);
    assert(resource_resets==4 && meshes_room==-1 && !scene_objects && !scene_object_count);
    assert(core_skybox_time==0x2345 && core_skybox_reset==2);
    loaded=false; oot_core_session_reset(0);
    assert(stage==3 && resource_resets==4 && core_skybox_time==0);
    return 0;
}
''')

    def test_top_alignment_and_named_scene_budget(self):
        h = packs.validate(image(), 123, used=0x40000 - 128)
        self.assertEqual(h['link_base'], 0x0276ff80)
        with self.assertRaisesRegex(ValueError, 'OOC.*OOB.*OAP'):
            packs.validate(image(), 123, used=0x40000 - 127)

    def test_malformed_sizes_tables_and_core_binding(self):
        cases = [dict(magic=0), dict(version=2), dict(header_bytes=76), dict(core_crc=122),
                 dict(file_bytes=123), dict(memory_bytes=0xffffffff), dict(memory_bytes=112),
                 dict(link_base=0x02730000), dict(bss_offset=120), dict(bss_bytes=5),
                 dict(ctors_offset=0xfffffffc), dict(ctor_count=0xffffffff),
                 dict(ctors_offset=81), dict(actor_count=1), dict(effects_offset=0),
                 dict(ctors_offset=84), dict(actors_offset=120),
                 dict(text_bytes=0), dict(flags=2)]
        for case in cases:
            with self.subTest(case=case), self.assertRaises(ValueError):
                packs.validate(image(**case), 123)

    def test_bad_checksum_and_constructor_address(self):
        bad = image()
        bad[84] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            packs.validate(bad, 123)
        bad = image()
        struct.pack_into('>I', bad, 120, 0x02770000)
        struct.pack_into('>I', bad, 60, 0)
        struct.pack_into('>I', bad, 60, zlib.crc32(bad))
        with self.assertRaisesRegex(ValueError, 'ctor pointer'):
            packs.validate(bad, 123)

    def test_real_sh2_fixture_when_built(self):
        path = ROOT / 'build/oot-core/pack-test/TEST.OAP'
        if not path.exists():
            self.skipTest('run make oot-actor-pack-test for SH-2 fixture')
        data = path.read_bytes()
        core_crc, = struct.unpack_from('>I', data, 12)
        h = packs.validate(data, core_crc)
        self.assertEqual((h['actor_count'], h['effect_count'], h['ctor_count']), (0, 0, 1))
        self.assertEqual(h['flags'], 1)
        elf = packs.Elf32(path.with_suffix('.elf'))
        self.assertGreaterEqual(elf.value('_oot_pack_ctor_result'), h['link_base'] + h['bss_offset'])
        report = json.loads(path.with_suffix('.json').read_text())
        self.assertEqual(report['total'] + report['free'], 0x40000)

    @unittest.skipUnless(sys.platform.startswith('linux'), 'SH-2 compilation uses Linux only')
    def test_helper_mutable_and_unresolved_state_rejected(self):
        compiler = ROOT.parents[1] / 'sh-elf-9.3-linux/bin/sh-elf-g++'
        if not compiler.exists():
            self.skipTest('Linux sh-elf 9.3 compiler unavailable')
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            for name, body, allowed in [
                ('plain', 'return x*3;', True),
                ('private', 'static int state; return x + ++state;', False),
                ('external', 'extern int state; return x + state;', False),
            ]:
                cpp, obj = tmp / (name + '.cpp'), tmp / (name + '.o')
                cpp.write_text('extern "C" int helper(int x) {' + body + '}')
                subprocess.run([str(compiler), '-m2', '-Os', '-fdata-sections', '-ffunction-sections',
                                '-c', str(cpp), '-o', str(obj)], check=True)
                if allowed:
                    packs.audit_helper(obj, {'_helper'})
                else:
                    with self.assertRaisesRegex(ValueError, 'mutable|not resolved'):
                        packs.audit_helper(obj, {'_helper'})
                with self.assertRaisesRegex(ValueError, 'not allowed'):
                    packs.audit_helper(obj, set())

    @unittest.skipUnless(sys.platform.startswith('linux'), 'SH-2 tools use Linux only')
    def test_core_elf_and_binary_must_match(self):
        compiler = ROOT.parents[1] / 'sh-elf-9.3-linux/bin/sh-elf-g++'
        core = ROOT / 'build/oot-core/oot-core.elf'
        if not compiler.exists() or not core.exists():
            self.skipTest('built core/Linux tools unavailable')
        with tempfile.TemporaryDirectory() as directory:
            tmp = Path(directory)
            (tmp / 'wrong.bin').write_bytes(b'wrong resident core')
            args = SimpleNamespace(core=str(core), core_bin=str(tmp / 'wrong.bin'),
                                   objects=[], helper_object=[], allow_helper_symbol=[],
                                   output=str(tmp / 'TEST.OAP'), cxx=str(compiler), used_bytes=0,
                                   payload=[], test_pack=True)
            with self.assertRaisesRegex(ValueError, 'ELF/BIN mismatch'):
                packs.build(args)
            self.assertFalse((tmp / 'TEST.OAP').exists())

    @unittest.skipUnless(sys.platform.startswith('linux') and platform.machine() == 'x86_64',
                         'Linux host executable mapping; target builds are WSL only')
    def test_actual_registration_ctors_release_and_failed_scene_admission(self):
        source = (ROOT / 'oot-core/src/bridge_actor_pack.cpp').read_text()
        source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include'))
        program = r'''
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include "oot_actor_pack.h"
#include "oot_scene_blob.h"
#include "oot_core_host.h"
#define check(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
typedef uint8_t u8; typedef uint32_t u32;
struct Actor { unsigned int words[4]; };
struct ActorEntry { short words[8]; };
struct Vec3s { short x,y,z; };
struct Path { unsigned char count; Vec3s* points; };
struct CollisionPoly { short words[8]; };
struct WaterBox { short words[8]; };
struct SurfaceType { unsigned int words[2]; };
struct BgCamInfo { unsigned int words[2]; };
struct CollisionHeader {
    unsigned short numVertices, numPolygons, numWaterBoxes;
    Vec3s* vtxList; CollisionPoly* polyList; WaterBox* waterBoxes;
    SurfaceType* surfaceTypeList; BgCamInfo* bgCamList;
};
struct PlayState { unsigned int marker; };
typedef void (*ActorFunc)(void);
struct ActorProfile {
    unsigned int id, category, instanceSize;
    ActorFunc init, destroy, update, draw;
};
struct ActorOverlay { void *vramStart,*vramEnd,*loadedRamAddr; ActorProfile* profile; signed char numLoaded; };
struct EffectSsProfile { unsigned int type; ActorFunc init; };
struct EffectSsOverlay { void *vramStart,*vramEnd,*loadedRamAddr; EffectSsProfile* profile; };
#define ACTORCAT_MAX 12
#define ACTOR_ID_MAX 8
#define EFFECT_SS_TYPE_MAX 8
#define OOT_PACK_UNCACHED_ALIAS 0
ActorOverlay gActorOverlayTable[8];
EffectSsOverlay gEffectSsOverlayTable[8];
PlayState* gOotCorePlay;
extern "C" { char oot_core_text_start[1], oot_core_text_end[1]; }
const OotCoreHost* gOotCoreHost;
''' + source + r'''
static unsigned char valid_pack[224];
static unsigned char valid_ooc[sizeof(OotSceneBlob)];
static int mode, reads;
static int fake_read(const char* name, void* data, unsigned int bytes) {
    const void* source = NULL; int length=0;
    ++reads;
    if (!strcmp(name,"S1.OOC")) { source=valid_ooc; length=sizeof(valid_ooc); }
    if (!strcmp(name,"S1.OAP")) { source=valid_pack; length=sizeof(valid_pack); }
    if (mode==1 && !strcmp(name,"S1.OOC")) return 0;
    if (mode==2 && !strcmp(name,"S1.OAP") && data) return 12; /* short header/read */
    if (!data) return length;
    if (!source || bytes>(unsigned)length) return -1;
    memcpy(data,source,bytes); return bytes;
}
static void fill(unsigned char* base) {
    memset(base,0,256);
    OotActorPackHeader* h=(OotActorPackHeader*)base;
    *h={OOT_ACTOR_PACK_MAGIC,1,80,123,0x0276ff00,224,256,224,32,
        200,1,204,1,212,1,0,80,16,1,0};
    /* Native host ctor writes a marker into BSS. No decomp actor imported. */
    unsigned char op[]={0xc7,0x04,0x25,0,0,0,0,0x83,0,0,0,0xc3};
    uint32_t address=h->link_base+224; memcpy(op+3,&address,4); memcpy(base+80,op,sizeof(op));
    *(u32*)(base+200)=h->link_base+80;
    *(OotActorPackProfile*)(base+204)={2,h->link_base+128};
    *(OotActorPackProfile*)(base+212)={3,h->link_base+184};
    ActorProfile* actor=(ActorProfile*)(base+128);
    actor->id=2; actor->category=5; actor->instanceSize=sizeof(Actor);
    actor->init=(ActorFunc)(uintptr_t)(h->link_base+80);
    EffectSsProfile* effect=(EffectSsProfile*)(base+184);
    effect->type=3; effect->init=actor->init;
    h->crc=OotActorPack_Crc(base,h->file_bytes,1);
}
int main() {
    ((OotSceneBlob*)valid_ooc)->format=OOT_SCENE_BLOB_FORMAT;
    void* region=mmap((void*)0x02730000,0x40000,PROT_READ|PROT_WRITE|PROT_EXEC,
                     MAP_PRIVATE|MAP_ANONYMOUS|MAP_FIXED,-1,0);
    check(region==(void*)0x02730000);
    unsigned char* base=(unsigned char*)0x0276ff00;
    fill(base); memcpy(valid_pack,base,sizeof(valid_pack));
    memset(base+224,0xa5,32);
    check(OotCore_PackBind(base,224,123));
    check(*(u32*)(base+224)==0x83 && base[255]==0);
    check(gActorOverlayTable[2].profile && !gActorOverlayTable[2].vramStart);
    check(gEffectSsOverlayTable[3].profile && !gEffectSsOverlayTable[3].loadedRamAddr);
    check(!OotCore_PackBind(base,224,123)); /* double bind does not rerun ctor */
    PlayState play={}; gOotCorePlay=&play; check(!OotCore_PackRelease());
    gOotCorePlay=NULL; gActorOverlayTable[2].numLoaded=1; check(!OotCore_PackRelease());
    gActorOverlayTable[2].numLoaded=0; check(OotCore_PackRelease());
    check(!gActorOverlayTable[2].profile && !gEffectSsOverlayTable[3].profile);
    check(OotCore_PackRelease());
    fill(base); base[90]^=1; check(!OotCore_PackBind(base,224,123));
    check(!gActorOverlayTable[2].profile); /* failed new pack stays unpublished */
    fill(base); check(!OotCore_PackBind(base,224,122));
    fill(base); gActorOverlayTable[2].profile=(ActorProfile*)base;
    check(!OotCore_PackBind(base,224,123)); /* never replace resident profile */
    gActorOverlayTable[2].profile=NULL;
    fill(base); check(OotCore_PackBind(base,224,123)); check(OotCore_PackRelease());
    /* Actual loader: absent optional OOC, partial OAP, success, safe failure,
     * then a reloaded previous image. Callbacks never see a published partial. */
    OotCoreHost host={}; host.scene_file=fake_read; gOotCoreHost=&host;
    const void* const* objects=(const void* const*)1; unsigned count=99;
    mode=1; check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==0);
    check(!objects && !count);
    mode=2; check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    check(!objects && !count && !gActorOverlayTable[2].profile);
    mode=0; check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==1);
    check(objects && !count && gActorOverlayTable[2].profile && *(u32*)(base+224)==0x83);
    mode=2; check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    check(!objects && !gActorOverlayTable[2].profile && !gEffectSsOverlayTable[3].profile);
    mode=0; check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==1);
    check(OotCore_PackRelease());
    OotSceneBlob* malformed=(OotSceneBlob*)valid_ooc;
    malformed->format=0;
    check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    malformed->format=OOT_SCENE_BLOB_FORMAT;
    malformed->num_transition_layers=1;
    malformed->transitions=(OotSceneLayer*)0x02730001;
    check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    malformed->num_transition_layers=0; malformed->transitions=NULL;
    malformed->num_rooms=1; malformed->num_layers=0xffffffff;
    check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    check(!objects && !gActorOverlayTable[2].profile);
    memset(valid_ooc,0,sizeof(valid_ooc));
    malformed->format=OOT_SCENE_BLOB_FORMAT;
    malformed->num_objects=1; malformed->objects=(unsigned short*)0x02730001;
    check(OotCore_SceneLoad(1,"S1.OOC",123,&objects,&count)==-1);
    munmap(region,0x40000);
    return 0;
}
'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            cpp, exe = path / 'probe.cpp', path / 'probe'
            cpp.write_text(program)
            subprocess.run([shutil.which('g++') or 'g++', '-std=c++17', '-O2',
                            '-I' + str(ROOT / 'oot-core/include'), str(cpp), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
