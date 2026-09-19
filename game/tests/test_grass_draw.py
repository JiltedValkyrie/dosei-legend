"""Run actual grass submission with a host SGL adapter."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class GrassDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source=(ROOT/'src/kokiri_sgl.c').read_text()
        start=source.index('void                kokiri_grass_draw(void)')
        body=source[start:source.index('/*\n** Pause equipment grid', start)]
        adapter='''
#include <stdint.h>
#include <stdbool.h>
#include "kokiri_actors.h"
typedef int32_t FIXED;
typedef uint16_t Uint16;
typedef struct { Uint16 texno, atrb; } SPR_ATTR;
#define SPR_ATTRIBUTE(...) {0,0}
#define KOKIRI_STREAM_ROOMS 1
#define FOREST_FAR 1310
#define FAIRY_COLMODE_RGB 5
#define FALSE 0
static struct { int x,y,z; } demo_camera;
static int forest_room;
static unsigned int grass_sprite=42, kokiri_rejected, cut, count;
static FIXED positions[32][5];
static bool gameplay_grass_cut(unsigned int i) { return (cut & (1u<<i)) != 0; }
static int slPutSprite(FIXED *p, SPR_ATTR *a, int angle) {
 unsigned int i;
 if(a->texno!=42) return 0;
 for(i=0;i<5;++i) positions[count][i]=p[i];
 ++count; return 1;
}
'''
        wrapper='''
unsigned int draw_grass(int room, unsigned int removed, int x, int z) {
 forest_room=room; cut=removed; count=0; demo_camera.x=x; demo_camera.z=z;
 kokiri_grass_draw(); return count;
}
int coordinate(unsigned int i, unsigned int axis) { return positions[i][axis]; }
'''
        out=Path(cls.temp.name)/'grass.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'build/generated'),'-I'+str(ROOT/'src'),
                        '-x','c','-',str(ROOT/'build/generated/kokiri_actors.c'),'-o',str(out)],
                       input=adapter+body+wrapper,text=True,env=env,check=True)
        cls.lib=ctypes.CDLL(str(out))

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_cut_room_and_distance_visibility(self):
        count=self.lib.draw_grass(0,0,-750,650)
        self.assertGreater(count,0)
        self.assertEqual(self.lib.coordinate(0,0),-835*65536)
        self.assertEqual(self.lib.coordinate(0,1),-(120+20)*65536)
        self.assertEqual(self.lib.draw_grass(0,1,-750,650),count-1)
        self.assertEqual(self.lib.draw_grass(0,0xffff,-750,650),0)
        self.assertEqual(self.lib.draw_grass(1,0,-750,650),0)
        self.assertEqual(self.lib.draw_grass(0,0,5000,5000),0)
