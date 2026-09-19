"""Read shipped binary banks, including ATTR policy and exact blob boundaries."""
import json
import pathlib
import struct
import unittest

GEN = pathlib.Path(__file__).resolve().parents[1] / 'build/generated'


@unittest.skipUnless((GEN / 'rooms_manifest.json').is_file(), 'room banks not built')
class RoomBankPolicy(unittest.TestCase):
    def test_all_banks_match_source_policy_and_lengths(self):
        for room in json.loads((GEN / 'rooms_manifest.json').read_text())['rooms']:
            with self.subTest(room=room['id']):
                mesh = (GEN / ('R%d.MSH' % room['id'])).read_bytes()
                tex = (GEN / ('R%d.TEX' % room['id'])).read_bytes()
                magic, nv, nf, nt, np, no, _, _ = struct.unpack_from('>8I', mesh)
                self.assertEqual(magic, 0x4b524d31)
                self.assertEqual((nv, nf, nt, np, no), tuple(room[k] for k in
                    ('vertices', 'polygons', 'tiles', 'pixel_bytes', 'objects')))
                self.assertEqual(len(tex), np)
                self.assertEqual(len(mesh), 32 + nv*12 + nf*20 + nf*12 +
                                 nt*12 + nt*32 + (nf+3)//4*4 + no*24)
                faces = json.loads((GEN / ('room%d' % room['id']) /
                                    'texture_manifest.json').read_text())['faces']
                self.assertEqual(len(faces), nf)
                attr = 32 + nv*12 + nf*20
                for i, face in enumerate(faces):
                    flag, sort, tile, mode, col, gst, direction = struct.unpack_from(
                        '>BB5H', mesh, attr+i*12)
                    self.assertEqual(flag, 0 if face['cull'] else 1)
                    self.assertEqual(bool(mode & 0x100), face['mesh'])
                    self.assertEqual(mode & ~0x100, 0x88)  # CL16Look + ECdis
                    self.assertEqual(sort, 0x67)  # SORT_CEN, palette, near clip
                    self.assertEqual(direction, 2)
                    self.assertLess(tile, nt)
                end = 0
                for i in range(nt):
                    width, height, offset, length = struct.unpack_from(
                        '>HHII', mesh, attr+nf*12+i*12)
                    self.assertEqual(length, width*height//2)
                    self.assertEqual(offset, end)
                    end = offset + (length+7)//8*8
                self.assertEqual(end, len(tex))
