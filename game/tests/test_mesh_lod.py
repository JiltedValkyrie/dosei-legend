"""Per-mesh LOD: bank table generation and runtime integer selection."""
import ctypes
import os
import pathlib
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_room_scene as rooms
import build_sgl_scene as scene
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')


def bank(lods, near_faces=True):
    vertices = [(0,0,0),(100,0,0),(100,0,100),(0,0,100),(0,10,0),(100,10,0),(100,10,100),(0,10,100)]
    faces = [dict(idx=(0,1,2,3),tex_off=0,cull=True,mesh=False),
             dict(idx=(4,5,6,7),tex_off=0,cull=True,mesh=False),
             dict(idx=(0,1,2,3),tex_off=0,cull=True,mesh=False)]
    tiles = {0:dict(index=0,width=8,height=2,pixels=bytes(8),clut=(0,)*16)}
    records = [dict(object=5,indices=[0,1,2,3]), dict(object=9,indices=[4,5,6,7])]
    if near_faces: records.append(dict(object=rooms.LOD0_OBJECT_BASE+5,indices=[0,1,2,3]))
    else: faces = faces[:2]
    return rooms.pack_room(vertices,faces,tiles,records,scene.face_normal,lods)


class LodTable(unittest.TestCase):
    def test_no_lods_is_byte_identical_header(self):
        blob,_,_ = bank({}, near_faces=False)
        self.assertEqual(struct.unpack_from('>8I',blob)[6],0)

    def test_row_maps_both_sets_and_integer_bounds(self):
        lods = {'5':dict(lod0_distance=1500,cull_distance=9000,lod0_faces=1)}
        blob,_,bounds = bank(lods)
        header = struct.unpack_from('>8I',blob)
        self.assertEqual(header[5],3); self.assertEqual(header[6],1)
        row = rooms.LOD_RECORD.unpack(blob[-16:])
        # objects sort 5, 9, 0x10005 -> compact 0, 1, 2
        self.assertEqual(row,(50,0,50,71,1500,9000,0,2))
        self.assertEqual(len(blob),32+8*12+3*32+44+4+3*24+16)

    def test_cull_only_mesh_has_no_lod0(self):
        lods = {'9':dict(lod0_distance=1500,cull_distance=4000,lod0_faces=0)}
        blob,_,_ = bank(lods)
        row = rooms.LOD_RECORD.unpack(blob[-16:])
        self.assertEqual(row[4:],(0,4000,1,rooms.LOD_NONE))

    def test_missing_object_and_bad_range_fail(self):
        with self.assertRaises(ValueError): bank({'77':dict(lod0_distance=1,cull_distance=2)})
        with self.assertRaises(ValueError): bank({'5':dict(lod0_distance=3000,cull_distance=2000)})
        with self.assertRaises(ValueError): bank({'9':dict(lod0_distance=1,cull_distance=2,lod0_faces=4)})

    def test_record_count_guard(self):
        verts=[(i,0,0) for i in range(4)]
        records=[dict(object=i,indices=[0,1,2,3]) for i in range(rooms.LOD_MAX_RECORDS+1)]
        lods={str(i):dict(lod0_distance=0,cull_distance=10) for i in range(rooms.LOD_MAX_RECORDS+1)}
        with self.assertRaises(ValueError):
            rooms.lod_table(verts,records,lods,{i:i for i in range(len(records))})

    def test_layout_validation(self):
        import layout_variants as layouts
        doc = layouts.empty()
        doc['lods'] = {'spot00_room_0/object/26':dict(sha256='0'*64,bundle=None,position=[0,0,0],
                       lod0_distance=1500,cull_distance=9000)}
        layouts.validate(doc)
        for bad in (dict(lod0_distance=9001),dict(cull_distance=0),dict(lod0_distance=1.5),
                    dict(bundle='xyz'),dict(position=[0,0,40000])):
            broken = {k:dict(v,**bad) for k,v in doc['lods'].items()}
            with self.assertRaises(ValueError): layouts.validate(dict(doc,lods=broken))


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class LodSelect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = pathlib.Path(cls.tmp.name)/'lod.dll'
        src = ('#include "mesh_lod.h"\n'
               '__declspec(dllexport) unsigned pick(int cx,int cy,int cz,int r,int n,int f,int lod0,int x,int y,int z){'
               'mesh_lod_t m={{cx,cy,cz},r,n,f,0,lod0?1:MESH_LOD_NONE,{0,0}};return mesh_lod_select(&m,x,y,z);}\n')
        env = dict(os.environ); env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Werror','-I',str(ROOT/'src'),'-x','c','-','-o',str(out)],
                       input=src,text=True,env=env,check=True)
        cls.lib = ctypes.CDLL(str(out))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def pick(self,*a): return self.lib.pick(*a)

    def test_bands(self):
        # radius 100, LOD0 under 1000, cull under 5000 (distance minus radius)
        self.assertEqual(self.pick(0,0,0,100,1000,5000,1,0,0,0),0)
        self.assertEqual(self.pick(0,0,0,100,1000,5000,1,1000,0,0),0)
        self.assertEqual(self.pick(0,0,0,100,1000,5000,1,1200,0,0),1)
        self.assertEqual(self.pick(0,0,0,100,1000,5000,1,5000,0,0),1)
        self.assertEqual(self.pick(0,0,0,100,1000,5000,1,5200,0,0),2)

    def test_no_lod0_never_near(self):
        self.assertEqual(self.pick(0,0,0,100,1000,5000,0,0,0,0),1)

    def test_extreme_coordinates_do_not_overflow(self):
        self.assertEqual(self.pick(-32768,-32768,-32768,32767,32767,32767,1,32767,32767,32767),2)
        self.assertEqual(self.pick(-32768,0,0,32767,0,32767,1,32000,0,0),1)
        self.assertEqual(self.pick(-32768,0,-32768,0,0,32767,0,32767,0,32767),2)
        self.assertEqual(self.pick(0,0,0,0,0,9000,0,100000,-100000,100000),2)
        self.assertEqual(self.pick(0,0,0,65535,65535,65535,1,32767,0,0),0)


if __name__ == '__main__': unittest.main()
