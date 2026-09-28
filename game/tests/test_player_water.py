"""M1k fixed-step swimming: real collision, clips, water boxes and shore exits."""
import ctypes as C
import os
import pathlib
import sys
import subprocess
import tempfile
import unittest
import test_player_bg as bg

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
class Water(C.Structure):
    _fields_ = [('phase', C.c_uint), ('timer', C.c_uint), ('submerged', C.c_uint),
                ('speed', C.c_int32), ('velocity', C.c_int32),
                ('remainder', C.c_int32 * 3), ('rise_depth', C.c_int32),
                ('yaw', C.c_uint16), ('grounded', C.c_bool)]
class Input(C.Structure):
    _fields_ = [('speed', C.c_int32), ('yaw', C.c_uint16),
                ('room', C.c_uint), ('scale', C.c_uint), ('pressed', C.c_bool),
                ('held', C.c_bool), ('stroke', C.c_bool), ('blocked', C.c_bool)]
class Box(C.Structure):
    _fields_ = [('x', C.c_int16), ('y', C.c_int16), ('z', C.c_int16),
                ('width', C.c_int16), ('length', C.c_int16), ('properties', C.c_uint32)]

@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class PlayerWater(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll = pathlib.Path(cls.tmp.name) / 'water.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I'+str(ROOT/'src'), '-I'+str(ROOT/'build/generated'),
            '-I'+str(ROOT.parent/'shared/lib/camera'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),
            str(ROOT/'src/player_water.c'), str(ROOT/'src/link_anim_state.c'),
            str(ROOT/'build/generated/link_clips.c'),
            str(ROOT/'tests/fixtures/traversal_host.c'),
            str(ROOT.parent/'shared/lib/collision/kokiri_collision.c'),
            '-o', str(dll), '-lm'], check=True, env=env)
        cls.lib = C.CDLL(str(dll))
        cls.lib.player_water_step.argtypes = [C.POINTER(Water), C.POINTER(Input),
            C.POINTER(bg.Vec), C.POINTER(C.c_uint16), C.c_int32, C.c_bool]
        cls.lib.player_water_step.restype = C.c_bool
        cls.lib.player_water_hazard.argtypes = [C.POINTER(Water)]
        cls.lib.player_water_hazard.restype = C.c_bool
        cls.lib.bg_scene_set.argtypes = [C.POINTER(bg.Mesh)]
        cls.lib.bg_mesh_bytes.argtypes = [C.c_char_p, C.c_uint32]
        cls.lib.bg_mesh_bytes.restype = C.c_uint32
        cls.lib.bg_mesh_decode.argtypes = [C.c_char_p, C.c_uint32, C.c_void_p,
                                          C.c_uint32, C.POINTER(bg.Mesh)]
        cls.lib.bg_mesh_decode.restype = C.c_bool
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.water = Water()
        self.input = Input()
        self.feet = bg.Vec(0, -40, 0)
        self.facing = C.c_uint16(0)
        self.lib.link_anim_reset_state()
        self.lib.bg_dyna_clear()
        self.world(bg.ground(-300))
    def world(self, triangles, properties=0):
        self.tris = (bg.Triangle * len(triangles))(*[t for t, _ in triangles])
        self.info = (C.c_uint16 * len(triangles))(*[i for _, i in triangles])
        self.surfaces = (C.c_uint32 * 2)(0, 0)
        self.boxes = (Box * 1)(Box(-500, 0, -500, 1000, 1000, properties))
        self.mesh = bg.Mesh(self.tris, len(triangles), self.info, self.surfaces, 1,
                            C.cast(self.boxes, C.c_void_p), 1, None, 0, None, 0)
        self.lib.bg_scene_set(C.byref(self.mesh))
    def step(self, incoming=0):
        result = self.lib.player_water_step(C.byref(self.water), C.byref(self.input),
                    C.byref(self.feet), C.byref(self.facing), incoming, False)
        self.input.pressed = self.input.stroke = False
        return result
    def surface(self):
        for _ in range(150):
            self.assertTrue(self.step())
        self.assertEqual(self.water.phase, 2)
        self.assertTrue(-33 <= self.feet.y <= -27, self.feet.y)
    def test_entry_exit_hysteresis_and_room(self):
        self.feet.y = -32
        self.assertFalse(self.step())
        self.feet.y = -33
        self.assertTrue(self.step())
        self.feet.y = -22
        self.assertTrue(self.step())
        self.feet.y = -21
        self.assertFalse(self.step())
        self.assertEqual(self.water.phase, 0)
        self.input.room = 1
        self.feet.y = -80
        self.assertFalse(self.step())
    def test_buoyancy_settles_after_fast_fall(self):
        self.assertTrue(self.step(-5120))
        self.assertGreaterEqual(self.water.velocity, -1280)
        self.surface()
    def test_swim_strokes_and_release_keep_fractional_motion(self):
        self.surface()
        self.input.speed = 1408
        for _ in range(90): self.step()
        self.assertGreater(self.feet.z, 40)
        self.assertLessEqual(self.water.speed, 1126)
        self.input.speed = 0
        for _ in range(180): self.step()
        self.assertEqual(self.water.speed, 0)
        self.assertTrue(-33 <= self.feet.y <= -27)
    def test_dive_depth_limit_then_surface_even_while_a_held(self):
        self.surface()
        self.input.pressed = self.input.held = True
        self.step()
        self.assertEqual(self.water.phase, 3)
        for _ in range(19): self.step()
        self.assertEqual(self.water.velocity, 0)
        self.step()
        self.assertEqual(self.water.velocity, -512)
        lowest = self.feet.y
        phases = set()
        for _ in range(250):
            self.step()
            lowest = min(lowest, self.feet.y)
            phases.add(self.water.phase)
        self.assertLessEqual(lowest, -120)
        self.assertGreater(lowest, -145)
        self.assertTrue({4, 5, 6, 7, 2}.issubset(phases), phases)
        self.assertTrue(-33 <= self.feet.y <= -27, self.feet.y)
    def test_release_dive_returns_early_and_floor_stops_descent(self):
        self.world(bg.ground(-75))
        self.surface()
        self.input.pressed = self.input.held = True
        self.step()
        lowest = 0
        for _ in range(160):
            self.step()
            lowest = min(lowest, self.feet.y)
        self.assertGreaterEqual(lowest, -75)
        self.assertEqual(self.water.phase, 2)
        self.input.pressed = True
        self.input.held = False
        self.step()
        for _ in range(120): self.step()
        self.assertEqual(self.water.phase, 2)

    def test_scale_depth_limits_and_hazard_threshold(self):
        for scale, limit in [(1, 240), (2, 360), (99, 360)]:
            self.water = Water()
            self.world(bg.ground(-600))
            self.feet = bg.Vec(0, -40, 0)
            self.surface()
            self.input.scale = scale
            self.input.pressed = self.input.held = True
            self.step()
            lowest = self.feet.y
            for _ in range(500):
                self.step()
                lowest = min(lowest, self.feet.y)
            self.assertLessEqual(lowest, -limit)
            self.assertGreater(lowest, -limit-25)
            self.assertEqual(self.water.phase, 2)
        self.water.submerged = 449
        self.assertFalse(self.lib.player_water_hazard(C.byref(self.water)))
        self.water.submerged = 450
        self.assertTrue(self.lib.player_water_hazard(C.byref(self.water)))
        self.feet.y = -29
        self.step()
        self.assertEqual(self.water.submerged, 0)
    def test_wall_blocks_swimming(self):
        wall = bg.quad((-100,-300,80),(-100,100,80),(100,100,80),(100,-300,80))
        self.world(bg.ground(-300) + wall)
        self.surface()
        self.input.speed = 1408
        for _ in range(140): self.step()
        self.assertLessEqual(self.feet.z, 66)
        self.assertGreater(self.feet.z, 50)
    def test_shore_ramp_returns_to_locomotion(self):
        ramp = bg.quad((-100,-80,-100),(-100,20,150),(100,20,150),(100,-80,-100))
        self.world(ramp)
        self.feet.z = -90
        self.feet.y = -70
        self.input.speed = 1408
        active = False
        for _ in range(200):
            active |= self.step()
            if active and not self.water.phase: break
        self.assertTrue(active)
        self.assertEqual(self.water.phase, 0)
        self.assertGreater(self.feet.y, -22)
    def test_roof_stops_rising_without_instant_drowning(self):
        roof = bg.quad((-200,-50,-200),(200,-50,-200),(200,-50,200),(-200,-50,200))
        self.world(bg.ground(-300) + roof)
        self.feet.y = -120
        for _ in range(500):
            self.assertTrue(self.step())
            self.assertLessEqual(self.feet.y, -90)
        self.assertTrue(self.lib.player_water_hazard(C.byref(self.water)))
        self.assertNotEqual(self.water.phase, 0)
    def test_real_forest_water_and_dry_house(self):
        for filename, expected in [('S1.COL', True), ('S0.COL', False)]:
            data = (ROOT/'build/cd'/filename).read_bytes()
            size = self.lib.bg_mesh_bytes(data, len(data))
            self.storage = C.create_string_buffer(size)
            self.mesh = bg.Mesh()
            self.assertTrue(self.lib.bg_mesh_decode(data, len(data), self.storage,
                                                    size, C.byref(self.mesh)))
            self.lib.bg_scene_set(C.byref(self.mesh))
            self.water = Water()
            self.feet = bg.Vec(700, -60, -100)
            self.assertEqual(self.step(), expected)

    def test_real_pond_float_then_swim_up_bank(self):
        data = (ROOT/'build/cd/S1.COL').read_bytes()
        size = self.lib.bg_mesh_bytes(data, len(data))
        self.storage = C.create_string_buffer(size)
        self.mesh = bg.Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(data, len(data), self.storage,
                                                size, C.byref(self.mesh)))
        self.lib.bg_scene_set(C.byref(self.mesh))
        self.feet = bg.Vec(1180, -60, 120)
        for _ in range(180): self.assertTrue(self.step())
        self.assertTrue(-46 <= self.feet.y <= -39)
        self.input.speed = 1408
        for _ in range(180):
            self.step()
            if not self.water.phase: break
        self.assertEqual(self.water.phase, 0)
        self.assertGreater(self.feet.z, 350)
        self.assertGreater(self.feet.y, -34)

    def test_low_roof_refuses_shore_step(self):
        bank = bg.ground(-20, z0=80, z1=300)
        roof = bg.quad((-200,0,80),(200,0,80),(200,0,300),(-200,0,300))
        self.world(bg.ground(-300) + bank + roof)
        self.surface()
        self.input.speed = 1408
        for _ in range(120):
            self.step()
            self.assertFalse(self.feet.z >= 80 and self.feet.y > -40)

    def test_blocked_input_cannot_start_dive_or_swim(self):
        self.surface()
        self.input.blocked = True
        self.input.speed = 1408
        self.input.pressed = self.input.held = self.input.stroke = True
        start = self.feet.z
        for _ in range(60): self.step()
        self.assertEqual(self.water.phase, 2)
        self.assertEqual(self.feet.z, start)

    @unittest.skipUnless(pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot/baseroms/ntsc-1.2').is_dir(),
                         'local source ROM required')
    def test_deku_tree_water_boxes_use_source_rooms(self):
        sys.path.insert(0, str(ROOT.parent/'shared/tools'))
        import build_kokiri_scene as source
        root = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
        scene = source.extract(root, root/'baseroms/ntsc-1.2', prefix='ydan')['ydan_scene']
        data = source.collision_data(scene)
        # Whole source mesh, no exporter-cap change or invented forest fixture.
        triangles = []
        for p in data['polys']:
            t = bg.Triangle()
            for j, vertex in enumerate(p['vertices']): t.vertex[j][:] = vertex
            t.normal[:] = p['normal']
            t.minimum[:] = [min(v[k] for v in p['vertices']) for k in range(3)]
            t.maximum[:] = [max(v[k] for v in p['vertices']) for k in range(3)]
            triangles.append((t, p['surface'] | (p['ignore'] << 8)))
        self.world(triangles)
        self.surfaces = (C.c_uint32 * (2*len(data['surfaces'])))(
            *[v for pair in data['surfaces'] for v in pair])
        self.boxes = (Box * len(data['water']))(*[Box(*b) for b in data['water']])
        self.mesh.surfaces = self.surfaces
        self.mesh.surface_count = len(data['surfaces'])
        self.mesh.water = C.cast(self.boxes, C.c_void_p)
        self.mesh.water_count = len(self.boxes)
        self.lib.bg_scene_set(C.byref(self.mesh))
        self.assertEqual([(b.properties >> 13) & 63 for b in self.boxes], [3, 5, 9])
        for b in self.boxes:
            self.water = Water()
            self.feet = bg.Vec(b.x+b.width//2, b.y-40, b.z+b.length//2)
            self.input.room = 0
            self.assertFalse(self.step())
            self.input.room = (b.properties >> 13) & 63
            self.assertTrue(self.step())
            self.assertNotEqual(self.water.phase, 0)

if __name__ == '__main__': unittest.main()
