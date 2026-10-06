"""Saturn pad -> OoT control mapping (C-Up view owns look axes; Z targets).

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
        self.lib.player_input_set_jump_button(Y)
        self.lib.control_reset()

    def test_custom_jump_replaces_gameplay_button_but_not_menu_confirm(self):
        self.lib.player_input_set_jump_button(A)
        self.tap(A)
        self.assertTrue(self.lib.control_jump())
        self.assertFalse(self.lib.control_interact())
        self.lib.player_input_set_dialogue(True)
        self.tap(A)
        self.assertFalse(self.lib.control_jump())
        self.assertTrue(self.lib.control_interact())

    def test_camera_chord_once_and_partial_release_does_not_cancel_or_guard(self):
        self.lib.control_sample(L|R|B)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_camera_experiment())

        for held in (L|R|B, L|R|B, R|B, B, 0):
            self.lib.control_sample(held)
            self.lib.control_step(True)
            self.assertFalse(self.lib.control_camera_experiment())
            self.assertFalse(self.lib.control_cancel())
            self.assertFalse(self.lib.control_shield())
            self.assertFalse(self.lib.control_map_toggle())
        self.lib.control_sample(L|R|B)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_camera_experiment())

    def test_orbit_z_edges_and_reverse_do_not_target_or_cancel(self):
        self.lib.player_input_set_orbit(True)
        for keys,direction in ((Z,1),(Z,0),(0,0),(B|Z,-1),(B|Z,0),(B,0),(0,0)):
            self.lib.control_sample(keys);self.lib.control_step(True)
            self.assertEqual(self.lib.control_orbit_turn(),direction)
            self.assertFalse(self.lib.control_cancel())
            self.assertFalse(self.lib.control_target_held())

    def test_camera_chord_short_tap_latched_but_menu_and_title_discarded(self):
        self.lib.control_sample(L|R|B)
        self.lib.control_sample(0)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_camera_experiment())
        self.lib.control_sample(L|R|B)
        self.lib.control_step(False)
        self.lib.control_sample(0)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_camera_experiment())
        self.lib.player_input_set_dialogue(True)
        self.lib.control_sample(L|R|B)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_camera_experiment())

    def test_custom_jump_and_reset_default_do_not_change_target_hold(self):
        self.lib.player_input_set_jump_button(C)
        self.hold(Z | C)
        self.assertTrue(self.lib.control_jump())
        self.assertTrue(self.lib.control_target_held())
        self.lib.player_input_set_jump_button(Y)
        self.hold(0)
        self.tap(Y)
        self.assertTrue(self.lib.control_jump())

    def test_pause_c_chord_assigns_without_moving_cursor(self):
        for direction, assigned in ((DOWN, C_DOWN), (LEFT, C_LEFT), (RIGHT, C_RIGHT)):
            self.lib.control_reset()
            self.lib.player_input_set_dialogue(True)
            self.hold(C | direction)
            self.assertEqual(self.lib.control_c_pressed(), assigned)
            self.assertEqual(self.lib.control_menu_step(), 0)
            self.assertEqual(self.lib.control_move_buttons(), 0)
            self.lib.control_step(True)
            self.assertEqual(self.lib.control_c_pressed(), C_NONE)

    def test_pause_assign_short_tap_survives_release_before_step(self):
        self.lib.player_input_set_dialogue(True)
        self.lib.control_sample(C | LEFT)
        self.lib.control_sample(0)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_c_pressed(), C_LEFT)
        self.assertEqual(self.lib.control_menu_step(), 0)

    def test_attack_tap_retains_release_edge(self):
        self.lib.control_sample(X)
        self.lib.control_sample(0)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_attack(), 1)
        self.assertEqual(self.lib.control_attack_held(), 0)
        self.assertEqual(self.lib.control_attack_released(), 1)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_attack_released(), 0)

    def test_title_consumes_attack_edges_but_exposes_physical_hold(self):
        self.hold(X, in_gameplay=False)
        self.assertEqual(self.lib.control_attack(), 0)
        self.assertEqual(self.lib.control_attack_held(), 1)
        self.hold(0, in_gameplay=False)
        self.assertEqual(self.lib.control_attack_released(), 0)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_attack(), 0)
        self.assertEqual(self.lib.control_attack_released(), 0)

    def hold(self, bits, steps=1, in_gameplay=True):
        """Hold `bits` across `steps` fixed steps, sampling once per step."""
        for _ in range(steps):
            self.lib.control_sample(bits)
            self.lib.control_step(in_gameplay)

    def tap(self, bits, vblanks=8, in_gameplay=True):
        """Press and release across `vblanks` VBlanks, then run one step."""
        self.lib.control_tap(bits, vblanks)
        self.lib.control_step(in_gameplay)

    def analog(self, bits=0, x=128, y=128):
        self.lib.player_input_sample_pad(bits, True, x, y)
        self.lib.control_step(True)

    def test_3d_trigger_axes_act_as_shoulders_and_release(self):
        sample = self.lib.player_input_sample_3d
        sample.argtypes = [ctypes.c_uint16, ctypes.c_bool] + [ctypes.c_uint8] * 4
        for right, left in ((255, 0), (0, 255), (255, 255), (128, 128),
                            (0, 0), (127, 127), (144, 144)):
            sample(0, True, 128, 128, right, left)
            self.lib.control_step(True)
            self.assertEqual(self.lib.control_shield(), right >= 176)
            self.assertFalse(self.lib.control_look_mode())
        sample(0, False, 128, 128, 255, 255)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_shield())
        self.assertFalse(self.lib.control_look_mode())
        sample(L | R, True, 128, 128, 0, 0)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_shield())
        self.assertFalse(self.lib.control_look_mode())

    def test_trigger_deadzone_and_hysteresis_release_camera(self):
        sample = self.lib.player_input_sample_3d
        sample.argtypes = [ctypes.c_uint16, ctypes.c_bool] + [ctypes.c_uint8] * 4
        for value, pressed in ((128, False), (136, False), (175, False),
                               (176, True), (160, True), (145, True),
                               (144, False), (150, False), (128, False)):
            sample(0, True, 128, 128, 0, value)
            self.lib.control_step(True)
            self.assertFalse(self.lib.control_look_mode())

    def test_light_tilt_turns_without_translation(self):
        self.analog(x=180)  # mapped strength 41: turn only
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.assertEqual(self.lib.control_motion_heading(0), 49152)
        self.analog(x=181)  # last turn-only strength: 42
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.analog(x=182)  # mapped strength 43: movement
        self.assertGreater(self.lib.control_motion_speed(), 0)
        self.lib.link_anim_turn.argtypes = [ctypes.c_bool, ctypes.c_uint16,
                                          ctypes.POINTER(ctypes.c_uint16)]
        self.lib.link_anim_reset_state()
        facing = ctypes.c_uint16(0)
        self.lib.link_anim_turn(True, 49152, ctypes.byref(facing))
        self.assertEqual(facing.value, 65536 - 800)
        self.assertEqual(self.lib.link_anim_state(), 14)
        for _ in range(30):
            self.lib.link_anim_turn(True, 49152, ctypes.byref(facing))
        self.assertEqual(facing.value, 49152)
        self.assertEqual(self.lib.link_anim_state(), 0)
        self.lib.link_anim_turn(True, 50000, ctypes.byref(facing))
        self.lib.link_anim_turn(False, 0, ctypes.byref(facing))
        self.assertEqual(self.lib.link_anim_state(), 0)

    def test_analog_deadzone_and_proportional_speed(self):
        for x, y in ((128, 128), (140, 138), (128, 112)):
            self.analog(x=x, y=y)
            self.assertEqual(self.lib.control_motion_speed(), 0)
        self.analog(y=64)
        half = self.lib.control_motion_speed()
        self.assertGreater(half, 0)
        self.analog(y=0)
        self.assertEqual(self.lib.control_motion_speed(), 1408)
        self.assertLess(half, 1408)
        self.analog(x=255, y=0)
        self.assertLessEqual(self.lib.control_motion_speed(), 1408)
        self.assertGreater(self.lib.control_motion_speed(), 1380)

    def test_analog_handedness_and_continuous_heading(self):
        for x, y, heading in ((128, 0, 0), (255, 128, 49152),
                               (0, 128, 16384), (128, 255, 32768)):
            self.analog(x=x, y=y)
            self.assertEqual(self.lib.control_motion_heading(0), heading)
            self.assertEqual(self.lib.control_motion_heading(16384), (heading + 16384) & 65535)
        self.analog(x=160, y=0)
        heading = self.lib.control_motion_heading(0)
        self.assertGreater(heading, 57344)
        self.assertLess(heading, 65536)

    def test_analog_c_and_stick_together_then_menu(self):
        self.analog(LEFT | Y | Z, y=0)
        self.assertEqual(self.lib.control_c_pressed(), C_LEFT)
        self.assertEqual(self.lib.control_move_buttons(), UP)
        self.assertTrue(self.lib.control_jump())
        self.assertTrue(self.lib.control_target_held())
        self.lib.player_input_set_dialogue(True)
        self.analog()
        self.analog(DOWN, y=0)
        self.assertEqual(self.lib.control_menu_step(), 1)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.lib.player_input_set_dialogue(False)
        self.analog(DOWN)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_motion_speed(), 0)

    def test_analog_look_and_digital_reconnect(self):
        self.lib.player_input_set_view_look(True)
        self.analog(L, x=255)
        self.assertEqual(self.lib.control_look_yaw(), -420)
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.lib.player_input_set_view_look(False)
        self.hold(0)
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.hold(RIGHT)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_motion_heading(0), 49152)

    def test_analog_c_tap_survives_slow_frame_and_disconnect(self):
        self.lib.player_input_sample_pad(RIGHT, True, 128, 128)
        self.lib.player_input_sample_pad(0, True, 128, 128)
        self.lib.control_step(True)
        self.assertEqual(self.lib.control_c_pressed(), C_RIGHT)
        self.assertEqual(self.lib.control_c_released(), C_RIGHT)
        self.analog(UP, y=0)
        self.hold(0)
        self.assertEqual(self.lib.control_motion_speed(), 0)
        self.assertEqual(self.lib.control_c_released(), C_UP)

    def test_analog_walk_cap_and_menu_owns_debug_chord(self):
        self.analog(B, y=0)
        self.assertEqual(self.lib.control_motion_speed(), 768)
        self.lib.player_input_set_dialogue(True)
        self.analog(L | R | UP)
        self.assertEqual(self.lib.control_menu_step(), -1)
        self.assertEqual(self.lib.control_c_pressed(), C_NONE)
        self.assertEqual(self.lib.control_motion_speed(), 0)

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

    def test_a_held_and_stick_pushed_for_the_ledge_hang(self):
        """Player_Action_8084BBE4 reads A held (let go) and a stick pushed
        55 of 60 (pull up); digital directions are full throw."""
        self.hold(A, steps=3)
        self.assertTrue(self.lib.control_interact_held())
        self.assertFalse(self.lib.control_stick_pushed())
        self.hold(0)
        self.assertFalse(self.lib.control_interact_held())
        self.hold(UP)
        self.assertTrue(self.lib.control_stick_pushed())
        self.analog(y=64)                 # half throw
        self.assertFalse(self.lib.control_stick_pushed())
        self.analog(y=0)                  # full throw
        self.assertTrue(self.lib.control_stick_pushed())
        self.analog()
        self.assertFalse(self.lib.control_stick_pushed())

    def test_r_is_shield_only(self):
        self.hold(R)
        self.assertTrue(self.lib.control_shield())
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertFalse(self.lib.control_look_mode())

    def test_z_recenters_on_a_press_edge(self):
        self.tap(Z)
        self.assertTrue(self.lib.control_recenter())
        # Holding Z must not recenter every step.
        self.hold(Z, steps=5)
        self.assertFalse(self.lib.control_recenter())

    # --- B: hold walks, tap cancels / puts the item away -------------------

    def test_gameplay_starts_in_run_mode(self):
        self.hold(UP)
        self.assertFalse(self.lib.control_walking())

    def test_held_b_walks_and_release_returns_to_run(self):
        self.hold(B, steps=30)
        self.assertTrue(self.lib.control_walking())
        self.hold(0)
        self.assertFalse(self.lib.control_walking())

    def test_held_b_does_not_cancel(self):
        self.hold(B, steps=30)
        self.assertFalse(self.lib.control_cancel())
        self.hold(0)
        self.assertFalse(self.lib.control_cancel())

    def test_short_b_tap_cancels_once_on_release(self):
        self.lib.control_sample(B)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_cancel())
        self.lib.control_sample(0)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_cancel())
        self.hold(0)
        self.assertFalse(self.lib.control_cancel())

    def test_short_b_tap_survives_a_slow_frame(self):
        self.tap(B, vblanks=20)
        self.assertTrue(self.lib.control_cancel())

    def test_b_press_that_closes_a_box_does_not_act_again_on_release(self):
        self.lib.player_input_set_dialogue(True)
        self.lib.control_sample(B)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_cancel())
        self.lib.player_input_set_dialogue(False)     # the box closed
        self.hold(B, steps=30)
        self.assertFalse(self.lib.control_walking())  # claimed press never walks
        self.assertFalse(self.lib.control_cancel())
        self.hold(0)
        self.assertFalse(self.lib.control_cancel())   # no put-away on release

    def test_b_press_in_first_person_view_is_claimed(self):
        self.lib.player_input_set_view_look(True)
        self.lib.control_sample(B)
        self.lib.control_step(True)
        self.assertTrue(self.lib.control_cancel())
        self.lib.player_input_set_view_look(False)
        self.hold(0)
        self.assertFalse(self.lib.control_cancel())

    def test_claimed_b_survives_a_slow_frame(self):
        self.lib.player_input_set_dialogue(True)
        self.tap(B, vblanks=20)                       # press+release, one step
        self.assertTrue(self.lib.control_cancel())
        self.lib.player_input_set_dialogue(False)
        self.hold(0)
        self.assertFalse(self.lib.control_cancel())

    def test_next_b_tap_after_a_claimed_press_works(self):
        self.lib.player_input_set_dialogue(True)
        self.tap(B)
        self.lib.player_input_set_dialogue(False)
        self.hold(0)
        self.tap(B)
        self.assertTrue(self.lib.control_cancel())

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
        self.lib.player_input_set_view_look(True)
        self.lib.control_sample(L | Y)
        self.lib.control_step(True)
        self.assertFalse(self.lib.control_jump())
        self.hold(0)
        self.assertFalse(self.lib.control_jump())

    # --- modifier priority and consumption --------------------------------

    def test_c_consumes_the_dpad(self):
        self.hold(C | UP)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertEqual(self.lib.control_c_held(), C_UP)

    def test_digital_c_up_keeps_a_held_z_lock(self):
        # Human report: on the digital pad, C + Up while holding Z dropped
        # the lock, so C-Up on a locked enemy never reached Navi.
        self.hold(Z)
        self.hold(Z | C | UP)
        self.assertTrue(self.lib.control_target_held())
        self.assertEqual(self.lib.control_c_held(), C_UP)
        self.assertEqual(self.lib.control_move_buttons(), 0)

    def test_look_consumes_the_dpad(self):
        self.lib.player_input_set_view_look(True)
        self.hold(L | LEFT)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.assertTrue(self.lib.control_look_mode())

    def test_target_keeps_the_dpad_for_strafing(self):
        # Z does NOT consume the direction: holding it strafes and backs up
        # around the facing, so the movement bits must still come through.
        self.hold(Z | LEFT)
        self.assertEqual(self.lib.control_move_buttons(), LEFT)
        self.assertTrue(self.lib.control_target_held())
        self.assertFalse(self.lib.control_look_mode())

    def test_c_release_survives_aim_view_without_movement(self):
        self.hold(C | DOWN)
        self.lib.player_input_set_view_look(True)
        self.hold(0)
        self.assertEqual(self.lib.control_c_released(), C_DOWN)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.hold(0)
        self.assertEqual(self.lib.control_c_released(), C_NONE)

    def test_look_outranks_c(self):
        self.lib.player_input_set_view_look(True)
        self.hold(L | C | RIGHT)
        self.assertTrue(self.lib.control_look_mode())
        self.assertEqual(self.lib.control_c_held(), C_NONE)
        self.assertEqual(self.lib.control_c_pressed(), C_RIGHT)
        self.assertTrue(self.lib.control_look_exited())
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
        self.hold(L | UP)
        self.assertEqual(self.lib.control_move_buttons(), UP)

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

    # --- L look mode ------------------------------------------------------

    def test_look_aims_with_the_dpad_and_moves_nothing(self):
        self.lib.player_input_set_view_look(True)
        # Looking RIGHT DECREASES yaw. With the camera's +Y-up, +Z-forward
        # convention, screen right is (f x up) = -X, so increasing yaw swings
        # the view left. This assertion used to expect the opposite, from when
        # the renderer itself was mirrored; see main.c's screen X flip.
        self.hold(L | RIGHT)
        self.assertLess(self.lib.control_look_yaw(), 0)
        self.lib.control_reset()
        self.lib.player_input_set_view_look(True)
        self.hold(L | LEFT)
        self.assertGreater(self.lib.control_look_yaw(), 0)
        self.lib.control_reset()
        self.lib.player_input_set_view_look(True)
        self.hold(L | RIGHT)
        self.assertEqual(self.lib.control_look_pitch(), 0)
        self.assertEqual(self.lib.control_move_buttons(), 0)
        self.lib.control_reset()
        self.lib.player_input_set_view_look(True)
        self.hold(L | UP)
        self.assertGreater(self.lib.control_look_pitch(), 0)
        self.hold(L | DOWN)
        self.assertLess(self.lib.control_look_pitch(), 0)

    def test_look_never_raises_the_shield(self):
        self.lib.player_input_set_view_look(True)
        self.hold(L | R)
        self.assertTrue(self.lib.control_look_mode())
        self.assertFalse(self.lib.control_shield())

    def test_releasing_look_exits_look_mode_once(self):
        self.lib.player_input_set_view_look(True)
        self.hold(L | UP, steps=3)
        self.lib.player_input_set_view_look(False)
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
        self.hold(B)
        self.assertTrue(self.lib.control_walking())
        self.assertEqual(self.travel(UP), 900)   # 3 units/step for 10 s

    def test_walk_diagonals_are_normalized(self):
        self.hold(B)
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
        self.hold(B)
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

    def test_slow_travel_rounding_does_not_define_facing(self):
        # At a shallow angle the fixed-point remainder emits different whole-
        # unit deltas each step. Both digital walk and analog creep must retain
        # their requested heading rather than feeding those deltas to the camera.
        self.lib.kokiri_camera_move_heading.argtypes = [
            ctypes.POINTER(Position), ctypes.c_uint16, ctypes.c_int32]
        for analog in (False, True):
            self.lib.control_reset()
            self.lib.kokiri_camera_reset_actor_motion()
            if analog:
                self.analog(y=64)  # above the turn-only band
            else:
                self.hold(B | UP)
            p = Position()
            heading = self.lib.control_motion_heading(5000)
            speed = self.lib.control_motion_speed()
            rounded_headings = set()
            for _ in range(120):
                before = (p.x, p.z)
                self.lib.kokiri_camera_move_heading(ctypes.byref(p), heading, speed)
                dx, dz = p.x - before[0], p.z - before[1]
                if dx or dz:
                    rounded_headings.add(round(math.atan2(dx, dz) * 65536 / math.tau))
                self.assertEqual(self.lib.control_motion_heading(5000), heading)
            self.assertGreater(len(rounded_headings), 1)
            self.assertGreater(max(rounded_headings) - min(rounded_headings), 3000)

    def test_recomp_faces_input_not_quantized_displacement(self):
        text = (ROOT / 'src/recomp.c').read_text()
        self.assertNotIn('kokiri_camera_facing(recomp_link.x - step_x', text)
        self.assertIn('player_input_motion(&input, recomp_yaw, &recomp_link_yaw,', text)
        self.assertIn('walk && roll_speed <= 0 &&', text)

    # --- shoulders never orbit -------------------------------------------

    def test_shoulders_never_orbit_the_gameplay_camera(self):
        for buttons in (L, R, L | R, L | UP, R | UP, Z | R, Z | UP):
            p, angle, pitch = Position(), ctypes.c_uint16(4321), ctypes.c_int32()
            self.lib.kokiri_camera_update(ctypes.byref(p), ctypes.byref(angle),
                ctypes.byref(pitch), buttons, False, True)
            self.assertEqual(angle.value, 4321, hex(buttons))

    def test_shoulders_never_translate_link(self):
        # L aims and R guards; neither is a movement button. L DOES enter look
        # mode now, so only translation is asserted here.
        for buttons in (L, R, L | R):
            self.lib.control_reset()
            self.hold(buttons, steps=2)
            self.assertEqual(self.lib.control_move_buttons(), 0, hex(buttons))

    def test_diagnostics_chord_leaves_plain_look_plus_guard_alone(self):
        self.lib.control_reset()
        self.hold(L | R, steps=2)
        self.assertFalse(self.lib.control_look_mode())
        self.assertTrue(self.lib.control_shield())

    # --- source guards ----------------------------------------------------

    def test_jump_is_wired_to_y_not_a_in_recomp(self):
        text = (ROOT / 'src/recomp.c').read_text()
        self.assertNotIn('JO_KEY_A', text)
        self.assertIn('if (in_gameplay && input.jump) jump_pending = true;',
                      text)

    def test_pending_actions_are_recorded_not_substituted(self):
        text = (ROOT / 'src/recomp.c').read_text()
        self.assertIn('++recomp_interact_requests', text)
        self.assertIn('++recomp_attack_requests', text)

    def test_diagnostics_chord_is_gated_out_of_the_clean_build(self):
        text = (ROOT / 'src/player_input.c').read_text()
        chord = text.split('#ifndef DOSEI_CLEAN_TEST', 1)[1]
        chord = chord.split('#endif', 1)[0]
        self.assertIn('CAMERA_L', chord)
        # A direction is required, or the chord would eat look-plus-guard.
        self.assertIn('CAMERA_UP | CAMERA_DOWN', chord)


if __name__ == '__main__':
    unittest.main()
