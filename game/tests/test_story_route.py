"""Drive production story ownership and owl progression with platform-only stubs."""
import ctypes,os,re,shutil,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
GCC=Path(shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class StoryRoute(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  source=(ROOT/'src/story_route.c').read_text()
  source=source.split('void story_route_draw(')[0]+source[source.index('/* OnePoint 8700'):]
  source=re.sub(r'^#include.*$','',source,flags=re.M)
  pre=r'''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <math.h>
#include "save_state.h"
#include "actor_sys.h"
#include "cutscenes.h"
#include "song_ids.h"
#include "npc_sprite.h"
typedef struct {int x,y,z;} camera_position_t;
typedef struct {int dummy;} actor_mesh_t;
static actor_t actor;
static camera_position_t recomp_link,recomp_camera;
static unsigned recomp_link_yaw;
static uint16_t recomp_yaw;
static int32_t recomp_pitch;
#define RECOMP_LINK_EYE_HEIGHT 90
static unsigned cs,playing,starts,fail_load,fail_start,errors,clock_tick,song,flaps;
static bool source_owl;
static bool oot_core_owns_owl(void){return source_owl;}
static struct {bool talking;} gameplay;
static unsigned char sheets[8],live[8];
static unsigned null_frees,invalid_frees;
unsigned char *npc_sprite_load(const char *s){
 (void)s;if(fail_load)return 0;
 for(unsigned i=0;i<8;++i)if(!live[i]){live[i]=1;return &sheets[i];}
 return 0;
}
static void jo_free(void *m){
 if(!m){++null_frees;return;}
 for(unsigned i=0;i<8;++i)if(m==&sheets[i]){
  if(!live[i])++invalid_frees;else live[i]=0;return;
 }
 ++invalid_frees;
}
actor_t *actor_resolve(actor_handle_t h){return h && actor.profile?&actor:0;}
void actor_kill(actor_t *a){if(a)a->profile=0;}
actor_handle_t actor_handle(const actor_t *a){return a?1:0;}
actor_t *actor_spawn(const actor_profile_t *p,unsigned s,int r,int32_t x,int32_t y,int32_t z,uint16_t yaw,uint16_t param){
 (void)s;(void)r;(void)yaw;(void)param;actor.profile=p;actor.flags=p->flags;actor.x=x;actor.y=y;actor.z=z;return &actor;}
static bool cutscene_start_in_scene(unsigned id){if(fail_start)return false;cs=id;playing=true;++starts;return true;}
static unsigned cutscene_id(void){return cs;}
static bool cutscene_is_playing(void){return playing;}
static bool gameplay_blocks_world(void){return gameplay.talking;}
static bool gameplay_is_talking(void){return gameplay.talking;}
static bool gameplay_actor_message(unsigned id){(void)id;gameplay.talking=true;return true;}
static void music_play(unsigned s){song=s;}
static unsigned recomp_clock(void){return clock_tick;}
static void jo_core_error(const char *s){(void)s;++errors;}
static void action_audio_owl_flap(void){++flaps;}
static void kokiri_camera_sincos(unsigned y,int32_t *s,int32_t *c){
 double angle=(uint16_t)y*(6.283185307179586/65536.0);
 *s=lround(sin(angle)*65536.0);*c=lround(cos(angle)*65536.0);
}
static uint16_t collide_heading(int32_t x,int32_t z){return (uint16_t)lround(atan2(x,z)*(65536.0/6.283185307179586));}
static uint32_t collide_isqrt(uint32_t v){return (uint32_t)sqrt(v);}
static void npc_smooth_step(int16_t *v,int16_t t,int a,int b,int c){(void)a;(void)b;(void)c;*v=t;}
'''
  post=r'''
void reset(void){story_route_free();source_owl=false;save_new_game();cs=playing=starts=fail_load=fail_start=errors=clock_tick=song=flaps=0;gameplay.talking=false;memset(&actor,0,sizeof(actor));recomp_link=(camera_position_t){4284,90,7600};recomp_camera=(camera_position_t){4284,600,7200};recomp_link_yaw=0;}
void admit_owl(int admitted){source_owl=admitted;}
int load(int scene,int fail){fail_load=fail;save_state.scene_id=scene;return story_route_load(scene);}
void arrive(int spawn,int fail){fail_start=fail;story_route_arrive(spawn);}
void finish(void){playing=0;story_route_finish();}
void close_text(void){gameplay.talking=false;}
void tick(void){clock_tick+=2;story_route_step();}
void camera_frame(unsigned frame){clock_tick=talk_started+frame*3;story_owl_camera();}
void link_position(int x,int z,unsigned yaw){recomp_link.x=x;recomp_link.z=z;recomp_link_yaw=yaw;}
int camera_value(unsigned n){switch(n){case 0:return recomp_camera.x;case 1:return recomp_camera.y;case 2:return recomp_camera.z;case 3:return talk_at[0];case 4:return talk_at[1];case 5:return talk_at[2];case 6:return owl_yaw;case 7:return actor.yaw;case 8:return story_owl_screen_distance();default:return recomp_yaw;}}
unsigned cleanup_errors(void){return null_frees+invalid_frees;}
unsigned live_allocations(void){unsigned n=0;for(unsigned i=0;i<8;++i)n+=live[i];return n;}
int value(int n){switch(n){case 0:return cs;case 1:return starts;case 2:return errors;case 3:return gameplay.talking;case 4:return owl_phase;case 5:return song;case 6:return save_state.fairy_ocarina;case 7:return flaps;default:return 0;}}
'''
  cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);dll=Path(cls.tmp.name)/'story.dll'
  env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
  subprocess.run([str(GCC),'-shared','-fPIC','-O2','-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),'-x','c','-',str(ROOT/'src/save_state.c'),'-o',str(dll),'-lm'],input=pre+source+post,text=True,check=True,env=env)
  cls.lib=ctypes.CDLL(str(dll))
  for name in ('save_get_event_chk_inf','save_get_switch'):getattr(cls.lib,name).restype=ctypes.c_bool
 def setUp(self):self.lib.reset()
 def tearDown(self):
  self.lib.story_route_free()
  self.lib.story_route_free()
  self.assertEqual(self.lib.cleanup_errors(),0)
  self.assertEqual(self.lib.live_allocations(),0)
 def test_bridge_requires_boss_reward_and_correct_entrance(self):
  g=self.lib;g.load(1,0);g.arrive(9,0);self.assertEqual(g.value(1),0)
  g.save_give_quest_item(18);g.arrive(8,0);self.assertEqual(g.value(1),0)
  g.arrive(9,0);self.assertEqual(g.value(0),9);self.assertEqual(g.value(6),0)
  g.finish();self.assertEqual(g.value(6),1);self.assertTrue(g.save_get_event_chk_inf(0xC1))
  g.arrive(9,0);self.assertEqual(g.value(1),1)
 def test_source_admitted_owl_has_no_host_actor_or_assets(self):
  g=self.lib;g.admit_owl(1);self.assertTrue(g.load(10,0));g.tick()
  self.assertEqual(g.live_allocations(),0);self.assertEqual(g.value(4),0)
  g.admit_owl(0);self.assertTrue(g.load(10,0));self.assertEqual(g.live_allocations(),2)
 def test_failed_bridge_start_does_not_grant_item_or_flag(self):
  g=self.lib;g.load(1,0);g.save_give_quest_item(18);g.arrive(9,1)
  self.assertEqual(g.value(2),1);self.assertEqual(g.value(6),0);self.assertFalse(g.save_get_event_chk_inf(0xC1))
 def test_field_intro_holds_owl_then_completion_prevents_replay(self):
  g=self.lib;g.load(10,0);g.arrive(3,0);g.tick()
  self.assertEqual(g.value(0),10);self.assertEqual(g.value(3),0)
  g.finish();self.assertTrue(g.save_get_event_chk_inf(0xA0));g.arrive(3,0);self.assertEqual(g.value(1),1)
  g.tick();self.assertEqual(g.value(3),1);self.assertEqual(g.value(5),90)
 def test_owl_departure_persists_and_plays_wings(self):
  g=self.lib;g.load(10,0);g.tick();self.assertTrue(g.save_get_event_chk_inf(0x6F))
  self.assertFalse(g.save_get_switch(10,12));g.close_text();g.tick();self.assertTrue(g.save_get_switch(10,12))
  for _ in range(140):g.tick()
  self.assertEqual(g.value(4),5);self.assertGreater(g.value(7),0)
  g.story_route_free();g.load(10,0);g.tick();self.assertEqual(g.value(4),0)
 def test_missing_owl_asset_refuses_scene_initialization(self):self.assertFalse(self.lib.load(10,1))
 def camera_pose(self):return tuple(self.lib.camera_value(i) for i in range(6))
 def start_owl(self):
  self.lib.load(10,0);self.lib.tick()
  self.assertEqual(self.lib.value(4),2)
 def test_owl_faces_link_before_actor_relative_camera(self):
  g=self.lib
  for x,z,yaw in ((4284,7600,0x8000),(4284,8100,0),(4500,7877,0x4000),(4000,7877,0xc000)):
   g.reset();g.link_position(x,z,0);self.start_owl()
   self.assertEqual(g.camera_value(6),yaw)
   self.assertEqual(g.camera_value(7),yaw)
   g.camera_frame(60)
   # EnOwl's 0x4343 eye lies in front of its face, toward Link.
   dot=(g.camera_value(0)-4284)*(x-4284)+(g.camera_value(2)-7877)*(z-7877)
   self.assertGreater(dot,0)
 def test_first_shot_holds_before_switching_to_owl(self):
  self.start_owl();self.lib.camera_frame(9);first=self.camera_pose()
  self.lib.camera_frame(29);self.assertEqual(self.camera_pose(),first)
  self.assertEqual(self.lib.camera_value(8),120)
  self.lib.camera_frame(30);self.assertNotEqual(self.camera_pose(),first)
  self.assertEqual(self.lib.camera_value(8),257)
 def test_camera_catchup_matches_20hz_at_low_display_rate(self):
  g=self.lib;self.start_owl()
  for frame in range(61):g.camera_frame(frame)
  expected=self.camera_pose()
  g.reset();self.start_owl()
  for frame in range(0,61,6):g.camera_frame(frame)
  self.assertEqual(self.camera_pose(),expected)
  g.reset();self.start_owl();g.camera_frame(60)
  self.assertEqual(self.camera_pose(),expected)
 def test_camera_holds_when_render_repeats_or_dialogue_waits(self):
  self.start_owl();self.lib.camera_frame(60);held=self.camera_pose()
  self.lib.camera_frame(60);self.assertEqual(self.camera_pose(),held)
  self.lib.camera_frame(1000000);self.assertEqual(self.camera_pose(),held)
 def test_closed_owl_dialogue_releases_camera(self):
  self.start_owl();self.lib.camera_frame(35);held=self.camera_pose()
  self.lib.close_text();self.lib.tick();self.lib.camera_frame(60)
  self.assertEqual(self.camera_pose(),held)
if __name__=='__main__':unittest.main()
