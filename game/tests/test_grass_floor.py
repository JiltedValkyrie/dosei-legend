"""BUG-021: authored foliage must not become the pickup builder's floor."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import build_actors as actors

OOT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
ROM = OOT / 'baseroms/ntsc-1.2'


@unittest.skipUnless(ROM.is_dir(), 'local source ROM required')
class GrassFloor(unittest.TestCase):
    def test_source_entity_ignore_excludes_grass_from_pickup_floors(self):
        scene = actors.source.extract(OOT, ROM)['spot04_scene']
        raw = actors.source.collision_triangles(scene)
        solid = actors.entity_floor_triangles(scene)
        for x, z, old, ground in [(60, -430, 28, 1),
                                  (-480, 190, 28, 1),
                                  (-570, 1720, 144, 120)]:
            self.assertAlmostEqual(actors.floor_under(raw, x, z, 200), old, delta=1)
            self.assertAlmostEqual(actors.floor_under(solid, x, z, 200), ground, delta=1)
        # The retired ground-pickup spots are En_Item00 rupee spots; they
        # still sit on real floor, not on the grass tops.
        for x, y, z in ((-537, 1, 194), (35, 1, -418)):
            self.assertEqual(actors.floor_under(solid, x, z, y), 1)


if __name__ == '__main__':
    unittest.main()
