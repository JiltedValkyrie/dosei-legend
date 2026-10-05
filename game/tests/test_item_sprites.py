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
                self.assertLessEqual(h, 48 if name == 'ITMEXP' else self.items.SHEETS[name][3])
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


if __name__ == '__main__':
    unittest.main()
