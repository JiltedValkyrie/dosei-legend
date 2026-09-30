"""Drive the real gameplay.c: chest, wonder rupees, Mido, equip, targeting, swing window, cutting.

Compiled and called through ctypes rather than reimplemented, so a rule that
changes in C changes here too.
"""
import ctypes
import re
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
GP_SLOT_SAVE = 2
GP_EVENT_RECENTER = 1 << 21


@unittest.skipUnless(GCC.is_file() and (GENERATED / 'kokiri_actors.c').is_file()
                     and (GENERATED / 'kokiri_dialogue.c').is_file(),
                     'host compiler and generated tables required')
class Gameplay(unittest.TestCase):
    def test_live_seed_ammo_sweep_and_hit(self):
        g = self.lib
        g.player_items_reset(); g.gp_item_floor(0); g.gp_item_inventory(2, 2)
        self.assertTrue(g.player_items_use(2, 0, 0, 0, 0, 0))
        self.assertEqual(g.gp_item_ammo(2), 1)
        self.assertFalse(g.player_items_use(2, 0, 0, 0, 0, 0))
        g.gp_item_victim(0, 0, 45, 4)
        g.player_items_step()
        self.assertTrue(g.gp_item_contacts() & 4)
        x, y, z = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        self.assertEqual(g.player_items_body(0, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z)), 0)
        self.assertEqual(g.gp_item_ammo(2), 1)

    def test_seed_sweep_hits_actor_before_floor_impact(self):
        g=self.lib
        g.player_items_reset(); g.gp_item_floor(1); g.gp_item_inventory(1,0)
        self.assertTrue(g.player_items_use(2,0,0,0,0,-0x4000))
        g.gp_item_victim(0,0,12,4)
        g.player_items_step()
        self.assertTrue(g.gp_item_contacts() & 4)
        self.assertTrue(g.player_items_events() & 2)
        g.gp_item_floor(0)

    def test_live_nut_flash_mask_and_one_hit(self):
        g = self.lib
        g.player_items_reset(); g.gp_item_floor(1); g.gp_item_inventory(0, 2)
        self.assertTrue(g.player_items_use(3, 0, 0, 0, 0, 0))
        g.player_items_step()
        self.assertEqual(g.player_items_flash(), 6)
        self.assertEqual(g.gp_item_ammo(3), 1)
        g.gp_item_victim(0, 0, 80, 4)  # seeds only: nut immune
        self.assertFalse(g.gp_item_contacts() & 4)
        g.gp_item_victim(0, 0, 80, 1)
        self.assertTrue(g.gp_item_contacts() & 4)
        self.assertFalse(g.gp_item_contacts() & 4)
        for _ in range(6): g.player_items_step()
        self.assertEqual(g.player_items_flash(), 0)
        g.gp_item_floor(0)

    def test_live_items_empty_timeout_and_reset(self):
        g = self.lib
        g.player_items_reset(); g.gp_item_floor(0); g.gp_item_inventory(-1, 0)
        self.assertFalse(g.player_items_use(2, 0, 0, 0, 0, 0))
        self.assertFalse(g.player_items_use(3, 0, 0, 0, 0, 0))
        g.gp_item_inventory(2, 2)
        self.assertTrue(g.player_items_use(3, 0, 10000, 0, 0, 0))
        for _ in range(24): g.player_items_step()
        self.assertEqual(g.player_items_flash(), 0)
        self.assertEqual(g.player_items_events(), 0)
        self.assertTrue(g.player_items_use(2, 0, 0, 0, 0, 0))
        g.player_items_reset()
        self.assertEqual(g.player_items_events(), 0)
        x, y, z = ctypes.c_int(), ctypes.c_int(), ctypes.c_int()
        self.assertEqual(g.player_items_body(0, ctypes.byref(x), ctypes.byref(y), ctypes.byref(z)), 0)

    def test_stick_burn_expiry_putaway_and_room_change(self):
        g = self.lib
        g.player_items_reset(); g.gp_sticks(1, 3, 1)
        self.assertTrue(g.player_items_use(1, 0, 0, 0, 0, 0))
        self.assertEqual(g.gp_stick_ammo(), 3)
        g.player_items_ignite()
        for _ in range(100): g.player_items_step()
        g.player_items_room_changed()
        self.assertEqual(g.player_items_burning(), 215)
        for _ in range(215): g.player_items_step()
        self.assertEqual(g.gp_stick_ammo(), 2)
        self.assertFalse(g.player_items_stick())
        g.player_items_use(1, 0, 0, 0, 0, 0); g.player_items_ignite()
        g.player_items_putaway()
        for _ in range(320): g.player_items_step()
        self.assertEqual(g.gp_stick_ammo(), 2)

    def test_dungeon_map_floor_selection_wraps_but_world_map_stays_fixed(self):
        self.assertEqual(self.lib.gp_map_step(2,0,0,-1,0),4)
        self.assertEqual(self.lib.gp_map_step(2,4,0,1,0),0)
        self.assertEqual(self.lib.gp_map_step(3,2,1,0,0),3)
        self.assertEqual(self.lib.gp_map_step(0,2,1,0,0),2)
        self.assertEqual(self.lib.gp_map_step(2,2,0,1,1),2)
        self.assertTrue(self.lib.gp_save_prompt())

    def test_deku_source_chests_grant_persistent_map_compass_and_slingshot(self):
        import math
        g = self.lib
        for reward, expected in ((0x41, 2), (0x40, 1), (5, 30)):
            g.gp_reset_no_greeting(); g.gp_scene(2)
            i = next(i for i in range(g.gp_chest_total())
                     if g.gp_chest_scene(i) == 2 and ((g.gp_chest_param(i) >> 5) & 127) == reward)
            x,y,z,yaw,room = self.chest(i)
            g.gp_room(room)
            angle = yaw * math.tau / 65536
            self.step(x - 25*math.sin(angle), y, z - 25*math.cos(angle), yaw=yaw, interact=1)
            self.assertTrue(g.gameplay_chest_opened(i))
            if reward == 5: self.assertEqual(g.gp_item_ammo(2), expected)
            else: self.assertTrue(g.gp_dungeon_items() & expected)
            block = ctypes.create_string_buffer(314)
            g.gp_save_pack(block); g.save_new_game()
            self.assertEqual(g.gp_save_unpack(block,314), 0)
            if reward != 5: self.assertTrue(g.gp_dungeon_items() & expected)

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        generated = pathlib.Path(cls.tmp.name) / 'generated'
        generated.mkdir()
        import shutil, sys
        for file in GENERATED.iterdir():
            if file.suffix in ('.h', '.c'): shutil.copy2(file, generated / file.name)
        subprocess.run([sys.executable, str(ROOT / 'tools/build_actors.py'),
                        '--out', str(generated)], check=True, capture_output=True)
        subprocess.run([sys.executable, str(ROOT / 'tools/build_dialogue.py'),
                        '--out', str(generated), '--cd', str(generated)],
                       check=True, capture_output=True)
        cls.generated = generated
        output = pathlib.Path(cls.tmp.name) / 'gameplay.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(generated), '-I' + str(ROOT / 'src'),
                        '-I' + str(ROOT.parent / 'shared/lib/camera'),
                        '-I' + str(ROOT.parent / 'shared/lib/collision'),
                        str(ROOT / 'tests/fixtures/gameplay_host.c'),
                        str(ROOT / 'src/gameplay.c'),
                        str(ROOT / 'src/player_items.c'),
                        str(ROOT / 'src/world_props.c'),
                        str(ROOT / 'src/world_signs.c'),
                        str(ROOT / 'src/item_drop.c'),
                        str(ROOT / 'src/pause_window_state.c'),
                        str(ROOT / 'src/dialogue_text.c'),
                        str(ROOT / 'src/ui_preferences.c'),
                        str(ROOT / 'src/text_pool.c'),
                        str(ROOT / 'src/collide.c'),
                        str(ROOT / 'src/actor_sys.c'),
                        str(ROOT / 'src/attention.c'),
                        str(ROOT / 'src/karebaba.c'),
                        str(ROOT / 'src/game_over.c'),
                        str(ROOT / 'src/save_state.c'),
                        str(ROOT / 'src/save_file.c'),
                        str(generated / 'kokiri_actors.c'),
                        str(generated / 'kokiri_dialogue.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        cls.lib.gp_page_line.restype = ctypes.c_char_p
        # Line text comes from the disc file, as on target (BUG-033).
        cls.text = ctypes.create_string_buffer((generated / 'DIALOG.TXT').read_bytes())
        assert cls.lib.gp_bind_text(cls.text, len(cls.text.raw) - 1)
        cls.lib.gp_speaker_name.restype = ctypes.c_char_p
        cls.lib.gp_slot_name.restype = ctypes.c_char_p
        cls.lib.gp_slot_use.restype = ctypes.c_char_p
        for name in ('save_mido_demands_met', 'gameplay_chest_opened', 'gameplay_sword_active', 'gameplay_jump_attack_start',
                     'gameplay_grass_cut', 'gameplay_rupee_taken',
                     'save_get_item_get_inf', 'save_get_collectible',
                     'save_get_inf_table', 'save_get_event_chk_inf'):
            getattr(cls.lib, name).restype = ctypes.c_bool
        for name in ('gp_grass_at', 'gp_npc_at', 'gp_chest_at', 'gp_wonder_at'):
            getattr(cls.lib, name).restype = None

    def setUp(self):
        self.lib.ui_preferences_reset()
        self.lib.ui_text_set_analog(False)
        # gameplay_reset() deliberately does NOT clear the save: quest flags
        # outlive a scene by design. Each test therefore starts a fresh file
        # too, or flags set by one test would leak into the next.
        self.lib.save_new_game()
        self.lib.gp_scene(0)             # Kokiri Forest
        self.lib.gp_stick(-1, 0)
        self.lib.gp_hold_x(0)
        self.lib.gp_blade_set(0, 0, 0, 0, 0, 0, 0)
        self.lib.gp_blade_wall(0)
        self.lib.gp_ball_wall(0)
        self.lib.gp_actors_clear()
        self.lib.gp_sight_block_x(-2**31)
        self.lib.gp_offscreen_x(-2**31)
        self.lib.gp_c_up(0)
        self.lib.gp_navi_timer_set(0)
        self.lib.gp_go_reset()
        self.lib.gp_saria_cs_reset()
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(0)
        # A fresh forest file is a file Saria has not greeted yet, so En_Sa
        # spawns as SARIA_TYPE_GREETING and its cutscene owns the first step of
        # the scene. That is the real behaviour and has its own tests below;
        # every other test wants the ordinary walking-around forest. Decline
        # the greeting rather than setting its flag: the flag also changes
        # which line Saria says, which several tests below check.
        self.lib.gp_saria_greeting_cancel()

    def test_interior_people_have_dialogue_and_no_forest_targets(self):
        for scene, expected in ((4,1),(6,3),(7,1),(5,0),(8,0),(9,0)):
            self.lib.gp_scene(scene)
            self.lib.gp_reset_no_greeting()
            present = [i for i in range(self.lib.gp_npc_count()) if self.lib.gp_npc_present(i)]
            self.assertEqual(len(present),expected)
            for i in present:
                self.assertEqual(self.lib.gp_npc_scene(i),scene)
                self.assertGreater(self.talk_to(i),0)
                self.lib.gp_reset_no_greeting()

    # --- helpers ---------------------------------------------------------
    def pickup(self, index):
        """Test setup: gear owned and equipped (index 0 sword, 1 shield).

        The ground pickups are gone (FEAT-001); the returned spot is a neutral
        place to keep stepping, far from every rupee."""
        item = (GP_SWORD, GP_SHIELD)[index]
        self.lib.gp_grant(item)
        return 0, 0, 0, item

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
        # Default attack is RIGHT_SLASH_1H, live from clip frame 1: the cut
        # lands on the third step after the press.
        for _ in range(2): self.step(gx,gy,gz-40)
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

    def test_pause_freezes_the_drop(self):
        gx,gy,gz = self.spawn_grass_rupee()
        self.lib.gp_step_full(gx,gy,gz,0,0,0,0,0,1,0,1,0)
        for _ in range(20): self.step(gx,gy,gz)
        self.assertEqual(self.lib.gp_drop_age(0),0)

    def test_reset_clears_the_uncollected_drop_but_keeps_the_wallet(self):
        """This test used to assert that a reset emptied the wallet.

        That expectation was the bug the human hit: gameplay_reset() runs when
        entering a scene, which is after a save has been loaded, so wiping the
        wallet there threw away collected rupees. A reset now clears only the
        volatile per-scene state; only save_new_game() empties the wallet.
        """
        gx,gy,gz = self.spawn_grass_rupee()
        for _ in range(20): self.step(gx,gy,gz)
        carried = self.lib.gp_rupees()
        self.assertGreater(carried, 0)
        self.lib.gp_reset_no_greeting()
        self.assertEqual(self.lib.gp_rupees(), carried)
        # The uncut-grass drop itself is volatile, so it does go.
        self.assertEqual(self.lib.gp_drop(0), 0)
        self.lib.save_new_game()
        self.lib.gp_reset_no_greeting()
        self.assertEqual(self.lib.gp_rupees(), 0)
        self.assertFalse(self.lib.gameplay_rupee_taken(0))

    # --- inventory -------------------------------------------------------
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
        self.step(x, y, z, attack=1)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_SWING)
        self.assertEqual(self.lib.gp_attack_phase(), 1)

    def test_contact_colliders_fit_their_cart_carve(self):
        header = (ROOT / 'src/ram_cart.h').read_text()
        size = int(re.search(r'RAM_CART_CONTACT_BYTES\s+0x([0-9A-Fa-f]+)u', header).group(1), 16)
        # Host pointers are 8 bytes, wider than SH-2's, so this is an upper bound.
        self.assertLessEqual(self.lib.gp_contacts_bytes(), size)

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

    def test_shield_raises_when_owned_and_blocks_attacks(self):
        sx, sy, sz, _ = self.pickup(0)
        hx, hy, hz, _ = self.pickup(1)
        self.step(sx, sy, sz)
        self.step(hx, hy, hz)
        self.step(hx, hy, hz, shield=1)
        self.assertTrue(self.lib.gp_shielding())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SHIELD_UP)
        # func_808428D8: X while guarding is the crouch stab, not a slash;
        # the guard stays up and the stab ends on defense_wait.
        self.step(hx, hy, hz, shield=1, attack=1)
        self.assertTrue(self.lib.gp_shielding())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SWING)
        self.assertEqual(self.lib.gp_attack_phase(), 7)

    def test_crouch_stab_hits_only_while_frame_below_two(self):
        sx, sy, sz, _ = self.pickup(0)
        hx, hy, hz, _ = self.pickup(1)
        self.step(sx, sy, sz)
        self.step(hx, hy, hz)
        self.step(hx, hy, hz, shield=1)
        self.step(hx, hy, hz, shield=1, attack=1)
        live = []
        for _ in range(12):
            self.step(hx, hy, hz, shield=1)
            live.append(bool(self.lib.gp_sword_live()))
        # Speed 1.0: frame 1 on the first step after the press, then off.
        self.assertEqual(live[:3], [True, False, False])
        self.assertTrue(self.lib.gp_shielding())

    # --- targeting (HOLD, not switch) ------------------------------------
    # OoT's own alternative to Switch targeting: the lock lasts exactly as long
    # as L is held (z_player.c:3896 keeps it alive on zButtonHeld and sets
    # LOCK_ON_WITH_SWITCH only in Switch mode). A press shorter than
    # GP_TARGET_HOLD_STEPS is a tap and recentres instead of locking, so
    # brushing L while running past a Kokiri does not grab them. The tap/hold
    # threshold is this slice's own choice, not ported from OoT.
    GP_TARGET_HOLD_STEPS = 5

    def hold_target(self, x, y, z, steps=None, yaw=0):
        """Hold L for `steps` steps at one spot."""
        if steps is None:
            steps = self.GP_TARGET_HOLD_STEPS
        for _ in range(steps):
            self.step(x, y, z, yaw=yaw, target=1)

    def test_holding_l_locks_the_nearest_npc_in_front(self):
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        self.assertGreaterEqual(self.lib.gp_target(), 0)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TARGET_ON)
        self.assertTrue(self.lib.gp_face_locked())

    def test_a_short_tap_does_not_lock_anything(self):
        """The reported annoyance: a brief L press near a Kokiri grabbed them."""
        nx, ny, nz = self.npc(0)
        for _ in range(self.GP_TARGET_HOLD_STEPS - 1):
            self.step(nx, ny, nz - 200, yaw=0, target=1)
            self.assertEqual(-1, self.lib.gp_target())
            self.assertFalse(self.lib.gp_face_locked())
        self.assertFalse(self.lib.gp_events() & GP_EVENT_TARGET_ON)

    def test_a_short_tap_recentres_the_camera_instead(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.step(nx, ny, nz - 200, yaw=0, target=0)        # released early
        self.assertTrue(self.lib.gp_events() & GP_EVENT_RECENTER)
        self.assertEqual(-1, self.lib.gp_target())

    def test_releasing_a_hold_drops_the_lock(self):
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        self.assertGreaterEqual(self.lib.gp_target(), 0)
        self.step(nx, ny, nz - 200, yaw=0, target=0)
        self.assertEqual(-1, self.lib.gp_target())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TARGET_OFF)
        self.assertFalse(self.lib.gp_face_locked())

    def test_releasing_a_hold_that_locked_does_not_also_recentre(self):
        """Recentring after a lock would swing the view off the actor the
        player was just looking at."""
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        self.step(nx, ny, nz - 200, yaw=0, target=0)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_RECENTER)

    def test_the_lock_persists_for_as_long_as_l_is_held(self):
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        for _ in range(30):
            self.step(nx, ny, nz - 200, yaw=0, target=1)
            self.assertGreaterEqual(self.lib.gp_target(), 0)
            self.assertTrue(self.lib.gp_face_locked())

    def test_holding_l_with_nothing_in_front_locks_nothing_and_no_recentre(self):
        self.hold_target(6000, 0, 6000)
        self.assertEqual(-1, self.lib.gp_target())
        self.assertFalse(self.lib.gp_face_locked())
        self.step(6000, 0, 6000, yaw=0, target=0)
        # It was a hold, not a tap, so it is not the recentre gesture either.
        self.assertFalse(self.lib.gp_events() & GP_EVENT_RECENTER)

    def test_a_held_l_acquires_an_actor_turned_toward_later(self):
        """Holding L and turning to face someone picks them up, rather than
        needing a fresh press."""
        nx, ny, nz = self.npc(0)
        self.hold_target(6000, 0, 6000)
        self.assertEqual(-1, self.lib.gp_target())
        self.step(nx, ny, nz - 200, yaw=0, target=1)
        self.assertGreaterEqual(self.lib.gp_target(), 0)

    def test_walking_far_away_drops_the_lock_even_while_held(self):
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        self.assertGreaterEqual(self.lib.gp_target(), 0)
        self.step(nx, ny, nz - 900, yaw=0, target=1)
        self.assertEqual(-1, self.lib.gp_target())

    def test_locked_facing_refreshes_from_post_movement_position(self):
        nx, ny, nz = self.npc(2)   # EnKo type 3 also moves toward Link (M3b)
        self.hold_target(nx, ny, nz - 200)
        self.assertEqual(2, self.lib.gp_target())
        nx, nz = self.lib.gameplay_npc_x(2), self.lib.gameplay_npc_z(2)
        self.lib.gameplay_update_facing(nx - 100, nz)
        self.assertLessEqual(abs(self.lib.gp_face_yaw() - 16384), 1)

    def test_exit_kokiri_tracks_player_on_source_80_unit_ring(self):
        x, y, z = self.npc(2)
        self.step(x + 200, y, z)
        self.assertAlmostEqual(self.lib.gameplay_npc_x(2), x + 80, delta=1)
        self.assertAlmostEqual(self.lib.gameplay_npc_z(2), z, delta=1)
        self.step(x, y, z - 200)
        self.assertAlmostEqual(self.lib.gameplay_npc_x(2), x, delta=1)
        self.assertAlmostEqual(self.lib.gameplay_npc_z(2), z - 80, delta=1)

    def test_locked_facing_points_at_the_target(self):
        nx, ny, nz = self.npc(0)
        self.hold_target(nx, ny, nz - 200)
        # Target is due north of Link, so the held heading is ~0 binang.
        yaw = self.lib.gp_face_yaw()
        self.assertTrue(yaw < 600 or yaw > 65536 - 600, yaw)

    # --- M2d shared attention -------------------------------------------
    # Away from every Kokiri NPC; yaw 0 faces +z.
    SPOT = (6000, 0, 6000)
    RANGE_1 = 1                      # Karebaba ATTENTION_RANGE_1 (170 / 255)

    def enemy(self, dx=0, dz=100, focus=(0, 40, 0), rng=None, arrow=25):
        x, y, z = self.SPOT
        h = self.lib.gp_spawn_enemy(x + dx, y, z + dz, *focus,
                                    self.RANGE_1 if rng is None else rng, arrow)
        self.assertNotEqual(0, h)
        return h

    def hold_at_spot(self, steps=None, yaw=0):
        self.hold_target(*self.SPOT, steps=steps, yaw=yaw)

    def test_enemy_lock_uses_the_registry_handle(self):
        h = self.enemy()
        self.hold_at_spot()
        self.assertEqual(h, self.lib.gp_target_handle())
        self.assertEqual(-1, self.lib.gp_target())       # not an NPC

    def test_lock_drops_when_targetable_clears_though_actor_lives(self):
        """Karebaba clears attention while dying but stays alive to regrow."""
        h = self.enemy()
        self.hold_at_spot()
        self.lib.gp_actor_targetable(h, 0)
        self.step(*self.SPOT, target=1)
        self.assertEqual(0, self.lib.gp_target_handle())
        self.assertTrue(self.lib.gp_events() & GP_EVENT_TARGET_OFF)
        self.lib.gp_actor_targetable(h, 1)               # regrown
        self.step(*self.SPOT, target=1)
        self.assertEqual(h, self.lib.gp_target_handle()) # same identity again

    def test_lock_drops_when_attention_kind_clears(self):
        h = self.enemy()
        self.hold_at_spot()
        self.lib.gp_actor_attention(h, 0)
        self.step(*self.SPOT, target=1)
        self.assertEqual(0, self.lib.gp_target_handle())

    def test_killed_target_drops_and_a_reused_slot_is_a_new_identity(self):
        h = self.enemy()
        self.hold_at_spot()
        self.lib.gp_actor_kill(h)
        self.step(*self.SPOT, target=1)
        self.assertNotEqual(h, self.lib.gp_target_handle())
        self.lib.gp_actors_reap()
        h2 = self.enemy()
        self.assertNotEqual(h, h2)
        self.step(*self.SPOT, target=1)
        self.assertEqual(h2, self.lib.gp_target_handle())

    def test_blocked_nearest_does_not_hide_a_valid_farther_target(self):
        near = self.enemy(dx=-10, dz=60)
        far = self.enemy(dx=10, dz=140)
        self.lib.gp_sight_block_x(self.SPOT[0] - 10)     # line to near blocked
        self.hold_at_spot()
        self.assertEqual(far, self.lib.gp_target_handle())
        self.lib.gp_sight_block_x(-2**31)

    def test_offscreen_nearest_does_not_hide_an_onscreen_farther_target(self):
        self.enemy(dx=-10, dz=60)
        far = self.enemy(dx=10, dz=140)
        self.lib.gp_offscreen_x(self.SPOT[0] - 10)       # near focus off screen
        self.hold_at_spot()
        self.assertEqual(far, self.lib.gp_target_handle())

    def test_a_held_lock_survives_going_off_screen(self):
        """Attention_ActorOnScreen is acquisition only."""
        h = self.enemy(dz=100)
        self.hold_at_spot()
        self.lib.gp_offscreen_x(self.SPOT[0])
        for _ in range(5):
            self.step(*self.SPOT, target=1)
        self.assertEqual(h, self.lib.gp_target_handle())

    def test_navi_skips_an_offscreen_arrow_actor(self):
        self.enemy(dz=100)
        self.lib.gp_offscreen_x(self.SPOT[0])
        self.step(*self.SPOT)
        self.assertEqual(0, self.lib.gp_arrow_handle())

    def test_acquisition_cone_is_sixty_degrees(self):
        inside = self.enemy(dx=100, dz=100)             # 45 degrees
        self.hold_at_spot()
        self.assertEqual(inside, self.lib.gp_target_handle())

    def test_outside_the_cone_is_not_acquired(self):
        self.enemy(dx=100, dz=40)                        # ~68 degrees
        self.hold_at_spot()
        self.assertEqual(0, self.lib.gp_target_handle())

    def test_out_of_range_is_not_acquired(self):
        self.enemy(dz=175)                               # RANGE_1 is 170
        self.hold_at_spot()
        self.assertEqual(0, self.lib.gp_target_handle())

    def test_retention_uses_the_leash_not_the_range_or_cone(self):
        h = self.enemy(dz=150)
        self.hold_at_spot()
        x, y, z = self.SPOT
        self.lib.gp_actor_move(h, x, y, z + 205)         # past 170, inside 208
        self.step(x, y, z, yaw=32768, target=1)          # facing away
        self.assertEqual(h, self.lib.gp_target_handle())
        self.lib.gp_actor_move(h, x, y, z + 212)         # past sqrt(170*255)
        self.step(x, y, z, target=1)
        self.assertEqual(0, self.lib.gp_target_handle())

    def test_locked_facing_aims_at_the_focus_not_the_origin(self):
        self.enemy(dz=100, focus=(100, 40, 0))           # focus 45 degrees right
        self.hold_at_spot()
        yaw = self.lib.gp_face_yaw()
        self.assertLessEqual(abs(yaw - 8192), 64)

    def test_npc_actor_tracks_live_mido(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200)
        h = self.lib.gp_npc_handle(0)
        self.assertNotEqual(0, h)
        for _ in range(20):
            self.step(nx, ny, nz - 200)
        ax, ay, az = (ctypes.c_int() for _ in range(3))
        self.lib.gp_actor_pos(h, *(ctypes.byref(v) for v in (ax, ay, az)))
        mx, mz = ctypes.c_int(), ctypes.c_int()
        self.lib.gp_mido_pos(ctypes.byref(mx), ctypes.byref(mz))
        self.assertEqual((ax.value, az.value), (mx.value, mz.value))

    def test_npc_actors_leave_with_the_forest(self):
        nx, ny, nz = self.npc(0)
        self.step(nx, ny, nz - 200)
        self.assertNotEqual(0, self.lib.gp_npc_handle(0))
        self.lib.gp_scene(5)
        self.step(nx, ny, nz - 200)
        self.assertEqual(0, self.lib.gp_npc_handle(0))

    def navi_hover(self):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_navi_hover(*(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def test_navi_hovers_the_lock_and_takes_the_enemy_colour(self):
        self.enemy(dz=100, focus=(0, 40, 0), arrow=25)
        self.hold_at_spot()
        for _ in range(9):                               # 4 source updates + margin
            self.step(*self.SPOT, target=1)
        x, y, z = self.SPOT
        self.assertEqual((x, y + 40 + 25, z + 100), self.navi_hover())
        self.assertEqual(2, self.lib.gp_navi_colour())   # ATTN_COLOUR_ENEMY
        self.assertFalse(self.lib.gp_navi_moving())

    def test_navi_returns_to_link_on_release(self):
        self.enemy(dz=100)
        self.hold_at_spot()
        for _ in range(9):
            self.step(*self.SPOT, target=1)
        # Released and turned away: no lock, no arrow actor in the cone.
        for _ in range(9):
            self.step(*self.SPOT, yaw=32768)
        x, y, z = self.SPOT
        self.assertEqual((x, y + 56 + 5, z), self.navi_hover())
        self.assertEqual(0, self.lib.gp_navi_colour())
        self.assertFalse(self.lib.gp_navi_has_actor())

    def test_navi_hovers_the_arrow_actor_without_a_lock(self):
        h = self.enemy(dz=100)
        self.step(*self.SPOT)
        self.step(*self.SPOT)            # Navi runs 2 of 3 steps (20 Hz)
        self.assertEqual(h, self.lib.gp_arrow_handle())
        self.assertTrue(self.lib.gp_navi_has_actor())

    def test_stick_back_while_locked_hides_the_next_arrow(self):
        self.enemy(dz=100)
        second = self.enemy(dx=20, dz=120)
        self.hold_at_spot()
        self.assertEqual(second, self.lib.gp_arrow_handle())
        self.lib.gp_stick(2, 1)
        self.step(*self.SPOT, target=1)
        self.assertEqual(0, self.lib.gp_arrow_handle())
        self.lib.gp_stick(-1, 0)

    # --- M2d.2 En_Karebaba --------------------------------------------
    GROW, IDLE, AWAKEN, UPRIGHT, SPIN, DYING, DROP, RETRACT, DEAD, REGROW = range(10)

    def baba_home(self, i=0):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_baba_home(i, *(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def baba_pos(self, i=0):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_baba_pos(i, *(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def at_baba(self, dx=0, dz=0, steps=1, i=0, **kw):
        hx, hy, hz = self.baba_home(i) if self.lib.gp_baba_count() else (2109, -1, -317)
        seen = 0
        for _ in range(steps):
            self.step(hx + dx, hy, hz + dz, **kw)
            seen |= self.lib.gp_baba_events()
        return seen

    def wake(self, i=0):
        self.lib.gp_room(1)
        self.at_baba(dz=150, steps=2)
        self.at_baba(dz=150, steps=40)           # awaken 46 -> 60 at 5 a tick
        self.assertEqual(self.UPRIGHT, self.lib.gp_baba_action(i))

    def test_five_source_spawns_in_room_1_only(self):
        self.lib.gp_room(0)
        self.step(*self.SPOT)
        self.assertEqual(0, self.lib.gp_baba_count())
        self.lib.gp_room(1)
        self.step(*self.SPOT)
        self.assertEqual(5, self.lib.gp_baba_count())
        self.assertEqual((2109, -1, -317), self.baba_home(0))
        self.assertEqual(self.IDLE, self.lib.gp_baba_action(0))
        self.assertTrue(self.lib.gp_baba_body_hard(0))   # idle bud bounces the sword

    def test_wakes_inside_200_xz_and_30_y(self):
        self.lib.gp_room(1)
        self.at_baba(dz=210, steps=4)
        self.assertEqual(self.IDLE, self.lib.gp_baba_action(0))
        ev = self.at_baba(dz=150, steps=2)
        self.assertEqual(self.AWAKEN, self.lib.gp_baba_action(0))
        self.assertTrue(ev & 1)                          # NA_SE_EN_DUMMY482

    def test_upright_spins_after_40_and_retracts_past_240(self):
        self.wake()
        self.assertFalse(self.lib.gp_baba_body_hard(0))
        self.at_baba(dz=150, steps=61)                   # 40 updates
        self.assertEqual(self.SPIN, self.lib.gp_baba_action(0))
        self.at_baba(dz=150, steps=61)
        self.assertEqual(self.UPRIGHT, self.lib.gp_baba_action(0))
        self.at_baba(dz=250, steps=2)
        self.assertEqual(self.RETRACT, self.lib.gp_baba_action(0))

    def test_sword_hit_kills_drops_one_stick_and_regrows(self):
        self.wake()
        h = self.lib.gp_baba_handle(0)
        self.lib.gp_baba_hit(0)
        ev = self.at_baba(dz=150, steps=2)
        self.assertEqual(self.DYING, self.lib.gp_baba_action(0))
        self.assertTrue(ev & 4 and ev & 8)               # DEAD + LAST_DAMAGE
        hx, hy, hz = self.baba_home()
        self.lib.gp_baba_floor(hy)
        ev = self.at_baba(dz=150, steps=30)
        self.assertEqual(self.DROP, self.lib.gp_baba_action(0))
        self.assertTrue(ev & 16)                         # DODO_M_GND
        # Dying cleared attention: a lock cannot take it, but it is alive.
        self.assertNotEqual(0, h)
        px, py, pz = self.baba_pos()
        self.assertEqual(0, self.lib.gp_stick_ammo())
        ev = 0
        for _ in range(3):
            self.step(px, py, pz)
            ev |= self.lib.gp_baba_events()
        self.assertTrue(ev & 32)                         # first stick: get-item show
        self.step(px, py, pz)
        self.assertEqual(self.lib.gp_step_baba_events(), 0)
        self.step(px, py, pz)
        self.assertEqual(self.lib.gp_step_baba_events(), 0)
        self.assertEqual((1, 1), (self.lib.gp_stick_ammo(), self.lib.gp_stick_upgrade()))
        self.lib.gp_c_up(0)
        self.step(px, py, pz, cancel=1)
        for _ in range(4):
            self.step(px, py, pz)
        self.assertEqual(self.DEAD, self.lib.gp_baba_action(0))
        self.assertEqual(1, self.lib.gp_stick_ammo())    # no second reward
        for _ in range(301 + 31):                        # Dead 200, Regrow 20
            self.step(*self.SPOT)
        self.assertEqual(self.IDLE, self.lib.gp_baba_action(0))

    def test_upright_baba_bites_link_through_the_real_collision_pass(self):
        # Human report: no contact either way. Colliders sit at the spawn
        # point (source quirk) as offsets from the moving actor.
        self.lib.gp_health_set(48, 48)
        self.wake()
        hx, hy, hz = self.baba_home()
        for _ in range(6):
            self.step(hx + 10, hy, hz)
        self.assertLess(self.lib.gp_health(), 48)

    def test_real_sword_cut_kills_an_upright_baba(self):
        self.pickup(0)
        self.lib.gp_health_set(48, 48)
        self.wake()
        hx, hy, hz = self.baba_home()
        # Blade across the base, 30 in front of Link standing 40 south.
        self.lib.gp_blade_set(1, hx - 20, hy + 30, hz - 10, hx + 20, hy + 30, hz - 10)
        self.step(hx, hy, hz - 40, attack=1)
        for _ in range(6):
            self.step(hx, hy, hz - 40)
        self.assertEqual(self.DYING, self.lib.gp_baba_action(0))

    def test_item_assignment_owned_only_and_moves_existing_binding(self):
        self.lib.gp_assign_item(0, 1)
        self.assertEqual(self.lib.gp_c_item(0), 0)
        self.lib.gp_sticks(1, 4, 1)
        self.lib.gp_assign_item(0, 1)
        self.assertEqual(self.lib.gp_c_item(0), 1)
        self.lib.gp_assign_item(0, 3)
        self.assertEqual(self.lib.gp_c_item(0), 0)
        self.assertEqual(self.lib.gp_c_item(2), 1)
        self.lib.gp_assign_item(5, 3)
        self.assertEqual(self.lib.gp_c_item(2), 1)

    def test_full_bag_still_consumes_the_stick(self):
        self.lib.gp_sticks(1, 10, 1)
        self.wake()
        self.lib.gp_baba_hit(0)
        hx, hy, hz = self.baba_home()
        self.lib.gp_baba_floor(hy)
        self.at_baba(dz=150, steps=32)
        self.assertEqual(self.DROP, self.lib.gp_baba_action(0))
        px, py, pz = self.baba_pos()
        ev = 0
        for _ in range(6):
            self.step(px, py, pz)
            ev |= self.lib.gp_baba_events()
        self.assertTrue(ev & 64)                         # quiet GET_ITEM path
        self.assertEqual(10, self.lib.gp_stick_ammo())   # clamped at capacity
        self.assertEqual(self.DEAD, self.lib.gp_baba_action(0))

    def test_unpicked_stick_expires_after_200(self):
        self.wake()
        self.lib.gp_baba_hit(0)
        hx, hy, hz = self.baba_home()
        self.lib.gp_baba_floor(hy)
        self.at_baba(dz=150, steps=32)
        self.at_baba(dz=150, steps=301)
        self.assertEqual(self.DEAD, self.lib.gp_baba_action(0))
        self.assertEqual(0, self.lib.gp_stick_ammo())

    def test_baba_refused_by_full_pool_is_retried_not_dropped(self):
        self.lib.karebaba_reset()
        self.lib.gp_fill_pool(2)
        room = 1                                   # kokiri_babas[0].room
        self.lib.gp_baba_sync(room)
        self.assertEqual(self.lib.gp_baba_count(), 2)
        self.lib.gp_baba_sync(room)                # still full: no duplicates
        self.assertEqual(self.lib.gp_baba_count(), 2)
        self.lib.gp_free_fillers()
        self.lib.gp_baba_sync(room)
        self.assertEqual(self.lib.gp_baba_count(), 5)
        self.assertEqual(sorted(self.lib.gp_baba_spawn(i) for i in range(5)), list(range(5)))

    def test_dying_baba_drops_the_lock_but_stays_alive(self):
        self.wake()
        hx, hy, hz = self.baba_home()
        h = self.lib.gp_baba_handle(0)
        for _ in range(self.GP_TARGET_HOLD_STEPS + 2):
            self.step(hx, hy, hz - 120, target=1)
        self.assertEqual(h, self.lib.gp_target_handle())
        self.lib.gp_baba_hit(0)
        self.lib.gp_baba_floor(hy)
        for _ in range(32):
            self.step(hx, hy, hz - 120, target=1)
        self.assertEqual(self.DROP, self.lib.gp_baba_action(0))
        self.assertNotEqual(h, self.lib.gp_target_handle())

    # --- M2e hurt, death, Game Over ------------------------------------
    DEATH, VOID, ALARM, LAND = 64, 128, 256, 32
    GO_OFF, GO_DYING, GO_DELAY, GO_MESSAGE, GO_SAVE, GO_SAVING, GO_SAVED, GO_CONTINUE, GO_FINISH = range(9)

    def test_fall_damage_thresholds_and_the_landing_roll(self):
        self.lib.gp_health_set(48, 48)
        self.lib.gp_land(399, 0)
        self.assertEqual(48, self.lib.gp_health())
        self.lib.gp_land(600, 1)                         # rolled: no damage
        self.assertEqual(48, self.lib.gp_health())
        self.lib.gp_land(400, 0)
        self.assertEqual(40, self.lib.gp_health())       # half a heart
        self.assertEqual(60, self.lib.gp_intangible())   # 40 source frames
        self.lib.gp_land(800, 0)
        self.assertEqual(24, self.lib.gp_health())       # a heart

    def test_void_respawn_costs_a_heart(self):
        self.lib.gp_health_set(48, 48)
        self.lib.gp_void_respawned()
        self.assertEqual(32, self.lib.gp_health())

    def test_lethal_hit_kills_once_and_only_on_the_ground(self):
        self.lib.gp_health_set(8, 48)
        self.lib.gp_hurt_set(8, 0)
        self.step(*self.SPOT, grounded=0)
        self.assertEqual(0, self.lib.gp_health())
        self.assertFalse(self.lib.gp_dead())             # airborne: not yet
        seen = 0
        for _ in range(3):
            self.step(*self.SPOT)
            seen += bool(self.lib.gp_events2() & self.DEATH)
        self.assertTrue(self.lib.gp_dead())
        self.assertEqual(1, seen)
        self.assertEqual(self.GO_DYING, self.lib.gp_go_state())

    def die(self):
        self.lib.gp_navi_timer_set(900)
        self.lib.gp_health_set(0, 48)
        self.step(*self.SPOT)
        self.assertTrue(self.lib.gp_dead())
        self.assertEqual(0, self.lib.gp_navi_timer())    # DEATH_START reset
        self.lib.gp_death_anim_done()
        for _ in range(30 + 60):                         # delay 20 + window 40
            self.lib.gp_go_step(0, 0)
        self.assertEqual(self.GO_SAVE, self.lib.gp_go_state())

    def test_game_over_save_failure_is_reported_then_continue_restores_three_hearts(self):
        self.die()
        self.lib.gp_go_step(0, 1)                        # Save? Yes
        self.assertEqual(self.GO_SAVING, self.lib.gp_go_state())
        self.lib.gp_go_save_done(0)
        self.assertEqual(self.GO_SAVE, self.lib.gp_go_state())
        self.assertTrue(self.lib.gp_go_failed())
        self.lib.gp_go_step(0, 1)
        self.lib.gp_go_save_done(1)
        self.assertEqual(self.GO_SAVED, self.lib.gp_go_state())
        self.lib.gp_go_step(0, 1)                        # too early to skip
        self.assertEqual(self.GO_SAVED, self.lib.gp_go_state())
        for _ in range(20):
            self.lib.gp_go_step(0, 0)
        self.lib.gp_go_step(0, 1)                        # skip with A
        self.assertEqual(self.GO_CONTINUE, self.lib.gp_go_state())
        self.lib.gp_go_step(0, 1)                        # Continue? Yes
        result = 0
        for _ in range(60):
            result = result or self.lib.gp_go_step(0, 0)
        self.assertEqual(1, result)                      # GAME_OVER_RESULT_CONTINUE
        self.assertEqual(0x30, self.lib.gp_health())

    def test_game_over_no_and_no_returns_to_title_without_healing(self):
        self.die()
        self.lib.gp_go_step(1, 0)                        # cursor to No
        self.lib.gp_go_step(0, 1)
        self.assertEqual(self.GO_CONTINUE, self.lib.gp_go_state())
        self.lib.gp_go_step(1, 0)
        self.lib.gp_go_step(0, 1)
        result = 0
        for _ in range(60):
            result = result or self.lib.gp_go_step(0, 0)
        self.assertEqual(2, result)                      # GAME_OVER_RESULT_TITLE
        self.assertEqual(0, self.lib.gp_health())

    def test_low_health_alarm_beats_every_thirty_steps(self):
        self.lib.gp_health_set(16, 48)                   # critical: <= 1 heart
        beats = 0
        for _ in range(90):
            self.step(*self.SPOT)
            beats += bool(self.lib.gp_events2() & self.ALARM)
        self.assertEqual(3, beats)
        self.lib.gp_health_set(17, 48)
        for _ in range(60):
            self.step(*self.SPOT)
            self.assertFalse(self.lib.gp_events2() & self.ALARM)

    def test_hit_from_behind_picks_the_back_clip(self):
        self.lib.gp_health_set(48, 48)
        self.lib.gp_hurt_set(8, 0)                       # pushed along +z
        self.step(*self.SPOT, yaw=0)                     # Link faces +z
        e = self.lib.gp_events2()
        self.assertTrue(e & (1 << 9) and e & (1 << 10) and e & (1 << 11))

    # --- M2d Navi call / C-Up -------------------------------------------
    NAVI_HELLO, NAVI_CALL, NAVI_TALK, LOCK_HOSTILE = 1, 2, 4, 16

    def test_navi_hint_waits_for_the_timer_window(self):
        self.lib.gp_navi_timer_set(598)
        self.step(*self.SPOT)
        self.assertEqual(0, self.lib.gp_navi_text())
        for _ in range(4):
            self.step(*self.SPOT)
        self.assertEqual(0x0140, self.lib.gp_navi_text())

    def test_navi_says_hey_once_per_offer_without_a_lock(self):
        self.lib.gp_navi_timer_set(700)
        self.step(*self.SPOT)
        self.assertTrue(self.lib.gp_events2() & self.NAVI_HELLO)
        self.step(*self.SPOT)
        self.assertFalse(self.lib.gp_events2() & (self.NAVI_HELLO | self.NAVI_CALL))

    def test_c_up_reads_the_hint_and_marks_it_read(self):
        self.lib.gp_navi_timer_set(700)
        self.step(*self.SPOT)
        self.lib.gp_c_up(1)
        self.step(*self.SPOT)
        self.lib.gp_c_up(0)
        self.assertTrue(self.lib.gp_talking())
        self.assertTrue(self.lib.gp_events2() & self.NAVI_TALK)
        self.assertEqual(3001, self.lib.gp_navi_timer())
        self.assertEqual(0, self.lib.gp_navi_text())

    def test_hint_changes_after_the_deku_tree_opens(self):
        self.lib.save_set_event_chk_inf(0x05)
        self.lib.gp_navi_timer_set(700)
        self.step(*self.SPOT)
        self.assertEqual(0x0141, self.lib.gp_navi_text())

    def test_no_hint_outside_the_forest(self):
        self.lib.gp_scene(5)
        self.lib.gp_reset_no_greeting()
        self.lib.gp_navi_timer_set(700)
        self.step(*self.SPOT)
        self.assertEqual(0, self.lib.gp_navi_text())

    def test_locked_enemy_with_navi_text_calls_hey_listen(self):
        h = self.enemy(dz=100)
        self.lib.gp_actor_navi_text(h, 0x0140)
        self.hold_at_spot()
        seen = 0
        for _ in range(2):
            seen |= self.lib.gp_events2()
            self.step(*self.SPOT, target=1)
        self.assertTrue(seen & self.NAVI_CALL)

    def test_hostile_lock_flags_the_hostile_lock_sound(self):
        h = self.enemy(dz=100)
        self.lib.gp_actor_hostile(h)
        seen = 0
        for _ in range(self.GP_TARGET_HOLD_STEPS):
            self.step(*self.SPOT, target=1)
            seen |= self.lib.gp_events2()
        self.assertTrue(seen & self.LOCK_HOSTILE)

    def test_scene_change_resets_a_short_timer(self):
        self.lib.gp_navi_timer_set(1200)
        self.lib.gp_reset_no_greeting()
        self.assertEqual(0, self.lib.gp_navi_timer())

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
            self.lib.gp_reset_no_greeting()
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
            self.lib.gp_reset_no_greeting()
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
            self.lib.gp_reset_no_greeting()
            x, y, z = self.talk_spot(index)
            self.step(x, y, z, yaw=0)
            self.step(x, y, z, yaw=0, interact=1)
            if not self.lib.gp_talking():
                continue
            name = self.lib.gp_speaker_name()
            self.assertIn(name, (b'Kokiri Boy', b'Kokiri Girl', b'Fado', b'Know-It-All Brother'))
            girl = (self.lib.gp_npc_param(index) & 255) in (1, 5, 6, 9, 10)
            if name.startswith(b'Kokiri'):
                self.assertEqual(name, b'Kokiri Girl' if girl else b'Kokiri Boy')
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

    def test_b_opens_save_confirmation_and_b_returns_to_page(self):
        self.menu(pause=1)
        self.menu(cancel=1)
        self.assertTrue(self.lib.gp_paused())
        self.assertTrue(self.lib.gp_save_prompt())
        self.menu(cancel=1)
        self.assertFalse(self.lib.gp_save_prompt())
        self.assertTrue(self.lib.gp_paused())

    def test_start_leaves_save_prompt_and_reopens_main_page(self):
        self.menu(pause=1)
        self.menu(cancel=1)
        self.assertTrue(self.lib.gp_save_prompt())
        self.menu(pause=1)
        self.assertFalse(self.lib.gp_paused())
        self.menu(pause=1)
        self.assertFalse(self.lib.gp_save_prompt())

    def test_dpad_moves_equipment_cursor_vertically_and_wraps(self):
        self.menu(pause=1)
        self.assertEqual(self.lib.gp_cursor(), 1)
        for expected in (5, 9, 13, 1):
            self.menu(menu_step=1)
            self.assertEqual(self.lib.gp_cursor(), expected)
        self.menu(menu_step=-1)
        self.assertEqual(self.lib.gp_cursor(), 13)

    def test_save_confirmation_raises_request_and_equips_nothing(self):
        GP_EVENT_SAVE = 1 << 19
        self.menu(pause=1)
        self.menu(cancel=1)
        self.menu(interact=1)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SAVE)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_EQUIP)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_DENIED)
        self.assertEqual(0, self.lib.gp_equipped())

    def test_the_save_row_has_no_item_but_still_has_a_name_and_a_use(self):
        self.assertEqual(0, self.lib.gp_slot_item(GP_SLOT_SAVE))
        self.assertTrue(self.lib.gp_slot_name(GP_SLOT_SAVE))
        self.assertTrue(self.lib.gp_slot_use(GP_SLOT_SAVE))

    def test_equipping_a_real_slot_still_raises_equip_not_save(self):
        GP_EVENT_SAVE = 1 << 19
        sx, sy, sz, _ = self.pickup(0)
        self.step(sx, sy, sz)
        self.menu(pause=1)
        self.menu(interact=1)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_EQUIP)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_SAVE)

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

    # --- quest-correct dialogue ------------------------------------------
    # These are the regression tests for the bug the human reported: NPCs
    # speaking lines from later in the game. Each speaker's text-id function is
    # extracted as an ordered rule list, and the FIRST rule whose conditions
    # hold wins, so a fresh save must never reach a later-quest line.

    KOKIRI_NPC_MIDO = 1
    KOKIRI_NPC_SARIA = 2

    # save_state.h
    EQUIP_TYPE_SWORD = 0
    EQUIP_TYPE_SHIELD = 1
    EQUIP_VALUE_SWORD_KOKIRI = 1
    EQUIP_VALUE_SHIELD_DEKU = 1
    QUEST_KOKIRI_EMERALD = 18
    EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI = 0x04
    INFTABLE_MIDO_REFUSED_ONCE = 0x0C
    INFTABLE_SARIA_GREETED_LINK = 0x00

    def npc_of_kind(self, kind):
        for i in range(self.lib.gp_npc_count()):
            if self.lib.gp_npc_kind(i) == kind:
                return i
        self.fail('no NPC of kind %d placed' % kind)

    def talk_to(self, index):
        """Open a FRESH box on one speaker and report the message chosen.

        Closing first matters: with a box already open an A press advances or
        closes it instead of re-selecting a rule, so a second talk_to() would
        report the previous speaker's message.
        """
        x, y, z = self.talk_spot(index)
        while self.lib.gp_talking():
            self.step(x, y, z, yaw=0, cancel=1)
        self.step(x, y, z, yaw=0)
        self.step(x, y, z, yaw=0, interact=1)
        self.assertTrue(self.lib.gp_talking())
        return self.lib.gp_rule_text_id()

    def test_mido_says_his_fresh_file_line_not_the_post_emerald_one(self):
        """The reported bug. 0x1045 needs the Kokiri Emerald; 0x102F is the
        real no-flag baseline -- 'you can't go see the Great Deku Tree without
        a sword and a shield' (z_en_md.c:419-447)."""
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.assertEqual(0x102F, self.talk_to(mido))

    def test_saria_says_her_fresh_file_line(self):
        """0x1002 requires INFTABLE_SARIA_GREETED_LINK; 0x1001 is the real
        baseline (z_en_sa.c)."""
        saria = self.npc_of_kind(self.KOKIRI_NPC_SARIA)
        self.assertEqual(0x1001, self.talk_to(saria))

    def test_mido_line_advances_once_he_has_refused_once(self):
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.lib.save_set_inf_table(self.INFTABLE_MIDO_REFUSED_ONCE)
        self.assertEqual(0x1030, self.talk_to(mido))

    def test_mido_gate_line_needs_gear_equipped_not_merely_owned(self):
        """0x1033 is the line that makes Mido stand aside, and z_en_md.c:437
        tests CUR_EQUIP_VALUE -- owning the gear is not enough."""
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.lib.save_give_equip(self.EQUIP_TYPE_SWORD,
                                 self.EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(self.EQUIP_TYPE_SHIELD,
                                 self.EQUIP_VALUE_SHIELD_DEKU)
        self.assertEqual(0x102F, self.talk_to(mido))
        self.lib.save_set_equip(self.EQUIP_TYPE_SWORD,
                                self.EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_set_equip(self.EQUIP_TYPE_SHIELD,
                                self.EQUIP_VALUE_SHIELD_DEKU)
        self.assertEqual(0x1033, self.talk_to(mido))

    def test_mido_says_the_post_emerald_line_only_with_the_emerald(self):
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.lib.save_give_quest_item(self.QUEST_KOKIRI_EMERALD)
        self.assertEqual(0x1045, self.talk_to(mido))

    def test_higher_priority_rule_wins_over_a_later_one(self):
        """Both guards hold at once; the Emerald rule comes first in the
        original ladder, so it must win."""
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.lib.save_set_event_chk_inf(
            self.EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI)
        self.assertEqual(0x1034, self.talk_to(mido))
        self.lib.save_give_quest_item(self.QUEST_KOKIRI_EMERALD)
        self.assertEqual(0x1045, self.talk_to(mido))

    def test_setting_one_speakers_flag_does_not_move_another_speaker(self):
        mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        saria = self.npc_of_kind(self.KOKIRI_NPC_SARIA)
        self.lib.save_set_inf_table(self.INFTABLE_MIDO_REFUSED_ONCE)
        self.assertEqual(0x1001, self.talk_to(saria))
        self.assertEqual(0x1030, self.talk_to(mido))

    # --- surviving a save and reload -------------------------------------
    # The human reported: pick up the sword and shield, save, reload -- both
    # gone. gameplay_reset() runs when entering a scene, which is AFTER the
    # file select has loaded a file, and it was writing the session's empty
    # gear back over the save it had just restored.

    def test_gear_survives_a_scene_reset(self):
        """A reset must restore gear from the save, not wipe it."""
        for index in range(2):
            x, y, z, _ = self.pickup(index)
            self.step(x, y, z)
        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_owned())
        self.lib.gp_reset_no_greeting()
        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_owned())
        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_equipped())
        self.assertTrue(self.lib.save_mido_demands_met())

    def test_rupees_survive_a_scene_reset(self):
        x, y, z, value, room = self.rupee(0)
        self.lib.gp_room(room)
        self.step(x, y, z)
        self.assertEqual(value, self.lib.gp_rupees())
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(room)
        self.assertEqual(value, self.lib.gp_rupees())
        # Source flag 0x24 is temporary: scene reload respawns this green.
        self.assertEqual(0x24, self.lib.gp_rupee_flag(0))
        self.step(x, y, z)
        self.assertEqual(value * 2, self.lib.gp_rupees())

    def test_a_new_game_still_starts_empty_handed(self):
        """The fix must not make a fresh file inherit the last one's gear."""
        for index in range(2):
            x, y, z, _ = self.pickup(index)
            self.step(x, y, z)
        self.lib.save_new_game()
        self.lib.gp_reset_no_greeting()
        self.assertEqual(0, self.lib.gp_owned())
        self.assertEqual(0, self.lib.gp_equipped())
        self.assertEqual(0, self.lib.gp_rupees())
        self.assertFalse(self.lib.save_mido_demands_met())

    def test_cut_grass_is_deliberately_not_persisted(self):
        """OoT keeps grass in the temp half of the scene flags, which it never
        saves, so regrowing across a reload is the original's behaviour."""
        gx, gy, gz = self.spawn_grass_rupee()
        self.assertTrue(self.lib.gameplay_grass_cut(0))
        self.lib.gp_reset_no_greeting()
        self.assertFalse(self.lib.gameplay_grass_cut(0))

    def test_gear_survives_an_actual_save_and_reload(self):
        """The human's exact report, end to end through the real serialiser.

        Collect the sword and shield, write the save block the way the pause
        menu's SAVE does, wipe everything as returning to the title and loading
        a file would, then read the block back and re-enter the scene.
        """
        SAVE_FILE_BYTES = 314  # v7: 8 + 304 + 2
        for index in range(2):
            x, y, z, _ = self.pickup(index)
            self.step(x, y, z)
        rupee_x, rupee_y, rupee_z, value, room = self.rupee(4)
        self.lib.gp_room(room)
        self.step(rupee_x, rupee_y, rupee_z)
        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_owned())
        purse = self.lib.gp_rupees()
        self.assertGreaterEqual(purse, value)

        block = ctypes.create_string_buffer(SAVE_FILE_BYTES)
        self.lib.gp_save_pack(block)

        # Everything gone, as it is after a return to the title.
        self.lib.save_new_game()
        self.lib.gp_reset_no_greeting()
        self.assertEqual(0, self.lib.gp_owned())

        self.assertEqual(0, self.lib.gp_save_unpack(bytes(block.raw), SAVE_FILE_BYTES))
        self.lib.gp_reset_no_greeting()           # entering the scene, as on load
        self.lib.gp_room(room)

        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_owned())
        self.assertEqual(GP_SWORD | GP_SHIELD, self.lib.gp_equipped())
        self.assertEqual(purse, self.lib.gp_rupees())
        self.assertTrue(self.lib.save_mido_demands_met())
        # The rupee is not lying on the floor again.
        self.step(rupee_x, rupee_y, rupee_z)
        self.assertEqual(purse, self.lib.gp_rupees())

    # --- M2b.1 starter route (FEAT-001) ------------------------------------
    SAVE_SCENE_KOKIRI_FOREST = 0

    def forest(self, room=0):
        self.lib.gp_scene(self.SAVE_SCENE_KOKIRI_FOREST)
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(room)

    def chest(self, index=0):
        vals = [ctypes.c_int() for _ in range(5)]
        self.lib.gp_chest_at(index, *(ctypes.byref(v) for v in vals))
        return tuple(v.value for v in vals)

    def wonders(self):
        out = []
        for i in range(self.lib.gp_wonder_total()):
            vals = [ctypes.c_int() for _ in range(8)]
            self.lib.gp_wonder_at(i, *(ctypes.byref(v) for v in vals))
            x, y, z, mode, value, room, rot_z, param = (v.value for v in vals)
            out.append(dict(i=i, x=x, y=y, z=z, mode=mode, value=value,
                            room=room, rot_z=rot_z, param=param))
        return out

    def test_mido_chests_grant_source_rewards_once_and_keep_scene_flags_separate(self):
        import math
        for i, reward in ((1, 5), (2, 5), (3, 1), (4, 0)):
            self.lib.gp_scene(8)
            self.lib.gp_reset_no_greeting()
            self.lib.gp_room(0)
            vals = [ctypes.c_int() for _ in range(5)]
            self.lib.gp_chest_at(i, *(ctypes.byref(v) for v in vals))
            x,y,z,yaw,room = (v.value for v in vals)
            angle = yaw * math.tau / 65536
            px, pz = x-round(25*math.sin(angle)), z-round(25*math.cos(angle))
            before = self.lib.gp_rupees()
            self.lib.gp_step_full(px,y,pz,yaw,0,0,0,1,1,0,0,0)
            self.assertTrue(self.lib.gp_chest_flag(i))
            self.assertFalse(self.lib.save_get_treasure(0, i-1))
            self.assertEqual(before+reward, self.lib.gp_rupees())
            self.lib.gp_reset_no_greeting()
            self.lib.gp_step_full(px,y,pz,yaw,0,0,0,1,1,0,0,0)
            self.assertEqual(before+reward,self.lib.gp_rupees())

    def world_prop(self, kind):
        for i in range(self.lib.gp_world_prop_count()):
            v=[ctypes.c_int() for _ in range(6)]
            self.lib.gp_world_prop_at(i,*(ctypes.byref(x) for x in v))
            x,y,z,aid,scene,param=(x.value for x in v)
            if aid==kind:
                self.lib.gp_scene(scene);self.lib.gp_reset_no_greeting();self.lib.gp_actors_reap()
                self.lib.gp_room(self.lib.gp_world_prop_room(i))
                self.step(x,y,z-35)
                return i,x,y,z,param
        self.fail('missing source actor '+hex(kind))

    def test_pot_attaches_to_hand_then_throw_breaks_on_impact(self):
        i,x,y,z,param=self.world_prop(0x111)
        handle=self.lib.gp_prop_handle(i)
        self.assertNotEqual(0,handle)
        self.step(x,y,z-35,interact=1)
        self.assertTrue(self.lib.gp_world_carrying())
        self.lib.gp_lift_sync(1,0,0,0,x,y+50,z-20)
        pos=[ctypes.c_int() for _ in range(3)]
        self.lib.gp_actor_pos(handle,*(ctypes.byref(v) for v in pos))
        self.assertEqual([x,y+50,z-20],[v.value for v in pos])
        self.lib.gp_lift_sync(2,2048,3072,0,x,y+50,z-20)
        self.assertFalse(self.lib.gp_world_carrying())
        self.lib.gp_ball_wall(1)
        self.step(x+200,y,z)
        self.assertEqual(0,self.lib.gp_prop_handle(i))
        self.assertTrue(self.lib.gp_events() & GP_EVENT_CUT)
        self.lib.gp_ball_wall(0)
        self.step(x+200,y,z)
        self.assertEqual(0,self.lib.gp_prop_handle(i))

    def test_put_down_keeps_pot_and_rock_cannot_be_cut_by_sword(self):
        i,x,y,z,param=self.world_prop(0x111)
        self.step(x,y,z-35,interact=1)
        self.lib.gp_lift_sync(1,0,0,0,x,y+20,z)
        self.lib.gp_lift_sync(2,0,0,0,x,y+20,z)
        self.lib.gp_ball_wall(1);self.step(x+200,y,z)
        self.assertNotEqual(0,self.lib.gp_prop_handle(i))
        self.assertEqual(0,self.lib.gp_prop_data(self.lib.gp_prop_handle(i),1))
        self.lib.gp_ball_wall(0)
        i,x,y,z,param=self.world_prop(0x14E)
        self.lib.gp_grant(GP_SWORD,GP_SWORD);self.step(x,y,z-35,attack=1)
        for _ in range(20): self.step(x,y,z-35)
        self.assertNotEqual(0,self.lib.gp_prop_handle(i))

    def test_sword_breaks_pot_once(self):
        i,x,y,z,param=self.world_prop(0x111)
        self.lib.gp_grant(GP_SWORD,GP_SWORD);self.step(x,y,z-35,attack=1)
        for _ in range(20): self.step(x,y,z-35)
        self.assertEqual(0,self.lib.gp_prop_handle(i))
        self.lib.gp_actors_reap();self.step(x,y,z-35)
        self.assertEqual(0,self.lib.gp_prop_handle(i))

    def test_all_signs_read_their_authored_text(self):
        import math
        for i in range(self.lib.gp_sign_count()):
            self.lib.gp_reset_no_greeting();self.lib.gp_actors_reap()
            v=[ctypes.c_int() for _ in range(6)]
            self.lib.gp_sign_at(i,*(ctypes.byref(x) for x in v))
            x,y,z,yaw,room,text=(a.value for a in v)
            angle=yaw*math.tau/65536
            self.lib.gp_room(room)
            self.step(x+round(40*math.sin(angle)),y,z+round(40*math.cos(angle)),yaw=yaw+32768,interact=1)
            self.assertEqual(text,self.lib.gp_rule_text_id(),i)

    def test_cut_sign_spawns_pieces_and_stops_reading_until_scene_reset(self):
        v=[ctypes.c_int() for _ in range(6)]
        self.lib.gp_sign_at(0,*(ctypes.byref(x) for x in v))
        x,y,z,yaw,room,text=(a.value for a in v)
        self.lib.gp_room(room);self.gear()
        self.step(x,y,z-35,attack=1)
        for _ in range(20): self.step(x,y,z-35)
        self.assertNotEqual(0x7FF,self.lib.gp_sign_parts(0))
        self.assertGreater(self.lib.gp_piece_count(),0)
        self.lib.gp_reset_no_greeting()
        self.assertEqual(0x7FF,self.lib.gp_sign_parts(0))
        self.assertEqual(0,self.lib.gp_piece_count())

    def test_gossip_stone_reacts_without_becoming_a_drop(self):
        i,x,y,z,param=self.world_prop(0x1B9)
        self.lib.gp_grant(GP_SWORD,GP_SWORD);before=self.lib.gp_drop_count()
        self.step(x,y,z-35,attack=1)
        seen=False
        for _ in range(18):
            self.step(x,y,z-35)
            seen |= self.lib.gp_prop_data(self.lib.gp_prop_handle(i),6)>0
        self.assertTrue(seen)
        self.assertNotEqual(0,self.lib.gp_prop_handle(i))
        self.assertEqual(before,self.lib.gp_drop_count())

    def test_fado_has_her_source_dialogue(self):
        fado=next(i for i in range(self.lib.gp_npc_count()) if self.lib.gp_npc_kind(i)==0 and (self.lib.gp_npc_param(i)&255)==12)
        self.assertEqual(0x10D7,self.talk_to(fado))
        self.step(*self.talk_spot(fado),cancel=1)
        self.assertTrue(self.lib.save_get_inf_table(0xB7))
        self.assertEqual(0x10D8,self.talk_to(fado))

    def saria(self):
        return next(i for i in range(self.lib.gp_npc_count())
                    if self.lib.gp_npc_kind(i) == 2 and self.lib.gp_npc_scene(i) == 0)

    def test_saria_fairy_line_advances_on_close(self):
        """Her spoken lines after the greeting, from EnSa_UpdateTalkState.

        0x1001 is the greeting cutscene's own text and is not reached by
        walking up to her, so this starts from a file that has already been
        greeted -- which is exactly what INFTABLE_SARIA_GREETED_LINK means.
        """
        saria = self.saria()
        self.lib.save_set_inf_table(0)          # INFTABLE_SARIA_GREETED_LINK
        self.assertEqual(0x1002, self.talk_to(saria))
        x, y, z = self.talk_spot(saria)
        self.step(x, y, z, cancel=1)
        self.assertTrue(self.lib.save_get_inf_table(1))
        self.assertEqual(0x1003, self.talk_to(saria))

    def test_closing_the_greeting_box_does_not_set_the_greeted_flag(self):
        """EnSa_BecomeIdle owns that flag, and only at the end of the cutscene.

        The interim this replaces set it when the 0x1001 box closed, which let
        a file skip the greeting entirely by talking past it.
        """
        saria = self.saria()
        self.assertEqual(0x1001, self.talk_to(saria))
        self.step(*self.talk_spot(saria), cancel=1)
        self.assertFalse(self.lib.save_get_inf_table(0))

    def test_greeting_runs_once_per_file_and_ends_by_setting_its_flag(self):
        """EnSa_Init starts it at spawn; EnSa_BecomeIdle closes it out.

        The type is chosen once, so a greeting that has been declined or
        already seen is not retried on every step for the rest of the scene.
        """
        self.lib.gameplay_reset()               # arms it, as scene entry does
        self.assertTrue(self.lib.gp_saria_greeting_step())
        self.assertTrue(self.lib.gp_saria_cs_playing())
        self.assertTrue(self.lib.gp_saria_cs_meshes())
        self.assertTrue(self.lib.gp_saria_cs_running())
        self.assertFalse(self.lib.save_get_inf_table(0))
        # The script runs out: the flag is written and the clips are freed.
        self.lib.gp_saria_cs_end()
        self.assertFalse(self.lib.gp_saria_greeting_step())
        self.assertTrue(self.lib.save_get_inf_table(0))
        self.assertFalse(self.lib.gp_saria_cs_meshes())
        self.assertFalse(self.lib.gp_saria_cs_running())
        # Re-entering the scene does not play it again.
        self.lib.gameplay_reset()
        self.assertFalse(self.lib.gp_saria_greeting_step())
        self.assertFalse(self.lib.gp_saria_cs_playing())

    def test_greeting_moves_saria_by_her_cue_and_returns_her_home(self):
        """EnSa_HandleCutscene takes her position and facing from cue channel 1.

        Her home is a long way from where the cue puts her, so drawing her at
        the placement instead of the cue would leave the shot empty.
        """
        saria = self.saria()
        home = (self.lib.gp_npc_x(saria), self.lib.gp_npc_y(saria),
                self.lib.gp_npc_z(saria))
        self.lib.gameplay_reset()
        self.assertTrue(self.lib.gp_saria_greeting_step())
        self.lib.gp_saria_cs_cue(3, 80, -7, 0, 409, 0x4000)
        self.assertEqual((self.lib.gp_npc_x(saria), self.lib.gp_npc_y(saria),
                          self.lib.gp_npc_z(saria)), (-7, 0, 409))
        self.assertEqual(self.lib.gp_npc_yaw(saria), 0x4000)
        # EnSa_BecomeIdle puts her back on home.pos and initRot.
        self.lib.gp_saria_cs_end()
        self.lib.gp_saria_greeting_step()
        self.assertEqual((self.lib.gp_npc_x(saria), self.lib.gp_npc_y(saria),
                          self.lib.gp_npc_z(saria)), home)

    def test_greeting_does_not_start_when_its_clips_cannot_load(self):
        """Without them she would stand in her idle pose through her own shot.

        The flag stays clear so the greeting is retried on the next entry
        rather than being silently skipped for the rest of the file.
        """
        self.lib.gp_saria_cs_fail_meshes(1)
        self.lib.gameplay_reset()
        self.assertFalse(self.lib.gp_saria_greeting_step())
        self.assertFalse(self.lib.gp_saria_cs_playing())
        self.assertFalse(self.lib.save_get_inf_table(0))
        self.lib.gp_saria_cs_fail_meshes(0)
        self.lib.gameplay_reset()
        self.assertTrue(self.lib.gp_saria_greeting_step())

    def test_heart_chest_still_opens_when_health_is_full(self):
        import math
        self.lib.gp_scene(8);self.lib.gp_reset_no_greeting()
        vals=[ctypes.c_int() for _ in range(5)]
        self.lib.gp_chest_at(4,*(ctypes.byref(v) for v in vals))
        x,y,z,yaw,room=(v.value for v in vals)
        self.lib.gp_room(room);self.lib.gp_health_set(48,48)
        angle=yaw*math.tau/65536
        self.step(x-round(25*math.sin(angle)),y,z-round(25*math.cos(angle)),yaw=yaw,interact=1)
        self.assertTrue(self.lib.gp_chest_flag(4))
        self.assertEqual(48,self.lib.gp_health())

    def test_placed_hearts_do_not_convert_to_rupees_and_collect_once(self):
        for i in range(self.lib.gp_world_prop_count()):
            vals=[ctypes.c_int() for _ in range(6)]
            self.lib.gp_world_prop_at(i,*(ctypes.byref(v) for v in vals))
            x,y,z,aid,scene,param=(v.value for v in vals)
            if aid!=0x15: continue
            self.lib.gp_scene(scene);self.lib.gp_reset_no_greeting();self.lib.gp_room(0)
            self.lib.save_damage(16)
            before=self.lib.gp_rupees()
            self.step(x,y,z)
            if ((param>>8)&63) < 32:
                self.assertTrue(self.lib.save_get_collectible(scene,(param>>8)&63))
            self.assertEqual(before,self.lib.gp_rupees())
            self.lib.gp_reset_no_greeting();self.step(x,y,z)
            self.assertEqual(before,self.lib.gp_rupees())

    def test_sword_chest_is_the_source_maze_chest(self):
        self.assertEqual(self.lib.gp_chest_total(), 11)
        x, y, z, yaw, room = self.chest()
        self.assertEqual((x, y, z, yaw, room), (-232, 178, 2245, 0, 2))
        self.assertEqual(self.lib.gp_chest_param(0), 0x04E0)

    def test_chest_opens_once_grants_sword_owned_not_equipped(self):
        x, y, z, _, room = self.chest()
        self.forest(room)
        self.step(x, y, z - 25, yaw=0)
        self.assertEqual(self.lib.gp_chest_prompt(), 0)
        self.step(x, y, z - 25, yaw=0, interact=1)
        self.assertEqual(self.lib.gp_owned(), GP_SWORD)
        self.assertEqual(self.lib.gp_equipped(), 0)      # pause screen equips
        self.assertTrue(self.lib.gameplay_chest_opened(0))
        self.assertTrue(self.lib.gp_talking())
        self.assertEqual(self.lib.gp_rule_text_id(), 0x00A4)
        self.assertEqual(self.lib.gp_get_item(), GP_SWORD)
        while self.lib.gp_talking():
            self.step(x, y, z - 25, yaw=0, interact=1)
        self.assertEqual(self.lib.gp_get_item(), 0)
        self.step(x, y, z - 25, yaw=0)
        self.assertEqual(self.lib.gp_chest_prompt(), -1)
        self.step(x, y, z - 25, yaw=0, interact=1)
        self.assertFalse(self.lib.gp_events() & GP_EVENT_PICKUP)
        self.lib.gp_reset_no_greeting()                        # reload the scene
        self.assertTrue(self.lib.gameplay_chest_opened(0))
        self.assertEqual(self.lib.gp_owned(), GP_SWORD)

    def test_chest_needs_the_source_offer_box_and_facing(self):
        x, y, z, _, room = self.chest()
        self.forest(room)
        for dx, dy, dz, yaw in ((0, 0, 10, 0x8000),     # in front of the lid
                                (0, 0, -60, 0),          # too far back
                                (25, 0, -25, 0),         # off to the side
                                (0, 12, -25, 0),         # height
                                (0, 0, -25, 0x4000)):    # facing away
            self.step(x + dx, y + dy, z + dz, yaw=yaw)
            self.assertEqual(self.lib.gp_chest_prompt(), -1, (dx, dy, dz, yaw))
        self.lib.gp_scene(5)                             # Link's house
        self.step(x, y, z - 25, yaw=0)
        self.assertEqual(self.lib.gp_chest_prompt(), -1)

    def test_proximity_wonder_pays_once_until_its_room_reloads(self):
        w = next(w for w in self.wonders() if w['mode'] == 2 and w['room'] == 2)
        self.assertEqual(w['param'] & 0x3F, 0x3F)            # no switch flag
        self.forest(2)
        before = self.lib.gp_rupees()
        self.step(w['x'], w['y'], w['z'])
        self.assertEqual(self.lib.gp_rupees(), before + w['value'])
        self.step(w['x'], w['y'], w['z'])
        self.assertEqual(self.lib.gp_rupees(), before + w['value'])
        self.lib.gp_room(0); self.step(0, 0, 0)               # leave the maze
        self.lib.gp_room(2); self.step(w['x'], w['y'], w['z'])
        self.assertEqual(self.lib.gp_rupees(), before + 2 * w['value'])

    def test_switch_flagged_wonder_stays_paid_after_reload(self):
        w = next(w for w in self.wonders() if w['param'] == 0x1256)
        self.forest(0)
        self.step(w['x'], w['y'], w['z'])
        paid = self.lib.gp_rupees()
        self.assertEqual(paid, 5)
        self.lib.gp_reset_no_greeting(); self.lib.gp_room(0)
        self.step(w['x'], w['y'], w['z'])
        self.assertEqual(self.lib.gp_rupees(), paid)

    def tags(self, mode, room=0):
        return sorted((w for w in self.wonders() if w['mode'] == mode and w['room'] == room),
                      key=lambda w: w['rot_z'] & 0xFF)

    def test_free_multitag_pays_after_every_tag(self):
        owner = next(w for w in self.wonders() if w['mode'] == 0)
        self.forest(0)
        for t in self.tags(1):
            self.assertEqual(self.lib.gp_rupees(), 0)
            self.step(t['x'], t['y'], t['z'])
        self.step(1000, 0, -1000)
        self.assertEqual(self.lib.gp_rupees(), owner['value'])

    def test_multitag_timer_runs_out(self):
        self.forest(0)
        first, second = self.tags(1)
        self.step(first['x'], first['y'], first['z'])
        for _ in range(130):                   # 81 frames at 20 Hz = 122 steps
            self.step(1000, 0, -1000)
        self.step(second['x'], second['y'], second['z'])
        self.step(1000, 0, -1000)
        self.assertEqual(self.lib.gp_rupees(), 0)

    def test_ordered_multitag_fails_out_of_order(self):
        owner = next(w for w in self.wonders() if w['mode'] == 5)
        first, second = self.tags(6)
        self.forest(0)
        self.step(second['x'], second['y'], second['z'])
        self.step(first['x'], first['y'], first['z'])
        self.step(1000, 0, -1000)
        self.assertEqual(self.lib.gp_rupees(), 0)
        self.forest(0)
        self.step(first['x'], first['y'], first['z'])
        self.step(second['x'], second['y'], second['z'])
        self.step(1000, 0, -1000)
        self.assertEqual(self.lib.gp_rupees(), owner['value'])

    def test_interact_wonder_needs_a_sword_hit(self):
        w = next(w for w in self.wonders() if w['mode'] == 3)
        i = w['i']
        self.forest(w['room'])
        for _ in range(3):
            self.step(w['x'], w['y'], w['z'] - 40, yaw=0)
        self.assertEqual(self.lib.gp_wonder_drop(i), 0)
        self.pickup(0)
        self.step(w['x'], w['y'], w['z'] - 40, yaw=0, attack=1)
        for _ in range(14):
            self.step(w['x'], w['y'], w['z'] - 40, yaw=0)
        self.assertEqual(self.lib.gp_wonder_drop(i), w['value'])
        for _ in range(20):
            self.step(w['x'], w['y'], w['z'])
        self.assertEqual(self.lib.gp_rupees(), w['value'])

    def test_a_fresh_file_can_afford_the_shield_without_a_sword(self):
        """FEAT-001: 40 rupees from source placements before any sword."""
        self.forest(0)
        spots = []
        for i in range(8):
            x, y, z, value, room = self.rupee(i)
            spots.append((room, x, y, z))
        for w in self.wonders():
            if w['mode'] == 2:
                spots.append((w['room'], w['x'], w['y'], w['z']))
        for mode in (1, 6):
            for t in self.tags(mode):
                spots.append((0, t['x'], t['y'], t['z']))
                spots.append((0, 1000, 0, -1000))
        for room, x, y, z in spots:
            self.lib.gp_room(room)
            self.step(x, y, z)
        self.assertEqual(self.lib.gp_owned(), 0)
        self.assertGreaterEqual(self.lib.gp_rupees(), 40)

    def test_mido_blocks_60_units_from_home_toward_link(self):
        self.forest(0)
        self.step(1522, 0, -300)
        self.assertEqual((self.lib.gp_mido_x(), self.lib.gp_mido_z()), (1522, 45))
        self.step(1822, 0, 105)
        self.assertEqual((self.lib.gp_mido_x(), self.lib.gp_mido_z()), (1582, 105))
        x, z = ctypes.c_int(), ctypes.c_int()
        self.assertEqual(self.lib.gp_mido_body(0, ctypes.byref(x), ctypes.byref(z)), 1)
        self.assertEqual(self.lib.gp_mido_body(2, ctypes.byref(x), ctypes.byref(z)), 0)

    def talk_mido(self):
        """Stand south of Mido's home, facing him, and talk the box through."""
        x, z = 1522, 105 - 150
        self.step(x, 0, z)
        self.step(x, 0, z, interact=1)
        self.assertTrue(self.lib.gp_talking())
        text = self.lib.gp_rule_text_id()
        while self.lib.gp_talking():
            self.step(x, 0, z, interact=1)
        return text

    def test_mido_refusal_sets_the_source_flags(self):
        self.forest(0)
        self.assertEqual(self.talk_mido(), 0x102F)
        self.assertTrue(self.lib.save_get_inf_table(self.INFTABLE_MIDO_REFUSED_ONCE))
        self.assertEqual(self.talk_mido(), 0x1030)
        self.assertEqual(self.lib.gp_mido_state(), 0)

    def test_mido_needs_both_equipped_then_walks_aside(self):
        self.forest(0)
        self.pickup(0)                                  # sword only
        self.assertIn(self.talk_mido(), (0x102F, 0x1030))
        self.assertEqual(self.lib.gp_mido_state(), 0)
        self.pickup(1)
        self.assertEqual(self.talk_mido(), 0x1033)
        self.assertEqual(self.lib.gp_mido_state(), 1)
        self.assertTrue(self.lib.save_get_event_chk_inf(
            self.EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI))
        for _ in range(400):
            self.step(1000, 0, -1000)
        self.assertEqual(self.lib.gp_mido_state(), 2)
        self.assertEqual((self.lib.gp_mido_x(), self.lib.gp_mido_z()), (1412, 211))
        self.lib.gp_reset_no_greeting()                       # later visit
        self.assertEqual((self.lib.gp_mido_x(), self.lib.gp_mido_z()), (1412, 211))
    # --- Kokiri Shop: the 40-rupee Deku Shield ------------------------------
    def test_post_emerald_mido_departure_waits_for_talk_and_path(self):
        self.lib.save_set_event_chk_inf(self.EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI)
        self.lib.save_give_quest_item(self.QUEST_KOKIRI_EMERALD)
        self.forest(0)
        self.assertEqual(self.lib.gp_mido_state(), 0)
        for _ in range(20):
            self.step(1522, 0, -300)
        self.assertFalse(self.lib.save_get_event_chk_inf(0x1C))
        self.assertEqual(self.talk_mido(), 0x1045)
        self.assertFalse(self.lib.save_get_event_chk_inf(0x1C))
        for _ in range(400):
            self.step(1000, 0, -1000)
        self.assertTrue(self.lib.save_get_event_chk_inf(0x1C))
        x, z = ctypes.c_int(), ctypes.c_int()
        self.assertFalse(self.lib.gp_mido_body(0, ctypes.byref(x), ctypes.byref(z)))
        forest_mido = self.npc_of_kind(self.KOKIRI_NPC_MIDO)
        self.assertFalse(self.lib.gp_npc_present(forest_mido))
        self.lib.gp_reset_no_greeting()
        self.assertFalse(self.lib.gp_npc_present(forest_mido))
        self.lib.gp_scene(8)
        self.lib.gp_reset_no_greeting()
        house = [i for i in range(self.lib.gp_npc_count()) if
                 self.lib.gp_npc_kind(i) == self.KOKIRI_NPC_MIDO and self.lib.gp_npc_scene(i) == 8]
        self.assertEqual(len(house), 1)
        self.assertTrue(self.lib.gp_npc_present(house[0]))

    def test_post_emerald_exit_guard_uses_source_path_endpoint_on_reload(self):
        guard = next(i for i in range(self.lib.gp_npc_count()) if
                     self.lib.gp_npc_kind(i) == 0 and
                     self.lib.gp_npc_scene(i) == 0 and (self.lib.gp_npc_param(i) & 255) == 3)
        self.lib.save_give_quest_item(self.QUEST_KOKIRI_EMERALD)
        for _ in range(2):
            self.forest(0)
            self.step(-1400, -80, -350)
            self.assertEqual((self.lib.gp_npc_x(guard), self.lib.gp_npc_y(guard),
                              self.lib.gp_npc_z(guard)), (-1416, -74, -138))

    SAVE_SCENE_KOKIRI_SHOP = 4
    COUNTER = (0, 0, 60, 0x8000)                # in front of EnOssan, facing him

    def shop(self, rupees):
        self.lib.gp_scene(self.SAVE_SCENE_KOKIRI_SHOP)
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(0)
        self.lib.gp_wallet(rupees)

    def shop_step(self, interact=0, cancel=0, menu_step=0, dx=0):
        x, y, z, yaw = self.COUNTER
        self.lib.gp_menu_dx(dx)
        self.lib.gp_step_full(x, y, z, yaw, 0, 0, 0, interact, 1, cancel, 0, menu_step)
        self.lib.gp_menu_dx(0)
        return self.lib.gp_rule_text_id() if self.lib.gp_talking() else None

    def to_facing(self):
        self.shop_step()
        self.assertTrue(self.lib.gp_shop_prompt())
        self.assertEqual(self.shop_step(interact=1), 0x009E)     # hello
        self.assertEqual(self.shop_step(interact=1), 0x0083)     # talk / quit
        self.assertEqual(self.lib.gp_choice_lines(), 2)

    def to_shelf(self, dx):
        """D-pad toward a shelf: the view turns 30 degrees, then the item text."""
        self.to_facing()
        self.shop_step(dx=dx)
        for _ in range(40):
            if self.lib.gp_shop_state() != 4:                   # GP_SHOP_TURN
                break
            self.shop_step()
        self.assertEqual(self.lib.gp_shop_face(), 30 if dx < 0 else -30)
        return self.lib.gp_rule_text_id()

    def to_choice(self):
        """Right shelf, bottom slot 0: the Deku Shield, then its buy prompt."""
        self.assertEqual(self.to_shelf(1), 0x009F)
        self.assertEqual(self.shop_step(interact=1), 0x0089)
        self.assertEqual(self.lib.gp_choice_lines(), 2)

    # ---- M3a generic choices (En_Ko EnKo_UpdateTalkState) -----------------

    def choice_step(self, interact=0, cancel=0, menu_step=0):
        self.lib.gp_step_full(0, 0, 0, 0, 0, 0, 0, interact, 1, cancel, 0, menu_step)
        return self.lib.gp_rule_text_id() if self.lib.gp_talking() else None

    def test_three_choice_clamps_and_continues_to_the_picked_text(self):
        self.assertTrue(self.lib.gp_open_choice(0x1038, 0))
        self.assertEqual(self.lib.gp_choice_lines(), 3)
        self.choice_step(menu_step=-1)
        self.assertEqual(self.lib.gp_choice(), 0)           # clamped, no wrap
        self.choice_step(menu_step=1)
        self.choice_step(menu_step=1)
        self.choice_step(menu_step=1)
        self.assertEqual(self.lib.gp_choice(), 2)           # clamped at last
        self.assertEqual(self.choice_step(interact=1), 0x103B)
        self.assertEqual(self.lib.gp_speaker(), 0)          # same box, same speaker

    def test_npc_choice_b_confirms_the_cursor_like_message_should_advance(self):
        self.assertTrue(self.lib.gp_open_choice(0x1035, 0))
        self.choice_step(menu_step=1)
        self.assertEqual(self.choice_step(cancel=1), 0x1037)

    def test_two_choice_first_option(self):
        self.assertTrue(self.lib.gp_open_choice(0x103E, 0))
        self.assertEqual(self.choice_step(interact=1), 0x103F)

    def test_shield_costs_exactly_40_and_is_owned_not_equipped(self):
        self.shop(40)
        self.to_choice()
        self.assertEqual(self.shop_step(interact=1), 0x004C)     # Buy
        self.assertEqual(self.lib.gp_rupees(), 0)
        self.assertEqual(self.lib.gp_owned(), GP_SHIELD)
        self.assertEqual(self.lib.gp_equipped(), 0)
        self.assertEqual(self.lib.gp_get_item(), GP_SHIELD)
        self.assertEqual(self.shop_step(interact=1), 0x006B)     # continue?
        self.shop_step(menu_step=1)
        self.assertEqual(self.shop_step(interact=1), None)       # quit
        # A second purchase is refused and costs nothing.
        self.lib.gp_wallet(99)
        self.to_choice()
        self.assertEqual(self.shop_step(interact=1), 0x0086)
        self.assertEqual(self.lib.gp_rupees(), 99)

    def test_39_rupees_is_refused_without_a_debit(self):
        self.shop(39)
        self.to_choice()
        self.assertEqual(self.shop_step(interact=1), 0x0085)
        self.assertEqual(self.lib.gp_rupees(), 39)
        self.assertEqual(self.lib.gp_owned(), 0)

    def test_dont_buy_returns_to_the_item_text(self):
        self.shop(50)
        self.to_choice()
        self.shop_step(menu_step=1)
        self.assertEqual(self.lib.gp_choice(), 1)
        self.assertEqual(self.shop_step(interact=1), 0x009F)
        self.assertEqual(self.lib.gp_rupees(), 50)
        self.assertEqual(self.lib.gp_owned(), 0)
        # B on the buy prompt is Don't buy (EnOssan_TestCancelOption).
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(cancel=1), 0x009F)
        self.assertEqual(self.lib.gp_rupees(), 50)

    def test_shop_shelf_cursor_follows_en_ossan(self):
        self.shop(99)
        self.assertEqual(self.to_shelf(1), 0x009F)               # slot 0
        self.assertEqual(self.shop_step(menu_step=-1), 0x00B2)   # up: nuts 5
        self.assertEqual(self.shop_step(dx=1), 0x00A1)           # outer: stick (3)
        self.assertEqual(self.lib.gp_shop_cursor(), 3)
        self.assertEqual(self.shop_step(dx=1), 0x00A1)           # edge: stays
        self.shop_step(dx=-1)                                    # back to 1
        self.shop_step()                                         # release
        self.shop_step(dx=-1)                                    # inner edge: turn
        self.assertEqual(self.lib.gp_shop_state(), 4)
        for _ in range(40):
            if self.lib.gp_shop_state() != 4:
                break
            self.shop_step()
        self.assertEqual(self.lib.gp_rule_text_id(), 0x0083)
        self.assertEqual(self.lib.gp_shop_face(), 0)
        # Left shelf enters at slot 4 (seeds) keeping the top/bottom row.
        self.lib.gp_menu_dx(0)
        self.shop_step(dx=-1)
        for _ in range(40):
            if self.lib.gp_shop_state() != 4:
                break
            self.shop_step()
        self.assertIn(self.lib.gp_shop_cursor(), (4, 5))

    def test_shop_held_direction_repeats_after_accumulating(self):
        """EnOssan_UpdateJoystickInputState: one move on the push, then every
        update once the accumulated stick passes 500."""
        self.shop(99)
        self.to_shelf(-1)                                        # left shelf, slot 4
        self.assertEqual(self.lib.gp_shop_cursor(), 4)
        self.shop_step(dx=-1)                                    # push: 6
        self.assertEqual(self.lib.gp_shop_cursor(), 6)
        moved = []
        for _ in range(12):                                      # keep holding
            self.shop_step(dx=-1)
            moved.append(self.lib.gp_shop_cursor())
        self.assertEqual(moved[0], 6)                            # no instant repeat
        self.assertEqual(moved[-1], 6)                           # outer edge holds
        self.shop_step()
        # Holding toward the shopkeeper walks back and turns at the inner edge.
        states = []
        for _ in range(20):
            self.shop_step(dx=1)
            states.append(self.lib.gp_shop_state())
        self.assertIn(4, states)                                 # GP_SHOP_TURN

    def test_shop_refusals_follow_en_girla(self):
        self.shop(99)
        self.to_shelf(-1)                                        # seeds
        self.lib.gp_menu_dx(0)
        if self.lib.gp_shop_cursor() != 4:
            self.shop_step(menu_step=1)
        self.assertEqual(self.lib.gp_rule_text_id(), 0x00DF)
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(interact=1), 0x0086)     # no bullet bag
        self.assertEqual(self.lib.gp_rupees(), 99)
        self.assertEqual(self.shop_step(interact=1), 0x00DF)     # back to item

    def test_shop_nuts_first_buy_fanfare_then_quick_buy(self):
        self.shop(99)
        self.to_shelf(1)
        self.assertEqual(self.shop_step(menu_step=-1), 0x00B2)   # nuts 5, 15 R
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(interact=1), 0x0034)     # first get
        self.assertEqual(self.lib.gp_rupees(), 84)
        self.assertEqual(self.shop_step(interact=1), 0x006B)
        self.assertEqual(self.shop_step(interact=1), 0x0083)     # continue
        self.shop_step(dx=1)
        for _ in range(40):
            if self.lib.gp_shop_state() != 4:
                break
            self.shop_step()
        self.assertEqual(self.lib.gp_rule_text_id(), 0x00B2)     # row kept
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(interact=1), 0x0084)     # quick buy
        self.assertEqual(self.lib.gp_rupees(), 69)

    def test_shop_heart_needs_missing_health(self):
        self.shop(99)
        self.to_shelf(-1)
        self.shop_step(menu_step=-1)
        for _ in range(3):
            self.shop_step(dx=-1)
        self.assertEqual(self.lib.gp_rule_text_id(), 0x00AC)     # heart (7)
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(interact=1), 0x0086)     # full health
        self.shop_step(interact=1)
        self.lib.gp_set_health(32)
        self.shop_step(interact=1)
        self.assertEqual(self.shop_step(interact=1), 0x0084)
        self.assertEqual(self.lib.gp_health_now(), 48)
        self.assertEqual(self.lib.gp_rupees(), 89)

    def test_b_ends_the_exchange_while_browsing(self):
        self.shop(50)
        self.to_shelf(1)
        self.assertIsNone(self.shop_step(cancel=1))
        self.assertEqual(self.lib.gp_shop_state(), 0)

    def test_shop_purchase_survives_save_and_reload(self):
        SAVE_FILE_BYTES = 314  # v7
        self.shop(45)
        self.to_choice()
        self.shop_step(interact=1)
        block = ctypes.create_string_buffer(SAVE_FILE_BYTES)
        self.lib.gp_save_pack(block)
        self.lib.save_new_game()
        self.assertEqual(0, self.lib.gp_save_unpack(bytes(block.raw), SAVE_FILE_BYTES))
        self.lib.gp_reset_no_greeting()
        self.assertEqual(self.lib.gp_owned(), GP_SHIELD)
        self.assertEqual(self.lib.gp_rupees(), 5)

    def test_shopkeeper_is_only_in_the_shop(self):
        self.lib.gp_scene(self.SAVE_SCENE_KOKIRI_FOREST)
        self.lib.gp_reset_no_greeting()
        self.shop_step()
        self.assertFalse(self.lib.gp_shop_prompt())

    def test_full_starter_route_reaches_mido_passage(self):
        """Fresh file: rupees, maze chest, shop, equip both, Mido stands aside."""
        self.test_a_fresh_file_can_afford_the_shield_without_a_sword()
        purse = self.lib.gp_rupees()
        x, y, z, _, room = self.chest()
        self.lib.gp_room(room)
        self.step(x, y, z - 25, yaw=0, interact=1)
        while self.lib.gp_talking():
            self.step(x, y, z - 25, yaw=0, interact=1)
        self.lib.gp_scene(self.SAVE_SCENE_KOKIRI_SHOP)
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(0)
        self.assertEqual(self.lib.gp_rupees(), purse)
        self.to_choice()
        self.shop_step(interact=1)                         # buy: 0x4C
        self.shop_step(interact=1)                         # 0x6B continue?
        self.shop_step(cancel=1)                           # B ends
        self.assertFalse(self.lib.gp_talking())
        self.assertEqual(self.lib.gp_rupees(), purse - 40)
        self.assertEqual(self.lib.gp_owned(), GP_SWORD | GP_SHIELD)
        self.lib.gp_scene(self.SAVE_SCENE_KOKIRI_FOREST)
        self.lib.gp_reset_no_greeting()
        self.lib.gp_room(0)
        self.assertNotEqual(self.talk_mido(), 0x1033)      # owned, not equipped
        for slot in (0, 1):                               # pause screen equip
            self.menu(pause=1)
            if slot: self.menu(menu_step=1)
            self.menu(interact=1)
            self.menu(pause=1)
        self.assertEqual(self.lib.gp_equipped(), GP_SWORD | GP_SHIELD)
        self.assertEqual(self.talk_mido(), 0x1033)
        self.assertEqual(self.lib.gp_mido_state(), 1)
    def test_dialogue_text_refuses_a_mismatched_file(self):
        """BUG-033: line text is a disc file; a stale or cut file is refused."""
        raw = self.text.raw[:-1]
        for bad in (b'XDLG' + raw[4:], raw[:4] + bytes([0, 1]) + raw[6:], raw[:-1] + b'x',
                    raw[:40]):
            buf = ctypes.create_string_buffer(bad)
            self.assertFalse(self.lib.gp_bind_text(buf, len(bad)))
        self.assertTrue(self.lib.gp_bind_text(self.text, len(raw)))
    # --- En_Goroiwa: maze rolling boulder (BUG-032) -------------------------
    GP_EVENT_HURT = 1 << 25
    PATH = [(-247, 120, 1869), (-247, 120, 1538), (-575, 120, 1538),
            (-575, 120, 1869), (-247, 120, 1869)]
    FAR = (-411, 120, 1700)                    # maze room, inside the loop

    def boulder(self):
        v = [ctypes.c_int() for _ in range(3)]
        state = self.lib.gp_boulder(*(ctypes.byref(x) for x in v))
        return tuple(x.value for x in v), state

    def maze(self):
        self.forest(2)
        self.step(*self.FAR)

    def test_boulder_spawns_on_path_start_and_rolls_the_loop(self):
        self.maze()
        self.assertTrue(self.lib.gp_boulder_live())
        (x, y, z), state = self.boulder()
        self.assertEqual((x, y), (-247, 120))
        self.assertLess(z, 1869)
        seen = set()
        for _ in range(600):
            self.step(*self.FAR)
            seen.add(self.lib.gp_boulder_next())
            (x, y, z), _ = self.boulder()
            self.assertEqual(y, 120)
            self.assertTrue(x in (-247, -575) or z in (1538, 1869), (x, z))
        self.assertEqual(seen, {1, 2, 3, 4})

    def test_boulder_top_speed_is_source_kokiri_speed(self):
        self.maze()
        for _ in range(40):
            self.step(*self.FAR)
        (_, _, z0), _ = self.boulder()
        self.step(*self.FAR)
        (_, _, z1), _ = self.boulder()
        self.assertIn(z0 - z1, (6, 7))          # 9.2 a frame at 20 Hz

    def run_into_boulder(self, shield=0):
        self.maze()
        spot = (-247, 120, 1650)                # on its first leg
        for _ in range(200):
            self.step(*spot, yaw=0, shield=shield)
            if self.lib.gp_events() & self.GP_EVENT_HURT:
                return spot
        self.fail('boulder never hit Link')

    def test_boulder_hit_costs_a_quarter_heart_and_knocks_back(self):
        start = self.lib.gp_health()
        self.run_into_boulder()
        self.assertEqual(self.lib.gp_health(), start - 4)
        self.assertEqual(self.lib.gp_knock_yaw(), 0x8000)   # away, toward -z
        (_, _, _), state = self.boulder()
        self.assertEqual(state, 1)                          # hop after hit

    def test_shield_does_not_block_the_boulder(self):
        start = self.lib.gp_health()
        self.run_into_boulder(shield=1)
        self.assertEqual(self.lib.gp_health(), start - 4)

    def test_boulder_keeps_its_direction_and_skips_hits_for_50_frames(self):
        spot = self.run_into_boulder()
        start = self.lib.gp_health()
        hurt = 0
        for _ in range(74):
            self.step(*spot)
            hurt += bool(self.lib.gp_events() & self.GP_EVENT_HURT)
        self.assertEqual(hurt, 0)
        self.assertEqual(self.lib.gp_health(), start)
        self.assertEqual(self.lib.gp_boulder_next(), 1)     # still toward point 1

    def test_boulder_restarts_when_the_maze_room_reloads(self):
        self.maze()
        for _ in range(30):
            self.step(*self.FAR)
        self.lib.gp_room(0); self.step(0, 0, 0)
        self.assertFalse(self.lib.gp_boulder_live())
        self.lib.gp_room(2); self.step(*self.FAR)
        (x, _, z), _ = self.boulder()
        self.assertEqual(x, -247)
        self.assertGreater(z, 1860)

    def test_boulder_contact_does_not_replay_knockdown_during_cooldown(self):
        spot = self.run_into_boulder()
        self.assertTrue(self.lib.gp_events() & (1 << 26))
        for tick in range(74):
            self.step(*spot)
            self.assertFalse(self.lib.gp_events() & (1 << 26),
                             'old hit restarted knockdown at step %d' % tick)

    # --- M2b: Link body/shield in the shared contact pass --------------------
    def test_contact_storage_fits_its_cart_carve(self):
        self.assertLessEqual(self.lib.gp_contacts_bytes(), 0x2000)   # host is larger

    def test_body_hit_costs_health_on_the_next_step(self):
        """Player_UpdateDamage reads the previous frame's cylinder AC_HIT."""
        self.maze()
        spot = (-247, 120, 1650)
        start = self.lib.gp_health()
        for _ in range(200):
            self.step(*spot)
            if self.lib.gp_boulder_hit():
                break
        else:
            self.fail('no contact')
        self.assertEqual(self.lib.gp_health(), start)          # same step: none
        self.step(*spot)
        self.assertEqual(self.lib.gp_health(), start - 4)
        self.assertTrue(self.lib.gp_events() & self.GP_EVENT_HURT)
        self.assertTrue(self.lib.gp_events() & (1 << 26))       # knockdown

    def test_intangible_link_takes_no_second_hit(self):
        spot = self.run_into_boulder()
        self.assertEqual(self.lib.gp_intangible(), 30)

    # --- M2c: source sword timeline -----------------------------------------
    MWA = dict(FORWARD=0, FORWARD_COMBO=2, RIGHT=4, RIGHT_COMBO=6, LEFT=8,
               STAB=12, STAB_COMBO=14)

    def armed(self):
        self.forest(0)
        self.lib.gp_grant(GP_SWORD, GP_SWORD)
        self.lib.gp_stick(-1, 0)

    def swing(self, stick=-1, target=0):
        self.lib.gp_stick(stick, 0)
        self.step(0, 0, 0, attack=1, target=target)
        return self.lib.gp_attack_id()

    def test_attack_follows_stick_and_targeting(self):
        """func_80837818 / D_80854480."""
        cases = [(-1, 0, 'RIGHT'), (-1, 1, 'FORWARD'), (0, 0, 'FORWARD'),
                 (0, 1, 'STAB'), (1, 0, 'RIGHT'), (2, 0, 'RIGHT'), (3, 0, 'LEFT')]
        for stick, target, name in cases:
            self.armed()
            self.assertEqual(self.swing(stick, target), self.MWA[name], (stick, target))

    def run_attack(self):
        for _ in range(40):
            if self.lib.gp_attack_phase() != 1:
                return
            self.step(0, 0, 0)

    def test_third_same_attack_in_a_row_is_the_combo(self):
        self.armed()
        ids = []
        for _ in range(4):
            ids.append(self.swing())
            self.run_attack()
        R, RC = self.MWA['RIGHT'], self.MWA['RIGHT_COMBO']
        self.assertEqual(ids, [R, R, RC, R])     # combo row breaks the chain

    def test_combo_count_expires_after_8_frames(self):
        self.armed()
        self.swing(); self.run_attack()
        self.swing(); self.run_attack()
        self.lib.gp_stick(-1, 1)                 # walk off: recovery ends
        for _ in range(12):
            self.step(0, 0, 0)
        self.lib.gp_stick(-1, 0)
        self.assertEqual(self.swing(), self.MWA['RIGHT'])

    def test_blade_window_is_the_source_frames(self):
        """RIGHT_SLASH_1H is live on clip frames 1..4 at 2/3 frame a step."""
        self.armed()
        self.swing()
        live = []
        for _ in range(8):
            self.step(0, 0, 0)
            live.append(bool(self.lib.gameplay_sword_active()))
        # checked frames (thirds): 0,2,4,6,8,10,12 -> frame 1 starts at 3
        self.assertEqual(live[:6], [False, False, True, True, True, True])

    def test_recovery_ends_on_stick_or_chains_on_x(self):
        self.armed()
        self.swing(); self.run_attack()
        self.assertEqual(self.lib.gp_attack_phase(), 2)
        self.lib.gp_stick(0, 1)
        self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_attack_phase(), 0)
        self.armed()
        self.swing(); self.run_attack()
        self.swing()
        self.assertEqual(self.lib.gp_attack_phase(), 1)
        self.assertTrue(self.lib.gp_events() & GP_EVENT_SWING)

    def test_forest_npcs_do_not_talk_or_target_inside_other_scenes(self):
        """Link's house (scene 5) sits over forest coordinates."""
        x, y, z = self.npc(0)[:3]
        self.lib.gp_scene(5)
        self.lib.gp_reset_no_greeting()
        for yaw in range(0, 65536, 8192):
            self.step(x, y, z - 30, yaw=yaw)
            self.assertEqual(self.lib.gp_prompt(), -1, yaw)

    def test_forward_stick_attack_lunges_then_slows(self):
        """PLAYER_STATE2_30: speedXZ 15 on frame 0, -5 a frame."""
        self.armed()
        self.swing(stick=0)                      # forward slash, not targeting
        self.lib.gp_stick(-1, 0)
        self.step(0, 0, 0)
        speeds = [self.lib.gp_lunge()]
        for _ in range(6):
            self.step(0, 0, 0)
            speeds.append(self.lib.gp_lunge())
        self.assertEqual(speeds[0], 655360)
        self.assertTrue(all(a > b or b == 0 for a, b in zip(speeds, speeds[1:])))
        self.assertEqual(speeds[-1], 0)
        self.armed()
        self.swing(stick=-1)
        self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_lunge(), 0)   # no stick: no lunge

    def charge_up(self, steps):
        self.armed()
        self.lib.gp_hold_x(1)
        self.swing()
        for _ in range(steps):
            self.step(0, 0, 0)

    def test_holding_x_through_the_swing_charges(self):
        self.charge_up(14)
        self.assertIn(self.lib.gp_attack_phase(), (3, 4))
        self.lib.gp_hold_x(0)

    def test_early_release_cancels_the_charge(self):
        self.charge_up(14)
        while self.lib.gp_attack_phase() == 3:
            self.step(0, 0, 0)
        self.lib.gp_hold_x(0)
        self.step(0, 0, 0)                   # charge < 0.1: cancel
        self.assertEqual(self.lib.gp_attack_phase(), 5)

    def test_release_after_commit_spins_and_long_charge_is_big_spin(self):
        self.charge_up(30)
        self.assertEqual(self.lib.gp_attack_phase(), 4)
        self.lib.gp_hold_x(0)
        self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_attack_id(), 24)       # SPIN_ATTACK_1H
        self.assertEqual(self.lib.gp_attack_phase(), 1)
        self.assertGreaterEqual(self.lib.gp_intangible(), 11)
        self.charge_up(90)
        self.assertGreaterEqual(self.lib.gp_charge(), 55706)
        self.lib.gp_hold_x(0)
        self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_attack_id(), 26)       # BIG_SPIN_1H

    def test_letting_go_during_the_swing_forfeits_the_charge(self):
        self.armed()
        self.lib.gp_hold_x(0)
        self.swing()
        self.step(0, 0, 0)
        self.lib.gp_hold_x(1)
        for _ in range(14):
            self.step(0, 0, 0)
        self.assertNotIn(self.lib.gp_attack_phase(), (3, 4))
        self.lib.gp_hold_x(0)

    def test_jump_slash_air_window_then_finishing_cut_on_landing(self):
        """func_8083BA90 / Player_Action_80844AF4: blade from frame 7 in the
        air; landing plays JUMPSLASH_FINISH with the combo count at 3."""
        self.armed()
        self.assertTrue(self.lib.gameplay_jump_attack_start())
        self.assertEqual(self.lib.gp_attack_phase(), 6)
        live = []
        for _ in range(12):
            self.step(0, 0, 0)
            live.append(bool(self.lib.gameplay_sword_active()))
        self.assertEqual(live.index(True), 11)         # damage from frame 7 (6 = trail)
        self.lib.gameplay_jump_attack_land()
        self.assertEqual(self.lib.gp_attack_id(), 19)
        self.assertEqual(self.lib.gp_attack_phase(), 1)

    def test_no_jump_slash_without_a_sword(self):
        self.forest(0)
        self.assertFalse(self.lib.gameplay_jump_attack_start())

    # --- M2c: blade contact, wall rebound, guard recoil, nutsball ----------
    def gear(self):
        self.forest(0)
        self.lib.gp_grant(GP_SWORD, GP_SWORD)
        self.lib.gp_grant(GP_SHIELD, GP_SHIELD)
        self.lib.gp_stick(-1, 0)

    def test_posed_blade_capsules_cut_grass_in_reach_only(self):
        self.gear()
        gx, gy, gz = self.grass(0)
        self.lib.gp_blade_set(1, gx - 40, gy + 20, gz, gx, gy + 20, gz)
        self.step(gx - 45, gy, gz, yaw=0x4000, attack=1)
        for _ in range(8):
            self.step(gx - 45, gy, gz, yaw=0x4000)
        self.assertTrue(self.lib.gameplay_grass_cut(0))

    def test_posed_blade_out_of_reach_cuts_nothing(self):
        self.gear()
        gx, gy, gz = self.grass(0)
        self.lib.gp_blade_set(1, gx - 200, gy + 20, gz, gx - 150, gy + 20, gz)
        self.step(gx - 45, gy, gz, yaw=0x4000, attack=1)
        for _ in range(8):
            self.step(gx - 45, gy, gz, yaw=0x4000)
        self.assertFalse(self.lib.gameplay_grass_cut(0))

    def test_wall_hit_pushes_back_once_per_swing(self):
        self.gear()
        self.lib.gp_blade_set(1, 0, 20, 10, 0, 20, 40)
        self.lib.gp_blade_wall(1)
        self.step(0, 0, 0, attack=1)
        pushed = False
        for _ in range(20):
            self.step(0, 0, 0)
            if self.lib.gp_events() & (1 << 28):
                pushed = True
                break
        self.assertTrue(pushed)
        # func_80842DF4: speedXZ -14 = -9.33 a step (Q16), then decays.
        self.assertLess(self.lib.gp_lunge(), 0)
        self.assertGreaterEqual(self.lib.gp_lunge(), -611669)
        self.step(0, 0, 0)
        self.assertFalse(self.lib.gp_events() & (1 << 28))

    def test_no_wall_push_before_frame_two(self):
        self.gear()
        self.lib.gp_blade_set(1, 0, 20, 10, 0, 20, 40)
        self.lib.gp_blade_wall(1)
        self.step(0, 0, 0, attack=1)
        self.step(0, 0, 0)          # thirds 2..4: curFrame < 2
        self.assertFalse(self.lib.gp_events() & (1 << 28))

    def test_blade_bounce_plays_rebound_then_idles(self):
        self.gear()
        self.step(0, 0, 0, attack=1)
        self.step(0, 0, 0)
        self.lib.gp_set_bounced()
        self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_attack_phase(), 8)
        self.assertTrue(self.lib.gp_events() & (1 << 29))
        self.assertLess(self.lib.gp_lunge(), 0)
        for _ in range(12):
            self.step(0, 0, 0)
        self.assertEqual(self.lib.gp_attack_phase(), 0)
        self.assertEqual(self.lib.gp_lunge(), 0)

    def test_blade_bounce_ends_crouch_stab_but_keeps_guard(self):
        self.gear()
        self.step(0, 0, 0, shield=1)
        self.step(0, 0, 0, shield=1, attack=1)
        self.assertEqual(self.lib.gp_attack_phase(), 7)
        self.lib.gp_set_bounced()
        self.step(0, 0, 0, shield=1)
        self.assertEqual(self.lib.gp_attack_phase(), 0)
        self.assertTrue(self.lib.gp_shielding())
        self.assertLess(self.lib.gp_lunge(), 0)

    def nut_at(self):
        x, y, z = (ctypes.c_int() for _ in range(3))
        self.lib.gp_nut_pos(*(ctypes.byref(v) for v in (x, y, z)))
        return x.value, y.value, z.value

    def test_nutsball_hurts_link_without_guard(self):
        self.gear()
        self.lib.gameplay_nut_fire(0, 10, 200, 0x8000)   # toward -z, at Link
        hurt = False
        for _ in range(60):
            self.step(0, 0, 0)
            hurt |= bool(self.lib.gp_hurt())
            if not self.lib.gp_nut_state():
                break
        self.assertTrue(hurt)
        self.assertFalse(self.lib.gp_nut_state())

    def test_deku_shield_reflects_nutsball_and_recoils(self):
        self.gear()
        self.step(0, 0, 0, yaw=0, shield=1)
        self.lib.gameplay_nut_fire(0, 10, 200, 0x8000)
        reflected = recoil = False
        for _ in range(60):
            self.step(0, 0, 0, yaw=0, shield=1)
            reflected |= bool(self.lib.gp_nut_reflected())
            recoil |= self.lib.gp_attack_phase() == 9
            self.assertEqual(self.lib.gp_hurt(), 0)
            if reflected and recoil:
                break
        self.assertTrue(reflected)
        self.assertTrue(recoil)
        self.assertEqual(self.lib.gp_nut_yaw(), 0)       # out along Link's facing
        z0 = self.nut_at()[2]
        self.step(0, 0, 0, yaw=0, shield=1)
        self.assertGreater(self.nut_at()[2], z0)

    def test_sword_breaks_nutsball(self):
        self.gear()
        self.lib.gameplay_nut_fire(0, 10, 60, 0x8000)
        self.step(0, 0, 0, attack=1)
        broke = False
        for _ in range(20):
            self.step(0, 0, 0)
            if self.lib.gp_events() & (1 << 30):
                broke = True
                break
        self.assertTrue(broke)

    def test_nutsball_breaks_on_a_wall(self):
        self.forest(0)
        self.lib.gameplay_nut_fire(0, 10, 500, 0)
        self.lib.gp_ball_wall(1)
        self.step(0, 0, 0)
        self.step(0, 0, 0)
        self.assertFalse(self.lib.gp_nut_state())

    def test_nutsball_falls_after_its_timer(self):
        self.forest(0)
        self.lib.gameplay_nut_fire(0, 100, 1000, 0)
        for _ in range(45):
            self.step(0, 0, 0)
        y0 = self.nut_at()[1]
        for _ in range(10):
            self.step(0, 0, 0)
        self.assertLess(self.nut_at()[1], y0)

    def test_dynamic_action_labels_all_presets_and_both_pad_modes(self):
        buf = ctypes.create_string_buffer(512)
        def expand(text):
            self.lib.ui_text_expand(text.encode(), buf, len(buf))
            return buf.value.decode()
        for preset, attack in enumerate(['X', 'X', 'B', 'B', 'Square']):
            for analog in (False, True):
                self.lib.ui_text_set_analog(analog)
                value = expand('[A] [B] [Jump] [Z] [R] [C-Up] [C] [Start]')
                self.assertIn('[' + attack + ']', value)
                self.assertNotIn('[]', value)
                self.assertNotIn('[Start]', value) if preset in (1, 4) else None
                self.assertNotIn('[C-Up]', value) if preset != 2 or not analog else None
            self.lib.ui_preferences_cycle(False)
        # Binding a jump to A removes its gameplay interaction; say so rather
        # than teaching a button that cannot perform the action.
        self.lib.ui_preferences_cycle(True)
        self.assertEqual(expand('[A] [Jump]'), '[unbound] [A]')
        self.assertEqual(expand('[Confirm]'), '[A]')
        self.assertNotIn('unbound', expand('[MenuPrev] [MenuNext] [AssignModifier]'))

    def test_custom_jump_labels_never_empty_in_any_preset(self):
        out = ctypes.create_string_buffer(64)
        for preset in range(5):
            for analog in (False, True):
                self.lib.ui_text_set_analog(analog)
                for binding in range(8):
                    self.lib.ui_text_expand(b'[Jump]', out, len(out))
                    self.assertNotIn(out.value, (b'[]', b'[Jump]', b'[unbound]'))
                    self.lib.ui_preferences_cycle(True)
            self.lib.ui_preferences_cycle(False)

    def test_every_source_page_survives_label_expansion_and_wrapping(self):
        text = (self.generated / 'kokiri_dialogue.c').read_text()
        pages = text.split('const dialogue_page_t dialogue_pages', 1)[1].split('};', 1)[0]
        pages = [(int(a), int(b)) for a,b in re.findall(r'{\s*(\d+),\s*(\d+)\s*}', pages)]
        self.lib.dialogue_line.restype = ctypes.c_char_p
        self.lib.dialogue_row.restype = ctypes.c_char_p
        expanded = ctypes.create_string_buffer(512)
        for preset in range(5):
            for analog in (False, True):
                self.lib.ui_text_set_analog(analog)
                for first,count in pages:
                    expected = []
                    for index in range(first, first + count):
                        self.lib.ui_text_expand(self.lib.dialogue_line(index), expanded, len(expanded))
                        expected.append(expanded.value.decode())
                    rows = self.lib.dialogue_prepare(first, count, 0)
                    lines = [self.lib.dialogue_row(i).decode() for i in range(rows)]
                    self.assertTrue(all(len(line) <= 38 for line in lines))
                    self.assertTrue(all(line.count('[') == line.count(']') for line in lines))
                    self.assertEqual(' '.join(' '.join(lines).split()),
                                     ' '.join(' '.join(expected).split()), (preset, analog, first))
            self.lib.ui_preferences_cycle(False)

if __name__ == '__main__':
    unittest.main()
