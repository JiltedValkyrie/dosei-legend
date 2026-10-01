"""Compile the actual demo aim routing and projection blocks with host state."""
import ctypes as C
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class ItemAim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        demo = (ROOT/'src/demo.c').read_text()
        latch = demo[demo.index('    cancel_pending = cancel_pending || input.cancel_pending'):]
        latch = latch[:latch.index('    if (input.menu_step)')]
        route = demo[demo.index('                if (input.look_mode) {', demo.index('gameplay_input_t action = {0};')):]
        route = route[:route.index('                if (!gameplay_blocks_world() && !action.pause &&')]
        projection = demo[demo.index('static int project_attention('):]
        projection = projection[:projection.index('\nbool attention_on_screen')]
        source = r'''
#include <math.h>
#include <string.h>
#include "gameplay.h"
#include "save_state.h"
#include "player_input.h"
gameplay_t gameplay; save_state_t save_state;
static unsigned item_aim,c_use; static bool view_first_person,cancel_pending,interact_pending,pause_pending;
static unsigned short demo_link_yaw,demo_yaw; static int demo_pitch;
static struct {int x,y,z;} demo_camera;
static struct {int look_pitch,look_yaw;} link_follow;
static bool fp_camera_done; static int fp_steps;
static void first_person_camera_step(const player_input_t *in){(void)in;++fp_steps;}
int camera_steps(void){return fp_steps;}
static int last_pitch,last_eye; int fired_pitch(void){return last_pitch;} int fired_from_eye(void){return last_eye;}
void set_look_pitch(int p){link_follow.look_pitch=p;}
bool gameplay_blocks_world(void){return gameplay.paused || gameplay.talking;}
static void snap_camera_to_link(void){}
static void oot_follow_look_exit(void *p){(void)p;link_follow.look_pitch=link_follow.look_yaw=0;}
static void oot_follow_look(void *p,int x,int y){(void)p;(void)x;(void)y;}
static int demo_screen_distance(void){return 160;}
void kokiri_camera_sincos(uint16_t a,int32_t *s,int32_t *c){*s=lround(sin(a*6.28318530718/65536)*65536);*c=lround(cos(a*6.28318530718/65536)*65536);}
void reset(void){memset(&gameplay,0,sizeof(gameplay));memset(&save_state,0,sizeof(save_state));
save_state.slingshot=1;save_state.ammo_seeds=10;save_state.c_items[0]=2;
item_aim=0;view_first_person=false;cancel_pending=false;pause_pending=false;demo_link_yaw=0;}
int aiming(void){return item_aim && view_first_person;}
int route(int press,int cancel,int target,int pause){
player_input_t input={0};gameplay_input_t action={0};
input.look_mode=view_first_person; input.c_pressed=press?PLAYER_C_DOWN:PLAYER_C_NONE;
input.look_exited=input.look_mode && (press || cancel);input.cancel_pending=cancel;
c_use=press;pause_pending=pause; action.pause=pause;action.grounded=true;
action.c_use=press;action.target_held=target;
''' + latch + route + r'''
last_pitch=action.item_pitch;last_eye=action.item_from_eye;return action.c_use;
}
''' + projection + r'''
int screen(int x,int y,int z,int pitch,int axis){int32_t p[3]={x,y,z},sx,sy;demo_pitch=pitch;project_attention(p,&sx,&sy);return axis?sy:sx;}
int screen_pose(int x,int y,int z,int yaw,int pitch,int axis){demo_yaw=yaw;return screen(x,y,z,pitch,axis);}
'''
        out = Path(cls.tmp.name)/'aim.dll'
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'src'),
                        '-I'+str(ROOT.parent/'shared/lib/camera'),
                        '-I'+str(ROOT.parent/'shared/lib/collision'),
                        '-x','c','-','-o',str(out),'-lm'],input=source,text=True,check=True,env=env)
        cls.lib = C.CDLL(str(out))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self): self.lib.reset()

    def test_tap_enters_release_holds_second_tap_fires_and_cancel_exits(self):
        g=self.lib
        self.assertEqual(g.route(1,0,0,0),0)
        self.assertTrue(g.aiming())
        for _ in range(30): self.assertEqual(g.route(0,0,0,0),0)
        self.assertTrue(g.aiming())
        self.assertEqual(g.route(1,0,0,0),1)
        self.assertTrue(g.aiming())
        self.assertEqual(g.route(0,1,0,0),0)
        self.assertFalse(g.aiming())

    def test_fire_applies_this_steps_look_first_and_keeps_pitch_sign(self):
        g=self.lib
        g.route(1,0,0,0)                         # enter aim
        before=g.camera_steps()
        g.set_look_pitch(3000)                   # positive is looking up
        self.assertEqual(g.route(1,0,0,0),1)     # fire
        self.assertEqual(g.camera_steps(),before+1)
        self.assertEqual(g.fired_pitch(),3000)   # not negated
        self.assertTrue(g.fired_from_eye())

    def test_target_press_fires_directly_and_pause_closes_aim(self):
        g=self.lib
        self.assertEqual(g.route(1,0,1,0),1)
        self.assertFalse(g.aiming())
        g.route(1,0,0,0)
        self.assertEqual(g.route(1,0,0,1),0)
        self.assertFalse(g.aiming())

    def test_marker_projection_matches_y_up_camera_and_screen_handedness(self):
        g=self.lib
        self.assertEqual(g.screen(0,0,100,0,0),160)
        self.assertEqual(g.screen(0,0,100,0,1),120)
        self.assertGreater(g.screen(-20,0,100,0,0),160)
        self.assertLess(g.screen(0,20,100,0,1),120)
        self.assertAlmostEqual(g.screen(0,100,100,8192,1),120,delta=1)
        self.assertAlmostEqual(g.screen(0,-100,100,-8192,1),120,delta=1)

    def test_pitched_camera_projects_its_look_at_point_to_screen_centre(self):
        # Geometric ray: positive camera pitch looks UP, as the live follow
        # camera contract specifies. Include down-looking battle cameras and
        # nonzero yaw; zero-pitch tests cannot expose the old sign reversal.
        for yaw in (0, 8192, 24576, 49152):
            for pitch in (-8192, -4096, 0, 4096, 8192):
                y = yaw * math.tau / 65536
                p = pitch * math.tau / 65536
                point = (round(1000 * math.sin(y) * math.cos(p)),
                         round(1000 * math.sin(p)),
                         round(1000 * math.cos(y) * math.cos(p)))
                with self.subTest(yaw=yaw, pitch=pitch):
                    self.assertAlmostEqual(self.lib.screen_pose(*point,yaw,pitch,0),160,delta=1)
                    self.assertAlmostEqual(self.lib.screen_pose(*point,yaw,pitch,1),120,delta=1)


if __name__=='__main__': unittest.main()
