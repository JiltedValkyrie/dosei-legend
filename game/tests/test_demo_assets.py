import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_demo_assets import rgb555, main
from build_sgl_scene import read_scene

class DemoAssets(unittest.TestCase):
    def test_color_key_and_channels(self):
        self.assertEqual(rgb555((0, 0, 0)), 0)
        self.assertEqual(rgb555((255, 0, 0)), 0x801f)
        self.assertEqual(rgb555((0, 255, 0)), 0x83e0)
        self.assertEqual(rgb555((0, 0, 255)), 0xfc00)
        self.assertEqual(rgb555((1, 0, 0)), 0x8000)

    def test_staged_assets_preserve_baseline(self):
        main()
        baseline = ROOT.parent / 'shared'
        data, header, _, _ = read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
        start = header['collision_off']
        collision = (ROOT / 'build/cd/FOREST.COL').read_bytes()
        self.assertEqual(len(collision), 1692 * 36)
        self.assertEqual(collision, data[start:start + len(collision)])
        self.assertEqual((ROOT / 'build/cd/START.RGB').read_bytes(),
                         (baseline / 'assets/static/ui/PRESS_START.RAW').read_bytes())
        title = (ROOT / 'build/cd/TITLE.RGB').read_bytes()
        self.assertEqual(len(title), 512 * 256 * 2)
        self.assertTrue(any(title))
        self.assertEqual(title[:2], b'\0\0')
