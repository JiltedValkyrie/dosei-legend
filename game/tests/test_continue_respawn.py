"""Continue must reload the bank for the saved Tree entrance."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECOMP = (ROOT / 'src/recomp.c').read_text()
TABLE = (ROOT / 'build/generated/scene_table.c').read_text()


class ContinueRespawn(unittest.TestCase):
    def test_tree_has_many_entrance_rooms_that_need_their_own_bank(self):
        entries = re.search(r'const scene_entry_t scene_entries\[SCENE_COUNT\] = \{(.*?)\n\};',
                            TABLE, re.S).group(1)
        tree = next(line for line in entries.splitlines()
                    if 'SAVE_SCENE_DEKU_TREE' in line)
        self.assertIn(', 12, 19, 2, SAVE_SCENE_DEKU_TREE,', tree)

    def test_continue_always_reloads_saved_scene_and_spawn(self):
        body = RECOMP.split('respawn_after_game_over(void)\n{', 1)[1].split('\n}\n\nstatic void', 1)[0]
        self.assertNotIn('scene != resident &&', body)
        self.assertIn('if (!scene_flow_load(scene, spawn))', body)
        self.assertIn('if (!scene_flow_load(scene, spawn)) {\n            jo_core_error("Continue recovery load failed")', body)
        self.assertIn('if (spawn >= scene_entries[scene].spawns)', body)
        self.assertIn('if (save_state.health < GAME_OVER_CONTINUE_HEALTH)', body)


if __name__ == '__main__':
    unittest.main()
