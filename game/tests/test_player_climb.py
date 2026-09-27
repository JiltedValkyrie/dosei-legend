"""M1e: ladder and vine climbing (func_8083EC18, Player_Action_8084BF1C/8084C5F8).

Real C: player_climb.c, player_bg.c, kokiri_collision.c, kokiri_camera.c,
link_anim_state.c + generated clips. Scenes: a synthetic ladder shaped like
Link's house ladder, a vine wall, and the real S1.COL ladder.
"""

import ctypes
import pathlib
import unittest

try:
    import test_player_bg as bgt
except ImportError:                     # run as tests.test_player_climb
    from tests import test_player_bg as bgt
Bg, EYE, GCC, GEN, Hit, STATE, Vec = (bgt.Bg, bgt.EYE, bgt.GCC, bgt.GEN, bgt.Hit,
                                      bgt.STATE, bgt.Vec)
ground, quad = bgt.ground, bgt.quad

ROOT = bgt.ROOT
FOREST = ROOT / 'build/cd/S1.COL'
ON, ENDING, DONE, VINE_TOP, LET_GO = 1, 2, 3, 4, 5
TOP = 180
LADDER, LIP, VINE = 1, 2, 3
SURFACES = ((0, 0), (2 << 21, 0), (3 << 21, 0), (4 << 21, 0))
FULL = 80


class Climb(ctypes.Structure):
    _fields_ = [('phase', ctypes.c_int), ('var1', ctypes.c_int8), ('var2', ctypes.c_int8),
                ('interact', ctypes.c_bool), ('wall', Hit), ('events', ctypes.c_uint32)]


class Input(ctypes.Structure):
    _fields_ = [('stick_x', ctypes.c_int32), ('stick_y', ctypes.c_int32),
                ('a_pressed', ctypes.c_bool), ('stick_pushed', ctypes.c_bool)]


def minus_z(x0, x1, y0, y1, z, surface=0):
    """A wall across x0..x1 at z, facing -z (towards an approach from -z)."""
    return quad((x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z), surface)


def plus_z(x0, x1, y0, y1, z, surface=0):
    return quad((x1, y0, z), (x1, y1, z), (x0, y1, z), (x0, y0, z), surface)


def ladder_world():
    """Face z = 0 (x -16..16, facing -z, type 2), a platform top at 180 behind
    it, and a 20-high lip on the platform edge facing it (type 3), as at
    Link's house (S1.COL polys 784-787)."""
    face = minus_z(-16, 16, 0, 195, 0, LADDER)
    lip = plus_z(-16, 16, TOP, TOP + 20, 4, LIP)
    top = quad((-200, TOP, 4), (-200, TOP, 300), (200, TOP, 300), (200, TOP, 4))
    return [face, lip, top]


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file(),
                     'host compiler and generated clips required')
