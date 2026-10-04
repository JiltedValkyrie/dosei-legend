"""Offline Skin ownership, clock and runtime staging boundary regressions."""
import hashlib
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_horse_sprites as bake


class HorseSprites(unittest.TestCase):
    def test_separate_skin_limb_vertices_do_not_weld(self):
        a = [{'source_vertices': [0, 1, 2]}]
        b = [{'source_vertices': [0, 1, 2]}]
        bake.body_identity(a, 0)
        bake.body_identity(b, 7)
        keys = {(tuple(local), owner) for face in a + b
                for local, owner in zip(face['local'], face['vertex_limbs'])}
        self.assertEqual(len(keys), 6)
        self.assertTrue(all(k[1] < 0 for k in keys))

    def test_all_gameplay_horse_visual_variants_have_recipe(self):
        objects = {(r[2], r[3]) for r in bake.RECIPES}
        self.assertEqual(objects, {('object_horse_link_child', 'normal'),
                                   ('object_horse_normal', 'normal'),
                                   ('object_horse', 'epona'),
                                   ('object_hni', 'ingo'),
                                   ('object_hni', 'gerudo_saddle')})

    @unittest.skipUnless((ROOT / 'build/generated/horse-sprites/manifest.json').exists(), 'offline bake required')
    def test_actual_packages_preserve_clock_and_declared_costs(self):
        folder = ROOT / 'build/generated/horse-sprites'
        rows = json.loads((folder / 'manifest.json').read_text())['recipes']
        self.assertEqual(len(rows), 41)
        for row in rows:
            with self.subTest(clip=row['clip'], variant=row['variant']):
                blob = (folder / row['package']).read_bytes()
                self.assertEqual(blob[:4], b'SPR1')
                w, h, dirs, poses, ticks = struct.unpack_from('>5H', blob, 4)
                self.assertEqual(ticks, row['ticks'])
                self.assertGreater(ticks, 0)
                self.assertLessEqual(poses, bake.MAX_POSES)
                self.assertEqual(dirs, 5)
                self.assertEqual(row['cart_bytes'], len(blob) + 1)
                self.assertEqual(row['vdp1_instance_bytes'], ((w * h // 2 + 31) & ~31) + 32)
                order = struct.unpack_from(f'>{ticks}H', blob, 52)
                self.assertTrue(all(p < poses for p in order))
                start = (52 + ticks * 2 + 3) & ~3
                self.assertEqual(len(blob), start + w * h // 2 * dirs * poses)
                self.assertTrue(any(blob[start:]))
                self.assertEqual(hashlib.sha256(blob).hexdigest(), row['package_sha256'])
                self.assertFalse(row['runtime_imported'])
                self.assertFalse(row['staged'])
        self.assertFalse(list(folder.glob('*.BIN')))
        self.assertFalse(list(folder.glob('*.SKN')))
        self.assertFalse(list(folder.glob('*.ANM')))


if __name__ == '__main__':
    unittest.main()
