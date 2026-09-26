"""Actor pool and actor-vs-actor collision check (M0 skeleton).

actor_sys.c follows OoT ActorContext rules: category-ordered update, deferred
kill, room ownership, persistent actors, per-scene flag hooks. collide.c
follows z_collision_check.c: AT/AC alignment + DMG bits, DamageTable lookup
by highest DMG bit, OC mass push-out.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

NPC, ENEMY, SWITCH, KEEP, FAIL = range(5)
ATTN_NPC, ATTN_ENEMY = 1, 2
CAT_SWITCH, CAT_NPC, CAT_ENEMY, CAT_MISC = 0, 4, 5, 8
AT_PLAYER, AT_ENEMY = 1 << 3, 1 << 4
DMG_NUT, DMG_SLASH, DMG_SPIN = 1 << 0, 1 << 8, 1 << 22
OC_ON, OC_PLAYER, OC_T1 = 1, 1 << 3, 1 << 4
MASS_IMMOVABLE, MASS_HEAVY = 0xFF, 0xFE
HYRULE_FIELD = 10


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class ActorSys(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name) / 'actor_sys.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-o', str(out),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'tests/fixtures/actor_sys_host.c'),
                        str(ROOT / 'src/actor_sys.c'), str(ROOT / 'src/collide.c'),
                        str(ROOT / 'src/save_state.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(out))

    def setUp(self):
        self.lib.save_new_game()
        self.assertEqual(self.lib.as_reset(), 1)

    def spawn(self, kind, room=0, x=0, z=0, params=0, attention=0, scene=0):
        return self.lib.as_spawn(kind, scene, room, x, z, params, attention)

    # ---- pool -----------------------------------------------------------
    def test_storage_too_small_is_refused(self):
        self.assertEqual(self.lib.as_init_small(), 0)

    def test_spawn_runs_init_and_fills_to_capacity(self):
        slots = [self.spawn(NPC) for _ in range(64)]
        self.assertEqual(sorted(slots), list(range(64)))
        self.assertEqual(self.lib.as_inits(), 64)
        self.assertEqual(self.lib.as_data0(0), 7)
        self.assertEqual(self.spawn(NPC), -1)
        self.assertEqual(self.lib.actor_sys_live(), 64)

    def test_init_self_kill_returns_no_actor(self):
        self.assertEqual(self.spawn(FAIL), -1)
        self.assertEqual(self.lib.actor_sys_live(), 0)
        self.assertEqual(self.lib.as_destroys(), 1)

    def test_update_is_category_ordered(self):
        self.spawn(ENEMY)
        self.spawn(NPC)
        self.spawn(SWITCH)
        self.lib.actor_sys_update()
        order = [self.lib.as_order(i) for i in range(self.lib.as_order_len())]
        self.assertEqual(order, [CAT_SWITCH, CAT_NPC, CAT_ENEMY])

    def test_kill_during_update_is_deferred_then_reaped(self):
        a = self.spawn(NPC, params=1)
        b = self.spawn(NPC)
        self.lib.actor_sys_update()
        self.assertEqual(self.lib.as_updates(), 2)
        self.assertEqual(self.lib.as_data0(a), -1)
        self.assertEqual(self.lib.as_data0(b), 7)
        self.assertEqual(self.lib.as_destroys(), 1)
        self.lib.actor_sys_draw()
        self.assertEqual(self.lib.as_draws(), 1)

    def test_room_unload_keeps_scene_wide_and_persistent(self):
        room0 = self.spawn(NPC, room=0)
        room1 = self.spawn(NPC, room=1)
        wide = self.spawn(NPC, room=-1)
        keep = self.spawn(KEEP, room=0)
        self.lib.actor_sys_room_unload(0)
        self.assertEqual(self.lib.as_data0(room0), -1)
        self.assertEqual(self.lib.as_data0(room1), 7)
        self.assertEqual(self.lib.as_data0(wide), 7)
        self.assertEqual(self.lib.as_data0(keep), 7)
        self.lib.actor_sys_scene_unload()
        self.assertEqual(self.lib.actor_sys_live(), 1)
        self.assertEqual(self.lib.as_data0(keep), 7)

    def test_find_iterates_by_id(self):
        self.spawn(NPC); self.spawn(ENEMY); self.spawn(NPC)
        self.assertEqual(self.lib.as_find_count(1), 2)
        self.assertEqual(self.lib.as_find_count(2), 1)

    def test_nearest_attention_respects_mask_and_range(self):
        far_npc = self.spawn(NPC, x=300, attention=ATTN_NPC)
        near_enemy = self.spawn(ENEMY, x=100, attention=ATTN_ENEMY)
        self.spawn(SWITCH, x=10, attention=ATTN_NPC)     # not targetable
        self.assertEqual(self.lib.as_nearest(0, 0, 400, 1 << ATTN_NPC), far_npc)
        self.assertEqual(self.lib.as_nearest(0, 0, 400, (1 << ATTN_NPC) | (1 << ATTN_ENEMY)), near_enemy)
        self.assertEqual(self.lib.as_nearest(0, 0, 200, 1 << ATTN_NPC), -1)

    def test_nearest_attention_far_diagonal_does_not_overflow(self):
        # Astra M0 review: (40000,40000) is ~56569 away, outside range 46340.
        self.spawn(NPC, x=40000, z=40000, attention=ATTN_NPC)
        self.assertEqual(self.lib.as_nearest(0, 0, 46340, 1 << ATTN_NPC), -1)
        near = self.spawn(NPC, x=30000, z=30000, attention=ATTN_NPC)  # ~42426
        self.assertEqual(self.lib.as_nearest(0, 0, 46340, 1 << ATTN_NPC), near)
        self.assertEqual(self.lib.as_nearest(0, 0, 1 << 20, 1 << ATTN_NPC), near)

    def test_flag_hooks_write_the_actors_scene(self):
        a = self.spawn(NPC, scene=HYRULE_FIELD)
        self.assertEqual(self.lib.as_flag_round_trip(a, 5), 0x0F)
        self.assertTrue(self.lib.save_get_treasure(HYRULE_FIELD, 5) & 0xFF)
        self.assertFalse(self.lib.save_get_treasure(0, 5) & 0xFF)

    # ---- collide --------------------------------------------------------
    def test_isqrt(self):
        for v in (0, 1, 2, 15, 16, 17, 9999, 1 << 30, 0xFFFFFFFF):
            r = self.lib.collide_isqrt(ctypes.c_uint32(v)) & 0xFFFFFFFF
            self.assertLessEqual(r * r, v)
            self.assertGreater((r + 1) * (r + 1), v)

    def test_cylinder_overlap_needs_height_and_radius(self):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 50, 50)
        self.lib.co_cyl(1, 30, 0, 0, 20, 50, 50)
        self.assertEqual(self.lib.co_overlap(0, 1), 10)
        self.lib.co_cyl(1, 30, 51, 0, 20, 50, 50)
        self.assertEqual(self.lib.co_overlap(0, 1), -1)
        self.lib.co_cyl(1, 40, 0, 0, 20, 50, 50)
        self.assertEqual(self.lib.co_overlap(0, 1), -1)

    def test_sword_capsule_hits_enemy_with_table_damage(self):
        self.lib.co_clear()
        self.lib.co_capsule(0, 0, 30, 0, 60, 30, 0, 5)
        self.lib.co_cyl(1, 50, 0, 10, 15, 40, 50)
        self.lib.co_at(0, DMG_SLASH, 1, AT_PLAYER)
        self.lib.co_ac(1, 0xFFFFFFFF, 1, 0, AT_PLAYER, 0)
        self.lib.co_run()
        self.assertEqual(self.lib.co_ac_hit(1), 0)
        self.assertEqual(self.lib.co_at_hit(0), 1)
        self.assertEqual(self.lib.co_damage(1), 2)

    def test_capsule_vertical_and_sloped_contacts(self):
        # Astra M0 review cases: both previously returned no contact.
        self.lib.co_clear()
        self.lib.co_capsule(0, 0, 0, 0, 0, 100, 0, 5)
        self.lib.co_cyl(1, 0, 40, 0, 10, 20, 50)
        self.assertEqual(self.lib.co_overlap(0, 1), 15)
        self.lib.co_capsule(0, 0, 0, 0, 100, 100, 0, 5)
        self.lib.co_cyl(1, 0, 40, 0, 50, 20, 50)
        self.assertGreater(self.lib.co_overlap(0, 1), 0)
        self.assertGreater(self.lib.co_overlap(1, 0), 0)     # either order

    def test_capsule_misses_outside_height_and_reach(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 0, 40, 0, 10, 20, 50)
        self.lib.co_capsule(0, 0, 0, 0, 0, 30, 0, 4)          # stops below 36
        self.assertEqual(self.lib.co_overlap(0, 1), -1)
        self.lib.co_capsule(0, 0, 70, 0, 0, 100, 0, 4)        # starts above 64
        self.assertEqual(self.lib.co_overlap(0, 1), -1)
        self.lib.co_capsule(0, 20, 0, 0, 20, 100, 0, 5)       # xz 20 >= 15
        self.assertEqual(self.lib.co_overlap(0, 1), -1)
        self.lib.co_capsule(0, 100, 100, 0, 0, 0, 0, 5)       # reversed slope
        self.lib.co_cyl(1, 0, 40, 0, 50, 20, 50)
        self.assertGreater(self.lib.co_overlap(0, 1), 0)
        self.lib.co_capsule(0, -30, 50, 0, 30, 50, 0, 5)      # flat, inside span
        self.lib.co_cyl(1, 0, 40, 0, 10, 20, 50)
        self.assertEqual(self.lib.co_overlap(0, 1), 15)

    def test_table_uses_highest_dmg_bit_and_reaction(self):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.lib.co_at(0, DMG_NUT, 0, AT_PLAYER)
        self.lib.co_ac(1, 0xFFFFFFFF, 1, 0, AT_PLAYER, 0)
        self.lib.co_run()
        self.assertEqual((self.lib.co_damage(1), self.lib.co_effect(1)), (0, 1))
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.lib.co_at(0, DMG_SPIN | DMG_SLASH, 0, AT_PLAYER)
        self.lib.co_ac(1, 0xFFFFFFFF, 1, 0, AT_PLAYER, 0)
        self.lib.co_run()
        self.assertEqual(self.lib.co_damage(1), 4)

    def test_no_table_uses_damage_minus_defense(self):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.lib.co_at(0, DMG_SLASH, 3, AT_ENEMY)
        self.lib.co_ac(1, 0xFFFFFFFF, 0, 1, AT_ENEMY, 0)
        self.lib.co_run()
        self.assertEqual(self.lib.co_damage(1), 2)

    def test_alignment_bumper_and_invincibility_block_hits(self):
        for at_type, bumper, inv in ((AT_ENEMY, 0xFFFFFFFF, 0),
                                     (AT_PLAYER, DMG_NUT, 0),
                                     (AT_PLAYER, 0xFFFFFFFF, 3)):
            self.lib.co_clear()
            self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
            self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
            self.lib.co_at(0, DMG_SLASH, 1, at_type)
            self.lib.co_ac(1, bumper, 0, 0, AT_PLAYER, inv)
            self.lib.co_run()
            self.assertEqual(self.lib.co_ac_hit(1), -1)
        self.lib.co_tick(1)
        self.assertEqual(self.lib.co_invincible(1), 2)

    def oc_pair(self, mass_a, mass_b):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, mass_a)
        self.lib.co_cyl(1, 30, 0, 0, 20, 40, mass_b)
        self.lib.co_oc(0, OC_ON | OC_T1 | OC_PLAYER, OC_PLAYER)
        self.lib.co_oc(1, OC_ON | OC_PLAYER, OC_T1)
        self.lib.co_run()
        return self.lib.co_disp_x(0), self.lib.co_disp_x(1)

    def test_oc_mass_rules(self):
        self.assertEqual(self.oc_pair(50, 50), (-5, 5))
        self.assertEqual(self.oc_pair(MASS_IMMOVABLE, 50), (0, 10))
        self.assertEqual(self.oc_pair(MASS_HEAVY, 50), (0, 10))
        self.assertEqual(self.oc_pair(50, MASS_HEAVY), (-10, 0))
        self.assertEqual(self.oc_pair(MASS_HEAVY, MASS_HEAVY), (-5, 5))
        self.assertEqual(self.oc_pair(MASS_IMMOVABLE, MASS_IMMOVABLE), (0, 0))
        self.assertEqual(self.lib.co_oc_hit(0), 1)
        self.lib.co_apply(1)
        self.assertEqual(self.lib.co_x(1), 30)

    def test_oc_type_mismatch_skips(self):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_cyl(1, 30, 0, 0, 20, 40, 50)
        self.lib.co_oc(0, OC_ON | OC_T1, OC_T1)
        self.lib.co_oc(1, OC_ON | OC_PLAYER, OC_PLAYER)
        self.lib.co_run()
        self.assertEqual(self.lib.co_oc_hit(0), -1)


if __name__ == '__main__':
    unittest.main()
