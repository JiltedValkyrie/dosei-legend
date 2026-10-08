"""Item/projectile SPR1 sheets from build_item_sprites.py (needs decomp + ROM)."""
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OOT = Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')


def valid(s):
    """src/npc_sprite.c npc_sprite_valid."""
    if len(s) < 0x34 or s[:4] != b'SPR1':
        return False
    w, h, dirs, poses, ticks = struct.unpack_from('>5H', s, 4)
    if not w or w > 256 or w & 7 or not h or h > 255 or not poses or poses > 256:
        return False
    if not ticks or dirs != 5 or not struct.unpack_from('>H', s, 16)[0]:
        return False
    base = (0x34 + 2 * ticks + 3) & ~3
    if base + w * h // 2 * poses * 5 != len(s):
        return False
    return all(t < poses for t in struct.unpack_from('>%dH' % ticks, s, 0x34))


def cel(s, pose, d):
    w, h, _, _, ticks = struct.unpack_from('>5H', s, 4)
    size = w * h // 2
    base = (0x34 + 2 * ticks + 3) & ~3
    return s[base + (pose * 5 + d) * size: base + (pose * 5 + d + 1) * size]


@unittest.skipUnless((OOT / 'assets/xml/objects/gameplay_keep.xml').exists()
                     and any((OOT / 'baseroms/ntsc-1.2').glob('*.z64')), 'decomp/ROM missing')
class ItemSprites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import build_item_sprites as items
        cls.items = items
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.manifest = items.build(OOT, None, t, preview_dir=t, manifest=t / 'm.json')
        cls.out = t

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_sheets(self):
        for name in self.items.NAMES:
            with self.subTest(name=name):
                s = (self.out / (name + '.SPR')).read_bytes()
                self.assertTrue(valid(s))
                w, h, _, poses, ticks = struct.unpack_from('>5H', s, 4)
                entry = self.manifest[name]
                self.assertEqual((entry['w'], entry['h'], entry['poses']), (w, h, poses))
                # Cap from the baker's table (hero gear is 2x linear).
                self.assertLessEqual(h, 48 if name == 'ITMEXP' else
                                     self.items.AIM_SIZE if name == 'ITMAIM' else self.items.SHEETS[name][3])
                if name in self.items.ANCHORS:
                    self.assertIn('hand' if name not in ('ITMIRB', 'ITMHOB') else 'leg', entry['anchor'])
                if name == 'ITMEXP':
                    self.assertTrue(4 <= poses <= 8)
                    self.assertEqual(ticks, poses)
                    self.assertEqual(struct.unpack_from('>%dH' % ticks, s, 0x34), tuple(range(poses)))
                    for p in range(poses):
                        self.assertTrue(any(cel(s, p, 0)))
                        self.assertTrue(all(cel(s, p, d) == cel(s, p, 0) for d in range(5)))
                elif entry['pitch_bands']:
                    self.assertEqual((poses, ticks), (5, 5))
                    self.assertEqual(struct.unpack_from('>5H', s, 0x34), (0, 1, 2, 3, 4))
                    # Pitch 0 seen front-on is end-on (arrow tip, chain); side cel must show it.
                    self.assertTrue(any(cel(s, 2, 0)) or any(cel(s, 2, 2)))
                    self.assertTrue(any(cel(s, 2, 2)))
                else:
                    self.assertEqual(poses, 1)
                if name == 'ITMBGS':
                    self.assertGreater(entry['blade_length'], 10)
                    self.assertTrue(any(cel(s, 0, 0)))

    def test_aim_tools_share_one_bounded_cel_and_keep_distinct_source_shapes(self):
        s = (self.out / 'ITMAIM.SPR').read_bytes()
        entry = self.manifest['ITMAIM']
        self.assertEqual(len(s), 10296)
        self.assertEqual(self.items.vram_bytes(entry), 2080)
        self.assertEqual(entry['screen_atlas'][:3], ['slingshot', 'bow', 'hookshot'])
        self.assertEqual(len(set(cel(s, 0, i) for i in range(3))), 3)
        for i in range(3):
            self.assertTrue(any(cel(s, 0, i)))
        for i in (3, 4):
            self.assertFalse(any(cel(s, 0, i)))


class ThickenArrow(unittest.TestCase):
    def test_one_texel_shaft_grows_without_changing_size_or_clut(self):
        import build_item_sprites as items
        w, h = 8, 4
        cels = bytearray(w * h // 2 * 5)
        cels[1 * w // 2 + 1] = 0x30          # one texel, index 3, row 1 x 2
        head = struct.pack('>4s5HhHh', b'SPR1', w, h, 5, 1, 1, 0, 256, 0)
        head += struct.pack('>16H', *range(16)) + struct.pack('>H', 0) + bytes(2)
        with tempfile.TemporaryDirectory() as t:
            dest = Path(t) / 'A.SPR'
            dest.write_bytes(head + cels)
            items.thicken_sprite(dest, 1)
            out = dest.read_bytes()
        self.assertEqual(len(out), len(head + cels))
        self.assertEqual(out[:len(head)], head)
        self.assertTrue(valid(out))
        px = [b for v in cel(out, 0, 0) for b in (v >> 4, v & 15)]
        self.assertEqual(sorted(i for i, v in enumerate(px) if v), [2, 9, 10, 11, 18])
        self.assertEqual({v for v in px if v}, {3})


if __name__ == '__main__':
    unittest.main()
