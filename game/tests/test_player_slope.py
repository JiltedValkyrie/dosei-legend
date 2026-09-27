"""Integer slope action and source fall-impact thresholds."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest
import test_player_bg as bg
class Slope(C.Structure):
    _fields_=[('active',C.c_bool),('face_up',C.c_bool),('speed',C.c_int32),
              ('push',C.c_int32),('yaw',C.c_uint16),('push_yaw',C.c_uint16)]

@unittest.skipUnless(bg.GCC.is_file(),'host compiler required')
class PlayerSlope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll=pathlib.Path(cls.tmp.name)/'slope.dll'
        root=bg.ROOT
        env=dict(os.environ)
        env['PATH']=str(bg.GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(bg.GCC),'-shared','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(root/'src'),'-I'+str(root.parent/'shared/lib/collision'),
            '-I'+str(root.parent/'shared/lib/camera'),str(root/'src/player_slope.c'),
            str(root.parent/'shared/lib/collision/kokiri_collision.c'),
            str(root/'tests/fixtures/traversal_host.c'),'-o',str(dll),'-lm'],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.player_slope_update.argtypes=[C.POINTER(Slope),C.POINTER(bg.Hit),
            C.c_uint16,C.c_int32,C.POINTER(C.c_uint16)]
        cls.lib.player_slope_ground.argtypes=[C.POINTER(bg.Vec)]
        cls.lib.player_slope_ground.restype=C.c_bool
        cls.lib.bg_scene_set.argtypes=[C.POINTER(bg.Mesh)]
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.s=Slope()
        self.floor=bg.Hit()
        self.floor.normal[:]=(0,13107,9830)
        self.floor.data1=1<<4
        self.facing=C.c_uint16(0)
    def step(self,yaw=0,speed=1408,floor=True):
        self.lib.player_slope_update(C.byref(self.s),C.byref(self.floor) if floor else None,
            yaw,speed,C.byref(self.facing))
    def test_downhill_slides_and_caps_speed(self):
        self.step()
        self.assertTrue(self.s.active)
        self.assertGreater(self.s.speed,1408)
        for _ in range(60): self.step()
        self.assertAlmostEqual(self.s.speed,2048,delta=1)
        self.floor.normal[:]=(0,8192,14189)
        for _ in range(60): self.step()
        self.assertEqual(self.s.speed,2560)
    def test_uphill_force_and_entry_boundary(self):
        self.step(yaw=0x8000)
        self.assertFalse(self.s.active)
        self.assertEqual(self.s.push,205)
        self.assertEqual(self.s.push_yaw,0)
        self.s=Slope(); self.step(yaw=0x3E80)
        self.assertTrue(self.s.active)
        self.s=Slope(); self.step(yaw=0x3E81)
        self.assertFalse(self.s.active)
    def test_uphill_facing_pose_and_flat_exit(self):
        self.facing.value=0x8000
        self.step()
        self.assertTrue(self.s.face_up)
        self.assertEqual(self.facing.value,0x8000)
        self.floor.normal[:]=(0,16384,0);self.floor.data1=0
        for _ in range(8): self.step()
        self.assertFalse(self.s.active)
        self.assertEqual(self.s.speed,0)
    def test_airborne_clears_slide_and_force(self):
        self.step();self.step(floor=False)
        self.assertFalse(self.s.active)
        self.assertEqual((self.s.speed,self.s.push),(0,0))
    def test_ordinary_slope_does_not_slide(self):
        self.floor.data1=0
        self.step()
        self.assertFalse(self.s.active)
        self.assertEqual(self.s.push,0)
    def test_fall_damage_boundaries_and_floor_types(self):
        for distance,damage in ((-1,0),(399,0),(400,8),(799,8),(800,16),(5000,16)):
            self.assertEqual(self.lib.player_fall_damage(distance,0),damage)
            for floor_type in (6,9):
                self.assertEqual(self.lib.player_fall_damage(distance,floor_type),0)
        self.assertEqual(self.lib.player_fall_damage(800,7),16)

    def test_steep_slope_ground_glue_but_not_a_ledge_snap(self):
        items=bg.quad((-200,100,0),(-200,-240,200),
                      (200,-240,200),(200,100,0))
        tris=(bg.Triangle*len(items))(*[t for t,_ in items])
        info=(C.c_uint16*len(items))()
        surf=(C.c_uint32*2)(0,16)
        mesh=bg.Mesh(tris,len(items),info,surf,1,None,0,None,0,None,0)
        self.lib.bg_scene_set(C.byref(mesh))
        feet=bg.Vec(0,66,20)
        for z in range(30,100,10):
            feet.z=z
            self.assertTrue(self.lib.player_slope_ground(C.byref(feet)))
            self.assertAlmostEqual(feet.y,100-z*1.7,delta=1)
        feet.z+=20
        before=feet.y
        self.assertFalse(self.lib.player_slope_ground(C.byref(feet)))
        self.assertEqual(feet.y,before)
        self.lib.bg_scene_set(C.byref(bg.Mesh()))

if __name__=='__main__': unittest.main()
