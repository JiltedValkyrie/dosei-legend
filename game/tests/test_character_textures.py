"""Character budget preserves faces, transparency and VDP1 tile layout."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import character_textures as textures


def bake(face, size):
    return bytes(range(32)) + bytes([0x01, 0x23] * (size * size // 4))


class CharacterTextures(unittest.TestCase):
    def test_body_quarters_pixels(self):
        tile, width, height = textures.bake_character_tile({}, 16, bake)
        self.assertEqual((width, height, len(tile)), (8, 8, 64))

    def test_face_bytes_unchanged(self):
        for size in (8, 16):
            tile, width, height = textures.bake_character_tile({'face_detail': True}, size, bake)
            self.assertEqual((width, height), (size, size))
            self.assertEqual(tile, bake({}, size))

    def test_small_body_repeats_columns_without_losing_transparency(self):
        tile, width, height = textures.bake_character_tile({}, 8, bake)
        self.assertEqual((width, height), (8, 4))
        self.assertEqual(tile[:32], bytes(range(32)))
        self.assertEqual(tile[32:], bytes([0x00, 0x11, 0x22, 0x33] * 4))

    def test_source_material_classification(self):
        names = ['gEyeTex', 'gNoseTex', 'gHeadHairTex', 'gHoodTex', 'object_test_Tex_0400', 'gBodyTex']
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'actor.xml'
            xml.write_text('<Root>' + ''.join(
                f'<Texture Name="{name}" Offset="0x{i * 256:X}"/>'
                for i, name in enumerate(names)) + '</Root>')
            faces = [dict(texture={'address': 0x06000000 + i * 256},
                          texture_segment=6, limb=10) for i in range(len(names))]
            faces += [dict(texture_segment=10, limb=3), dict(texture_segment=4, limb=10)]
            textures.mark_faces(faces, xml, 10, (8, 9, 10))
        self.assertEqual([f['face_detail'] for f in faces],
                         [True, True, False, False, True, False, True, False])


if __name__ == '__main__':
    unittest.main()
