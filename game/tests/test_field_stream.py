"""Hyrule Field streaming: KRM2 bake (pieces, sweep, pack) and runtime selection."""
import ctypes
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_field_chunks as fc
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
CELL = 1 << fc.CELL_SHIFT


def tile(seed):
    return dict(width=16, height=16, clut=(0,)+(0x8000+seed,)*15, pixels=bytes([seed])*128)


def source_quad(x0, z0, size, y=0, obj=1):
    v = lambda x, z: (x, y, z, 0, 0, 255, 255, 255, 255)
    a, b, c, d = v(x0, z0), v(x0+size, z0), v(x0+size, z0+size), v(x0, z0+size)
    base = dict(texture=None, lighting=False, prim=(255, 255, 255, 255), room='r', object=obj,
                cull=False, transparent=False)
    return [dict(base, vertices=[a, b, c]), dict(base, vertices=[a, c, d])]


def field(cells=3, lod=None):
    """A strip of `cells` cells, one textured quad each, plus optional LOD object 9."""
    positions, records, tiles, faces = [], [], {}, []
    for i in range(cells):
        x0 = i * CELL
        ids = []
        for p in ((x0, 0, 0), (x0+CELL, 0, 0), (x0+CELL, 0, CELL), (x0, 0, CELL)):
            if p not in positions: positions.append(p)
            ids.append(positions.index(p))
        tiles[i] = dict(tile(i+1), index=i)
        records.append(dict(indices=ids, object=1, tile=i, cull=False, mesh=False))
        faces += source_quad(x0, 0, CELL)
    lods, near = {}, []
    if lod:
        ids = []
        for p in ((10, 5, 10), (200, 5, 10), (200, 5, 200), (10, 5, 200)):
            positions.append(p); ids.append(len(positions)-1)
        tiles[cells] = dict(tile(99), index=cells)
        records.append(dict(indices=ids, object=9, tile=cells, cull=False, mesh=False))
        lods = {'9': dict(lod0_distance=lod, cull_distance=9000, lod0_faces=2)}
        near = [dict(f, object=fc.LOD0_OBJECT_BASE+9, lod0_of=9) for f in source_quad(10, 10, 190, 6, 9)]
    return fc.build_pieces(positions, records, tiles, faces, lods, near)


