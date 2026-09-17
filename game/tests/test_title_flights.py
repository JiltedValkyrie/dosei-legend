"""Run the actual title-camera C over every frame of the authored flights."""
import ctypes
import math
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'native GCC required')
class TitleFlights(unittest.TestCase):
    def test_all_flights_travel_without_heading_snaps_or_floor_bob(self):
        subprocess.run([os.sys.executable, str(ROOT/'tools/build_title_paths.py')], check=True)
        source = (ROOT/'src/demo.c').read_text()
        function = source[source.index('static void title_showcase_camera'):source.index('static bool recover_link')]
        adapter = '''
#include <stdint.h>
#include "title_paths.h"
struct { int32_t x,y,z; } demo_camera;
uint16_t demo_yaw;
int32_t demo_pitch;
'''
        adapter += function + '''
void sample(unsigned int tick, int *out) {
 title_showcase_camera(tick);
 out[0]=demo_camera.x; out[1]=demo_camera.y; out[2]=demo_camera.z;
 out[3]=demo_yaw; out[4]=demo_pitch;
}
int shots(void) { return TITLE_SHOT_COUNT; }
int duration(void) { return TITLE_SHOT_TICKS; }
'''
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            dll = Path(tmp)/'flights.dll'
            env = dict(os.environ)
            env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
            subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'build/generated'),
                            '-x','c','-','-o',str(dll)], input=adapter, text=True, check=True, env=env)
            lib = ctypes.CDLL(str(dll))
            self.assertEqual(lib.shots(), 8)
            self.assertEqual(lib.duration(), 600)
            out = (ctypes.c_int*5)()
            subjects = [(-292,58,-430), (45,58,-272), (669,58,521),
                        (853,158,-311), (-10,238,-22), (-608,178,1022),
                        (18,-22,873), (-678,59,-179)]
            for shot in range(lib.shots()):
                previous = None
                first = None
                for tick in range(lib.duration()):
                    lib.sample(shot*lib.duration()+tick, out)
                    current = list(out)
                    if first is None:
                        first = current
                    dx, dy, dz = [subjects[shot][j]-current[j] for j in range(3)]
                    yaw, pitch = [current[j]*math.tau/65536 for j in (3,4)]
                    right = dx*math.cos(yaw)-dz*math.sin(yaw)
                    forward = dx*math.sin(yaw)+dz*math.cos(yaw)
                    depth = forward*math.cos(pitch)+dy*math.sin(pitch)
                    vertical = dy*math.cos(pitch)-forward*math.sin(pitch)
                    self.assertGreater(depth, 0)
                    self.assertAlmostEqual(160+180*right/depth, 60 if shot%2==0 else 260, delta=3)
                    self.assertAlmostEqual(120-180*vertical/depth, 120, delta=3)
                    self.assertLess(current[4], 0, 'must look down, not skim floor')
                    if previous is not None:
                        self.assertLessEqual(abs(current[1]-previous[1]), 1, 'no floor bob')
                        delta = (current[3]-previous[3]+32768)%65536-32768
                        self.assertLessEqual(abs(delta), 50, 'no heading snap within shot')
                        self.assertLessEqual(abs(current[0]-previous[0]), 2)
                        self.assertLessEqual(abs(current[2]-previous[2]), 2)
                    previous = current
                self.assertGreater(math.dist(first[:3], current[:3]), 150,
                                   'must travel, not just swivel in place')
