"""Real King Dodongo gameplay survives the material-only Saturn adapter."""
import os
from pathlib import Path
import re
import struct
import sys
import unittest

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
import dodongo_boss_sources as source
from build_room_scene import pack_room

OOT = Path(os.environ.get('DOSEI_OOT', 'D:/Workspace-Claude/game-decomps/n64/oot'))


def body(text, name):
    match = re.search(r'^(?:void|s32|s16) ' + name + r'\([^;{}]*\) \{', text, re.M)
    if match is None:
        raise AssertionError(name)
    return text[match.start():text.index('\n}', match.end()) + 2]


@unittest.skipUnless((OOT / source.BOSS_SOURCE).exists(), 'local OoT decomp required')
class BossSource(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = (OOT / source.BOSS_SOURCE).read_text(encoding='utf-8')
        cls.adapted = source.adapt(source.BOSS_SOURCE, cls.original)

    def test_real_combat_pose_and_story_actions_retained(self):
        for name in ('BossDodongo_AteExplosive', 'BossDodongo_Inhale',
                     'BossDodongo_BlowFire', 'BossDodongo_Vulnerable',
                     'BossDodongo_UpdateDamage', 'BossDodongo_DeathCutscene',
                     'BossDodongo_IntroCutscene', 'BossDodongo_PostLimbDraw',
                     'BossDodongo_OverrideLimbDraw', 'BossDodongo_UpdateEffects'):
            with self.subTest(function=name):
                self.assertEqual(body(self.original, name), body(self.adapted, name))
        self.assertIn('SkelAnime_Init(', self.adapted)
        self.assertIn('Collider_UpdateSpheres(limbIndex, &this->collider)', self.adapted)
        for pattern in (r'Actor_Spawn\w*\(', r'Flags_SetClear\(', r'Item_Drop\w*\('):
            self.assertEqual(len(re.findall(pattern, self.original)),
                             len(re.findall(pattern, self.adapted)))

    def test_texture_placeholders_never_written(self):
        self.assertNotIn('sLavaFloorLavaTex', self.adapted)
        self.assertNotIn('sLavaFloorRockTex', self.adapted)
        self.assertNotIn('gDodongosCavernBossLavaFloorTex', self.adapted)
        self.assertNotIn('func_808C1554(', self.adapted)
        self.assertIn('this->saturnLavaPhase = 0;', self.adapted)
        self.assertIn('this->saturnLavaPhase = 256;', self.adapted)
        self.assertIn('Math_SmoothStepToF(&this->unk_224, 0.0f, 1.0f, 0.01f, 0.0f)', self.adapted)

    def test_profile_uses_boss_identity_for_renderer_and_effect_views(self):
        profile = self.adapted.split('ActorProfile Boss_Dodongo_Profile = {', 1)[1].split('};', 1)[0]
        self.assertIn('ACTOR_BOSS_DODONGO,', profile)
        self.assertNotIn('ACTOR_EN_DODONGO,', profile)
        self.assertIn('ACTORCAT_BOSS,', profile)

    def test_child_support_keeps_source_burn_reward_and_story(self):
        cases = ((source.SUPPORT_SOURCES[0], ('EnBdfire_Update', 'func_809BC598', 'func_809BC2A4')),
                 (source.SUPPORT_SOURCES[1], ('DoorWarp1_PlayerInRange', 'DoorWarp1_ChildWarpIdle',
                                             'DoorWarp1_ChildWarpOut', 'DoorWarp1_WarpAppear')),
                 (source.SUPPORT_SOURCES[2], ('ItemBHeart_Init', 'ItemBHeart_Update')))
        for rel, names in cases:
            original = (OOT / rel).read_text(encoding='utf-8')
            adapted = source.adapt(rel, original)
            for name in names:
                with self.subTest(function=name):
                    self.assertEqual(body(original, name), body(adapted, name))
            if rel == source.SUPPORT_SOURCES[0]:
                self.assertNotIn('Matrix_', adapted)

    def test_portal_height_is_source_driven_in_both_layers(self):
        rel = source.SUPPORT_SOURCES[1]
        adapted = source.adapt(rel, (OOT / rel).read_text(encoding='utf-8'))
        self.assertIn('DoorWarp1_SaturnPortal(this, play, this->unk_194 * 230.0f)', adapted)
        self.assertIn('DoorWarp1_SaturnPortal(this, play, this->unk_198 * 60.0f)', adapted)
        self.assertEqual(adapted.count('gSPDisplayList(POLY_XLU_DISP++, gWarpPortalDL)'), 1)


class LavaBank(unittest.TestCase):
    def setUp(self):
        self.vertices = [(0, 0, 0), (10, 0, 0), (0, 0, 10)]
        self.faces = [dict(idx=(0, 1, 2, 2), tex_off=0, cull=False, mesh=False)]
        self.tiles = {0: dict(width=8, height=1, pixels=b'\x11'*4, clut=(0,)*16, index=0)}
        self.records = [dict(object=0, indices=[0, 1, 2, 2], surface_tag=0xDD01)]

    def pack(self):
        return pack_room(self.vertices, self.faces, self.tiles, self.records,
                         lambda vertices, indices: (0, 65536, 0))[0]

    def test_tag_preserves_existing_bank_layout(self):
        tagged = self.pack()
        attr = struct.unpack_from('>BB5H', tagged, 32 + 3*12 + 20)
        self.assertEqual(attr[5], 0xDD01)
        self.records[0]['surface_tag'] = 0
        plain = self.pack()
        self.assertEqual(len(tagged), len(plain))
        self.assertEqual(sum(a != b for a, b in zip(tagged, plain)), 2)

    def test_lava_cannot_share_tile_with_ordinary_surface(self):
        self.faces.append(dict(self.faces[0]))
        self.records.append(dict(self.records[0], surface_tag=0))
        with self.assertRaisesRegex(ValueError, 'shares a tile'):
            self.pack()

    def test_unknown_material_and_oversize_metadata_rejected(self):
        self.records[0]['surface_tag'] = 0xBEEF
        with self.assertRaisesRegex(ValueError, 'unknown room material'):
            self.pack()
        self.records[0]['surface_tag'] = 0xDD01
        self.tiles[0]['pixels'] = b'\x11' * 65536
        with self.assertRaisesRegex(ValueError, 'metadata bits'):
            self.pack()


if __name__ == '__main__':
    unittest.main()