class Bake(unittest.TestCase):
    def test_cells_get_full_and_far_pieces(self):
        pieces, pool, origin = field()
        kinds = [p['kind'] for p in pieces]
        self.assertEqual(kinds.count(fc.KIND_FULL), 3)
        self.assertEqual(kinds.count(fc.KIND_FAR), 3)
        self.assertEqual(origin, (0, 0))
        far = [p for p in pieces if p['kind'] == fc.KIND_FAR]
        self.assertTrue(all(len(p['faces']) == fc.LOD2_GRID**2 for p in far))
        # Full pieces cover their whole cell, so bands meet at the boundary.
        full = pieces[0]
        self.assertEqual((full['bounds'][0], full['bounds'][3]), (0, CELL))

    def test_lod_object_pieces_and_group_exclusive(self):
        pieces, pool, _ = field(lod=1500)
        lod = [p for p in pieces if p['kind'] in (fc.KIND_LOD0, fc.KIND_LOD1)]
        self.assertEqual(sorted(p['kind'] for p in lod), [fc.KIND_LOD1, fc.KIND_LOD0])
        self.assertEqual(len({p['group'] for p in lod}), 1)
        lod1 = next(p for p in lod if p['kind'] == fc.KIND_LOD1)
        self.assertEqual((lod1['near'], lod1['far']), (1500, 9000))

    def test_sweep_counts_exclusive_member_max_and_owl_mode(self):
        pieces, pool, _ = field(lod=1500)
        actor = dict(tiles=[], polygons=0, vertices=0)
        plan = fc.sweep(pieces, pool, actor)
        self.assertFalse(plan['failures'])
        # Owl mode never keeps the close-up resident.
        for x, z in ((0, 0), (100, 100)):
            ids = fc.resident(pieces, (x, z), fc.SWEEP_WIDEN, owl=True)
            self.assertNotIn(fc.KIND_LOD0, [pieces[i]['kind'] for i in ids])
        heavy = dict(tiles=[], polygons=fc.MAX_TABLE_POLYGONS, vertices=0)
        self.assertTrue(any('table budget' in f for f in fc.sweep(pieces, pool, heavy)['failures']))

    def test_pack_round_trip_offsets_indices_and_tiles(self):
        pieces, pool, _ = field(lod=1500)
        plan = fc.sweep(pieces, pool, dict(tiles=[], polygons=0, vertices=0))
        blob = fc.pack(pieces, pool, plan)
        header, buckets, tiles, rows = fc.unpack(blob)
        self.assertEqual(header[2], len(pieces))
        self.assertEqual(header[13], len({p['group'] for p in pieces}))
        self.assertEqual(sum(n for _, n in buckets), header[6])
        pool_offset = header[12]
        for row in rows:
            self.assertEqual(row['offset'] % 4, 0)
            at = row['offset']
            polys = at + row['points']*12
            attrs = polys + row['polys']*20
            refs_at = attrs + row['polys']*12
            refs = struct.unpack_from('>%dH' % row['refs'], blob, refs_at)
            self.assertLessEqual(refs_at + 2*row['refs'], pool_offset)
            for k in range(row['polys']):
                idx = struct.unpack_from('>4H', blob, polys + k*20 + 12)
                self.assertTrue(all(i < row['points'] for i in idx))
                texno = struct.unpack_from('>H', blob, attrs + k*12 + 2)[0]
                self.assertIn(texno, refs)
        for t in tiles:
            self.assertLessEqual(t[2] + t[3], header[4])
            self.assertLessEqual(t[3], buckets[t[4]][0])

    def test_distance_is_xz_to_bounds(self):
        b = (0, -5, 0, 100, 5, 100)
        self.assertEqual(fc.xz_distance((50, 50), b), 0)
        self.assertEqual(fc.xz_distance((103, 104), b), 5)


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class Runtime(unittest.TestCase):
    SRC = r'''
#include "field_stream.h"
#define X __declspec(dllexport)
static field_piece_t p[4];
static uint16_t cur[2] = {FIELD_NONE, FIELD_NONE}, want[2];
X void setup(void) {
    int i;
    for (i = 0; i < 4; ++i) {
        p[i].bounds[0] = 0; p[i].bounds[2] = 0; p[i].bounds[3] = 100; p[i].bounds[5] = 100;
    }
    p[0].near = 0; p[0].far = 1000; p[0].kind = FIELD_KIND_FULL; p[0].group = 0;
    p[1].near = 1000; p[1].far = FIELD_FAR_INF; p[1].kind = FIELD_KIND_FAR; p[1].group = 0;
    p[2].near = 0; p[2].far = 500; p[2].kind = FIELD_KIND_LOD0; p[2].group = 1;
    p[3].near = 500; p[3].far = 9000; p[3].kind = FIELD_KIND_LOD1; p[3].group = 1;
    cur[0] = cur[1] = FIELD_NONE;
}
X int step(int x, int owl) {
    int changed = field_choose(p, 4, cur, want, 2, x, 50, 200, owl);
    cur[0] = want[0]; cur[1] = want[1];
    return changed;
}
X int get(int g) { return cur[g] == FIELD_NONE ? -1 : cur[g]; }
static uint16_t stack[8];
static field_slots_t s;
X int slots_init(void) {
    field_bucket_t b[2] = {{128, 3}, {512, 2}};
    return field_slots_init(&s, b, 2, stack, 8);
}
X int alloc(int bucket) { unsigned v = field_slot_alloc(&s, bucket); return v == FIELD_NONE ? -1 : (int)v; }
X int release(int bucket, int slot) { return field_slot_free(&s, bucket, slot); }
'''

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name)/'field.dll'
        env = dict(os.environ); env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Werror', '-I', str(ROOT/'src'),
                        '-x', 'c', '-', '-o', str(out)], input=cls.SRC, text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(out))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_bands_with_hysteresis(self):
        lib = self.lib; lib.setup()
        self.assertEqual(lib.step(50, 0), 1)
        self.assertEqual((lib.get(0), lib.get(1)), (0, 2))       # inside: full + LOD0
        lib.step(100 + 1100, 0)                                   # 1100 away: inside widened full band
        self.assertEqual(lib.get(0), 0)
        lib.step(100 + 1250, 0)                                   # past 1000+200: swap to far
        self.assertEqual(lib.get(0), 1)
        lib.step(100 + 900, 0)                                    # back inside but within widen of far
        self.assertEqual(lib.get(0), 1)
        lib.step(100 + 700, 0)                                    # below 1000-200: full again
        self.assertEqual(lib.get(0), 0)
        self.assertEqual(lib.step(100 + 700, 0), 0)               # unchanged: no swap request

    def test_lod_pair_and_owl_mode(self):
        lib = self.lib; lib.setup()
        lib.step(50, 0)
        self.assertEqual(lib.get(1), 2)
        lib.step(50, 1)                                           # owl: LOD0 refused, LOD1 near too
        self.assertEqual(lib.get(1), 3)
        lib.step(50, 0)                                           # owl gone, Link close: LOD0 back
        self.assertEqual(lib.get(1), 2)
        lib.setup(); lib.step(100 + 9300, 0)                      # past cull: nothing for the object
        self.assertEqual(lib.get(1), -1)

    def test_slots_per_bucket(self):
        lib = self.lib
        self.assertEqual(lib.slots_init(), 1)
        self.assertEqual([lib.alloc(0) for _ in range(4)], [0, 1, 2, -1])
        self.assertEqual([lib.alloc(1) for _ in range(3)], [3, 4, -1])
        self.assertEqual(lib.release(0, 4), 0)                    # wrong bucket refused
        self.assertEqual(lib.release(0, 1), 1)
        self.assertEqual(lib.alloc(0), 1)
        self.assertEqual(lib.alloc(5), -1)


if __name__ == '__main__': unittest.main()
