import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import build_quads as q
import build_hybrid_scene as hybrid
from vdp1_budget import Budget, COMMAND_RESERVE, TEXTURE_BASE, VDP1_END, tile_bytes


def texture(**kwargs):
    return dict(dict(width=16, height=16, address=1, scale=(1,1),
                     shifts=0, shiftt=0, uls=0, ult=0, cms=0, cmt=0,
                     masks=4, maskt=4, colors=[(255,255,255,255)]*256), **kwargs)


def point(x, y, s, t):
    return (x,y,0,s,t,0,0,127,255)


def face(points, **kwargs):
    return dict(dict(vertices=points, texture=texture(), lighting=True,
                     cull=True, transparent=False, room='test', prim=(255,)*4), **kwargs)


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.points = [point(0,0,0,0), point(32,0,32,0),
                       point(32,16,32,16), point(0,16,0,16)]
        a,b,c,d = self.points
        self.faces = [face([a,b,c]),face([a,c,d])]

    def test_join_preserves_normal_and_sources(self):
        groups = q.build(self.faces)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['source'], [0,1])
        self.assertEqual(q.normal(groups[0]['points']), q.normal(self.points))
        self.assertEqual(groups[0]['kind'], q.SPLIT)

    def test_split_includes_uvs_and_exact_edges(self):
        pieces = q.subdivide(q.build(self.faces)[0])
        self.assertEqual(len(pieces), 2)
        self.assertEqual(pieces[0][1], pieces[1][0])
        self.assertEqual(pieces[0][2], pieces[1][3])
        self.assertEqual(pieces[0][1][3], 16)

    def test_transposed_uv_split_uses_correct_axis(self):
        points = [point(0,0,0,0),point(16,0,0,16),
                  point(16,32,32,16),point(0,32,32,0)]
        pieces = q.subdivide(dict(points=points,repeat=(2,1)))
        self.assertEqual(len(pieces),2)
        self.assertEqual(pieces[0][2][4],16)
        self.assertEqual(pieces[0][2][3],16)

    def test_sampler_shift_changes_repeat_count(self):
        self.assertEqual(q.classify(self.points,texture(shifts=1))[0],q.DIRECT)

    def test_clamped_repetition_is_baked(self):
        self.assertEqual(q.classify(self.points,texture(cms=2))[0],q.BAKE)

    def test_cull_and_room_boundaries_do_not_join(self):
        for key, value in (('cull',False),('transparent',True),('room','other')):
            changed = [self.faces[0],dict(self.faces[1], **{key:value})]
            self.assertEqual(len(q.build(changed)),2)

    def test_bent_pair_does_not_join(self):
        a,c,d = self.faces[1]['vertices']
        self.faces[1]['vertices'] = [a,c,(d[0],d[1],20)+d[3:]]
        self.assertEqual(len(q.build(self.faces)),2)

    def test_negative_normals_remain_signed_when_interpolated(self):
        self.assertEqual(hybrid.shade((0,0,0,0,0,-127,0,0,255),True),(.65,)*3)

    def test_shared_tile_does_not_repeat_first_texel_at_last_column(self):
        group = q.build(self.faces)[0]
        group = dict(group, points=q.subdivide(group)[0])
        group['texture'] = texture(colors=[(x*16,0,0,255) for y in range(16) for x in range(16)])
        clut, data = hybrid.render_tile(group,16,16,True)
        self.assertNotEqual(clut[data[0] >> 4], clut[data[7] & 15])

    def test_budget_counts_generator_and_commands_once(self):
        budget = Budget()
        budget.add('example',((16,16) for _ in range(3)),3,9)
        self.assertEqual(budget.tiles,3)
        self.assertEqual(budget.texture_bytes,3*tile_bytes(16,16))
        self.assertEqual(budget.vram_limit,VDP1_END-TEXTURE_BASE)
        self.assertGreaterEqual(TEXTURE_BASE,COMMAND_RESERVE)
        self.assertLessEqual(VDP1_END,512*1024)

    def test_ground_subdivision_preserves_winding_and_source_uv(self):
        group = q.build(self.faces)[0]
        group['kind'] = q.BAKE
        parts = hybrid.split_ground(group)
        self.assertEqual(len(parts),4)
        for part in parts:
            self.assertGreater(q.normal(part['points'])[2],0)
            for p in part['points']:
                self.assertAlmostEqual(p[0],p[3])
                self.assertAlmostEqual(p[1],p[4])
            self.assertEqual(part['source'],[0,1])

    def test_flat_link_container_uses_actual_small_tile_dimensions(self):
        import tempfile
        import build_link_model as link
        import build_sgl_scene as sgl
        tri = face(self.points[:3],texture=texture(width=1,height=1,colors=[(80,160,40,255)]))
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp)/'LINK.BIN'
            link.write_model([tri,tri],path)
            data,head,_,faces = sgl.read_scene(path)
            tiles = sgl.collect_tiles(data,head,faces)
            self.assertEqual(len(tiles),1)
            self.assertEqual((faces[0]['width'],faces[0]['height']),(8,2))
            self.assertEqual(len(next(iter(tiles.values()))['pixels']),8)

    def test_budget_rejects_overflow(self):
        budget = Budget()
        budget.add('bad',[(128,128)]*100,2601,2501)
        self.assertEqual(len(budget.failures()),3)


if __name__ == '__main__':
    unittest.main()
