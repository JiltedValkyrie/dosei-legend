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

SCENE = ROOT / 'levels/kokiri/assets/static/FOREST.BIN'

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
        """__jo_sprite_def has JO_MAX_SPRITE entries and reserves index 0.

        Every mesh shares that table, so the limit must cover their combined
        tile count -- not just the scene's. Overrunning it aborts into Jo's
        error handler during load, which is how a Link texture change that
        added 26 tiles took the whole build down.
        """
        makefile = (ROOT / 'makefile').read_text()
        match = re.search(r'^JO_MAX_SPRITE\s*=\s*(\d+)', makefile, re.M)
        self.assertIsNotNone(match, 'makefile must pin JO_MAX_SPRITE')
        total = len(self.tiles)
        model = ROOT / 'build/generated' / 'LINK.BIN'
        if model.is_file():
            data, head, _, faces = conv.read_scene(model)
            total += len(conv.collect_tiles(data, head, faces))
        self.assertGreaterEqual(int(match.group(1)), total + 1,
                                'JO_MAX_SPRITE must cover all meshes (%d tiles)'
                                % total)

    def test_cull_and_mesh_flags_are_decoded(self):
        self.assertEqual(sum(f['cull'] for f in self.faces), 1937)
        self.assertEqual(sum(f['mesh'] for f in self.faces), 89)
        for i, face in enumerate(self.faces):
            flags = struct.unpack_from(conv.FACE, self.data,
                                       self.head['face_off'] + i * 20)[-1]
            self.assertEqual(face['cull'], bool(flags & 2))
            self.assertEqual(face['mesh'], bool(flags & 1))


@unittest.skipUnless((ROOT / 'build/generated' / 'kokiri_scene.c').is_file(),
                     'generated tables not built')
class GeneratedOutputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gen = ROOT / 'build/generated'
        cls.scene_c = (gen / 'kokiri_scene.c').read_text()
        cls.header = (gen / 'kokiri_scene.h').read_text()
        cls.pixels = (gen / 'kokiri_pixels.bin').read_bytes()

    def _define(self, name):
        match = re.search(r'#\s*define\s+%s\s+(\d+)' % name, self.header)
        self.assertIsNotNone(match, name)
        return int(match.group(1))

    def test_counts_agree_between_header_and_tables(self):
        self.assertEqual(self.scene_c.count('toFIXED('), self._define('KOKIRI_VERTEX_COUNT') * 3)
        self.assertEqual(self.scene_c.count('ATTRIBUTE('), self._define('KOKIRI_POLYGON_COUNT'))
        self.assertLessEqual(self._define('KOKIRI_VERTEX_COUNT'), 2500)
        self.assertLessEqual(self._define('KOKIRI_POLYGON_COUNT'), 2600)

    def test_pixel_blob_length_matches_header(self):
        self.assertEqual(len(self.pixels), self._define('KOKIRI_PIXEL_BYTES'))

    def test_attributes_use_four_bit_lookup_tables(self):
        """The source CLUTs live in VDP1 VRAM, not CRAM colour banks."""
        for line in self.scene_c.splitlines():
            if 'ATTRIBUTE(' not in line:
                continue
            self.assertIn('CL16Look', line)
            self.assertIn('UsePalette', line)
            self.assertNotIn('CL16Bnk', line)
            self.assertNotIn('CL256Bnk', line)

    def test_near_clipping_is_left_to_sgl(self):
        self.assertIn('UseNearClip', self.scene_c)

    def test_render_policy_matches_source_flags(self):
        _, _, _, faces = conv.read_scene(SCENE)
        manifest = ROOT / 'build/generated/texture_manifest.json'
        if manifest.is_file():
            import json
            faces = json.loads(manifest.read_text())['faces']
        attrs = [line for line in self.scene_c.splitlines() if 'ATTRIBUTE(' in line]
        self.assertEqual(len(attrs), len(faces))
        for face, line in zip(faces, attrs):
            self.assertIn('Single_Plane' if face['cull'] else 'Dual_Plane', line)
            self.assertEqual('MESHon' in line, face['mesh'])
            self.assertIn('ECdis', line)
            self.assertNotIn('CL_Trans', line)

    def test_normals_are_unit_length_and_perpendicular(self):
        _, _, verts, faces = conv.read_scene(SCENE)
        baked = [(x, -y, z) for x, y, z in verts]
        for face in faces:
            normal = conv.face_normal(baked, face['idx'])
            self.assertAlmostEqual(sum(n*n for n in normal) ** .5, 65536, delta=1)
            a, b, c = [baked[i] for i in face['idx'][:3]]
            for endpoint in (b, c):
                edge = [q-p for p, q in zip(a, endpoint)]
                self.assertLessEqual(abs(sum(n*e for n, e in zip(normal, edge))),
                                     sum(abs(e) for e in edge))

    def test_staged_texture_matches_generated_blob(self):
        staged = ROOT / 'build/cd' / 'KOKIRI.TEX'
        if not staged.is_file():
            self.skipTest('cd/KOKIRI.TEX not staged')
        self.assertEqual(staged.read_bytes(), self.pixels)


if __name__ == '__main__':
    unittest.main()
