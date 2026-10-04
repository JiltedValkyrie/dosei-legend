"""Sprite keys must survive object compaction; wings must use texture alpha."""
import sys
import unittest
import re
import struct
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from build_sprite_keys import resolve
from oot_core_import import sprite_animation_header
import build_fairy
from PIL import Image


class SpritePipeline(unittest.TestCase):
    @unittest.skipUnless((ROOT / 'build/all-scenes/spot20_room_0/room.msh').exists(), 'baked Ranch required')
    def test_ranch_room_leaves_actor_bank_and_margin(self):
        import vdp1_budget as budget
        mesh = (ROOT / 'build/all-scenes/spot20_room_0/room.msh').read_bytes()
        tiles, pixels = struct.unpack_from('>2I', mesh, 12)
        header = (ROOT / 'build/generated/link_scene.h').read_text()
        value = lambda n: int(re.search(r'#\s*define\s+' + n + r'\s+(\d+)', header)[1])
        total = budget.bank_bytes(pixels, tiles) + budget.bank_bytes(value('LINK_PIXEL_BYTES'), value('LINK_TILE_COUNT'))
        total += budget.RUNTIME_SPRITE_BYTES + budget.FOREST_ACTOR_BYTES + budget.FOREST_VRAM_MARGIN
        self.assertLessEqual(total, budget.VDP1_USER_AREA)
        self.assertIn('spot20', budget.ACTOR_SCENES)

    def test_linked_key_replaces_rom_offset(self):
        rows = [[0xe0, 18, 'gMalonChildIdleAnim', 20]]
        result = resolve(rows, '_gMalonChildIdleAnim = 0x06000bd8;')
        self.assertIn('0x000BD8', result)
        # Recompacting a blob must change the key without rebaking its pixels.
        self.assertIn('0x000080', resolve(rows, '_gMalonChildIdleAnim = 0x06000080;'))
        with self.assertRaises(KeyError):
            resolve(rows, '')
        with self.assertRaises(ValueError):
            resolve(rows, '_gMalonChildIdleAnim = 0x02000080;')

    def test_clock_metadata_has_no_pose_pointers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'clip.inc.c').write_text('{12, // frameCount\n}, frames, joints, 6,')
            header = sprite_animation_header('clip', 'AnimationHeader clip = {\n#include "clip.inc.c"\n};', root)
            self.assertEqual(header, 'AnimationHeader clip = { { 12 }, NULL, NULL, 0 };')

    def test_wing_pixels_depend_on_source_texture(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('gCircleGlowLTex', 'gCircleGlowSLTex'):
                Image.new('L', (32, 32), 0).save(root / (name + '.i8.png'))
            quad = [(-6, 6, 0), (6, 6, 0), (6, -6, 0), (-6, -6, 0)]
            frames = [[quad] * 4] * 10
            wing = root / 'gFairyWingTex.i8.png'
            Image.new('L', (32, 64), 0).save(wing)
            self.assertFalse(any(build_fairy.fairy_textures(root, frames)[0]))
            Image.new('L', (32, 64), 255).save(wing)
            cels = build_fairy.fairy_textures(root, frames)
            self.assertEqual([len(c) for c in cels], [1024] * 3)
            self.assertTrue(any(cels[0]))
            self.assertEqual(cels[0][0], 0)  # no opaque rectangle


if __name__ == '__main__':
    unittest.main()
