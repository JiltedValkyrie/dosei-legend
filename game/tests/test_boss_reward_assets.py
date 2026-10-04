import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from build_boss_rewards import WarpLists


class WarpMatrices(unittest.TestCase):
    def test_load_owns_transform_and_mixed_ring_triangle(self):
        w=WarpLists(b'',b'',top_scale=2,top_y=69)
        v=(10,0,20,0,0,255,255,255,255)
        w.matrix(0xDA380003,0x0A000000);w.load_vertex(0,v)
        w.matrix(0xDA380003,0x09000000);w.load_vertex(1,v)
        w.load_vertex(2,(30,0,40)+v[3:])
        w.triangle(0x000204,True)
        self.assertEqual(w.faces[0]['vertex_limbs'],[0,1,1])
        self.assertEqual(w.cache[0][:3],(10,0,20))
        self.assertEqual(w.cache[1][:3],(20,69,40))
        w.matrix(0xDA380003,0x0A000000);w.load_vertex(1,v)
        self.assertEqual(w.vertex_limbs[1],0)
        self.assertEqual(w.cache[1][:3],(10,0,20))

    def test_unknown_matrix_and_vertex_without_owner_rejected(self):
        w=WarpLists(b'',b'')
        with self.assertRaises(ValueError):w.load_vertex(0,(0,)*9)
        for word,address in ((0xDA380003,0x09000040),(0xDA380001,0x09000000),(0xDA380003,0x0D000000)):
            with self.assertRaises(ValueError):w.matrix(word,address)

if __name__=='__main__':unittest.main()
