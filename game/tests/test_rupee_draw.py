"""Exercise actual rupee world and HUD submissions with a host SGL adapter."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class RupeeDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = (ROOT/'src/kokiri_sgl.c').read_text()
        start = source.index('unsigned int kokiri_scene_room(void)')
        body = source[start:source.index('void                kokiri_grass_draw(void)', start)]
        adapter = r"""
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include "kokiri_actors.h"
#include "gameplay.h"
typedef int32_t FIXED;
typedef uint16_t Uint16;
typedef struct { Uint16 texno, atrb; } SPR_ATTR;
#define SPR_ATTRIBUTE(...) {0,0}
#define KOKIRI_STREAM_ROOMS 1
#define FOREST_FAR 1310
#define FAIRY_COLMODE_RGB 5
#define FALSE 0
#define JO_TV_WIDTH_2 160
#ifdef DOSEI_HIRES
#define JO_TV_HEIGHT_2 240
#else
#define JO_TV_HEIGHT_2 120
#endif
gameplay_t gameplay;
static struct { int x,y,z; } demo_camera;
static int forest_room;
static unsigned int rupee_sprite[2]={40,41}, digit_sprite[10]={50,51,52,53,54,55,56,57,58,59};
static unsigned int kokiri_rejected, count, hud_count;
static FIXED positions[64][5], hud[3][5];
static Uint16 textures[64], hud_tex[3];
bool gameplay_rupee_taken(unsigned int i) { return gameplay.rupee_taken & (1u<<i); }
bool gameplay_is_talking(void) { return gameplay.talking; }
static int slPutSprite(FIXED *p, SPR_ATTR *a, int angle) {
 memcpy(positions[count],p,5*sizeof(FIXED)); textures[count++]=a->texno; return 1;
}
static int slDispSprite(FIXED *p, SPR_ATTR *a, int angle) {
 /* Actual SGL 3.02j SpriteEntry: reject z <= (240 >> 3). The old mock
  * accepted depth 1 and hid the missing HUD bug. */
 if (p[2] <= 30 * 65536) return 0;
 memcpy(hud[hud_count],p,5*sizeof(FIXED)); hud_tex[hud_count++]=a->texno; return 1;
}
"""
        adapter += r"""
static int slDispSpriteHV(FIXED *p, SPR_ATTR *a, int angle) {
 if (!angle) return 0; /* SDK notes a zero-angle bug for unequal scaling. */
 return slDispSprite(p,a,angle);
}
"""
        wrapper = r"""
void reset(void) { memset(&gameplay,0,sizeof(gameplay)); count=hud_count=0; }
int draw(int room, int x, int z, unsigned int removed) {
 forest_room=room; demo_camera.x=x; demo_camera.z=z; gameplay.rupee_taken=removed;
 count=0; kokiri_rupees_draw(0); return count;
}
void drop(unsigned int i, unsigned int value, unsigned int age) {
 gameplay.grass_rupee[i]=value; gameplay.grass_age[i]=age;
}
int coord(unsigned int i,unsigned int axis) { return positions[i][axis]; }
int tex(unsigned int i) { return textures[i]; }
int draw_hud(unsigned int amount,int talking) {
 gameplay.rupees=amount; gameplay.talking=talking; hud_count=0;
 kokiri_rupee_hud_draw(); return hud_count;
}
int hud_texture(unsigned int i) { return hud_tex[i]; }
int hud_coord(unsigned int i,unsigned int axis) { return hud[i][axis]; }
"""
        out=Path(cls.tmp.name)/'rupees.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'build/generated'),'-I'+str(ROOT/'src'),
                        '-x','c','-',str(ROOT/'build/generated/kokiri_actors.c'),'-o',str(out)],
                       input=adapter+body+wrapper,text=True,env=env,check=True)
        cls.lib=ctypes.CDLL(str(out))
        out_hi=Path(cls.tmp.name)/'rupees-hires.dll'
        subprocess.run([str(GCC),'-shared','-O2','-DDOSEI_HIRES',
                        '-I'+str(ROOT/'build/generated'),'-I'+str(ROOT/'src'),
                        '-x','c','-',str(ROOT/'build/generated/kokiri_actors.c'),'-o',str(out_hi)],
                       input=adapter+body+wrapper,text=True,env=env,check=True)
        cls.lib_hi=ctypes.CDLL(str(out_hi))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self): self.lib.reset()

    def test_placed_rupees_use_room_colour_and_taken_state(self):
        self.assertEqual(self.lib.draw(0,0,0,0),6)
        self.assertEqual(self.lib.tex(0),40)
        self.assertEqual(self.lib.tex(4),41)
        self.assertEqual(self.lib.coord(0,0),-537*65536)
        self.assertEqual(self.lib.draw(0,0,0,1),5)
        self.assertEqual(self.lib.draw(1,0,0,0),0)
        self.assertEqual(self.lib.draw(2,-800,1500,0),2)
        self.assertEqual(self.lib.draw(0,5000,5000,0),0)

    def test_grass_drops_hidden_until_spawn_then_hop(self):
        self.assertEqual(self.lib.draw(0,-800,650,65535),0)
        self.lib.drop(0,1,0)
        self.assertEqual(self.lib.draw(0,-800,650,65535),1)
        base=self.lib.coord(0,1)
        self.lib.drop(0,1,7)
        self.lib.draw(0,-800,650,65535)
        self.assertLess(self.lib.coord(0,1),base)
        self.lib.drop(0,0,15)
        self.assertEqual(self.lib.draw(0,-800,650,65535),0)

    def test_hud_uses_original_screen_positions_and_two_digits(self):
        self.assertEqual(self.lib.draw_hud(5,0),3)
        self.assertEqual([self.lib.hud_texture(i) for i in range(3)],[40,50,55])
        self.assertGreater(self.lib.hud_coord(0,2),30*65536)
        self.assertEqual(self.lib.hud_coord(0,0),(26-160+8)*65536)
        self.assertEqual(self.lib.hud_coord(0,1),(206-120+8)*65536)
        self.lib.draw_hud(99,0)
        self.assertEqual([self.lib.hud_texture(i) for i in (1,2)],[59,59])
        self.assertEqual(self.lib.draw_hud(99,1),0)

    def test_hires_hud_keeps_logical_position_and_doubles_height(self):
        self.lib_hi.reset()
        self.assertEqual(self.lib_hi.draw_hud(5,0),3)
        self.assertEqual(self.lib_hi.hud_coord(0,0),(26-160+8)*65536)
        self.assertEqual(self.lib_hi.hud_coord(0,1),(206*2-240+16)*65536)
        self.assertEqual(self.lib_hi.hud_coord(0,3),65536)
        self.assertEqual(self.lib_hi.hud_coord(0,4),2*65536)
