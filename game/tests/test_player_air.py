"""M1b: source gravity, the automatic ledge jump and its animation.

Real C: player_air.c (func_8083AA10 / func_8083A4A8 rules), kokiri_collision.c,
kokiri_camera.c movement, link_anim_state.c + generated clips.
"""

import ctypes
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
GEN = ROOT / 'build/generated'
FOREST = ROOT / 'build/cd/S1.COL'

LEAVE_FALL, LEAVE_REVERT_XZ, LEAVE_REVERT_STOP, LEAVE_JUMP, LEAVE_RUN_JUMP, LEAVE_HANG = range(6)
STATE = dict(IDLE=0, WALK=1, RUN=2, FALL=3, LANDING=4, ROLL=5, JUMP=6, JUMP_LANDING=7)
RUN_Q8, WALK_Q8 = 1408, 768
EYE = 90


class Leave(ctypes.Structure):
    _fields_ = [('ground_leave', ctypes.c_bool), ('swinging', ctypes.c_bool),
                ('prev_floor_property', ctypes.c_uint8), ('y_dist_to_floor', ctypes.c_int32),
                ('speed_q8', ctypes.c_int32), ('yaw_diff', ctypes.c_int16)]


class Vec(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int32), ('y', ctypes.c_int32), ('z', ctypes.c_int32)]


class Triangle(ctypes.Structure):
    _fields_ = [('vertex', (ctypes.c_int16 * 3) * 3), ('normal', ctypes.c_int16 * 3),
                ('minimum', ctypes.c_int16 * 3), ('maximum', ctypes.c_int16 * 3)]


def flat(x0, x1, z0, z1, y):
    out = []
    for vs in (((x0, y, z0), (x1, y, z1), (x1, y, z0)), ((x0, y, z0), (x0, y, z1), (x1, y, z1))):
        t = Triangle()
        for i, v in enumerate(vs):
            t.vertex[i][:] = v
        t.normal[:] = (0, 16384, 0)
        t.minimum[:] = (min(x0, x1), y, min(z0, z1))
        t.maximum[:] = (max(x0, x1), y, max(z0, z1))
        out.append(t)
    return out


def clip_ids():
    header = (GEN / 'link_clips.h').read_text()
    return {m[0]: int(m[1]) for m in re.findall(r'#\s*define\s+LINK_CLIP_(\w+)\s+(\d+)', header)}


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file(),
                     'host compiler and generated clips required')
