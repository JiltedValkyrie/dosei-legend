"""Effect closure covers actor helpers and preserves original motion/lifetimes."""
import os
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME/'tools'))
import child_route_effects as effects
import scene_pack_actors as packs
OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT/'src/code/z_actor.c').exists(), 'local decomp required')
class SourceEffects(unittest.TestCase):
    def test_updates_survive_draw_adapter(self):
        for rel in effects.SOURCES:
            source = (OOT/rel).read_text(encoding='utf-8')
            before = effects.functions(source)
            after = effects.functions(effects.adapt(rel, source))
            for name, body in before.items():
                if '_Draw' in name:
                    self.assertNotIn('gSP', after[name])
                elif name == 'EffectSsDeadDs_Update':
                    self.assertEqual(after[name].replace('\n    EffectSsDeadDs_SaturnContact(play, this);', ''), body)
                elif name == 'EffectSsKiraKira_UpdateDispersed':
                    continue  # source angle expression is converted below
                elif 'Update' in name:
                    expected = body.replace('Rand_CenteredFloat(65535.0f)', '(Rand_CenteredFloat(32767.0f) * 2)')
                    expected = expected.replace('(32768.0f / this->rLifespan) * this->life', '(32768 * this->life) / this->rLifespan')
                    self.assertEqual(after[name], expected, name)

    def test_dead_ds_preserves_source_contact_queries_before_snapshot(self):
        rel = next(p for p in effects.SOURCES if p.endswith('z_eff_ss_dead_ds.c'))
        text = effects.adapt(rel, (OOT/rel).read_text(encoding='utf-8'))
        contact = effects.functions(text)['EffectSsDeadDs_SaturnContact']
        for token in ('BgCheck_EntitySphVsWall1', 'BgCheck_EntityRaycastDown1',
                      'this->pos.y = mf.yw;', 'this->rTimer++;'):
            self.assertIn(token, contact)

    def test_dungeon_profile_closure_includes_wrappers_and_child_tools(self):
        scene = next((OOT/'extracted/ntsc-1.2/assets/scenes').rglob('ddan_scene.c'))
        names = effects.scene_effects(OOT, packs.scene_pack(scene, packs.child_spawns(OOT)))
        for name in ('Dust', 'En_Ice', 'D_Fire', 'Dead_Dd', 'Dead_Ds', 'Dead_Db',
                     'Bomb2', 'Blast', 'G_Spk', 'Kakera', 'HitMark', 'Bubble', 'G_Ripple'):
            self.assertIn(name, names)
        self.assertNotIn('G_Magma', names)
        self.assertNotIn('G_Magma2', names)
        self.assertEqual(len(names), len(set(names)))


if __name__ == '__main__':
    unittest.main()
