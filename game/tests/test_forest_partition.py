"""Execute the actual renderer preparation body with host-side SGL adapters."""
import ctypes
import os
import pathlib
import random
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class ForestPartition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (ROOT / 'src/kokiri_sgl.c').read_text()
        body = text[text.index('void                kokiri_scene_draw(void)'):]
        body = body[:body.index('void                kokiri_link_draw')]
        adapters = (ROOT / 'tests/fixtures/forest_partition_host.c').read_text()
        fog_init = text[text.index('static void forest_fog_init(void)'):]
        fog_init = fog_init[:fog_init.index('/* Pixel blobs')]
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        output = pathlib.Path(cls.tmp.name) / 'forest.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-x', 'c', '-', '-o', str(output)],
                       input=adapters + '\n' + fog_init + body, text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(output))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_changing_visibility_keeps_every_record_paired(self):
        self.lib.reset_scene()
        rng = random.Random(17)
        for _ in range(100):
            depths = [rng.choice((-20, 0, 100, 1300, 1311)) for _ in range(8)]
            for i, depth in enumerate(depths):
                self.lib.set_depth(i, depth)
            self.lib.kokiri_scene_draw()
            count = self.lib.visible_count()
            ids = [self.lib.polygon_id(i) for i in range(8)]
            self.assertEqual(set(ids[:count]), {i for i,d in enumerate(depths) if 0<=d<=1310})
            self.assertEqual(sorted(ids), list(range(8)))
            self.assertTrue(all(self.lib.paired(i) for i in range(8)))

    def test_floor_walls_and_overhead_keep_original_world_sort(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
            self.lib.set_floor_footprint(i)
        self.lib.set_surface(0, 0, -65536)  # supporting floor
        self.lib.set_surface(1, -50, -60000)  # slope below feet
        self.lib.set_surface(2, 0, 0)  # wall
        self.lib.set_surface(3, 50, -65536)  # bridge overhead
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.assertEqual(self.lib.sort_for_id(1), 0x67)
        self.assertEqual(self.lib.sort_for_id(2), 0x67)
        self.assertEqual(self.lib.sort_for_id(3), 0x67)

    def test_link_height_does_not_reorder_world_faces(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
            self.lib.set_floor_footprint(i)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_link_feet(-10)
        self.lib.kokiri_scene_draw()
        self.assertTrue(self.lib.scene_reused())
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_link_feet(40)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_link_active(0)
        self.lib.kokiri_scene_draw()
        self.assertTrue(self.lib.scene_reused())
        self.assertEqual(self.lib.sort_for_id(0), 0x67)

    def test_floor_crossing_above_feet_keeps_centre_sort(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
            self.lib.set_floor_footprint(i)
        self.lib.set_corner_height(2, 1)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_corner_height(2, 0)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)

    def test_ground_keeps_centre_sort_as_link_crosses_footprint_edge(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
            self.lib.set_floor_footprint(i)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_link_x(11)
        self.lib.kokiri_scene_draw()
        self.assertTrue(self.lib.scene_reused())
        self.assertEqual(self.lib.sort_for_id(0), 0x67)
        self.lib.set_link_x(10)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.sort_for_id(0), 0x67)

    def test_unchanged_view_never_reorders_records(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, -100 if i%2 else 100)
        self.lib.kokiri_scene_draw()
        before = [self.lib.polygon_id(i) for i in range(8)]
        for _ in range(5):
            self.lib.kokiri_scene_draw()
            self.assertEqual([self.lib.polygon_id(i) for i in range(8)], before)

    def test_camera_change_invalidates_prepared_list(self):
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.visible_count(), 8)
        self.lib.set_camera_z(200)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.visible_count(), 0)
        self.lib.set_camera_z(0)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.visible_count(), 8)

    def test_fog_fast_path_matches_original_quantization(self):
        self.lib.reset_scene()
        for depth in range(0, 1311):
            self.lib.set_depth(0, depth)
            self.lib.kokiri_scene_draw()
            original = max(0, min(16, int((depth-655)*16/655)))
            self.assertEqual(self.lib.fog_level(0), original)

    def test_invisible_tile_keeps_palette_until_reentry(self):
        self.lib.reset_scene()
        self.lib.set_depth(0, 1000)
        self.lib.kokiri_scene_draw()
        level = self.lib.fog_level(0)
        self.lib.set_depth(0, -10)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.fog_level(0), level)
        self.lib.set_depth(0, 100)
        self.lib.kokiri_scene_draw()
        self.assertEqual(self.lib.fog_level(0), 0)

    def test_channel_lookup_matches_signed_rounding(self):
        self.lib.reset_scene()
        for target, color in enumerate((27, 19)):
            for amount in range(17):
                for channel in range(32):
                    self.assertEqual(self.lib.fog_color(target, amount, channel),
                                     channel + int((color-channel)*amount/16))

    def test_moving_route_rebuilds_every_frame(self):
        """A moving camera must not reuse the prepared list.

        The 928 us scene figure in the capture came from a STATIONARY camera
        reusing the prepared list, so it says nothing about the cull loop's
        cost while moving. This pins the precondition for measuring it: along
        a moving route the list is rebuilt every frame, so the partition work
        is actually being done.
        """
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
        for step in range(20):
            self.lib.set_camera_z(step * 37)
            self.lib.kokiri_scene_draw()
            self.assertFalse(self.lib.scene_reused(),
                             'moving camera reused the list at step %d' % step)

    def test_stationary_camera_reuses_and_reports_it(self):
        """And the reuse must be visible, so stale timers are not misread."""
        self.lib.reset_scene()
        for i in range(8):
            self.lib.set_depth(i, 100)
        self.lib.set_camera_z(500)
        self.lib.kokiri_scene_draw()
        self.assertFalse(self.lib.scene_reused(), 'first build is not a reuse')
        for _ in range(5):
            self.lib.kokiri_scene_draw()
            self.assertTrue(self.lib.scene_reused(),
                            'stationary camera should reuse the prepared list')
