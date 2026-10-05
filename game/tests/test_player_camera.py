"""Traversal framing, return continuity, camera collision and crawl data checks."""
import ctypes as C
import os
import pathlib
import subprocess
import tempfile
import unittest
import test_player_bg as bg
import test_oot_follow as follow

ROOT=pathlib.Path(__file__).resolve().parents[1]
class Camera(C.Structure):
    _fields_=[('mode',C.c_uint),('at_y',C.c_int32),('previous_y',C.c_int32),
              ('climb_offset',C.c_int32),('initialized',C.c_bool),('returning',C.c_bool)]
class BgCamera(C.Structure):
    _fields_=[('setting',C.c_uint16),('count',C.c_int16),('first',C.c_uint32)]

@unittest.skipUnless(bg.GCC.is_file(),'host compiler required')
class TraversalCamera(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll=pathlib.Path(cls.tmp.name)/'camera.dll'
        env=dict(os.environ)
        env['PATH']=str(bg.GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(bg.GCC),'-shared','-O2','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'src'),'-I'+str(ROOT.parent/'shared/lib/camera'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),str(ROOT/'src/player_camera.c'),
            str(ROOT.parent/'shared/lib/camera/oot_follow.c'),
            str(ROOT.parent/'shared/lib/collision/kokiri_collision.c'),
            str(ROOT/'tests/fixtures/traversal_host.c'),'-o',str(dll),'-lm'],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.player_camera_update.argtypes=[C.POINTER(Camera),C.POINTER(follow.Follow),
            C.c_uint,C.POINTER(follow.Position),C.c_uint16,C.c_bool,C.POINTER(follow.Position),
            C.POINTER(C.c_uint16),C.POINTER(C.c_int32)]
        cls.lib.oot_follow_update.argtypes=[C.POINTER(follow.Follow),C.POINTER(follow.Position),
            C.c_uint16,C.c_bool,C.POINTER(follow.Position),C.POINTER(C.c_uint16),C.POINTER(C.c_int32)]
        cls.lib.bg_scene_set.argtypes=[C.POINTER(bg.Mesh)]
        cls.lib.player_camera_crawl_line.argtypes=[C.POINTER(bg.Mesh),C.c_uint,
                                                 C.POINTER(bg.Vec),C.POINTER(C.c_int32)]
        cls.lib.player_camera_crawl_line.restype=C.c_bool
    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.lib.oot_follow_set_adult(False)
        self.lib.oot_follow_set_legacy(False)
        self.camera=Camera();self.follow=follow.Follow()
        self.player=follow.Position(0,90,0);self.eye=follow.Position()
        self.yaw=C.c_uint16();self.pitch=C.c_int32()
        self.mesh=bg.Mesh()
        self.lib.bg_dyna_clear()
        self.lib.bg_scene_set(C.byref(self.mesh))
    def step(self,mode=0,facing=0,moving=False):
        self.lib.player_camera_update(C.byref(self.camera),C.byref(self.follow),mode,
            C.byref(self.player),facing,moving,C.byref(self.eye),C.byref(self.yaw),C.byref(self.pitch))
    def test_stationary_climb_keeps_far_distance_and_returns_on_exit(self):
        for _ in range(120): self.step(mode=0)
        near = self.follow.distance
        for _ in range(120): self.step(mode=1)
        self.assertGreater(self.follow.distance, near + 30)
        self.assertEqual(self.follow.distance, 139 * 3 // 2)
        far = self.follow.distance
        for _ in range(60): self.step(mode=1)
        self.assertEqual(self.follow.distance, far)
        for _ in range(120): self.step(mode=0)
        self.assertLess(self.follow.distance, far - 30)

    def world(self,triangles):
        self.tris=(bg.Triangle*len(triangles))(*[t for t,_ in triangles])
        self.info=(C.c_uint16*len(triangles))(*[i for _,i in triangles])
        self.mesh=bg.Mesh(self.tris,len(triangles),self.info,None,0,None,0,None,0,None,0)
        self.lib.bg_scene_set(C.byref(self.mesh))
    def test_normal_camera_is_unchanged(self):
        reference=follow.Follow();eye=follow.Position();yaw=C.c_uint16();pitch=C.c_int32()
        for i in range(100):
            self.player.x+=1
            heading=i*80
            self.step(facing=heading,moving=True)
            self.lib.oot_follow_update(C.byref(reference),C.byref(self.player),heading,True,
                                      C.byref(eye),C.byref(yaw),C.byref(pitch))
            self.assertEqual((self.eye.x,self.eye.y,self.eye.z,self.yaw.value,self.pitch.value),
                             (eye.x,eye.y,eye.z,yaw.value,pitch.value))
    def test_hang_lowers_target_and_holds_view_yaw(self):
        self.step()
        original=self.yaw.value
        for _ in range(1800):self.step(2,facing=32768)
        self.assertEqual(self.camera.at_y,44-37)
        self.assertEqual(self.follow.pitch,7282)
        self.assertEqual(self.yaw.value,original)
        self.assertGreater(self.eye.y,self.camera.at_y)

    def test_adult_camera_tracks_source_height_in_normal_and_hang(self):
        self.lib.oot_follow_set_adult(True)
        for _ in range(180): self.step()
        self.assertEqual(self.camera.at_y,68-14)
        self.assertEqual(self.follow.distance,136)
        for _ in range(1800): self.step(2)
        self.assertEqual(self.camera.at_y,68-54)
        self.assertEqual(self.follow.pitch,7282)
    def test_climb_tracks_stationary_facing_and_flattens_near_floor(self):
        self.world(bg.ground())
        self.step()
        self.player.y+=20
        for _ in range(600):self.step(1,facing=16384)
        self.assertEqual(self.camera.climb_offset,-14)
        self.assertEqual(self.camera.at_y,20+44-14)
        self.assertEqual(self.follow.pitch,500)
        self.assertEqual(self.yaw.value,16384)
    def test_exit_hang_eases_target_back_without_cut(self):
        for _ in range(180):self.step(2)
        before=self.camera.at_y
        self.step(0)
        self.assertGreater(self.camera.at_y,before)
        self.assertLess(self.camera.at_y,44-9)
        for _ in range(180):self.step(0)
        self.assertEqual(self.camera.at_y,44-9)
        self.assertFalse(self.camera.returning)
    def test_camera_wall_and_camera_ignore_flag(self):
        wall=bg.quad((-200,-200,-60),(200,-200,-60),(200,300,-60),(-200,300,-60))
        self.world(wall)
        for _ in range(90):self.step(2)
        self.assertGreaterEqual(self.eye.z,-58)
        self.world([(t,1<<8) for t,_ in wall])
        self.step(2)
        self.assertLess(self.eye.z,-60)

    def test_normal_and_far_camera_squeeze_before_wall_for_both_ages(self):
        self.world(bg.wall(-60,-200,300))
        for adult in (False,True):
            for legacy in (False,True):
                with self.subTest(adult=adult,legacy=legacy):
                    self.lib.oot_follow_set_adult(adult)
                    self.lib.oot_follow_set_legacy(legacy)
                    self.camera=Camera();self.follow=follow.Follow()
                    for _ in range(30):self.step()
                    self.assertGreaterEqual(self.eye.z,-52)
                    self.assertLessEqual(self.eye.z,0)

    def test_normal_camera_does_not_enter_rising_ground(self):
        # Ground rises behind Link: y=-z, so the desired eye lies underground.
        self.world(bg.quad((-300,300,-300),(-300,0,0),(300,0,0),(300,300,-300)))
        for adult in (False,True):
            for legacy in (False,True):
                with self.subTest(adult=adult,legacy=legacy):
                    self.lib.oot_follow_set_adult(adult)
                    self.lib.oot_follow_set_legacy(legacy)
                    self.camera=Camera();self.follow=follow.Follow()
                    for _ in range(30):self.step()
                    self.assertGreater(self.eye.y,-self.eye.z)
                    self.assertLess(self.eye.z,0)

    def test_normal_camera_respects_camera_ignore_and_recovers_clear_distance(self):
        wall=bg.wall(-60,-200,300)
        self.world(wall)
        for _ in range(30):self.step()
        self.assertGreaterEqual(self.eye.z,-52)
        self.world([(t,1<<8) for t,_ in wall])
        self.step()
        self.assertLess(self.eye.z,-60)
        self.world([])
        self.step()
        self.assertLess(self.eye.z,-60)

    def test_recorded_field_turn_keeps_camera_above_real_collision_floor(self):
        data=(ROOT/'build/cd/SA.COL').read_bytes()
        self.lib.bg_mesh_bytes.argtypes=[C.c_char_p,C.c_uint32]
        self.lib.bg_mesh_bytes.restype=C.c_uint32
        self.lib.bg_mesh_decode.argtypes=[C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.POINTER(bg.Mesh)]
        size=self.lib.bg_mesh_bytes(data,len(data));store=C.create_string_buffer(size)
        mesh=bg.Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(data,len(data),store,size,C.byref(mesh)))
        self.lib.bg_scene_set(C.byref(mesh))
        self.lib.bg_floor.argtypes=[C.POINTER(bg.Vec),C.c_uint32,C.POINTER(bg.Hit)]
        self.lib.bg_floor.restype=C.c_int32
        self.lib.oot_follow_set_adult(True);self.lib.oot_follow_set_legacy(True)
        self.player=follow.Position(60,90,3367)
        self.follow.initialised=True;self.follow.yaw=40906;self.follow.distance=204
        self.step(facing=24521)
        hit=bg.Hit();ray=bg.Vec(self.eye.x,1000,self.eye.z)
        floor=self.lib.bg_floor(C.byref(ray),1,C.byref(hit))
        self.assertGreaterEqual(self.eye.y-floor,50,(self.eye.x,self.eye.y,self.eye.z,floor))
        self.assertLess(self.pitch.value,0)

    def test_slope_keeps_age_and_pitch_height_above_ground(self):
        for adult in (False,True):
            with self.subTest(adult=adult):
                self.lib.oot_follow_set_adult(adult)
                self.world([]);self.camera=Camera();self.follow=follow.Follow()
                for _ in range(30):self.step()
                clearance=self.eye.y
                self.world(bg.quad((-300,300,-300),(-300,0,0),(300,0,0),(300,300,-300)))
                self.step()
                self.assertGreaterEqual(self.eye.y+self.eye.z,clearance)
                self.assertLess(self.pitch.value,-1820)

    def test_ground_raise_still_stops_at_wall(self):
        self.world(bg.quad((-300,300,-300),(-300,0,0),(300,0,0),(300,300,-300))+
                   bg.wall(-60,-200,500))
        for _ in range(30):self.step()
        self.assertGreater(self.eye.z,-60)
        self.assertGreater(self.eye.y,-self.eye.z)
    def test_crawl_line_rejects_invalid_setting_ranges_and_zero_length(self):
        self.cams=(BgCamera*1)(BgCamera(0x1E,4,0))
        self.vectors=(C.c_int16*12)(0,0,0,10,20,30,10,20,130,0,0,0)
        self.mesh.cameras=C.cast(self.cams,C.c_void_p);self.mesh.camera_count=1
        self.mesh.camera_vectors=C.cast(self.vectors,C.c_void_p);self.mesh.camera_vector_count=4
        point=bg.Vec();direction=(C.c_int32*3)()
        def valid(index=0):
            return self.lib.player_camera_crawl_line(C.byref(self.mesh),index,C.byref(point),direction)
        self.assertTrue(valid());self.assertEqual(tuple(direction),(0,0,100))
        self.assertFalse(valid(1))
        self.cams[0].setting=0;self.assertFalse(valid());self.cams[0].setting=0x1E
        self.cams[0].first=0xFFFFFFFF;self.assertFalse(valid());self.cams[0].first=0
        self.cams[0].count=-1;self.assertFalse(valid());self.cams[0].count=4
        self.vectors[8]=30;self.assertFalse(valid())

    def test_real_sword_maze_camera_line_is_accepted(self):
        data=(ROOT/'build/cd/S1.COL').read_bytes()
        self.lib.bg_mesh_bytes.argtypes=[C.c_char_p,C.c_uint32]
        self.lib.bg_mesh_bytes.restype=C.c_uint32
        self.lib.bg_mesh_decode.argtypes=[C.c_char_p,C.c_uint32,C.c_void_p,C.c_uint32,C.POINTER(bg.Mesh)]
        size=self.lib.bg_mesh_bytes(data,len(data))
        store=C.create_string_buffer(size);mesh=bg.Mesh()
        self.assertTrue(self.lib.bg_mesh_decode(data,len(data),store,size,C.byref(mesh)))
        point=bg.Vec();direction=(C.c_int32*3)()
        self.assertTrue(self.lib.player_camera_crawl_line(C.byref(mesh),9,C.byref(point),direction))
        self.assertEqual((point.x,point.y,point.z),(-784,132,1037))
        self.assertEqual(tuple(direction),(0,0,364))

    def view_step(self, x=0, y=0, facing=0, aim=False):
        focus=bg.Vec(0, 44, 0)
        self.lib.player_camera_first_person(C.byref(self.follow), C.byref(focus),
            facing, x, y, C.byref(self.eye), C.byref(self.yaw), C.byref(self.pitch), aim)

    def test_slingshot_aim_holds_pitch_after_releasing_direction(self):
        for _ in range(20): self.view_step(420,280,aim=True)
        yaw,pitch=self.yaw.value,self.pitch.value
        for _ in range(100): self.view_step(aim=True)
        self.assertEqual((self.yaw.value,self.pitch.value),(yaw,pitch))
        for _ in range(100): self.view_step(y=280,aim=True)
        self.assertEqual(self.pitch.value,-14400)

    def test_first_person_turns_full_circle_and_pitch_returns_to_level(self):
        for i in range(180): self.view_step(420, 280)
        self.assertGreater(self.pitch.value, 13000)
        self.assertEqual(self.yaw.value, (180*640) & 65535)
        for i in range(200): self.view_step()
        self.assertEqual(self.pitch.value, 0)
        self.assertLessEqual(abs(self.eye.x)+abs(self.eye.z), 7)
        self.assertEqual(self.eye.y, 44)

    def test_first_person_eye_does_not_cross_nearby_wall(self):
        # Reuse the collision fixture helper: vertical wall behind the focus.
        self.world([bg.tri(((-20,0,-3),(20,0,-3),(20,100,-3))),
                    bg.tri(((-20,0,-3),(20,100,-3),(-20,100,-3)))])
        self.view_step()
        self.assertGreater(self.eye.z, -3)

if __name__=='__main__':unittest.main()
