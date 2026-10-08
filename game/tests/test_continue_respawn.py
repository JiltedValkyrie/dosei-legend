"""Continue must reload the bank for the saved Tree entrance."""
import json
import pathlib
import struct
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
RECOMP = (ROOT / 'src/recomp.c').read_text()
TABLE = json.loads((ROOT / 'build/generated/scene_table.json').read_text())


class ContinueRespawn(unittest.TestCase):
    def test_tree_has_many_entrance_rooms_that_need_their_own_bank(self):
        tree = next(row for row in TABLE['scenes'] if row['prefix'] == 'ydan')
        self.assertEqual((tree['rooms'], tree['first_spawn'], tree['spawns']), (12, 19, 2))
        blob = (ROOT / 'build/cd/SCENETAB.BIN').read_bytes()
        self.assertEqual(TABLE['layout']['entry_bytes'], 26)
        entry = struct.unpack_from('>BB3h2H2hBxH5Bx', blob,
                                   TABLE['layout']['entry_offset'] + tree['index'] * 26)
        self.assertEqual(entry[9:13], (12, 19, 2, tree['save_scene']))
        spawns = [struct.unpack_from('>3hH2B', blob, (tree['first_spawn'] + i) * 10)
                  for i in range(tree['spawns'])]
        self.assertEqual([row[4] for row in spawns], [tree['index']] * 2)
        self.assertEqual([row[5] for row in spawns], [0, 9])

    def test_continue_always_reloads_saved_scene_and_spawn(self):
        body = RECOMP.split('respawn_after_game_over(void)\n{', 1)[1].split('\n}\n\nstatic void', 1)[0]
        self.assertNotIn('scene != resident &&', body)
        self.assertIn('if (!scene_flow_load(scene, spawn))', body)
        self.assertIn('if (!scene_flow_load(scene, spawn)) {\n            jo_core_error("Continue recovery load failed")', body)
        self.assertIn('if (spawn >= scene_entries[scene].spawns)', body)
        self.assertIn('if (save_state.health < GAME_OVER_CONTINUE_HEALTH)', body)


if __name__ == '__main__':
    unittest.main()
