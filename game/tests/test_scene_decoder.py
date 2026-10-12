"""Source room discovery and explicit empty-stage banks, without invented mesh."""
import collections
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT.parent / 'shared/tools')]
import build_all_scenes as all_scenes
import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_kokiri_scene as source
import test_graphics_backend as graphics

OOT = Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')


class SourceSceneDecoder(unittest.TestCase):
    def test_retail_scene_discovery_respects_source_debug_condition(self):
        all_rows = all_scenes.scene_list(OOT)
        retail = all_scenes.scene_list(OOT, retail_only=True)
        self.assertEqual((len(retail), len(all_rows)), (101, 110))
        self.assertEqual({r['prefix'] for r in all_rows} - {r['prefix'] for r in retail},
                         {'test01', 'besitu', 'depth_test', 'syotes', 'syotes2',
                          'sutaru', 'hairal_niwa2', 'sasatest', 'testroom'})
        self.assertTrue(all(r['id'] < 0x65 for r in retail))

    def test_room_word_in_scene_prefix_does_not_decode_scene_as_room(self):
        # A real F3DEX2 triangle and RoomShapeNormal. The scene has no room
        # shape command: parsing it as a room is the former moribossroom bug.
        room = bytearray(0xB0)
        struct.pack_into('>4I', room, 0, 0x0A000000, 0x03000020, 0x14000000, 0)
        struct.pack_into('>BB2xII', room, 0x20, 0, 1, 0x03000030, 0x03000038)
        struct.pack_into('>2I', room, 0x30, 0x03000040, 0)
        struct.pack_into('>6I', room, 0x40, 0x01003006, 0x03000070,
                         0x05000204, 0, 0xDF000000, 0)
        for i, p in enumerate(((0, 0, 0), (32, 0, 0), (0, 0, 32))):
            struct.pack_into('>3hH2h4B', room, 0x70 + i * 16, *p, 0, 0, 0, 255, 255, 255, 255)
        segments = {'moribossroom_scene': bytes.fromhex('1400000000000000'),
                    'moribossroom_room_0': bytes(room), 'moribossroom_room_1': bytes(room)}
        with mock.patch.object(source, 'extract', return_value=segments):
            faces = hybrid.load_faces(Path('.'), prefix='moribossroom')
        self.assertEqual([f['room'] for f in faces], ['moribossroom_room_0', 'moribossroom_room_1'])
        self.assertEqual([tuple(v[:3]) for v in faces[0]['vertices']],
                         [(0, 0, 0), (32, 0, 0), (0, 0, 32)])

    def test_cutscene_stage_source_has_no_static_faces_but_keeps_collision(self):
        segments = source.extract(OOT, prefix='hiral_demo')
        self.assertEqual(hybrid.load_faces(OOT, prefix='hiral_demo'), [])
        self.assertEqual(len(source.collision_data(segments['hiral_demo_scene'])['polys']), 2)
        room = segments['hiral_demo_room_0']
        shape = int.from_bytes(room[0x2C:0x30], 'big') & 0xFFFFFF
        entries = int.from_bytes(room[shape + 4:shape + 8], 'big') & 0xFFFFFF
        opaque, translucent = struct.unpack_from('>2I', room, entries)
        self.assertEqual(opaque, 0)
        self.assertEqual(room[translucent & 0xFFFFFF:(translucent & 0xFFFFFF) + 8],
                         bytes.fromhex('DF00000000000000'))

    def test_source_empty_bank_is_explicit_and_has_no_fake_floor(self):
        mesh, pixels, bounds = rooms.pack_room([], [], collections.OrderedDict(), [],
                                              lambda *args: None, source_empty=True)
        self.assertEqual(struct.unpack('>8I', mesh), (0x4B524D31, 0, 0, 0, 0, 0, 0, 1))
        self.assertEqual((pixels, bounds), (b'', []))
        with self.assertRaisesRegex(ValueError, 'no geometry'):
            rooms.pack_room([(0, 0, 0)], [], {}, [], lambda *args: None, source_empty=True)

    def test_only_source_empty_cutscene_stage_gets_empty_converter_output(self):
        actor = dict(tiles=[], polygons=0, vertices=0)
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            _, vertices, faces, tiles = hybrid.convert(OOT, None, actor, out,
                prefix='hiral_demo', room='hiral_demo_room_0', layout={})
            self.assertEqual((vertices, faces, tiles), ([], [], {}))
            self.assertTrue(json.loads((out / 'texture_manifest.json').read_text())['source_empty'])
            with mock.patch.object(hybrid, 'load_faces', return_value=[]):
                with self.assertRaisesRegex(ValueError, 'unverified'):
                    hybrid.convert(OOT, None, actor, out, prefix='ddan', room='ddan_room_0', layout={})


