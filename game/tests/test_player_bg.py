"""M1c: source step-up, wall contact, ledge probe and the ground ledge climbs.

Real C: kokiri_collision.c (actor step in Actor_UpdateBgCheckInfo order),
player_bg.c (Player_ProcessSceneCollision wall block, Player_ActionHandler_12),
kokiri_camera.c movement, link_anim_state.c + generated clips.
"""

import ctypes
import math
import os
import pathlib
import re
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
GEN = ROOT / 'build/generated'
EYE = 90
RUN_Q8 = 1408
STATE = dict(IDLE=0, WALK=1, RUN=2, FALL=3, LANDING=4, ROLL=5, JUMP=6,
             JUMP_LANDING=7, STEP_UP=8, JUMP_START=9, HANG=10, PULL_UP=11,
             CLIMB=12, CRAWL=13)
HANG_NONE, HANG_LEDGE, HANG_CLIMB = range(3)
NONE, CLIMB_1, CLIMB_2, CLIMB_3, CLIMB_4 = range(5)
ACT_NONE, ACT_HOP, ACT_STEP100, ACT_STEP150, ACT_JUMP250 = range(5)
BG_SCENE = 50
GP_EVENT_CLIMB_END = 1 << 22


class Vec(ctypes.Structure):
    _fields_ = [('x', ctypes.c_int32), ('y', ctypes.c_int32), ('z', ctypes.c_int32)]


class Hit(ctypes.Structure):
    _fields_ = [('normal', ctypes.c_int16 * 3), ('poly', ctypes.c_uint16),
                ('bg_id', ctypes.c_uint8), ('ignore', ctypes.c_uint8),
                ('conveyor', ctypes.c_uint8), ('data0', ctypes.c_uint32),
                ('data1', ctypes.c_uint32)]


class Bg(ctypes.Structure):
    _fields_ = [('wall', ctypes.c_bool), ('interact', ctypes.c_bool), ('wall_hit', Hit),
                ('wall_yaw', ctypes.c_uint16), ('touched_flags', ctypes.c_uint32),
                ('shape_yaw_to_wall', ctypes.c_uint16), ('world_yaw_to_wall', ctypes.c_uint16),
                ('dist_to_wall', ctypes.c_int32), ('y_dist_to_ledge', ctypes.c_int32),
                ('ledge_type', ctypes.c_uint8), ('delay_timer', ctypes.c_uint8)]


class Triangle(ctypes.Structure):
    _fields_ = [('vertex', (ctypes.c_int16 * 3) * 3), ('normal', ctypes.c_int16 * 3),
                ('minimum', ctypes.c_int16 * 3), ('maximum', ctypes.c_int16 * 3)]


class Mesh(ctypes.Structure):
    _fields_ = [('triangles', ctypes.POINTER(Triangle)), ('triangle_count', ctypes.c_uint32),
                ('info', ctypes.POINTER(ctypes.c_uint16)),
                ('surfaces', ctypes.POINTER(ctypes.c_uint32)), ('surface_count', ctypes.c_uint32),
                ('water', ctypes.c_void_p), ('water_count', ctypes.c_uint32),
                ('cameras', ctypes.c_void_p), ('camera_count', ctypes.c_uint32),
                ('camera_vectors', ctypes.c_void_p), ('camera_vector_count', ctypes.c_uint32)]


def tri(vs, surface=0):
    """Triangle with its Q14 normal from the winding (counter-clockwise seen
    from the front)."""
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vs
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    n = (uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx)
    length = sum(c * c for c in n) ** 0.5
    t = Triangle()
    for i, v in enumerate(vs):
        t.vertex[i][:] = v
    t.normal[:] = tuple(int(round(c * 16384 / length)) for c in n)
    t.minimum[:] = tuple(min(v[k] for v in vs) for k in range(3))
    t.maximum[:] = tuple(max(v[k] for v in vs) for k in range(3))
    return (t, surface)


def quad(a, b, c, d, surface=0):
    return [tri((a, b, c), surface), tri((a, c, d), surface)]


def ground(y=0, x=600, z0=-600, z1=600):
    # Up-facing: seen from above, counter-clockwise in (x, z) with +y up.
    return quad((-x, y, z0), (-x, y, z1), (x, y, z1), (x, y, z0))


def box(h, z0=0, z1=300, x=200, top_rise=0, wall_lean=0, surface=0):
    """A block across the path: front wall at z0 facing -z, top at h."""
    front = quad((-x, 0, z0), (-x, h, z0 + wall_lean), (x, h, z0 + wall_lean), (x, 0, z0),
                 surface)
    top = quad((-x, h, z0 + wall_lean), (-x, h + top_rise, z1), (x, h + top_rise, z1),
               (x, h, z0 + wall_lean))
    return front + top


def wall(z, y0, y1, x=200, surface=0):
    return quad((-x, y0, z), (-x, y1, z), (x, y1, z), (x, y0, z), surface)


def ceiling(y, z0, z1, x=200):
    # Down-facing.
    return quad((-x, y, z0), (x, y, z0), (x, y, z1), (-x, y, z1))


def clip_ids():
    header = (GEN / 'link_clips.h').read_text()
    return {m[0]: int(m[1]) for m in re.findall(r'#\s*define\s+LINK_CLIP_(\w+)\s+(\d+)', header)}


def rise(name):
    header = (GEN / 'link_clips.h').read_text()
    return int(re.search(r'#\s*define\s+LINK_%s_RISE_Q8\s+(-?\d+)' % name, header)[1])


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file(),
                     'host compiler and generated clips required')
