"""Fixed-step attack edge ownership, including cancellation across UI/actions."""
import ctypes
import os
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class CombatInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = pathlib.Path(cls.tmp.name) / 'input.c'
        source.write_text('''#include "combat_input.h"
static combat_input_t input;
void reset(void) { input = (combat_input_t){0}; }
void feed(int p,int h,int r,int b) { combat_input_feed(&input,p,h,r,b); }
void cancel(void) { combat_input_cancel(&input); }
int take(void) { combat_buttons_t b=combat_input_take(&input);
 return b.pressed | (b.held<<1) | (b.released<<2); }
int allowed(int state) { return combat_input_land_allowed(state); }
''')
        output = source.with_suffix('.dll')
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-Werror',
                        '-I'+str(ROOT/'src'), str(source), '-o', str(output)], check=True, env=env)
        cls.lib = ctypes.CDLL(str(output))
    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
    def setUp(self):
        self.lib.reset()
    def test_tap_between_steps_keeps_both_edges(self):
        self.lib.feed(1,1,0,0)
        self.lib.feed(0,0,1,0)
        self.assertEqual(self.lib.take(),5)
        self.assertEqual(self.lib.take(),0)
    def test_catchup_steps_keep_hold_without_repeating_press(self):
        self.lib.feed(1,1,0,0)
        self.assertEqual(self.lib.take(),3)
        self.assertEqual(self.lib.take(),2)
    def test_blocked_tap_does_not_escape_menu(self):
        self.lib.feed(1,0,1,1)
        self.lib.feed(0,0,0,0)
        self.assertEqual(self.lib.take(),0)
    def test_cancelled_hold_requires_release_then_new_press(self):
        self.lib.feed(1,1,0,0)
        self.lib.cancel()
        self.lib.feed(0,1,0,0)
        self.assertEqual(self.lib.take(),0)
        self.lib.feed(0,0,1,0)
        self.assertEqual(self.lib.take(),0)
        self.lib.feed(1,1,0,0)
        self.assertEqual(self.lib.take(),3)
    def test_release_in_menu_rearms_next_press(self):
        self.lib.feed(1,1,0,1)
        self.lib.feed(0,0,1,1)
        self.lib.feed(1,1,0,0)
        self.assertEqual(self.lib.take(),3)
    def test_traversal_owns_pose_water_owns_stroke(self):
        for state in (8,9,10,11,12,13,15,16,17,18,19):
            self.assertFalse(self.lib.allowed(state),state)
        for state in (0,1,2,3,4,5,6,7,14):
            self.assertTrue(self.lib.allowed(state),state)
