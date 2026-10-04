"""Execute the production title level-select input gate, without asset banks."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class LevelSelectDelay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        demo = (ROOT / 'src/demo.c').read_text()
        start = demo.index('static void __attribute__((optimize("Os"))) file_select_tick(void)')
        # Compile the actual menu branch, stopping before ordinary save slots.
        branch = demo[start:demo.index('    menu_step = menu_dx = menu_dy = menu_page = 0;', start)]
        source = r'''
#include <stdbool.h>
#include "level_select.h"
#include "file_select.h"
level_select_t level_select;
static unsigned ticks,level_select_open_tick;
static int menu_step,menu_dx,menu_dy,menu_page,c_assign,c_use;
static bool interact_pending,cancel_pending,pause_pending;
static int entered,cancelled,moved,toggled,era;
#define GAME_MODE_TITLE 0
#define NA_BGM_TITLE 0
void level_select_move(int y,int x){moved+=y+x;}
void level_select_toggle_max_gear(void){++toggled;}
void level_select_toggle_era(void){++era;}
static void level_select_enter(void){++entered;}
static void game_mode_set(int mode){(void)mode;++cancelled;}
static void player_input_reset(void){}
static void player_input_set_dialogue(bool on){(void)on;}
static void music_play(int song){(void)song;}
''' + branch + '}' + r'''
void reset(unsigned start){level_select.visible=true;level_select_open_tick=ticks=start;
entered=cancelled=moved=toggled=era=0;interact_pending=cancel_pending=pause_pending=false;
menu_step=menu_dx=menu_dy=menu_page=c_assign=c_use=0;}
void press(unsigned elapsed,int confirm,int cancel,int direction){
ticks=level_select_open_tick+elapsed;interact_pending=confirm;cancel_pending=cancel;
menu_dy=direction;file_select_tick();}
void shoulder(unsigned elapsed,int page){ticks=level_select_open_tick+elapsed;menu_page=page;file_select_tick();}
int result(int kind){return kind==0?entered:kind==1?cancelled:kind==2?moved:kind==3?toggled:era;}
'''
        out = Path(cls.tmp.name) / 'delay.dll'
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'src'),
                        '-x', 'c', '-', '-o', str(out)], input=source, text=True,
                       check=True, env=env)
        cls.lib = ctypes.CDLL(str(out))
        cls.lib.reset.argtypes = [ctypes.c_uint]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_early_inputs_discarded_then_navigation_and_confirm_work_at_150(self):
        g = self.lib
        g.reset(1000)
        for elapsed in (0, 60, 149):
            g.press(elapsed, 1, 1, 1)
            self.assertEqual([g.result(i) for i in range(3)], [0, 0, 0])
        g.press(150, 0, 0, 0)
        self.assertEqual([g.result(i) for i in range(3)], [0, 0, 0])
        g.press(150, 0, 0, 1)
        g.press(151, 1, 0, 0)
        self.assertEqual((g.result(0), g.result(2)), (1, 1))

    def test_cancel_at_deadline_and_timer_wrap(self):
        g = self.lib
        g.reset(0xfffffff0)
        g.press(149, 0, 1, 0)
        self.assertEqual(g.result(1), 0)
        g.press(150, 0, 1, 0)
        self.assertEqual(g.result(1), 1)

    def test_shoulder_toggles_only_after_delay_without_moving_scene_or_entering(self):
        g = self.lib
        g.reset(0)
        g.shoulder(149,1)
        self.assertEqual([g.result(i) for i in range(4)], [0,0,0,0])
        g.shoulder(150,0)
        self.assertEqual(g.result(3),0)
        g.shoulder(151,1)
        self.assertEqual([g.result(i) for i in range(5)], [0,0,0,0,1])
        g.shoulder(152,-1)
        self.assertEqual([g.result(i) for i in range(5)], [0,0,0,1,1])


if __name__ == '__main__':
    unittest.main()
