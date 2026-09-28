"""World-collision contract (DEMO_PLAN M1): KBG2 files, surface bits, queries.

Drives the real shared/lib/collision/kokiri_collision.c through ctypes against
the real Kokiri Forest S1.COL and the real Obj_Oshihiki push-block mesh
(PUSHBLK.COL, gPushBlockCol), plus synthetic walls where exact numbers matter.
"""

import ctypes
import os
import pathlib
import struct
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'shared/lib/collision/kokiri_collision.c'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
FOREST = ROOT / 'build/cd/S1.COL'
HOUSE = ROOT / 'build/cd/S0.COL'
BLOCK = ROOT / 'build/generated/PUSHBLK.COL'

BG_SCENE, BG_NONE, BG_Y_MIN = 50, 0xFF, -32000
BG_IGNORE_ENTITY = 2
BG_CHECK_WALL, BG_CHECK_FLOOR, BG_CHECK_CEILING, BG_CHECK_ALL = 1, 2, 4, 7
BG_DYNA_POS, BG_DYNA_ROT_Y = 1, 2
# D_80119D90, z_bgcheck.c
WALL_FLAGS = (0, 0x01, 0x03, 0x05, 0x08, 0x10, 0x20, 0x40)


class Vec(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int32), ('y', ctypes.c_int32), ('z', ctypes.c_int32)]


class Hit(ctypes.Structure):
    _fields_ = [('normal', ctypes.c_int16 * 3), ('poly', ctypes.c_uint16),
                ('bg_id', ctypes.c_uint8), ('ignore', ctypes.c_uint8),
                ('conveyor', ctypes.c_uint8), ('data0', ctypes.c_uint32),
                ('data1', ctypes.c_uint32)]

    def wall_type(self):
        return self.data0 >> 21 & 0x1F

    def bgcam(self):
        return self.data0 & 0xFF

    def exit(self):
        return self.data0 >> 8 & 0x1F


class Triangle(ctypes.Structure):
    _fields_ = [('vertex', (ctypes.c_int16 * 3) * 3), ('normal', ctypes.c_int16 * 3),
                ('minimum', ctypes.c_int16 * 3), ('maximum', ctypes.c_int16 * 3)]


def triangle(vertices, normal):
    t = Triangle()
    for i, v in enumerate(vertices):
        t.vertex[i][:] = v
    t.normal[:] = normal
    t.minimum[:] = tuple(min(v[k] for v in vertices) for k in range(3))
    t.maximum[:] = tuple(max(v[k] for v in vertices) for k in range(3))
    return t


def parse_kbg2(data):
    """Python reading of the same file, independent of the C decoder."""
    assert data[:4] == b'KBG2'
    tris, surfaces, water, cams, vectors, _ = struct.unpack_from('>6H', data, 4)
    polys = [struct.unpack_from('>18h', data, 16 + 36 * i) for i in range(tris)]
    o = 16 + 36 * tris
    info = struct.unpack_from('>%dH' % tris, data, o)
    o += (tris * 2 + 3) & ~3
    surf = [struct.unpack_from('>2I', data, o + 8 * i) for i in range(surfaces)]
    o += 8 * surfaces
    boxes = [struct.unpack_from('>5h2xI', data, o + 16 * i) for i in range(water)]
    return polys, info, surf, boxes, cams


class Mesh(ctypes.Structure):
    """Opaque storage for bg_mesh_t (13 pointer/count fields)."""
    _fields_ = [('raw', ctypes.c_uint8 * 128)]


