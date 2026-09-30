"""Real shutter rules and source web collision against host DynaPoly."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class Mechanisms(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        doors=(ROOT/'src/dungeon_doors.c').read_text().replace('#include <jo/jo.h>','').replace('#include "kokiri_scene.h"','')
        pre=r'''#include <stdint.h>
#include <math.h>
#include "gameplay.h"
#include "save_state.h"
#include "kokiri_collision.h"
#include "dungeon_webs.h"
typedef struct {short front,back,x,y,z,yaw;unsigned char scene,kind,flag;} kokiri_portal;
#define KOKIRI_PORTAL_COUNT 1
static kokiri_portal kokiri_portals[1]={{0,1,0,0,0,0,7,9,3}};
gameplay_t gameplay;
void kokiri_camera_sincos(uint16_t yaw,int32_t *s,int32_t *c) {
    *s=(int32_t)round(sin(yaw*6.283185307179586/65536)*65536);
    *c=(int32_t)round(cos(yaw*6.283185307179586/65536)*65536);
}
'''
        post=r'''
static unsigned char dyna[0x4800];
static bg_mesh_t empty;
void reset(void) {dungeon_webs_reset();bg_dyna_init(dyna,sizeof(dyna));bg_scene_set(&empty);save_new_game();dungeon_doors_reset();save_state.scene_id=2;}
int door_step(int type,int room,int press,int z) {
    gameplay_input_t in={0};kokiri_portals[0].kind=8+type;
    in.room=room;in.z=z;in.yaw=z>0?0x8000:0;in.grounded=true;in.interact=press;
    return dungeon_doors_step(&in);
}
int wall(int from,int to) {int32_t x=0,z=to;door_step(1,1,0,from);dungeon_doors_constrain(&x,&z,0);return z;}
int floor_at(int x,int y,int z) {bg_vec_t p={x,y,z};return bg_floor(&p,BG_IGNORE_ENTITY,0);}
'''
        src=folder/'test.c';src.write_text(pre+doors+post)
        dll=folder/'test.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
            '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            '-I'+str(ROOT.parent/'shared/lib/collision'),'-I'+str(ROOT.parent/'shared/lib/camera'),
            str(src),str(ROOT/'src/dungeon_webs.c'),str(ROOT/'src/save_state.c'),
            str(ROOT.parent/'shared/lib/collision/kokiri_collision.c'),'-o',str(dll),'-lm'],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        for name in ('dungeon_webs_step','dungeon_webs_land','save_get_switch','dungeon_door_open'):
            getattr(cls.lib,name).restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.lib.reset()
    def test_clear_door_keeps_back_locked_until_clear_and_front_opens(self):
        g=self.lib
        for _ in range(30):g.door_step(1,1,1,40)
        self.assertFalse(g.dungeon_door_open(0))
        g.save_set_clear(2,1)
        for _ in range(24):g.door_step(1,1,1,40)
        self.assertTrue(g.dungeon_door_open(0))
        g.reset()
        for _ in range(24):g.door_step(1,0,1,-40)
        self.assertTrue(g.dungeon_door_open(0))
    def test_switch_gate_uses_own_flag_and_swept_closed_collision(self):
        g=self.lib
        g.save_set_switch(2,4)
        for _ in range(24):g.door_step(2,1,1,40)
        self.assertFalse(g.dungeon_door_open(0))
        self.assertEqual(g.wall(40,-40),22)
        g.save_set_switch(2,3)
        for _ in range(24):g.door_step(2,1,1,40)
        self.assertTrue(g.dungeon_door_open(0))
    def test_web_catches_small_fall_breaks_high_central_fall_and_stays_gone(self):
        g=self.lib
        self.assertTrue(g.dungeon_webs_step(2,0))
        floor=g.floor_at(0,30,0)
        self.assertGreater(floor,-20)
        self.assertFalse(g.dungeon_webs_land(0,floor,0,750))
        self.assertFalse(g.dungeon_webs_land(90,0,0,900))
        self.assertTrue(g.dungeon_webs_land(0,floor,0,751))
        for _ in range(30):self.assertTrue(g.dungeon_webs_step(2,3))
        self.assertTrue(g.save_get_switch(2,5))
        self.assertEqual(g.floor_at(0,30,0),-32000)
        g.dungeon_webs_step(2,1);g.dungeon_webs_step(2,0)
        self.assertEqual(g.floor_at(0,30,0),-32000)
    def test_room_unload_removes_web_collision_without_granting_switch(self):
        g=self.lib;g.dungeon_webs_step(2,0);g.dungeon_webs_step(2,1)
        self.assertEqual(g.floor_at(0,30,0),-32000)
        self.assertFalse(g.save_get_switch(2,5))
if __name__=='__main__':unittest.main()
