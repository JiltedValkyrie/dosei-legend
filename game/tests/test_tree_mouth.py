"""Production mouth state: source trigger, retry targeting and timed collision motion."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')
@unittest.skipUnless(GCC.exists(),'host compiler required')
class TreeMouth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source=(ROOT/'src/tree_mouth.c').read_text(encoding='utf-8').replace('#include <jo/jo.h>','').replace('#include "kokiri_sgl.h"','')
        pre=r'''#include <string.h>
#include "actor_sys.h"
#include "recomp.h"
#include "gameplay.h"
#include "save_state.h"
#include "cutscene.h"
#include "kokiri_collision.h"
static actor_t actor;
static unsigned clock_tick,room=1,frame,csid,starts,flags;
static bool playing;
static bg_vec_t placed;
camera_position_t recomp_link;
uint16_t recomp_link_yaw;
gameplay_t gameplay;
save_state_t save_state;
unsigned kokiri_scene_room(void) {return room;}
unsigned recomp_clock(void) {return clock_tick;}
void action_audio_tree_open(void) {}
void jo_core_error(const char *s) {(void)s;}
bool gameplay_blocks_world(void) {return false;}
bool cutscene_is_playing(void) {return playing;}
bool cutscene_is_in_scene(void) {return true;}
unsigned cutscene_id(void) {return csid;}
unsigned cutscene_frame(void) {return frame;}
bool cutscene_start_in_scene(unsigned id) {csid=id;playing=true;++starts;return true;}
int32_t cutscene_link_x(void) {return recomp_link.x;}
int32_t cutscene_link_y(void) {return recomp_link.y-RECOMP_LINK_EYE_HEIGHT;}
int32_t cutscene_link_z(void) {return recomp_link.z;}
uint16_t cutscene_link_yaw(void) {return 0;}
bool save_get_event_chk_inf(unsigned f) {return (flags&(1u<<f))!=0;}
void save_set_event_chk_inf(unsigned f) {flags|=1u<<f;}
uint16_t collide_heading(int32_t x,int32_t z) {(void)x;return z<0?0x8000:0;}
actor_t *actor_resolve(actor_handle_t h) {return h && actor.profile?&actor:0;}
actor_handle_t actor_handle(const actor_t *a) {return a?1:0;}
actor_t *actor_spawn(const actor_profile_t *p,unsigned s,int r,int32_t x,int32_t y,int32_t z,uint16_t yaw,uint16_t param) {
 (void)s;(void)r;(void)yaw;(void)param;memset(&actor,0,sizeof(actor));actor.profile=p;actor.x=x;actor.y=y;actor.z=z;return &actor;
}
void actor_kill(actor_t *a) {if(a)a->profile=0;}
unsigned bg_dyna_register(const bg_mesh_t *m,unsigned flags) {(void)m;(void)flags;return 0;}
void bg_dyna_remove(unsigned id) {(void)id;}
void bg_dyna_set(unsigned id,const bg_vec_t *p,uint16_t yaw,int32_t scale) {(void)id;(void)yaw;(void)scale;placed=*p;}
'''
        post=r'''
void reset(void) {tree_mouth_reset();flags=clock_tick=starts=frame=0;room=1;playing=false;gameplay.target=0;save_state.scene_id=SAVE_SCENE_KOKIRI_FOREST;recomp_link.x=2800;recomp_link.y=90;recomp_link.z=-600;}
void tick(void) {clock_tick+=3;tree_mouth_step();}
void finish(void) {playing=false;}
void target(void) {gameplay.target=1;}
unsigned start_count(void) {return starts;}
unsigned current(void) {return csid;}
void begin_open(void) {save_set_event_chk_inf(EVENTCHKINF_DEKU_TREE_MOUTH_OPEN);csid=CUTSCENE_TREE_OPEN;frame=20;playing=true;}
int y(void) {return placed.y;}
'''
        path=Path(cls.tmp.name)/'tree.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-Os','-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),'-I'+str(ROOT.parent/'shared/lib/collision'),'-I'+str(ROOT.parent/'shared/lib/camera'),'-x','c','-','-o',str(path)],input=pre+source+post,text=True,check=True,env=env)
        cls.lib=C.CDLL(str(path))
    def setUp(self):self.lib.reset()
    def test_first_meeting_auto_then_retry_requires_target(self):
        g=self.lib;g.tick();self.assertEqual(g.start_count(),1);self.assertEqual(g.current(),5)
        g.finish();g.tick();self.assertEqual(g.start_count(),1)
        g.target();g.tick();self.assertEqual(g.start_count(),2);self.assertEqual(g.current(),6)
    def test_mouth_moves_collision_over_100_original_ticks(self):
        g=self.lib;g.tick();self.assertEqual(g.y(),136)
        g.begin_open();g.tick();self.assertEqual(g.y(),136)
        for _ in range(50):g.tick()
        self.assertEqual(g.y(),-63)
        g.finish()
        for _ in range(50):g.tick()
        self.assertEqual(g.y(),-263)
        self.assertEqual(g.start_count(),1)
if __name__=='__main__':unittest.main()
