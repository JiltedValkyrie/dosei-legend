"""Focused host checks for Link's fixed-point gravity and floor landing."""

import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'shared/lib/collision/kokiri_collision.c'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


class Position(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int32), ('y', ctypes.c_int32),
                ('z', ctypes.c_int32)]


class Triangle(ctypes.Structure):
    _fields_ = [('vertex', (ctypes.c_int16 * 3) * 3),
                ('normal', ctypes.c_int16 * 3),
                ('minimum', ctypes.c_int16 * 3),
                ('maximum', ctypes.c_int16 * 3)]


def flat_triangle(vertices, height):
    triangle = Triangle()
    for i, (x, z) in enumerate(vertices):
        triangle.vertex[i][:] = (x, height, z)
    triangle.normal[:] = (0, 16384, 0)
    triangle.minimum[:] = (min(x for x, _ in vertices), height,
                           min(z for _, z in vertices))
    triangle.maximum[:] = (max(x for x, _ in vertices), height,
                           max(z for _, z in vertices))
    return triangle


def platform(x0, x1, height):
    return [
        flat_triangle(((x0, -100), (x1, -100), (x1, 100)), height),
        flat_triangle(((x0, -100), (x1, 100), (x0, 100)), height),
    ]


def downhill_slope():
    # y = -x/4, with a normalized Q14 upward normal of roughly (1, 4, 0).
    triangles = []
    for vertices in (
            ((-100, 25, -100), (100, -25, -100), (100, -25, 100)),
            ((-100, 25, -100), (100, -25, 100), (-100, 25, 100))):
        triangle = Triangle()
        for i, vertex in enumerate(vertices):
            triangle.vertex[i][:] = vertex
        triangle.normal[:] = (3973, 15894, 0)
        triangle.minimum[:] = tuple(min(v[k] for v in vertices)
                                   for k in range(3))
        triangle.maximum[:] = tuple(max(v[k] for v in vertices)
                                   for k in range(3))
        triangles.append(triangle)
    return triangles


@unittest.skipUnless(SOURCE.is_file() and GCC.is_file(),
                     'collision source and mingw gcc required')
class CollisionGravityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        library = pathlib.Path(cls.tmp.name) / 'collision.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(library),
                        str(SOURCE)], check=True, env=env)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.kokiri_collision_init.argtypes = [ctypes.POINTER(Triangle),
                                                   ctypes.c_uint32]
        cls.lib.kokiri_collision_fall.argtypes = [ctypes.POINTER(Position),
                                                   ctypes.POINTER(ctypes.c_int32),
                                                   ctypes.POINTER(ctypes.c_int32)]
        cls.lib.kokiri_collision_fall.restype = ctypes.c_bool
        cls.lib.kokiri_collision_jump.argtypes = cls.lib.kokiri_collision_fall.argtypes
        cls.lib.kokiri_collision_jump.restype = ctypes.c_bool
        cls.lib.kokiri_collision_move.argtypes = [ctypes.POINTER(Position),
                                                   ctypes.c_int32,
                                                   ctypes.c_int32,
                                                   ctypes.c_int32]
        cls.lib.kokiri_collision_move_actor.argtypes = [
            ctypes.POINTER(Position), ctypes.c_int32, ctypes.c_int32,
            ctypes.c_int32]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _load(self, triangles):
        self.triangles = (Triangle * len(triangles))(*triangles)
        self.lib.kokiri_collision_init(self.triangles, len(triangles))

    def test_grounded_link_does_not_sink(self):
        self._load(platform(-100, 100, 0))
        position = Position(0, 90, 0)
        velocity = ctypes.c_int32(-500)
        remainder = ctypes.c_int32(-100)

        grounded = self.lib.kokiri_collision_fall(
            ctypes.byref(position), ctypes.byref(velocity),
            ctypes.byref(remainder))

        self.assertTrue(grounded)
        self.assertEqual(position.y, 90)
        self.assertEqual((velocity.value, remainder.value), (0, 0))

    def test_manual_jump_rises_peaks_and_lands_without_double_jump(self):
        self._load(platform(-100, 100, 0))
        link, velocity, remainder = Position(0,90,0), ctypes.c_int32(), ctypes.c_int32()
        args = ctypes.byref(link), ctypes.byref(velocity), ctypes.byref(remainder)
        self.assertTrue(self.lib.kokiri_collision_jump(*args))
        self.assertFalse(self.lib.kokiri_collision_jump(*args))
        heights = []
        for step in range(90):
            self.lib.kokiri_collision_move_actor(ctypes.byref(link), 2, 0, 0)
            grounded = self.lib.kokiri_collision_fall(*args)
            heights.append(link.y)
            if grounded:
                break
            self.assertFalse(self.lib.kokiri_collision_jump(*args), 'no double jump')
        self.assertTrue(grounded)
        self.assertGreater(heights[0], 90, 'ground snap must not cancel takeoff')
        self.assertTrue(45 <= max(heights)-90 <= 55)
        self.assertTrue(25 <= len(heights) <= 35)
        self.assertEqual(link.y, 90)
        self.assertGreater(link.x, 40, 'jump must retain horizontal movement')
        self.assertEqual((velocity.value,remainder.value), (0,0))
        for _ in range(10):
            self.assertTrue(self.lib.kokiri_collision_fall(*args))
            self.assertEqual(link.y, 90, 'no automatic bounce after landing')
        self.assertTrue(self.lib.kokiri_collision_jump(*args), 'new press can jump again')

    def test_jump_hits_low_ceiling_and_clears_upward_velocity(self):
        self._load(platform(-100,100,0)+platform(-100,100,80))
        link, velocity, remainder = Position(0,90,0), ctypes.c_int32(), ctypes.c_int32()
        args = ctypes.byref(link), ctypes.byref(velocity), ctypes.byref(remainder)
        self.assertTrue(self.lib.kokiri_collision_jump(*args))
        hit = False
        for _ in range(60):
            old_velocity = velocity.value
            grounded = self.lib.kokiri_collision_fall(*args)
            self.assertLessEqual(link.y-90+62, 80, 'head passed ceiling')
            if old_velocity > 0 and velocity.value == 0:
                hit = True
            if grounded:
                break
        self.assertTrue(hit)
        self.assertTrue(grounded)
        self.assertEqual(link.y, 90)

    def test_airborne_press_and_void_press_do_not_jump(self):
        self._load(platform(-100,100,0))
        for link in (Position(0,110,0), Position(200,90,0)):
            velocity, remainder = ctypes.c_int32(-30), ctypes.c_int32(12)
            self.assertFalse(self.lib.kokiri_collision_jump(ctypes.byref(link),
                             ctypes.byref(velocity),ctypes.byref(remainder)))
            self.assertEqual((velocity.value,remainder.value), (-30,12))

    def test_link_falls_from_high_platform_to_lower_floor(self):
        self._load(platform(-100, 0, 100) + platform(1, 100, 0))
        # The horizontal controller has just carried Link across x=0 while
        # retaining the high platform's eye height.
        position = Position(50, 190, 0)
        velocity = ctypes.c_int32()
        remainder = ctypes.c_int32()

        heights = []
        for _ in range(90):
            grounded = self.lib.kokiri_collision_fall(
                ctypes.byref(position), ctypes.byref(velocity),
                ctypes.byref(remainder))
            heights.append(position.y)
            if grounded:
                break

        self.assertTrue(grounded)
        self.assertEqual(position.y, 90)
        self.assertTrue(all(a >= b for a, b in zip(heights, heights[1:])))
        self.assertGreater(len(set(heights)), 2, 'fall snapped in one update')
        self.assertEqual((velocity.value, remainder.value), (0, 0))

    def test_child_link_fits_below_bridge_that_blocks_eye_camera(self):
        # A walkable bridge sits just over the 62-unit model but inside the old
        # camera-derived floor search, which incorrectly treated it as a step.
        bridge = platform(-100, 100, 65)
        self._load(bridge)

        camera = Position(0, 90, 0)
        self.lib.kokiri_collision_move(ctypes.byref(camera), 8, 0, 0)
        self.assertEqual(camera.x, 0, 'camera sphere should hit the bridge')

        link = Position(0, 90, 0)
        self.lib.kokiri_collision_move_actor(ctypes.byref(link), 8, 0, 0)
        self.assertEqual(link.x, 8, 'child Link body should fit below bridge')

    def test_overhead_bridge_does_not_hide_ground_from_gravity(self):
        self._load(platform(-100, 100, 0) + platform(-100, 100, 65))
        link = Position(0, 90, 0)
        velocity = ctypes.c_int32(-500)
        remainder = ctypes.c_int32(-100)

        grounded = self.lib.kokiri_collision_fall(
            ctypes.byref(link), ctypes.byref(velocity),
            ctypes.byref(remainder))

        self.assertTrue(grounded)
        self.assertEqual(link.y, 90)
        self.assertEqual((velocity.value, remainder.value), (0, 0))

    def test_grounded_link_follows_walkable_slope_downhill(self):
        self._load(downhill_slope())
        # The normalized Q14 plane rounds its x=0 floor height to 1.
        link = Position(0, 91, 0)

        self.lib.kokiri_collision_move_actor(ctypes.byref(link), 8, 0, 0)

        self.assertEqual(link.x, 8)
        self.assertEqual(link.y, 89)

    def test_grounded_link_does_not_cling_to_real_ledge(self):
        self._load(platform(-100, 0, 0) + platform(1, 100, -20))
        link = Position(0, 90, 0)

        self.lib.kokiri_collision_move_actor(ctypes.byref(link), 8, 0, 0)

        self.assertEqual(link.x, 8)
        self.assertEqual(link.y, 90)


if __name__ == '__main__':
    unittest.main()
