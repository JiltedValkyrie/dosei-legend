import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from PIL import Image
import room_imports


class RoomImports(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.obj = self.root / 'room.obj'
        self.obj.write_text('v 0 0 0\nv 16 0 0\nv 0 0 16\nf 1 2 3\n')
        self.actor = dict(tiles=[], polygons=0, vertices=0)

    def test_flat_needs_no_uv_and_packs(self):
        from build_room_scene import pack_room
        from build_sgl_scene import face_normal
        v, f, t, m = room_imports.convert(dict(obj=self.obj, uv_mode='flat'), self.actor)
        self.assertEqual(len(f), 1)
        self.assertEqual(t, {})
        self.assertEqual(f[0]['idx'], (0, 1, 2, 2))
        self.assertTrue(f[0]['colour'] & 0x8000)
        blob, pixels, bounds = pack_room(v, f, t, m['faces'], face_normal)
        self.assertEqual(blob[:4], b'KRM1')
        self.assertEqual(pixels, b'')
        self.assertEqual(bounds, [(0, 0, 0, 16, 0, 16)])

    def test_missing_uv_rejected(self):
        atlas = self.root / 'atlas.png'
        Image.new('RGBA', (16, 16), 'green').save(atlas)
        with self.assertRaisesRegex(ValueError, 'Missing UVs'):
            room_imports.convert(dict(obj=self.obj, atlas=atlas), self.actor)

    def test_textured_and_transfer(self):
        atlas = self.root / 'atlas.png'
        Image.new('RGBA', (16, 16), 'green').save(atlas)
        source = self.root / 'source.obj'
        source.write_text('v 0 0 0\nv 16 0 0\nv 0 0 16\n'
                          'vt 0 0\nvt 1 0\nvt 0 1\nf 1/1 2/2 3/3\n')
        keep = room_imports.convert(dict(obj=source, atlas=atlas), self.actor)
        transfer = room_imports.convert(dict(obj=self.obj, atlas=atlas,
            uv_mode='transfer', uv_from=source), self.actor)
        self.assertEqual(keep[:3], transfer[:3])
        self.assertEqual(len(keep[2]), 1)


if __name__ == '__main__':
    unittest.main()
