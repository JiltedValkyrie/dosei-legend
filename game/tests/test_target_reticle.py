"""Lock reticle source geometry and fanfare cap contracts."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_demo_assets import build_lock_reticle_corner, rgb555


class TargetReticleTests(unittest.TestCase):
    def test_four_source_triangle_rotations_are_coloured_and_transparent(self):
        colour = (255, 255, 0)
        corners = [build_lock_reticle_corner(i, colour) for i in range(4)]
        expected = rgb555(colour)
        for corner in corners:
            words = [rgb555(pixel) for pixel in corner.getdata()]
            self.assertIn(expected, words)
            self.assertIn(0, words)
            self.assertEqual(words.count(expected),
                             sum(pixel == colour for pixel in corners[0].getdata()))
        self.assertEqual(corners[0].getpixel((2, 2)), colour)
        self.assertEqual(corners[1].getpixel((13, 2)), colour)
        self.assertEqual(corners[2].getpixel((13, 13)), colour)
        self.assertEqual(corners[3].getpixel((2, 13)), colour)

    def test_target_ui_uses_reticle_not_dialogue_glyphs(self):
        main = (ROOT / 'src/main.c').read_text(encoding='utf-8')
        block = main[main.index('if (demo_slingshot_aiming())'):main.index('kokiri_rupee_hud_draw()', main.index('if (demo_slingshot_aiming())'))]
        self.assertIn('kokiri_lock_reticle_draw(160,120,KOKIRI_RETICLE_AIM)', block)
        self.assertIn('kokiri_lock_reticle_draw(x,y,kind)', block)
        self.assertNotIn('kokiri_message_mark_draw', block)

    def test_player_facing_cd_fanfares_have_short_bounded_tracks(self):
        tracks = {entry['name']: entry for entry in
                  json.loads((ROOT / 'assets/audio/cdda_tracks.json').read_text())['tracks']}
        self.assertEqual(tracks['CHEST']['max_seconds'], 2.5)
        self.assertEqual(tracks['SMALL_ITEM']['max_seconds'], 2.25)
        self.assertEqual(tracks['ITEM_GET']['max_seconds'], 2.75)


if __name__ == '__main__':
    unittest.main()
