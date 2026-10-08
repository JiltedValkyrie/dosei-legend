"""Final staged retail-map admission checks. Run after the complete asset build.

These checks deliberately fail on a partial bake; they do not turn missing maps
or unbuilt files into skips. Host decoding proves data admission, not Saturn
timing, visual acceptance, actor completion, or dungeon progression.
"""
import ctypes
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / 'build/generated'
CD = ROOT / 'build/cd'
OOT = Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')
sys.path[:0] = [str(ROOT / 'tools'), str(ROOT.parent / 'shared/tools')]
import asset_names
import build_all_scenes
import build_kokiri_scene as source
import check_disc_directory

BASE_SCENES = ('link_home', 'spot04', 'kokiri_shop', 'kokiri_home', 'kokiri_home3',
               'kokiri_home4', 'kokiri_home5', 'ydan', 'spot10', 'ydan_boss', 'spot00')


class Triangle(ctypes.Structure):
    _fields_ = [('vertex', (ctypes.c_int16 * 3) * 3), ('normal', ctypes.c_int16 * 3),
                ('minimum', ctypes.c_int16 * 3), ('maximum', ctypes.c_int16 * 3)]


class Mesh(ctypes.Structure):
    _fields_ = [('triangles', ctypes.POINTER(Triangle)), ('triangle_count', ctypes.c_uint32),
                ('info', ctypes.POINTER(ctypes.c_uint16)),
                ('surfaces', ctypes.POINTER(ctypes.c_uint32)), ('surface_count', ctypes.c_uint32),
                ('water', ctypes.c_void_p), ('water_count', ctypes.c_uint32),
                ('cameras', ctypes.c_void_p), ('camera_count', ctypes.c_uint32),
                ('camera_vectors', ctypes.POINTER(ctypes.c_int16)),
                ('camera_vector_count', ctypes.c_uint32)]


