"""Local Field square retopology: geometry, collision pairing, schema.

Offline checks only (tools/field_retopo.py). No SH-2, VDP1 or emulator
behaviour is exercised: a passing run does not show the floor looks right.
"""
import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

GAME = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
sys.path.insert(0, str(GAME.parent / 'shared/tools'))
sys.path.insert(0, str(GAME / "tests"))
OOT = pathlib.Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')
ROMS = OOT / 'baseroms/ntsc-1.2'
SCENE_C = OOT / 'extracted/ntsc-1.2/assets/scenes/overworld/spot00/spot00_scene.c'
SIZE = int(os.environ.get("RETOPO_SIZE", "184"))  # 256 = fallback candidate

import field_retopo as retopo  # noqa: E402
import layout_variants  # noqa: E402


@unittest.skipUnless(ROMS.is_dir(), 'OoT decomp and US 1.2 ROM required')
class FieldRetopoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_kokiri_scene as source
        cls.faces, cls.segments = retopo.load_source(OOT, ROMS)
        cls.collision = source.collision_data(cls.segments['spot00_scene'])
        cls.model = retopo.build(cls.faces, cls.collision, SIZE)
        cls.metrics = retopo.metrics(cls.model, cls.faces)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.game = pathlib.Path(cls.tmp.name)
        identity = retopo.store_bundle(retopo.bundle_files(cls.model, cls.faces, cls.collision), cls.game)
        cls.document = dict(layout_variants.empty(), patches={retopo.PATCH_NAME: dict(
            sha256=__import__('hashlib').sha256(cls.segments[retopo.ROOM]).hexdigest(),
            bundle=identity)})

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_patch_sources_match_collision_one_to_one(self):
        self.assertEqual(retopo.check_patch(self.faces, self.collision), (5, 0, 0))
        retopo.check_normal_convention(self.collision)

    def test_squares_are_exact_grid_cells_and_planar(self):
        m = self.metrics
        self.assertGreater(m['faces']['square'], {184: 100, 256: 40}.get(SIZE, 0))
        self.assertEqual(m['square_xz_error'], 0)
        self.assertLess(m['square_planarity'], 1.5)
        self.assertLess(m['square_side_ratio_pct'], 6)
        self.assertLess(m['max_plane_distance'], 1.0)

    def test_patch_covers_the_source_area_without_t_junctions(self):
        m = self.metrics
        self.assertEqual(m['t_junctions'], 0)
        self.assertLess(abs(m['area_new'] - m['area_old']) / m['area_old'], 1e-4)

    def test_no_degenerate_or_bow_tie_faces_after_rounding(self):
        for f in self.model['faces']:
            p = [retopo.ipos(v) for v in f['vertices']]
            self.assertEqual(len(set(p)), len(p))
            q = [(v[0], v[2]) for v in p]
            area = retopo.area_poly(q)
            self.assertGreater(abs(area), 1)
            if len(q) == 4:
                self.assertTrue(retopo.quad_ok(q if area > 0 else q[::-1], 20, 160), f)
        self.assertGreater(self.metrics['worst_triangle_angle_deg'], 2)

    def test_outline_points_are_shared_with_outside_fans(self):
        inside = {retopo.ipos(v) for f in self.model['faces'] for v in f['vertices']}
        for tris in self.model['fans'].values():
            ring = {retopo.ipos(v) for t in tris for v in t}
            self.assertTrue(ring & inside)
        for e, pts in self.model['result']['boundary']:
            if any(left['edge'] == e for left in self.model['left']):
                continue
            for _, pt in pts:
                self.assertIn(retopo.ipos(pt.pos), inside)

    def test_curb_and_wall_seams_are_closed(self):
        self.assertEqual(self.model['left'], [])
        fanned = set(self.model['fans'])
        # Curb riser 748/750 and walls 782/1039 share the outline with the fan.
        self.assertTrue({748, 750, 782, 1039} <= fanned, sorted(fanned))
        inside = {retopo.ipos(v) for f in self.model['faces'] for v in f['vertices']}
        self.assertIn((1472, 400, 4330), inside)  # curb lip T-vertex now shared

    def test_collision_replaces_slots_and_appends(self):
        patched, info = retopo.patch_collision(self.collision, 'spot00', self.document, self.game)
        tris = retopo.collision_triangles(self.model)
        polys = patched['polys']
        self.assertEqual(len(polys), len(self.collision['polys']) - len(retopo.PATCH) + len(tris))
        self.assertLessEqual(len(polys), 2321)
        slots = sorted(retopo.PATCH.values()) + list(range(len(self.collision['polys']), len(polys)))
        self.assertEqual([[tuple(v) for v in polys[i]['vertices']] for i in slots],
                         [[tuple(v) for v in t] for t in tris])
        for i, poly in enumerate(polys):
            if i in slots:
                self.assertEqual((poly['surface'], poly['ignore'], poly['conveyor']), (5, 0, 0))
                self.assertGreater(poly['normal'][1], 0)
            else:
                self.assertIs(poly, self.collision['polys'][i])

    def test_unpatched_document_changes_nothing(self):
        same, info = retopo.patch_collision(self.collision, 'spot00', layout_variants.empty(), self.game)
        self.assertIs(same, self.collision)
        self.assertIsNone(info)
        groups = [dict(source=[1])]
        self.assertIs(retopo.apply_patches(groups, self.faces, self.segments, layout_variants.empty()), groups)

    @unittest.skipUnless(SCENE_C.is_file(), 'extracted spot00 scene required')
    def test_oot_core_scene_collision_matches_sa_col(self):
        patched, _ = retopo.patch_collision(self.collision, 'spot00', self.document, self.game)
        with tempfile.TemporaryDirectory() as out:
            swaps = retopo.scenecol_patch(SCENE_C, out, self.document, self.game)
            self.assertEqual(len(swaps), 2)
            poly_text = (pathlib.Path(out) / 'spot00_retopo_PolyList.inc.c').read_text()
            vtx_text = (pathlib.Path(out) / 'spot00_retopo_VtxList.inc.c').read_text()
        verts = [tuple(int(m.group(k)) for k in (1, 2, 3)) for m in retopo.VTX_ENTRY.finditer(vtx_text)]
        blocks = list(retopo.POLY_ENTRY.finditer(poly_text))
        self.assertEqual(len(blocks), len(patched['polys']))
        new_slots = set(retopo.PATCH.values()) | set(range(len(self.collision['polys']), len(blocks)))
        for slot, (block, poly) in enumerate(zip(blocks, patched['polys'])):
            if slot in new_slots:
                # One quantization: OOC Q15 exactly, COL round(q15 / 2).
                literal = [float(x) for x in re.findall(r'COLPOLY_SNORMAL\(([-0-9.]+)\)', block.group(1))]
                q15 = [int(x * 32767) for x in literal]
                self.assertEqual(q15, retopo.plane_q15(poly['vertices'])[0])
                self.assertEqual(poly['normal'], [round(q / 2) for q in q15])
            ids = [int(x) for x in re.findall(r'COLPOLY_VTX\((\d+),', block.group(1))]
            self.assertEqual([verts[i] for i in ids], [tuple(v) for v in poly['vertices']])
            surface = int(re.search(r'(\d+), // type', block.group(1)).group(1))
            self.assertEqual(surface, poly['surface'])

    def test_layout_schema_accepts_patch_and_rejects_bad_keys(self):
        layout_variants.validate(self.document)
        bad = json.loads(json.dumps(self.document))
        bad['patches'] = {'spot04_room_0/retopo/x': next(iter(self.document['patches'].values()))}
        with self.assertRaises(ValueError):
            layout_variants.validate(bad)
        bad['patches'] = {retopo.PATCH_NAME: dict(sha256='0' * 64)}
        with self.assertRaises(ValueError):
            layout_variants.validate(bad)
        for name in layout_variants.names():
            layout_variants.load(name)

    def test_pairing_check_refuses_mixed_bundles(self):
        with tempfile.TemporaryDirectory() as game:
            retopo.record('stm', self.document, game=game)
            retopo.record('col', layout_variants.empty(), game=game)
            with self.assertRaises(SystemExit):
                retopo.check_pairing(('stm', 'col'), game=game)
            retopo.record('col', self.document, game=game)
            retopo.check_pairing(('stm', 'col'), game=game)


GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
COLLISION_C = GAME.parent / 'shared/lib/collision/kokiri_collision.c'


@unittest.skipUnless(ROMS.is_dir() and GCC.is_file() and COLLISION_C.is_file(),
                     'ROM, collision source and mingw gcc required')
class FieldRetopoFloorTest(unittest.TestCase):
    """The runtime C collision finds the same floor before and after."""

    @classmethod
    def setUpClass(cls):
        import ctypes as C
        import subprocess
        import build_kokiri_scene as source
        import build_scene_table as table
        import test_player_bg as bg
        cls.C, cls.bg = C, bg
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll = pathlib.Path(cls.tmp.name) / 'collision.dll'
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I' + str(COLLISION_C.parent), str(COLLISION_C),
                        '-o', str(dll), '-lm'], check=True, env=env)
        cls.lib = C.CDLL(str(dll))
        cls.lib.bg_mesh_bytes.argtypes = [C.c_char_p, C.c_uint32]
        cls.lib.bg_mesh_bytes.restype = C.c_uint32
        cls.lib.bg_mesh_decode.argtypes = [C.c_char_p, C.c_uint32, C.c_void_p, C.c_uint32,
                                           C.POINTER(bg.Mesh)]
        cls.lib.bg_scene_set.argtypes = [C.POINTER(bg.Mesh)]
        cls.lib.bg_floor.argtypes = [C.POINTER(bg.Vec), C.c_uint32, C.POINTER(bg.Hit)]
        cls.lib.bg_floor.restype = C.c_int32
        faces, segments = retopo.load_source(OOT, ROMS)
        collision = source.collision_data(segments['spot00_scene'])
        model = retopo.build(faces, collision, SIZE)
        cls.game = pathlib.Path(cls.tmp.name)
        identity = retopo.store_bundle(retopo.bundle_files(model, faces, collision), cls.game)
        document = dict(layout_variants.empty(), patches={retopo.PATCH_NAME: dict(
            sha256=__import__('hashlib').sha256(segments[retopo.ROOM]).hexdigest(), bundle=identity)})
        patched, _ = retopo.patch_collision(collision, 'spot00', document, cls.game)
        cls.collision = collision
        cls.meshes, cls.stores = [], []
        for data in (collision, patched):
            blob = table.collision_file(data)
            size = cls.lib.bg_mesh_bytes(blob, len(blob))
            store = C.create_string_buffer(size)
            mesh = bg.Mesh()
            assert cls.lib.bg_mesh_decode(blob, len(blob), store, size, C.byref(mesh))
            cls.meshes.append(mesh)
            cls.stores.append((blob, store))
        pts = [retopo.ipos(v) for s in retopo.PATCH for v in faces[s]['vertices']]
        cls.box = (min(p[0] for p in pts) - 200, max(p[0] for p in pts) + 200,
                   min(p[2] for p in pts) - 200, max(p[2] for p in pts) + 200)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def floor(self, mesh, x, z):
        C, bg = self.C, self.bg
        self.lib.bg_scene_set(C.byref(mesh))
        hit = bg.Hit()
        y = self.lib.bg_floor(C.byref(bg.Vec(x, 2000, z)), 0, C.byref(hit))
        return y, (hit.data0, hit.data1, hit.ignore, hit.conveyor)

    def overlay(self, x, z, y, word):
        """An original polygon with this surface word within 2 units at x,z."""
        for poly in self.collision['polys']:
            v = poly['vertices']
            w = __import__('build_hybrid_scene').barycentric((x, 0, z), v, axes=(0, 2))
            if w is None or min(w) < -1e-6:
                continue
            h = sum(wi * p[1] for wi, p in zip(w, v))
            if abs(h - y) <= 2 and tuple(self.collision['surfaces'][poly['surface']]) == word[:2]:
                return True
        return False

    def test_floor_height_and_surface_unchanged_over_patch(self):
        """Same height everywhere; a surface may only flip to a coplanar
        overlay already within 2 units (road decal over grass: ties decided
        by sub-unit rounding of the new integer vertices)."""
        x0, x1, z0, z1 = self.box
        checked, flips = 0, []
        for x in range(x0, x1, 37):
            for z in range(z0, z1, 37):
                y0, s0 = self.floor(self.meshes[0], x, z)
                y1, s1 = self.floor(self.meshes[1], x, z)
                if y0 < -30000:
                    continue
                checked += 1
                self.assertGreater(y1, -30000, ('floor lost', x, z))
                self.assertLessEqual(abs(y1 - y0), 2, ('height', x, z, y0, y1))
                if s1 != s0:
                    self.assertTrue(self.overlay(x, z, y0, s1), ('surface', x, z, s0, s1))
                    flips.append((x, z))
        self.assertGreater(checked, 5000)
        # Recorded in FIELD_SQUARE_RETOPO_PLAN.md; fail if it grows.
        self.assertLessEqual(len(flips) / checked, .02, (len(flips), checked))
        print('floor sweep: %d points, %d overlay ties flipped' % (checked, len(flips)))

if __name__ == '__main__':
    unittest.main()
