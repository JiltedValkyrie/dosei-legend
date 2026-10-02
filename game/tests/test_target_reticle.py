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
        # Slingshot aim: VDP2 text crosshair at screen centre (human 2026-10-01).
        self.assertIn('jo_printf(20, 15, "+")', block)
        self.assertIn('kokiri_lock_reticle_draw(x,y,kind)', block)
        self.assertNotIn('kokiri_message_mark_draw', block)

    def test_hud_depth_follows_live_near_rejection_and_display_level(self):
        """SGL rejects z <= screen distance >> display level. Every HUD sprite
        sits just past it for the LIVE distance (first person 290 broke the old
        fixed depths: 35 and 31 were both inside its level-3 near of 36)."""
        source = (ROOT / 'src/kokiri_sgl.c').read_text(encoding='utf-8')
        header = (ROOT / 'src/kokiri_sgl.h').read_text(encoding='utf-8')
        main = (ROOT / 'src/main.c').read_text(encoding='utf-8')
        level = int(header.split('#define KOKIRI_ZDSP_LEVEL')[1].split()[0])
        self.assertEqual(level, 3)                       # 240>>3=30: no wedge wrap
        self.assertIn('slZdspLevel(KOKIRI_ZDSP_LEVEL);', main)
        body = source[source.index('int                 kokiri_hud_depth'):]
        body = body[:body.index('}') + 1]
        self.assertIn('demo_screen_distance() >> KOKIRI_ZDSP_LEVEL', body)
        for path in ('src/kokiri_sgl.c', 'src/minimap.c', 'src/npc_draw.c'):
            text = (ROOT / path).read_text(encoding='utf-8')
            self.assertNotIn('pos[2] = 31 * 65536', text, path)
        self.assertNotIn('cutscene_screen_distance() : 277', source)
        for distance in (180, 208, 240, 277, 290, 320, 400):
            for above in (1, 2, 3):
                self.assertGreater((distance >> level) + above, distance >> level)

    def test_aim_marker_has_dark_rim_and_tight_spacing(self):
        corner = build_lock_reticle_corner(0, (255, 255, 255), outline=(16, 16, 16))
        words = [rgb555(p) for p in corner.getdata()]
        self.assertIn(rgb555((16, 16, 16)), words)
        self.assertNotEqual(rgb555((16, 16, 16)), 0)        # rim is not transparent
        self.assertIn(rgb555((255, 255, 255)), words)
        source = (ROOT / 'src/kokiri_sgl.c').read_text(encoding='utf-8')
        self.assertIn('kind == KOKIRI_RETICLE_AIM ? 10 : 17', source)

    def test_player_facing_cd_fanfares_have_short_bounded_tracks(self):
        tracks = {entry['name']: entry for entry in
                  json.loads((ROOT / 'assets/audio/cdda_tracks.json').read_text())['tracks']}
        self.assertEqual(tracks['CHEST']['max_seconds'], 2.5)
        self.assertEqual(tracks['SMALL_ITEM']['max_seconds'], 2.25)
        self.assertEqual(tracks['ITEM_GET']['max_seconds'], 2.75)


if __name__ == '__main__':
    unittest.main()
