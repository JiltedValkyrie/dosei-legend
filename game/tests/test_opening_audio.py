"""Opening cue timing, resident-bank bounds, and music/effect isolation."""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class OpeningAudio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cs = (ROOT / 'src/cutscene.c').read_text()
        sounds = cs[cs.index('static void step_sounds('):cs.index('static void step_events(')]
        music = (ROOT.parent / 'shared/lib/music/music.c').read_text()
        volume = music[music.index('static unsigned int faded_level('):music.index('static void stop_all(')]
        harness = '''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "cutscenes.h"
#include "action_audio.h"
static struct { unsigned short sound_frame,frame; unsigned int id;
 const cutscene_cue_t *actor_cues[10]; int actor_pos[10][3];
 int sound_bridge_angle,sound_navi_y; bool sound_hooves,sound_navi_falling; } state;
static int plays[9], stops[7], bridge;
void action_audio_opening_play(unsigned int s,unsigned int c,bool loop){ ++plays[s]; }
void action_audio_opening_stop(unsigned int c){ ++stops[c]; }
static int cutscene_bridge_angle(void){ return bridge; }
''' + sounds + '''
void reset(void) { memset(&state,0,sizeof(state)); memset(plays,0,sizeof(plays));
 memset(stops,0,sizeof(stops)); state.sound_frame=65535; state.id=CUTSCENE_NIGHTMARE;
 state.sound_bridge_angle=bridge=-16384; }
void step(int frame,int angle){ state.frame=frame; bridge=angle; step_sounds(); }
int played(int sound){ return plays[sound]; }
int stopped(int channel){ return stops[channel]; }
#define MUSIC_MAX_VOICES 24
static unsigned short regs[32];
#define SLOT(s,o) regs[s]
static bool active[24];
static unsigned char voice_levels[24],volume;
''' + volume + '''
int fade(int level,int slot) { active[0]=true; voice_levels[0]=12;
 regs[24]=77; set_volume(level); return regs[slot]; }
'''
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(cls.tmp.name)
        (path/'test.c').write_text(harness)
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'src'),
                        '-I'+str(ROOT/'build/generated'), str(path/'test.c'),
                        '-o', str(path/'test.dll')], check=True, env=env)
        cls.lib = ctypes.CDLL(str(path/'test.dll'))

    def test_held_frame_never_retriggers_shot_accent(self):
        self.lib.reset()
        for _ in range(100): self.lib.step(20, -15000)
        self.assertEqual(self.lib.played(0), 1)
        self.assertEqual(self.lib.played(1), 1)

    def test_source_shot_accents_and_paired_lightning(self):
        self.lib.reset()
        for frame in range(541): self.lib.step(frame, -16384)
        self.assertEqual(self.lib.played(0), 11)
        self.assertEqual(self.lib.played(1), 3)
        self.assertEqual(self.lib.played(8), 1)

    def test_bridge_loop_stops_when_bridge_lands(self):
        self.lib.reset()
        self.lib.step(10, -16384)
        self.lib.step(11, -16264)
        self.lib.step(147, 0)
        self.lib.step(148, 0)
        self.assertEqual(self.lib.played(2), 1)
        self.assertEqual(self.lib.played(3), 1)
        self.assertEqual(self.lib.stopped(3), 1)

    def test_silent_music_does_not_mute_effect_slots(self):
        for level in range(16):
            self.assertEqual(self.lib.fade(level,24), 77)
        self.assertEqual(self.lib.fade(0,0), 255)
        self.assertEqual(self.lib.fade(15,0), 12)

    def test_opening_pcm_stays_in_reserved_action_tail(self):
        data = json.loads((ROOT/'build/generated/opening_audio.json').read_text())
        pcm = (ROOT/'build/generated/OPENING.PCM').read_bytes()
        self.assertEqual(len(pcm),data['bytes'])
        self.assertGreaterEqual(data['base'],0x3C000)
        self.assertLessEqual(data['base']+len(pcm),0x80000)
        self.assertEqual([s['name'] for s in data['samples']],
                         ['cut','thunder','bridge','bridge_stop','hooves','neigh','dust','dash','rain'])
        for sample in data['samples']:
            self.assertLessEqual(sample['offset']+sample['length'],len(pcm))
            self.assertTrue(any(pcm[sample['offset']:sample['offset']+sample['length']]))