@unittest.skipUnless(SOURCE.is_file() and GCC.is_file(), 'collision source and mingw gcc required')
class BgCheckContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        library = pathlib.Path(cls.tmp.name) / 'bgcheck.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
                        '-o', str(library), str(SOURCE)], check=True, env=env)
        lib = cls.lib = ctypes.CDLL(str(library))
        P = ctypes.POINTER
        lib.bg_mesh_bytes.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        lib.bg_mesh_bytes.restype = ctypes.c_uint32
        lib.bg_mesh_decode.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p,
                                       ctypes.c_uint32, P(Mesh)]
        lib.bg_mesh_decode.restype = ctypes.c_bool
        lib.bg_scene_set.argtypes = [P(Mesh)]
        lib.kokiri_collision_init.argtypes = [P(Triangle), ctypes.c_uint32]
        lib.kokiri_collision_index.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.kokiri_collision_index.restype = ctypes.c_bool
        lib.kokiri_collision_floor.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32,
                                               P(ctypes.c_int32)]
        lib.kokiri_collision_floor.restype = ctypes.c_bool
        lib.bg_floor.argtypes = [P(Vec), ctypes.c_uint32, P(Hit)]
        lib.bg_floor.restype = ctypes.c_int32
        lib.bg_wall.argtypes = [P(Vec), P(Vec), P(Vec), ctypes.c_int32, ctypes.c_int32,
                                ctypes.c_uint32, ctypes.c_bool, P(Hit)]
        lib.bg_wall.restype = ctypes.c_bool
        lib.bg_ceiling.argtypes = [P(ctypes.c_int32), P(Vec), ctypes.c_int32, ctypes.c_uint32,
                                   P(Hit)]
        lib.bg_ceiling.restype = ctypes.c_bool
        lib.bg_line.argtypes = [P(Vec), P(Vec), P(Vec), ctypes.c_uint32, ctypes.c_uint32, P(Hit)]
        lib.bg_line.restype = ctypes.c_bool
        lib.bg_water_surface.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_uint32,
                                         P(ctypes.c_int32), ctypes.c_void_p]
        lib.bg_water_surface.restype = ctypes.c_bool
        lib.bg_wall_flags.argtypes = [P(Hit)]
        lib.bg_wall_flags.restype = ctypes.c_uint32
        lib.bg_dyna_init.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.bg_dyna_register.argtypes = [P(Mesh), ctypes.c_uint32]
        lib.bg_dyna_register.restype = ctypes.c_uint32
        lib.bg_dyna_set.argtypes = [ctypes.c_uint32, P(Vec), ctypes.c_uint16, ctypes.c_int32]
        lib.bg_dyna_enable.argtypes = [ctypes.c_uint32, ctypes.c_bool]
        lib.bg_dyna_remove.argtypes = [ctypes.c_uint32]
        lib.bg_dyna_carry.argtypes = [ctypes.c_uint32, P(Vec), P(ctypes.c_uint16)]
        lib.bg_dyna_carry.restype = ctypes.c_bool
        lib.bg_dyna_triangles_used.restype = ctypes.c_uint32
        cls.dyna_buffer = ctypes.create_string_buffer(512 * 36)
        lib.bg_dyna_init(cls.dyna_buffer, 512 * 36)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.lib.bg_dyna_clear()

    # ---- helpers ----
    def decode(self, data):
        need = self.lib.bg_mesh_bytes(data, len(data))
        self.assertGreater(need, 0)
        store = ctypes.create_string_buffer(need)
        mesh = Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(data, len(data), store, need, ctypes.byref(mesh)))
        return mesh, store

    def use_file(self, path):
        data = path.read_bytes()
        self.mesh, self.store = self.decode(data)
        self.lib.bg_scene_set(ctypes.byref(self.mesh))
        self.index = ctypes.create_string_buffer(16 * 1024)
        self.assertTrue(self.lib.kokiri_collision_index(self.index, 16 * 1024))
        return parse_kbg2(data)

    def use_triangles(self, tris):
        self.tris = (Triangle * max(len(tris), 1))(*tris)
        self.lib.kokiri_collision_init(self.tris, len(tris))

    def floor(self, x, y, z, ignore=0):
        hit = Hit()
        return self.lib.bg_floor(ctypes.byref(Vec(x, y, z)), ignore, ctypes.byref(hit)), hit

    def test_grass_tops_do_not_support_player(self):
        self.use_file(FOREST)
        for x, z, top, ground in [(60, -430, 28, 1),
                                   (-480, 190, 28, 1),
                                   (-570, 1720, 144, 120)]:
            self.assertEqual(self.floor(x, 200, z)[0], top)
            self.assertEqual(self.floor(x, 200, z, BG_IGNORE_ENTITY)[0], ground)
            height = ctypes.c_int32()
            self.assertTrue(self.lib.kokiri_collision_floor(x, z, 200,
                                                           ctypes.byref(height)))
            self.assertEqual(height.value, ground)

    def line(self, a, b, checks=BG_CHECK_ALL):
        hit, at = Hit(), Vec()
        ok = self.lib.bg_line(ctypes.byref(Vec(*a)), ctypes.byref(Vec(*b)), ctypes.byref(at),
                              checks, 0, ctypes.byref(hit))
        return ok, hit, at

    def through(self, poly, depth=10):
        """Line through a triangle's centroid along its normal (front -> back)."""
        v = [poly[0:3], poly[3:6], poly[6:9]]
        n = poly[9:12]
        c = [sum(p[k] for p in v) // 3 for k in range(3)]
        length = max(abs(x) for x in n)
        d = [round(n[k] * depth / length) for k in range(3)]
        return self.line([c[k] + d[k] for k in range(3)], [c[k] - d[k] for k in range(3)])

    # ---- file / decode ----
    def test_file_rejects_bad_magic_and_truncation(self):
        data = FOREST.read_bytes()
        self.assertEqual(self.lib.bg_mesh_bytes(b'XBG2' + data[4:], len(data)), 0)
        self.assertEqual(self.lib.bg_mesh_bytes(data[:-2], len(data) - 2), 0)
        need = self.lib.bg_mesh_bytes(data, len(data))
        small = ctypes.create_string_buffer(need - 4)
        self.assertFalse(self.lib.bg_mesh_decode(data, len(data), small, need - 4,
                                                 ctypes.byref(Mesh())))

    def test_camera_vector_range_cannot_wrap(self):
        data = bytearray(HOUSE.read_bytes())
        tris, surfaces, water, cams, vectors, _ = struct.unpack_from('>6H', data, 4)
        o = 16 + 36 * tris + ((tris * 2 + 3) & ~3) + 8 * surfaces + 16 * water
        self.assertGreater(cams, 0)
        struct.pack_into('>hI', data, o + 2, 1, 0xFFFFFFFF)   # count 1, first 2^32-1
        need = self.lib.bg_mesh_bytes(bytes(data), len(data))
        store = ctypes.create_string_buffer(need)
        self.assertFalse(self.lib.bg_mesh_decode(bytes(data), len(data), store, need,
                                                 ctypes.byref(Mesh())))

    def test_every_surface_word_survives_export(self):
        """Raw SurfaceType words, ignore flags and conveyor bit reach the runtime."""
        polys, info, surfaces, _, _ = self.use_file(FOREST)
        self.assertEqual(len(polys), 1692)
        self.assertEqual(len(surfaces), 46)
        checked = set()
        for i, poly in enumerate(polys):
            s = info[i] & 0xFF
            if s in checked or poly[10] >= 8192 or poly[10] < -13107:
                continue
            ok, hit, _ = self.through(poly)
            if not ok or hit.poly != i:
                continue        # an adjacent poly lies closer on this line
            self.assertEqual(hit.bg_id, BG_SCENE)
            self.assertEqual((hit.data0, hit.data1), surfaces[s])
            self.assertEqual(hit.ignore, info[i] >> 8 & 7)
            checked.add(s)
        self.assertGreater(len(checked), 10)

    # ---- real Kokiri Forest facts (extracted spot04, US 1.2) ----
    def test_house_ladder_face_is_wall_type_2(self):
        self.use_file(FOREST)
        ok, hit, at = self.line((-29, 50, 990), (-29, 50, 1020), BG_CHECK_WALL)
        self.assertTrue(ok)
        self.assertEqual(at.z, 1004)
        self.assertEqual(hit.wall_type(), 2)
        self.assertEqual(self.lib.bg_wall_flags(ctypes.byref(hit)), 0x03)   # FLAG_0 | FLAG_1

    def test_house_ladder_lip_is_wall_type_3(self):
        self.use_file(FOREST)
        ok, hit, at = self.line((-29, 110, 1030), (-29, 110, 1000), BG_CHECK_WALL)
        self.assertTrue(ok)
        self.assertEqual(at.z, 1008)
        self.assertEqual(hit.wall_type(), 3)
        self.assertEqual(self.lib.bg_wall_flags(ctypes.byref(hit)), 0x05)   # FLAG_0 | FLAG_2

    def test_porch_floor_carries_bgcam_4(self):
        self.use_file(FOREST)
        y, hit = self.floor(-31, 150, 1073)
        self.assertEqual(y, 100)
        self.assertEqual(hit.bg_id, BG_SCENE)
        self.assertEqual(hit.bgcam(), 4)

    def test_crawlspace_and_type_4_walls_map_through_the_flag_table(self):
        polys, info, surfaces, _, _ = self.use_file(FOREST)
        found = {}
        for i, poly in enumerate(polys):
            wall = surfaces[info[i] & 0xFF][0] >> 21 & 0x1F
            if wall in (4, 5) and not (poly[10] >= 8192 or poly[10] < -13107):
                ok, hit, _ = self.through(poly)
                if ok and hit.poly == i:
                    found.setdefault(wall, []).append(poly)
                    self.assertEqual(self.lib.bg_wall_flags(ctypes.byref(hit)), WALL_FLAGS[wall])
        self.assertIn(4, found)
        self.assertIn(5, found)
        # The crawl hole to the sword maze, and the one WALL_TYPE_4 wall.
        for poly in found[5]:
            xs = poly[0:9:3]
            self.assertTrue(all(-801 <= x <= -769 for x in xs), xs)
        for poly in found[4]:
            xs = poly[0:9:3]
            self.assertTrue(all(-539 <= x <= -525 for x in xs), xs)

    def test_exit_polygons_report_their_exit_index(self):
        polys, info, surfaces, _, _ = self.use_file(FOREST)
        seen = 0
        for i, poly in enumerate(polys):
            exit_index = surfaces[info[i] & 0xFF][0] >> 8 & 0x1F
            if not exit_index or poly[10] < 8192:
                continue
            c = [sum(poly[k + 3 * j] for j in range(3)) // 3 for k in range(3)]
            y, hit = self.floor(c[0], c[1] + 20, c[2])
            if hit.poly == i:
                self.assertEqual(hit.exit(), exit_index)
                seen += 1
        self.assertGreater(seen, 0)

    def test_forest_waterbox(self):
        _, _, _, boxes, _ = self.use_file(FOREST)
        self.assertEqual(boxes, [(73, -12, -588, 1400, 1040, 269)])
        surface = ctypes.c_int32()
        self.assertTrue(self.lib.bg_water_surface(700, -100, 0, ctypes.byref(surface), None))
        self.assertEqual(surface.value, -12)
        # Strict bounds, as BgCheck_GetWaterSurface (its documented seam bug).
        self.assertFalse(self.lib.bg_water_surface(73, -100, 0, ctypes.byref(surface), None))
        self.assertFalse(self.lib.bg_water_surface(700, 452, 0, ctypes.byref(surface), None))
        # Room 0 only.
        self.assertFalse(self.lib.bg_water_surface(700, -100, 1, ctypes.byref(surface), None))

    def test_house_has_no_water_and_still_decodes(self):
        _, _, _, boxes, cams = self.use_file(HOUSE)
        self.assertEqual(boxes, [])
        self.assertEqual(cams, 3)
        surface = ctypes.c_int32()
        self.assertFalse(self.lib.bg_water_surface(0, 0, 0, ctypes.byref(surface), None))

    def test_old_floor_query_unchanged_over_the_forest(self):
        """The eye-anchor API answers as before after the KBG2 decode."""
        self.use_file(FOREST)
        height = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(-31, 1073, 150, ctypes.byref(height)))
        self.assertEqual(height.value, 100)

    # ---- synthetic geometry: exact numbers ----
    def wall_at_x100(self):
        # Vertical wall x=100 facing -x, y 0..100, z -100..100.
        n = (-16384, 0, 0)
        return [triangle(((100, 0, -100), (100, 100, -100), (100, 100, 100)), n),
                triangle(((100, 0, -100), (100, 100, 100), (100, 0, 100)), n)]

    def test_sphere_pushes_out_to_radius(self):
        self.use_triangles(self.wall_at_x100())
        result, hit = Vec(), Hit()
        self.assertTrue(self.lib.bg_wall(ctypes.byref(result), ctypes.byref(Vec(95, 0, 0)),
                                         ctypes.byref(Vec(80, 0, 0)), 14, 26, BG_IGNORE_ENTITY,
                                         False, ctypes.byref(hit)))
        self.assertEqual((result.x, result.z), (86, 0))
        self.assertEqual(hit.bg_id, BG_SCENE)
        self.assertEqual(hit.normal[0], -16384)

    def test_fast_move_cannot_tunnel_through_a_wall(self):
        self.use_triangles(self.wall_at_x100())
        result, hit = Vec(), Hit()
        self.assertTrue(self.lib.bg_wall(ctypes.byref(result), ctypes.byref(Vec(130, 0, 0)),
                                         ctypes.byref(Vec(80, 0, 0)), 14, 26, 0, False,
                                         ctypes.byref(hit)))
        self.assertEqual(result.x, 86)

    def test_no_wall_contact_leaves_position(self):
        self.use_triangles(self.wall_at_x100())
        result, hit = Vec(), Hit()
        self.assertFalse(self.lib.bg_wall(ctypes.byref(result), ctypes.byref(Vec(70, 0, 5)),
                                          ctypes.byref(Vec(60, 0, 5)), 14, 26, 0, False,
                                          ctypes.byref(hit)))
        self.assertEqual((result.x, result.y, result.z), (70, 0, 5))
        # Sphere entirely below the wall's lowest vertex: no contact.
        self.use_triangles([triangle(((100, 200, -100), (100, 300, -100), (100, 300, 100)),
                                     (-16384, 0, 0))])
        self.assertFalse(self.lib.bg_wall(ctypes.byref(result), ctypes.byref(Vec(95, 0, 0)),
                                          ctypes.byref(Vec(95, 0, 0)), 14, 26, 0, True,
                                          ctypes.byref(hit)))

    def test_ceiling_reports_clearance(self):
        # Ceiling at y=40 over x/z -100..100, facing down.
        n = (0, -16384, 0)
        self.use_triangles([triangle(((-100, 40, -100), (100, 40, 100), (100, 40, -100)), n),
                            triangle(((-100, 40, -100), (-100, 40, 100), (100, 40, 100)), n)])
        out, hit = ctypes.c_int32(), Hit()
        self.assertTrue(self.lib.bg_ceiling(ctypes.byref(out), ctypes.byref(Vec(0, 10, 0)), 40, 0,
                                            ctypes.byref(hit)))
        self.assertEqual(out.value, 0)          # feet may rise to 40 - 40
        self.assertFalse(self.lib.bg_ceiling(ctypes.byref(out), ctypes.byref(Vec(0, -40, 0)), 40,
                                             0, ctypes.byref(hit)))
        self.assertFalse(self.lib.bg_ceiling(ctypes.byref(out), ctypes.byref(Vec(0, 50, 0)), 40,
                                             0, ctypes.byref(hit)))

    def test_floor_is_strictly_below_and_misses_off_the_edge(self):
        n = (0, 16384, 0)
        self.use_triangles([triangle(((-100, 20, -100), (100, 20, 100), (100, 20, -100)), n),
                            triangle(((-100, 20, -100), (-100, 20, 100), (100, 20, 100)), n)])
        self.assertEqual(self.floor(0, 21, 0)[0], 20)
        self.assertEqual(self.floor(0, 20, 0)[0], BG_Y_MIN)     # yIntersect < pos.y
        self.assertEqual(self.floor(300, 50, 0)[0], BG_Y_MIN)
        self.assertEqual(self.floor(300, 50, 0)[1].bg_id, BG_NONE)

    # ---- DynaPoly with the real push block ----
    def block(self, transform=BG_DYNA_POS):
        self.block_mesh, self.block_store = self.decode(BLOCK.read_bytes())
        return self.lib.bg_dyna_register(ctypes.byref(self.block_mesh), transform)

    def test_push_block_mesh_is_gpushblockcol(self):
        polys, info, surfaces, _, _ = parse_kbg2(BLOCK.read_bytes())
        self.assertEqual(len(polys), 12)
        # Sides WALL_TYPE_7 (WALL_FLAG_6: pushable), top/bottom WALL_TYPE_0.
        walls = {surfaces[info[i] & 0xFF][0] >> 21 & 0x1F
                 for i, p in enumerate(polys) if p[10] == 0}
        self.assertEqual(walls, {7})

    def test_dyna_floor_wall_move_carry_disable_remove(self):
        self.use_triangles([])
        bg = self.block()
        self.assertEqual(bg, 0)
        tenth = 6554                                    # actor scale 0.1 (Q16)
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(0, 0, 0)), 0, tenth)
        y, hit = self.floor(0, 100, 0)
        self.assertEqual(y, 60)
        self.assertEqual(hit.bg_id, bg)
        # Old eye-anchor API sees it as well.
        height = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(0, 0, 100, ctypes.byref(height)))
        self.assertEqual(height.value, 60)
        # Side face: WALL_FLAG_6.
        ok, hit, at = self.line((-60, 30, 0), (0, 30, 0), BG_CHECK_WALL)
        self.assertTrue(ok)
        self.assertEqual(hit.bg_id, bg)
        self.assertEqual(at.x, -30)
        self.assertEqual(self.lib.bg_wall_flags(ctypes.byref(hit)), 0x40)
        # Moving it carries a rider standing on top.
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(30, 0, 0)), 0, tenth)
        rider, yaw = Vec(0, 60, 0), ctypes.c_uint16(0)
        self.assertTrue(self.lib.bg_dyna_carry(bg, ctypes.byref(rider), ctypes.byref(yaw)))
        self.assertEqual((rider.x, rider.y, rider.z, yaw.value), (30, 60, 0, 0))
        # No motion since the step: POS still applies (source returns true),
        # moving the rider by nothing.
        self.lib.bg_dyna_step()
        self.assertTrue(self.lib.bg_dyna_carry(bg, ctypes.byref(rider), ctypes.byref(yaw)))
        self.assertEqual((rider.x, rider.y, rider.z), (30, 60, 0))
        # Disabled collision is invisible; removal frees the slot and space.
        self.lib.bg_dyna_enable(bg, False)
        self.assertEqual(self.floor(30, 100, 0)[0], BG_Y_MIN)
        self.lib.bg_dyna_enable(bg, True)
        self.assertEqual(self.floor(30, 100, 0)[0], 60)
        self.lib.bg_dyna_remove(bg)
        self.assertEqual(self.floor(30, 100, 0)[0], BG_Y_MIN)
        self.assertEqual(self.lib.bg_dyna_triangles_used(), 0)
        self.assertEqual(self.block(), 0)

    def test_dyna_rotation_turns_rider_and_mesh(self):
        self.use_triangles([])
        bg = self.block(BG_DYNA_POS | BG_DYNA_ROT_Y)
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(0, 0, 0)), 0, 6554)
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(0, 0, 0)), 0x4000, 6554)
        rider, yaw = Vec(10, 60, 0), ctypes.c_uint16(0x1000)
        self.assertTrue(self.lib.bg_dyna_carry(bg, ctypes.byref(rider), ctypes.byref(yaw)))
        # Y rotation [c 0 s; 0 1 0; -s 0 c] by 90 degrees: (10, 0) -> (0, -10).
        self.assertEqual((rider.x, rider.y, rider.z), (0, 60, -10))
        self.assertEqual(yaw.value, 0x5000)
        # A face that pointed +x now points -z.
        ok, hit, _ = self.line((0, 30, -60), (0, 30, 0), BG_CHECK_WALL)
        self.assertTrue(ok)
        self.assertEqual(tuple(hit.normal), (0, 0, -16384))

    # ---- carry semantics, DynaPolyActor_TransformCarriedActor ----
    def moved(self, transform, before, after, rider, yaw=0x1000):
        """Place a block `before`, step, place it `after`, carry `rider`."""
        self.use_triangles([])
        bg = self.block(transform)
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(*before[0])), before[1], before[2])
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(*after[0])), after[1], after[2])
        pos, turn = Vec(*rider), ctypes.c_uint16(yaw)
        ok = self.lib.bg_dyna_carry(bg, ctypes.byref(pos), ctypes.byref(turn))
        return ok, (pos.x, pos.y, pos.z), turn.value

    TENTH = 6554

    def test_pos_only_rotates_position_not_facing(self):
        ok, pos, yaw = self.moved(BG_DYNA_POS, ((0, 0, 0), 0, self.TENTH),
                                  ((0, 0, 0), 0x4000, self.TENTH), (10, 0, 0))
        self.assertTrue(ok)
        self.assertEqual(pos, (0, 0, -10))
        self.assertEqual(yaw, 0x1000)

    def test_rot_y_only_turns_facing_not_position(self):
        ok, pos, yaw = self.moved(BG_DYNA_ROT_Y, ((0, 0, 0), 0, self.TENTH),
                                  ((0, 0, 0), 0x4000, self.TENTH), (10, 0, 0))
        self.assertTrue(ok)
        self.assertEqual(pos, (10, 0, 0))
        self.assertEqual(yaw, 0x5000)

    def test_neither_flag_carries_nothing(self):
        ok, pos, yaw = self.moved(0, ((0, 0, 0), 0, self.TENTH),
                                  ((50, 0, 0), 0x4000, self.TENTH), (10, 0, 0))
        self.assertFalse(ok)
        self.assertEqual((pos, yaw), ((10, 0, 0), 0x1000))

    def test_translation_plus_rotation(self):
        ok, pos, yaw = self.moved(BG_DYNA_POS | BG_DYNA_ROT_Y, ((100, 0, 0), 0, self.TENTH),
                                  ((200, 5, 0), 0x4000, self.TENTH), (110, 60, 0))
        self.assertTrue(ok)
        self.assertEqual(pos, (200, 65, -10))
        self.assertEqual(yaw, 0x5000)

    def test_scale_change_scales_the_rider_offset(self):
        ok, pos, _ = self.moved(BG_DYNA_POS, ((0, 0, 0), 0, self.TENTH),
                                ((0, 0, 0), 0, 2 * self.TENTH), (10, 60, 0))
        self.assertTrue(ok)
        self.assertEqual(pos, (20, 120, 0))

    def test_registering_does_not_reset_other_platforms(self):
        """Astra M1A_REVIEW P1 repro: register B between A's move and A's carry."""
        self.use_triangles([])
        a = self.block()
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(a, ctypes.byref(Vec(30, 0, 0)), 0, 65536)
        b = self.block()
        self.assertNotEqual(a, b)
        rider = Vec(0, 100, 0)
        self.assertTrue(self.lib.bg_dyna_carry(a, ctypes.byref(rider), None))
        self.assertEqual(rider.x, 30)
        # The new slot starts still: nothing to carry yet.
        rider = Vec(5, 100, 0)
        self.assertTrue(self.lib.bg_dyna_carry(b, ctypes.byref(rider), None))
        self.assertEqual((rider.x, rider.y, rider.z), (5, 100, 0))
        # Reusing a freed slot mid-step: fresh history, other slot untouched.
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(b, ctypes.byref(Vec(0, 0, 40)), 0, 65536)
        self.lib.bg_dyna_remove(a)
        c = self.block()
        self.assertEqual(c, a)
        rider = Vec(7, 0, 0)
        self.assertTrue(self.lib.bg_dyna_carry(c, ctypes.byref(rider), None))
        self.assertEqual((rider.x, rider.z), (7, 0))
        rider = Vec(0, 0, 0)
        self.assertTrue(self.lib.bg_dyna_carry(b, ctypes.byref(rider), None))
        self.assertEqual(rider.z, 40)

    def test_disabled_or_removed_slot_carries_nothing(self):
        self.use_triangles([])
        bg = self.block()
        self.lib.bg_dyna_step()
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(30, 0, 0)), 0, 65536)
        rider = Vec(0, 0, 0)
        self.lib.bg_dyna_enable(bg, False)
        self.assertFalse(self.lib.bg_dyna_carry(bg, ctypes.byref(rider), None))
        self.lib.bg_dyna_enable(bg, True)
        self.lib.bg_dyna_remove(bg)
        self.assertFalse(self.lib.bg_dyna_carry(bg, ctypes.byref(rider), None))
        self.assertEqual(rider.x, 0)

    def test_dyna_blocks_the_old_actor_move(self):
        """A registered block stops the existing Link movement too."""
        n = (0, 16384, 0)
        self.use_triangles([triangle(((-500, 0, -500), (500, 0, 500), (500, 0, -500)), n),
                            triangle(((-500, 0, -500), (-500, 0, 500), (500, 0, 500)), n)])
        bg = self.block()
        self.lib.bg_dyna_set(bg, ctypes.byref(Vec(100, 0, 0)), 0, 6554)
        self.lib.kokiri_collision_move_actor.argtypes = [ctypes.POINTER(Vec), ctypes.c_int32,
                                                         ctypes.c_int32, ctypes.c_int32]
        link = Vec(0, 90, 0)                    # eye anchor: feet 0 + 90
        self.lib.kokiri_collision_move_actor(ctypes.byref(link), 200, 0, 0)
        self.assertLessEqual(link.x, 100 - 30 - 14 + 4)
        self.assertGreater(link.x, 40)


if __name__ == '__main__':
    unittest.main()
