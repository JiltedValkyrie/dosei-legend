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
        """200/300 raw, scaled by OUR Link's height of 62, not OoT's 44.

        Camera_Normal1 scales to whatever the player actually measures.
        yNormal = 1 + (-0.1) - (-0.1 * 68/62) = 1.00968
        scale   = yNormal * 0.62              = 0.62600
        """
        scale = (1 - 0.1 + 0.1 * (68.0 / 62.0)) * 0.62
        self.assertAlmostEqual(200 * scale, 125.2, places=1)
        self.assertAlmostEqual(300 * scale, 187.8, places=1)
        source = (ROOT.parent / 'shared/lib/camera/oot_follow.h').read_text()
        self.assertIn('OOT_CAM_DIST_MIN        125', source)
        self.assertIn('OOT_CAM_DIST_MAX        188', source)

    def test_camera_is_far_closer_than_the_retired_viewer_follow(self):
        """The viewer camera sat 260 units back. The real one is not close.

        This is the single most visible difference and the easiest thing to
        silently regress by reintroducing a fixed offset.
        """
        _cam, eye, _yaw, _pitch = self.run_steps(120, moving=False)
        distance = math.hypot(eye.x, eye.z)
        self.assertLess(distance, 220, 'camera drifted out toward the old 260')
        self.assertGreater(distance, 90, 'camera collapsed onto the player')

    def test_settles_between_dist_min_and_max(self):
        stopped, _e, _y, _p = self.run_steps(200, moving=False)
        self.assertEqual(stopped.distance, 125)
        running, _e, _y, _p = self.run_steps(200, moving=True)
        self.assertEqual(running.distance, 188)

    def test_pitch_output_is_negative_so_the_view_looks_down(self):
        """The eye is raised, so the view must look down to stay on Link.

        kokiri_camera_update() adds for Up, so positive pitch looks up. A sign
        error here puts Link off the bottom of the screen.
        """
        _cam, _eye, _yaw, pitch = self.run_steps(120)
        self.assertLess(pitch, 0)

    def test_link_is_framed_on_screen_at_both_distances(self):
        """Project Link's feet and head and require both inside 0..240.

        This is the check that would have caught the shipped framing bug: the
        at-point was applied to demo_link.y, which is his EYE at floor+90, not
        his origin, so the camera aimed 90 units high and his feet projected to
        screen y 375. Everything else about the camera still passed.

        main.c: sy = 120 + SCREEN_DISTANCE * (camera_y - point_y) / depth.
        """
        SCREEN_DISTANCE, EYE_HEIGHT, LINK_HEIGHT = 240, 90, 62
        for moving in (False, True):
            cam, eye, _yaw, _pitch = self.run_steps(200, moving=moving)
            depth = math.hypot(eye.x, eye.z)
            for height, part in ((0, 'feet'), (LINK_HEIGHT, 'head')):
                point_y = height - EYE_HEIGHT     # relative to demo_link.y
                sy = 120 + SCREEN_DISTANCE * (eye.y - point_y) / depth
                self.assertGreater(sy, 0, '%s above the screen at d=%d'
                                   % (part, cam.distance))
                self.assertLess(sy, 240, '%s below the screen at d=%d'
                                % (part, cam.distance))

    def test_at_point_targets_the_feet_not_the_eye(self):
        """OoT aims at the player origin; demo_link.y is 90 units above it."""
        source = (ROOT.parent / 'shared/lib/camera/oot_follow.c').read_text()
        self.assertIn('OOT_CAM_PLAYER_ORIGIN', source)

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
