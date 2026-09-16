"""Guards for the FOREST.BIN -> SGL conversion used by the Jo viewer.

These are host tests over the generated tables. They do not exercise SGL,
VDP1 or the SH-2, so a pass here says the data is well formed -- not that the
viewer renders correctly in Kronos or on hardware.
"""

import pathlib
import re
import struct
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

import build_sgl_scene as conv  # noqa: E402

SCENE = ROOT.parent / 'title-screen' / 'cd' / 'FOREST.BIN'

# Counts the handoff records for US 1.2 geometry.
EXPECTED_VERTICES = 1268
EXPECTED_POLYGONS = 2060
EXPECTED_COLLISION = 1692

# VDP1 texture area, from ../../joengine/jo_engine/jo/sega_saturn.h.
VDP1_USER_AREA_SIZE = 0x71D38


@unittest.skipUnless(SCENE.is_file(), '%s not present' % SCENE)
class ConversionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.head, cls.verts, cls.faces = conv.read_scene(SCENE)
        cls.tiles = conv.collect_tiles(cls.data, cls.head, cls.faces)

    def test_header_matches_documented_scene(self):
        self.assertEqual(self.head['version'], 2)
        self.assertEqual(self.head['nverts'], EXPECTED_VERTICES)
        self.assertEqual(self.head['ntris'], EXPECTED_POLYGONS)
        self.assertEqual(self.head['ncollision'], EXPECTED_COLLISION)
        self.assertEqual(self.head['total'], SCENE.stat().st_size)

    def test_vertices_are_shared_not_expanded(self):
        """The whole point of the SGL PDATA layout: one shared POINT table."""
        self.assertEqual(len(self.verts), EXPECTED_VERTICES)
        self.assertLess(len(self.verts), len(self.faces) * 4)

    def test_every_face_repeats_its_third_corner(self):
        """SGL draws a triangle as a quad whose last two corners coincide."""
        for i, face in enumerate(self.faces):
            v0, v1, v2, v3 = face['idx']
            self.assertEqual(v2, v3, 'face %d' % i)
            self.assertEqual(len({v0, v1, v2}), 3, 'face %d degenerate' % i)

    def test_vertex_indices_are_in_range(self):
        for i, face in enumerate(self.faces):
            for idx in face['idx']:
                self.assertLess(idx, len(self.verts), 'face %d' % i)

    def test_tile_sizes_are_supported(self):
        for off, tile in self.tiles.items():
            self.assertIn((tile['width'], tile['height']), {(16, 16), (32, 32)},
                          'tile at %d' % off)
            self.assertEqual(len(tile['pixels']),
                             tile['width'] * tile['height'] // 2)

    def test_texture_payload_fits_vdp1_user_area(self):
        pixels = sum(len(t['pixels']) for t in self.tiles.values())
        cluts = len(self.tiles) * 32
        self.assertLessEqual(pixels + cluts, VDP1_USER_AREA_SIZE)

    def test_tile_count_fits_configured_sprite_table(self):
        """__jo_sprite_def has JO_MAX_SPRITE entries and reserves index 0."""
        makefile = (ROOT / 'makefile').read_text()
        match = re.search(r'^JO_MAX_SPRITE\s*=\s*(\d+)', makefile, re.M)
        self.assertIsNotNone(match, 'makefile must pin JO_MAX_SPRITE')
        self.assertGreaterEqual(int(match.group(1)), len(self.tiles) + 1)

    def test_transparent_and_two_sided_flags_are_decoded(self):
        two_sided = sum(1 for f in self.faces if f['two_sided'])
        transparent = sum(1 for f in self.faces if f['transparent'])
        self.assertEqual(two_sided, 1937)
        self.assertEqual(transparent, 89)


@unittest.skipUnless((ROOT / 'generated' / 'kokiri_scene.c').is_file(),
                     'generated tables not built')
class GeneratedOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen = ROOT / 'generated'
        cls.scene_c = (gen / 'kokiri_scene.c').read_text()
        cls.header = (gen / 'kokiri_scene.h').read_text()
        cls.pixels = (gen / 'kokiri_pixels.bin').read_bytes()

    def _define(self, name):
        match = re.search(r'#\s*define\s+%s\s+(\d+)' % name, self.header)
        self.assertIsNotNone(match, name)
        return int(match.group(1))

    def test_counts_agree_between_header_and_tables(self):
        self.assertEqual(self._define('KOKIRI_VERTEX_COUNT'), EXPECTED_VERTICES)
        self.assertEqual(self._define('KOKIRI_POLYGON_COUNT'), EXPECTED_POLYGONS)
        self.assertEqual(self.scene_c.count('toFIXED('), EXPECTED_VERTICES * 3)
        self.assertEqual(self.scene_c.count('ATTRIBUTE('), EXPECTED_POLYGONS)

    def test_pixel_blob_length_matches_header(self):
        self.assertEqual(len(self.pixels), self._define('KOKIRI_PIXEL_BYTES'))

    def test_attributes_use_four_bit_colour_bank_with_palette(self):
        """4bpp tiles need CL16Bnk, and colour-bank modes need UsePalette."""
        for line in self.scene_c.splitlines():
            if 'ATTRIBUTE(' not in line:
                continue
            self.assertIn('CL16Bnk', line)
            self.assertIn('UsePalette', line)
            self.assertNotIn('CL256Bnk', line)

    def test_near_clipping_is_left_to_sgl(self):
        self.assertIn('UseNearClip', self.scene_c)

    def test_staged_texture_matches_generated_blob(self):
        staged = ROOT / 'cd' / 'KOKIRI.TEX'
        if not staged.is_file():
            self.skipTest('cd/KOKIRI.TEX not staged')
        self.assertEqual(staged.read_bytes(), self.pixels)


if __name__ == '__main__':
    unittest.main()
