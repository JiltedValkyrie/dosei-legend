"""M1f: crawlspaces (Player_TryEnteringCrawlspace, Player_Action_8084C760,
Player_TryLeavingCrawlspace, Player_Action_8084C81C) on the real Kokiri Forest
sword-maze hole: S1.COL walls type 5 at z 1059/1079 and 1359/1379,
x -801..-769, floor 120.
"""

import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

try:
    import test_player_bg as bgt
except ImportError:
    from tests import test_player_bg as bgt

ROOT = bgt.ROOT
GCC, GEN, EYE, STATE, Vec, Hit, Bg = bgt.GCC, bgt.GEN, bgt.EYE, bgt.STATE, bgt.Vec, bgt.Hit, bgt.Bg
FOREST = ROOT / 'build/cd/S1.COL'
NONE, ENTER, IN, LEAVE, DONE = range(5)
HOLE_X = -785


class Crawl(ctypes.Structure):
    _fields_ = [('phase', ctypes.c_int), ('speed_q8', ctypes.c_int32)]


@unittest.skipUnless(GCC.is_file() and (GEN / 'link_clips.c').is_file() and FOREST.is_file(),
                     'host compiler, clips and S1.COL required')
class ForestCrawlspace(bgt.PlayerBg):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'crawl.dll'
        camera = ROOT.parent / 'shared/lib/camera'
        collision = ROOT.parent / 'shared/lib/collision'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-o', str(out),
                        '-I' + str(camera), '-I' + str(collision), '-I' + str(ROOT / 'src'),
                        '-I' + str(GEN),
                        str(ROOT / 'src/player_crawl.c'), str(ROOT / 'src/player_bg.c'),
                        str(collision / 'kokiri_collision.c'), str(camera / 'kokiri_camera.c'),
                        str(ROOT / 'src/link_anim_state.c'), str(GEN / 'link_clips.c'),
                        str(ROOT / 'tests/fixtures/traversal_host.c'), '-lm'],
                       check=True, env=env)
        cls._bind(ctypes.CDLL(str(out)))
        P = ctypes.POINTER
        cls.lib.player_crawl_enter.argtypes = [P(Crawl), P(Bg), ctypes.c_bool, P(Vec),
                                               P(ctypes.c_uint16)]
        cls.lib.player_crawl_enter.restype = ctypes.c_bool
        cls.lib.player_crawl_prompt.argtypes = [P(Bg), P(Vec)]
        cls.lib.player_crawl_prompt.restype = ctypes.c_bool
        cls.lib.player_crawl_update.argtypes = [P(Crawl), ctypes.c_int32, ctypes.c_bool,
                                                P(Hit), P(Vec), P(ctypes.c_uint16)]

    def setUp(self):
        bgt.ForestLedges.setUp(self)
        self.lib.kokiri_collision_actor_set_crawl(False)
        self.crawl = Crawl()
        self.facing = ctypes.c_uint16(0)
        self.last_wall, self.last_hit = False, Hit()

    def tearDown(self):
        self.lib.kokiri_collision_actor_set_crawl(False)

    def approach(self, x=HOLE_X, yaw=0, steps=30, press_a=True):
        floor = ctypes.c_int32()
        self.assertTrue(self.lib.kokiri_collision_floor(x, 1020, 200, ctypes.byref(floor)))
        self.place(x, floor.value, 1020)
        for _ in range(steps):
            self.step(yaw=yaw)
            if self.bg.interact and self.bg.shape_yaw_to_wall < 0x3000:
                feet, facing = self.feet(), ctypes.c_uint16(yaw)
                if self.lib.player_crawl_enter(ctypes.byref(self.crawl), ctypes.byref(self.bg),
                                               press_a, ctypes.byref(feet), ctypes.byref(facing)):
                    self.pos = Vec(feet.x, feet.y + EYE, feet.z)
                    self.facing = facing
                    return True
        return False

    def crawl_step(self, stick_y):
        """demo.c's order: the action on last step's wall, then the move."""
        lib = self.lib
        feet = self.feet()
        lib.player_crawl_update(ctypes.byref(self.crawl), stick_y, self.last_wall,
                                ctypes.byref(self.last_hit), ctypes.byref(feet),
                                ctypes.byref(self.facing))
        self.pos = Vec(feet.x, feet.y + EYE, feet.z)
        lib.kokiri_collision_actor_begin_step()
        if self.crawl.phase == IN and self.crawl.speed_q8:
            yaw = self.facing.value if self.crawl.speed_q8 > 0 else (self.facing.value + 0x8000) & 0xFFFF
            lib.kokiri_camera_move_heading(ctypes.byref(self.pos), yaw, abs(self.crawl.speed_q8))
        if self.lib.link_anim_state() != STATE['CLIMB']:
            lib.kokiri_collision_fall(ctypes.byref(self.pos), ctypes.byref(self.vel),
                                      ctypes.byref(self.rem))
        lib.kokiri_collision_actor_probe_still(ctypes.byref(self.pos))
        stepped, hit = ctypes.c_bool(), Hit()
        self.last_wall = lib.kokiri_collision_actor_wall(ctypes.byref(stepped), ctypes.byref(hit))
        if self.last_wall:
            self.last_hit = hit
        return self.crawl.phase

    def crawl_until(self, want, stick_y, steps=600):
        for _ in range(steps):
            if self.crawl_step(stick_y) == want:
                return
        self.fail('phase %d not reached (at %d, z %d)' % (want, self.crawl.phase, self.pos.z))

    def test_standing_cannot_bypass_the_hole(self):
        self.assertFalse(self.approach(press_a=False))
        self.assertLess(self.pos.z, 1059)

    def test_enter_prompt_only_in_front_of_the_hole(self):
        """PLAYER_STATE2_DO_ACTION_ENTER: shown at the hole's centre line,
        not 9 off it, and without A nothing enters."""
        for x, shown in ((HOLE_X, True), (HOLE_X + 9, False)):
            with self.subTest(x=x):
                self.assertFalse(self.approach(x=x, press_a=False))
                feet = self.feet()
                self.assertTrue(self.bg.interact)
                self.assertEqual(self.lib.player_crawl_prompt(ctypes.byref(self.bg),
                                                              ctypes.byref(feet)), shown)

    def test_off_centre_gets_no_prompt(self):
        self.assertFalse(self.approach(x=HOLE_X + 9))

    def test_crawl_through_forwards(self):
        self.assertTrue(self.approach())
        self.assertEqual(self.crawl.phase, ENTER)
        self.assertEqual((self.pos.x, self.facing.value), (HOLE_X, 0))
        self.assertEqual(self.lib.link_anim_state(), STATE['CLIMB'])
        self.crawl_until(IN, 80)
        self.assertEqual(self.lib.link_anim_state(), STATE['CRAWL'])
        self.assertGreater(self.pos.z, 1059)
        self.crawl_until(LEAVE, 80)
        self.assertGreater(self.pos.z, 1300)
        self.assertEqual(self.facing.value, 0)
        self.crawl_until(DONE, 80)
        self.assertGreater(self.pos.z, 1379)             # out the far side
        self.assertEqual(self.lib.link_anim_state(), STATE['IDLE'])

    def test_back_out_the_way_he_came(self):
        self.assertTrue(self.approach())
        self.crawl_until(IN, 80)
        for _ in range(20):
            self.crawl_step(80)
        self.crawl_until(LEAVE, -80)
        self.assertEqual(self.facing.value, 0)          # the exit wall's own yaw
        self.crawl_until(DONE, -80)
        self.assertLess(self.pos.z, 1059)                # back outside


for _name in [n for n in dir(bgt.PlayerBg) if n.startswith('test_')]:
    setattr(ForestCrawlspace, _name, None)


if __name__ == '__main__':
    unittest.main()
