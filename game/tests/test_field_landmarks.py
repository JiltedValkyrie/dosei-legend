"""Landmark retention must neither duplicate near geometry nor share fog CLUTs."""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_field_chunks as fc
import build_hybrid_scene as hybrid


def triangle(x, y, z, obj, index, transparent=False):
    v = lambda a, b: (a, y, b, 0, 0, 255, 255, 255, 255)
    return dict(vertices=[v(x, z), v(x + 2048, z), v(x, z + 2048)],
                object=obj, source_index=index, texture=None, lighting=False,
                prim=(255, 255, 255, 255), room='r', cull=False,
                transparent=transparent)


def fixture():
    sources = [triangle(0, 0, 0, 1, 0), triangle(0, 300, 0, 6, 312, True),
               triangle(0, 400, 0, 6, 310, True)]
    positions, records = [], []
    for source in sources:
        base = len(positions)
        positions += [v[:3] for v in source['vertices']]
        records.append(dict(indices=[base, base + 1, base + 2, base + 2],
                            source=[source['source_index']], object=source['object'],
                            tile=0, cull=False, mesh=source['transparent']))
    clut, pixels = hybrid.quantize([(255, 255, 255, 255)] * 256, 16, 16)
    tiles = {0: dict(width=16, height=16, clut=clut, pixels=pixels)}
    return positions, records, tiles, sources


class Landmarks(unittest.TestCase):
    def test_near_originals_removed_lod_ground_clean_and_always_resident(self):
        pieces, pool, _ = fc.build_pieces(*fixture(), {}, [],
            [('mountain', 6, (310, 312))])
        hero = [i for i, p in enumerate(pieces) if p['kind'] == fc.KIND_LANDMARK]
        self.assertEqual(len(hero), 1)
        p = pieces[hero[0]]
        self.assertEqual((p['near'], p['far'], p['flags']), (0, fc.FAR_INF, 1))
        self.assertEqual(len(p['faces']), 2)
        self.assertEqual(sum(len(p['faces']) for p in pieces if p['kind'] == fc.KIND_FULL), 1)
        for p in pieces:
            if p['kind'] in (fc.KIND_FULL, fc.KIND_FAR):
                self.assertTrue(all(v[1] == 0 for v in p['points']))
                self.assertTrue(all(pool.tiles[t]['policy'] == 0 for t in p['tiles']))
        for owl in (False, True):
            for point in ((0, 0), (-12000, -2000), (8000, 19000)):
                self.assertIn(hero[0], fc.resident(pieces, point, 0, owl))

    def test_palette_policy_isolated_and_smoke_mesh_preserved(self):
        pieces, pool, _ = fc.build_pieces(*fixture(), {}, [],
            [('mountain', 6, (310, 312))])
        p = next(p for p in pieces if p['kind'] == fc.KIND_LANDMARK)
        faces = {f['source'][0]: f for f in p['faces']}
        self.assertTrue(faces[310]['mesh'])
        self.assertFalse(faces[312]['mesh'])
        tile = pool.tiles[faces[312]['tile']]
        self.assertEqual((tile['width'], tile['height'], tile['policy']), (16, 16, 1))
        # Even identical colour/pixels must not reuse the terrain tile/CLUT.
        self.assertEqual(tile['pixels'], pool.tiles[0]['pixels'])
        self.assertEqual(tile['clut'], pool.tiles[0]['clut'])
        self.assertNotEqual(faces[312]['tile'], 0)
        plan = fc.sweep(pieces, pool, dict(tiles=[], polygons=0, vertices=0))
        _, _, _, rows = fc.unpack(fc.pack(pieces, pool, plan))
        self.assertEqual([r['flags'] for r in rows if r['kind'] == fc.KIND_LANDMARK], [1])

    def test_fail_closed_on_changed_source_or_mixed_group(self):
        with self.assertRaisesRegex(ValueError, 'not object'):
            fc.build_pieces(*fixture(), {}, [], [('mountain', 7, (312,))])
        args = list(fixture())
        args[1][1]['source'] = [0, 312]
        with self.assertRaisesRegex(ValueError, 'mixes landmark'):
            fc.build_pieces(*args, {}, [], [('mountain', 6, (312,))])
        args = list(fixture())
        args[1] = args[1][:1]
        with self.assertRaisesRegex(ValueError, 'originals missing'):
            fc.build_pieces(*args, {}, [], [('mountain', 6, (312,))])

    @unittest.skipUnless(hybrid.OOT_DEFAULT.is_dir(), 'extracted source unavailable')
    def test_actual_source_geometry_and_counts(self):
        faces = hybrid.load_faces(hybrid.OOT_DEFAULT, prefix='spot00')
        pool = fc.Pool()
        pieces, ids = fc.landmark_faces(faces, pool, fc.LANDMARKS)
        self.assertEqual(len(ids), 313)
        self.assertEqual([len(p['faces']) for p in pieces], [9, 4, 87, 85])
        self.assertEqual(len(pool.tiles), 182)
        self.assertEqual(sum(len(t['pixels']) + 32 for t in pool.tiles), 29120)
        for piece in pieces:
            for f in piece['faces']:
                self.assertEqual(f['mesh'], faces[f['source'][0]]['transparent']
                                 and not set(f['source']) <= fc.MOUNTAIN_BODY)
                self.assertTrue(all(v in [tuple(round(x) for x in point[:3])
                                         for i in f['source'] for point in faces[i]['vertices']]
                                    for v in f['points']))


if __name__ == '__main__':
    unittest.main()
