"""Enemy source inventory must not mistake candidates for ready content."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_enemy_roster as roster


class EnemyRoster(unittest.TestCase):
    def test_category_alone_decides_boss_exemption(self):
        self.assertEqual(roster.classify({'symbol': 'En_Ik', 'category': 'ACTORCAT_BOSS'}), 'boss_exempt')
        self.assertEqual(roster.classify({'symbol': 'En_Bdfire', 'category': 'ACTORCAT_ENEMY'}), 'sprite_enemy')
        self.assertEqual(roster.classify({'symbol': 'Boss_New', 'category': 'ACTORCAT_ENEMY'}), 'sprite_enemy')

    def test_hazards_and_children_keep_explicit_policy(self):
        self.assertEqual(roster.classify({'symbol': 'En_Yukabyun', 'category': 'ACTORCAT_ENEMY'}), 'hazard_geometry')
        self.assertEqual(roster.classify({'symbol': 'En_Fd_Fire', 'category': 'ACTORCAT_ENEMY'}), 'sprite_child')

    def test_armost_statue_only_and_grabber_player_gates(self):
        self.assertEqual(roster.player_gate('En_Am', 0), 'real_player_cutover')
        self.assertIsNone(roster.player_gate('En_Am', 1))
        self.assertEqual(roster.player_gate('En_Am'), 'params_review')
        self.assertEqual(roster.player_gate('En_Mb', 1), 'real_player_cutover')

    def test_placement_preserves_params_expression(self):
        self.assertEqual(roster.params('{ACTOR_EN_ST, {1, 2, 3}, {0, 0, 0}, -0x001,}'), ('-0x001', 65535))
        self.assertEqual(roster.params('{ACTOR_EN_ST, {1,2,3}, {0,0,0}, PARAMS(1, 2)}'), ('PARAMS(1, 2)', None))

    def test_adult_night_falls_back_to_day_then_main(self):
        layers = [{'layer': 0, 'present': True}, {'layer': 1, 'present': True},
                  {'layer': 2, 'present': True}, {'layer': 3, 'present': False}]
        self.assertEqual(roster.effective_layer(layers, 3)[0], 2)
        layers[2]['present'] = False
        self.assertEqual(roster.effective_layer(layers, 3)[0], 0)
        self.assertEqual(roster.effective_layer(layers, 4)[0], 0)

    def fixture(self):
        return {'actors': {'ENEMY': {'category': 'ACTORCAT_ENEMY', 'classification': 'sprite_enemy',
                                    'spawn_calls': [{'targets': ['ENEMY']}]}},
                'known_actor_ids': ['ENEMY'], 'source_boss_set': [],
                'scenes': [{'prefix': 'room', 'ready': False, 'rooms': [
                    {'room': 'r0', 'layer': 0, 'unknown_spawn_calls': [],
                     'budget': {'peak_instances': None, 'zelda_arena_bytes': None, 'tha_bytes': None}}]}]}

    def test_unknown_target_and_wrong_boss_set_fail_inventory(self):
        data = self.fixture()
        data['actors']['ENEMY']['spawn_calls'][0]['targets'] = ['UNKNOWN']
        data['source_boss_set'] = ['ENEMY']
        errors = roster.validate(data)
        self.assertTrue(any('unknown spawn target' in e for e in errors))
        self.assertTrue(any('boss set differs' in e for e in errors))

    def test_unknown_peak_cannot_pass_admission(self):
        data = self.fixture()
        self.assertEqual(roster.validate(data), [])
        self.assertTrue(any('unmeasured actor peak' in e for e in roster.validate(data, ['room'])))
        self.assertTrue(any('THA unmeasured' in e for e in roster.validate(data, ['room'])))

    def test_oversized_arenas_fail_even_with_complete_status(self):
        data = self.fixture()
        data['scenes'][0]['ready'] = True
        data['scenes'][0]['rooms'][0]['budget'] = {
            'peak_instances': 20, 'zelda_arena_bytes': 131073, 'tha_bytes': 196609}
        errors = roster.validate(data, ['room'])
        self.assertEqual(len(errors), 2)
        self.assertTrue(any('ZeldaArena exceeds' in e for e in errors))

    def test_non_enemy_spawner_remains_in_room_closure(self):
        actors = {'PROP': {'spawn_dependencies': ['ENEMY']}, 'ENEMY': {'spawn_dependencies': []}}
        rows = {'ENEMY': {'symbol': 'En_St', 'object_id': 5, 'sfx': [], 'effect_types': []}}
        layer = {'layer': 0, 'placements': [{'actor': 'PROP', 'entry': '{ PROP, {0,0,0}, {0,0,0}, 0 }'}]}
        result = roster.room_record({'prefix': 'scene'}, {'room': 'r0'}, 0, layer, rows, actors)
        self.assertEqual(result['reachable_actor_candidates'], ['ENEMY'])
        self.assertEqual(result['non_enemy_spawner_candidates'], ['PROP'])
        self.assertEqual(result['budget']['placed_instances_by_actor'], {})
        self.assertIsNone(result['budget']['peak_instances'])


if __name__ == '__main__':
    unittest.main()
