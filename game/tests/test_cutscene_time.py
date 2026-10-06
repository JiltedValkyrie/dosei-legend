"""Original explicit-time truncation and night-advance command boundaries."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_cutscenes as bake

GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class TimeBake(unittest.TestCase):
    def test_separate_truncations_and_minute_increment(self):
        self.assertEqual(bake.cutscene_time(0, 0), 45)
        self.assertEqual(bake.cutscene_time(7, 0), 19159)
        self.assertEqual(bake.cutscene_time(23, 59), 65535)


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class TimeRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'src/cutscene.c').read_text()
        body = source[source.index('static void update_misc('):source.index('\nunsigned int cutscene_shot_key')]
        harness = r'''
#include <stdint.h>
typedef int cutscene_t;
typedef struct { unsigned short scene, frame, value; } cutscene_time_t;
typedef struct { unsigned char scene, kind; short start, end; } cutscene_misc_t;
#define CUTSCENE_TIME_COUNT 1
#define CUTSCENE_MISC_COUNT 2
static cutscene_time_t cutscene_times[1]={{1,5,19159}};
static cutscene_misc_t cutscene_misc[2]={{2,6,10,13},{3,6,10,10}};
static struct { unsigned id, frame, flash, rain, bridge_start; } state;
static struct { uint16_t day_time; } save_state;
static unsigned sky;
static void oot_core_clock_reset(unsigned value) { sky=value; }
''' + body + r'''
void reset(unsigned time) { save_state.day_time=time; sky=60000; }
void frame(unsigned scene,unsigned frame) { state.id=scene;state.frame=frame;update_misc(0); }
unsigned day(void) { return save_state.day_time; }
unsigned skytime(void) { return sky; }
'''
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        dll = Path(cls.temp.name) / 'time.dll'
        subprocess.run([str(GCC), '-shared', '-O2', '-x', 'c', '-', '-o', str(dll)],
                       input=harness, text=True, check=True,
                       env=dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ['PATH']))
        cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):
        del cls.lib
        cls.temp.cleanup()

    def test_explicit_time_sets_both_only_on_start(self):
        p=self.lib; p.reset(100);p.frame(1,4)
        self.assertEqual((p.day(),p.skytime()),(100,60000))
        p.frame(1,5)
        self.assertEqual((p.day(),p.skytime()),(19159,19159))
        p.reset(200);p.frame(1,6)
        self.assertEqual((p.day(),p.skytime()),(200,60000))

    def test_night_range_and_clamp_preserve_sky(self):
        p=self.lib;p.reset(51800)
        for f in range(9,15):p.frame(2,f)
        self.assertEqual((p.day(),p.skytime()),(51882,60000))
        p.reset(65520);p.frame(2,10)
        self.assertEqual(p.day(),14)  # u16 wrap precedes source clamp.

    def test_equal_range_end_is_continuous_as_source(self):
        p=self.lib;p.reset(100);p.frame(3,9);p.frame(3,10);p.frame(3,20)
        self.assertEqual(p.day(),160)


if __name__ == '__main__':
    unittest.main()
