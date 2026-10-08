"""Opt-in mesh tile density preserves indices, palettes and binary contracts."""
import collections
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import struct
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_hybrid_scene as hybrid
import build_all_scenes as all_scenes
import build_room_scene as rooms
import build_sgl_scene as sgl
import build_opening_banks as opening
import asset_names
import prune_obsolete_room_banks as obsolete


def tile(width=32, height=8):
    # Paired indices make all 16 values, including transparency, survive.
    return dict(index=0, width=width, height=height,
                pixels=bytes(((x // 2) % 16) * 17 for _ in range(height)
                             for x in range(0, width, 2)),
                clut=tuple(0x8000 + i for i in range(16)))


class TextureHalvingTests(unittest.TestCase):
    def test_obsolete_cleanup_keeps_backdrops_mesh_scenes_and_virtual_banks(self):
        scenes = [dict(prefix='image', shape='image', rooms=1),
                  dict(prefix='mesh', shape='mesh', rooms=1)]
        with tempfile.TemporaryDirectory() as tmp:
            folders = [pathlib.Path(tmp) / name for name in ('generated', 'cd')]
            names = ('S0R0.MSH', 'S0R0.TEX', 'S0R0.RGB', 'S0.COL',
                     'S1R0.MSH', 'S1R0.TEX', 'C2R0.MSH', 'C2R0.TEX')
            for folder in folders:
                folder.mkdir()
                for name in names:
                    (folder / name).write_bytes(name.encode())
            removed = obsolete.prune(*folders, scenes)
            self.assertEqual(len(removed), 4)
            for folder in folders:
                self.assertEqual({p.name for p in folder.iterdir()}, set(names) - {'S0R0.MSH', 'S0R0.TEX'})
                for path in folder.iterdir():
                    self.assertEqual(path.read_bytes(), path.name.encode())
            self.assertEqual(obsolete.prune(*folders, scenes), [])

    def test_navi_pool_reuses_already_halved_tiles_and_matching_maps(self):
        vertices = [(-20, 0, 300), (20, 0, 300), (0, 40, 300)]
        faces = [dict(idx=(0, 1, 2, 2), tex_off=0, cull=False, mesh=False)]
        with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='2'):
            tiles, _ = hybrid.halve_texture_tiles({0: tile()})
            verts, bank_faces, bank_tiles = opening.forest_bank(
                [(vertices, faces, tiles)], [(0, 0, 0, 0, 0, 0, 240)])
        self.assertEqual(bank_tiles[0], tiles[0])
        records = [dict(object=0, indices=f['idx']) for f in bank_faces]
        mesh, pixels, _ = rooms.pack_room(verts, bank_faces, bank_tiles, records, sgl.face_normal)
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()):
            folder = pathlib.Path(tmp)
            for bank in range(10):
                for ext, data in [('MSH', mesh), ('TEX', pixels)]:
                    (folder / asset_names.room_asset(asset_names.STORY_BANK_NAVI, bank, ext)).write_bytes(data)
            with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='2'):
                opening.emit_flight_cache(folder)
            self.assertEqual((folder / 'NAVIPOOL.TEX').read_bytes(), pixels)
            for bank in range(10):
                mapping = folder / asset_names.room_asset(asset_names.STORY_BANK_NAVI, bank, 'MAP')
                self.assertEqual(struct.unpack('>I', mapping.read_bytes()), (0,))

    def test_converter_halves_before_cap_and_records_both_steps(self):
        points = [(0, 0, 0, 0, 0, 255, 255, 255, 255),
                  (32, 0, 0, 16, 0, 255, 255, 255, 255),
                  (32, 32, 0, 16, 16, 255, 255, 255, 255),
                  (0, 32, 0, 0, 16, 255, 255, 255, 255)]
        texture = dict(width=16, height=16, address=1, scale=(1, 1),
                       shifts=0, shiftt=0, uls=0, ult=0, cms=0, cmt=0,
                       masks=4, maskt=4, colors=[(x * 16, y * 16, 64, 255)
                                              for y in range(16) for x in range(16)])
        faces = [dict(vertices=[points[i] for i in indices], texture=texture,
                      lighting=False, cull=True, transparent=False,
                      room='test_room_0', prim=(255,) * 4)
                 for indices in ((0, 1, 2), (0, 2, 3))]
        actor = dict(tiles=[(8, 8)], polygons=1, vertices=4)
        with tempfile.TemporaryDirectory() as tmp, \
                mock.patch.object(hybrid, 'load_faces', return_value=faces), \
                contextlib.redirect_stdout(io.StringIO()):
            folder = pathlib.Path(tmp)
            with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='0'):
                original = hybrid.convert(None, {}, actor, folder / 'off', room='test_room_0', layout={})
            with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='2'), \
                    mock.patch.object(hybrid, 'fit_room_pixels', wraps=hybrid.fit_room_pixels) as cap:
                fitted = hybrid.convert(None, {}, actor, folder / 'on', room='test_room_0',
                                        layout={}, room_pixel_limit=8)
                expected, _ = hybrid.halve_texture_tiles(original[3])
                self.assertEqual(cap.call_args.args[0], expected)
            report = json.loads((folder / 'on/texture_manifest.json').read_text())['pixel_budget']
        self.assertEqual(original[1:3], fitted[1:3])
        self.assertEqual(report['before'], hybrid.room_pixel_bytes(original[3]))
        self.assertEqual(report['after'], 8)
        self.assertEqual(report['reductions'][0]['reason'], 'DOSEI_TEX_HALVE')
        self.assertNotIn('reason', report['reductions'][-1])

    def test_quarter_pixels_preserves_every_palette_index(self):
        original = {7: tile()}
        with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='1'):
            fitted, report = hybrid.halve_texture_tiles(original, 'actor')
        self.assertEqual((fitted[7]['width'], fitted[7]['height']), (16, 4))
        self.assertEqual(len(fitted[7]['pixels']), len(original[7]['pixels']) // 4)
        self.assertEqual(fitted[7]['clut'], original[7]['clut'])
        self.assertEqual(fitted[7]['pixels'], bytes(range(1, 256, 34)) * 4)
        self.assertEqual({n for b in fitted[7]['pixels'] for n in (b >> 4, b & 15)}, set(range(16)))
        self.assertEqual(report['reductions'][0]['before'], [32, 8])
        self.assertEqual(original[7]['width'], 32)

    def test_width_floor_rounding_odd_heights_and_alignment(self):
        original = collections.OrderedDict((w, tile(w, 5)) for w in range(8, 505, 8))
        with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='2'):
            fitted, report = hybrid.halve_texture_tiles(original)
        for w, t in fitted.items():
            self.assertEqual(t['width'], max(8, (w + 15) // 16 * 8))
            self.assertEqual(t['height'], 3)
            self.assertEqual(t['width'] % 8, 0)
            self.assertEqual(len(t['pixels']), t['width'] * t['height'] // 2)
        self.assertEqual(report['after'], hybrid.room_pixel_bytes(fitted))
        with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='1'):
            fitted, report = hybrid.halve_texture_tiles({0: tile(8, 1)})
        self.assertEqual(report['reductions'], [])

    def test_off_default_and_mode_two_actor_are_byte_identical(self):
        original = {0: tile()}
        vertices = [(0, 0, 0), (8, 0, 0), (8, 0, 8), (0, 0, 8)]
        faces = [dict(idx=(0, 1, 2, 3), tex_off=0, cull=True, mesh=False)]
        records = [dict(object=0, indices=(0, 1, 2, 3))]
        before = rooms.pack_room(vertices, faces, original, records, sgl.face_normal)
        for mode, kind in ((None, 'room'), ('0', 'room'), ('0', 'actor'), ('2', 'actor')):
            with mock.patch.dict(os.environ, clear=True):
                if mode is not None:
                    os.environ['DOSEI_TEX_HALVE'] = mode
                fitted, report = hybrid.halve_texture_tiles(original, kind)
            self.assertIs(fitted, original)
            self.assertEqual(report['reductions'], [])
            self.assertEqual(rooms.pack_room(vertices, faces, fitted, records, sgl.face_normal), before)

    def test_modes_invalidate_all_scene_cache(self):
        fingerprints = []
        for mode in ('0', '1', '2'):
            with mock.patch.dict(os.environ, DOSEI_TEX_HALVE=mode):
                fingerprints.append(all_scenes.converter_fingerprint())
        self.assertEqual(len(set(fingerprints)), 3)
        with mock.patch.dict(os.environ, DOSEI_TEX_HALVE='bad'):
            with self.assertRaisesRegex(ValueError, 'must be 0, 1 or 2'):
                hybrid.halve_texture_tiles({0: tile()})


if __name__ == '__main__':
    unittest.main()
