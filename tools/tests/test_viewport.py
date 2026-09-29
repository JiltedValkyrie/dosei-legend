"""Camera conventions and read-only source decoding regressions."""
import itertools
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'mesh-workshop'))
from viewport_math import Camera, clip_near, contains, project
import viewport_scene as scene


class ViewportTests(unittest.TestCase):
    def test_fly_and_mouse_right_follow_native_handedness(self):
        camera = Camera()
        camera.position = (0, 0, 0)
        camera.pitch = 0
        camera.fly({'d'}, 1)
        self.assertEqual(camera.position, (-700, 0, 0))
        camera.look(20, 0)
        self.assertLess(camera.basis()[0][0], 0)
        camera.fly({'e'}, 1)
        self.assertEqual(camera.position[1], 700)

    def test_frame_fits_every_corner_in_tall_and_wide_views(self):
        for width, height in ((300, 900), (1200, 600)):
            camera = Camera()
            camera.frame(((-500, -100, -300), (500, 200, 300)), width/height)
            for point in itertools.product((-500, 500), (-100, 200), (-300, 300)):
                p = camera.view(point)
                self.assertGreater(p[2], 5)
                x, y = project(p, width, height)
                self.assertTrue(0 <= x <= width and 0 <= y <= height)

    def test_near_plane_clips_crossing_face(self):
        points = clip_near([(-10, 0, -5), (10, 0, 15), (0, 20, 15)])
        self.assertEqual(len(points), 4)
        self.assertTrue(all(p[2] >= 5 for p in points))
        self.assertEqual(clip_near([(0, 0, -1)] * 3), [])
        self.assertTrue(contains([(0, 0), (10, 0), (10, 10), (0, 10)], 5, 5))
        self.assertFalse(contains([(0, 0), (10, 0), (0, 10)], 20, 20))

    def test_actor_flags_rotation_and_unsigned_params_preserved(self):
        data = struct.pack('>BBHI', 1, 1, 0, 0x03000010)
        data += bytes([0x14]) + bytes(7)
        data += struct.pack('>H6hH', 0xA123, -7, 8, 9, -10, 11, -12, 0xFFFF)
        actor = scene.actor_entries(data)[0]
        self.assertEqual((actor['actor_id'], actor['spawn_flags']), (0x123, 10))
        self.assertEqual(actor['rotation'], (-10, 11, -12))
        self.assertEqual(actor['params'], 65535)
        with self.assertRaises(ValueError): scene.actor_entries(data[:-1])

    def test_baked_coordinates_and_corrupt_ranges(self):
        data = struct.pack('>8I', 0x4B524D31, 3, 1, 0, 0, 1, 0, 0)
        data += struct.pack('>9i', 0, -65536, 0, 65536, 0, 0, 0, 0, 65536)
        data += struct.pack('>3i4H', 0, 0, 0, 0, 1, 2, 2)
        data += struct.pack('>BB5H', 0, 0, 0, 0, 31, 0, 4)
        data += bytes(4 + 24)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'room.MSH'
            path.write_bytes(data)
            vertices, faces = scene.read_room(path)
            self.assertEqual(vertices[0], (0, 1, 0))
            self.assertEqual(faces[0]['colour'], (255, 0, 0))
            self.assertEqual(len(faces[0]['points']), 3)
            path.write_bytes(data[:-1])
            with self.assertRaises(ValueError): scene.read_room(path)

    def test_missing_inputs_are_reported_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch.object(scene, 'segments', side_effect=FileNotFoundError('ROM missing')):
                result = scene.load_room('spot04', 1, 0, project=root,
                                         paths={'oot_decomp':root, 'oot_roms':root})
            self.assertEqual(len(result['warnings']), 2)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == '__main__': unittest.main()
