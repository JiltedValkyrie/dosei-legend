"""Exercise the actual ribbon lifetime and world placement without SGL."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.is_file(), 'host GCC required')
class SwordTrail(unittest.TestCase):
    def test_world_placement_expiry_and_reset(self):
        source = (ROOT / 'src/kokiri_sgl.c').read_text()
        source = source[source.index('/* Four untextured, mesh-transparent'):]
        adapter = r"""
#include <stdint.h>
#include <stdbool.h>
#include <math.h>
typedef int32_t FIXED;
typedef uint16_t ANGLE;
typedef FIXED POINT[3];
typedef struct { FIXED norm[3]; uint16_t Vertices[4]; } POLYGON;
typedef int ATTR;
typedef struct { POINT *p; int n; POLYGON *f; int nbPolygon; ATTR *a; } PDATA;
#define ATTRIBUTE(...) 0
static FIXED slSin(ANGLE a) { return lround(sin(a*6.283185307179586/65536)*65536); }
static FIXED slCos(ANGLE a) { return lround(cos(a*6.283185307179586/65536)*65536); }
static FIXED slMulFX(FIXED a,FIXED b) { return ((int64_t)a*b)>>16; }
static void kokiri_submit_pdata(PDATA *p) { (void)p; }
static void link_anim_blade(int32_t out[2][3]) {
    for (int i=0;i<2;i++) { out[i][0]=i*10*65536; out[i][1]=65536; out[i][2]=0; }
}
"""
        probe = r"""
int faces(void) { return trail_data.nbPolygon; }
int point(int end,int axis) { return trail_points[end][axis]; }
"""
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            output = Path(tmp) / 'trail.dll'
            env = dict(os.environ)
            env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH','')
            subprocess.run([str(GCC), '-shared', '-O2', '-x', 'c', '-', '-lm', '-o', str(output)],
                           input=adapter+source+probe, text=True, env=env, check=True)
            lib = ctypes.CDLL(str(output))
            update = lib.link_anim_trail_update
            update.argtypes = [ctypes.c_int]*4 + [ctypes.c_bool]
            lib.link_anim_trail_reset()
            update(100,20,30,16384,True)
            self.assertEqual(lib.faces(),0)
            self.assertEqual(lib.point(1,0),100*65536)
            self.assertEqual(lib.point(1,1),-21*65536)
            self.assertEqual(lib.point(1,2),20*65536)
            for i in range(4): update(101+i,20,30,0,True)
            self.assertEqual(lib.faces(),4)
            for expected in (3,2,1,0):
                update(105,20,30,0,False)
                self.assertEqual(lib.faces(),expected)
            update(200,20,30,0,True)
            self.assertEqual(lib.faces(),0)  # no bridge across idle gap
            update(201,20,30,0,True)
            self.assertEqual(lib.faces(),1)
            lib.link_anim_trail_reset()
            self.assertEqual(lib.faces(),0)
