"""Drive the real save_state.c: flag spaces, equipment, health, new game.

Compiled and called through ctypes rather than reimplemented, so a rule that
changes in C changes here too. save_state.c is platform free, so no Saturn and
no BUP device is involved.

The flag numbers below are the ones lifted from the decomp; the point of most
of these tests is that a flag written through one accessor is readable through
the same accessor and does NOT disturb its neighbours, because the whole
progression rests on that.
"""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

# Mirrors of save_state.h. Kept literal so a rename in C shows up as a failure
# here rather than silently testing nothing.
EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS = 0x02
EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI = 0x04
EVENTCHKINF_DEKU_TREE_CLEARED = 0x09
EVENTCHKINF_BEGAN_GOHMA_BATTLE = 0x70
EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN = 0xA8

INFTABLE_SARIA_GREETED_LINK = 0x00
INFTABLE_MIDO_REFUSED_ONCE = 0x0C

QUEST_KOKIRI_EMERALD = 18

EQUIP_TYPE_SWORD = 0
EQUIP_TYPE_SHIELD = 1
EQUIP_VALUE_SWORD_KOKIRI = 1
EQUIP_VALUE_SHIELD_DEKU = 1

SAVE_SCENE_KOKIRI_FOREST = 0
SAVE_SCENE_DEKU_TREE = 2
SAVE_SCENE_COUNT = 11