class PlayerClimb(bgt.PlayerBg):
    @classmethod
    def setUpClass(cls):
        import os, subprocess, tempfile
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'climb.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        collision = ROOT.parent / 'shared/lib/collision'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-o', str(out),
                        '-I' + str(camera), '-I' + str(collision), '-I' + str(ROOT / 'src'),
                        '-I' + str(GEN),
                        str(ROOT / 'src/player_climb.c'), str(ROOT / 'src/player_bg.c'),
                        str(collision / 'kokiri_collision.c'), str(camera / 'kokiri_camera.c'),
                        str(ROOT / 'src/link_anim_state.c'), str(GEN / 'link_clips.c'),
                        str(ROOT / 'tests/fixtures/traversal_host.c'), '-lm'],
                       check=True, env=env)
        cls._bind(ctypes.CDLL(str(out)))
        lib = cls.lib
        P = ctypes.POINTER
        lib.player_climb_start.argtypes = [P(Climb), P(Bg), P(Vec), P(ctypes.c_uint16), ctypes.c_bool]
        lib.player_climb_start.restype = ctypes.c_bool
        lib.player_climb_update.argtypes = [P(Climb), P(Input), P(Vec), P(ctypes.c_uint16)]
        lib.player_climb_start_walk_off.argtypes = [P(Climb), P(Hit), P(ctypes.c_uint16)]
        lib.link_anim_move_clip.restype = ctypes.c_uint

    # -- harness: demo.c's order ----------------------------------------------
    def start_world(self, *parts):
        self.world(ground(), *parts, surfaces=SURFACES)
        self.climb = Climb()
        self.facing = ctypes.c_uint16(0)

    def try_start(self, grounded=True):
        feet = self.feet()
        ok = self.lib.player_climb_start(ctypes.byref(self.climb), ctypes.byref(self.bg),
                                         ctypes.byref(feet), ctypes.byref(self.facing), grounded)
        if ok:
            self.pos = Vec(feet.x, feet.y + EYE, feet.z)
        return ok

    def walk_to_start(self, yaw=0, steps=20):
        for _ in range(steps):
            self.step(yaw=yaw)
            if self.bg.interact and self.bg.shape_yaw_to_wall < 0x3000 and self.try_start():
                return True
        return False

    def climb_step(self, x=0, y=0, a=False):
        feet = self.feet()
        cin = Input(x, y, a, bool(x or y))
        self.lib.player_climb_update(ctypes.byref(self.climb), ctypes.byref(cin),
                                     ctypes.byref(feet), ctypes.byref(self.facing))
        self.pos = Vec(feet.x, feet.y + EYE, feet.z)
        return self.climb.phase

    def climb_until(self, want, steps=400, **kw):
        for i in range(steps):
            if self.climb_step(**kw) in want:
                return i
        self.fail('phase %d not reached (at %d, y %d)' % (min(want), self.climb.phase,
                                                          self.pos.y - EYE))

    # -- start (func_8083EC18) ------------------------------------------------
    def test_ladder_start_centres_faces_and_snaps_to_a_rung(self):
        self.start_world(*ladder_world())
        self.place(x=5, z=-40)
        self.assertTrue(self.walk_to_start())
        self.assertEqual(self.climb.phase, ON)
        self.assertEqual((self.climb.var1, self.climb.var2), (0, -2))
        self.assertEqual(self.lib.link_anim_state(), STATE['CLIMB'])
        self.assertEqual(self.lib.link_anim_move_clip(), self.clips['LADDER_START'])
        # x/z box centre + normal x (dist - 1): 13 in front of the face.
        self.assertEqual((self.pos.x, self.pos.z), (0, -13))
        self.assertEqual(self.facing.value, 0)
        self.assertEqual((self.pos.y - EYE) % 15, 0)

    def test_ladder_start_refusals(self):
        self.start_world(*ladder_world())
        self.place(x=9, z=-40)                     # 9 off the centre: >= 8
        self.assertFalse(self.walk_to_start())
        plain = minus_z(-16, 16, 0, 195, 0)
        self.start_world(plain)
        self.place(z=-40)
        self.assertFalse(self.walk_to_start())     # not climbable
        short = minus_z(-16, 16, 0, 40, 0, LADDER)
        self.start_world(short, quad((-200, 40, 0), (-200, 40, 300), (200, 40, 300), (200, 40, 0)))
        self.place(z=-40)
        self.assertFalse(self.walk_to_start())     # yDistToLedge < 79: a ledge

    # -- climbing (8084BF1C) -----------------------------------------------------
    def test_climb_up_the_ladder_and_off_the_top(self):
        self.start_world(*ladder_world())
        self.place(z=-40)
        self.assertTrue(self.walk_to_start())
        heights = []
        self.climb_until((ENDING,), y=FULL)
        heights.append(self.pos.y - EYE)
        self.assertEqual(self.lib.link_anim_move_clip() in
                         (self.clips['LADDER_ENDBR'], self.clips['LADDER_ENDBL']), True)
        self.assertGreater(heights[0] + 55, TOP)   # the top is within reach
        self.climb_until((DONE,), y=FULL)
        for _ in range(5):
            self.step(speed=0)                     # gravity settles the last unit
        self.assertEqual(self.pos.y - EYE, TOP)    # stood on the platform
        self.assertGreater(self.pos.z, 4)
        self.assertEqual(self.lib.link_anim_state(), STATE['IDLE'])

    def test_rungs_are_15_apart_and_neutral_holds(self):
        self.start_world(*ladder_world())
        self.place(z=-40)
        self.assertTrue(self.walk_to_start())
        self.climb_until((ON,), steps=1)
        while self.climb.var2 < 0:
            self.climb_step(y=FULL)
        start = self.pos.y
        ends = []
        for _ in range(3):
            clip = None
            while True:
                self.climb_step(y=FULL)
                c = self.lib.link_anim_move_clip()
                if clip is not None and c != clip:
                    break
                clip = c
            ends.append(self.pos.y)
        self.assertEqual([b - a for a, b in zip([start] + ends, ends)][1:], [15, 15])
        # Centred, playSpeed is 1.0: the rung in hand finishes, then he holds.
        for _ in range(30):
            self.assertEqual(self.climb_step(), ON)
        held = self.pos.y
        for _ in range(20):
            self.assertEqual(self.climb_step(), ON)
        self.assertEqual(self.pos.y, held)
        self.assertEqual(self.pos.z, -12)          # func_8083F360: 12 from the wall

    def test_climb_down_and_step_off_at_the_bottom(self):
        self.start_world(*ladder_world())
        self.place(z=-40)
        self.assertTrue(self.walk_to_start())
        for _ in range(60):
            self.climb_step(y=FULL)
        self.assertGreater(self.pos.y - EYE, 30)
        self.climb_until((ENDING,), y=-FULL)
        self.assertLess(self.pos.y - EYE, 15 + 15)
        self.assertIn(self.lib.link_anim_move_clip(),
                      (self.clips['LADDER_ENDAL'], self.clips['LADDER_ENDAR']))
        self.climb_until((DONE,), y=-FULL)
        self.assertEqual(self.pos.y - EYE, 0)
        self.assertLess(self.pos.z, 0)

    def test_a_lets_go(self):
        self.start_world(*ladder_world())
        self.place(z=-40)
        self.assertTrue(self.walk_to_start())
        for _ in range(40):
            self.climb_step(y=FULL)
        self.assertEqual(self.climb_step(a=True), LET_GO)

    def test_a_low_lip_is_not_touched_from_above(self):
        """The house lip is 20 high: the wall sphere's centre (+26) is outside
        its box (CirSquareVsTriSquare, +1), so walking at it starts nothing."""
        self.start_world(*ladder_world())
        self.place(z=60, feet=TOP)
        self.assertFalse(self.walk_to_start(yaw=0x8000, steps=9))

    def test_down_from_the_top_at_a_flag2_wall(self):
        """func_8083EC18's WALL_FLAG_2 branch: turn and climb down
        (climb_startB), facing the wall's own yaw."""
        face = minus_z(-16, 16, 0, 195, 0, LADDER)
        lip = plus_z(-16, 16, TOP, TOP + 40, 4, LIP)
        top = quad((-200, TOP, 4), (-200, TOP, 300), (200, TOP, 300), (200, TOP, 4))
        self.start_world(face, lip, top)
        self.place(z=60, feet=TOP)
        self.assertTrue(self.walk_to_start(yaw=0x8000))
        self.assertEqual(self.lib.link_anim_move_clip(), self.clips['LADDER_DOWN'])
        self.assertEqual((self.climb.var1, self.climb.var2), (0, -4))
        self.assertEqual(self.facing.value, 0)     # faces the platform
        self.climb_until((ENDING,), y=-FULL, steps=800)
        self.climb_until((DONE,), y=-FULL)
        self.assertEqual(self.pos.y - EYE, 0)

    # -- vines -----------------------------------------------------------------
    def vine_world(self):
        wall = minus_z(-100, 100, 0, 150, 0, VINE)
        top = quad((-100, 150, 0), (-100, 150, 300), (100, 150, 300), (100, 150, 0))
        self.start_world(wall, top)

    def test_vine_start_side_and_top(self):
        self.vine_world()
        self.place(x=30, z=-40)
        self.assertTrue(self.walk_to_start())
        self.assertEqual((self.climb.var1, self.climb.var2), (2, -2))
        self.assertEqual(self.lib.link_anim_move_clip(), self.clips['VINE_START'])
        self.assertEqual(self.pos.x, 30)           # vines: no centring
        while self.climb.var2 < 0:
            self.climb_step()
        x0 = self.pos.x
        for _ in range(12):
            self.climb_step(x=FULL)
        # Fclimb_sideL: root x 8 -> -1592, 16 units to his right (-x here).
        self.assertLessEqual(self.pos.x, x0 - 15)
        self.climb_until((VINE_TOP,), y=FULL)
        self.assertEqual(self.pos.y - EYE, 150)    # stood on the top to pull up

    def test_vine_bottom_lets_go(self):
        self.vine_world()
        self.place(z=-40)
        self.assertTrue(self.walk_to_start())
        for _ in range(30):
            self.climb_step(y=FULL)
        self.climb_until((LET_GO,), y=-FULL)
        self.assertLess(self.pos.y - EYE, 15)      # within 15 of the floor


