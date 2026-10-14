"""Source puzzle, reward and hazard actions survive Saturn presentation."""
import os
from pathlib import Path
import sys
import unittest

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME/'tools'))
import child_route_props as props
from child_route_effects import functions
OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


@unittest.skipUnless((OOT/props.SOURCES[0]).exists(), 'local decomp required')
class RouteProps(unittest.TestCase):
    def test_source_actions_are_retained(self):
        for rel in props.SOURCES:
            source = (OOT/rel).read_text(encoding='utf-8')
            adapted = props.adapt(rel, source)
            before, after = functions(source), functions(adapted)
            for name, body in before.items():
                if rel.endswith(('z_en_fire_rock.c', 'z_en_encount2.c')) and '_Draw' in name:
                    self.assertNotIn('Matrix_', after[name])
                    continue
                if name == 'EnRiverSound_Draw':
                    self.assertEqual(after['EnRiverSound_SaturnAudio'], body)
                    continue
                expected = body.replace('Rand_ZeroFloat(65536.0f)', '(s32)(Rand_ZeroFloat(32767.0f)) * 2')
                expected = expected.replace('(s16)(this->stalkSizeMultiplier * 700000.0f)',
                                            '(s16)((s32)(this->stalkSizeMultiplier * 10000.0f) * 70)')
                actual = after[name].replace('\n    if (thisx->update != NULL) EnRiverSound_SaturnAudio(thisx, play);', '')
                self.assertEqual(actual, expected, name)

    def test_vase_lid_and_damaging_rock_children_are_admitted(self):
        import scene_pack_actors as packs
        children = packs.child_spawns(OOT)
        self.assertIn('Bg_Spot18_Futa', children['Bg_Spot18_Basket'])
        self.assertIn('En_Fire_Rock', children['En_Encount2'])
        self.assertIn('En_Sw', children['Obj_Kibako2'])
        self.assertIn('En_Sw', children['Obj_Makekinsuta'])
        self.assertNotIn('ACTOR_EN_FIRE_ROCK', [name for name, _ in props.DRAW_SOURCES])
        self.assertIn('object_efc_star_field', props.SPRITE_OBJECTS)

    def test_field_keep_preserves_resident_keys_and_collision(self):
        import oot_core_import as imp
        data, ph, names = imp.object_blob_sources('gameplay_field_keep', OOT/'extracted/ntsc-1.2')
        self.assertIn('gBgBombwallCol', data)
        self.assertIn('gBgBombwallNormalDL', names)
        self.assertIn('gGrottoDL', names)
        self.assertFalse(set(names) & set(imp.KEEP_PLACEHOLDERS))
        self.assertNotIn('gSilverRockDL[1]', ph)


if __name__ == '__main__':
    unittest.main()
