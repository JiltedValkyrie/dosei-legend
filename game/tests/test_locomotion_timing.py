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
                        '-I' + str(ROOT / 'src'),
                        '-I' + str(ROOT / 'build/generated'),
                        str(camera / 'kokiri_camera.c'),
                        str(camera / 'oot_follow.c'),
                        str(ROOT / 'src/player_input.c'),
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
        cls.lib.link_anim_roll_speed_q8.restype = ctypes.c_int32
        cls.lib.link_anim_roll_input.argtypes = [ctypes.c_int32, ctypes.c_bool]
        cls.lib.kokiri_camera_input_heading.argtypes = [ctypes.c_uint16,
            ctypes.c_uint16, ctypes.POINTER(ctypes.c_uint16)]
        cls.lib.kokiri_camera_move_heading.argtypes = [ctypes.POINTER(Position),
            ctypes.c_uint16, ctypes.c_int32]

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
        self.assertIn('input_edge_consume(&start_edge', text)
        # Start now hands the title over to the file select rather than going
        # straight to the forest, so the guarded line reads differently than it
        # used to. What still matters is that the transition is refused while a
        # score switch is running, or the artwork and the music would disagree
        # about which state we are in.
        self.assertIn('!music_busy()', text)
        self.assertIn('file_select_open()', text)

    def test_the_file_select_is_included_in_the_gameplay_input_gate(self):
        """player_input_step() zeroes every action and returns early when
        in_gameplay is false, AFTER consuming the press edges. The file select
        runs before Link exists, so leaving it out of that gate swallowed A, B
        and the D-pad and nothing on the screen could be chosen -- while the
        screen itself still drew correctly, which made it look like a menu bug.

        This is a source check because the wiring lives in demo.c, which has no
        host harness; the player_input side is covered in test_player_controls.
        """
        text = (ROOT / 'src/demo.c').read_text()
        self.assertIn('demo_link_active || file_select_visible ||', text)
        self.assertIn('game_mode() == GAME_MODE_CUTSCENE', text)
        # They must also claim the pad, or B toggles walk/run instead of
        # cancelling, and A would not advance cutscene text boxes.
        self.assertIn('file_select_visible || game_mode() == GAME_MODE_CUTSCENE',
                      text)

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


    # --- manual roll ------------------------------------------------------

    def settle(self):
        self.lib.link_anim_reset_state()
        for _ in range(50):
            self.lib.link_anim_update(5, True, 0, False)

    RUN_Q8 = 1408
    ROLL_MIN_Q8 = RUN_Q8 // 3

    def test_manual_roll_takes_its_speed_from_the_source_formula(self):
        # z_player.c:9754: 1.5x what locomotion would give, floored at 3.0 --
        # which is a third of a run here. It does NOT decay to a stop; the
        # roll ends because the animation ends.
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(5, True, 0, True)
        self.assertEqual(self.lib.link_anim_state(), 5)  # roll
        self.assertEqual(self.lib.link_anim_roll_speed_q8(), 5 * 256 * 3 // 2)
        speeds = []
        while self.lib.link_anim_state() == 5:
            speeds.append(self.lib.link_anim_roll_speed_q8())
            self.lib.link_anim_update(0, True, 0, False)
        # Held forward the whole way: it approaches the running target and
        # stays there -- never the floor, and never a decay to a stop.
        self.assertEqual(speeds[-1], self.RUN_Q8 * 3 // 2)
        self.assertGreater(min(speeds), self.ROLL_MIN_Q8)
        self.assertEqual(self.lib.link_anim_roll_speed_q8(), 0)

    def test_a_slow_roll_still_gets_the_source_floor(self):
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(1, True, 0, True)
        self.assertEqual(self.lib.link_anim_roll_speed_q8(), self.ROLL_MIN_Q8)

    def test_releasing_the_pad_eases_the_roll_to_the_floor_not_to_a_stop(self):
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(5, True, 0, True)
        self.lib.link_anim_roll_input(self.RUN_Q8, False)
        speeds = []
        while self.lib.link_anim_state() == 5:
            speeds.append(self.lib.link_anim_roll_speed_q8())
            self.lib.link_anim_update(0, True, 0, False)
        self.assertGreater(speeds[0], speeds[-1])
        self.assertEqual(speeds[-1], self.ROLL_MIN_Q8)

    def test_forward_again_restores_the_roll_speed(self):
        # The target is recomputed from the CURRENT input every step, so the
        # speed comes back up; taking the current speed as the target would
        # make every release permanent.
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(5, True, 0, True)
        peak = self.lib.link_anim_roll_speed_q8()
        self.lib.link_anim_roll_input(self.RUN_Q8, False)
        for _ in range(3):
            self.lib.link_anim_update(0, True, 0, False)
        self.assertLess(self.lib.link_anim_roll_speed_q8(), peak)
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        for _ in range(3):
            self.lib.link_anim_update(0, True, 0, False)
        self.assertGreater(self.lib.link_anim_roll_speed_q8(),
                           self.ROLL_MIN_Q8)

    def test_only_forward_input_keeps_the_roll_fast(self):
        # Source drops non-forward input to the floor outright.
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(5, True, 0, True)
        self.lib.link_anim_roll_input(self.RUN_Q8, False)
        while self.lib.link_anim_state() == 5:
            last = self.lib.link_anim_roll_speed_q8()
            self.lib.link_anim_update(0, True, 0, False)
        self.assertEqual(last, self.ROLL_MIN_Q8)

    def test_input_heading_is_measured_against_links_facing(self):
        # A direction is only "forward" when it points where Link is facing;
        # demo.c compares this heading with his yaw.
        heading = ctypes.c_uint16()
        UP, DOWN, LEFT = 0x1000, 0x2000, 0x4000
        self.assertTrue(self.lib.kokiri_camera_input_heading(0, UP,
                                                             ctypes.byref(heading)))
        self.assertEqual(heading.value, 0)
        self.lib.kokiri_camera_input_heading(0, DOWN, ctypes.byref(heading))
        self.assertEqual(heading.value, 32768)          # 180 degrees
        self.lib.kokiri_camera_input_heading(0, LEFT, ctypes.byref(heading))
        self.assertEqual(heading.value, 16384)          # 90 degrees
        self.assertFalse(self.lib.kokiri_camera_input_heading(0, 0,
                                                              ctypes.byref(heading)))


    def test_cancelling_a_roll_stops_its_travel_immediately(self):
        self.settle()
        self.lib.link_anim_roll_input(self.RUN_Q8, True)
        self.lib.link_anim_update(5, True, 0, True)
        self.assertGreater(self.lib.link_anim_roll_speed_q8(), 0)
        self.lib.link_anim_cancel_roll()
        self.assertNotEqual(self.lib.link_anim_state(), 5)
        self.assertEqual(self.lib.link_anim_roll_speed_q8(), 0)


    def test_standing_still_cannot_roll(self):
        self.settle()
        self.lib.link_anim_update(0, True, 0, True)
        self.assertNotEqual(self.lib.link_anim_state(), 5)
        self.assertEqual(self.lib.link_anim_roll_speed_q8(), 0)

    def test_roll_travel_follows_the_heading_through_collision(self):
        for yaw, axis in ((0, 'z'), (16384, 'x')):
            p = Position()
            self.lib.kokiri_camera_reset_actor_motion()
            for _ in range(10):
                self.lib.kokiri_camera_move_heading(ctypes.byref(p), yaw, 1408)
            self.assertGreater(getattr(p, axis), 0, yaw)
            self.assertEqual(getattr(p, 'x' if axis == 'z' else 'z'), 0, yaw)

    def test_a_press_claimed_by_the_world_never_also_rolls(self):
        text = (ROOT / 'src/demo.c').read_text()
        claim = text.split('roll_pending = interact_pending', 1)[1].split(';', 1)[0]
        for event in ('GP_EVENT_TALK_OPEN', 'GP_EVENT_PICKUP',
                      'GP_EVENT_MENU_OPEN', 'GP_EVENT_EQUIP'):
            self.assertIn(event, claim)
        self.assertIn('gameplay_blocks_world()', claim)

    def test_combat_poses_follow_action_clock_and_release(self):
        """gameplay.c owns the attack timeline; the pose is its clip/frame."""
        self.lib.link_anim_reset_state()
        self.lib.link_anim_update(0, True, 0, False)
        idle = self.lib.link_anim_clip()
        for clip, frame in ((10, 0), (10, 3), (11, 5)):
            self.lib.link_anim_combat(True, clip, frame, False)
            self.assertEqual((self.lib.link_anim_clip(), self.lib.link_anim_frame()),
                             (clip, frame))
        self.lib.link_anim_combat(False, 0, 0, False)
        self.assertEqual(self.lib.link_anim_clip(), idle)

        self.lib.link_anim_combat(False, 0, 0, True)
        raising = self.lib.link_anim_clip()
        for _ in range(5):
            self.lib.link_anim_combat(False, 0, 0, True)
        self.assertNotEqual(self.lib.link_anim_clip(), raising)
        self.lib.link_anim_combat(False, 0, 0, False)
        self.assertEqual(self.lib.link_anim_clip(), idle)

    def test_motion_sound_events_do_not_repeat_on_same_frame_or_at_rest(self):
        self.lib.link_anim_reset_state()
        for _ in range(50): self.lib.link_anim_update(0, True, 0, False)
        for _ in range(30):
            self.lib.link_anim_update(0, True, 0, False)
            self.assertEqual(self.lib.link_anim_motion_events(), 0)
        steps = []
        for tick in range(60):
            self.lib.link_anim_update(6, True, 0, False)
            if self.lib.link_anim_motion_events() & (1<<16): steps.append(tick)
        self.assertEqual(len(steps),4)
        self.assertTrue(all(b-a == 15 for a,b in zip(steps,steps[1:])))
        for _ in range(25):
            self.lib.link_anim_update(6, False, 0, False)
            self.assertEqual(self.lib.link_anim_motion_events(),0)

    def test_roll_sounds_fire_once_at_source_frames(self):
        self.lib.link_anim_reset_state()
        self.lib.link_anim_update(0, False, 0, False)
        self.lib.link_anim_update(6, True, 100, False)
        events = []
        for _ in range(35):
            self.lib.link_anim_update(0, True, 0, False)
            flags=self.lib.link_anim_motion_events()
            if flags: events.append((self.lib.link_anim_frame(),flags))
        self.assertEqual(events,[(1,1<<17),(6,1<<15)])

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
