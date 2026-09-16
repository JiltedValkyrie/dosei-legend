"""Execute the real OoT follow camera C code on the host.

The camera's geometry is derived arithmetic -- OoT's raw table values scaled by
a player-height factor -- and a wrong factor produces a camera that still looks
plausible in isolation while being twice as far back as the original. These
tests pin the derivation against the decomp's own numbers and check the
behaviour that the parameters are supposed to produce.

What is NOT covered: how any of this feels, and every mode this does not
implement (targeting, first person, swing, collision). See ANIM_PARITY_NOTES.md.
"""

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


class Follow(ctypes.Structure):
    _fields_ = [('distance', ctypes.c_int32), ('yaw', ctypes.c_uint16),
                ('pitch', ctypes.c_int32), ('initialised', ctypes.c_bool)]


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class OotFollowCamera(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'follow.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(camera),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        str(camera / 'oot_follow.c'),
                        str(ROOT / 'tests/fixtures/locomotion_host.c'), '-lm'],
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.oot_follow_update.argtypes = [
            ctypes.POINTER(Follow), ctypes.POINTER(Position), ctypes.c_uint16,
            ctypes.c_bool, ctypes.POINTER(Position),
            ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_int32)]
        cls.lib.oot_follow_snap.argtypes = [
            ctypes.POINTER(Follow), ctypes.POINTER(Position), ctypes.c_uint16]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_steps(self, steps, facing=0, moving=True, player=None):
        cam, eye = Follow(), Position()
        yaw, pitch = ctypes.c_uint16(), ctypes.c_int32()
        player = player or Position(0, 0, 0)
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0)
        for _ in range(steps):
            self.lib.oot_follow_update(
                ctypes.byref(cam), ctypes.byref(player), facing, moving,
                ctypes.byref(eye), ctypes.byref(yaw), ctypes.byref(pitch))
        return cam, eye, yaw.value, pitch.value

    def test_distance_matches_the_scaled_decomp_values(self):
        """200 and 300 raw, scaled by 0.4640 for child Link's height of 44.

        yNormal = 1 + (-0.1) - (-0.1 * 68/44) = 1.05454
        scale   = yNormal * 0.44              = 0.46400
        """
        scale = (1 - 0.1 + 0.1 * (68.0 / 44.0)) * 0.44
        self.assertAlmostEqual(200 * scale, 92.8, places=1)
        self.assertAlmostEqual(300 * scale, 139.2, places=1)
        source = (ROOT.parent / 'shared/lib/camera/oot_follow.h').read_text()
        self.assertIn('OOT_CAM_DIST_MIN        93', source)
        self.assertIn('OOT_CAM_DIST_MAX        139', source)

    def test_camera_is_far_closer_than_the_retired_viewer_follow(self):
        """The viewer camera sat 260 units back. The real one is not close.

        This is the single most visible difference and the easiest thing to
        silently regress by reintroducing a fixed offset.
        """
        _cam, eye, _yaw, _pitch = self.run_steps(120, moving=False)
        distance = math.hypot(eye.x, eye.z)
        self.assertLess(distance, 160, 'camera drifted out toward the old 260')
        self.assertGreater(distance, 60, 'camera collapsed onto the player')

    def test_settles_between_dist_min_and_max(self):
        stopped, _e, _y, _p = self.run_steps(200, moving=False)
        self.assertEqual(stopped.distance, 93)
        running, _e, _y, _p = self.run_steps(200, moving=True)
        self.assertEqual(running.distance, 139)

    def test_pitch_output_is_negative_so_the_view_looks_down(self):
        """The eye is raised, so the view must look down to stay on Link.

        kokiri_camera_update() adds for Up, so positive pitch looks up. A sign
        error here puts Link off the bottom of the screen.
        """
        _cam, _eye, _yaw, pitch = self.run_steps(120)
        self.assertLess(pitch, 0)

    def test_eye_sits_above_the_player(self):
        _cam, eye, _yaw, _pitch = self.run_steps(120)
        self.assertGreater(eye.y, 0, 'a raised eye is what the pitch looks down from')

    def test_yaw_follows_the_player_only_while_moving(self):
        """Normal1 swings back behind the player only while xzSpeed > 0."""
        target = 0x4000
        moving, _e, yaw_moving, _p = self.run_steps(200, facing=target, moving=True)
        self.assertEqual(yaw_moving, target)
        _still, _e, yaw_still, _p = self.run_steps(200, facing=target, moving=False)
        self.assertEqual(yaw_still, 0, 'a standing camera must not swing on its own')

    def test_yaw_takes_the_short_way_round(self):
        """Approaching 0xF000 from 0 must go backwards, not 15/16 of a turn."""
        cam, eye = Follow(), Position()
        yaw, pitch = ctypes.c_uint16(), ctypes.c_int32()
        player = Position(0, 0, 0)
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0)
        self.lib.oot_follow_update(
            ctypes.byref(cam), ctypes.byref(player), 0xF000, True,
            ctypes.byref(eye), ctypes.byref(yaw), ctypes.byref(pitch))
        # One step toward 0xF000 the short way is a small decrease, which wraps
        # to just under 0x10000 -- never a small increase.
        self.assertGreater(yaw.value, 0x8000)

    def test_snap_is_immediate(self):
        """Recenter and void recovery must not ease; both call snap."""
        cam = Follow()
        player = Position(0, 0, 0)
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0x2000)
        self.assertEqual(cam.yaw, 0x2000)
        self.assertTrue(cam.initialised)


if __name__ == '__main__':
    unittest.main()
