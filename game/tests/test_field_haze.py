"""Execute the submitted haze geometry with a recording SGL interface."""
import ctypes as C
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'


@unittest.skipUnless(Path(GCC).is_file() or shutil.which(GCC), 'host GCC required')
class FieldHaze(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        p = Path(cls.tmp.name)
        (p/'test.c').write_text(r'''
#include <stdint.h>
typedef int32_t POINT[3];
typedef uint16_t ANGLE;
typedef struct {int32_t normal[3]; uint16_t vertex[4];} POLYGON;
typedef struct {unsigned plane,sort,texture,colno,gouraud,mode,command,option;} ATTR;
typedef struct {POINT *points;int count;POLYGON *faces;int polygons;ATTR *attrs;} PDATA;
#define Dual_Plane 1
#define SORT_MIN 1
#define UseNearClip 32
#define No_Gouraud 0
#define MESHon 256
#define ECdis 128
#define SPdis 64
#define sprPolygon 4
#define No_Option 0
#define C_RGB(r,g,b) (32768|(r)|((g)<<5)|((b)<<10))
#define ATTRIBUTE(a,b,c,d,e,f,g,h) {a,b,c,d,e,f,g,h}
#define SCENE_SPOT00 10
static unsigned forest_scene,recomp_yaw;
static struct {int32_t x,y,z;} recomp_link;
static struct {int32_t x,y,z;} recomp_camera;
static int depth,calls,turn,recomp_pitch,tilt;
static int32_t translation[3];
static PDATA *queued;
static void slPushMatrix(void){++depth;}
static void slPopMatrix(void){--depth;}
static void slTranslate(int32_t x,int32_t y,int32_t z){translation[0]=x;translation[1]=y;translation[2]=z;}
static void slRotY(ANGLE yaw){turn=yaw;}
static void slRotX(ANGLE pitch){tilt=(int16_t)pitch;}
void pitch(int p){recomp_pitch=p;}
static void submit(PDATA *p,unsigned mask){queued=p;++calls;}
static unsigned scene_flow_scene(void){return forest_scene;}
static unsigned oot_core_skybox_time(void){return 0;}
static unsigned short environment_haze_colour(unsigned scene,unsigned time){return 0x8000u+scene+time;}
#include "field_haze.h"
int fade(int cx,int cz,int lx,int lz,int s,int c,int depth){
    recomp_camera.x=cx;recomp_camera.z=cz;recomp_link.x=lx;recomp_link.z=lz;
    return depth+field_fade_offset(s,c);
}
void draw(int scene,int x,int y,int z,int yaw){
    forest_scene=scene;recomp_link.x=x;recomp_link.y=y;recomp_link.z=z;recomp_yaw=yaw;
    recomp_camera.x=x+100;recomp_camera.y=y+300;recomp_camera.z=z-600;
    calls=depth=0;field_haze_draw();
}
int value(int key){
    if(key==101)return queued->attrs->colno;
    if(key==100)return tilt;
    if(key==0)return calls;if(key==1)return depth;if(key==2)return turn;
    if(key>=3&&key<6)return translation[key-3];
    if(key==6)return queued->count;if(key==7)return queued->polygons;
    if(key==8)return queued->attrs->sort;if(key==9)return queued->attrs->mode;
    return queued->points[(key-10)/3][(key-10)%3];
}
''')
        lib = p / ('test.dll' if os.name == 'nt' else 'test.so')
        env = dict(os.environ, PATH=str(Path(GCC).parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([GCC,'-shared','-O2','-I'+str(ROOT/'src'),str(p/'test.c'),'-o',str(lib)],
                       check=True,env=env)
        cls.lib = C.CDLL(str(lib))
        cls.lib.draw.argtypes = [C.c_int]*5
        cls.lib.value.argtypes = [C.c_int]
        cls.lib.value.restype = C.c_int

    @classmethod
    def tearDownClass(cls):
        cls.lib = None
        cls.tmp.cleanup()

    def test_all_maps_two_panels_balanced_matrix_and_hardware_dither(self):
        for scene in (0,1,9,11,100):
            self.lib.draw(scene,0,0,0,0)
            self.assertEqual(self.lib.value(0),1)
            self.assertEqual(self.lib.value(1),0)
            self.assertEqual(self.lib.value(101),0x8000+scene)
        self.lib.draw(10,0,0,0,0)
        self.assertEqual([self.lib.value(i) for i in (0,1,6,7)], [1,0,6,2])
        self.assertEqual(self.lib.value(8),1|32)
        self.assertEqual(self.lib.value(9),256|128|64)

    def test_world_curtain_follows_link_yaw_but_not_camera_pitch(self):
        for yaw in (0,16384,32768,49152):
            self.lib.draw(10,6000,450,-4000,yaw)
            self.assertEqual([self.lib.value(i)//65536 for i in (3,4,5)],[6000,-450,-4000])
            self.assertEqual(self.lib.value(2),yaw)
            vertices = [[self.lib.value(10+i*3+k)/65536 for k in range(3)] for i in range(6)]
            self.assertTrue(all(1800 < p[2] < 4000 for p in vertices))
            self.assertGreater(max(p[0] for p in vertices),3200*160/240)
            rows=[]
            for angle in (-8192,0,8192):
                self.lib.pitch(angle)
                self.lib.draw(10,6000,450,-4000,yaw)
                self.assertEqual(self.lib.value(100),0)
                pitch=angle*math.tau/65536
                y,z=vertices[0][1:]
                # Upright world geometry receives normal view pitch.
                vy=y*math.cos(pitch)+z*math.sin(pitch)
                vz=-y*math.sin(pitch)+z*math.cos(pitch)
                rows.append(120+240*vy/vz)
            self.assertGreater(max(rows)-min(rows),100)
            self.lib.pitch(0)

    def test_each_panel_has_visible_corners_at_normal_camera_pitch(self):
        self.lib.draw(10,0,0,0,0)
        vertices = [[self.lib.value(10+i*3+k)/65536 for k in range(3)] for i in range(6)]
        for pitch in (-math.pi/18,0):
            for face in ((0,1,2,3),(1,4,5,2)):
                visible=0
                for i in face:
                    x,y,z=vertices[i]
                    vy=y*math.cos(pitch)+z*math.sin(pitch)
                    vz=-y*math.sin(pitch)+z*math.cos(pitch)
                    visible += abs(240*x/vz)<160 and abs(240*vy/vz)<112
                self.assertGreaterEqual(visible,2)

    def test_field_fade_is_independent_of_camera_pullback(self):
        for s,c in ((0,65536),(65536,0),(0,-65536),(-65536,0)):
            for back in (0,100,600,800,1400):
                cx=1000-s*back//65536;cz=2000-c*back//65536
                self.assertEqual(self.lib.fade(cx,cz,1000,2000,s,c,1800+back),1800)


if __name__ == '__main__':
    unittest.main()
