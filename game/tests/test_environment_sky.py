"""Source-clock boundaries, real integer gradient, and floor-only colour baking."""
import ctypes as C
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_environment_sky as sky
from environment_source import sky_schedule

OOT = Path(os.environ.get('OOT_DECOMP', 'D:/Workspace-Claude/game-decomps/n64/oot'))
GCC = shutil.which('gcc') or ('C:/msys64/mingw64/bin/gcc.exe' if Path('C:/msys64/mingw64/bin/gcc.exe').exists() else None)


def room(polygons, tiles):
    """polygons: (vertices, normal, tile); tiles: (palette, packed pixels)."""
    points, faces = [], []
    for corners, normal, tile in polygons:
        indices = list(range(len(points), len(points) + len(corners)))
        points.extend(corners)
        if len(indices) == 3:
            indices.append(indices[-1])
        faces.append((normal, indices, tile))
    pixels = b''.join(t[1] for t in tiles)
    data = bytearray(struct.pack('>8I', 0x4B524D31, len(points), len(faces), len(tiles), len(pixels), 0, 0, 0))
    for point in points:
        data += struct.pack('>3i', *(c * 65536 for c in point))
    for normal, indices, tile in faces:
        data += struct.pack('>3i4H', *normal, *indices)
    for normal, indices, tile in faces:
        data += struct.pack('>BB5H', 0, 0x67, tile, 0x88, 0, 0, 2)
    offset = 0
    for palette, raw in tiles:
        data += struct.pack('>HHII', 2, 2, offset, len(raw))
        offset += len(raw)
    for palette, raw in tiles:
        data += struct.pack('>16H', *palette)
    return bytes(data), pixels


RED, GREEN, BLUE = 0x801F, 0x83E0, 0xFC00
PALETTE = (0, RED, GREEN, BLUE) + (0,) * 12
FLOOR = [(0, 0, 0), (16, 0, 0), (16, 0, 16), (0, 0, 16)]
UP = (0, -65536, 0)


class FloorBake(unittest.TestCase):
    def test_area_not_face_count_and_transparent_pixels(self):
        # One large green floor beats ten red 1-unit triangles. A huge blue
        # ceiling and wall must not influence floor colour.
        faces = [(FLOOR, UP, 0)]
        faces += [([(0, 0, 0), (1, 0, 0), (0, 0, 1)], UP, 1)] * 10
        huge = [(x * 100, y, z * 100) for x, y, z in FLOOR]
        faces += [(huge, (0, 65536, 0), 2), (huge, (65536, 0, 0), 2)]
        data, pixels = room(faces, [(PALETTE, b'\x02\x22'), (PALETTE, b'\x11\x11'), (PALETTE, b'\x33\x33')])
        hist, count, area = sky.mesh_histogram(data, pixels)
        self.assertEqual(max(hist, key=hist.get), GREEN)
        self.assertNotIn(0x8000, hist)
        self.assertNotIn(BLUE, hist)
        self.assertEqual(count, 11)
        self.assertEqual(area, 261)
        self.assertEqual(hist[GREEN], 256 * 2 * .75)

    def test_subdivision_preserves_colour_weight(self):
        original = room([(FLOOR, UP, 0)], [(PALETTE, b'\x12\x22')])
        subdivided = room([(FLOOR[:3], UP, 0), ([FLOOR[0], FLOOR[2], FLOOR[3]], UP, 0)],
                          [(PALETTE, b'\x12\x22')])
        a, _, area_a = sky.mesh_histogram(*original)
        b, _, area_b = sky.mesh_histogram(*subdivided)
        self.assertEqual(a, b)
        self.assertEqual(area_a, area_b)

    def test_scenes_keep_separate_colours_and_missing_is_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            for index, pixel in ((0, 0x11), (1, 0x22)):
                data, pixels = room([(FLOOR, UP, 0)], [(PALETTE, bytes([pixel] * 2))])
                (folder / ('S%dR0.MSH' % index)).write_bytes(data)
                (folder / ('S%dR0.TEX' % index)).write_bytes(pixels)
            for index, expected in ((0, RED), (1, GREEN), (2, sky.GROUND_FALLBACK)):
                colour, report = sky.scene_ground(folder, dict(index=index, rooms=1, prefix='test'))
                self.assertEqual(colour, expected)
                self.assertEqual(report['fallback'], index == 2)
                self.assertEqual(report['missing_rooms'], [0] if index == 2 else [])

    def test_bad_bank_and_pixels_fail(self):
        data, pixels = room([(FLOOR, UP, 0)], [(PALETTE, b'\x22\x22')])
        for bad_data, bad_pixels in ((data[:20], pixels), (data, pixels[:1]), (data[:-1], pixels)):
            with self.assertRaises(ValueError):
                sky.mesh_histogram(bad_data, bad_pixels)

    def test_streamed_ground_skips_far_and_replacement_lod_duplicates(self):
        # Original full-cell and object LOD1 green geometry contribute. Far
        # red cells and close-up red replacements overlap them and must not.
        tiles = [(PALETTE, b'\x22\x22'), (PALETTE, b'\x11\x11')]
        metadata_bytes = 64 + 2 * (16 + 32) + 4 * sky.PIECE.size
        blocks, pieces = bytearray(), bytearray()
        for kind, tile in ((0, 0), (1, 1), (2, 0), (3, 1)):
            mesh, pixels = room([(FLOOR, UP, tile)], tiles)
            block = mesh[32:32 + 4 * 12 + 32]
            pieces += sky.PIECE.pack(0, 0, 0, 16, 0, 16, 0, 65535,
                                     4, 1, 0, kind, kind // 2, 0,
                                     metadata_bytes + len(blocks), 0)
            blocks += block
        pool_at = metadata_bytes + len(blocks)
        header = struct.pack('>16I', 0x4B524D32, 1, 4, 2, 4, 0, 2,
                             pool_at + 4, 4, 1, 4, 0, pool_at, 2, 9000, 0)
        tile_table = b''.join(struct.pack('>HHIIHH', 2, 2, i * 2, 2, 0, 0) for i in range(2))
        palettes = struct.pack('>32H', *(PALETTE * 2))
        histogram, faces, area = sky.field_histogram(header + tile_table + palettes + pieces + blocks + pixels)
        self.assertEqual(set(histogram), {GREEN})
        self.assertEqual(faces, 2)
        self.assertEqual(area, 512)

    def test_source_top_image_ignores_transparent_pixels_and_reports_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'gDaySkybox5Tex.test.png'
            image = Image.new('RGBA', (2, 1))
            image.putdata([(255, 0, 0, 255), (0, 0, 255, 0)])
            image.save(path)
            colours, report = sky.sky_colours(folder)
            self.assertEqual(colours[1], RED)
            self.assertFalse(report[1]['fallback'])
            self.assertEqual(sum(r['fallback'] for r in report), 9)

    @unittest.skipUnless((ROOT / 'build/cd/SAR0.STM').exists(), 'staged Field required')
    def test_real_streamed_field_contains_ground(self):
        hist, count, area = sky.field_histogram((ROOT / 'build/cd/SAR0.STM').read_bytes())
        self.assertGreater(count, 100)
        self.assertGreater(area, 1000000)
        self.assertGreater(sum(hist.values()), 1000000)
        self.assertTrue(all(c & 0x8000 for c in hist))