class PlayerAir(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'air.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        collision = ROOT.parent / 'shared/lib/collision'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-o', str(out),
                        '-I' + str(camera), '-I' + str(collision), '-I' + str(ROOT / 'src'),
                        '-I' + str(GEN),
                        str(ROOT / 'src/player_air.c'), str(collision / 'kokiri_collision.c'),
                        str(camera / 'kokiri_camera.c'), str(ROOT / 'src/link_anim_state.c'),
                        str(GEN / 'link_clips.c'), str(ROOT / 'tests/fixtures/traversal_host.c'),
                        '-lm'], check=True, env=env)
        lib = cls.lib = ctypes.CDLL(str(out))
        P = ctypes.POINTER
        lib.player_leave_ground.argtypes = [P(Leave), P(ctypes.c_int32)]
        lib.player_leave_ground.restype = ctypes.c_int
        lib.kokiri_collision_init.argtypes = [P(Triangle), ctypes.c_uint32]
        lib.kokiri_collision_fall.argtypes = [P(Vec), P(ctypes.c_int32), P(ctypes.c_int32)]
        lib.kokiri_collision_fall.restype = ctypes.c_bool
        lib.kokiri_collision_jump.argtypes = lib.kokiri_collision_fall.argtypes
        lib.kokiri_collision_jump.restype = ctypes.c_bool
        lib.kokiri_collision_floor.argtypes = [ctypes.c_int32] * 3 + [P(ctypes.c_int32)]
        lib.kokiri_collision_floor.restype = ctypes.c_bool
        lib.kokiri_camera_move_heading.argtypes = [P(Vec), ctypes.c_uint16, ctypes.c_int32]
        lib.link_anim_update.argtypes = [ctypes.c_int32, ctypes.c_bool, ctypes.c_int32,
                                         ctypes.c_bool]
        lib.link_anim_auto_jump.argtypes = [ctypes.c_bool]
        lib.link_anim_set_air.argtypes = [ctypes.c_bool]
        lib.link_anim_state.restype = ctypes.c_int
        lib.link_anim_clip.restype = ctypes.c_uint
        lib.link_anim_frame.restype = ctypes.c_uint
        cls.clips = clip_ids()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def leave(self, **kw):
        args = dict(ground_leave=True, swinging=False, prev_floor_property=0,
                    y_dist_to_floor=100, speed_q8=RUN_Q8, yaw_diff=0)
        args.update(kw)
        velocity = ctypes.c_int32(0)
        act = self.lib.player_leave_ground(ctypes.byref(Leave(**args)), ctypes.byref(velocity))
        return act, velocity.value

    # ---- func_8083AA10 / func_8083A4A8 rules ----
    def test_running_off_a_ledge_run_jumps_at_7_5(self):
        self.assertEqual(self.leave(), (LEAVE_RUN_JUMP, 1920))      # IREG(67) 7.5

    def test_launch_speed_below_5_4_scales_with_speed(self):
        # 1.25 + 0.4 * speed (IREG(68), IREG(69) child boots)
        act, v = self.leave(speed_q8=5 * 256)
        self.assertEqual((act, v), (LEAVE_RUN_JUMP, 320 + 512))
        act, v = self.leave(speed_q8=1382)                           # not > 5.4
        self.assertEqual(v, 320 + 1382 * 400 // 1000)
        act, v = self.leave(speed_q8=1383)
        self.assertEqual(v, 1920)

    def test_run_jump_needs_speed_over_4_and_yaw_under_0x1000(self):
        self.assertEqual(self.leave(speed_q8=4 * 256)[0], LEAVE_JUMP)
        self.assertEqual(self.leave(speed_q8=4 * 256 + 1)[0], LEAVE_RUN_JUMP)
        self.assertEqual(self.leave(yaw_diff=0x0FFF)[0], LEAVE_RUN_JUMP)
        self.assertEqual(self.leave(yaw_diff=0x1000)[0], LEAVE_JUMP)
        self.assertEqual(self.leave(yaw_diff=-0x1000)[0], LEAVE_JUMP)

    def test_no_auto_jump_when_slow_sideways_shallow_or_on_no_jump_floor(self):
        self.assertEqual(self.leave(speed_q8=3 * 256)[0], LEAVE_HANG)    # not > 3
        self.assertEqual(self.leave(speed_q8=WALK_Q8, y_dist_to_floor=30)[0], LEAVE_FALL)
        self.assertEqual(self.leave(yaw_diff=0x2000)[0], LEAVE_HANG)
        self.assertEqual(self.leave(y_dist_to_floor=20)[0], LEAVE_FALL)
        self.assertEqual(self.leave(y_dist_to_floor=21)[0], LEAVE_RUN_JUMP)
        self.assertEqual(self.leave(prev_floor_property=6)[0], LEAVE_HANG)
        self.assertEqual(self.leave(prev_floor_property=9)[0], LEAVE_FALL)

    def test_floor_properties_7_8_and_swinging_block_leaving(self):
        self.assertEqual(self.leave(prev_floor_property=8)[0], LEAVE_REVERT_XZ)
        self.assertEqual(self.leave(prev_floor_property=7)[0], LEAVE_REVERT_STOP)
        self.assertEqual(self.leave(swinging=True)[0], LEAVE_REVERT_STOP)

    def test_hang_request_only_below_child_unk_34(self):
        self.assertEqual(self.leave(speed_q8=0, y_dist_to_floor=45)[0], LEAVE_FALL)
        self.assertEqual(self.leave(speed_q8=0, y_dist_to_floor=46)[0], LEAVE_HANG)

    # ---- gravity (TRAVERSAL_TIMING.md) ----
    def test_free_fall_is_source_gravity_and_terminal(self):
        self.lib.kokiri_collision_init(None, 0)
        link, velocity, remainder = Vec(0, 5000, 0), ctypes.c_int32(0), ctypes.c_int32(0)
        seen = []
        for _ in range(40):
            self.lib.kokiri_collision_fall(ctypes.byref(link), ctypes.byref(velocity),
                                           ctypes.byref(remainder))
            seen.append(velocity.value)
        self.assertEqual(seen[:3], [-171, -342, -513])      # -1.0 x 2/3 per step
        self.assertEqual(seen[-1], -5120)                   # minVelocityY -20

    # ---- animation ----
    def anim_reset(self):
        self.lib.link_anim_reset_state()
        self.lib.link_anim_update(0, True, 0, False)        # spawn landing
        for _ in range(40):
            self.lib.link_anim_update(0, True, 0, False)
        self.assertEqual(self.lib.link_anim_state(), STATE['IDLE'])

    def test_run_jump_holds_then_lands_with_run_jump_end(self):
        self.anim_reset()
        self.lib.link_anim_auto_jump(True)
        for _ in range(30):
            self.lib.link_anim_set_air(False)
            self.lib.link_anim_update(5, False, 0, False)
        self.assertEqual(self.lib.link_anim_state(), STATE['JUMP'])
        self.assertEqual(self.lib.link_anim_clip(), self.clips['RUN_JUMP'])
        self.assertEqual(self.lib.link_anim_frame(), 12)    # held on the last frame
        self.lib.link_anim_update(5, True, 150, False)      # would roll otherwise
        self.assertEqual(self.lib.link_anim_state(), STATE['JUMP_LANDING'])
        self.assertEqual(self.lib.link_anim_clip(), self.clips['RUN_JUMP_END'])

    def test_descending_below_departure_switches_to_fall_and_normal_landing(self):
        self.anim_reset()
        self.lib.link_anim_auto_jump(True)
        self.lib.link_anim_set_air(False)
        self.lib.link_anim_update(5, False, 0, False)
        self.lib.link_anim_set_air(True)
        self.lib.link_anim_update(5, False, 0, False)
        self.assertEqual(self.lib.link_anim_state(), STATE['FALL'])
        self.lib.link_anim_update(5, True, 150, False)      # 80 < fall < 800, moving
        self.assertEqual(self.lib.link_anim_state(), STATE['ROLL'])

    def test_standing_jump_clip_and_short_landing(self):
        self.anim_reset()
        self.lib.link_anim_auto_jump(False)
        self.lib.link_anim_update(4, False, 0, False)
        self.assertEqual(self.lib.link_anim_clip(), self.clips['JUMP'])
        self.lib.link_anim_update(0, True, 10, False)
        self.assertEqual(self.lib.link_anim_state(), STATE['LANDING'])

    # ---- walking off a real edge: collision + rules together ----
    def run_off(self, triangles, start, heading, speed_q8, steps=120):
        """Mirror of recomp.c's step order around a departure."""
        tris = (Triangle * len(triangles))(*triangles)
        self.lib.kokiri_collision_init(tris, len(triangles))
        link = Vec(*start)
        velocity, remainder = ctypes.c_int32(0), ctypes.c_int32(0)
        on_ground, departure, events, apex = True, link.y, [], link.y
        floor = ctypes.c_int32()
        for _ in range(steps):
            before = (link.x, link.z)
            self.lib.kokiri_camera_move_heading(ctypes.byref(link), heading, speed_q8)
            standing = (self.lib.kokiri_collision_floor(link.x, link.z, link.y - EYE + 4,
                                                        ctypes.byref(floor))
                        and link.y == floor.value + EYE)
            if on_ground and velocity.value == 0 and not standing:
                feet = link.y - EYE
                ydist = (feet - floor.value) if self.lib.kokiri_collision_floor(
                    link.x, link.z, feet, ctypes.byref(floor)) else 32000
                act, launch = self.leave(y_dist_to_floor=ydist, speed_q8=speed_q8)
                events.append((act, launch, ydist))
                if act in (LEAVE_JUMP, LEAVE_RUN_JUMP):
                    velocity.value, remainder.value = launch, 0
                elif act in (LEAVE_REVERT_XZ, LEAVE_REVERT_STOP):
                    link.x, link.z = before
            grounded = self.lib.kokiri_collision_fall(ctypes.byref(link), ctypes.byref(velocity),
                                                      ctypes.byref(remainder))
            apex = max(apex, link.y)
            if grounded and not on_ground:
                return link, events, departure - link.y, apex - departure
            if grounded:
                departure = link.y
            on_ground = grounded
        return link, events, None, apex - departure

    def test_running_off_a_60_unit_step_jumps_then_lands_below(self):
        tris = flat(-200, 100, -200, 200, 60) + flat(100, 800, -200, 200, 0)
        link, events, fell, rise = self.run_off(tris, (0, 60 + EYE, 0), 0x4000, RUN_Q8)
        self.assertEqual(events[0][:2], (LEAVE_RUN_JUMP, 1920))
        self.assertEqual(fell, 60)                          # departure - landing
        self.assertGreater(rise, 20, 'auto-jump rises before falling')
        self.assertGreater(link.x, 150, 'carried forward by the jump')

    def test_walking_off_a_30_unit_step_just_falls(self):
        tris = flat(-200, 100, -200, 200, 30) + flat(100, 800, -200, 200, 0)
        link, events, fell, rise = self.run_off(tris, (0, 30 + EYE, 0), 0x4000, WALK_Q8)
        self.assertEqual(events[0][0], LEAVE_FALL)
        self.assertEqual(fell, 30)
        self.assertEqual(rise, 0)

    def test_small_step_down_is_followed_not_a_departure(self):
        tris = flat(-200, 100, -200, 200, 10) + flat(100, 800, -200, 200, 0)
        link, events, fell, _ = self.run_off(tris, (0, 10 + EYE, 0), 0x4000, RUN_Q8, steps=60)
        self.assertEqual(events, [])                        # 11-unit ground follow
        self.assertEqual(link.y, EYE)


if __name__ == '__main__':
    unittest.main()
