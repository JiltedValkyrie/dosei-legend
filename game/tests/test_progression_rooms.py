import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import asset_names
import build_sgl_scene as sgl

OUT = ROOT / 'build/progression-rooms'


@unittest.skipUnless((OUT / 'room_preflight.json').is_file(), 'run build_progression_rooms.py first')
class BakedProgressionRooms(unittest.TestCase):
    def test_all_source_rooms_have_valid_independent_banks(self):
        report = json.loads((OUT / 'room_preflight.json').read_text())
        self.assertFalse(report['runtime_registered'])
        self.assertEqual(len(report['rooms']), 24)
        identities = set()
        names = set()
        for room in report['rooms']:
            with self.subTest(scene=room['prefix'], room=room['room']):
                self.assertEqual(room['status'], 'baked')
                identity = (room['scene'], room['room'])
                self.assertNotIn(identity, identities)
                identities.add(identity)
                self.assertEqual(room['mesh'], asset_names.room_asset(*identity, 'MSH'))
                self.assertNotIn(room['mesh'], names)
                names.add(room['mesh'])
                blob = (OUT / room['mesh']).read_bytes()
                magic, nv, nf, nt, nb, no, _, _ = struct.unpack_from('>8I', blob)
                self.assertEqual(magic, 0x4B524D31)
                self.assertEqual(len(blob), 32 + nv*12 + nf*32 + nt*44 + ((nf+3)&~3) + no*24)
                self.assertEqual(nb, (OUT / room['pixels']).stat().st_size)
                detail = json.loads((OUT / ('%s_room_%d' % (room['prefix'], room['room'])) /
                                     'texture_manifest.json').read_text())
                self.assertEqual(len(detail['faces']), nf)
                for i in range(nf):
                    indices = struct.unpack_from('>4H', blob, 32 + nv*12 + i*20 + 12)
                    self.assertLess(max(indices), nv)
                    attr = struct.unpack_from('>BB5H', blob, 32 + nv*12 + nf*20 + i*12)
                    self.assertLess(attr[2], nt)
        self.assertIn('S7RA.MSH', names)
        self.assertIn('S7RB.MSH', names)


if __name__ == '__main__':
    unittest.main()
