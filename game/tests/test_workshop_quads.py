import hashlib
import json
import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'tools'))
import build_quads as quads
from workshop_quads import preferred_pairs


class WorkshopQuadsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = pathlib.Path(self.temp.name)
        self.source = self.root / 'source.bin'
        self.source.write_bytes(b'source geometry')
        (self.root / 'source.json').write_text(json.dumps(
            {'sha256': hashlib.sha256(self.source.read_bytes()).hexdigest()}))
        self.obj = self.root / 'mesh.obj'
        self.obj.write_text('v 0 0 0\nv 32 0 0\nv 32 32 0\nv 0 32 0\n'
                            'vt 0 0\nvt 1 0\nvt 1 1\nvt 0 1\n'
                            'usemtl flags_2\nf 1/1 2/2 3/3 4/4\n')
        points = [(x,y,0,x,y,255,255,255,255)
                  for x,y in ((0,0),(32,0),(32,32),(0,32))]
        tex = dict(width=32,height=32,scale=(1,1),shifts=0,shiftt=0,
                   uls=0,ult=0,cms=0,cmt=0)
        self.faces = [dict(vertices=[points[i] for i in ids], texture=tex,
                           lighting=False,prim=(255,)*4,cull=True,
                           transparent=False,room='test')
                      for ids in ((0,1,2),(0,2,3))]

    def test_uses_quad_topology_and_preserves_source_uvs(self):
        pairs, report = preferred_pairs(self.obj,self.faces,self.source)
        self.assertEqual(pairs,[(0,1)])
        group, = quads.build(self.faces,pairs)
        self.assertEqual(group['source'],[0,1])
        self.assertEqual(len(group['points']),4)
        self.assertEqual(report['accepted_pairs'],1)

    def test_material_boundary_stays_separate(self):
        self.faces[1]['prim'] = (100,100,100,255)
        pairs, report = preferred_pairs(self.obj,self.faces,self.source)
        self.assertEqual(pairs,[])
        self.assertEqual(report['material_or_uv_rejected'],1)
        self.assertEqual(len(quads.build(self.faces,pairs)),2)

    def test_moved_geometry_rejected_to_preserve_collision(self):
        self.obj.write_text(self.obj.read_text().replace('v 32 0 0','v 33 0 0'))
        with self.assertRaisesRegex(ValueError,'unchanged source positions'):
            preferred_pairs(self.obj,self.faces,self.source)

    def test_wrong_source_rejected(self):
        self.source.write_bytes(b'other scene')
        with self.assertRaisesRegex(ValueError,'source hash'):
            preferred_pairs(self.obj,self.faces,self.source)
