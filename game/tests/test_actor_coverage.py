"""Inventory keeps hidden states/dependencies explicit; absence cannot pass ready."""
import sys
import unittest
import tempfile
import struct
from pathlib import Path
from unittest.mock import patch

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

    def test_spawner_local_choice_keeps_both_source_targets(self):
        source = '''if (type == WOLF) spawnId = ACTOR_EN_WF;
                    else spawnId = ACTOR_EN_SKB;
                    Actor_SpawnAsChild(ctx, self, play, spawnId, 0);'''
        edge = coverage.spawn_edges(source, 'z_en_encount1.c')[0]
        self.assertEqual(edge['resolution'], 'finite_source_assignments')
        self.assertEqual(edge['targets'], ['ACTOR_EN_SKB', 'ACTOR_EN_WF'])
        source = source.replace('ACTOR_EN_SKB', 'ids[type]')
        self.assertEqual(coverage.spawn_edges(source, 'z_en_encount1.c')[0]['resolution'], 'review_indirect')

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

    def test_overlay_identity_survives_misdeclared_profile_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'src/code').mkdir(parents=True)
            (root / 'include/tables').mkdir(parents=True)
            (root / 'include/tables/actor_table.h').write_text('''
            /* 0x04 */ DEFINE_ACTOR(Boss_Goma, ACTOR_BOSS_GOMA)
            /* 0x05 */ DEFINE_ACTOR(En_Goma, ACTOR_EN_GOMA)
            ''')
            (root / 'include/tables/scene_table.h').write_text('')
            (root / 'src/code/actors.c').write_text('''
            ActorProfile Boss_Goma_Profile = {
              ACTOR_BOSS_GOMA, ACTORCAT_BOSS, FLAGS, OBJECT_GOMA,
              sizeof(BossGoma), Init, Destroy, Update, Draw };
            ActorProfile En_Goma_Profile = {
              ACTOR_BOSS_GOMA, ACTORCAT_ENEMY, FLAGS, OBJECT_GOL,
              sizeof(EnGoma), Init, Destroy, Update, Draw };
            void Spawn(void) { Actor_Spawn(ctx, play, choice, 0); }
            int flags = ACTOR_FLAG_ATTENTION_ENABLED;
            ''')
            with patch.object(coverage.imp, 'object_ids', return_value=({'OBJECT_GOMA': 1, 'OBJECT_GOL': 2}, {})):
                actors = coverage.build(root, root)['actors']
            self.assertEqual(actors['ACTOR_BOSS_GOMA']['category'], 'ACTORCAT_BOSS')
            self.assertEqual(actors['ACTOR_EN_GOMA']['object_id'], 2)
            self.assertEqual(actors['ACTOR_EN_GOMA']['profile_declared_id'], 'ACTOR_BOSS_GOMA')
            self.assertNotIn('ACTOR_FLAG_ATTENTION_ENABLED', actors['ACTOR_EN_GOMA']['spawn_dependencies'])

    def test_sprite_archives_count_one_object_skeleton_library(self):
        import build_sprite_keys
        rows = [[3, 8, 'Idle', 0, 'Body'], [3, 8, 'Walk', 1, 'Body'],
                [3, 8, 'Tail', 2, 'TailSkel']]
        symbols = 'Body = 0x06000100; TailSkel = 0x06000200; Idle = 0x06000300; Walk = 0x06000400; Tail = 0x06000500;'
        def sheet(width):
            blob = bytearray(56 + width * 8 // 2 * 5)
            struct.pack_into('>4s8H', blob, 0, b'SPR1', width, 8, 5, 1, 1, 4, 1, 0)
            return bytes(blob)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'build/oot-core').mkdir(parents=True)
            (root / 'build/oot-core/obj_syms.ld').write_text(symbols)
            (root / 'G00300.SP2').write_bytes(build_sprite_keys.pack(0x100, [(0x300, sheet(8)), (0x400, sheet(16))]))
            (root / 'G00301.SP2').write_bytes(build_sprite_keys.pack(0x200, [(0x500, sheet(8))]))
            with patch.object(coverage, 'GAME', root):
                packages = coverage.sheets(rows, root)[3]
            self.assertEqual(len(packages), 2)
            self.assertEqual(packages[0]['clips'], ['Idle', 'Walk'])
            self.assertEqual(packages[0]['vdp1_instance_bytes'], 96)
            self.assertEqual(packages[1]['skeleton_key'], 0x200)


if __name__ == '__main__':
    unittest.main()
