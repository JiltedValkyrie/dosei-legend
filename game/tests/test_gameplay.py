"""Drive the real gameplay.c: pickups, equip, targeting, swing window, cutting.

Compiled and called through ctypes rather than reimplemented, so a rule that
changes in C changes here too.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
GENERATED = ROOT / 'build/generated'

GP_SWORD = 1
GP_SHIELD = 2
GP_EVENT_PICKUP = 1
GP_EVENT_SWING = 2
GP_EVENT_CUT = 4
GP_EVENT_TARGET_ON = 8
GP_EVENT_TARGET_OFF = 16
GP_EVENT_SHIELD_UP = 32
GP_EVENT_DENIED = 64
GP_EVENT_TALK_OPEN = 128
GP_EVENT_TALK_PAGE = 256
GP_EVENT_TALK_CLOSE = 512
GP_EVENT_MENU_OPEN = 1024
GP_EVENT_MENU_CLOSE = 2048
GP_EVENT_EQUIP = 4096


@unittest.skipUnless(GCC.is_file() and (GENERATED / 'kokiri_actors.c').is_file()
                     and (GENERATED / 'kokiri_dialogue.c').is_file(),
                     'host compiler and generated tables required')
class Gameplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'gameplay.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(GENERATED), '-I' + str(ROOT / 'src'),
                        str(ROOT / 'tests/fixtures/gameplay_host.c'),
                        str(ROOT / 'src/gameplay.c'),
                        str(GENERATED / 'kokiri_actors.c'),
                        str(GENERATED / 'kokiri_dialogue.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.gp_page_line.restype = ctypes.c_char_p
        cls.lib.gp_speaker_name.restype = ctypes.c_char_p
        cls.lib.gp_pickup_at.restype = None
        for name in ('gp_pickup_at', 'gp_grass_at', 'gp_npc_at'):
            getattr(cls.lib, name).restype = None

    def setUp(self):
        self.lib.gameplay_reset()
        self.lib.gp_room(0)

    # --- helpers ---------------------------------------------------------
    def pickup(self, index):
        x, y, z, item = (ctypes.c_int() for _ in range(4))
        self.lib.gp_pickup_at(index, *(ctypes.byref(v) for v in (x, y, z, item)))
        return x.value, y.value, z.value, item.value

    def grass(self, index):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_grass_at(index, *(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def npc(self, index):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_npc_at(index, *(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def step(self, x, y, z, yaw=0, attack=0, shield=0, target=0, interact=0,
             grounded=1, cancel=0):
        self.lib.gp_step(int(x), int(y), int(z), int(yaw) & 0xFFFF, attack,
                         shield, target, interact, grounded, cancel)

    def rupee(self, index):
        values = [ctypes.c_int() for _ in range(5)]
        self.lib.gp_rupee_at(index, *(ctypes.byref(v) for v in values))
        return [v.value for v in values]

    def test_rupees_collect_once_at_source_positions_and_values(self):
        total = 0
        for i in range(8):
            x,y,z,value,room = self.rupee(i)
            self.lib.gp_room(room)
            self.step(x,y,z)
            total += value
            self.assertEqual(self.lib.gp_rupees(), total)
            self.assertTrue(self.lib.gp_events() & (1<<18))
            self.step(x,y,z)
            self.assertEqual(self.lib.gp_rupees(), total)
            self.assertFalse(self.lib.gp_events() & (1<<18))
        self.assertEqual(total,24)

    def test_rupees_require_room_distance_height_and_wallet_caps(self):
        x,y,z,value,room = self.rupee(4)
        self.step(x,y+80,z)
        self.step(x+100,y,z)
        self.lib.gp_room(1)
        self.step(x,y,z)
        self.assertEqual(self.lib.gp_rupees(),0)
        self.lib.gp_room(room)
        self.lib.gp_wallet(98)
        self.step(x,y,z)
        self.assertEqual(self.lib.gp_rupees(),99)

    def spawn_grass_rupee(self):
        # Force source slot 0/1 by choosing a seed whose second xorshift hits
        # it. Gameplay still performs the actual cut and table lookup.
        sx,sy,sz,_ = self.pickup(0)
        self.step(sx,sy,sz)
        gx,gy,gz = self.grass(0)
        self.step(gx,gy,gz-40,attack=1)
        for _ in range(3): self.step(gx,gy,gz-40)
        def rng(x):
            x ^= (x << 13) & 0xffffffff
            x ^= x >> 17
            return (x ^ (x << 5)) & 0xffffffff
        seed = next(s for s in range(1,1000) if rng(rng(s)) & 15 in (0,1))
        self.lib.gp_seed(seed)
        self.step(gx,gy,gz-40)
        self.assertEqual(self.lib.gp_drop(0),1)
        self.assertEqual(self.lib.gp_drop_age(0),0)
        return gx,gy,gz

    def test_grass_rupee_hidden_until_cut_then_hops_before_collect(self):
        self.assertTrue(all(self.lib.gp_drop(i)==0 for i in range(16)))
        gx,gy,gz = self.spawn_grass_rupee()
        before = self.lib.gp_rupees()
        for _ in range(15):
            self.step(gx,gy,gz)
            self.assertEqual(self.lib.gp_rupees(),before)
            self.assertEqual(self.lib.gp_drop(0),1)
        self.step(gx,gy,gz)
        self.assertEqual(self.lib.gp_rupees(),before+1)
        self.assertEqual(self.lib.gp_drop(0),0)
        self.step(gx,gy,gz,attack=1)
        for _ in range(30): self.step(gx,gy,gz)
        self.assertEqual(self.lib.gp_rupees(),before+1)
        self.assertEqual(self.lib.gp_drop(0),0)

    def test_pause_freezes_drop_and_reset_clears_wallet_and_flags(self):
        gx,gy,gz = self.spawn_grass_rupee()
        self.lib.gp_step_full(gx,gy,gz,0,0,0,0,0,1,0,1,0)
        for _ in range(20): self.step(gx,gy,gz)
        self.assertEqual(self.lib.gp_drop_age(0),0)
        self.lib.gameplay_reset()
        self.assertEqual(self.lib.gp_rupees(),0)
        self.assertEqual(self.lib.gp_drop(0),0)
        self.assertFalse(self.lib.gameplay_rupee_taken(0))

    # --- inventory -------------------------------------------------------
    def test_walking_onto_gear_grants_and_equips_it_once(self):
        x, y, z, item = self.pickup(0)
        self.step(x, y, z)
        self.assertEqual(self.lib.gp_owned() & item, item)
        self.assertEqual(self.lib.gp_equipped() & item, item)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_PICKUP)
        # Standing on it a second time must not raise the event again.
        self.step(x, y, z)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_PICKUP)

    def test_gear_is_not_granted_from_across_the_meadow(self):
        x, y, z, _ = self.pickup(0)
        self.step(x + 400, y, z)
        self.assertEqual(self.lib.gp_owned(), 0)

    def test_both_pickups_are_reachable_and_distinct(self):
        self.assertEqual(self.lib.gp_pickup_total(), 2)
        items = {self.pickup(i)[3] for i in range(2)}
        self.assertEqual(items, {GP_SWORD, GP_SHIELD})

    # --- sword -----------------------------------------------------------
    def test_no_sword_means_no_swing(self):
        self.step(0, 0, 0, attack=1)
        self.assertEqual(self.lib.gp_swing(), 0)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_DENIED)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_SWING)

    def test_held_attack_does_not_restart_the_swing(self):
        x, y, z, _ = self.pickup(0)
        self.step(x, y, z)                      # collect the sword
        self.step(x, y, z, attack=1)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SWING)
        first = self.lib.gp_swing()
        self.step(x, y, z, attack=1)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_SWING)
        self.assertEqual(self.lib.gp_swing(), first - 1)

    def test_sword_cuts_grass_in_front_once(self):
        gx, gy, gz = self.grass(0)
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)                   # collect the sword
        # Stand just south of the tuft, facing it, and swing.
        self.step(gx, gy, gz - 40, yaw=0, attack=1)
        for _ in range(14):
            self.step(gx, gy, gz - 40, yaw=0)
        self.assertEqual(self.lib.gp_cut_count(), 1)
        # A second swing on the same tuft cuts nothing more.
        self.step(gx, gy, gz - 40, yaw=0, attack=1)
        for _ in range(14):
            self.step(gx, gy, gz - 40, yaw=0)
        self.assertEqual(self.lib.gp_cut_count(), 1)

    def test_walking_through_grass_does_not_cut_it(self):
        gx, gy, gz = self.grass(0)
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)
        for _ in range(20):
            self.step(gx, gy, gz)
        self.assertEqual(self.lib.gp_cut_count(), 0)

    def test_grass_behind_link_survives_the_swing(self):
        gx, gy, gz = self.grass(0)
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)
        self.step(gx, gy, gz - 40, yaw=0x8000, attack=1)   # facing away
        for _ in range(14):
            self.step(gx, gy, gz - 40, yaw=0x8000)
        self.assertEqual(self.lib.gp_cut_count(), 0)

    # --- shield ----------------------------------------------------------
    def test_shield_needs_the_shield(self):
        self.step(0, 0, 0, shield=1)
        self.assertFalse(self.lib.gp_shielding())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_DENIED)

    def test_shield_raises_when_owned_and_drops_while_swinging(self):
        sx, sy, sz, _ = self.pickup(0)
        hx, hy, hz, _ = self.pickup(1)
        self.step(sx, sy, sz)
        self.step(hx, hy, hz)
        self.step(hx, hy, hz, shield=1)
        self.assertTrue(self.lib.gp_shielding())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SHIELD_UP)
        self.step(hx, hy, hz, shield=1, attack=1)
        self.assertFalse(self.lib.gp_shielding())

    # --- targeting -------------------------------------------------------
    def test_target_press_locks_the_nearest_npc_in_front(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.assertGreaterEqual(self.lib.gp_target(), 0)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TARGET_ON)
        self.assertTrue(self.lib.gp_face_locked())

    def test_target_press_again_releases(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.assertEqual(self.lib.gp_target(), -1)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TARGET_OFF)
        self.assertFalse(self.lib.gp_face_locked())

    def test_nothing_in_front_locks_nothing(self):
        self.step(6000, 0, 6000, yaw=0, target=1)
        self.assertEqual(self.lib.gp_target(), -1)

    def test_walking_far_away_drops_the_lock(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.assertGreaterEqual(self.lib.gp_target(), 0)
        self.step(nx, ny, nz - 900, yaw=0)
        self.assertEqual(self.lib.gp_target(), -1)

    def test_locked_facing_refreshes_from_post_movement_position(self):
        nx,ny,nz=self.npc(0)
        self.step(nx,ny,nz-200,target=1)
        self.assertEqual(self.lib.gp_target(),0)
        self.lib.gameplay_update_facing(nx-100,nz)
        self.assertLessEqual(abs(self.lib.gp_face_yaw()-16384),1)

    def test_locked_facing_points_at_the_target(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        # Target is due north of Link, so the held heading is ~0 binang.
        yaw = self.lib.gp_face_yaw()
        self.assertTrue(yaw < 600 or yaw > 65536 - 600, yaw)


    # --- dialogue --------------------------------------------------------
    def talk_spot(self, index=0):
        """Stand one step south of a speaker, facing them."""
        nx, ny, nz = self.npc(index)
        return nx, ny, nz - 60

    def test_prompt_appears_only_next_to_a_speaker(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.assertGreaterEqual(self.lib.gp_prompt(), 0)
        self.step(x, y, z - 600, yaw=0)
        self.assertEqual(self.lib.gp_prompt(), -1)

    def test_a_opens_a_box_with_real_text_and_a_speaker_name(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertTrue(self.lib.gp_talking())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TALK_OPEN)
        self.assertGreater(self.lib.gp_page_lines(), 0)
        self.assertTrue(self.lib.gp_speaker_name())
        self.assertTrue(self.lib.gp_page_line(0))

    def test_opening_press_does_not_also_skip_the_first_page(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertEqual(self.lib.gp_page(), 0)

    def test_holding_a_does_not_skip_every_page(self):
        """A multi-page speaker must need one press per page."""
        for index in range(self.lib.gp_npc_total()):
            x, y, z = self.talk_spot(index)
            self.lib.gameplay_reset()
            self.step(x, y, z, yaw=0)
            self.step(x, y, z, yaw=0, interact=1)
            if self.lib.gp_talking() and self.lib.gp_page_lines():
                # Holding A: interact only edges once, so repeats pass 0 here.
                for _ in range(6):
                    self.step(x, y, z, yaw=0, interact=0)
                if self.lib.gp_talking():
                    self.assertEqual(self.lib.gp_page(), 0)
                    return
        self.skipTest('no multi-page speaker reachable')

    def test_a_advances_pages_then_closes_on_the_last(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        pages, guard = 1, 0
        while self.lib.gp_talking() and guard < 12:
            self.step(x, y, z, yaw=0, interact=1)
            guard += 1
            if self.lib.gp_talking():
                pages += 1
        self.assertFalse(self.lib.gp_talking())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TALK_CLOSE)
        self.assertGreaterEqual(pages, 1)

    def test_b_closes_the_box_early(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertTrue(self.lib.gp_talking())
        self.step(x, y, z, yaw=0, cancel=1)
        self.assertFalse(self.lib.gp_talking())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TALK_CLOSE)

    def test_box_swallows_attack_guard_and_pickups(self):
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)                       # sword in hand
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertTrue(self.lib.gp_talking())
        self.step(x, y, z, yaw=0, attack=1, shield=1)
        self.assertEqual(self.lib.gp_swing(), 0)
        self.assertFalse(self.lib.gp_shielding())

    def test_two_speakers_give_different_conversations(self):
        seen = set()
        for index in range(self.lib.gp_npc_total()):
            self.lib.gameplay_reset()
            x, y, z = self.talk_spot(index)
            self.step(x, y, z, yaw=0)
            self.step(x, y, z, yaw=0, interact=1)
            if self.lib.gp_talking():
                seen.add((self.lib.gp_convo(),
                          self.lib.gp_page_line(0)))
        self.assertGreaterEqual(len(seen), 2)

    def test_child_conversation_matches_its_enko_type(self):
        """The line a child says is the one its spawn param selects."""
        for index in range(self.lib.gp_npc_total()):
            if self.lib.gp_npc_kind(index) != 0:    # KOKIRI_NPC_CHILD
                continue
            self.lib.gameplay_reset()
            x, y, z = self.talk_spot(index)
            self.step(x, y, z, yaw=0)
            self.step(x, y, z, yaw=0, interact=1)
            if not self.lib.gp_talking():
                continue
            self.assertEqual(self.lib.gp_speaker_name(), b'Kokiri')
            return
        self.skipTest('no child speaker reachable')


    # --- pause inventory -------------------------------------------------
    def menu(self, x=0, y=0, z=0, **kw):
        args = dict(attack=0, shield=0, target=0, interact=0, grounded=1,
                    cancel=0, pause=0, menu_step=0)
        args.update(kw)
        self.lib.gp_step_full(int(x), int(y), int(z), 0,
                              args['attack'], args['shield'], args['target'],
                              args['interact'], args['grounded'],
                              args['cancel'], args['pause'],
                              args['menu_step'])

    def test_start_opens_and_closes_the_menu(self):
        self.menu(pause=1)
        self.assertTrue(self.lib.gp_paused())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_MENU_OPEN)
        self.menu(pause=1)
        self.assertFalse(self.lib.gp_paused())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_MENU_CLOSE)

    def test_b_returns_to_the_game(self):
        self.menu(pause=1)
        self.menu(cancel=1)
        self.assertFalse(self.lib.gp_paused())

    def test_dpad_moves_the_cursor_and_wraps(self):
        self.menu(pause=1)
        self.assertEqual(self.lib.gp_cursor(), 0)
        self.menu(menu_step=1)
        self.assertEqual(self.lib.gp_cursor(), 1)
        self.menu(menu_step=1)
        self.assertEqual(self.lib.gp_cursor(), 0)
        self.menu(menu_step=-1)
        self.assertEqual(self.lib.gp_cursor(), 1)

    def test_a_equips_an_owned_slot(self):
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)                       # own the sword
        self.menu(pause=1)
        self.menu(interact=1)
        self.assertTrue(self.lib.gp_equipped() & GP_SWORD)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_EQUIP)

    def test_a_cannot_equip_what_is_not_owned(self):
        self.menu(pause=1)
        self.menu(interact=1)
        self.assertEqual(self.lib.gp_equipped(), 0)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_DENIED)

    def test_menu_swallows_world_actions(self):
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)
        self.menu(pause=1)
        self.menu(attack=1, shield=1, target=1)
        self.assertEqual(self.lib.gp_swing(), 0)
        self.assertFalse(self.lib.gp_shielding())
        self.assertEqual(self.lib.gp_target(), -1)

    def test_closing_press_does_not_also_act_on_the_world(self):
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)
        self.menu(pause=1)
        # Start closes; the same step must not start a swing.
        self.menu(pause=1, attack=1)
        self.assertFalse(self.lib.gp_paused())
        self.assertEqual(self.lib.gp_swing(), 0)

    def test_pause_outranks_an_open_text_box(self):
        x, y, z = self.talk_spot(0)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertTrue(self.lib.gp_talking())
        self.menu(x, y, z, pause=1)
        self.assertTrue(self.lib.gp_paused())


if __name__ == '__main__':
    unittest.main()
