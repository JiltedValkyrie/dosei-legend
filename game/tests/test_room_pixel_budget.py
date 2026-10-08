"""Generic room density changes must retain every face and exact KRM1 limits."""
import contextlib
import io
import json
import pathlib
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_sgl_scene as sgl
import build_quads as quads
from vdp1_budget import FOREST_ACTOR_BYTES


def tile(index, width, height):
    return dict(index=index, width=width, height=height,
                pixels=bytes((0x10, 0x32, 0x54, 0x76)) * (width * height // 8),
                clut=tuple(range(16)))


class RoomPixelBudgetTests(unittest.TestCase):
    def test_crop_padding_counts_in_admission_and_packed_bytes(self):
        # Raw payload is 16 B, but independently aligned crops consume 24 B.
        original = {0: tile(0, 8, 1), 1: tile(1, 8, 3)}
        self.assertEqual(hybrid.room_pixel_bytes(original), 24)
        fitted, report = hybrid.fit_room_pixels(original, 16)
        vertices = [(0, 0, 0), (8, 0, 0), (8, 0, 8), (0, 0, 8)]
        faces = [dict(idx=(0, 1, 2, 3), tex_off=i, cull=True, mesh=False)
                 for i in original]
        records = [dict(object=1, indices=(0, 1, 2, 3)) for _ in faces]
        blob, pixels, _ = rooms.pack_room(vertices, faces, fitted, records, sgl.face_normal)
        self.assertEqual(len(pixels), 16)
        self.assertEqual(struct.unpack_from('>I', blob, 16)[0], len(pixels))
        self.assertEqual(report['after'], len(pixels))
        self.assertEqual(fitted[0], original[0])
        self.assertEqual(original[1]['height'], 3)

    def test_shared_ids_palette_transparency_and_geometry_survive(self):
        original = {0: tile(0, 16, 4)}
        fitted, report = hybrid.fit_room_pixels(original, 16)
        self.assertEqual(tuple(fitted), (0,))
        self.assertEqual(fitted[0]['index'], original[0]['index'])
        self.assertEqual(fitted[0]['clut'], original[0]['clut'])
        self.assertIn(0, [n for b in fitted[0]['pixels'] for n in (b >> 4, b & 15)])
        vertices = [(0, 0, 0), (8, 0, 0), (8, 0, 8), (0, 0, 8)]
        faces = [dict(idx=(0, 1, 2, 3), tex_off=0, cull=True, mesh=mesh)
                 for mesh in (False, True)]
        records = [dict(object=7, indices=(0, 1, 2, 3)) for _ in faces]
        before = rooms.pack_room(vertices, faces, original, records, sgl.face_normal)
        after = rooms.pack_room(vertices, faces, fitted, records, sgl.face_normal)
        geometry_end = 32 + 4 * 12 + 2 * 32
        self.assertEqual(before[0][32:geometry_end], after[0][32:geometry_end])
        self.assertEqual(before[2], after[2])
        self.assertEqual(report['before'], 32)
        self.assertEqual(report['after'], 16)

    def test_exact_fit_keeps_bytes_and_palette_unmodified(self):
        original = {0: tile(0, 24, 5), 1: tile(1, 8, 1)}
        fitted, report = hybrid.fit_room_pixels(original, 72)
        self.assertEqual(fitted, original)
        self.assertEqual(report['reductions'], [])
        self.assertEqual(report['after'], 72)

    def test_impossible_minimum_rejects_instead_of_omitting_tiles(self):
        with self.assertRaisesRegex(ValueError, 'minimum 16 exceeds limit 15'):
            hybrid.fit_room_pixels({0: tile(0, 8, 1), 1: tile(1, 8, 1)}, 15)

    def test_converter_applies_cap_without_changing_geometry_or_actor_reserve(self):
        points = [(0, 0, 0, 0, 0, 255, 255, 255, 255),
                  (32, 0, 0, 16, 0, 255, 255, 255, 255),
                  (32, 32, 0, 16, 16, 255, 255, 255, 255),
                  (0, 32, 0, 0, 16, 255, 255, 255, 255)]
        texture = dict(width=16, height=16, address=1, scale=(1, 1),
                       shifts=0, shiftt=0, uls=0, ult=0, cms=0, cmt=0,
                       masks=4, maskt=4,
                       colors=[(x * 16, y * 16, 64, 255)
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
            original = hybrid.convert(None, {}, actor, folder / 'original',
                                      room='test_room_0', layout={})
            capped = hybrid.convert(None, {}, actor, folder / 'capped',
                                    room='test_room_0', layout={}, room_pixel_limit=16)
            report = json.loads((folder / 'capped/texture_manifest.json').read_text())
        self.assertEqual(original[1:3], capped[1:3])
        self.assertGreater(hybrid.room_pixel_bytes(original[3]), 16)
        self.assertLessEqual(hybrid.room_pixel_bytes(capped[3]), 16)
        self.assertEqual(report['pixel_budget']['after'], 16)
        self.assertTrue(any(part['bytes'] == FOREST_ACTOR_BYTES
                            for part in report['budget']))


class RoomGeometryBudgetTests(unittest.TestCase):
    def floor(self):
        points = [(0, 0, 0, 0, 0, 255, 255, 255, 255),
                  (512, 0, 0, 32, 0, 255, 255, 255, 255),
                  (512, 0, 512, 32, 32, 255, 255, 255, 255),
                  (0, 0, 512, 0, 32, 255, 255, 255, 255)]
        return dict(kind=quads.BAKE, points=points, size=512, source=[3, 4],
                    tri=dict(transparent=False))

    def test_optional_floor_split_respects_independent_face_and_vertex_limits(self):
        original = self.floor()
        self.assertEqual(hybrid.bounded_room_ground([original], 4, 4), [original])
        self.assertEqual(hybrid.bounded_room_ground([original], 9, 1), [original])
        parts = hybrid.bounded_room_ground([original], 9, 4)
        self.assertEqual(len(parts), 4)
        area = 0
        for part in parts:
            self.assertEqual(part['source'], original['source'])
            p = part['points']
            area += abs(sum(p[i][0] * p[(i + 1) % 4][2] -
                            p[(i + 1) % 4][0] * p[i][2] for i in range(4))) / 2
            for point in p:
                self.assertEqual(point[3], point[0] / 16)
                self.assertEqual(point[4], point[2] / 16)
        self.assertEqual(area, 512 * 512)

    def test_tall_shared_quads_count_real_emitted_points_before_floor_refinement(self):
        original = self.floor()
        wall = dict(kind=quads.DIRECT,
                    points=[(p[0], p[2], 1024) + p[3:] for p in original['points']],
                    size=512, source=[5, 6], tri=dict(transparent=False))
        parts = hybrid.bounded_room_ground([original, wall], 20, 3)
        self.assertEqual(parts, [original, wall])
        self.assertEqual(len(hybrid.shared_room_pieces(wall)), 2)

    def test_refinement_respects_caps_without_removing_original_faces(self):
        original = self.floor()
        actor = dict(vertices=0, polygons=0)
        self.assertEqual(hybrid.refine_room_ground([original], [], actor,
                                                  vertex_limit=4, face_limit=4), [original])
        self.assertEqual(hybrid.refine_room_ground([original], [], actor,
                                                  vertex_limit=9, face_limit=1), [original])
        self.assertEqual(len(hybrid.refine_room_ground([original], [], actor,
                                                       vertex_limit=9, face_limit=4)), 4)

    def test_unfit_source_geometry_fails_instead_of_silently_omitting_it(self):
        with self.assertRaisesRegex(ValueError, 'before optional refinement'):
            hybrid.bounded_room_ground([self.floor()], 3, 4)


if __name__ == '__main__':
    unittest.main()
