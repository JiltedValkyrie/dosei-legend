"""Secret test starts preserve progression puzzles and never write backup RAM."""
import ctypes as C
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path(shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class LevelSelect(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        (folder/'jo').mkdir()
        (folder/'jo/jo.h').write_text('#include <stdint.h>\n#include <stdbool.h>\n'
            'void *jo_fs_read_file(const char *name,int *length);\n')
        room_header=(ROOT/'build/generated/kokiri_scene.h').read_text()
        portal_type=re.search(r'typedef struct(?: kokiri_portal)? \{[^}]+\} kokiri_portal;',room_header)[0]
        cls.header_portal_count=int(re.search(r'#define KOKIRI_PORTAL_COUNT (\d+)',room_header)[1])
        src=folder/'test.c'
        src.write_text(portal_type+'\n'+'''#include "level_select.h"
#include "save_state.h"
#include "scene_table.h"
#include <string.h>
const kokiri_portal *kokiri_portals;
static void *table_data;
static int table_bytes;
void *jo_fs_read_file(const char *name,int *length){
 if(strcmp(name,"SCENETAB.BIN"))return 0;
 *length=table_bytes;return table_data;
}
int bind_scene_table(void *data,int bytes){table_data=data;table_bytes=bytes;return scene_table_load();}
unsigned portal_size(void){return sizeof(kokiri_portal);}
unsigned portal_offset(void){return (const unsigned char*)kokiri_portals-(const unsigned char*)table_data;}
int portal_field(unsigned index,unsigned field){
 const kokiri_portal *p=&kokiri_portals[index];
 const int values[]={p->front,p->back,p->x,p->y,p->z,p->yaw,p->scene,p->kind,p->flag};
 return field<9?values[field]:-1;
}
unsigned portal_layers(unsigned index){return kokiri_portals[index].layers;}
unsigned page(void){return level_select.page;}
unsigned cursor(void){return level_select.cursor;}
unsigned region(void){return level_select.region;}
unsigned scene(void){return level_select.scene;}
unsigned room(void){return level_select.room;}
unsigned scene_count(void){return SCENE_COUNT;}
unsigned selected_rooms(void){return scene_entries[level_select.scene].rooms;}
unsigned selected_spawns(void){return scene_entries[level_select.scene].spawns;}
unsigned selected_save_scene(void){return scene_entries[level_select.scene].save_scene;}
unsigned entry_size(void){return sizeof(scene_entry_t);}
int selected_entry_field(unsigned field){
 const scene_entry_t *e=&scene_entries[level_select.scene];
 const int values[]={e->image,e->panorama,e->cam_x,e->cam_y,e->cam_z,e->cam_pitch,
 e->cam_yaw,e->cam_fov,e->cam_dist,e->rooms,e->first_spawn,e->spawns,e->save_scene,
 e->sfx_bank,e->seq,e->oot_scene};
 return field<16?values[field]:-1;
}
unsigned selected_spawn_room(unsigned spawn){return scene_spawns[scene_entries[level_select.scene].first_spawn+spawn].room;}
unsigned selected_spawn_scene(unsigned spawn){return scene_spawns[scene_entries[level_select.scene].first_spawn+spawn].scene;}
unsigned kit(void){return save_state.equip_sword && save_state.equip_shield && save_state.slingshot && save_state.ammo_seeds==30 && save_state.stick_ammo==10 && save_state.nut_ammo==10;}
unsigned saved_scene(void){return save_state.scene_id;}
unsigned puzzle_flags(void){return save_state.scene[SAVE_SCENE_DEKU_TREE].clear;}
unsigned boosted(void){return level_select.max_gear;}
unsigned adult(void){return level_select.adult;}
unsigned saved_age(void){return save_state.link_age;}
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
        dll=folder/('test.dll' if os.name=='nt' else 'test.so')
        subprocess.run([str(GCC),'-shared',*(['-fPIC'] if os.name!='nt' else []),'-O2','-Wall','-Werror','-I'+str(folder),'-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),
            str(src),str(ROOT/'src/level_select.c'),str(ROOT/'src/save_state.c'),str(ROOT/'build/generated/scene_table.c'),'-o',str(dll)],check=True,env=env)
        cls.lib=C.CDLL(str(dll))
        cls.lib.save_check_quest_item.restype=C.c_bool
        cls.lib.bind_scene_table.argtypes=[C.c_void_p,C.c_int]
        cls.lib.scene_name.argtypes=[C.c_uint]
        cls.lib.scene_name.restype=C.c_char_p
        cls.lib.portal_layers.restype=C.c_uint
        cls.table=json.loads((ROOT/'build/generated/scene_table.json').read_text())
        cls.disk_blob=(ROOT/'build/cd/SCENETAB.BIN').read_bytes()
        native=bytearray(cls.disk_blob)
        cls.entry_format='BB3h2H2hBxH5Bx'
        cls.portal_format='6h3BxI'
        assert cls.table['layout']['entry_bytes']==struct.calcsize('>'+cls.entry_format)==26
        assert cls.lib.entry_size()==26
        # The shipped blob is native SH-2 big-endian data. Host execution
        # uses the same layouts with entry and portal words byte-swapped.
        for row in cls.table['scenes']:
            offset=cls.table['layout']['entry_offset']+row['index']*26
            fields=struct.unpack_from('>'+cls.entry_format,cls.disk_blob,offset)
            struct.pack_into('='+cls.entry_format,native,offset,*fields)
        cls.disk_portals=[]
        for index in range(cls.table['layout']['portal_count']):
            offset=cls.table['layout']['portal_offset']+index*20
            fields=struct.unpack_from('>'+cls.portal_format,cls.disk_blob,offset)
            cls.disk_portals.append(fields)
            struct.pack_into('='+cls.portal_format,native,offset,*fields)
        cls.table_blob=C.create_string_buffer(bytes(native))
        assert cls.lib.bind_scene_table(cls.table_blob,len(native))
    def test_region_navigation_covers_every_map_once(self):
        g=self.lib
        seen=[]
        for region in range(10):
            g.level_select_open()
            for _ in range(region):g.level_select_step(1,0,0,0)
            self.assertEqual(0,g.level_select_step(0,0,1,0))
            self.assertEqual(1,g.page())
            for index in range(g.level_select_count()):
                seen.append(g.level_select_map(region,index))
                g.level_select_step(0,0,1,0)
                self.assertEqual(seen[-1],g.scene())
                self.assertEqual(2,g.page())
                g.level_select_step(0,0,0,1)
                self.assertEqual(index,g.cursor())
                g.level_select_step(1,0,0,0)
        self.assertEqual(list(range(g.scene_count())),sorted(seen))

    def test_a_toggles_options_then_explicit_begin_or_go_back(self):
        g=self.lib
        g.level_select_open();g.capture()
        g.level_select_step(0,0,1,0);g.level_select_step(0,0,1,0)
        g.level_select_step(1,0,0,0)
        self.assertEqual(0,g.level_select_step(0,0,1,0));self.assertEqual(1,g.adult())
        g.level_select_step(1,0,0,0)
        self.assertEqual(0,g.level_select_step(0,0,1,0));self.assertEqual(1,g.boosted())
        g.level_select_step(1,0,0,0)
        self.assertEqual(1,g.level_select_step(0,0,1,0))
        self.assertEqual(1,g.unchanged())
        g.level_select_step(1,0,0,0)
        self.assertEqual(0,g.level_select_step(0,0,1,0));self.assertEqual(1,g.page())
        g.level_select_step(0,0,0,1);self.assertEqual(0,g.page())
        self.assertEqual(2,g.level_select_step(0,0,0,1))

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
    def test_era_defaults_child_and_applies_only_on_confirm(self):
        g=self.lib;g.save_new_game();g.capture();g.level_select_open()
        self.assertFalse(g.adult());self.assertEqual(g.saved_age(),1)
        g.level_select_toggle_era()
        self.assertTrue(g.adult());self.assertTrue(g.unchanged())
        g.level_select_prepare();self.assertEqual(g.saved_age(),0)
        g.capture();g.level_select_open()
        self.assertFalse(g.adult());self.assertTrue(g.unchanged())
        g.level_select_prepare();self.assertEqual(g.saved_age(),1)

    def test_every_registered_row_has_label_valid_spawns_and_reachable_rooms(self):
        g=self.lib
        g.level_select_open()
        first=g.scene();seen=set()
        summaries={row['index']:row for row in self.table['scenes']}
        self.assertEqual(g.scene_count(),len(summaries))
        for _ in range(g.scene_count()):
            scene=g.scene()
            self.assertNotIn(scene,seen);seen.add(scene)
            label=g.scene_name(scene).decode('ascii')
            self.assertTrue(label.strip(),scene)
            offset=self.table['layout']['entry_offset']+scene*26
            expected=struct.unpack_from('>'+self.entry_format,self.disk_blob,offset)
            self.assertEqual(tuple(g.selected_entry_field(i) for i in range(16)),expected,label)
            rooms=g.selected_rooms();self.assertGreater(rooms,0,label)
            self.assertEqual(rooms,summaries[scene]['rooms'],label)
            self.assertEqual(g.selected_save_scene(),summaries[scene]['save_scene'],label)
            self.assertEqual(g.selected_spawns(),summaries[scene]['spawns'],label)
            self.assertGreater(g.selected_spawns(),0,label)
            spawn_rooms=set()
            for spawn in range(g.selected_spawns()):
                self.assertEqual(g.selected_spawn_scene(spawn),scene,label)
                self.assertLess(g.selected_spawn_room(spawn),rooms,label)
                spawn_rooms.add(g.selected_spawn_room(spawn))
            # level_select_enter uses an authored spawn first, then an
            # authored portal position (vertical kind2 has no safe fallback).
            self.assertTrue(0 in spawn_rooms or any(p[6]==scene and 0 in p[:2] and p[7]!=2
                                                   for p in self.disk_portals),label)
            g.level_select_move(0,-1);self.assertEqual(g.room(),rooms-1,label)
            g.level_select_move(0,1);self.assertEqual(g.room(),0,label)
            for room in range(rooms):
                self.assertEqual(g.room(),room,label)
                g.level_select_move(0,1)
            self.assertEqual(g.room(),0,label)
            g.level_select_prepare();self.assertEqual(g.saved_scene(),g.selected_save_scene(),label)
            g.level_select_move(1,0);self.assertEqual(g.room(),0,label)
        self.assertEqual((g.scene(),len(seen)),(first,g.scene_count()))

    def test_relocated_portals_preserve_every_record_and_pointer(self):
        g=self.lib;layout=self.table['layout']
        self.assertEqual(layout['portal_bytes'],struct.calcsize('>'+self.portal_format))
        self.assertEqual(g.portal_size(),20)
        self.assertEqual(g.portal_offset(),layout['portal_offset'])
        self.assertEqual(g.portal_offset()%4,0)
        self.assertEqual(self.header_portal_count,max(1,len(self.disk_portals)))
        rooms=json.loads((ROOT/'build/generated/rooms_manifest.json').read_text())
        fields=('front','back','x','y','z','yaw','scene','kind','flag','layers')
        self.assertEqual(self.disk_portals,[tuple(p[k] for k in fields) for p in rooms['portals']])
        for index,expected in enumerate(self.disk_portals):
            actual=tuple(g.portal_field(index,k) for k in range(9))+(g.portal_layers(index),)
            self.assertEqual(actual,expected,index)

    def test_portals_match_independent_source_transition_records(self):
        oot=Path(os.environ.get('DOSEI_OOT',str(ROOT.parents[2]/'game-decomps/n64/oot')))
        config=oot/'baseroms/ntsc-1.2'
        if not config.is_dir():self.skipTest('local retail source required')
        # Reuse only the established segment/header readers, not the transition
        # converter or either table generator. Decode the source actor records.
        sys.path.insert(0,str(ROOT/'tools'))
        from build_actor_manifest import header,alt_headers,layer_header
        from extract_title_source import yaz0
        rom=None
        for candidate in config.glob('*.z64'):
            data=candidate.read_bytes()
            if hashlib.md5(data).hexdigest()=='57a9719ad547c516342e1a15d5c28c3d':
                rom=data;break
        if rom is None:self.skipTest('verified US 1.2 ROM required')
        dma=int(re.search(r'dmadata_start: (\w+)',(config/'config.yml').read_text())[1],16)
        with (config/'segments.csv').open() as source:
            segments={row['Name']:i for i,row in enumerate(csv.DictReader(source))}
        expected={}
        for scene in self.table['scenes']:
            index=segments[scene['prefix']+'_scene']
            start,end,physical,packed_end=struct.unpack_from('>4I',rom,dma+index*16)
            data=yaz0(rom[physical:packed_end]) if packed_end else rom[physical:physical+end-start]
            self.assertEqual(len(data),end-start)
            main=header(data,0,2)
            for layer in range(max(4,len(alt_headers(data,main,2))+1)):
                offset,_=layer_header(data,main,2,layer)
                for command,count,address in header(data,offset,2):
                    if command!=0x0e:continue
                    for i in range(count):
                        front,_,back,_,actor,x,y,z,yaw,params=struct.unpack_from('>4b5hH',data,(address&0xffffff)+i*16)
                        if not all(-1<=side<scene['rooms'] for side in (front,back)):continue
                        kind={9:24+((params>>7)&7),46:8+((params>>6)&15),35:(params>>6)&7}.get(actor,255)
                        key=(front,back,x,y,z,yaw,scene['index'],kind,params&(127 if actor==9 else 63))
                        expected[key]=expected.get(key,0)|(1<<layer)
        actual={}
        for record in self.disk_portals:
            self.assertNotIn(record[:-1],actual,record)
            actual[record[:-1]]=record[-1]
        self.assertEqual(actual,expected)
