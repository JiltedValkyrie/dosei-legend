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
        (folder/'jo').mkdir()
        (folder/'jo/jo.h').write_text('#include <stdint.h>\n#include <stdbool.h>\n'
            'static inline void *jo_fs_read_file(const char *name,int *length){return 0;}\n')
        src=folder/'test.c'
        src.write_text('''#include "level_select.h"
#include "save_state.h"
#include "scene_table.h"
#include <string.h>
unsigned scene(void){return level_select.scene;}
unsigned room(void){return level_select.room;}
unsigned scene_count(void){return SCENE_COUNT;}
unsigned kit(void){return save_state.equip_sword && save_state.equip_shield && save_state.slingshot && save_state.ammo_seeds==30 && save_state.stick_ammo==10 && save_state.nut_ammo==10;}
unsigned saved_scene(void){return save_state.scene_id;}
unsigned puzzle_flags(void){return save_state.scene[SAVE_SCENE_DEKU_TREE].clear;}
unsigned boosted(void){return level_select.max_gear;}
static save_state_t snapshot;
void capture(void){snapshot=save_state;}
unsigned unchanged(void){return !memcmp(&snapshot,&save_state,sizeof(snapshot));}
unsigned progression_unchanged(void){
 return !memcmp(snapshot.event_chk_inf,save_state.event_chk_inf,sizeof(snapshot.event_chk_inf)) &&
 !memcmp(snapshot.item_get_inf,save_state.item_get_inf,sizeof(snapshot.item_get_inf)) &&
 !memcmp(snapshot.inf_table,save_state.inf_table,sizeof(snapshot.inf_table)) &&
 !memcmp(snapshot.scene,save_state.scene,sizeof(snapshot.scene)) &&
 !memcmp(snapshot.generic_scene,save_state.generic_scene,sizeof(snapshot.generic_scene)) &&
 !memcmp(snapshot.skull_flags,save_state.skull_flags,sizeof(snapshot.skull_flags));
}
unsigned max_kit(void){
 unsigned i;
 if(save_state.health!=320 || save_state.health_capacity!=320 || save_state.rupees!=500 ||
    save_state.equip_sword!=1 || save_state.equip_shield!=1 || !save_state.slingshot ||
    save_state.ammo_seeds!=50 || !save_state.stick_owned || save_state.stick_upgrade!=3 ||
    save_state.stick_ammo!=30 || !save_state.nut_owned || save_state.nut_upgrade!=3 ||
    save_state.nut_ammo!=40 || !save_state.fairy_ocarina || save_state.deku_dungeon_items!=3 ||
    save_state.dungeon_items[0]!=6 || save_state.quest_items!=0x00ffffff ||
    save_state.source_equipment!=0x7777 || save_state.source_upgrades!=0x36e4db ||
    save_state.source_magic_level!=2 || save_state.source_magic!=96 ||
    !save_state.source_double_defense || save_state.source_tokens!=100)return 0;
 for(i=0;i<4;++i)if(save_state.bottle_items[i]!=0x14+i)return 0;
 for(i=1;i<SAVE_DUNGEON_ITEMS_COUNT;++i)if(save_state.dungeon_items[i]!=7)return 0;
 for(i=0;i<SAVE_DUNGEON_KEYS_COUNT;++i)if(save_state.dungeon_keys[i]!=8)return 0;
 return 1;
}
unsigned basic_hearts(void){return save_state.health==48 && save_state.health_capacity==48;}
''')
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        dll=folder/'test.dll'
        subprocess.run([str(GCC),'-shared','-O2','-Wall','-Werror','-I'+str(folder),'-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
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
        for _ in range(g.scene_count()-9):g.level_select_move(1,0)
        self.assertEqual((g.scene(),g.room()),(0,0))
    def test_test_kit_equipped_without_solving_dungeon(self):
        g=self.lib;g.level_select_open();g.level_select_prepare()
        self.assertTrue(g.kit());self.assertEqual(g.saved_scene(),2);self.assertEqual(g.puzzle_flags(),0)
        self.assertFalse(g.save_check_quest_item(18))
    def test_open_navigation_and_toggle_do_not_change_loaded_state(self):
        g=self.lib;g.save_new_game();g.save_give_quest_item(18);g.save_damage(7);g.capture()
        g.level_select_open();self.assertFalse(g.boosted());self.assertTrue(g.unchanged())
        g.level_select_move(1,1);g.level_select_toggle_max_gear()
        self.assertTrue(g.boosted());self.assertTrue(g.unchanged())
        g.level_select_toggle_max_gear();self.assertFalse(g.boosted());self.assertTrue(g.unchanged())
        g.level_select_toggle_max_gear();g.level_select_open()
        self.assertFalse(g.boosted());self.assertTrue(g.unchanged())
    def test_confirm_yes_caps_supported_kit_without_extra_story_flags(self):
        g=self.lib;g.level_select_open();g.level_select_prepare();g.capture()
        self.assertTrue(g.basic_hearts());self.assertTrue(g.kit())
        g.level_select_toggle_max_gear();self.assertTrue(g.unchanged())
        g.level_select_prepare()
        self.assertTrue(g.max_kit());self.assertTrue(g.progression_unchanged())
        g.capture();g.save_test_max_gear()
        self.assertTrue(g.max_kit());self.assertTrue(g.unchanged())
    def test_confirm_no_keeps_original_basic_test_kit(self):
        g=self.lib;g.level_select_open();g.level_select_toggle_max_gear();g.level_select_toggle_max_gear()
        g.level_select_prepare()
        self.assertTrue(g.kit());self.assertTrue(g.basic_hearts());self.assertFalse(g.max_kit())
