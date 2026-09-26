"""Base-36 scene/room file names: Python tools and C runtime agree."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_names


class AssetNames(unittest.TestCase):
    def test_single_digit_names_unchanged(self):
        self.assertEqual(asset_names.room_asset(1, 2, 'MSH'), 'S1R2.MSH')
        self.assertEqual(asset_names.scene_asset(0, 'COL'), 'S0.COL')

    def test_ten_plus_rooms_stay_8_3(self):
        self.assertEqual(asset_names.room_asset(3, 11, 'TEX'), 'S3RB.TEX')
        self.assertEqual(asset_names.room_asset(35, 35, 'RGB'), 'SZRZ.RGB')
        self.assertEqual(asset_names.scene_asset(10, 'SUR'), 'SA.SUR')

    def test_out_of_range_rejected(self):
        for bad in (-1, 36):
            with self.assertRaises(ValueError):
                asset_names.digit(bad)

    def test_c_header_matches(self):
        text = (ROOT / 'src/asset_names.h').read_text()
        self.assertIn('#define ASSET_ID_LIMIT 36u', text)
        self.assertIn("'A' + (value - 10u)", text)
        self.assertEqual(asset_names.LIMIT, 36)

    def test_runtime_loaders_use_helper(self):
        for name in ('kokiri_sgl.c', 'scene_flow.c'):
            text = (ROOT / 'src' / name).read_text()
            self.assertNotRegex(text, r"(scene|room) > 9")
            self.assertIn('asset_name_digit', text)


if __name__ == '__main__':
    unittest.main()
