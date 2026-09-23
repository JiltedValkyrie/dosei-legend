"""Execute the real bank-swap wait against delayed and stuck VDP1 draws."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host GCC required')
class DrawWait(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        source = re.sub(r'^#include .*$', '', (ROOT / 'src/vdp1_draw_wait.h').read_text(), flags=re.M)
        fixture = '''
#include <stdbool.h>
static unsigned int reads, ready_at, tick, step;
unsigned int demo_clock(void) { unsigned int now=tick; tick+=step; return now; }
static unsigned int status(void) { ++reads; return ready_at && reads>=ready_at ? 2 : 0; }
#define JO_VDP1_EDSR status()
'''
        fixture += source + '''
int run(unsigned int ready, unsigned int clock_step, unsigned int initial) {
    reads=0; ready_at=ready; tick=initial; step=clock_step;
    return vdp1_wait_for_draw_end();
}
unsigned int count(void) { return reads; }
'''
        dll = Path(cls.temp.name) / 'draw_wait.dll'
        subprocess.run([str(GCC), '-shared', '-O2', '-x', 'c', '-', '-o', str(dll)],
                       input=fixture, text=True, check=True,
                       env=dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ['PATH']))
        cls.lib = ctypes.CDLL(str(dll))
        cls.lib.run.argtypes = [ctypes.c_uint] * 3
        cls.lib.count.restype = ctypes.c_uint

    @classmethod
    def tearDownClass(cls):
        from _ctypes import FreeLibrary
        FreeLibrary(cls.lib._handle)
        cls.lib = None
        cls.temp.cleanup()

    def test_already_done(self):
        self.assertEqual(self.lib.run(1, 0, 0), 1)
        self.assertEqual(self.lib.count(), 1)

    def test_busy_at_callback_entry_can_complete_without_another_draw(self):
        self.assertEqual(self.lib.run(100, 0, 0), 1)
        self.assertEqual(self.lib.count(), 100)

    def test_stuck_draw_times_out_in_two_ticks(self):
        self.assertEqual(self.lib.run(0, 1, 0), 0)
        self.assertEqual(self.lib.count(), 2)

    def test_tick_wrap_does_not_extend_timeout(self):
        self.assertEqual(self.lib.run(0, 1, 0xffffffff), 0)
        self.assertEqual(self.lib.count(), 2)

    def test_stopped_clock_still_has_finite_wait(self):
        self.assertEqual(self.lib.run(0, 0, 0), 0)
        self.assertEqual(self.lib.count(), 1048576)
