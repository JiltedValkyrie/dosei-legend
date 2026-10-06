"""Permanent shot skip: real VBlank input and production seek/cleanup code."""
import ctypes
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.exists(), 'host compiler required')
class ShotSkip(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'src/cutscene.c').read_text()
        state = source[source.index('typedef struct'):source.index('#define CUTSCENE_FADE_FRAMES')]
        functions = source[source.index('static void finish_cutscene'):source.index('bool cutscene_is_playing(void)')]
        harness = r'''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "cutscenes.h"
#include "skip_input.h"
#include "action_audio.h"
#include "asset_names.h"
#include "save_state.h"
save_state_t save_state;
static void oot_core_clock_reset(unsigned value) { (void)value; }
static skip_input_t input;
void sample(int active,int held,unsigned tick,unsigned shot) {
 skip_input_sample(&input,active,held,tick,shot);
}
int prompt(void) { return input.armed; }
int consume(void) { return input_edge_consume(&input.request); }
''' + state + r'''
static cutscene_point_t track[100];
static const cutscene_music_t music[] = {{1,0,95}};
static const unsigned short shots[] = {0,20,60};
static const cutscene_text_t texts[] = {{1,0,19},{2,20,59},{3,60,99}};
const cutscene_t cutscenes[CUTSCENE_COUNT] = {
 { .frames=100,.stop_frame=-1,.destination=1,.destination_frame=99,
   .text=texts,.text_count=3,.shots=shots,.shot_count=3, .music=music,.music_count=1 },
 { .frames=100,.stop_frame=99,.destination=-1,.destination_frame=-1,
   .text=texts,.text_count=3,.shots=shots,.shot_count=3 }
};
const cutscene_misc_t cutscene_misc[CUTSCENE_MISC_COUNT] = {
 {0,0,10,11}, {0,2,15,16}
};
static int next_id, stopped, freed, restored, flag, applied, cue_steps;
static bool message, busy;
static void update_cues(const cutscene_t *cs) { (void)cs; ++cue_steps; }
static void message_stop(void) { message=false; }
static bool cutscene_start(unsigned id) { next_id=id; state.id=id;
 state.active=true; state.finished=false; state.frame=state.applied_frame=0; return true; }
void tree_mouth_prepare_choice(void) {}
static unsigned choice;
unsigned message_choice(void) {return choice;}
bool cutscene_start_in_scene(unsigned id) {return cutscene_start(id);}
static void emerald_story_free(void) {}
static void cutscene_actors_free(void) { ++freed; }
static void asset_loading(const char *s) { (void)s; }
static void asset_loading_done(void) {}
static void jo_core_error(const char *s) { (void)s; }
bool action_audio_set_opening(bool b) { if (!b) ++restored; return true; }
void action_audio_opening_stop(unsigned i) { (void)i; ++stopped; }
void action_audio_opening_play(unsigned a,unsigned b,bool c) { (void)a;(void)b;(void)c; }
void save_set_event_chk_inf(unsigned f) { flag=f; }
static int cutscene_bridge_angle(void) { return -100; }
/* finish_cutscene's in-scene branch frees the track and hands the mode back
** instead of reloading the sound bank; the harness watches both. */
static int mode, track_freed;
static void jo_free(void *p) { (void)p; ++track_freed; }
enum { GAME_MODE_PLAY = 1 };
static void game_mode_set(int m) { mode = m; }
bool cutscene_step(bool confirm);
static bool vdp1_wait_for_draw_end(void) { return true; }
static bool kokiri_scene_load_bank(unsigned a,unsigned b) { (void)a;(void)b;return true; }
static void apply_camera(const cutscene_point_t *p) { (void)p; applied=state.frame; }
static void update_fade(const cutscene_t *cs) { (void)cs; }
static void step_sounds(void) {}
static bool message_is_active(void) { return message; }
static void step_events(const cutscene_t *cs,bool confirm) {
 (void)confirm;
 if (!busy) while(state.music_cursor < cs->music_count &&
 cs->music[state.music_cursor].start <= state.frame) ++state.music_cursor;
}
''' + functions + r'''
void reset(void) { memset(&input,0,sizeof(input)); memset(&state,0,sizeof(state));
 state.track=track; busy=false; state.active=true; state.frame=6; state.applied_frame=5; state.text_cursor=1;
 state.bridge_start=-1; next_id=applied=-1; stopped=freed=restored=flag=cue_steps=0;
 mode=track_freed=0; message=true; }
void tree_branch(int answer) {choice=answer;state.in_scene=true;state.id=CUTSCENE_TREE_MEETING;finish_cutscene(&cutscenes[CUTSCENE_TREE_MEETING]);}
void set_in_scene(int v) { state.in_scene=v; }
void set_busy(int b) { busy=b; }
void at(int id,int frame) { state.id=id; state.frame=frame+1; state.applied_frame=frame; }
int value(int which) { switch(which) {
 case 0:return applied; case 1:return state.text_cursor; case 2:return next_id;
 case 3:return freed; case 4:return restored; case 5:return flag;
 case 6:return state.rain; case 7:return state.bridge_start;
 case 8:return cue_steps; case 9:return stopped; case 10:return message;
 case 20:return mode; case 21:return track_freed; case 22:return state.in_scene;
 default:return state.finished; }}
'''
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        out = Path(cls.tmp.name) / 'skip.dll'
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC), '-shared', '-O2', '-Wall', '-I'+str(ROOT/'src'),
                        '-I'+str(ROOT/'build/generated'), '-x','c','-','-o',str(out)],
                       input=harness,text=True,check=True,env=env)
        cls.lib=ctypes.CDLL(str(out))

    def setUp(self): self.lib.reset()

    def test_tree_yes_opens_and_no_preserves_closed_flag(self):
        self.lib.tree_branch(1)
        self.assertEqual(self.lib.value(2),8) # TREE_AGAIN, appended stable ID
        self.assertEqual(self.lib.value(5),0)
        self.lib.reset()
        self.lib.tree_branch(0)
        self.assertEqual(self.lib.value(2),7) # TREE_OPEN
        self.assertEqual(self.lib.value(5),0x05)

    def test_first_press_prompts_hold_does_not_skip(self):
        self.lib.sample(1,1,10,0)
        self.assertEqual(self.lib.prompt(),1)
        self.lib.sample(1,1,50,0)
        self.assertEqual(self.lib.consume(),0)

    def test_two_edges_survive_slow_frame_and_consume_once(self):
        for held,tick in ((1,10),(0,11),(1,130)):
            self.lib.sample(1,held,tick,0)
        self.assertEqual(self.lib.prompt(),0)
        self.assertEqual(self.lib.consume(),1)
        self.assertEqual(self.lib.consume(),0)

    def test_timeout_and_new_shot_require_fresh_confirmation(self):
        for tick,shot in ((131,0),(20,1)):
            self.lib.reset()
            self.lib.sample(1,1,10,0)
            self.lib.sample(1,0,11,0)
            self.lib.sample(1,1,tick,shot)
            self.assertEqual(self.lib.consume(),0)
            self.assertEqual(self.lib.prompt(),1)
        self.lib.sample(0,0,140,1)
        self.assertEqual(self.lib.prompt(),0)

    def test_unsigned_clock_wrap(self):
        self.lib.sample(1,1,ctypes.c_uint(0xfffffff0),0)
        self.lib.sample(1,0,ctypes.c_uint(0xfffffff1),0)
        self.lib.sample(1,1,16,0)
        self.assertEqual(self.lib.consume(),1)

    def test_skip_only_next_shot_preserves_target_text_and_misc(self):
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(0),20)
        self.assertEqual(self.lib.value(1),1)
        self.assertEqual(self.lib.value(2),-1)
        self.assertEqual(self.lib.value(6),20)
        self.assertEqual(self.lib.value(7),15)
        self.assertEqual(self.lib.value(8),15)
        self.assertEqual(self.lib.value(9),7)
        self.assertEqual(self.lib.value(10),0)

    def test_boundary_uses_displayed_frame(self):
        self.lib.at(0,19)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(0),20)
        self.lib.at(0,20)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(0),60)

    def test_last_shot_chains_instead_of_skipping_sequence(self):
        self.lib.at(0,61)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(2),1)
        self.assertEqual(self.lib.value(4),0)

    def test_last_shot_waits_for_pending_music_before_chain(self):
        self.lib.at(0,61)
        self.lib.set_busy(1)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(2),-1)
        self.lib.set_busy(0)
        self.lib.cutscene_step(0)
        self.assertEqual(self.lib.value(2),1)

    def test_final_shot_restores_gameplay_bank_and_progress(self):
        self.lib.at(1,61)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(3),1)
        self.assertEqual(self.lib.value(4),1)
        self.assertNotEqual(self.lib.value(5),0)
        self.assertEqual(self.lib.value(11),1)

    def test_in_scene_finish_keeps_the_scene_and_its_sound_bank(self):
        """An in-scene cutscene ends by handing the mode back, nothing else.

        The scene, its actors, the action sound bank and the music were never
        unloaded, so restoring them would reload a room in the middle of
        gameplay. EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN belongs to the opening
        chain and must not be set by a cutscene that just plays inside a room.
        """
        self.lib.at(1, 61)
        self.lib.set_in_scene(1)
        self.lib.cutscene_skip_shot()
        self.assertEqual(self.lib.value(3), 0)    # no cutscene_actors_free
        self.assertEqual(self.lib.value(4), 0)    # ACTIONS.PCM not reloaded
        self.assertEqual(self.lib.value(5), 0)    # no opening flag written
        self.assertEqual(self.lib.value(21), 1)   # its track is freed
        self.assertEqual(self.lib.value(20), 1)   # back to GAME_MODE_PLAY
        # The flag survives the finish: recomp.c reads it on the frame it sees
        # cutscene_finished() to know the world behind it is still standing.
        self.assertEqual(self.lib.value(22), 1)

if __name__ == '__main__': unittest.main()
