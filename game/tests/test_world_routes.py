"""Shared source gate policy, Ranch doors/returns and complete entrance metadata."""
import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_room_scene as rooms
import build_scene_table as scenes
OOT=Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')
GXX=shutil.which('g++') or ('C:/msys64/mingw64/bin/g++.exe' if Path('C:/msys64/mingw64/bin/g++.exe').exists() else None)


@unittest.skipUnless(GXX,'host compiler required')
class SourceGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        text=(ROOT/'oot-core/src/oot_core_api.cpp').read_text()
        start=text.index('static int oot_core_door_action(')
        end=text.index('\nstatic unsigned int oot_core_current_layer',start)
        pre=r'''
#include <stdint.h>
#include <string.h>
#define ARRAY_COUNT(a) (sizeof(a)/sizeof((a)[0]))
#define SCENE_DEKU_TREE_BOSS 17
#define SCENE_SHADOW_TEMPLE_BOSS 24
#define SCENE_GANONS_TOWER 10
#define SCENE_GANONDORF_BOSS 25
#define SCENE_INSIDE_GANONS_CASTLE 13
#define EVENTCHKINF_TALON_RETURNED_FROM_CASTLE 0x14
#define GET_EVENTCHKINF(n) (event_flag)
static int event_flag,flushes,temp_clear;
struct PlayState { int sceneId; struct {struct {int num;}curRoom;}roomCtx;uint32_t swch,clear;};
static PlayState state,*gOotCorePlay=&state;
static struct {struct {unsigned short dayTime;struct {struct {signed char dungeonKeys[19];unsigned char dungeonItems[20];}inventory;}info;}save;}gSaveContext;
static int Flags_GetSwitch(PlayState*p,unsigned f){return f<32 && (p->swch&(1u<<f));}
static void Flags_SetSwitch(PlayState*p,unsigned f){if(f<32)p->swch|=1u<<f;}
static int Flags_GetClear(PlayState*p,unsigned r){return p->clear&(1u<<r);}
static int Flags_GetTempClear(PlayState*,unsigned r){return temp_clear&(1u<<r);}
static void Flags_SetClear(PlayState*p,unsigned r){p->clear|=1u<<r;}
static void save_copy_out(PlayState*){++flushes;}
'''
        post=r'''
extern "C" {
void reset_gate(int scene){memset(&state,0,sizeof(state));memset(&gSaveContext,0,sizeof(gSaveContext));state.sceneId=scene;event_flag=flushes=temp_clear=0;}
int gate(unsigned k,unsigned f,int side,int commit){return oot_core_door_action(k,f,side,commit);}
void set_key(int i,int n){gSaveContext.save.info.inventory.dungeonKeys[i]=n;}
int get_key(int i){return gSaveContext.save.info.inventory.dungeonKeys[i];}
void boss_key(int i){gSaveContext.save.info.inventory.dungeonItems[i]=1;}
void set_event(int n){event_flag=n;}
void set_time(int n){gSaveContext.save.dayTime=n;}
void set_clear(int n){state.clear=n;}
void set_temp_clear(int n){temp_clear=n;}
void set_switch(int n){state.swch=n;}
int flush_count(){return flushes;}
}
'''
        source=folder/'gate.cpp';source.write_text(pre+text[start:end]+post)
        dll=folder/('gate.dll' if os.name=='nt' else 'gate.so')
        env=dict(os.environ,PATH=str(Path(GXX).parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([GXX,'-std=c++11','-shared','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(dll)],check=True,env=env)
        cls.lib=ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def setUp(self):self.lib.reset_gate(3)

    def test_ordinary_handles_and_room_variants(self):
        for kind in (24,26,27,28,31):
            for side in (0,1):self.assertEqual(self.lib.gate(kind,63,side,0),0)

    def test_key_refused_then_consumed_once_and_unlock_persisted(self):
        g=self.lib
        self.assertEqual(g.gate(25,3,0,1),0x203)
        g.set_key(3,2)
        self.assertEqual(g.gate(25,3,0,0),0)
        self.assertEqual(g.get_key(3),2)
        self.assertEqual(g.gate(25,3,0,1),0)
        self.assertEqual(g.get_key(3),1)
        for _ in range(5):self.assertEqual(g.gate(25,3,1,1),0)
        self.assertEqual(g.get_key(3),1)
        self.assertEqual(g.flush_count(),1)

    def test_boss_key_does_not_spend_small_keys_or_open_wrong_side(self):
        g=self.lib;g.set_key(3,2)
        self.assertEqual(g.gate(13,7,0,1),0x204)
        g.boss_key(3)
        self.assertEqual(g.gate(13,7,1,1),0xFF00)
        self.assertEqual(g.gate(13,7,0,1),0)
        self.assertEqual(g.get_key(3),2)

    def test_clear_switch_and_boss_encounter_bars_stay_gated(self):
        g=self.lib
        self.assertEqual(g.gate(9,2,0,0),0xFF00)
        self.assertEqual(g.gate(9,2,1,0),0)
        g.set_clear(1);self.assertEqual(g.gate(9,2,0,0),0)
        self.assertEqual(g.gate(10,2,0,0),0xFF00)
        g.set_switch(4);self.assertEqual(g.gate(10,2,0,0),0)
        for kind in (12,14,16,17,18,20,255):
            for side in (0,1):self.assertEqual(g.gate(kind,0,side,1),0xFF00)

    def test_talon_exception_and_strict_evening_window(self):
        g=self.lib
        self.assertEqual(g.gate(29,0x29,0,0),0)
        g.set_event(1);self.assertEqual(g.gate(29,0x29,0,0),0x229)
        self.assertEqual(g.gate(29,0x28,0,0),0x228)
        for time in (0,0xC000,0xE000,0xFFFF):
            g.set_time(time);self.assertEqual(g.gate(30,0x2A,0,0),0x22A)
        g.set_time(0xC001);self.assertEqual(g.gate(30,0x2A,0,0),0)

    def test_last_enemy_temp_clear_becomes_persistent_once(self):
        g=self.lib;g.set_temp_clear(1)
        self.assertEqual(g.gate(9,0,0,0),0)
        g.set_temp_clear(0)
        self.assertEqual(g.gate(9,0,0,0),0)
        self.assertEqual(g.flush_count(),1)

    def test_ganon_tower_key_uses_tower_not_castle_slot(self):
        g=self.lib;g.reset_gate(25);g.boss_key(13)
        self.assertEqual(g.gate(13,1,0,1),0x204)
        g.boss_key(10);self.assertEqual(g.gate(13,1,0,1),0)


@unittest.skipUnless(OOT.is_dir(),'source extraction required')
class SourceGraph(unittest.TestCase):
    def test_metadata_keeps_every_entrance_including_circle_transitions(self):
        self.assertEqual(set(scenes.entrance_table(OOT)),set(scenes.entrance_metadata(OOT)))

    def test_ranch_handles_all_layers_and_seals(self):
        main=rooms.transitions(OOT,prefix='spot20')
        self.assertEqual([p['kind'] for p in main],[27,27,27])
        all_rows=rooms.transitions(OOT,prefix='spot20',all_layers=True)
        self.assertTrue(any(p['kind']==29 for p in all_rows))
        data=scenes.source.collision_data(scenes.source.extract(OOT,None,prefix='spot20')['spot20_scene'])
        self.assertEqual(sum(scenes.shutter_cap(p,all_rows) for p in data['polys']),6)

    def test_ranch_buildings_and_stable_have_source_roundtrip(self):
        table=scenes.entrance_table(OOT)
        registered={e['scene']:i for i,e in enumerate(scenes.SCENES)}
        rows={}
        for prefix in ('spot20','souko','malon_stable'):
            data=scenes.source.extract(OOT,None,prefix=prefix)[prefix+'_scene']
            rows[prefix]=scenes.scene_doors(0,prefix,data,table,registered,[])
        self.assertTrue(any(d['target_name']=='SCENE_LON_LON_BUILDINGS' for d in rows['spot20']))
        self.assertTrue(any(d['target_name']=='SCENE_STABLE' for d in rows['spot20']))
        for prefix in ('souko','malon_stable'):
            self.assertTrue(any(d['target_name']=='SCENE_LON_LON_RANCH' for d in rows[prefix]))


@unittest.skipUnless(GXX,'host compiler required')
class RuntimeRoundTrips(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        folder=Path(cls.tmp.name)
        flow=(ROOT/'src/scene_flow.c').read_text()
        flow=flow[flow.index('static bool     inside_triangle('):flow.index('\n/*\n** END OF FILE',flow.index('static bool     inside_triangle('))]
        demo=(ROOT/'src/demo.c').read_text()
        start=demo.index('static bool __attribute__((optimize("Os"))) take_door(void)')
        demo=demo[start:demo.index('\n/* Area themes',start)]
        pre=r'''
#include <stdint.h>
#include <stdbool.h>
#define SCENE_COUNT 2
#define SCENE_DOOR_COUNT 2
#define SCENE_ENTRANCE_COUNT 2
#define SCENE_DOOR_HEIGHT 60
#define DEMO_LINK_EYE_HEIGHT 90
#define GAME_MODE_LOADING 2
#define GAME_MODE_PLAY 1
typedef struct {int16_t x[3],z[3],y;uint8_t scene,target,spawn,keep_music;uint16_t entrance;uint32_t layers;}scene_door_t;
typedef struct {unsigned char save_scene,spawns;}scene_entry_t;
typedef struct {unsigned char target,spawn,keep_music;}scene_entrance_t;
static scene_door_t scene_doors[2]={{{-30,30,0},{-10,-10,40},0,0,1,0,1,0,15},{{-30,30,0},{-10,-10,40},0,1,0,0,0,1,15}};
static scene_entry_t scene_entries[2]={{0,1},{1,1}};
static scene_entrance_t scene_entrances[2]={{1,0,1},{0,0,0}};
static struct {int32_t x,y,z;}demo_link;
static unsigned short demo_link_yaw;
static struct {uint8_t scene_id,entrance;uint16_t source_entrance;
    unsigned day_time,link_age,keys,flags;}save_state;
static bool loaded=true,door_armed,can_exit=true;
static unsigned current_scene,music_count,loads,messages,active_layer,fail_load;
static unsigned attempts,resets,errors,mode,placed_scene,placed_spawn,collision_scene,pixels_scene,actor_scene;
static int script=-1;
static unsigned oot_core_scene_layer(void){return active_layer;}
static int oot_core_transition_request(bool consume){int old=script;if(consume)script=-1;return old;}
static bool dungeon_doors_exit_allowed(int32_t,int32_t,int32_t){return can_exit;}
static void game_mode_set(int next){mode=next;}
static unsigned scene_flow_scene(void){return current_scene;}
static bool scene_flow_load(unsigned s,unsigned){
    ++attempts;
    /* Failure occurs after shared storage has already been replaced. */
    current_scene=collision_scene=pixels_scene=actor_scene=s;
    if(fail_load){--fail_load;return false;}
    door_armed=false;++loads;return true;
}
static const scene_entry_t*scene_flow_entry(void){return &scene_entries[current_scene];}
static void kokiri_camera_sincos(unsigned,int32_t*s,int32_t*c){*s=0;*c=65536;}
static void kokiri_collision_move(void*,int32_t,int32_t,int32_t z){demo_link.z+=z;}
static void gameplay_actor_message(unsigned){++messages;}
static void scene_music(void){++music_count;}
static void place_at_spawn(unsigned s,unsigned p){placed_scene=s;placed_spawn=p;demo_link.x=demo_link.z=0;demo_link.y=90;}
static void gameplay_reset(void){++resets;}
static void jo_core_error(const char*){++errors;}
static bool scene_flow_is_interior(void){return false;}
static void interior_camera(void){}
static void story_route_arrive(unsigned){}
'''
        post=r'''
extern "C" {
void reset_routes(){current_scene=music_count=loads=messages=active_layer=0;attempts=resets=errors=0;collision_scene=pixels_scene=actor_scene=0;mode=GAME_MODE_PLAY;placed_scene=placed_spawn=255;save_state={0,0,0x155,0xc123,0,3,0x12345678};door_armed=false;can_exit=true;fail_load=0;script=-1;scene_doors[0].target=1;scene_entrances[0].target=1;demo_link.x=demo_link.z=0;demo_link.y=90;}
int go(int x,int y,int z){demo_link.x=x;demo_link.y=y+90;demo_link.z=z;return take_door();}
unsigned here(){return current_scene;}
unsigned music_calls(){return music_count;}
unsigned load_calls(){return loads;}
unsigned load_attempts(){return attempts;}
unsigned reset_calls(){return resets;}
unsigned error_calls(){return errors;}
unsigned current_mode(){return mode;}
unsigned restored_assets(){return current_scene==collision_scene && current_scene==pixels_scene && current_scene==actor_scene;}
unsigned placed_here(){return placed_scene==current_scene && placed_spawn==save_state.entrance;}
unsigned saved_scene(){return save_state.scene_id;}
unsigned preserved_progress(){return save_state.day_time==0xc123 && !save_state.link_age && save_state.keys==3 && save_state.flags==0x12345678;}
unsigned message_calls(){return messages;}
void exit_open(int yes){can_exit=yes;}
void load_fails(int yes){fail_load=yes;}
void missing_target(){scene_doors[0].target=255;scene_entrances[0].target=255;}
void restore_target(){scene_entrances[0].target=1;}
void request(int entrance){script=entrance;}
void layer(unsigned n){active_layer=n;}
int pending(){return script;}
unsigned saved_source_entrance(){return save_state.source_entrance;}
}
'''
        source=folder/'routes.cpp';source.write_text(pre+flow+demo+post)
        dll=folder/('routes.dll' if os.name=='nt' else 'routes.so')
        env=dict(os.environ,PATH=str(Path(GXX).parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([GXX,'-std=c++11','-shared','-O2','-Wall','-Wextra','-Werror',str(source),'-o',str(dll)],check=True,env=env)
        cls.lib=ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.lib.reset_routes()

    def test_twenty_roundtrips_keep_music_and_block_spawn_bounce(self):
        g=self.lib
        for i in range(40):
            self.assertFalse(g.go(0,0,0),'arrival cannot bounce')
            self.assertFalse(g.go(0,0,-100))
            self.assertTrue(g.go(0,0,0))
            self.assertEqual(g.here(),(i+1)%2)
            self.assertEqual(g.saved_source_entrance(),i%2)
        self.assertEqual(g.load_calls(),40)
        self.assertEqual(g.music_calls(),20)

    def test_closed_handle_height_and_failed_load_do_not_transition(self):
        g=self.lib;g.go(0,0,-100);g.exit_open(0)
        self.assertFalse(g.go(0,0,0));g.exit_open(1)
        self.assertFalse(g.go(0,200,0));g.load_fails(1)
        self.assertTrue(g.go(0,0,0));self.assertEqual(g.here(),0)
        self.assertEqual(g.load_calls(),1)  # source scene was rebuilt
        self.assertEqual(g.load_attempts(),2)
        self.assertTrue(g.restored_assets());self.assertTrue(g.placed_here())
        self.assertEqual(g.saved_scene(),0);self.assertEqual(g.saved_source_entrance(),0x155)
        self.assertTrue(g.preserved_progress())
        self.assertEqual(g.reset_calls(),1);self.assertEqual(g.current_mode(),1)
        self.assertEqual(g.message_calls(),1);self.assertEqual(g.error_calls(),0)
        self.assertFalse(g.go(0,0,0),'recovery spawn cannot bounce back into the failed door')

    def test_failed_scripted_warp_is_consumed_and_does_not_retry_each_step(self):
        g=self.lib;g.request(0);g.load_fails(1)
        self.assertTrue(g.go(0,0,-200))
        self.assertEqual(g.pending(),-1);self.assertEqual(g.here(),0)
        self.assertEqual(g.load_attempts(),2);self.assertEqual(g.load_calls(),1)
        self.assertTrue(g.restored_assets());self.assertTrue(g.placed_here())
        self.assertEqual(g.saved_source_entrance(),0x155);self.assertEqual(g.music_calls(),0)
        self.assertTrue(g.preserved_progress())
        for _ in range(10):self.assertFalse(g.go(0,0,-200))
        self.assertEqual(g.load_attempts(),2)
        # A later explicit request remains usable after the transient failure.
        g.request(0);self.assertTrue(g.go(0,0,-200));self.assertEqual(g.here(),1)
        self.assertEqual(g.saved_source_entrance(),0);self.assertEqual(g.pending(),-1)

    def test_missing_destination_is_explicit_and_script_requests_share_loader(self):
        g=self.lib;g.missing_target();g.go(0,0,-100)
        self.assertTrue(g.go(0,0,0));self.assertEqual(g.message_calls(),1)
        self.assertEqual(g.here(),0);g.restore_target();g.request(0)
        self.assertTrue(g.go(0,0,-200));self.assertEqual(g.here(),1)
        self.assertEqual(g.pending(),-1);self.assertEqual(g.music_calls(),0)
        g.request(9999);self.assertTrue(g.go(0,0,-200))
        self.assertEqual(g.pending(),-1);self.assertEqual(g.message_calls(),2)

    def test_entrance_group_uses_age_time_variant_but_base_bgm_policy(self):
        g=self.lib;g.layer(1);g.request(0)
        self.assertTrue(g.go(0,0,-200))
        self.assertEqual(g.here(),0)  # variant 1, not child-day target 1
        self.assertEqual(g.music_calls(),0)  # base group says keep BGM


if __name__=='__main__':unittest.main()