class PlayerBg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'bg.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        collision = ROOT.parent / 'shared/lib/collision'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-o', str(out),
                        '-I' + str(camera), '-I' + str(collision), '-I' + str(ROOT / 'src'),
                        '-I' + str(GEN),
                        str(ROOT / 'src/player_bg.c'), str(collision / 'kokiri_collision.c'),
                        str(camera / 'kokiri_camera.c'), str(ROOT / 'src/link_anim_state.c'),
                        str(GEN / 'link_clips.c'), str(ROOT / 'tests/fixtures/traversal_host.c'),
                        '-lm'], check=True, env=env)
        cls._bind(ctypes.CDLL(str(out)))

    @classmethod
    def _bind(cls, lib):
        cls.lib = lib
        P = ctypes.POINTER
        i32 = ctypes.c_int32
        lib.bg_scene_set.argtypes = [P(Mesh)]
        lib.bg_dyna_init.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
        lib.bg_dyna_register.argtypes = [P(Mesh), ctypes.c_uint32]
        lib.bg_dyna_register.restype = ctypes.c_uint32
        lib.bg_dyna_set.argtypes = [ctypes.c_uint32, P(Vec), ctypes.c_uint16, i32]
        lib.kokiri_collision_floor.argtypes = [i32, i32, i32, P(i32)]
        lib.kokiri_collision_floor.restype = ctypes.c_bool
        lib.kokiri_collision_fall.argtypes = [P(Vec), P(i32), P(i32)]
        lib.kokiri_collision_fall.restype = ctypes.c_bool
        lib.kokiri_collision_jump.argtypes = [P(Vec), P(i32), P(i32)]
        lib.kokiri_collision_jump.restype = ctypes.c_bool
        lib.kokiri_camera_move_heading.argtypes = [P(Vec), ctypes.c_uint16, i32]
        lib.kokiri_collision_actor_wall.argtypes = [P(ctypes.c_bool), P(Hit)]
        lib.kokiri_collision_actor_wall.restype = ctypes.c_bool
        lib.kokiri_collision_actor_probe_still.argtypes = [P(Vec)]
        lib.kokiri_collision_actor_set_crawl.argtypes = [ctypes.c_bool]
        lib.player_bg_update.argtypes = [P(Bg), ctypes.c_bool, P(Hit), P(Vec),
                                         ctypes.c_uint16, ctypes.c_uint16, i32]
        lib.player_ledge_action.argtypes = [P(Bg), ctypes.c_bool, ctypes.c_bool, P(i32)]
        lib.player_ledge_action.restype = ctypes.c_int
        lib.player_ledge_jump250_velocity_q8.argtypes = [i32]
        lib.player_ledge_jump250_velocity_q8.restype = i32
        lib.player_ledge_step_target.argtypes = [P(Bg), P(Vec), P(ctypes.c_uint16)]
        lib.link_anim_update.argtypes = [i32, ctypes.c_bool, i32, ctypes.c_bool]
        lib.link_anim_step_up.argtypes = [ctypes.c_bool, i32]
        lib.link_anim_y_offset_q8.restype = i32
        lib.link_anim_jump250_launch.restype = ctypes.c_bool
        lib.link_anim_roll_input.argtypes = [i32, ctypes.c_bool]
        lib.link_anim_motion_events.restype = ctypes.c_uint32
        lib.player_hang_walk_off.argtypes = [P(Vec), P(Vec), i32, ctypes.c_uint8, P(Hit), P(i32)]
        lib.player_hang_walk_off.restype = ctypes.c_int
        lib.player_hang_grab.argtypes = [P(Bg), i32, i32, i32]
        lib.player_hang_grab.restype = ctypes.c_bool
        lib.player_hang_place.argtypes = [P(Hit), i32, P(Vec), P(ctypes.c_uint16), ctypes.c_bool]
        lib.link_anim_hang.argtypes = [ctypes.c_bool]
        lib.link_anim_hang_ready.restype = ctypes.c_bool
        lib.link_anim_pull_up_done.argtypes = [P(i32), P(i32), P(ctypes.c_uint16)]
        lib.link_anim_pull_up_done.restype = ctypes.c_bool
        lib.link_anim_let_go.argtypes = [P(i32), P(i32), P(i32)]
        cls.clips = clip_ids()
        header = (GEN / 'link_clips.h').read_text()
        cls.scale_q16 = int(re.search(r'LINK_ANIM_SCALE_Q16\s+(\d+)', header)[1])

    # -- world ---------------------------------------------------------------
    def world(self, *parts, surfaces=((0, 0),)):
        items = [t for part in parts for t in part]
        self.tris = (Triangle * len(items))(*[t for t, _ in items])
        self.info = (ctypes.c_uint16 * len(items))(*[s for _, s in items])
        flat = [w for pair in surfaces for w in pair]
        self.surf = (ctypes.c_uint32 * len(flat))(*flat)
        self.mesh = Mesh(self.tris, len(items), self.info, self.surf, len(surfaces),
                         None, 0, None, 0, None, 0)
        self.lib.bg_scene_set(ctypes.byref(self.mesh))
        self.dyna_buffer = ctypes.create_string_buffer(0x4800)
        self.lib.bg_dyna_init(self.dyna_buffer, 0x4800)
        self.lib.kokiri_camera_reset_actor_motion()
        self.lib.link_anim_reset_state()
        self.bg = Bg()
        self.lib.player_bg_reset(ctypes.byref(self.bg))
        self.vel = ctypes.c_int32(0)
        self.rem = ctypes.c_int32(0)

    def place(self, x=0, feet=0, z=-60):
        self.pos = Vec(x, feet + EYE, z)
        self.vel.value = 0
        self.rem.value = 0

    def feet(self):
        return Vec(self.pos.x, self.pos.y - EYE, self.pos.z)

    def step(self, speed=RUN_Q8, yaw=0, facing=None):
        lib = self.lib
        lib.kokiri_collision_actor_begin_step()
        lib.kokiri_camera_move_heading(ctypes.byref(self.pos), yaw, speed)
        grounded = lib.kokiri_collision_fall(ctypes.byref(self.pos), ctypes.byref(self.vel),
                                             ctypes.byref(self.rem))
        lib.kokiri_collision_actor_probe_still(ctypes.byref(self.pos))
        stepped, hit = ctypes.c_bool(), Hit()
        wall_hit = lib.kokiri_collision_actor_wall(ctypes.byref(stepped), ctypes.byref(hit))
        feet = self.feet()
        if stepped.value or speed == 0:
            lib.player_bg_update(ctypes.byref(self.bg), wall_hit, ctypes.byref(hit),
                                 ctypes.byref(feet), yaw if facing is None else facing,
                                 yaw, speed)
        return grounded

    def run_into(self, steps=40, **kw):
        for _ in range(steps):
            self.step(**kw)

    def action(self, a=False):
        v = ctypes.c_int32(0)
        act = self.lib.player_ledge_action(ctypes.byref(self.bg), True, a, ctypes.byref(v))
        return act, v.value

    # -- movement: Actor_UpdateBgCheckInfo order -----------------------------

    def test_roll_bonk_wall_angle_recoil_and_finish(self):
        self.lib.link_anim_bonk.argtypes = [ctypes.c_bool, ctypes.c_uint16]
        self.lib.link_anim_bonk.restype = ctypes.c_bool
        wall = quad((-200, 0, 0), (-200, 200, 0),
                    (200, 200, 0), (200, 0, 0))
        for yaw, expected in ((0, True), (0x2000, False), (0x3000, False)):
            self.world(ground(), wall)
            self.place(z=-30)
            self.run_into(steps=8, speed=2112, yaw=yaw)
            if expected:
                self.assertTrue(self.bg.interact)
            for _ in range(40):
                self.lib.link_anim_update(6, True, 0, False)
            self.lib.link_anim_update(6, True, 0, True)
            self.assertEqual(self.lib.link_anim_state(), STATE['ROLL'])
            self.assertEqual(self.lib.link_anim_bonk(
                self.bg.interact, self.bg.world_yaw_to_wall), expected)
            if expected:
                self.assertEqual(self.lib.link_anim_state(), 15)
                recoil = self.lib.link_anim_bonk_speed_q8()
                self.assertLess(recoil, -1792)
                before = self.pos.z
                self.step(speed=-recoil, yaw=0x8000)
                self.assertLess(self.pos.z, before)
                self.lib.link_anim_roll_input(0, False)
                self.lib.link_anim_update(0, True, 0, False)
                self.assertEqual(self.lib.link_anim_bonk_speed_q8(), recoil + 341)
                for _ in range(35):
                    self.lib.link_anim_update(0, True, 0, False)
                self.assertEqual(self.lib.link_anim_state(), STATE['IDLE'])
                self.assertEqual(self.lib.link_anim_bonk_speed_q8(), 0)

    def test_slow_roll_and_no_contact_do_not_bonk(self):
        self.lib.link_anim_bonk.argtypes = [ctypes.c_bool, ctypes.c_uint16]
        self.lib.link_anim_bonk.restype = ctypes.c_bool
        self.lib.link_anim_reset_state()
        for _ in range(40):
            self.lib.link_anim_update(3, True, 0, False)
        self.lib.link_anim_update(3, True, 0, True)
        self.assertFalse(self.lib.link_anim_bonk(True, 0))
        self.assertFalse(self.lib.link_anim_bonk(False, 0))
    def test_low_steps_step_up_tall_ones_block_at_the_radius(self):
        """No wall hit (sphere r14 at +26) -> the floor ray from +50 stands
        him on it. The wall's Approx test (detMax 300) gives this 400-wide
        face 300/400 = 0.75 of slack over its top: 25 is climbed onto, 26
        blocks with the sphere centre on it."""
        for h in (3, 10, 20, 24, 25):
            with self.subTest(h=h):
                self.world(ground(), box(h))
                self.place()
                self.run_into()
                self.assertEqual(self.pos.y - EYE, h)
                self.assertGreater(self.pos.z, 100)
        for h in (26, 30, 47, 80):
            with self.subTest(h=h):
                self.world(ground(), box(h))
                self.place()
                self.run_into()
                self.assertEqual(self.pos.y - EYE, 0)
                self.assertEqual(self.pos.z, -14)
                self.assertTrue(self.bg.wall)

    def test_blocked_headroom_reverts_xz(self):
        """Ceiling within ceilingCheckHeight 40 + dy - 10 above feet + 10,
        where a grounded dy is -7.5 (velocity -4 glue, gravity, x1.5): on the
        floor's bgId x/z go back. So 32 blocks and 33 passes."""
        self.world(ground(), ceiling(32, 0, 300))
        self.place()
        self.run_into()
        self.assertLessEqual(self.pos.z, 0)
        self.assertEqual(self.pos.y - EYE, 0)
        self.world(ground(), ceiling(33, 0, 300))
        self.place()
        self.run_into()
        self.assertGreater(self.pos.z, 100)
        # A step up under a low roof: floor 10, roof 45 -> 35 clear from the
        # step top, but the check is from the current feet (0 + 10 .. +40):
        # 45 is outside it, so he steps up.
        self.world(ground(), box(10), ceiling(45, 0, 300))
        self.place()
        self.run_into()
        self.assertEqual(self.pos.y - EYE, 10)

    def test_slopes_walkable_up_and_down_steep_is_a_wall(self):
        ramp = quad((-200, 0, 0), (-200, 100, 150), (200, 100, 150), (200, 0, 0))
        top = quad((-200, 100, 150), (-200, 100, 400), (200, 100, 400), (200, 100, 150))
        self.world(ground(), ramp, top)          # ny 0.83: floor
        self.place()
        grounded = []
        for _ in range(80):
            grounded.append(self.step())
        self.assertEqual(self.pos.y - EYE, 100)
        self.assertTrue(all(grounded[3:]))
        # And back down, still grounded all the way (ground follow <= 11).
        grounded = [self.step(yaw=0x8000) for _ in range(100)]
        self.assertEqual(self.pos.y - EYE, 0)
        self.assertTrue(all(grounded))
        steep = quad((-200, 0, 0), (-200, 100, 40), (200, 100, 40), (200, 0, 0))
        self.world(ground(), steep)              # ny 0.37: wall
        self.place()
        self.run_into()
        self.assertLess(self.pos.y - EYE, 26)
        self.assertLess(self.pos.z, 10)

    def test_wall_contact_is_the_sphere_poly(self):
        self.world(ground(), box(30))
        self.place()
        self.run_into()
        self.assertTrue(self.bg.wall and self.bg.interact)
        self.assertEqual(tuple(self.bg.wall_hit.normal), (0, 0, -16384))
        self.assertEqual(self.bg.wall_hit.bg_id, BG_SCENE)
        self.assertEqual(self.bg.wall_yaw, 0x8000)    # Math_Atan2S(-1, 0)
        self.assertEqual(self.bg.shape_yaw_to_wall, 0)
        self.assertEqual(self.bg.dist_to_wall, 14)

    def test_wall_yaw_basis(self):
        self.world(ground(), quad((100, 0, 200), (100, 60, 200), (100, 60, -200),
                                  (100, 0, -200)))   # faces -x
        self.place(x=0, z=0)
        self.run_into(yaw=0x4000)                 # moving +x
        self.assertTrue(self.bg.wall)
        self.assertEqual(self.bg.wall_yaw, 0xC000)
        self.assertEqual(self.pos.x, 86)

    # -- ledge probe ---------------------------------------------------------
    def probe(self, *parts, facing=None, **kw):
        self.world(ground(), *parts, **kw)
        self.place()
        self.run_into(facing=facing)
        return self.bg.ledge_type, self.bg.y_dist_to_ledge

    def test_ledge_types_at_every_child_threshold(self):
        expected = {26: CLIMB_1, 27: CLIMB_2, 38: CLIMB_2, 39: CLIMB_3,
                    46: CLIMB_3, 47: CLIMB_4, 70: CLIMB_4}
        for h, kind in expected.items():
            with self.subTest(h=h):
                self.assertEqual(self.probe(box(h)), (kind, h))
        # Above the 71 probe start the ray finds the ground under it: < 18.
        self.assertEqual(self.probe(box(72)), (NONE, 399))

    def test_facing_needs_the_interact_line(self):
        """shape yaw within 0x3000, and the 24-unit line must still reach."""
        self.assertEqual(self.probe(box(30), facing=0x2000)[0], CLIMB_2)
        kind = self.probe(box(30), facing=0x2800)[0]
        self.assertEqual(kind, NONE)
        self.assertFalse(self.bg.interact)

    def test_leaning_wall_is_not_a_ledge_wall(self):
        """|wallPoly->normal.y| < 600/32767: a wall 1 unit out of plumb over
        30 has ny ~546 in Q14 (0.033) and is refused."""
        self.assertEqual(self.probe(box(30, wall_lean=1))[0], NONE)
        self.assertTrue(self.bg.wall)

    def test_steep_ledge_top_refused_for_climbs(self):
        self.assertEqual(self.probe(box(30, top_rise=210))[0], NONE)
        self.assertGreaterEqual(self.bg.y_dist_to_ledge, 27)

    def test_ceiling_over_the_climb_refuses(self):
        # yDist 30: a ceiling within 30 + 20 of the feet blocks.
        self.assertEqual(self.probe(box(30), ceiling(49, -100, -1)), (NONE, 399))
        self.assertEqual(self.probe(box(30), ceiling(51, -100, -1))[0], CLIMB_2)

    def test_wall_just_behind_the_ledge_refuses(self):
        self.assertEqual(self.probe(box(30), wall(4, 30, 70)), (NONE, 399))

    def test_wall_flags(self):
        # data0 bits 21-25 = wall type. Type 1: WALL_FLAG_0 (no ledge grab).
        surfaces = ((0, 0), (1 << 21, 0), (2 << 21, 0))
        self.assertEqual(self.probe(box(30, surface=1), surfaces=surfaces)[0], NONE)
        self.assertEqual(self.bg.touched_flags, 0x01)
        # A blocking wall with WALL_FLAG_1 (type 2, ladder) does not refuse.
        self.assertEqual(self.probe(box(30), wall(4, 30, 70, surface=2),
                                    surfaces=surfaces)[0], CLIMB_2)

    # -- Player_ActionHandler_12 ----------------------------------------------
    def contact(self, h, **kw):
        self.world(ground(), box(h), **kw)
        self.place(z=-20)
        steps = 0
        while not self.bg.wall:
            self.step()
            steps += 1
            self.assertLess(steps, 10)

    def test_climb_waits_nine_steps_or_takes_a(self):
        self.contact(30)
        self.assertEqual(self.bg.ledge_type, CLIMB_2)
        self.assertEqual(self.action(a=True)[0], ACT_STEP100)
        waited = 0
        while self.action()[0] == ACT_NONE:
            self.step()
            waited += 1
        self.assertEqual(self.bg.delay_timer, 9)
        self.assertEqual(self.action()[0], ACT_STEP100)
        self.assertEqual(waited, 9)

    def test_action_by_height(self):
        for h, act in ((27, ACT_STEP100), (38, ACT_STEP100), (39, ACT_STEP150),
                       (46, ACT_STEP150), (47, ACT_JUMP250), (70, ACT_JUMP250)):
            with self.subTest(h=h):
                self.contact(h)
                self.assertEqual(self.action(a=True)[0], act)

    def test_hop_waits_five_steps_and_a_does_not_hurry_it(self):
        self.contact(26)
        self.assertEqual(self.bg.ledge_type, CLIMB_1)
        self.assertEqual(self.action(a=True)[0], ACT_NONE)
        for _ in range(5):
            self.step()
        act, velocity = self.action()
        self.assertEqual(act, ACT_HOP)
        self.assertEqual(velocity, 26 * 2048 // 100 + 1408)   # 0.08 d + 5.5

    def test_airborne_or_still_never_climbs(self):
        self.contact(30)
        for _ in range(10):
            self.step()
        v = ctypes.c_int32(0)
        self.assertEqual(self.lib.player_ledge_action(ctypes.byref(self.bg), False, True,
                                                      ctypes.byref(v)), ACT_NONE)
        # Speed 0 holds the timer (the source only counts while moving).
        timer = self.bg.delay_timer
        hit = Hit.from_buffer_copy(self.bg.wall_hit)
        feet = self.feet()
        self.lib.player_bg_update(ctypes.byref(self.bg), True, ctypes.byref(hit),
                                  ctypes.byref(feet), 0, 0, 0)
        self.assertEqual(self.bg.delay_timer, timer)

    def test_dyna_flag6_wall_needs_timer_and_a(self):
        self.world(ground())
        block = box(30)
        items = (Triangle * len(block))(*[t for t, _ in block])
        info = (ctypes.c_uint16 * len(block))(*([0] * len(block)))
        surf = (ctypes.c_uint32 * 2)(7 << 21, 0)      # type 7 -> WALL_FLAG_6
        mesh = Mesh(items, len(block), info, surf, 1, None, 0, None, 0, None, 0)
        self._keep = (items, info, surf, mesh)
        slot = self.lib.bg_dyna_register(ctypes.byref(mesh), 0)
        self.lib.bg_dyna_set(slot, ctypes.byref(Vec(0, 0, 0)), 0, 1 << 16)
        self.lib.bg_dyna_step()
        self.place(z=-20)
        while not self.bg.wall:
            self.step()
        self.assertNotEqual(self.bg.wall_hit.bg_id, BG_SCENE)
        self.assertEqual(self.bg.touched_flags, 0x40)
        self.assertEqual(self.action(a=True)[0], ACT_NONE)
        for _ in range(12):
            self.step()
        self.assertEqual(self.action()[0], ACT_NONE)
        self.assertEqual(self.action(a=True)[0], ACT_STEP100)

    def test_step_target_is_on_the_ledge(self):
        for h in (27, 30, 38, 42, 46):
            with self.subTest(h=h):
                self.contact(h)
                feet, facing = self.feet(), ctypes.c_uint16(0x1234)
                self.lib.player_ledge_step_target(ctypes.byref(self.bg), ctypes.byref(feet),
                                                  ctypes.byref(facing))
                self.assertEqual(facing.value, 0)
                self.assertEqual(feet.y, h)
                self.assertGreaterEqual(feet.z, 0)
                self.assertLessEqual(feet.z, 1)
                floor = ctypes.c_int32()
                self.assertTrue(self.lib.kokiri_collision_floor(feet.x, feet.z, feet.y + 4,
                                                                ctypes.byref(floor)))
                self.assertEqual(floor.value, h)

    # -- Player_Action_80845668 animation --------------------------------------
    def play_step_up(self, tall, y_dist, moving_from=None):
        lib = self.lib
        lib.link_anim_reset_state()
        lib.link_anim_update(0, True, 0, False)
        lib.link_anim_step_up(tall, y_dist)
        offsets, events, steps = [lib.link_anim_y_offset_q8()], [], 0
        while lib.link_anim_state() == STATE['STEP_UP']:
            moving = moving_from is not None and steps >= moving_from
            lib.link_anim_roll_input(RUN_Q8 if moving else 0, moving)
            lib.link_anim_update(0, True, 0, False)
            offsets.append(lib.link_anim_y_offset_q8())
            events.append(lib.link_anim_motion_events())
            steps += 1
            self.assertLess(steps, 80)
        lib.link_anim_roll_input(0, False)
        return offsets, events, steps

    def test_step_up_offset_timing_and_voice(self):
        offsets, events, steps = self.play_step_up(False, 30)
        self.assertEqual(offsets[0], rise('STEP100') - 30 * 256)
        self.assertEqual(offsets[-1], 0)
        # 28 frames at 1.3 per step: last frame reached on step 21, the
        # update after that reports done.
        self.assertEqual(steps, 22)
        climb = [i for i, e in enumerate(events) if e & GP_EVENT_CLIMB_END]
        self.assertEqual(climb, [12])            # frame 16: 13 * 1.3 = 16.9
        offsets, events, steps = self.play_step_up(True, 42)
        self.assertEqual(offsets[0], rise('STEP150') - 42 * 256)
        self.assertEqual(steps, 35)              # 45 frames
        climb = [i for i, e in enumerate(events) if e & GP_EVENT_CLIMB_END]
        self.assertEqual(climb, [23])            # frame 30: 24 * 1.3 = 31.2
        # 150: offset holds until past frame 5 (update 4: 5.2), then 1 unit a
        # step toward zero (the 44-unit child's rise is below the 42 lift, so
        # the start offset is negative since BUG-009).
        self.assertEqual(offsets[3], offsets[0])
        self.assertEqual(offsets[4], offsets[0] + (256 if offsets[0] < 0 else -256))

    def test_step_up_rise_is_the_child_adjusted_root(self):
        """The drawn rise is the root delta after x0.64, at the mesh scale."""
        self.assertAlmostEqual(rise('STEP100') / 256, (3377 - -638) * 0.64 * 0.01, delta=0.5)
        self.assertAlmostEqual(rise('STEP150') / 256, (3377 - -2612) * 0.64 * 0.01, delta=0.5)

    def test_movement_interrupts_only_the_last_four_frames(self):
        _, _, full = self.play_step_up(False, 30)
        _, _, early = self.play_step_up(False, 30, moving_from=0)
        # Frame >= 23 (27 - 4): 18 * 1.3 = 23.4 -> step 18.
        self.assertEqual(early, 18)
        self.assertLess(early, full)

    def test_jump250_launches_on_frame_8_and_comes_back_down(self):
        lib = self.lib
        self.assertEqual(lib.player_ledge_jump250_velocity_q8(50), 50 * 18432 // 1000 + 256)
        self.assertEqual(lib.player_ledge_jump250_velocity_q8(80), 71 * 18432 // 1000 + 256)
        self.contact(50)
        lib.link_anim_jump_start()
        steps = 0
        while not lib.link_anim_jump250_launch():
            lib.link_anim_update(0, True, 0, False)
            steps += 1
            self.assertLess(steps, 20)
        self.assertEqual(steps, 7)                # 7 * 1.3 = 9.1 >= 8
        self.assertEqual(lib.link_anim_state(), STATE['JUMP'])
        self.assertEqual(lib.link_anim_clip(), self.clips['JUMP250'])
        self.vel.value = lib.player_ledge_jump250_velocity_q8(50)
        peak = 0
        for _ in range(60):
            self.step(speed=256)
            peak = max(peak, self.pos.y - EYE)
        # No mid-air grab until M1d: a short hop, back on the ground below.
        self.assertLess(peak, 30)
        self.assertEqual(self.pos.y - EYE, 0)
        self.assertEqual(self.vel.value, 0)

    def test_hop_lands_on_the_ledge(self):
        for h in (26,):
            with self.subTest(h=h):
                self.contact(h)
                for _ in range(5):
                    self.step()
                act, velocity = self.action()
                self.assertEqual(act, ACT_HOP)
                self.vel.value = velocity
                self.rem.value = 0
                for _ in range(40):
                    self.step()
                self.assertEqual(self.pos.y - EYE, h)
                self.assertGreater(self.pos.z, 20)

    def test_y_jump_still_51_and_mounts_by_the_source_floor_ray(self):
        """The custom Y jump keeps its apex; once the wall sphere clears the
        top, the +50 floor ray stands him on it, as the source does."""
        self.world(ground())
        self.place(z=0)
        self.assertTrue(self.lib.kokiri_collision_jump(ctypes.byref(self.pos),
                                                       ctypes.byref(self.vel),
                                                       ctypes.byref(self.rem)))
        peak = 0
        for _ in range(40):
            self.step(speed=0)
            peak = max(peak, self.pos.y - EYE)
        self.assertEqual(peak, 51)
        self.world(ground(), box(40))
        self.place(z=-20)
        self.assertTrue(self.lib.kokiri_collision_jump(ctypes.byref(self.pos),
                                                       ctypes.byref(self.vel),
                                                       ctypes.byref(self.rem)))
        for _ in range(40):
            self.step()
        self.assertEqual(self.pos.y - EYE, 40)

    def jump_peak(self, steps=40, **kw):
        self.assertTrue(self.lib.kokiri_collision_jump(ctypes.byref(self.pos),
                                                       ctypes.byref(self.vel),
                                                       ctypes.byref(self.rem)))
        peak = 0
        for _ in range(steps):
            self.step(**kw)
            peak = max(peak, self.pos.y - EYE)
        return peak

    def test_a_wall_at_contact_never_pins_vertical_motion(self):
        """Resting exactly on the wall radius, he still jumps and lands:
        vertical motion checks ceilings and floors, not walls."""
        self.world(ground(), box(80))
        self.place(z=-20)
        self.run_into(steps=5)
        self.assertEqual(self.pos.z, -14)
        self.assertEqual(self.jump_peak(), 51)
        self.assertEqual(self.pos.y - EYE, 0)
        self.assertEqual(self.vel.value, 0)

    def test_a_ceiling_caps_the_rise_at_40_below_it(self):
        self.world(ground(), ceiling(60, -200, 200))
        self.place(z=0)
        self.assertEqual(self.jump_peak(speed=0), 20)
        self.assertEqual(self.pos.y - EYE, 0)

    def test_automatic_jump_still_leaves_a_ledge(self):
        """Walking off a 60 drop: the actor step keeps y (no ground follow
        past 11), so kokiri_collision_fall sees a real departure."""
        self.world(quad((-200, 60, -300), (-200, 60, 0), (200, 60, 0), (200, 60, -300)),
                   ground())
        self.place(feet=60, z=-30)
        states = [self.step() for _ in range(12)]
        self.assertFalse(all(states))
        self.assertLess(self.pos.y - EYE, 60)

    # -- M1d: hang (func_8083A6AC, Player_Action_8084411C grab, 8084BBE4/BDFC) --
    def cliff(self, h=60, surface=0, surfaces=((0, 0),)):
        """Ledge top at h for z < 0, ground at 0 beyond; the face at z = 0
        faces +z (the way Link walks off)."""
        top = quad((-200, h, -300), (-200, h, 0), (200, h, 0), (200, h, -300))
        low = quad((-200, 0, 0), (-200, 0, 300), (200, 0, 300), (200, 0, 0))
        face = quad((200, 0, 0), (200, h, 0), (-200, h, 0), (-200, 0, 0), surface)
        self.world(top, low, face, surfaces=surfaces)

    def walk_off(self, h=60, depth=-32000, prop=0):
        wall, dist = Hit(), ctypes.c_int32()
        pos, prev = Vec(0, h - 5, 3), Vec(0, h, -2)
        kind = self.lib.player_hang_walk_off(ctypes.byref(pos), ctypes.byref(prev), depth, prop,
                                             ctypes.byref(wall), ctypes.byref(dist))
        return kind, wall, dist.value, pos

    def test_walking_off_a_deep_drop_hangs_on_the_face_just_left(self):
        self.cliff()
        kind, wall, dist, pos = self.walk_off()
        self.assertEqual(kind, HANG_LEDGE)
        self.assertEqual(tuple(wall.normal), (0, 0, 16384))
        self.assertEqual(dist, 3)
        facing = ctypes.c_uint16()
        self.lib.player_hang_place(ctypes.byref(wall), dist, ctypes.byref(pos),
                                   ctypes.byref(facing), False)
        # (dist + 1) into the wall; facing the normal: out over the drop.
        self.assertEqual((pos.x, pos.z, facing.value), (0, -1, 0))
        floor = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(pos.x, pos.z, pos.y + 49,
                                                        ctypes.byref(floor)))
        self.assertEqual(floor.value, 60)

    def test_walk_off_refusals(self):
        self.cliff()
        self.assertEqual(self.walk_off(depth=-79)[0], HANG_NONE)     # water within 80
        self.assertEqual(self.walk_off(depth=-81)[0], HANG_LEDGE)
        self.assertEqual(self.walk_off(prop=6)[0], HANG_CLIMB)      # M1e
        self.cliff(surface=1, surfaces=((0, 0), (4 << 21, 0)))      # type 4: FLAG_3
        self.assertEqual(self.walk_off()[0], HANG_CLIMB)
        lean = quad((200, 0, 0), (200, 60, -2), (-200, 60, -2), (-200, 0, 0))
        self.world(quad((-200, 60, -300), (-200, 60, -2), (200, 60, -2), (200, 60, -300)),
                   ground(), lean)
        self.assertEqual(self.walk_off()[0], HANG_NONE)             # |ny| >= 600/32767

    def launch_250(self, h):
        self.contact(h)
        self.vel.value = self.lib.player_ledge_jump250_velocity_q8(self.bg.y_dist_to_ledge)
        self.rem.value = 0
        air, grabbed = 256, None
        for step in range(40):
            self.step(speed=air)
            air = max(0, air - 17)
            floor = ctypes.c_int32()
            feet = self.pos.y - EYE
            if not self.lib.kokiri_collision_floor(self.pos.x, self.pos.z, feet,
                                                   ctypes.byref(floor)):
                floor.value = -32000
            if self.vel.value < 0 and self.lib.player_hang_grab(ctypes.byref(self.bg), air,
                                                                feet, floor.value):
                grabbed = step, feet
                break
        return grabbed

    def test_250_jump_grabs_the_ledge_while_falling(self):
        for h in (50, 70):
            with self.subTest(h=h):
                grabbed = self.launch_250(h)
                self.assertIsNotNone(grabbed)
                self.assertLess(self.vel.value, 0)
                feet = Vec(self.pos.x, grabbed[1] + self.bg.y_dist_to_ledge, self.pos.z)
                facing = ctypes.c_uint16()
                self.lib.player_hang_place(ctypes.byref(self.bg.wall_hit), self.bg.dist_to_wall,
                                           ctypes.byref(feet), ctypes.byref(facing), True)
                self.assertEqual(feet.y, h)
                self.assertEqual(feet.z, 1)                  # 1 unit onto the ledge
                self.assertEqual(facing.value, 0)            # facing the wall
                floor = ctypes.c_int32()
                self.assertTrue(self.lib.kokiri_collision_floor(feet.x, feet.z, feet.y + 49,
                                                                ctypes.byref(floor)))
                self.assertEqual(floor.value, h)

    def test_grab_refusals(self):
        self.contact(50)
        for _ in range(3):
            self.step()
        self.assertEqual(self.bg.ledge_type, CLIMB_4)
        self.assertTrue(self.lib.player_hang_grab(ctypes.byref(self.bg), 1, 0, 0))
        self.assertFalse(self.lib.player_hang_grab(ctypes.byref(self.bg), 0, 0, 0))  # speed
        # Ledge top 45 above the floor under him: 70 x 11/17 = 45.3 is not met.
        self.assertFalse(self.lib.player_hang_grab(ctypes.byref(self.bg), 1, 0, 5))
        self.assertTrue(self.lib.player_hang_grab(ctypes.byref(self.bg), 1, 0, 4))
        # A low ledge (CLIMB_1) is never grabbed.
        self.contact(26)
        self.assertFalse(self.lib.player_hang_grab(ctypes.byref(self.bg), 1, 0, -100))

    def play_hang(self, walk_off):
        lib = self.lib
        lib.link_anim_reset_state()
        lib.link_anim_hang(walk_off)
        ready = None
        for step in range(1, 60):
            lib.link_anim_update(0, True, 0, False)
            if ready is None and lib.link_anim_hang_ready():
                ready = step
        return ready

    def test_hang_grab_frame_and_wait_loop(self):
        self.assertEqual(self.play_hang(True), 11)          # normal_fall frame 11
        self.assertEqual(self.lib.link_anim_clip(), self.clips['FALL_WAIT'])
        self.assertEqual(self.play_hang(False), 1)          # jump_climb_hold frame 1
        self.assertEqual(self.lib.link_anim_clip(), self.clips['CLIMB_WAIT'])
        self.assertEqual(self.lib.link_anim_state(), STATE['HANG'])

    def pull_up(self, walk_off):
        lib = self.lib
        self.play_hang(walk_off)
        lib.link_anim_pull_up()
        self.assertEqual(lib.link_anim_state(), STATE['PULL_UP'])
        lx, lz, yaw = ctypes.c_int32(), ctypes.c_int32(), ctypes.c_uint16()
        steps, events = 0, []
        while not lib.link_anim_pull_up_done(ctypes.byref(lx), ctypes.byref(lz), ctypes.byref(yaw)):
            lib.link_anim_update(0, True, 0, False)
            events.append(lib.link_anim_motion_events())
            steps += 1
            self.assertLess(steps, 100)
        return steps, lx.value, lz.value, yaw.value, events

    def test_pull_up_timing_and_root_transfer(self):
        q8 = lambda v: int(v * self.scale_q16 / 256)   # C truncation
        steps, lx, lz, yaw, events = self.pull_up(True)
        # fall_up: 86 frames at 1.3 a step; turns him round at the end.
        self.assertEqual(steps, 67)
        # Measured from sSkeletonBaseTransl (-57, 3377, 0) x 0.64 = (-36, ...).
        self.assertEqual((lx, lz, yaw), (q8(36 + 36), q8(-320), 0x8000))
        climb = [i for i, e in enumerate(events) if e & GP_EVENT_CLIMB_END]
        self.assertEqual(len(climb), 1)                     # frame 85 - 34
        steps, lx, lz, yaw, _ = self.pull_up(False)
        self.assertEqual(steps, 30)                         # jump_climb_up: 38 frames
        self.assertEqual((lx, lz, yaw), (q8(-36 + 36), q8(320), 0))
        self.assertEqual(self.lib.link_anim_state(), STATE['IDLE'])

    def test_let_go_drops_the_actor_to_the_hanging_pelvis(self):
        lib = self.lib
        self.play_hang(False)
        lx, ly, lz = ctypes.c_int32(), ctypes.c_int32(), ctypes.c_int32()
        lib.link_anim_let_go(ctypes.byref(lx), ctypes.byref(ly), ctypes.byref(lz))
        q8 = lambda v: int(v * self.scale_q16 / 256)   # C truncation
        # jump_climb_wait root (84 or 80, -3074, -664) x 0.64, y against the
        # standing pelvis (idle frame 0, 3378 x 0.64 = 2162).
        self.assertAlmostEqual(ly.value, q8(-1967 - 2162), delta=256)
        self.assertAlmostEqual(lz.value, q8(-425), delta=256)
        self.assertEqual(lib.link_anim_state(), STATE['FALL'])

    def local_move(self, lx, lz, yaw):
        a = yaw * 2 * math.pi / 65536
        sin, cos = int(math.sin(a) * 65536), int(math.cos(a) * 65536)
        self.pos.x += (lx * (int(cos / 256)) + lz * (int(sin / 256))) // 65536
        self.pos.z += (lz * (int(cos / 256)) - lx * (int(sin / 256))) // 65536

    def test_grab_pull_up_and_let_go_end_clear_of_the_wall(self):
        """demo.c's order, on the real collision: grab from a 250 jump, pull
        up onto the ledge; grab again and let go back to the ground."""
        for pull in (True, False):
            with self.subTest(pull=pull):
                grabbed = self.launch_250(50)
                self.assertIsNotNone(grabbed)
                feet = Vec(self.pos.x, grabbed[1] + self.bg.y_dist_to_ledge, self.pos.z)
                facing = ctypes.c_uint16()
                self.lib.player_hang_place(ctypes.byref(self.bg.wall_hit), self.bg.dist_to_wall,
                                           ctypes.byref(feet), ctypes.byref(facing), True)
                self.pos = Vec(feet.x, 50 + EYE, feet.z)
                self.vel.value = self.rem.value = 0
                self.play_hang(False)
                self.assertTrue(self.step(speed=0))                   # stands on the top
                if pull:
                    steps, lx, lz, yaw, _ = self.pull_up(False)
                    self.local_move(lx, lz, facing.value)
                    self.assertEqual(self.pos.y - EYE, 50)
                    self.assertGreater(self.pos.z, 1)
                    self.assertTrue(self.step(speed=0))
                else:
                    lx, ly, lz = ctypes.c_int32(), ctypes.c_int32(), ctypes.c_int32()
                    self.lib.link_anim_let_go(ctypes.byref(lx), ctypes.byref(ly), ctypes.byref(lz))
                    self.local_move(lx.value, lz.value, facing.value)
                    self.pos.y += int(ly.value / 256)
                    self.assertLess(self.pos.z, 0)                    # out over the drop
                    air = 205
                    for _ in range(60):
                        self.step(speed=air, yaw=(facing.value + 0x8000) & 0xFFFF)
                        air = max(0, air - 17)
                    self.assertEqual(self.pos.y - EYE, 0)
                    self.assertLessEqual(self.pos.z, -14)             # pushed clear


FOREST = ROOT / 'build/cd/S1.COL'


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file() and FOREST.is_file(),
                     'host compiler, clips and S1.COL required')
class ForestLedges(PlayerBg):
    """Real Kokiri Forest ledges (found by scanning every wall of S1.COL)."""

    def setUp(self):
        lib = self.lib
        P = ctypes.POINTER
        lib.bg_mesh_bytes.argtypes = [ctypes.c_char_p, ctypes.c_uint32]
        lib.bg_mesh_bytes.restype = ctypes.c_uint32
        lib.bg_mesh_decode.argtypes = [ctypes.c_char_p, ctypes.c_uint32, ctypes.c_void_p,
                                       ctypes.c_uint32, P(Mesh)]
        lib.bg_mesh_decode.restype = ctypes.c_bool
        data = FOREST.read_bytes()
        size = lib.bg_mesh_bytes(data, len(data))
        self.buffer = ctypes.create_string_buffer(size)
        self.mesh = Mesh()
        self.assertTrue(lib.bg_mesh_decode(data, len(data), self.buffer, size,
                                           ctypes.byref(self.mesh)))
        lib.bg_scene_set(ctypes.byref(self.mesh))
        self.dyna_buffer = ctypes.create_string_buffer(0x4800)
        lib.bg_dyna_init(self.dyna_buffer, 0x4800)
        lib.kokiri_camera_reset_actor_motion()
        self.bg = Bg()
        lib.player_bg_reset(ctypes.byref(self.bg))
        self.vel, self.rem = ctypes.c_int32(0), ctypes.c_int32(0)

    def test_forest_ledges(self):
        for feet, yaw, kind, y_dist in (((1219, -60, 59), 0x4000, CLIMB_3, 39),
                                        ((172, 1, -483), 0x8B87, CLIMB_4, 59),
                                        ((-462, 0, -682), 0x727D, CLIMB_4, 59)):
            with self.subTest(feet=feet):
                self.lib.player_bg_reset(ctypes.byref(self.bg))
                self.place(feet[0], feet[1], feet[2])
                self.run_into(steps=4, yaw=yaw)
                self.assertEqual((self.bg.ledge_type, self.bg.y_dist_to_ledge), (kind, y_dist))
                self.assertEqual(self.pos.y - EYE, feet[1])

    def test_forest_walk_off_hang(self):
        """Walking west off the 49 drop at (314, 3, -198): the line test finds
        the face just left and the hang stands him back on its top."""
        wall, dist = Hit(), ctypes.c_int32()
        pos, prev = Vec(308, 3 - 5, -198), Vec(314, 3, -198)
        self.assertEqual(self.lib.player_hang_walk_off(ctypes.byref(pos), ctypes.byref(prev),
                                                       -32000, 0, ctypes.byref(wall),
                                                       ctypes.byref(dist)), HANG_LEDGE)
        facing = ctypes.c_uint16()
        self.lib.player_hang_place(ctypes.byref(wall), dist.value, ctypes.byref(pos),
                                   ctypes.byref(facing), False)
        floor = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(pos.x, pos.z, pos.y + 49,
                                                        ctypes.byref(floor)))
        self.assertEqual(floor.value, 3)
        self.assertLess(abs((facing.value - 0xC000 + 0x8000) % 0x10000 - 0x8000), 0x800)

    def test_walk_through_grass_without_stepping_on_top(self):
        self.place(60, 1, -440)
        for _ in range(12):
            self.assertTrue(self.step(speed=3 * 256))
            self.assertEqual(self.feet().y, 1)
        self.assertGreater(self.pos.z, -410)


# The synthetic cases are not rerun on the forest mesh.
for _name in [n for n in dir(PlayerBg) if n.startswith('test_')]:
    setattr(ForestLedges, _name, None)


if __name__ == '__main__':
    unittest.main()
