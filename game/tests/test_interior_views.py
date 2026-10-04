"""Staged source panorama banks and their actual collision-camera records."""
import pathlib
import struct
import unittest
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from asset_names import room_asset, STORY_BANK_PANORAMA

class InteriorViews(unittest.TestCase):
    def test_five_house_banks_have_source_face_counts_and_texture_budget(self):
        for scene, sides in [(0, 4), (3, 4), (4, 3), (5, 3), (6, 3)]:
            mesh = (ROOT / 'build/cd' / room_asset(STORY_BANK_PANORAMA,scene,'MSH')).read_bytes()
            pixels = (ROOT / 'build/cd' / room_asset(STORY_BANK_PANORAMA,scene,'TEX')).read_bytes()
            magic, vertices, faces, tiles, size, objects, _, _ = struct.unpack_from('>8I', mesh)
            self.assertEqual(magic, 0x4b524d31)
            self.assertEqual((vertices, faces, tiles), (sides*128, sides*32, sides*32))
            self.assertEqual(size, len(pixels))
            self.assertLessEqual(size + tiles*32, 140000)

    def test_camera_zero_locked_one_pivot_except_shop(self):
        for scene in [0, 2, 3, 4, 5, 6]:
            blob = (ROOT / f'build/cd/S{scene}.COL').read_bytes()
            nt, ns, nw, nc, nv, _ = struct.unpack_from('>6H', blob, 4)
            offset = 16 + nt*36 + ((nt*2+3)&~3) + ns*8 + nw*16
            self.assertGreaterEqual(nc, 2)
            locked = struct.unpack_from('>HhI', blob, offset)
            pivot = struct.unpack_from('>HhI', blob, offset+8)
            self.assertEqual(locked[:2], (0x19, 3))
            self.assertEqual(pivot[:2], (0x17 if scene == 2 else 0x1a, 3))
            self.assertLessEqual(pivot[2]+pivot[1], nv)

if __name__ == '__main__': unittest.main()
