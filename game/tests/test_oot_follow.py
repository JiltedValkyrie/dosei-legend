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
    # Must match oot_follow_t exactly, in order: a mismatch silently reads
    # the wrong field rather than failing.
    _fields_ = [('distance', ctypes.c_int32), ('yaw', ctypes.c_uint16),
                ('pitch', ctypes.c_int32), ('initialised', ctypes.c_bool),
                ('swing_timer', ctypes.c_int32),
                ('look_yaw', ctypes.c_int32), ('look_pitch', ctypes.c_int32),
                ('look_active', ctypes.c_bool), ('targeting', ctypes.c_bool),
                ('aim_q8', ctypes.c_int32 * 3), ('aim_focus', ctypes.c_int32 * 3),
                ('aim_distance', ctypes.c_int32),
                ('aim_active', ctypes.c_bool), ('aim_off_ground', ctypes.c_bool)]


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
                        '-I' + str(ROOT / 'src'),
                        str(camera / 'oot_follow.c'),
                        str(camera / 'kokiri_camera.c'),
                        str(ROOT / 'src/player_input.c'),
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

    def setUp(self):
        self.lib.oot_follow_set_adult(False)

    def test_adult_uses_source_height_scale_and_keeps_feet_origin(self):
        self.lib.oot_follow_set_adult(True)
        still, eye, _, pitch = self.run_steps(150, moving=False, player=Position(0,90,0))
        moving, _, _, _ = self.run_steps(150, moving=True, player=Position(0,90,0))
        self.assertEqual(still.distance,136)
        self.assertEqual(moving.distance,204)
        rise=still.distance*math.sin(still.pitch*2*math.pi/65536)
        self.assertAlmostEqual(eye.y-rise,68-14,delta=1)
        self.lib.oot_follow_set_adult(False)
        child, _, _, _ = self.run_steps(150,moving=True,player=Position(0,90,0))
        self.assertEqual(child.distance,139)

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

    def test_lock_turns_behind_stationary_link_then_tracks_every_step(self):
        cam,eye=Follow(),Position()
        player=Position(0,90,0)
        yaw,pitch=ctypes.c_uint16(),ctypes.c_int32()
        self.lib.oot_follow_snap(ctypes.byref(cam),ctypes.byref(player),0)
        self.lib.oot_follow_look(ctypes.byref(cam),5000,5000)
        self.lib.oot_follow_target(ctypes.byref(cam),True)
        self.assertFalse(cam.look_active)
        for i in range(6):
            self.lib.oot_follow_update(ctypes.byref(cam),ctypes.byref(player),16384,False,
                                      ctypes.byref(eye),ctypes.byref(yaw),ctypes.byref(pitch))
            if i == 0: self.assertTrue(0 < yaw.value < 16384)
        self.assertEqual(yaw.value,16384)
        self.assertLess(eye.x,player.x)
        self.assertLessEqual(abs(eye.z-player.z),1)
        # Track across a wrap/large heading change; Normal1 rear-half hold must
        # not apply, whether moving or standing. Eye stays behind facing.
        for heading,moving in ((50000,True),(65000,False),(500,True)):
            player.x += 10
            self.lib.oot_follow_update(ctypes.byref(cam),ctypes.byref(player),heading,moving,
                                      ctypes.byref(eye),ctypes.byref(yaw),ctypes.byref(pitch))
            self.assertEqual(yaw.value,heading)
            a=heading*2*math.pi/65536
            dot=(eye.x-player.x)*math.sin(a)+(eye.z-player.z)*math.cos(a)
            self.assertLess(dot,-90)
        self.lib.oot_follow_target(ctypes.byref(cam),False)
        self.lib.oot_follow_update(ctypes.byref(cam),ctypes.byref(player),16000,False,
                                  ctypes.byref(eye),ctypes.byref(yaw),ctypes.byref(pitch))
        self.assertEqual(yaw.value,500) # release resumes ordinary idle hold

    def run_lock(self, focus, distance, off_ground=False, steps=20):
        cam, eye = Follow(), Position()
        player = Position(0, 90, 0)                    # feet 0, head 44
        yaw, pitch = ctypes.c_uint16(), ctypes.c_int32()
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0)
        self.lib.oot_follow_target(ctypes.byref(cam), True)
        f = (ctypes.c_int32 * 3)(*focus) if focus else None
        for _ in range(steps):
            self.lib.oot_follow_aim(ctypes.byref(cam), f,
                                    distance, off_ground)
            self.lib.oot_follow_update(ctypes.byref(cam), ctypes.byref(player), 0, False,
                                      ctypes.byref(eye), ctypes.byref(yaw), ctypes.byref(pitch))
        return cam, eye, yaw.value, pitch.value

    def test_lock_aim_shifts_toward_a_close_target_focus(self):
        """Camera_CalcAtForLockOn: v * (0.75 - 0.6 |v| / d) inside d."""
        cam, eye, yaw, pitch = self.run_lock((0, 44 + 60, 80), 180)   # |v| = 100
        scale = 0.75 - 0.6 * 100 / 180
        self.assertAlmostEqual(cam.aim_q8[1] / 256, 60 * scale, delta=1.5)
        self.assertAlmostEqual(cam.aim_q8[2] / 256, 80 * scale, delta=1.5)

    def test_lock_aim_is_fifteen_percent_past_the_mode_distance(self):
        cam = self.run_lock((0, 44, 400), 120)[0]
        self.assertAlmostEqual(cam.aim_q8[2] / 256, 400 * 0.15, delta=1.5)

    def test_lock_aim_off_ground_is_a_fifth(self):
        cam = self.run_lock((0, 44, 400), 120, off_ground=True)[0]
        self.assertAlmostEqual(cam.aim_q8[2] / 256, 400 * 0.03, delta=1.5)

    def _offset_after(self, focus, distance, steps):
        cam, eye, yaw, pitch = self.run_lock(focus, distance, steps=steps)
        at = [cam.aim_q8[0] / 256, 44 + cam.aim_q8[1] / 256, cam.aim_q8[2] / 256]
        target = math.degrees(math.atan2(focus[0] - at[0], focus[2] - at[2]))
        view = yaw * 360 / 65536
        return (target - view + 180) % 360 - 180, cam

    def test_keepon1_moves_a_dead_ahead_target_off_centre(self):
        """KeepOn1: standing still, a target straight ahead drifts to the
        swing angle (25..45 deg) instead of hiding behind Link."""
        off, cam = self._offset_after((0, 44, 100), 120, 600)
        # distRatio 100/120: swing = 25 + 20 * (1.1 - 0.833) = 30.3 deg.
        self.assertAlmostEqual(abs(off), 30.3, delta=1.5)
        self.assertGreaterEqual(cam.distance, 120)
        self.assertLessEqual(cam.distance, 140)

    def test_battle1_uses_its_own_swing_and_distance(self):
        off, cam = self._offset_after((0, 44, 300), 180, 600)
        # distRatio 1: swing = 10 + 70 * 0.1 = 17 deg; eyeDist 180.
        self.assertAlmostEqual(abs(off), 17, delta=1.5)
        self.assertEqual(cam.distance, 180)

    def test_far_off_centre_target_turns_the_view_toward_it(self):
        cam = Follow()
        off, _ = self._offset_after((300, 44, 0), 120, 1)
        off2, _ = self._offset_after((300, 44, 0), 120, 40)
        self.assertLess(abs(off2), abs(off))

    def test_lock_aim_eases_back_after_release(self):
        cam, eye, _, _ = self.run_lock((0, 162, 0), 180)
        player = Position(0, 90, 0)
        yaw, pitch = ctypes.c_uint16(), ctypes.c_int32()
        self.lib.oot_follow_target(ctypes.byref(cam), False)
        for _ in range(30):
            self.lib.oot_follow_aim(ctypes.byref(cam), None, 0, False)
            self.lib.oot_follow_update(ctypes.byref(cam), ctypes.byref(player), 0, False,
                                      ctypes.byref(eye), ctypes.byref(yaw), ctypes.byref(pitch))
        self.assertEqual(list(cam.aim_q8), [0, 0, 0])

    def test_distance_matches_the_scaled_decomp_values(self):
        """200/300 raw, scaled by Player_GetHeight's child 44 (BUG-009:
        Link now draws at the source 0.01 scale, 44 units tall).

        yNormal = 1 + (-0.1) - (-0.1 * 68/44) = 1.05455
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
        self.assertLess(distance, 220, 'camera drifted out toward the old 260')
        self.assertGreater(distance, 90, 'camera collapsed onto the player')

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

    def test_link_is_framed_on_screen_at_both_distances(self):
        """Project through camera pitch too, not a fictitious level camera."""
        SCREEN_DISTANCE, EYE_HEIGHT, LINK_HEIGHT = 240, 90, 44
        for moving in (False, True):
            cam, eye, _yaw, _pitch = self.run_steps(200, moving=moving)
            depth = math.hypot(eye.x, eye.z)
            for height, part in ((0, 'feet'), (LINK_HEIGHT, 'head')):
                point_y = height - EYE_HEIGHT     # relative to recomp_link.y
                angle = -_pitch * 2 * math.pi / 65536
                dy = eye.y - point_y
                view_y = dy * math.cos(angle) - depth * math.sin(angle)
                view_z = dy * math.sin(angle) + depth * math.cos(angle)
                sy = 120 + SCREEN_DISTANCE * view_y / view_z
                self.assertGreater(sy, 0, '%s above the screen at d=%d'
                                   % (part, cam.distance))
                self.assertLess(sy, 240, '%s below the screen at d=%d'
                                % (part, cam.distance))

    def test_at_point_includes_player_height(self):
        """Actual decomp: origin + Player_GetHeight() + yOffset."""
        for moving in (False, True):
            cam, eye, _yaw, _pitch = self.run_steps(200, moving=moving)
            rise = int(cam.distance * math.sin(cam.pitch * 2 * math.pi / 65536))
            self.assertAlmostEqual(eye.y + 90 - rise, 44 - 9, delta=1)

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

    def test_running_toward_camera_does_not_chase_opposite_facing(self):
        for facing in (0x7fff, 0x8000, 0x8001, 0x6000, 0xa000):
            _cam, _eye, yaw, _pitch = self.run_steps(120, facing=facing, moving=True)
            self.assertEqual(yaw, 0, 'rearward motion spun camera')


    def swing(self, target, steps):
        """Recenter from yaw 0 toward `target`, standing still."""
        self.lib.oot_follow_recenter.argtypes = [ctypes.POINTER(Follow)]
        cam, eye = Follow(), Position()
        yaw, pitch = ctypes.c_uint16(), ctypes.c_int32()
        player = Position(0, 0, 0)
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0)
        self.lib.oot_follow_recenter(ctypes.byref(cam))
        seen = []
        for _ in range(steps):
            self.lib.oot_follow_update(
                ctypes.byref(cam), ctypes.byref(player), target, False,
                ctypes.byref(eye), ctypes.byref(yaw), ctypes.byref(pitch))
            seen.append(yaw.value)
        return seen

    def test_recenter_does_not_cut_on_the_first_step(self):
        """A snap would arrive immediately; the turn must not."""
        self.assertNotEqual(self.swing(0x4000, 1)[0], 0x4000,
                            'recenter cut instead of turning')

    def test_recenter_uses_parallel1_timing_not_normal1(self):
        """Z-recenter is Camera_Parallel1, not Normal1's idle swing.

        sSetNormal0ModeZParallelData sets PARALLEL1_FLAG_3 | PARALLEL1_FLAG_1
        and not FLAG_2, so animTimer is CAM_DEFAULT_ANIM_TIME = 4 at OoT's
        20 Hz -- 0.2 s, which is 6 steps at our 30 Hz. Normal1's
        CAM_GLOBAL_50 + CAM_GLOBAL_51 is the camera drifting back behind a
        player who has STOPPED: a different behaviour entirely.
        """
        header = (ROOT.parent / 'shared/lib/camera/oot_follow.h').read_text()
        self.assertIn('OOT_CAM_SWING_STEPS     6', header)

    def test_recenter_completes_within_the_parallel1_window(self):
        """Six steps, not thirty: the turn must be finished by then."""
        self.assertEqual(self.swing(0x4000, 6)[-1], 0x4000,
                         'turn did not finish inside animTimer')

    def test_recenter_eases_out(self):
        """Each step must cover LESS than the previous one.

        Camera_Parallel1 divides by the triangular number of the remaining
        steps and multiplies by the countdown, so the steps shrink. A plain
        diff/remaining -- which this used to do -- is a constant share of a
        shrinking remainder, i.e. a linear turn with no ease at all.
        """
        seen = self.swing(0x4000, 6)
        deltas = [seen[0]] + [b - a for a, b in zip(seen, seen[1:])]
        moving = [d for d in deltas if d > 0]
        self.assertGreater(len(moving), 2, 'turn finished too fast to judge')
        for previous, current in zip(moving, moving[1:]):
            self.assertLess(current, previous,
                            'steps did not shrink: %s' % (deltas,))

    def test_recenter_does_not_overshoot(self):
        seen = self.swing(0x4000, 8)
        for previous, current in zip(seen, seen[1:]):
            self.assertGreaterEqual(current, previous)
            self.assertLessEqual(current, 0x4000)

    def test_recenter_turns_while_standing_still(self):
        """Ordinary yaw follow is gated on movement; the recenter is not."""
        self.assertEqual(self.swing(0x4000, 8)[-1], 0x4000)

    def test_snap_is_immediate(self):
        """Recenter and void recovery must not ease; both call snap."""
        cam = Follow()
        player = Position(0, 0, 0)
        self.lib.oot_follow_snap(ctypes.byref(cam), ctypes.byref(player), 0x2000)
        self.assertEqual(cam.yaw, 0x2000)
        self.assertTrue(cam.initialised)


if __name__ == '__main__':
    unittest.main()


class BehindCameraCulling(unittest.TestCase):
    """Polygons entirely behind the camera must not be submitted.

    The depth cull only removed distant geometry: anything behind the camera
    has negative depth, so the nearest-vertex test kept it and the whole rear
    hemisphere within 1310 units was transformed and submitted every frame for
    SGL to reject. That cost is paid on the title screen too, where Link is not
    drawn at all.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'src' / 'kokiri_sgl.c').read_text()

    def test_cull_uses_the_farthest_vertex_for_the_behind_test(self):
        """Nearest-vertex would drop polygons straddling the camera plane."""
        self.assertIn('farthest < 0', self.source)

    def test_far_cull_still_uses_the_nearest_vertex(self):
        """A polygon partly inside the draw distance must still be drawn."""
        self.assertIn('nearest > FOREST_FAR', self.source)

    def test_cull_decision_table(self):
        """The two tests together, over the cases that matter."""
        FAR = 4367 * 6 // 10 // 2
        def culled(depths):
            return max(depths) < 0 or min(depths) > FAR
        self.assertTrue(culled([-500, -400, -450, -480]), 'fully behind')
        self.assertFalse(culled([-100, 50, -20, 30]), 'straddles the plane')
        self.assertFalse(culled([200, 300, 250, 280]), 'in front')
        self.assertTrue(culled([1400, 1500, 1450, 1480]), 'beyond draw distance')
        self.assertFalse(culled([1200, 1400, 1300, 1350]), 'partly in range')


