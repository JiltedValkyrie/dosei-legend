"""Source lift/put/throw event frames, including strengthless bush refusal."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT=pathlib.Path(__file__).resolve().parents[1]
GCC=pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
class Lift(C.Structure):
    _fields_=[('phase',C.c_int),('timer',C.c_int),('attached',C.c_bool),
              ('throw_only',C.c_bool),('events',C.c_uint),
              ('speed',C.c_int32),('vertical',C.c_int32)]

@unittest.skipUnless(GCC.is_file(),'host compiler required')
class PlayerLift(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll=pathlib.Path(cls.tmp.name)/'lift.dll'
        env=dict(os.environ)
        env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            '-I'+str(ROOT.parent/'shared/lib/camera'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),
            str(ROOT/'src/player_lift.c'),str(ROOT/'src/link_anim_state.c'),
            str(ROOT/'build/generated/link_clips.c'),'-o',str(dll)],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.player_lift_begin.argtypes=[C.POINTER(Lift),C.c_bool,C.c_uint,C.c_bool]
        cls.lib.player_lift_update.argtypes=[C.POINTER(Lift),C.c_bool,C.c_int32]
        cls.lib.player_lift_cancel.argtypes=[C.POINTER(Lift)]

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.p=Lift()
        self.lib.link_anim_reset_state()
    def step(self,action=False,speed=0):
        self.lib.player_lift_update(C.byref(self.p),action,speed)
        return self.p.events
    def begin(self,bush=False,strength=0,throw_only=False):
        self.lib.player_lift_begin(C.byref(self.p),bush,strength,throw_only)
    def held(self,throw_only=False):
        self.begin(throw_only=throw_only)
        for frame in range(1,5):
            self.assertEqual(self.step(),1 if frame==4 else 0)
        for _ in range(100):
            if self.p.phase==5: break
            self.step()
        self.assertEqual(self.p.phase,5)
        self.assertTrue(self.p.attached)

    def test_bush_without_strength_never_attaches_or_drops(self):
        self.begin(bush=True)
        wait=0
        for _ in range(250):
            if self.p.phase==2: wait+=1
            self.assertEqual(self.step(),0)
            self.assertFalse(self.p.attached)
            if not self.p.phase: break
        self.assertEqual(wait,23)
        self.assertEqual(self.p.phase,0)
        self.assertEqual(self.lib.link_anim_state(),0)

    def test_attach_frame_four_and_put_frame_four(self):
        self.held()
        self.assertEqual(self.step(True),0)
        self.assertEqual(self.p.phase,7)
        self.step();self.step()
        self.assertEqual(self.step(),2)
        self.assertFalse(self.p.attached)
        self.assertEqual((self.p.speed,self.p.vertical),(0,0))
        self.assertEqual(self.step(),0)

    def test_throw_frame_three_and_motion_threshold(self):
        self.held()
        self.assertEqual(self.step(True,282),0)
        self.assertEqual(self.p.phase,6)
        self.assertEqual(self.step(speed=282),0)
        self.assertEqual(self.step(speed=282),2)
        self.assertEqual((self.p.speed,self.p.vertical),(282+2048,3072))
        self.assertEqual(self.step(),0)

    def test_throw_only_at_rest_and_cancel_releases_once(self):
        self.held(throw_only=True)
        self.step(True)
        self.assertEqual(self.p.phase,6)
        self.lib.player_lift_cancel(C.byref(self.p))
        self.assertEqual(self.p.events,2)
        self.assertEqual(self.p.phase,0)
        self.assertEqual(self.step(),0)

    def test_bush_with_strength_can_attach(self):
        self.begin(bush=True,strength=1)
        for _ in range(4): self.step()
        self.assertTrue(self.p.attached)

if __name__=='__main__': unittest.main()
