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

    def test_handle_does_not_follow_reused_slot(self):
        slot = self.spawn(NPC)
        old = self.lib.as_handle(slot)
        self.assertNotEqual(old, 0)
        self.lib.as_kill(slot)
        self.assertEqual(self.spawn(ENEMY), slot)
        self.assertEqual(self.lib.as_resolve(old), -1)
        fresh = self.lib.as_handle(slot)
        self.assertNotEqual(fresh, old)
        self.assertEqual(self.lib.as_resolve(fresh), slot)

    def test_handle_invalidated_before_deferred_reap(self):
        slot = self.spawn(NPC, params=1)
        old = self.lib.as_handle(slot)
        self.lib.actor_sys_update()
        self.assertEqual(self.lib.as_dead_handle_resolved(), 0)
        self.assertEqual(self.lib.as_resolve(old), -1)

    def test_handle_survives_persistent_scene_actor_only(self):
        ordinary = self.lib.as_handle(self.spawn(NPC))
        keep = self.lib.as_handle(self.spawn(KEEP))
        self.lib.actor_sys_scene_unload()
        self.assertEqual(self.lib.as_resolve(ordinary), -1)
        self.assertNotEqual(self.lib.as_resolve(keep), -1)
        self.lib.actor_sys_clear()
        self.assertEqual(self.lib.as_resolve(keep), -1)

    def test_pool_reinit_does_not_revive_handles(self):
        slot = self.spawn(NPC)
        old = self.lib.as_handle(slot)
        self.lib.as_reset()
        self.assertEqual(self.spawn(NPC), slot)
        self.assertEqual(self.lib.as_resolve(old), -1)
        self.assertEqual(self.lib.as_resolve(0), -1)

    def test_pool_still_fits_fixed_cart_carve(self):
        self.assertLessEqual(self.lib.actor_sys_bytes(), 8192)

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

    def test_oc_push_goes_through_world_checks(self):
        """A pool actor pushed toward a wall stops at it (collide_world_push)."""
        self.assertEqual(self.lib.as_reset(), 1)
        a, b = self.spawn(NPC), self.spawn(NPC, x=30)
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(0, a)
        self.lib.co_cyl(1, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(1, b)
        self.lib.co_oc(0, OC_ON | OC_T1, OC_T1)
        self.lib.co_oc(1, OC_ON | OC_T1, OC_T1)
        self.lib.co_wall(33)
        self.lib.co_run()
        self.lib.co_apply(1)
        self.lib.co_wall(0x7FFFFFFF)
        self.assertEqual(self.lib.as_x(b), 33)

    def elements_case(self, grouped):
        self.assertEqual(self.lib.as_reset(), 1)
        enemy, victim = self.spawn(ENEMY), self.spawn(NPC, x=10)
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 30, 40, 50)
        self.lib.co_bind(0, enemy)
        self.lib.co_at(0, DMG_SLASH, 2, AT_ENEMY)
        for i in (1, 2):
            self.lib.co_cyl(i, 5 * i, 0, 0, 10, 40, 50)
            self.lib.co_bind(i, victim)
            if grouped:
                self.lib.co_element(i)
            self.lib.co_ac(i, 0xFFFFFFFF, 0, 0, AT_ENEMY, 0)
        self.lib.co_run()
        return self.lib.co_events()

    def test_one_at_takes_one_element_of_a_multi_element_actor(self):
        """BUG-030: JntSph elements of one actor take one hit per AT per pass."""
        self.assertEqual(self.elements_case(True), 1)
        self.assertEqual(self.elements_case(False), 2)   # separate colliders

    def test_fifth_live_attack_evicts_and_invincibility_holds(self):
        """History is bounded (4); actor-level i-frames are the real guard."""
        self.lib.co_clear()
        self.lib.co_cyl(1, 0, 0, 0, 20, 40, 50)
        hits = [self.step(attack_id=a) for a in (1, 2, 3, 4, 1)]
        self.assertEqual(hits, [1, 1, 1, 1, 0])           # remembered
        hits = [self.step(attack_id=a) for a in (5, 1)]
        self.assertEqual(hits, [1, 1])                    # 1 evicted by 5
        self.lib.co_begin()
        self.swing(attack_id=6)
        self.lib.co_ac(1, 0xFFFFFFFF, 0, 0, AT_PLAYER, 30)
        self.lib.co_run()
        self.assertEqual(self.lib.co_events(), 0)         # victim intangible

    def test_oc_type_mismatch_skips(self):
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_cyl(1, 30, 0, 0, 20, 40, 50)
        self.lib.co_oc(0, OC_ON | OC_T1, OC_T1)
        self.lib.co_oc(1, OC_ON | OC_PLAYER, OC_PLAYER)
        self.lib.co_run()
        self.assertEqual(self.lib.co_oc_hit(0), -1)

    # ---- M2b contact loop -------------------------------------------------
    def swing(self, attack_id=7, tag=0):
        """Attacker 0 at the origin; victims overlap it."""
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_attack(0, attack_id, tag)
        self.lib.co_at(0, DMG_SLASH, 2, AT_PLAYER)

    def victims(self, *indices):
        for i in indices:
            self.lib.co_ac(i, 0xFFFFFFFF, 0, 0, AT_PLAYER, 0)

    def step(self, attack_id=7, tag=0, victims=(1,)):
        self.lib.co_begin()
        self.swing(attack_id, tag)
        self.victims(*victims)
        self.lib.co_run()
        return self.lib.co_events()

    def test_one_attack_hits_every_victim_once(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.lib.co_cyl(2, -10, 0, 0, 20, 40, 50)
        self.assertEqual(self.step(victims=(1, 2)), 2)
        self.assertEqual(self.lib.co_at_hits(0), 2)
        self.assertEqual({self.lib.co_event(0, 3), self.lib.co_event(1, 3)}, {7})
        # Next step, overlap lingers: the same attack instance cannot re-hit.
        self.assertEqual(self.step(victims=(1, 2)), 0)
        self.assertEqual(self.lib.co_ac_hit(1), -1)
        # A new attack instance does hit again.
        self.assertEqual(self.step(attack_id=8, victims=(1, 2)), 2)

    def test_separate_attackers_with_same_counter_both_hit(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.assertEqual(self.step(tag=1), 1)
        self.assertEqual(self.step(tag=2), 1)

    def test_untracked_attack_rehits_and_forget_rearms(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.assertEqual(self.step(attack_id=0), 1)
        self.assertEqual(self.step(attack_id=0), 1)
        self.assertEqual(self.step(), 1)
        self.assertEqual(self.step(), 0)
        self.lib.co_forget(1)
        self.assertEqual(self.step(), 1)

    def guard_case(self, shield_first, shield_dx=2):
        """Enemy attacker 0; Link's body 1 and hard shield 2 (both Link's)."""
        self.assertEqual(self.lib.as_reset(), 1)
        enemy, link = self.spawn(ENEMY), self.spawn(NPC, x=10)
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(0, enemy)
        self.lib.co_at(0, DMG_SLASH, 2, AT_ENEMY)
        self.lib.co_cyl(1, 0, 0, 0, 10, 40, 50)
        self.lib.co_bind(1, link)
        self.lib.co_cyl(2, shield_dx, 0, 0, 6, 40, 50)
        self.lib.co_bind(2, link)
        self.lib.co_hard(2)
        for i in ((2, 1) if shield_first else (1, 2)):
            self.lib.co_ac(i, 0xFFFFFFFF, 0, 0, AT_ENEMY, 0)
        self.lib.co_run()
        return enemy, link

    def test_shield_bounce_wins_regardless_of_registration_order(self):
        for first in (True, False):
            enemy, link = self.guard_case(first)
            self.assertEqual(self.lib.co_guard(2), 1, first)
            self.assertTrue(self.lib.co_result(0) & 2)          # AT_BOUNCED
            self.assertEqual(self.lib.co_ac_actor(1), self.lib.as_handle(enemy))
            self.assertEqual(self.lib.co_ac_actor(2), self.lib.as_handle(enemy))
            self.assertEqual(self.lib.co_at_actor(0) in
                             (self.lib.as_handle(link),), True)

    def test_guard_misses_when_shield_is_not_struck(self):
        self.guard_case(True, shield_dx=200)
        self.assertEqual(self.lib.co_guard(2), 0)
        self.assertEqual(self.lib.co_damage(1), 2)
        self.assertEqual(self.lib.co_result(0) & 2, 0)

    def test_hard_bounce_needs_actors_on_both_sides(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.lib.co_hard(1)
        self.assertEqual(self.step(), 1)
        self.assertEqual(self.lib.co_guard(1), 0)
        self.assertEqual(self.lib.co_event(0, 5), 0)

    def test_outside_pool_owners_count_as_actors_for_hard_bounce(self):
        """Link and the boulder live outside actor_sys but are source actors."""
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_outside(0)
        self.lib.co_at(0, DMG_SLASH, 2, AT_ENEMY)
        self.lib.co_cyl(1, 10, 0, 0, 10, 40, 50)
        self.lib.co_hard(1)
        self.lib.co_outside(1)
        self.lib.co_ac(1, 0xFFFFFFFF, 0, 0, AT_ENEMY, 0)
        self.lib.co_run()
        self.assertEqual(self.lib.co_guard(1), 1)

    def test_teardown_invalidates_contacts_before_slot_reuse(self):
        victim = self.spawn(ENEMY, x=10)
        self.lib.co_clear()
        self.lib.co_cyl(1, -10, 0, 0, 20, 40, 50)
        self.lib.co_bind(1, victim)
        self.assertEqual(self.step(), 1)
        held = self.lib.co_event(0, 1)
        self.assertEqual(self.lib.as_resolve(held), victim)
        self.lib.as_kill(victim)
        self.assertEqual(self.lib.as_resolve(held), -1)      # before reap
        self.lib.actor_sys_update()
        self.assertEqual(self.spawn(NPC, x=10), victim)      # slot reused
        self.assertEqual(self.lib.as_resolve(held), -1)
        # Killed before the run: no contact at all.
        self.lib.as_kill(victim)
        self.lib.co_forget(1)
        self.assertEqual(self.step(attack_id=9), 0)

    def test_bug028_registered_colliders_do_not_follow_reused_slots(self):
        # Victim replaced between registration and run.
        victim = self.spawn(ENEMY, x=10)
        self.lib.co_clear()
        self.lib.co_cyl(1, -10, 0, 0, 20, 40, 50)
        self.lib.co_bind(1, victim)
        self.swing()
        self.victims(1)
        self.lib.as_kill(victim)
        self.lib.actor_sys_update()
        self.assertEqual(self.spawn(NPC, x=10), victim)
        self.lib.co_run()
        self.assertEqual(self.lib.co_events(), 0)
        # Attacker replaced between registration and run.
        self.assertEqual(self.lib.as_reset(), 1)
        attacker = self.spawn(ENEMY)
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(0, attacker)
        self.lib.co_at(0, DMG_SLASH, 2, AT_PLAYER)
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.victims(1)
        self.lib.as_kill(attacker)
        self.lib.actor_sys_update()
        self.assertEqual(self.spawn(NPC), attacker)
        self.lib.co_run()
        self.assertEqual(self.lib.co_events(), 0)
        # OC partner replaced: no hit, no push onto the replacement.
        self.assertEqual(self.lib.as_reset(), 1)
        a, b = self.spawn(ENEMY), self.spawn(ENEMY, x=30)
        self.lib.co_clear()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(0, a)
        self.lib.co_cyl(1, 0, 0, 0, 20, 40, 50)
        self.lib.co_bind(1, b)
        self.lib.co_oc(0, OC_ON | OC_T1 | OC_PLAYER, OC_PLAYER)
        self.lib.co_oc(1, OC_ON | OC_PLAYER, OC_T1)
        self.lib.as_kill(b)
        self.lib.actor_sys_update()
        self.assertEqual(self.spawn(NPC, x=30), b)
        self.lib.co_run()
        self.assertEqual(self.lib.co_oc_hit(0), -1)
        self.assertEqual(self.lib.co_disp_x(0), 0)

    def test_bug029_alternating_attacks_hit_once_each(self):
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.assertEqual([self.step(tag=t) for t in (1, 2, 1, 2)], [1, 1, 0, 0])
        # Same with distinct attacker actors.
        self.assertEqual(self.lib.as_reset(), 1)
        actors = (self.spawn(ENEMY), self.spawn(ENEMY))
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        counts = []
        for who in (0, 1, 0):
            self.lib.co_begin()
            self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
            self.lib.co_bind(0, actors[who])
            self.lib.co_attack(0, 7, 0)
            self.lib.co_at(0, DMG_SLASH, 2, AT_PLAYER)
            self.victims(1)
            self.lib.co_run()
            counts.append(self.lib.co_events())
        self.assertEqual(counts, [1, 1, 0])

    def test_victim_memory_bound_is_explicit(self):
        # COLLIDE_SEEN_MAX = 4: a fifth distinct attack evicts the oldest.
        self.lib.co_clear()
        self.lib.co_cyl(1, 10, 0, 0, 20, 40, 50)
        self.assertEqual([self.step(tag=t) for t in (1, 2, 3, 4)], [1] * 4)
        self.assertEqual([self.step(tag=t) for t in (2, 3, 4)], [0] * 3)
        self.assertEqual(self.step(tag=5), 1)
        self.assertEqual(self.step(tag=1), 1)       # evicted: documented limit

    def test_list_overflow_is_counted(self):
        self.lib.co_clear()
        self.lib.co_overflow_reset()
        self.assertEqual(self.lib.co_flood(33), 32)
        self.assertEqual(self.lib.co_overflow(), 1)
        self.lib.co_overflow_reset()
        self.assertEqual(self.lib.co_overflow(), 0)

    def test_event_log_is_bounded(self):
        self.lib.co_clear()
        self.lib.co_overflow_reset()
        self.lib.co_cyl(0, 0, 0, 0, 20, 40, 50)
        self.lib.co_at(0, DMG_SLASH, 1, AT_PLAYER)
        self.assertEqual(self.lib.co_flood_hits(32), 32)
        self.lib.co_run()
        self.assertEqual(self.lib.co_events(), 32)
        self.assertEqual(self.lib.co_overflow(), 0)

    def test_sector_matches_slice_swing_reach(self):
        self.lib.co_clear()
        self.lib.co_sector(0, 0, 0, 0, 66, 60, 0, 16384)
        for x, y, z, hit in ((0, 0, 60, 1), (0, 0, 67, 0), (0, 61, 30, 0),
                             (30, 0, 1, 1), (30, 0, -5, 0), (-40, 40, 40, 1)):
            self.lib.co_cyl(1, x, y, z, 0, 0, 50)
            self.assertEqual(self.lib.co_overlap(0, 1) > 0, bool(hit), (x, y, z))

if __name__ == '__main__':
    unittest.main()
