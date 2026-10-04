"""Inventory keeps hidden states/dependencies explicit; absence cannot pass ready."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_actor_coverage as coverage


class ActorCoverage(unittest.TestCase):
    def test_multiline_placements_keep_spawn_variant(self):
        rows = coverage.actor_placements('''{
            ACTOR_EN_HORSE_NORMAL,
            { -730, 0, -1100 }, // pos
            { 0, 0x8000, 3 }, // child after Talon returns
            -0x001 /* 0xFFFF */,
        }, { ACTOR_EN_IN, {1,2,3}, {0,0,1}, 0 },''')
        self.assertEqual(len(rows), 2)
        self.assertIn('0x8000, 3', rows[0]['entry'])
        self.assertIn('-0x001', rows[0]['entry'])
        self.assertNotIn('0xFFFF', rows[0]['entry'])

    def test_direct_and_indirect_spawn_arguments(self):
        source = '''Actor_Spawn(&play->actorCtx, play, ACTOR_EN_HORSE, x,y,z, 0,0,0, p);
        Actor_SpawnAsChild(&play->actorCtx, thisx, play, ids[(a + b) % 3], x,y,z, 0,0,0, p);'''
        edges = coverage.spawn_edges(source, 'actor.c')
        self.assertEqual(edges[0]['targets'], ['ACTOR_EN_HORSE'])
        self.assertEqual(edges[0]['resolution'], 'direct')
        self.assertEqual(edges[1]['actor_expression'], 'ids[(a + b) % 3]')
        self.assertEqual(edges[1]['resolution'], 'review_indirect')

    def test_spawn_closure_handles_cycles_and_unimported_child(self):
        actors = {'A': {'spawn_dependencies': ['B']},
                  'B': {'spawn_dependencies': ['A', 'MISSING']}}
        self.assertEqual(coverage.closure(['A'], actors), ['A', 'B', 'MISSING'])

    def test_nested_multiline_source_gate_retains_original_condition(self):
        source = '''if (Flags_GetSwitch(play, PARAMS_GET_U(this->actor.params, 0, 6)) &&
            (LINK_IS_CHILD || GET_EVENTCHKINF(EVENTCHKINF_TALON_RETURNED_FROM_CASTLE))) {
            Actor_Kill(&this->actor);
        }'''
        rows = coverage.condition_sites(source)
        self.assertEqual(len(rows), 1)
        self.assertIn('PARAMS_GET_U(this->actor.params, 0, 6)', rows[0]['expression'])
        self.assertIn('EVENTCHKINF_TALON_RETURNED_FROM_CASTLE', rows[0]['expression'])

    def test_coverage_gate_is_explicit_not_category_guess(self):
        self.assertIn('ACTOR_EN_HORSE_NORMAL', coverage.CHARACTERS)
        self.assertIn('ACTOR_EN_HORSE_LINK_CHILD', coverage.CHARACTERS)
        self.assertNotIn('ACTOR_BOSS_GOMA', coverage.CHARACTERS)


if __name__ == '__main__':
    unittest.main()
