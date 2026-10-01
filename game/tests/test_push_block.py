"""Obj_Oshihiki movement with real PUSHBLK.COL, actor pool and DynaPoly."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest
import test_player_bg as bg

ROOT, GCC, Vec, Mesh = bg.ROOT, bg.GCC, bg.Vec, bg.Mesh

class Actor(C.Structure):
    _fields_ = [('profile', C.c_void_p), ('x', C.c_int32), ('y', C.c_int32),
                ('z', C.c_int32)]

class Push(C.Structure):
    _fields_=[('phase',C.c_int),('direction',C.c_int),('bg_id',C.c_uint),
              ('block_x',C.c_int32),('block_z',C.c_int32)]

@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class PushBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll = pathlib.Path(cls.tmp.name) / 'push.dll'
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        collision = ROOT.parent / 'shared/lib/collision'
        camera = ROOT.parent / 'shared/lib/camera'
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Wextra', '-Werror',
            '-I'+str(ROOT/'src'), '-I'+str(collision), '-I'+str(camera),
            '-I'+str(ROOT/'build/generated'),
            str(ROOT/'src/push_block.c'), str(ROOT/'src/actor_sys.c'),
            str(ROOT/'src/player_push.c'), str(ROOT/'src/player_bg.c'),
            str(ROOT/'src/link_anim_state.c'),str(ROOT/'build/generated/link_clips.c'),
            str(ROOT/'src/save_state.c'), str(collision/'kokiri_collision.c'),
            str(ROOT/'tests/fixtures/traversal_host.c'), '-o', str(dll), '-lm'],
            check=True, env=env)
        lib = cls.lib = C.CDLL(str(dll))
        lib.actor_sys_init.argtypes = [C.c_void_p, C.c_uint]
        lib.bg_dyna_init.argtypes = [C.c_void_p, C.c_uint]
        lib.bg_scene_set.argtypes = [C.POINTER(Mesh)]
        lib.bg_mesh_bytes.argtypes = [C.c_char_p,C.c_uint]
        lib.bg_mesh_decode.argtypes = [C.c_char_p,C.c_uint,C.c_void_p,C.c_uint,C.POINTER(Mesh)]
        lib.push_block_set_mesh.argtypes = [C.POINTER(Mesh)]
        lib.push_block_spawn.argtypes = [C.c_uint,C.c_int,Vec,C.c_uint16,C.c_uint16]
        lib.push_block_spawn.restype = C.POINTER(Actor)
        lib.push_block_request.argtypes = [C.POINTER(Actor),C.c_uint16,C.c_int,C.c_uint]
        lib.push_block_request.restype = C.c_bool
        lib.push_block_bg.argtypes = [C.POINTER(Actor)]
        lib.bg_dyna_carry.argtypes = [C.c_uint,C.POINTER(Vec),C.POINTER(C.c_uint16)]
        lib.bg_line.argtypes=[C.POINTER(Vec),C.POINTER(Vec),C.POINTER(Vec),
                             C.c_uint,C.c_uint,C.POINTER(bg.Hit)]
        lib.player_bg_update.argtypes=[C.POINTER(bg.Bg),C.c_bool,C.POINTER(bg.Hit),
                                      C.POINTER(Vec),C.c_uint16,C.c_uint16,C.c_int32]
        lib.player_push_start.argtypes=[C.POINTER(Push),C.POINTER(bg.Bg),C.c_bool,
                                       C.POINTER(C.c_uint16)]
        lib.player_push_prompt.argtypes=[C.POINTER(bg.Bg)]
        lib.player_push_prompt.restype=C.c_bool
        lib.player_push_update.argtypes=[C.POINTER(Push),C.c_bool,C.c_int32,
                                        C.c_uint16,C.POINTER(Vec),C.c_uint16]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.pool = C.create_string_buffer(self.lib.actor_sys_bytes())
        self.dyna = C.create_string_buffer(0x4800)
        self.assertTrue(self.lib.actor_sys_init(self.pool,len(self.pool)))
        self.assertTrue(self.lib.bg_dyna_init(self.dyna,len(self.dyna)))
        data = (ROOT/'build/generated/PUSHBLK.COL').read_bytes()
        size = self.lib.bg_mesh_bytes(data,len(data))
        self.store = C.create_string_buffer(size)
        self.mesh = Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(data,len(data),self.store,size,C.byref(self.mesh)))
        self.assertTrue(self.lib.push_block_set_mesh(C.byref(self.mesh)))
        self.world(bg.ground())
        self.lib.link_anim_reset_state()

    def tearDown(self):
        self.lib.actor_sys_clear()

    def world(self,*parts):
        items = [t for part in parts for t in part]
        self.tris = (bg.Triangle*len(items))(*[t for t,_ in items])
        self.info = (C.c_uint16*len(items))()
        self.surf = (C.c_uint32*2)()
        self.scene = Mesh(self.tris,len(items),self.info,self.surf,1,None,0,None,0,None,0)
        self.lib.bg_scene_set(C.byref(self.scene))

    def spawn(self,x=0,y=0,z=0,params=0):
        a = self.lib.push_block_spawn(1,0,Vec(x,y,z),0,params)
        self.assertTrue(a)
        return a

    def steps(self,n):
        for _ in range(n):
            self.lib.bg_dyna_step()
            self.lib.actor_sys_update()

    def test_push_pull_exact_grid_cooldown_and_cleanup(self):
        a = self.spawn()
        self.assertTrue(self.lib.push_block_request(a,0,1,0))
        self.steps(20)
        self.assertEqual(a.contents.z,20)
        self.assertFalse(self.lib.push_block_request(a,0,-1,0))
        self.steps(20)
        self.assertTrue(self.lib.push_block_request(a,0,-1,0))
        self.steps(20)
        self.assertEqual(a.contents.z,0)
        self.lib.actor_sys_room_unload(0)
        self.assertEqual(self.lib.bg_dyna_triangles_used(),0)

    def test_obstacle_refuses_before_motion(self):
        self.world(bg.ground(),bg.quad((-200,0,45),(-200,200,45),
                                      (200,200,45),(200,0,45)))
        a=self.spawn()
        self.assertFalse(self.lib.push_block_request(a,0,1,0))
        self.steps(20)
        self.assertEqual(a.contents.z,0)

    def test_strength_and_other_block_obstruction(self):
        a=self.spawn(params=2)
        self.assertFalse(self.lib.push_block_request(a,0,1,0))
        self.assertTrue(self.lib.push_block_request(a,0,1,1))
        self.lib.actor_sys_clear()
        a=self.spawn()
        self.spawn(z=70)
        self.assertFalse(self.lib.push_block_request(a,0,1,0))

    def test_fall_and_rider_translation(self):
        a=self.spawn(y=80)
        self.steps(45)
        self.assertEqual(a.contents.y,0)
        self.assertTrue(self.lib.push_block_request(a,0x4000,1,0))
        rider=Vec(0,60,0)
        slot=self.lib.push_block_bg(a)
        for _ in range(20):
            self.steps(1)
            self.lib.bg_dyna_carry(slot,C.byref(rider),None)
        self.assertEqual(a.contents.x,20)
        self.assertEqual(rider.x,20)

    def grab(self,a):
        feet=Vec(0,0,-44)
        hit,at=bg.Hit(),Vec()
        self.assertTrue(self.lib.bg_line(C.byref(Vec(0,26,-44)),C.byref(Vec(0,26,0)),
            C.byref(at),9,2,C.byref(hit)))
        probe=bg.Bg()
        self.lib.player_bg_update(C.byref(probe),True,C.byref(hit),C.byref(feet),0,0,0)
        self.assertTrue(self.lib.player_push_prompt(C.byref(probe)))
        state=Push()
        facing=C.c_uint16(0)
        self.assertTrue(self.lib.player_push_start(C.byref(state),C.byref(probe),True,C.byref(facing)))
        return state,feet,facing

    def test_player_grab_push_pull_release(self):
        a=self.spawn()
        state,feet,facing=self.grab(a)
        def drive(speed,heading,held=True):
            self.steps(1)
            self.lib.player_push_update(C.byref(state),held,speed,heading,
                                         C.byref(feet),facing.value)
        for _ in range(48): drive(1408,0)
        self.assertGreater(a.contents.z,0)
        self.assertEqual(feet.z,a.contents.z-49)
        furthest=a.contents.z
        for _ in range(100): drive(1408,0x8000)
        self.assertLess(a.contents.z,furthest)
        self.assertEqual(feet.z,a.contents.z-49)
        for _ in range(80): drive(0,0,False)
        self.assertEqual(state.phase,0)
        self.assertEqual(self.lib.link_anim_state(),0)

    def test_pull_refuses_wall_behind_player(self):
        self.world(bg.ground(),bg.quad((200,0,-70),(200,200,-70),
                                       (-200,200,-70),(-200,0,-70)))
        a=self.spawn()
        state,feet,facing=self.grab(a)
        for _ in range(100):
            self.steps(1)
            self.lib.player_push_update(C.byref(state),True,1408,0x8000,
                                         C.byref(feet),facing.value)
        self.assertEqual(a.contents.z,0)

if __name__ == '__main__':
    unittest.main()