class EmptyRoomRuntime(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_loader_replaces_previous_geometry_and_rejects_inconsistent_empty_bank(self):
        path = ROOT / 'src/kokiri_sgl.c'
        loader = graphics.function(path, 'static bool __attribute__((optimize("Os"))) room_load_bank(unsigned int scene, unsigned int room)\n{')
        self.run_c(r'''
#include <stdbool.h>
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int POINT[3]; typedef struct { int a[5]; } POLYGON;
typedef struct { int a[3]; } ATTR; typedef struct { int a[3]; } kokiri_tile;
typedef struct { int a[6]; } kokiri_object;
typedef struct { unsigned lod0_object,lod1_object,extra[2]; } mesh_lod_t;
typedef struct { int unused; } jo_file;
typedef struct { POINT *pntbl; int nbPoint; POLYGON *pltbl; int nbPolygon; ATTR *attbl; } PDATA;
static POINT points[100]; static POLYGON polygons[100]; static ATTR attrs[100];
static PDATA kokiri_pdata={points,0,polygons,0,attrs};
static kokiri_tile kokiri_tiles[100]; static unsigned short kokiri_cluts[100][16];
static unsigned char kokiri_objects[100],forest_mesh[100],tile_fog[100];
static kokiri_object kokiri_bounds[100]; static mesh_lod_t lod_buffer[100],*forest_lods;
static unsigned forest_lod_count,forest_vertex_count,forest_polygon_count,forest_tile_count,forest_object_count;
static unsigned resident_bytes=128,resident_sprites=2,vram_used,sprite_next,forest_sprite_base;
static unsigned actor_vram_base,actor_sprite_base,actor_bank_generation;
static int forest_room,requested_room,forest_far_current;static unsigned short forest_scene;
static bool field_active,forest_prepared=true;
static struct {void *mesh,*pixels;int mesh_bytes,pixel_bytes;} opening_cache[10];
static unsigned bank[100],bank_bytes;
#define SCENE_SPOT00 10
#define STORY_BANK_NAVI 1024
#define STORY_BANK_BASE 1024
#define ASSET_ID_LIMIT 36
#define KOKIRI_FIELD_SCENE 1025
#define CUTSCENE_TEXTURE_BASE 100000
#define GAME_TEXTURE_BASE 100000
#define KOKIRI_VERTEX_COUNT 100
#define KOKIRI_POLYGON_COUNT 100
#define KOKIRI_TILE_COUNT 100
#define KOKIRI_PIXEL_BYTES 1000
#define KOKIRI_OBJECT_COUNT 100
#define MESH_LOD_MAX 100
#define MESH_LOD_NONE 255
#define RAM_CART_MESH_LOD_OFFSET 0
#define RAM_CART_MESH_LOD_BYTES sizeof(lod_buffer)
#define JO_MAX_SPRITE 2400
#define FIELD_FAR 4000
#define FOREST_FAR_DEFAULT 2000
static void field_stream_free(void) {assert(0);}
static bool field_stream_load(unsigned a,unsigned b) {assert(0);return false;}
static bool kokiri_bank_allocate(void) {return true;}
static bool bank_allocate(void) {return kokiri_bank_allocate();}
static void slCashPurge(void) {}
static bool asset_scene_name(char *name,unsigned a,int b,const char*c) {strcpy(name,"ROOM.MSH");return true;}
static void asset_loading(const char *name) {} static void asset_loading_done(void) {}
static void *ram_cart_load_scratch(const char *name,int *bytes) {*bytes=bank_bytes;return bank;}
static void *ram_cart_fixed(unsigned a,unsigned b) {return lod_buffer;}
static int jo_fs_read_next_bytes(jo_file *f,char *p,unsigned n) {assert(0);return 0;}
static void jo_core_error(const char *f,...) {assert(0);}
static void relocate_resident(unsigned base) {}
static bool mesh_load(const char *n,unsigned b,kokiri_tile*t,unsigned c,
 const unsigned short(*clut)[16],PDATA*p,unsigned polys,const void *cache) {assert(0);return false;}
static unsigned char forest_face_flags(unsigned n) {return 0;}
static void forest_fog_init(void) {}
''' + graphics.function(path, 'static bool room_read(') + '\n' +
            graphics.function(path, 'static bool room_geometry_valid(') + '\n' + loader + r'''
static void flat_bank(void) {
 memset(bank,0,sizeof bank); bank[0]=0x4b524d31;bank[1]=4;bank[2]=1;bank[5]=1;bank_bytes=140;
}
int main(void) {
 flat_bank(); assert(room_load_bank(22,0));
 assert(forest_vertex_count==4 && forest_polygon_count==1 && forest_object_count==1);
 assert(kokiri_pdata.nbPolygon==1);
 memset(bank,0,sizeof bank);bank[0]=0x4b524d31;bank[7]=1;bank_bytes=32;forest_prepared=true;
 assert(room_load_bank(23,0));
 assert(!forest_vertex_count && !forest_polygon_count && !forest_tile_count && !forest_object_count);
 assert(!kokiri_pdata.nbPoint && !kokiri_pdata.nbPolygon && !forest_lod_count && !forest_prepared);
 assert(forest_scene==23 && actor_vram_base==resident_bytes && actor_sprite_base==resident_sprites);
 flat_bank();assert(room_load_bank(22,0));
 for(unsigned field=1;field<=6;++field) {
   memset(bank,0,sizeof bank);bank[0]=0x4b524d31;bank[7]=1;bank[field]=1;bank_bytes=32;
   assert(!room_load_bank(23,0)); assert(kokiri_pdata.nbPolygon==1 && forest_scene==22);
 }
 memset(bank,0,sizeof bank);bank[0]=0x4b524d31;bank_bytes=32;
 assert(!room_load_bank(23,0)); bank[7]=2;assert(!room_load_bank(23,0));
 bank[7]=1;bank_bytes=36;assert(!room_load_bank(23,0));
 flat_bank();assert(room_load_bank(24,0)); assert(forest_polygon_count==1);
 return 0;
}
''')

    def test_empty_geometry_never_reaches_sgl(self):
        self.run_c(r'''
#include <assert.h>
typedef struct {unsigned dir,atrb,gstb;} ATTR;
typedef struct {int nbPolygon;ATTR *attbl;} PDATA;
static unsigned hit_filter,texture_base,hit_table_offset,kokiri_rejected,kokiri_accepted_mask,submitted,calls;
#define ECdis 0
#define SPdis 0
#define CL_Gouraud 0
#define No_Gouraud 0
#define FALSE 0
static int slPutPolygon(PDATA *p) {++calls;return 1;}
''' + graphics.function(ROOT / 'src/kokiri_sgl.c', 'static void         submit(') + r'''
int main(void) {
 PDATA empty={0,0};hit_filter=1;submit(&empty,1u);assert(!calls && !submitted);
 ATTR attrs[1]={{0}};PDATA flat={1,attrs};submit(&flat,1u);assert(calls==1 && submitted==1);
 return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
