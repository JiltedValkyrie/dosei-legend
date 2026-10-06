"""Visual-only Field subdivisions retain planes, coverage and source UVs."""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import build_quads as quads
import build_hybrid_scene as hybrid
from field_ground_grid import extend, CELL
from field_retopo import area_poly


def group(points, source=1):
    vertices = [(x, x/8 + z/16, z, x/32, z/32, 255, 255, 255, 255) for x, z in points]
    face = dict(vertices=vertices, texture=None, lighting=False, prim=(255,)*4,
                room='spot00_room_0', object=17, cull=True, transparent=False)
    return dict(points=vertices, tri=face, source=[source], texture=None,
                kind=quads.BAKE, size=quads.span(vertices))


class GroundGrid(unittest.TestCase):
    def test_sloped_triangle_coverage_winding_plane_and_uv(self):
        for outline in ([(0, 5100), (CELL*3, 5100), (0, 5100+CELL*3)],
                        [(0, 5100+CELL*3), (CELL*3, 5100), (0, 5100)]):
            original = group(outline)
            extend([original], set())
            kids = original['retopo_drop']
            self.assertTrue(any(len(k['points']) == 4 for k in kids))
            self.assertAlmostEqual(sum(area_poly([(p[0],p[2]) for p in k['points']]) for k in kids),
                                   area_poly(outline), delta=1)
            for kid in kids:
                self.assertEqual(kid['source'], [1])
                for x,y,z,u,v,*_ in kid['points']:
                    self.assertLessEqual(abs(y-x/8-z/16), .5)
                    self.assertAlmostEqual(u, x/32)
                    self.assertAlmostEqual(v, z/32)
                self.assertEqual(math.copysign(1, area_poly([(p[0],p[2]) for p in kid['points']])),
                                 math.copysign(1, area_poly(outline)))

    def test_landmarks_existing_patch_and_small_faces_preserved(self):
        a = group([(0,0),(3000,0),(0,3000)], 2)
        b = group([(0,0),(3000,0),(0,3000)], 3)
        b['retopo_drop'] = ['accepted']
        c = group([(0,0),(100,0),(0,100)], 4)
        extend([a,b,c], {2})
        self.assertNotIn('retopo_drop', a)
        self.assertEqual(b['retopo_drop'], ['accepted'])
        self.assertNotIn('retopo_drop', c)

    @unittest.skipUnless(hybrid.OOT_DEFAULT.is_dir(), 'source decomp required')
    def test_actual_field_panels_preserve_area_and_source_planes(self):
        from build_field_chunks import LANDMARKS
        faces = hybrid.load_faces(hybrid.OOT_DEFAULT, prefix='spot00')
        groups = quads.build(faces)
        extend(groups, {i for _, _, ids in LANDMARKS for i in ids})
        checked = 0
        for parent in groups:
            if 'retopo_drop' not in parent:
                continue
            checked += 1
            normal = quads.normal(parent['points'])
            magnitude = math.sqrt(sum(n*n for n in normal))
            original = abs(area_poly([(p[0],p[2]) for p in parent['points']]))
            points = parent['points']
            perimeter = sum(math.hypot(a[0]-b[0], a[2]-b[2])
                            for a,b in zip(points, points[1:]+points[:1]))
            area = 0
            for kid in parent['retopo_drop']:
                area += abs(area_poly([(p[0],p[2]) for p in kid['points']]))
                for vertex in kid['points']:
                    error = abs(sum(normal[k]*(vertex[k]-parent['points'][0][k]) for k in range(3))) / magnitude
                    self.assertLessEqual(error, .87, parent['source'])
            # Integer XZ rounding moves a boundary by at most sqrt(.5).
            self.assertAlmostEqual(area, original, delta=perimeter*math.sqrt(.5)+4,
                                   msg=str(parent['source']))
        self.assertGreater(checked, 100)


if __name__ == '__main__':
    unittest.main()
