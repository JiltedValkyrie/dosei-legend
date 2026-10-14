"""Source-backed sprite conversion invariants for the Dodongo route."""
import os
from pathlib import Path
import re
import sys
import unittest

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import dodongo_enemy_sources as source
from build_dodongo_enemy_anchors import ANCHORS, parent_map, sample_frames

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


def body(text, name):
    match = re.search(r'^(?:void|s32|s16) ' + re.escape(name) + r'\([^;{}]*\) \{', text, re.M)
    if match is None:
        raise AssertionError(name)
    return text[match.start():text.index('\n}', match.end()) + 2]


@unittest.skipUnless((OOT / source.SPRITE_SOURCES[0]).exists(), 'local OoT decomp required')
class SourceAdapters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = {Path(p).stem: (OOT / p).read_text(encoding='utf-8') for p in source.SPRITE_SOURCES}
        cls.adapted = {Path(p).stem: source.adapt(p, cls.original[Path(p).stem]) for p in source.SPRITE_SOURCES}

    def test_all_actor_draws_and_allocations_removed(self):
        for name, text in self.adapted.items():
            with self.subTest(actor=name):
                self.assertNotRegex(text, r'\bSkelAnime_(?:Init|InitFlex|Draw\w*)\(')
                # Nut reflection reads real Player shield orientation. It is
                # gameplay, not an enemy skeleton/head transform.
                if name == 'z_en_nutsball':
                    self.assertEqual(text.count('Matrix_'), 1)
                    self.assertIn('Matrix_MtxFToYXZRotS(&player->shieldMf', text)
                elif name == 'z_en_sw':
                    # Wall/floor traversal rotates collision normals, not a pose.
                    self.assertEqual(text.count('Matrix_'), 6)
                else:
                    self.assertNotIn('Matrix_', text)
                self.assertNotIn('->jointTable[', text)
                self.assertNotIn('->morphTable[', text)
        for rel in source.SPRITE_SOURCES:
            header = rel[:-2] + '.h'
            text = source.adapt(header, (OOT / header).read_text(encoding='utf-8'))
            self.assertNotRegex(text, r'Vec3s (jointTable|morphTable)\[')

    def test_source_damage_drop_and_shop_functions_unchanged(self):
        checks = {
            'z_en_dodojr': ('EnDodojr_CheckDamaged', 'EnDodojr_DropItem'),
            'z_en_dodongo': ('EnDodongo_CollisionCheck', 'EnDodongo_Death', 'EnDodongo_AteBomb'),
            'z_en_am': ('EnAm_UpdateDamage',),
            'z_en_zf': ('EnZf_CheckCollide',),
            'z_en_shopnuts': ('EnShopnuts_ColliderCheck', 'EnShopnuts_SpawnSalesman'),
            'z_en_dns': ('EnDns_Update',),
            'z_en_kakasi2': ('EnKakasi2_Update',),
            'z_en_nutsball': ('EnNutsball_Projectile', 'EnNutsball_Update'),
            'z_en_vm': ('EnVm_CheckHealth', 'EnVm_Attack', 'EnVm_Die'),
            'z_en_si': ('func_80AFB768', 'func_80AFB89C', 'func_80AFB950'),
        }
        for stem, names in checks.items():
            for name in names:
                with self.subTest(actor=stem, function=name):
                    self.assertEqual(body(self.original[stem], name), body(self.adapted[stem], name))
        for stem in self.original:
            # Source reward and dynamic child-spawn calls never disappear.
            for pattern in (r'Item_Drop\w+\(', r'Actor_Spawn\w*\(', r'Actor_OfferGetItem\('):
                self.assertEqual(len(re.findall(pattern, self.original[stem])),
                                 len(re.findall(pattern, self.adapted[stem])), (stem, pattern))

    def test_contacts_precede_at_registration(self):
        for stem, update, helper, collider in (
                ('z_en_dodongo', 'EnDodongo_Update', 'DodongoSprite_Dodongo', 'colliderAT'),
                ('z_en_am', 'EnAm_Update', 'DodongoSprite_Armos', 'hitCollider'),
                ('z_en_zf', 'EnZf_Update', 'DodongoSprite_Lizalfos', 'swordCollider')):
            text = body(self.adapted[stem], update)
            self.assertLess(text.index(helper), text.index('CollisionCheck_SetAT'))
            self.assertIn(collider, text)

    def test_ice_clocks_survive_without_draw(self):
        for stem, helper, timer in (('z_en_dodongo', 'EnDodongo_SpriteIce', 'iceTimer'),
                                    ('z_en_am', 'EnAm_SpriteIce', 'iceTimer'),
                                    ('z_en_zf', 'EnZf_SpriteIce', 'frozenTimer')):
            text = self.adapted[stem]
            self.assertIn(f'{helper}(this, play);', text)
            self.assertIn(f'this->{timer}--', text)
            self.assertEqual(text.count(f'this->{timer}--'), self.original[stem].count(f'this->{timer}--'))

    def test_baby_source_visibility_survives(self):
        text = body(self.adapted['z_en_dodojr'], 'EnDodojr_Update')
        self.assertIn('this->actor.update != NULL', text)
        self.assertIn('this->actionFunc == EnDodojr_WaitUnderground', text)
        self.assertIn('this->actionFunc == EnDodojr_DropItem', text)

    def test_boss_untouched(self):
        rel = 'src/overlays/actors/ovl_Boss_Dodongo/z_boss_dodongo.c'
        original = (OOT / rel).read_text(encoding='utf-8')
        self.assertEqual(source.adapt(rel, original), original)
        self.assertIn('Collider_UpdateSpheres', original)


class SemanticRecipes(unittest.TestCase):
    def test_source_contact_counts(self):
        self.assertEqual({k: len(v) for k, v in ANCHORS.items()},
                         dict(object_dodojr=1, object_am=4, object_dodongo=21, object_zf=4,
                              object_vm=1, object_st=7))
        self.assertNotIn('object_kingdodongo', ANCHORS)

    def test_attack_windows_keep_each_frame(self):
        samples = sample_frames(48, extra=range(29, 44))
        self.assertTrue(set(range(29, 44)) <= set(samples))
        self.assertEqual((samples[0], samples[-1]), (0, 47))
        self.assertEqual(sample_frames(1), [0])
        with self.assertRaises(ValueError):
            sample_frames(0)

    def test_pre_limb_parent_recipe(self):
        limbs = [dict(child=1, sibling=255), dict(child=2, sibling=3),
                 dict(child=255, sibling=255), dict(child=255, sibling=255)]
        self.assertEqual(parent_map(limbs), {0: None, 1: 0, 2: 1, 3: 0})


if __name__ == '__main__':
    unittest.main()