class FrameTimerWrapping(unittest.TestCase):
    """The FRT is 16-bit; a slow frame wraps it more than once."""

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'src' / 'frame_timer.c').read_text()

    def test_prescaler_is_set_explicitly(self):
        """Inheriting the SDK's prescaler leaves the wrap period unknown."""
        self.assertIn('FRT_TCR = FRT_PRESCALER_128', self.source)

    def test_counter_is_extended_past_sixteen_bits(self):
        """At /8 a 125 ms frame wraps three times and reports the remainder."""
        self.assertIn('0x10000u', self.source)

    def test_unaccounted_time_is_reported(self):
        """Timing only suspected phases cannot explain a frame."""
        self.assertIn('frame_timer_other', self.source)




class CameraStepTiming(unittest.TestCase):
    """The camera must advance per fixed step, not per draw.

    OoT's easing rates are defined per update. Driving the camera from the
    draw callback makes every rate frame-rate dependent: a 6-step turn is
    0.2 s at 30 Hz but 0.75 s at 8 FPS. Skinning is the opposite case --
    it is expensive and purely visual, so it stays outside the loop and runs
    at most once per frame.
    """

    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / 'src' / 'recomp.c').read_text()

    def step_loop(self):
        body = self.source.split('while (steps--) {', 1)[1]
        depth, end = 0, None
        for index, character in enumerate(body):
            if character == '{':
                depth += 1
            elif character == '}':
                if depth == 0:
                    end = index
                    break
                depth -= 1
        self.assertIsNotNone(end, 'could not find the end of the step loop')
        return body[:end]

    def test_camera_updates_inside_the_step_loop(self):
        self.assertIn('player_camera_update', self.step_loop(),
                      'camera easing would be frame-rate dependent')

    def test_camera_updates_only_inside_the_step_loop(self):
        """A second call per draw would double-advance the easing."""
        self.assertEqual(self.source.count('oot_follow_update('), 1,
                         'only the spawn snap bypasses traversal camera selection')
        self.assertEqual(self.source.count('player_camera_update('),
                         self.step_loop().count('player_camera_update('),
                         'water/land camera calls must stay in the fixed-step loop')

    def test_skinning_stays_outside_the_step_loop(self):
        self.assertNotIn('link_anim_pose', self.step_loop(),
                         'skinning must not run once per catch-up step')


class VdpLabelHonesty(unittest.TestCase):
    """The COPR reading must not be presented as a busy measurement.

    Two adjacent reads can both land inside one long command, the sample
    happens after the wait it is meant to explain, and a positive reading
    proves only that some command advanced. None of that supports a
    CPU-versus-fill verdict, so the label must not imply one.
    """

    @classmethod
    def setUpClass(cls):
        camera = ROOT / 'src'
        cls.header = (camera / 'frame_timer.h').read_text()
        cls.main = (camera / 'main.c').read_text()

    def test_accessor_is_not_named_busy(self):
        self.assertIn('frame_timer_copr_changed', self.header)
        self.assertNotIn('frame_timer_vdp1_busy', self.header)

    def test_overlay_label_says_copr_not_busy(self):
        self.assertIn('copr%u%%', self.main)
        self.assertNotIn('vd%u%%', self.main)

    def test_header_records_why_it_cannot_measure_busy(self):
        """So the limitation travels with the code, not just a commit."""
        self.assertIn('deliberately NOT called "busy"', self.header)
        self.assertIn('CEF', self.header)
