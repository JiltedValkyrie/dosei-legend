"""Saturn pad -> OoT control mapping (approved 2026-09-18).

Executes the real player_input.c, kokiri_camera.c and oot_follow.c on the host.
These checks cover the MAPPING and its consumption rules only: they say nothing
about how the camera feels in Kronos, which still needs player confirmation.
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

# Normalized CAMERA_* bits from shared/lib/camera/kokiri_camera.h.
L, Z, Y, X, R, B, C, A = 0x0008, 0x0010, 0x0020, 0x0040, 0x0080, 0x0100, 0x0200, 0x0400
UP, DOWN, LEFT, RIGHT = 0x1000, 0x2000, 0x4000, 0x8000
# player_c_button_t
C_NONE, C_UP, C_DOWN, C_LEFT, C_RIGHT = range(5)


class Position(ctypes.Structure):
    _fields_ = [(axis, ctypes.c_int32) for axis in ('x', 'y', 'z')]


@unittest.skipUnless(GCC.is_file() and (ROOT / 'build/generated/link_clips.c').is_file(),
                     'host compiler and generated clips required')
class PlayerControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'controls.dll'
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
        cls.lib.control_sample.argtypes = [ctypes.c_uint16]
        cls.lib.control_step.argtypes = [ctypes.c_bool]
        cls.lib.control_tap.argtypes = [ctypes.c_uint16, ctypes.c_int]
        cls.lib.control_move_buttons.restype = ctypes.c_uint16
        cls.lib.control_look_yaw.restype = ctypes.c_int32
        cls.lib.control_look_pitch.restype = ctypes.c_int32
        cls.lib.kokiri_camera_update.argtypes = [ctypes.POINTER(Position),
            ctypes.POINTER(ctypes.c_uint16), ctypes.POINTER(ctypes.c_int32),
            ctypes.c_uint16, ctypes.c_bool, ctypes.c_bool]
        cls.lib.look_drive.argtypes = [ctypes.c_int, ctypes.c_int32,
                                       ctypes.c_int32]
        cls.lib.look_yaw.restype = ctypes.c_int32
        cls.lib.look_pitch.restype = ctypes.c_int32
        cls.lib.look_eye.argtypes = [ctypes.POINTER(Position),
            ctypes.POINTER(Position), ctypes.POINTER(ctypes.c_uint16),
            ctypes.POINTER(ctypes.c_int32)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.lib.control_reset()

    def hold(self, bits, steps=1, in_gameplay=True):
        """Hold `bits` across `steps` fixed steps, sampling once per step."""
        for _ in range(steps):
            self.lib.control_sample(bits)
            self.lib.control_step(in_gameplay)

    def tap(self, bits, vblanks=8, in_gameplay=True):
        """Press and release across `vblanks` VBlanks, then run one step."""
        self.lib.control_tap(bits, vblanks)
        self.lib.control_step(in_gameplay)

    # --- button mapping ---------------------------------------------------

    def test_menu_blocks_world_and_consumes_attack_jump_look(self):
        self.lib.player_input_set_dialogue(True)
        self.hold(UP | X | Y | Z | R | B)
        for field in ('move_buttons', 'attack', 'jump', 'shield', 'look_mode'):
            self.assertEqual(getattr(self.lib, 'control_' + field)(), 0, field)
        self.assertFalse(self.lib.control_walking())
        self.lib.player_input_set_dialogue(False)
        self.hold(0)
        self.assertFalse(self.lib.control_attack())
        self.assertFalse(self.lib.control_jump())

    def test_y_is_jump_and_a_is_not(self):
        self.tap(Y)
        self.assertTrue(self.lib.control_jump())
        self.assertFalse(self.lib.control_interact())
        self.lib.control_reset()
        self.tap(A)
        self.assertFalse(self.lib.control_jump())
        self.assertTrue(self.lib.control_interact())

    def test_x_is_attack_and_not_jump_or_interact(self):
        self.tap(X)
        self.assertTrue(self.lib.control_attack())
        self.assertFalse(self.lib.control_jump())
        self.assertFalse(self.lib.control_interact())

    def test_r_is_shield_only(self):
        self.hold(R)
        self.assertTrue(self.lib.control_shield())
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertFalse(self.lib.control_look_mode())

    def test_l_recenters_on_a_press_edge(self):
        self.tap(L)
        self.assertTrue(self.lib.control_recenter())
        # Holding L must not recenter every step.
        self.hold(L, steps=5)
        self.assertFalse(self.lib.control_recenter())

    # --- B walk/run toggle ------------------------------------------------

    def test_gameplay_starts_in_run_mode(self):
        self.hold(UP)
        self.assertFalse(self.lib.control_walking())

    def test_b_toggles_walk_and_run_once_per_press(self):
        self.tap(B)
        self.assertTrue(self.lib.control_walking())
        self.tap(B)
        self.assertFalse(self.lib.control_walking())

    def test_held_b_does_not_repeat_the_toggle(self):
        self.hold(B, steps=30)
        self.assertTrue(self.lib.control_walking())

    def test_short_b_tap_survives_a_slow_frame(self):
        # One VBlank down, many VBlanks up, and only then a rendered frame.
        self.tap(B, vblanks=20)
        self.assertTrue(self.lib.control_walking())

    def test_walk_mode_is_persistent_across_steps(self):
        self.tap(B)
        self.hold(UP, steps=10)
        self.assertTrue(self.lib.control_walking())

    # --- Y jump edges and rejection ---------------------------------------

    def test_short_y_tap_survives_a_slow_frame(self):
        self.tap(Y, vblanks=20)
        self.assertTrue(self.lib.control_jump())

    def test_held_y_does_not_retrigger(self):
        self.lib.control_sample(Y)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_jump())
        self.hold(Y, steps=30)
        self.assertFalse(self.lib.control_jump())

    def test_released_y_rearms(self):
        self.tap(Y)
        self.assertTrue(self.lib.control_jump())
        self.tap(Y)
        self.assertTrue(self.lib.control_jump())

    def test_a_menu_that_owns_the_pad_gets_cursor_confirm_and_cancel(self):
        """The file select relies on exactly this. It is not "in gameplay" --
        Link does not exist yet -- so it has to be passed in_gameplay=True and
        claim the pad, or player_input_step() zeroes every action and returns
        early. Getting this wrong made A, B and the D-pad do nothing on the
        file select while the screen itself drew correctly."""
        self.lib.player_input_set_dialogue(True)
        self.tap(A)
        self.assertTrue(self.lib.control_interact())
        self.tap(B)
        self.assertTrue(self.lib.control_cancel())
        # B must not also flip walk/run while a menu owns it.
        self.assertFalse(self.lib.control_walking())
        self.tap(DOWN)
        self.assertEqual(1, self.lib.control_menu_step())
        self.tap(UP)
        self.assertEqual(-1, self.lib.control_menu_step())
        self.lib.player_input_set_dialogue(False)

    def test_not_in_gameplay_yields_no_menu_input_at_all(self):
        """Why the caller must pass in_gameplay=True for a menu: with it false
        the early return discards these even though the pad was claimed."""
        self.lib.player_input_set_dialogue(True)
        self.lib.control_tap(A, 4)
        self.lib.control_step(False)
        self.assertFalse(self.lib.control_interact())
        self.lib.control_tap(DOWN, 4)
        self.lib.control_step(False)
        self.assertEqual(0, self.lib.control_menu_step())
        self.lib.player_input_set_dialogue(False)

    def test_title_input_is_discarded_not_queued(self):
        self.lib.control_tap(Y, 4)
        self.lib.control_step(False)          # still on the title
        self.assertFalse(self.lib.control_jump())
        self.lib.control_step(True)           # first gameplay step
        self.assertFalse(self.lib.control_jump())

    def test_y_is_consumed_in_look_mode_not_queued(self):
        self.lib.control_sample(Z | Y)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_jump())
        self.hold(0)
        self.assertFalse(self.lib.control_jump())

    # --- modifier priority and consumption --------------------------------

    def test_c_consumes_the_dpad(self):
        self.hold(C | UP)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertEqual(self.lib.control_c_held(), C_UP)

    def test_z_consumes_the_dpad(self):
        self.hold(Z | LEFT)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertTrue(self.lib.control_look_mode())

    def test_z_outranks_c(self):
        self.hold(Z | C | RIGHT)
        self.assertTrue(self.lib.control_look_mode())
        self.assertEqual(self.lib.control_c_held(), C_NONE)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_move_buttons(), 0)

    def test_c_outranks_movement(self):
        self.hold(C | DOWN)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertEqual(self.lib.control_c_held(), C_DOWN)

    def test_modifier_entered_while_direction_held_stops_movement(self):
        self.hold(UP, steps=3)
        self.assertEqual(self.lib.control_move_buttons(), UP)
        self.hold(C | UP)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.hold(Z | UP)
        self.assertEqual(self.lib.control_move_buttons(), 0)

    def test_releasing_modifier_resumes_movement_without_phantom_action(self):
        self.hold(C | UP, steps=3)
        self.hold(UP)
        self.assertEqual(self.lib.control_move_buttons(), UP)
        self.assertEqual(self.lib.control_c_held(), C_NONE)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        # The direction is still down, so it must not read as a new C press on
        # any later step either.
        self.hold(UP, steps=5)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_move_buttons(), UP)

    def test_leaving_c_reports_the_release_so_held_items_cannot_stick(self):
        self.hold(C | LEFT, steps=2)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)  # already down
        self.hold(0)
        self.assertEqual(self.lib.control_c_released(), C_LEFT)

    # --- literal C direction mapping --------------------------------------

    def test_c_directions_map_literally(self):
        for bit, expected in ((UP, C_UP), (DOWN, C_DOWN),
                              (LEFT, C_LEFT), (RIGHT, C_RIGHT)):
            self.lib.control_reset()
            self.hold(C | bit)
            self.assertEqual(self.lib.control_c_pressed(), expected)
            self.assertEqual(self.lib.control_c_held(), expected)

    def test_held_c_direction_does_not_repeat_its_press(self):
        self.hold(C | UP)
        self.assertEqual(self.lib.control_c_pressed(), C_UP)
        self.hold(C | UP, steps=20)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_c_held(), C_UP)

    def test_c_press_survives_a_slow_frame(self):
        self.lib.control_sample(C | RIGHT)
        for _ in range(12):
            self.lib.control_sample(C)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_c_pressed(), C_RIGHT)

    # --- Z look mode ------------------------------------------------------

    def test_look_aims_with_the_dpad_and_moves_nothing(self):
        # Looking RIGHT DECREASES yaw. With the camera's +Y-up, +Z-forward
        # convention, screen right is (f x up) = -X, so increasing yaw swings
        # the view left. This assertion used to expect the opposite, from when
        # the renderer itself was mirrored; see main.c's screen X flip.
        self.hold(Z | RIGHT)
        self.assertLess(self.lib.control_look_yaw(), 0)
        self.lib.control_reset()
        self.hold(Z | LEFT)
        self.assertGreater(self.lib.control_look_yaw(), 0)
        self.lib.control_reset()
        self.hold(Z | RIGHT)
        self.assertEqual(self.lib.control_look_pitch(), 0)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.lib.control_reset()
        self.hold(Z | UP)
        self.assertGreater(self.lib.control_look_pitch(), 0)
        self.hold(Z | DOWN)
        self.assertLess(self.lib.control_look_pitch(), 0)

    def test_look_never_raises_the_shield(self):
        self.hold(Z | R | UP)
        self.assertTrue(self.lib.control_look_mode())
        self.assertFalse(self.lib.control_shield())

    def test_releasing_z_exits_look_mode_once(self):
        self.hold(Z | UP, steps=3)
        self.hold(0)
        self.assertFalse(self.lib.control_look_mode())
        self.assertTrue(self.lib.control_look_exited())
        self.hold(0)
        self.assertFalse(self.lib.control_look_exited())

    def test_look_aim_is_bounded(self):
        self.lib.look_reset()
        self.lib.look_drive(600, 420, 280)
        self.assertEqual(self.lib.look_yaw(), 16384)
        self.assertEqual(self.lib.look_pitch(), 12000)
        self.lib.look_drive(600, -420, -280)
        self.assertEqual(self.lib.look_yaw(), -16384)
        self.assertEqual(self.lib.look_pitch(), -12000)

    def test_look_exit_restores_the_plain_follow_view_exactly(self):
        player = Position(100, 90, 200)
        eye, yaw, pitch = Position(), ctypes.c_uint16(), ctypes.c_int32()
        self.lib.look_reset()
        # Settle first: the follow distance eases toward distMin while he
        # stands still, so an unsettled baseline would differ for reasons that
        # have nothing to do with look mode.
        for _ in range(200):
            self.lib.look_eye(ctypes.byref(player), ctypes.byref(eye),
                              ctypes.byref(yaw), ctypes.byref(pitch))
        plain = (eye.x, eye.y, eye.z, yaw.value, pitch.value)
        self.lib.look_drive(10, 420, 280)
        self.assertTrue(self.lib.look_active())
        self.lib.look_eye(ctypes.byref(player), ctypes.byref(eye),
                          ctypes.byref(yaw), ctypes.byref(pitch))
        self.assertNotEqual((eye.x, eye.z, yaw.value), plain[0:2] + plain[3:4])
        self.lib.look_exit()
        self.assertFalse(self.lib.look_active())
        self.lib.look_eye(ctypes.byref(player), ctypes.byref(eye),
                          ctypes.byref(yaw), ctypes.byref(pitch))
        self.assertEqual((eye.x, eye.y, eye.z, yaw.value, pitch.value), plain)

    # --- walk/run travel --------------------------------------------------

    def travel(self, buttons, yaw=0, steps=300):
        self.lib.kokiri_camera_reset_actor_motion()
        p, angle, pitch = Position(), ctypes.c_uint16(yaw), ctypes.c_int32()
        for _ in range(steps):
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), buttons, False, True)
        return math.hypot(p.x, p.z)

    def test_run_mode_keeps_the_native_child_speed(self):
        self.tap(0)                 # stay in run
        self.assertEqual(self.travel(UP), 1650)

    def test_walk_mode_is_slower_than_run(self):
        self.tap(B)
        self.assertTrue(self.lib.control_walking())
        self.assertEqual(self.travel(UP), 900)   # 3 units/step for 10 s

    def test_walk_diagonals_are_normalized(self):
        self.tap(B)
        for buttons, yaw in ((UP, 0), (UP | RIGHT, 0), (UP, 8192),
                             (UP | RIGHT, 5000)):
            self.assertAlmostEqual(self.travel(buttons, yaw), 900, delta=4)

    def test_run_diagonals_are_still_normalized(self):
        self.tap(0)
        for buttons, yaw in ((UP, 0), (UP | RIGHT, 0), (UP | RIGHT, 5000)):
            self.assertAlmostEqual(self.travel(buttons, yaw), 1650, delta=4)

    def test_walk_speed_selects_the_walk_clip_from_actual_travel(self):
        """Animation must follow real movement, not the held button."""
        self.lib.kokiri_camera_reset_actor_motion()
        self.tap(B)
        p, angle, pitch = Position(), ctypes.c_uint16(), ctypes.c_int32()
        self.lib.link_anim_reset_state()
        for _ in range(60):
            before = (p.x, p.z)
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), UP, False, True)
            moved = int(math.hypot(p.x - before[0], p.z - before[1]))
            self.lib.link_anim_update(moved, True, 0, False)
        self.assertEqual(self.lib.link_anim_state(), 1)   # LINK_STATE_WALK
        self.lib.control_reset()
        self.lib.kokiri_camera_reset_actor_motion()
        for _ in range(60):
            before = (p.x, p.z)
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), UP, False, True)
            moved = int(math.hypot(p.x - before[0], p.z - before[1]))
            self.lib.link_anim_update(moved, True, 0, False)
        self.assertEqual(self.lib.link_anim_state(), 2)   # LINK_STATE_RUN

    # --- shoulders never orbit -------------------------------------------

    def test_shoulders_never_orbit_the_gameplay_camera(self):
        for buttons in (L, R, L | R, L | UP, R | UP, Z | R):
            p, angle, pitch = Position(), ctypes.c_uint16(4321), ctypes.c_int32()
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), buttons, False, True)
            self.assertEqual(angle.value, 4321, hex(buttons))

    def test_shoulders_are_not_routed_into_movement_or_look(self):
        for buttons in (L, R, L | R):
            self.lib.control_reset()
            self.hold(buttons, steps=2)
            self.assertEqual(self.lib.control_move_buttons(), 0, hex(buttons))
            self.assertFalse(self.lib.control_look_mode(), hex(buttons))

    # --- source guards ----------------------------------------------------

    def test_jump_is_wired_to_y_not_a_in_demo(self):
        text = (ROOT / 'src/demo.c').read_text()
        self.assertNotIn('JO_KEY_A', text)
        self.assertIn('if (in_gameplay && input.jump) jump_pending = true;',
                      text)

    def test_pending_actions_are_recorded_not_substituted(self):
        text = (ROOT / 'src/demo.c').read_text()
        self.assertIn('++demo_interact_requests', text)
        self.assertIn('++demo_attack_requests', text)

    def test_diagnostics_chord_is_gated_out_of_the_clean_build(self):
        text = (ROOT / 'src/player_input.c').read_text()
        chord = text.split('#ifndef DOSEI_CLEAN_TEST', 1)[1]
        self.assertIn('CAMERA_L', chord.split('#endif', 1)[0])


if __name__ == '__main__':
    unittest.main()