@unittest.skipUnless(GCC and (OOT / 'src/code/z_kankyo.c').exists(), 'host GCC and source decomp required')
class RuntimeGradient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        p = Path(cls.tmp.name)
        (p / 'scenes.json').write_text(json.dumps(dict(scenes=[dict(index=0, prefix='spot04', rooms=1), dict(index=1, prefix='spot00', rooms=1)])))
        sky.bake(OOT, p, p / 'scenes.json', p)
        (p / 'test.c').write_text(r'''
#include "environment_sky.h"
unsigned int select_sky(unsigned int time, unsigned int config) {
    unsigned int a,b,w;
    environment_sky_select(time,config,&a,&b,&w);
    return (a<<24)|(b<<16)|w;
}
unsigned short top(unsigned int t,unsigned int c){return environment_sky_top(t,c);}
unsigned short theme(unsigned int t,unsigned int m){return environment_sky_theme_top(t,m);}
unsigned short row(unsigned int y,unsigned short a,unsigned short b){return environment_sky_gradient(y,a,b);}
unsigned short horizon(unsigned int y,unsigned short a,unsigned short b){return environment_field_horizon(y,a,b);}
unsigned short haze(unsigned int s,unsigned int t){return environment_haze_colour(s,t);}
unsigned short map_colour(unsigned int s,unsigned int t){return environment_map_colour(s,t);}
unsigned short mix(unsigned short a,unsigned short b,unsigned int w){return environment_sky_mix(a,b,w);}
unsigned int table_bytes(void){return sizeof(environment_sky_schedule)+sizeof(environment_sky_sources)+sizeof(environment_sky_ground)+sizeof(environment_map_fog);}
''')
        env = dict(os.environ, PATH=str(Path(GCC).parent) + os.pathsep + os.environ.get('PATH', ''))
        library = p / ('test.dll' if os.name == 'nt' else 'test.so')
        subprocess.run([GCC, '-shared', '-O2', '-Wall', '-Werror', '-I' + str(ROOT / 'src'),
                        '-I' + str(p), str(p / 'test.c'), '-o', str(library)], check=True, env=env)
        cls.lib = C.CDLL(str(library))
        cls.lib.select_sky.argtypes = [C.c_uint, C.c_uint]
        cls.lib.select_sky.restype = C.c_uint
        cls.lib.row.argtypes = [C.c_uint, C.c_ushort, C.c_ushort]
        cls.lib.row.restype = C.c_ushort
        cls.lib.horizon.argtypes = [C.c_uint, C.c_ushort, C.c_ushort]
        cls.lib.horizon.restype = C.c_ushort
        cls.lib.top.argtypes = [C.c_uint, C.c_uint]
        cls.lib.top.restype = C.c_ushort
        cls.lib.theme.argtypes = [C.c_uint, C.c_uint]
        cls.lib.theme.restype = C.c_ushort
        cls.lib.mix.argtypes = [C.c_ushort, C.c_ushort, C.c_uint]
        cls.lib.mix.restype = C.c_ushort

    @classmethod
    def tearDownClass(cls):
        cls.lib = None
        cls.tmp.cleanup()

    def test_map_tint_uses_source_kokiri_palette_and_darkens_at_night(self):
        expected = [(120,80,80), (200,200,150), (150,130,60), (40,50,80)]
        for time, rgb in zip((16384,32768,49152,0), expected):
            self.assertEqual(self.lib.map_colour(0,time), sky.rgb555(rgb))
        self.assertNotEqual(self.lib.map_colour(0,32768), self.lib.map_colour(1,32768))
        self.assertLess(sum(sky.rgb888(self.lib.haze(0,0))),
                        sum(sky.rgb888(self.lib.haze(0,32768))))
        self.assertEqual(self.lib.map_colour(0,65536), self.lib.map_colour(0,0))

    def test_all_source_interval_boundaries_and_midpoints(self):
        for config, entries in enumerate(sky_schedule(OOT)):
            for start, end, change, first, second in entries:
                for time in (start, (start + end) // 2, end - 1):
                    packed = self.lib.select_sky(time, config)
                    a, b, weight = packed >> 24, (packed >> 16) & 255, packed & 65535
                    self.assertEqual((a, b), (8, 9) if config == 3 else (first, second))
                    if change:
                        self.assertLessEqual(abs(weight / 255 - (time - start) / (end - start)), 1 / 255)
                    elif config == 3:
                        self.assertEqual(weight, 0)
                    self.assertLessEqual(weight, 255)
        self.assertEqual(self.lib.select_sky(65535, 0) >> 16, 0x0303)
        self.assertEqual(self.lib.select_sky(65536, 0), self.lib.select_sky(0, 0))
        self.assertEqual(self.lib.select_sky(12345, 99), self.lib.select_sky(12345, 0))

    def test_lower_half_uses_ground_and_upper_is_monotonic(self):
        self.assertEqual(self.lib.row(0, BLUE, GREEN), BLUE)
        colours = [self.lib.row(y, BLUE, GREEN) for y in range(240)]
        self.assertTrue(all(c == GREEN for c in colours[120:]))
        greens = [(c >> 5) & 31 for c in colours]
        blues = [(c >> 10) & 31 for c in colours]
        self.assertEqual(greens, sorted(greens))
        self.assertEqual(blues, sorted(blues, reverse=True))
        self.assertEqual(self.lib.row(0xFFFFFFFF, BLUE, GREEN), GREEN)
        self.assertEqual(self.lib.mix(RED, BLUE, 0xFFFFFFFF), BLUE)

    def test_field_horizon_preserves_sky_and_foreground_with_dark_middle(self):
        for y in range(72):
            self.assertEqual(self.lib.horizon(y, BLUE, GREEN), self.lib.row(y, BLUE, GREEN))
        for y in range(160, 240):
            self.assertEqual(self.lib.horizon(y, BLUE, GREEN), GREEN)
        for y in range(96, 108):
            colour = self.lib.horizon(y, BLUE, GREEN)
            self.assertTrue(colour & 0x8000)
            self.assertLess((colour >> 5) & 31, 10)
        # Black night/fade stays black; the veil cannot invent light.
        for y in range(240):
            self.assertEqual(self.lib.horizon(y, 0x8000, 0x8000), 0x8000)

    def test_source_day_night_weather_differ_and_tables_small(self):
        noon, midnight = 32768, 0
        day, night, cloud = self.lib.top(noon, 0), self.lib.top(midnight, 0), self.lib.top(noon, 1)
        self.assertNotEqual(day, night)
        self.assertNotEqual(day, cloud)
        self.assertLess(sum(sky.rgb888(night)), sum(sky.rgb888(day)))
        self.assertEqual(self.lib.table_bytes(), 4 * 9 * 8 + 10 * 2 + 2 * 10)

    def test_source_static_themes_and_room_disabled_sky(self):
        self.assertEqual(self.lib.theme(32768, 1), self.lib.top(32768, 0))
        self.assertEqual(self.lib.theme(32768, 0x101), self.lib.top(32768, 1))
        self.assertEqual(self.lib.theme(0, 3), self.lib.theme(32768, 3))
        self.assertEqual(self.lib.theme(32768, 5), self.lib.top(32768, 3))
        for identity in (0, 29, 7):
            self.assertEqual(self.lib.theme(32768, identity), 0x8000)
        self.assertEqual(self.lib.theme(32768, 0x10001), 0x8000)


if __name__ == '__main__':
    unittest.main()
