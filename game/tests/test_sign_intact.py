"""The real intact sign and its borrowed hot tables preserve source materials."""
import pathlib
import struct
import sys
import tempfile
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as graphics

sys.path.insert(0, str(ROOT / 'tools'))
import build_sign_intact as bake


class SignIntact(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_verified_source_bakes_small_complete_intact_mesh(self):
        oot = bake.link.OOT_DEFAULT
        roms = oot / 'baseroms/ntsc-1.2'
        if not list(roms.glob('*.z64')):
            self.skipTest('verified source ROM required')
        with tempfile.TemporaryDirectory() as temp:
            dest = pathlib.Path(temp) / 'SIGNALL.BIN'
            self.assertEqual(bake.build(oot, roms, dest), (14, 19))
            blob = dest.read_bytes()
            head = struct.unpack_from('>8I', blob)
            self.assertEqual(head[0], 0x4B465231)
            self.assertEqual(head[2:4], (14, 19))
            points = [struct.unpack_from('>3h', blob, head[4] + i * 6) for i in range(14)]
            self.assertEqual([(min(p[k] for p in points), max(p[k] for p in points))
                              for k in range(3)], [(-20, 20), (0, 60), (-3, 2)])
            used = set()
            for i in range(19):
                face = struct.unpack_from('>4H', blob, head[5] + i * 20)
                self.assertLess(max(face), 14)
                used.update(face)
            self.assertEqual(len(used), 14)
            # The 1 KiB target cache includes the mesh descriptor and every
            # native point, polygon and material, not only a vertex buffer.
            self.assertLessEqual(80 + 14 * 12 + 19 * (20 + 12), 1024)

    def test_hot_copy_refreshes_materials_and_rejects_undersized_storage(self):
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define MESHon 0x100u
typedef int32_t POINT[3];
typedef struct {int32_t norm[3];uint16_t Vertices[4];} POLYGON;
typedef struct {uint16_t flag,sort,texno,atrb,colno,gstb,dir;} ATTR;
typedef struct {POINT *pntbl;int nbPoint;POLYGON *pltbl;int nbPolygon;ATTR *attbl;} PDATA;
typedef struct actor_mesh {
    bool loaded;void *animation;POINT *points;POLYGON *polygons;ATTR *attributes;PDATA pdata;
} actor_mesh_t;
'''
        source += function(ROOT / 'src/cutscene_actor.c', 'actor_mesh_t *actor_mesh_cache_static(')
        source += function(ROOT / 'src/cutscene_actor.c', 'actor_mesh_t *actor_mesh_cache_fade(')
        source += r'''
int main(void) {
    POINT points[14];POLYGON faces[19];ATTR attrs[19];
    union {uint64_t align;unsigned char bytes[2048];} arena;
    actor_mesh_t mesh={0};mesh.loaded=true;mesh.points=points;mesh.polygons=faces;
    mesh.attributes=attrs;mesh.pdata.nbPoint=14;mesh.pdata.nbPolygon=19;
    for(unsigned i=0;i<14;++i)for(unsigned k=0;k<3;++k)points[i][k]=(i*3+k)*65536;
    for(unsigned i=0;i<19;++i) {
        faces[i].norm[0]=1;faces[i].norm[1]=2;faces[i].norm[2]=3;
        for(unsigned k=0;k<4;++k)faces[i].Vertices[k]=(i+k)%14;
        attrs[i]=(ATTR){1,2,i,4,i+20,6,7};
    }
    unsigned required=sizeof(actor_mesh_t)+sizeof(points)+sizeof(faces)+sizeof(attrs);
    memset(arena.bytes,0xa5,sizeof(arena));
    assert(!actor_mesh_cache_static(&mesh,arena.bytes,required-1));
    for(unsigned i=0;i<sizeof(arena);++i)assert(arena.bytes[i]==0xa5);
    assert(!actor_mesh_cache_static(&mesh,arena.bytes+1,2047));
    actor_mesh_t *hot=actor_mesh_cache_static(&mesh,arena.bytes,required);
    assert(hot && hot->loaded && !hot->animation);
    assert(hot->pdata.pntbl==hot->points && hot->pdata.nbPoint==14);
    assert(hot->pdata.pltbl==hot->polygons && hot->pdata.nbPolygon==19);
    assert(hot->pdata.attbl==hot->attributes);
    assert(!memcmp(hot->points,points,sizeof(points)));
    assert(!memcmp(hot->polygons,faces,sizeof(faces)));
    assert(!memcmp(hot->attributes,attrs,sizeof(attrs)));
    for(unsigned i=required;i<sizeof(arena);++i)assert(arena.bytes[i]==0xa5);
    union {uint64_t align;unsigned char bytes[1024];} fade_arena;
    unsigned fade_bytes=sizeof(actor_mesh_t)+sizeof(attrs);
    memset(fade_arena.bytes,0x5a,sizeof(fade_arena));
    assert(!actor_mesh_cache_fade(hot,fade_arena.bytes,fade_bytes-1));
    for(unsigned i=0;i<sizeof(fade_arena);++i)assert(fade_arena.bytes[i]==0x5a);
    assert(!actor_mesh_cache_fade(hot,fade_arena.bytes+1,fade_bytes));
    actor_mesh_t *fade=actor_mesh_cache_fade(hot,fade_arena.bytes,fade_bytes);
    assert(fade && fade->loaded && !fade->animation);
    assert(fade->points==hot->points && fade->polygons==hot->polygons);
    assert(fade->pdata.pntbl==hot->points && fade->pdata.pltbl==hot->polygons);
    assert(fade->attributes!=hot->attributes && fade->pdata.attbl==fade->attributes);
    for(unsigned i=0;i<19;++i) {
        ATTR expected=attrs[i];expected.atrb|=MESHon;
        assert(!memcmp(&fade->attributes[i],&expected,sizeof(expected)));
        assert(!memcmp(&hot->attributes[i],&attrs[i],sizeof(expected)));
    }
    for(unsigned i=fade_bytes;i<sizeof(fade_arena);++i)assert(fade_arena.bytes[i]==0x5a);
    for(unsigned i=0;i<19;++i){attrs[i].texno+=100;attrs[i].colno+=500;}
    assert(actor_mesh_cache_static(&mesh,arena.bytes,required)==hot);
    assert(!memcmp(hot->attributes,attrs,sizeof(attrs)));
    assert(actor_mesh_cache_fade(hot,fade_arena.bytes,fade_bytes)==fade);
    for(unsigned i=0;i<19;++i) {
        assert(fade->attributes[i].texno==attrs[i].texno);
        assert(fade->attributes[i].colno==attrs[i].colno);
    }
    mesh.animation=&mesh;assert(!actor_mesh_cache_static(&mesh,arena.bytes,required));
    mesh.animation=0;mesh.pdata.nbPoint=65536;
    assert(!actor_mesh_cache_static(&mesh,arena.bytes,required));
    return 0;
}
'''
        self.run_c(source)
