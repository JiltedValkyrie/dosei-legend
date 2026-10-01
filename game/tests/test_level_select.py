"""Secret test starts preserve progression puzzles and never write backup RAM."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class LevelSelect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        src=folder/'test.c'
        src.write_text('''#include "level_select.h"
#include "save_state.h"
unsigned scene(void){return level_select.scene;}
unsigned room(void){return level_select.room;}
unsigned kit(void){return save_state.equip_sword && save_state.equip_shield && save_state.slingshot && save_state.ammo_seeds==30 && save_state.stick_ammo==10 && save_state.nut_ammo==10;}
unsigned saved_scene(void){return save_state.scene_id;}
unsigned puzzle_flags(void){return save_state.scene[SAVE_SCENE_DEKU_TREE].clear;}
''')
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        dll=folder/'test.dll'
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Werror','-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            str(src),str(ROOT/'src/level_select.c'),str(ROOT/'src/save_state.c'),str(ROOT/'build/generated/scene_table.c'),'-o',str(dll)],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.save_check_quest_item.restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_room_wrap_and_area_change_reset_room(self):
        g=self.lib;g.level_select_open();self.assertEqual(g.scene(),7)
        g.level_select_move(0,-1);self.assertEqual(g.room(),11)
        g.level_select_move(0,1);self.assertEqual(g.room(),0)
        g.level_select_move(1,0);self.assertEqual((g.scene(),g.room()),(8,0))
        g.level_select_move(1,0);self.assertEqual((g.scene(),g.room()),(9,0))
        g.level_select_move(0,-1);self.assertEqual(g.room(),1)
        g.level_select_move(1,0);self.assertEqual((g.scene(),g.room()),(0,0))
    def test_test_kit_equipped_without_solving_dungeon(self):
        g=self.lib;g.level_select_open();g.level_select_prepare()
        self.assertTrue(g.kit());self.assertEqual(g.saved_scene(),2);self.assertEqual(g.puzzle_flags(),0)
        self.assertFalse(g.save_check_quest_item(18))
