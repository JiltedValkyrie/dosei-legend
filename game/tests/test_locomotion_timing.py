"""Execute the actual C movement/state code; no emulator input required."""
import ctypes
import math
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


class Position(ctypes.Structure):
    _fields_ = [(axis, ctypes.c_int32) for axis in ('x', 'y', 'z')]


@unittest.skipUnless(GCC.is_file() and (ROOT / 'build/generated/link_clips.c').is_file(),
                     'host compiler and generated clips required')
class LocomotionTiming(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'locomotion.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(camera),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        '-I' + str(ROOT / 'build/generated'),
                        str(camera / 'kokiri_camera.c'),
                        str(ROOT / 'src/link_anim_state.c'),
                        str(ROOT / 'build/generated/link_clips.c'),
                        str(ROOT / 'tests/fixtures/locomotion_host.c'), '-lm'],
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.kokiri_camera_update.argtypes = [ctypes.POINTER(Position),
            ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_int32),
            ctypes.c_uint16, ctypes.c_bool, ctypes.c_bool]
        cls.lib.link_anim_update.argtypes = [ctypes.c_int32, ctypes.c_bool,
                                             ctypes.c_int32, ctypes.c_bool]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def travel(self, buttons, yaw=0):
        self.lib.kokiri_camera_reset_actor_motion()
        p, angle, pitch = Position(), ctypes.c_uint16(yaw), ctypes.c_int32()
        for _ in range(300):
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), buttons, False, True)
        return math.hypot(p.x, p.z)

    def test_native_child_run_speed_over_ten_seconds(self):
        self.assertEqual(self.travel(0x1000), 1650)

    def test_short_press_survives_eight_vblanks_without_draw(self):
        self.lib.edge_reset()
        self.lib.edge_sample(True)
        for _ in range(8):
            self.lib.edge_sample(False)
        self.assertEqual(self.lib.edge_consume(), 1)
        self.assertEqual(self.lib.edge_consume(), 0)

    def test_held_button_does_not_repeat(self):
        self.lib.edge_reset()
        self.lib.edge_sample(True)
        self.assertEqual(self.lib.edge_consume(), 1)
        for _ in range(20):
            self.lib.edge_sample(True)
        self.assertEqual(self.lib.edge_consume(), 0)

    def test_release_rearms_button(self):
        self.lib.edge_reset()
        self.lib.edge_sample(True)
        self.lib.edge_consume()
        self.lib.edge_sample(False)
        self.lib.edge_sample(True)
        self.assertEqual(self.lib.edge_consume(), 1)

    def test_start_no_longer_uses_ephemeral_edge(self):
        text = (ROOT / 'src/demo.c').read_text()
        self.assertNotIn('jo_is_pad1_key_down(JO_KEY_START)', text)
        self.assertIn('input_edge_sample(&start_edge', text)
        self.assertIn('if (start_pressed && !music_busy())', text)

    def test_diagonal_and_rotated_speed_match(self):
        for buttons, yaw in ((0x9000, 0), (0x1000, 8192), (0x9000, 5000)):
            self.assertAlmostEqual(self.travel(buttons, yaw), 1650, delta=4)

    def test_run_clip_slower_than_old_30_fps(self):
        self.lib.link_anim_reset_state()
        # Resolve spawn landing before measuring the run cycle.
        for _ in range(50):
            self.lib.link_anim_update(5, True, 0, False)
        start = self.lib.link_anim_frame()
        for _ in range(15):
            self.lib.link_anim_update(5, True, 0, False)
        self.assertEqual(self.lib.link_anim_state(), 2)  # run
        self.assertEqual((self.lib.link_anim_frame() - start) % 20, 10)

    def test_fall_decimation_preserves_source_cadence(self):
        self.lib.link_anim_reset_state()
        for _ in range(9):
            self.lib.link_anim_update(5, False, 0, False)
        self.assertEqual(self.lib.link_anim_frame(), 2)  # six source frames

    def test_fractional_pose_available(self):
        self.lib.link_anim_reset_state()
        self.lib.link_anim_update(5, False, 0, False)
        self.assertGreater(self.lib.link_anim_fraction(), 0)
        self.assertLess(self.lib.link_anim_fraction(), 256)

    def test_l_does_not_reach_gameplay_orbit(self):
        text = (ROOT / 'src/demo.c').read_text()
        mask = text.split('uint16_t walk = buttons &', 1)[1].split(';', 1)[0]
        self.assertNotIn('CAMERA_L', mask.replace('CAMERA_LEFT', ''))
        self.assertIn('recenter = recenter_pressed', text)
        # L must recenter, never orbit. It now starts an OoT-style swing
        # instead of assigning demo_yaw directly, so the check is that the
        # press reaches the camera's recenter entry point.
        self.assertIn('oot_follow_recenter(&link_follow)', text)

    def test_r_does_not_reach_gameplay_orbit(self):
        text = (ROOT / 'src/demo.c').read_text()
        mask = text.split('uint16_t walk = buttons &', 1)[1].split(';', 1)[0]
        self.assertNotIn('CAMERA_R', mask.replace('CAMERA_RIGHT', ''))

    def test_shoulders_never_orbit_actor_camera(self):
        for buttons in (0x0008, 0x0080, 0x0088, 0x1080):
            p, angle, pitch = Position(), ctypes.c_uint16(1234), ctypes.c_int32()
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), buttons, False, True)
            self.assertEqual(angle.value, 1234)
