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
            faces += [dict(texture_segment=10, limb=10), dict(texture_segment=4, limb=10)]
            textures.mark_faces(faces, xml, 10, (8, 9, 10))
        self.assertEqual([f['face_detail'] for f in faces],
                         [True, True, False, False, True, False, True, False])
        self.assertEqual([textures.keep_texture(f) for f in faces],
                         [True, True, True, False, True, False, True, True])

    def test_full_texture_cannot_restore_body_art(self):
        self.assertFalse(textures.keep_texture({'full_texture': True, 'limb': 10}))

    def test_stale_face_texture_binding_on_body_is_flat(self):
        with tempfile.TemporaryDirectory() as tmp:
            xml = Path(tmp) / 'actor.xml'
            xml.write_text('<Root><Texture Name="gEyeTex" Offset="0x0"/></Root>')
            faces = [dict(limb=3, texture_segment=8),
                     dict(limb=3, texture_segment=6, texture={'address': 0x06000000})]
            textures.mark_faces(faces, xml, 10, (8, 9))
        self.assertTrue(all(not textures.keep_texture(f) for f in faces))

    def test_writer_flattens_body_and_keeps_hair_face_and_props(self):
        import build_link_model as model
        import struct
        from unittest.mock import patch
        vertices = [(0, 0, 0, 0, 0, 255, 255, 255, 255),
                    (10, 0, 0, 0, 0, 255, 255, 255, 255),
                    (0, 10, 0, 0, 0, 255, 255, 255, 255)]
        for detail, character, expected in [({}, True, 0x102),
                ({'face_detail': True}, True, 0x210),
                ({'hair_detail': True}, True, 0x108), ({}, False, 0x210)]:
            face = dict(vertices=vertices, texture=None, lighting=False,
                        transparent=False, cull=True, limb=0, full_texture=True, **detail)
            with tempfile.TemporaryDirectory() as tmp, patch.object(model.scene_tool, 'bake', bake):
                path = Path(tmp) / 'model.bin'
                model.write_model([face], path, character=character)
                data = path.read_bytes()
                offset = struct.unpack_from('>I', data, 20)[0]
                self.assertEqual(struct.unpack_from('>H', data, offset + 16)[0], expected)


if __name__ == '__main__':
    unittest.main()