HEART_UNIT = 0x10
NEW_CAPACITY = 0x30


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class SaveState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'save_state.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(output),
                        '-I' + str(ROOT / 'src'),
                        str(ROOT / 'src/save_state.c')],
                       check=True, env=env, cwd=str(ROOT))
        cls.lib = ctypes.CDLL(str(output))
        for name in ('save_get_event_chk_inf', 'save_get_inf_table',
                     'save_get_item_get_inf', 'save_check_quest_item',
                     'save_get_treasure', 'save_get_switch', 'save_get_clear',
                     'save_get_collectible', 'save_mido_demands_met',
                     'save_is_dead'):
            getattr(cls.lib, name).restype = ctypes.c_bool
        for name in ('save_cur_equip_value', 'save_all_equip_value'):
            getattr(cls.lib, name).restype = ctypes.c_uint

    def setUp(self):
        self.lib.save_new_game()

    # ---- new game ------------------------------------------------------

    def test_new_game_gives_three_hearts(self):
        self.assertEqual(NEW_CAPACITY, 3 * HEART_UNIT)
        self.assertFalse(self.lib.save_is_dead())
        # Full health: healing cannot raise it, damage of the whole capacity
        # empties it exactly.
        self.lib.save_damage(NEW_CAPACITY)
        self.assertTrue(self.lib.save_is_dead())

    def test_new_game_clears_every_flag_space(self):
        for flag in (EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS,
                     EVENTCHKINF_BEGAN_GOHMA_BATTLE,
                     EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN):
            self.assertFalse(self.lib.save_get_event_chk_inf(flag))
        self.assertFalse(self.lib.save_get_inf_table(INFTABLE_MIDO_REFUSED_ONCE))
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        self.assertEqual(0, self.lib.save_all_equip_value(EQUIP_TYPE_SWORD))

    def test_new_game_clears_flags_set_by_a_previous_file(self):
        self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_CLEARED)
        self.lib.save_give_quest_item(QUEST_KOKIRI_EMERALD)
        self.lib.save_set_treasure(SAVE_SCENE_KOKIRI_FOREST, 0)
        self.lib.save_new_game()
        self.assertFalse(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_DEKU_TREE_CLEARED))
        self.assertFalse(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_KOKIRI_FOREST, 0))

    # ---- playtest refill cheat ----------------------------------------

    def test_cheat_refill_restores_hearts_without_raising_capacity(self):
        self.lib.save_damage(0x20)
        self.lib.save_cheat_refill()
        self.lib.save_damage(NEW_CAPACITY - 1)
        self.assertFalse(self.lib.save_is_dead())    # exactly full, no more
        self.lib.save_damage(1)
        self.assertTrue(self.lib.save_is_dead())

    # ---- flag addressing ----------------------------------------------

    def test_event_flag_round_trips(self):
        self.lib.save_set_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI)
        self.assertTrue(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI))

    def test_event_flag_does_not_disturb_neighbours(self):
        # Mido's two flags are adjacent bits in the same word; the opening
        # progression breaks outright if setting one implies the other.
        self.lib.save_set_event_chk_inf(
            EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS)
        self.assertFalse(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI))
        self.assertFalse(self.lib.save_get_event_chk_inf(0x03))
        self.assertFalse(self.lib.save_get_event_chk_inf(0x01))

    def test_high_flag_numbers_land_in_the_right_word(self):
        # 0xA8 and 0x70 are the highest the opening uses; index = flag >> 4.
        self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN)
        self.assertTrue(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN))
        self.assertFalse(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_BEGAN_GOHMA_BATTLE))
        self.lib.save_set_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE)
        self.assertTrue(self.lib.save_get_event_chk_inf(
            EVENTCHKINF_BEGAN_GOHMA_BATTLE))

    def test_out_of_range_flag_is_refused_not_wrapped(self):
        # 14 words * 16 bits = 224 flags, so 0xE0 is past the end. It must not
        # alias back onto flag 0 and fake story progress.
        self.lib.save_set_event_chk_inf(0xE0)
        self.assertFalse(self.lib.save_get_event_chk_inf(0xE0))
        self.assertFalse(self.lib.save_get_event_chk_inf(0x00))

    def test_flag_spaces_are_independent(self):
        self.lib.save_set_inf_table(INFTABLE_SARIA_GREETED_LINK)
        self.assertTrue(self.lib.save_get_inf_table(
            INFTABLE_SARIA_GREETED_LINK))
        self.assertFalse(self.lib.save_get_event_chk_inf(0x00))
        self.assertFalse(self.lib.save_get_item_get_inf(0x00))

    # ---- scene flags ---------------------------------------------------

    def test_scene_flags_are_per_scene(self):
        # The Kokiri Sword is chest flag 0 in Kokiri Forest and the Slingshot
        # is chest flag 1 in the Deku Tree; opening one must not open another.
        self.lib.save_set_treasure(SAVE_SCENE_KOKIRI_FOREST, 0)
        self.assertTrue(self.lib.save_get_treasure(SAVE_SCENE_KOKIRI_FOREST, 0))
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_DEKU_TREE, 0))
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_KOKIRI_FOREST, 1))

    def test_scene_flag_fields_are_independent(self):
        self.lib.save_set_switch(SAVE_SCENE_DEKU_TREE, 4)
        self.assertTrue(self.lib.save_get_switch(SAVE_SCENE_DEKU_TREE, 4))
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_DEKU_TREE, 4))
        self.assertFalse(self.lib.save_get_clear(SAVE_SCENE_DEKU_TREE, 4))
        self.assertFalse(self.lib.save_get_collectible(SAVE_SCENE_DEKU_TREE, 4))

    def test_unknown_scene_is_refused(self):
        self.lib.save_set_treasure(SAVE_SCENE_COUNT, 0)
        self.assertFalse(self.lib.save_get_treasure(SAVE_SCENE_COUNT, 0))
        # and did not spill into a real scene
        for scene in range(SAVE_SCENE_COUNT):
            self.assertFalse(self.lib.save_get_treasure(scene, 0))

    # ---- equipment and Mido's gate -------------------------------------

    def test_owning_gear_is_not_equipping_it(self):
        self.lib.save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.assertEqual(EQUIP_VALUE_SWORD_KOKIRI,
                         self.lib.save_all_equip_value(EQUIP_TYPE_SWORD))
        self.assertEqual(0, self.lib.save_cur_equip_value(EQUIP_TYPE_SWORD))
        # This is the whole point: Mido tests CUR_EQUIP_VALUE, so merely owning
        # the sword and shield must NOT open his gate.
        self.assertFalse(self.lib.save_mido_demands_met())

    def test_mido_gate_opens_only_with_both_equipped(self):
        self.lib.save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.assertFalse(self.lib.save_mido_demands_met())
        self.lib.save_set_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.assertTrue(self.lib.save_mido_demands_met())

    def test_cannot_equip_what_is_not_owned(self):
        self.lib.save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.assertEqual(0, self.lib.save_cur_equip_value(EQUIP_TYPE_SWORD))
        self.assertFalse(self.lib.save_mido_demands_met())

    def test_unequipping_closes_the_gate_again(self):
        self.lib.save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_set_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_set_equip(EQUIP_TYPE_SHIELD, 0)
        self.assertFalse(self.lib.save_mido_demands_met())

    # ---- health --------------------------------------------------------

    def test_damage_clamps_at_zero(self):
        self.lib.save_damage(NEW_CAPACITY * 4)
        self.assertTrue(self.lib.save_is_dead())

    def test_healing_clamps_at_capacity(self):
        self.lib.save_damage(HEART_UNIT)
        self.lib.save_heal(HEART_UNIT * 10)
        self.assertFalse(self.lib.save_is_dead())
        # At capacity, one full capacity of damage still kills exactly.
        self.lib.save_damage(NEW_CAPACITY)
        self.assertTrue(self.lib.save_is_dead())

    def test_partial_damage_does_not_kill(self):
        self.lib.save_damage(NEW_CAPACITY - 1)
        self.assertFalse(self.lib.save_is_dead())
        self.lib.save_damage(1)
        self.assertTrue(self.lib.save_is_dead())

    # ---- the opening chain ---------------------------------------------

    def test_opening_progression_replays_end_to_end(self):
        """The Kokiri -> Emerald flag chain, as a pure state sequence."""
        # Mido refuses, unarmed.
        self.assertFalse(self.lib.save_mido_demands_met())
        self.lib.save_set_event_chk_inf(
            EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS)
        self.lib.save_set_inf_table(INFTABLE_MIDO_REFUSED_ONCE)
        # Sword from the room 2 chest, shield bought, both equipped.
        self.lib.save_set_treasure(SAVE_SCENE_KOKIRI_FOREST, 0)
        self.lib.save_give_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_give_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.lib.save_set_equip(EQUIP_TYPE_SWORD, EQUIP_VALUE_SWORD_KOKIRI)
        self.lib.save_set_equip(EQUIP_TYPE_SHIELD, EQUIP_VALUE_SHIELD_DEKU)
        self.assertTrue(self.lib.save_mido_demands_met())
        # Mido stands aside; Deku Tree met, mouth opens, intro seen.
        self.lib.save_set_event_chk_inf(EVENTCHKINF_MIDO_STOOD_ASIDE_KOKIRI)
        self.lib.save_set_event_chk_inf(0x0C)
        self.lib.save_set_event_chk_inf(0x05)
        self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN)
        # Slingshot, Gohma, blue warp, Emerald.
        self.lib.save_set_treasure(SAVE_SCENE_DEKU_TREE, 1)
        self.lib.save_set_event_chk_inf(EVENTCHKINF_BEGAN_GOHMA_BATTLE)
        self.lib.save_set_event_chk_inf(0x07)
        self.lib.save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_CLEARED)
        self.lib.save_give_quest_item(QUEST_KOKIRI_EMERALD)
        # Every gate along the way is still readable and none cancelled another.
        self.assertTrue(self.lib.save_check_quest_item(QUEST_KOKIRI_EMERALD))
        for flag in (0x02, 0x04, 0x05, 0x07, 0x09, 0x0C,
                     EVENTCHKINF_BEGAN_GOHMA_BATTLE,
                     EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN):
            self.assertTrue(self.lib.save_get_event_chk_inf(flag), hex(flag))
        self.assertTrue(self.lib.save_get_treasure(SAVE_SCENE_KOKIRI_FOREST, 0))
        self.assertTrue(self.lib.save_get_treasure(SAVE_SCENE_DEKU_TREE, 1))
        # Flags Link never earned stay clear.
        self.assertFalse(self.lib.save_get_event_chk_inf(0x1C))
        self.assertFalse(self.lib.save_get_event_chk_inf(0x0A))


if __name__ == '__main__':
    unittest.main()