class AllRetailMaps(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((GEN / 'scene_table.json').read_text())
        cls.rows = cls.manifest['scenes']
        if len(cls.rows) != 101:
            raise AssertionError('All-map build incomplete: %d/101 retail maps generated' % len(cls.rows))
        # Import only once the generated table is complete; importing this
        # producer during a partial bake could refresh its registration cache.
        cls.plan = importlib.import_module('build_scene_table')
        cls.retail = build_all_scenes.scene_list(OOT, retail_only=True)
        cls.source_by_prefix = {r['prefix']: r for r in cls.retail}
        cls.raw_scenes, cls.source_rooms = {}, {}
        for row in cls.retail:
            prefix = row['prefix']
            segments = source.extract(OOT, prefix=prefix)
            cls.raw_scenes[prefix] = segments[prefix + '_scene']
            cls.source_rooms[prefix] = {
                int(name.rsplit('_', 1)[1]): build_all_scenes.room_shape(data)
                for name, data in segments.items() if name.startswith(prefix + '_room_')}
        cls.header = (GEN / 'scene_table.h').read_text()
        cls.defines = {k: int(v) for k, v in re.findall(
            r'^#\s*define\s+(SCENE_\w+)\s+(\d+)', cls.header, re.M)}

    def test_registration_matches_all_retail_source_ids_and_preserves_first_75(self):
        entries = self.plan.SCENES
        self.assertEqual(len(entries), 101)
        self.assertEqual(len(self.retail), 101)
        self.assertEqual({e['prefix'] for e in entries}, set(self.source_by_prefix))
        self.assertEqual([e['prefix'] for e in entries[:75]],
                         list(BASE_SCENES) + self.plan.LEGACY_GENERIC_ORDER)
        self.assertEqual(len(self.plan.LEGACY_GENERIC_ORDER), 64)
        self.assertEqual([r['prefix'] for r in self.rows], [e['prefix'] for e in entries])
        self.assertEqual(self.defines['SCENE_COUNT'], 101)
        self.assertEqual(self.defines['SCENE_GENERIC_FIRST'], 11)
        for index, (entry, row) in enumerate(zip(entries, self.rows)):
            with self.subTest(prefix=entry['prefix']):
                original = self.source_by_prefix[entry['prefix']]
                self.assertEqual(entry['scene'], original['scene'])
                self.assertEqual(row['index'], index)
                self.assertEqual(self.defines['SCENE_' + entry['prefix'].upper()], index)
                self.assertEqual(entry['rooms'], len(self.source_rooms[entry['prefix']]))
                self.assertEqual(row['rooms'], entry['rooms'])
                self.assertEqual(set(self.source_rooms[entry['prefix']]), set(range(entry['rooms'])))
                if index >= 11:
                    self.assertEqual(row['save_scene'], index)

    def test_disc_table_has_every_original_scene_enum_and_level_select_label(self):
        table = (CD / 'SCENETAB.BIN').read_bytes()
        layout = self.manifest['layout']
        self.assertEqual(layout['entry_bytes'], 26)
        self.assertEqual(layout['entry_offset'] % 4, 0)
        self.assertGreaterEqual(len(table), layout['entry_offset'] + 101 * 26)
        for index, (entry, row) in enumerate(zip(self.plan.SCENES, self.rows)):
            with self.subTest(prefix=entry['prefix']):
                at = layout['name_offset'] + index * 25
                expected = entry['scene'][6:].replace('_', ' ')[:24].encode('ascii').ljust(25, b'\0')
                self.assertEqual(table[at:at + 25], expected)
                record = table[layout['entry_offset'] + index * 26:layout['entry_offset'] + (index + 1) * 26]
                self.assertEqual(record[0], int(entry['shape'] == 'image'))
                self.assertEqual(record[16], entry['rooms'])
                self.assertEqual(struct.unpack_from('>H', record, 18)[0], row['first_spawn'])
                self.assertEqual(record[20], row['spawns'])
                self.assertEqual(record[21], row['save_scene'])
                self.assertEqual(record[24], self.source_by_prefix[entry['prefix']]['id'])
        capacity = int(re.search(r'#define JO_FS_MAX_FILES (\d+)',
                                 (ROOT / 'src/fs_capacity.h').read_text())[1])
        check_disc_directory.check(CD, capacity)

    def test_every_source_room_has_staged_visual_files_and_exact_bank_bounds(self):
        caps = self.plan.RUNTIME_CAPS
        for index, entry in enumerate(self.plan.SCENES):
            for room, source_shape in self.source_rooms[entry['prefix']].items():
                with self.subTest(prefix=entry['prefix'], room=room):
                    self.assertEqual(source_shape == 1, entry['shape'] == 'image')
                    if source_shape == 1:
                        backdrop = CD / asset_names.room_asset(index, room, 'RGB')
                        self.assertEqual(backdrop.stat().st_size, 320 * 240 * 2)
                        continue
                    if entry['prefix'] == 'spot00':
                        # Existing Field chunks have independent per-frame
                        # capacity/coverage tests; their asset is KRM2.
                        path = CD / asset_names.room_asset(index, room, 'STM')
                        self.assertGreater(path.stat().st_size, 32)
                        self.assertEqual(path.read_bytes()[:4], b'KRM2')
                        continue
                    mesh = (CD / asset_names.room_asset(index, room, 'MSH')).read_bytes()
                    pixels = (CD / asset_names.room_asset(index, room, 'TEX')).read_bytes()
                    magic, vertices, polys, tiles, pixel_bytes, objects, lods, flags = struct.unpack_from('>8I', mesh)
                    self.assertEqual(magic, 0x4B524D31)
                    for key, count in zip(('vertices', 'polygons', 'tiles', 'pixel_bytes', 'objects'),
                                          (vertices, polys, tiles, pixel_bytes, objects)):
                        self.assertLessEqual(count, caps[key], key)
                    self.assertEqual(pixel_bytes, len(pixels))
                    self.assertLessEqual(lods, 96)
                    self.assertEqual(len(mesh), 32 + vertices * 12 + polys * 32 + tiles * 44 +
                                     ((polys + 3) & ~3) + objects * 24 + lods * 16)
                    if flags:
                        self.assertEqual((entry['prefix'], room, flags), ('hiral_demo', 0, 1))
                        self.assertEqual((vertices, polys, tiles, pixel_bytes, objects, lods), (0,) * 6)
                    else:
                        self.assertGreater(vertices, 0)
                        self.assertGreater(polys, 0)
                    for i in range(polys):
                        indices = struct.unpack_from('>4H', mesh, 32 + vertices * 12 + i * 20 + 12)
                        self.assertLess(max(indices), vertices)
                        attr = struct.unpack_from('>BB5H', mesh, 32 + vertices * 12 + polys * 20 + i * 12)
                        if attr[6] & 7 < 4:  # textured sprite, not a flat RGB polygon
                            self.assertLess(attr[2], tiles)
                    tile_start = 32 + vertices * 12 + polys * 32
                    for i in range(tiles):
                        width, height, offset, length = struct.unpack_from('>HHII', mesh, tile_start + i * 12)
                        self.assertEqual(width % 8, 0)
                        self.assertGreater(height, 0)
                        self.assertEqual(length, width * height // 2)
                        self.assertLessEqual(offset + length, pixel_bytes)

    def test_all_collision_polygons_decode_and_preserve_complete_source_geometry(self):
        gcc = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            dll = Path(tmp) / ('collision.dll' if os.name == 'nt' else 'collision.so')
            env = dict(os.environ)
            env['PATH'] = str(Path(gcc).parent) + os.pathsep + env.get('PATH', '')
            subprocess.run([gcc, '-shared', '-fPIC', '-O2', '-o', str(dll),
                            str(ROOT.parent / 'shared/lib/collision/kokiri_collision.c')], check=True, env=env)
            lib = ctypes.CDLL(str(dll))
            lib.bg_mesh_bytes.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            lib.bg_mesh_bytes.restype = ctypes.c_uint32
            lib.bg_mesh_decode.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p,
                                           ctypes.c_uint32, ctypes.POINTER(Mesh)]
            lib.bg_mesh_decode.restype = ctypes.c_bool
            lib.bg_scene_set.argtypes = [ctypes.POINTER(Mesh)]
            lib.kokiri_collision_index.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
            lib.kokiri_collision_index.restype = ctypes.c_bool
            source_text = (ROOT / 'src/scene_flow.c').read_text()
            index_kib = int(re.search(r'SCENE_COLLISION_INDEX_BYTES\s+\((\d+) \* 1024\)', source_text)[1])
            for index, row in enumerate(self.rows):
                with self.subTest(prefix=row['prefix']):
                    blob = (CD / asset_names.scene_asset(index, 'COL')).read_bytes()
                    self.assertEqual(blob[:4], b'KBG2')
                    count, surfaces, water, cameras, vectors, reserved = struct.unpack_from('>6H', blob, 4)
                    if row['prefix'] != 'spot00':
                        # The historical summary records source counts; Field
                        # may have more polygons after its approved retopology.
                        self.assertEqual(count, row['triangles'])
                    self.assertLessEqual(count, self.plan.COLLISION_TRIANGLES_MAX)
                    need = lib.bg_mesh_bytes(blob, len(blob))
                    self.assertGreater(need, 0)
                    memory = ctypes.create_string_buffer(need + 16)
                    ctypes.memset(ctypes.addressof(memory) + need, 0xA5, 16)
                    mesh = Mesh()
                    self.assertTrue(lib.bg_mesh_decode(blob, len(blob), memory, need, ctypes.byref(mesh)))
                    self.assertEqual(memory.raw[-16:], bytes([0xA5]) * 16)
                    self.assertEqual(mesh.triangle_count, count)
                    self.assertEqual((mesh.surface_count, mesh.water_count, mesh.camera_count,
                                      mesh.camera_vector_count), (surfaces, water, cameras, vectors))
                    decoded = list(struct.iter_unpack('=18h', ctypes.string_at(mesh.triangles, count * 36)))
                    stored = list(struct.iter_unpack('>18h', blob[16:16 + count * 36]))
                    self.assertEqual(decoded, stored)
                    if row['prefix'] != 'spot00':  # Field's approved local retopology predates this change.
                        original = source.collision_data(self.raw_scenes[row['prefix']])['polys']
                        self.assertEqual(count, len(original))
                        expected = [tuple(n for v in p['vertices'] for n in v) + tuple(p['normal']) +
                                    tuple(min(v[k] for v in p['vertices']) for k in range(3)) +
                                    tuple(max(v[k] for v in p['vertices']) for k in range(3))
                                    for p in original]
                        self.assertEqual(decoded, expected)
                    lib.bg_scene_set(ctypes.byref(mesh))
                    lookup = ctypes.create_string_buffer(index_kib * 1024)
                    self.assertTrue(lib.kokiri_collision_index(lookup, len(lookup)), 'full collision index')

    def test_every_scene_ooc_and_objects_fit_carve_with_bounded_source_pointers(self):
        makefile = (ROOT / 'makefile').read_text()
        base, capacity = (int(re.search(r'^' + name + r'\s*=\s*(0x[0-9A-Fa-f]+)',
                                        makefile, re.M)[1], 16)
                          for name in ('OOT_SCENECOL_ADDR', 'OOT_SCENECOL_MAX_BYTES'))
        scene_header = (ROOT / 'oot-core/include/oot_scene_blob.h').read_text()
        room_limit = int(re.search(r'#define OOT_SCENE_MAX_ROOMS (\d+)', scene_header)[1])
        loader = (ROOT / 'oot-core/src/bridge_actor_pack.cpp').read_text()
        object_limit = int(re.search(r'blob->num_objects > (\d+)', loader)[1])
        self.assertEqual(object_limit, int(re.search(r'loaded_objects\[(\d+)\]', loader)[1]))
        align16 = lambda n: (n + 15) & ~15
        for index, row in enumerate(self.rows):
            with self.subTest(prefix=row['prefix']):
                data = (CD / asset_names.scene_asset(index, 'OOC')).read_bytes()
                self.assertGreaterEqual(len(data), 32)
                col, rooms, layers, lp, objects, nobj, paths, npaths = struct.unpack_from('>8I', data)

                def span(pointer, count, stride, alignment):
                    if not pointer:
                        self.assertEqual(count, 0)
                        return 0
                    self.assertEqual(pointer % alignment, 0)
                    self.assertGreaterEqual(pointer, base)
                    offset = pointer - base
                    self.assertLessEqual(offset, len(data))
                    self.assertLessEqual(count * stride, len(data) - offset)
                    return offset

                self.assertEqual(rooms, row['rooms'])
                self.assertLessEqual(rooms, room_limit)
                self.assertGreater(layers, 0)
                self.assertLessEqual(layers, len(data) // 24)
                self.assertLessEqual(nobj, object_limit)
                object_at = span(objects, nobj, 2, 2)
                layer_at = span(lp, rooms * layers, 24, 4)
                path_at = span(paths, npaths, 24, 4)
                for i in range(rooms * layers):
                    pointer, count = struct.unpack_from('>IH', data, layer_at + i * 24)
                    span(pointer, count, 16, 2)
                for i in range(npaths):
                    pointer, count = struct.unpack_from('>IH', data, path_at + i * 24)
                    if pointer:
                        self.assertGreater(count, 0, 'new OOC must retain complete path-array count')
                    at = span(pointer, count, 8, 4)
                    for j in range(count):
                        points = data[at + j * 8]
                        point_ptr = struct.unpack_from('>I', data, at + j * 8 + 4)[0]
                        span(point_ptr, points, 6, 2)
                co = span(col, 1, 44, 4)
                vertices = struct.unpack_from('>H', data, co + 12)[0]
                vertex_ptr = struct.unpack_from('>I', data, co + 16)[0]
                polys = struct.unpack_from('>H', data, co + 20)[0]
                poly_ptr, surface_ptr, camera_ptr = struct.unpack_from('>3I', data, co + 24)
                waters = struct.unpack_from('>H', data, co + 36)[0]
                water_ptr = struct.unpack_from('>I', data, co + 40)[0]
                staged_col = (CD / asset_names.scene_asset(index, 'COL')).read_bytes()
                self.assertEqual(polys, struct.unpack_from('>H', staged_col, 4)[0])
                span(vertex_ptr, vertices, 6, 2)
                span(poly_ptr, polys, 16, 2)
                span(water_ptr, waters, 16, 2)
                span(surface_ptr, int(bool(polys)), 8, 4)
                span(camera_ptr, int(bool(camera_ptr)), 8, 4)
                used = align16(len(data))
                for i in range(nobj):
                    oid = struct.unpack_from('>H', data, object_at + i * 2)[0]
                    payload = (CD / ('O%03X.OOB' % oid)).read_bytes()
                    self.assertEqual(payload[:4], b'OOB1')
                    used += align16(len(payload))
                self.assertLessEqual(used, capacity)


if __name__ == '__main__':
    unittest.main()