FOREST_CASES = FOREST.is_file()


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file() and FOREST_CASES,
                     'host compiler, clips and S1.COL required')
class ForestLadder(PlayerClimb):
    """Link's house ladder in S1.COL: face z 1004, x -45..-13, lip z 1008."""

    def setUp(self):
        bgt.ForestLedges.setUp(self)
        self.climb = Climb()
        self.facing = ctypes.c_uint16(0)

    def test_house_ladder_up_onto_the_porch(self):
        floor = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(-29, 960, 50, ctypes.byref(floor)))
        self.place(-29, floor.value, 960)
        self.assertTrue(self.walk_to_start(yaw=0))
        self.assertEqual(self.lib.link_anim_move_clip(), self.clips['LADDER_START'])
        self.climb_until((DONE,), y=FULL, steps=800)
        for _ in range(5):
            self.step(speed=0)                     # gravity settles the last unit
        self.assertEqual(self.pos.y - EYE, 100)    # the porch
        self.assertGreater(self.pos.z, 1008)
        # Back at the 20-high lip: no wall contact under the source rules
        # (see test_a_low_lip_is_not_touched_from_above). Human check vs OoT.
        self.assertFalse(self.walk_to_start(yaw=0x8000, steps=2))

    def test_forest_vine_wall(self):
        """S1.COL polys 468/469 (wall type 4, WALL_FLAG_3): from the foot at
        (-570, 60, -1036) toward +x, up to the top at 200."""
        self.place(-570, 60, -1036)
        self.assertTrue(self.walk_to_start(yaw=0x4000, steps=30))
        self.assertEqual(self.climb.var1, 2)
        self.climb_until((VINE_TOP,), y=FULL, steps=900)
        self.assertEqual(self.pos.y - EYE, 200)


for _name in [n for n in dir(PlayerClimb) if n.startswith('test_')] + \
             [n for n in dir(bgt.PlayerBg) if n.startswith('test_')]:
    setattr(ForestLadder, _name, None)
for _name in [n for n in dir(bgt.PlayerBg) if n.startswith('test_')]:
    setattr(PlayerClimb, _name, None)


if __name__ == '__main__':
    unittest.main()
