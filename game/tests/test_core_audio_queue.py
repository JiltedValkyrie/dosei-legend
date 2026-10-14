"""Execute the master audio queue with a drive held by the full chest cue."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
CC = shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe'


class CoreAudioQueue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        text = (ROOT / 'src/oot_core_host.c').read_text()
        start = text.index('static void host_audio_request(')
        end = text.index('static const OotCoreHost host', start)
        source = r'''
#include <stdbool.h>
#include <string.h>
#include "oot_core_audio.h"
typedef int oot_song_t;
typedef struct { int id; } music_bank_t;
#define NA_BGM_TIMED_MINI_GAME 64
#define NA_BGM_NATURE_AMBIENCE 1
struct {
 unsigned audio_queue[8], audio_count;
 const music_bank_t *resume_bank;
 unsigned short resume_sequence, source_sequence;
} draw;
#define CORE_DRAW (&draw)
static int cd, busy, fatal, plays, area_plays, fanfares, gain, fade, tempo, sequence;
static music_bank_t bank = { 19 };
static const music_bank_t *current;
static unsigned area_sequence;
void host_fatal(unsigned code, unsigned a, unsigned b) { ++fatal; }
bool cdda_busy(void) { return cd; }
bool music_busy(void) { return busy; }
bool music_fanfare_busy(void) { return false; }
bool music_song_routed(int song) { return song==43 || song==34 || song==19; }
bool music_play(int song) { if(!music_song_routed(song)) return false; ++plays; sequence= song; return true; }
bool music_area_play(unsigned song, unsigned fade) { ++area_plays; sequence=song; return true; }
bool music_area_fanfare(unsigned song) { ++fanfares; sequence=song; return true; }
unsigned music_area_current_sequence(void) { return area_sequence; }
const music_bank_t *music_current(void) { return current; }
void music_source_tempo(unsigned ratio) { tempo=ratio; }
void music_source_volume(unsigned volume, unsigned frames) { gain=volume;fade=frames; }
void music_source_singing(unsigned voice,unsigned melody,bool alone) {}
void music_source_spatial(unsigned gain,unsigned pan) {}
static unsigned sfx_id,sfx_ratio;
void action_audio_decomp_sfx_pitch(unsigned id,unsigned ratio) { sfx_id=id;sfx_ratio=ratio; }
void music_silence(unsigned frames) { sequence=-1; }
void music_fade_to(const music_bank_t *target, unsigned frames) { sequence=target->id; }
''' + text[start:end] + r'''
void reset(void) {
 memset(&draw,0,sizeof draw);draw.source_sequence=draw.resume_sequence=0xffff;
 cd=busy=fatal=plays=area_plays=fanfares=0;gain=127;tempo=256;
 area_sequence=0xffff;current=&bank;
}
void request(unsigned command,unsigned argument) { host_audio_request(command,argument); }
void service(void) { host_audio_service(); }
void drive(int yes) { cd=yes; }
void loading(int yes) { busy=yes; }
void area(unsigned id) { area_sequence=id; }
int readout(int k) { switch(k) {
 case 0:return draw.audio_count;case 1:return fatal;case 2:return plays;
 case 3:return area_plays;case 4:return gain;case 5:return fade;case 6:return tempo;
 case 7:return sequence;case 8:return fanfares;case 9:return sfx_id;case 10:return sfx_ratio;default:return -1; } }
'''
        path = Path(cls.temp.name) / 'queue.dll'
        env = dict(os.environ, PATH=str(Path(CC).parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([CC, '-shared', '-fPIC', '-O2', '-I', str(ROOT / 'oot-core/include'),
                        '-x', 'c', '-', '-o', str(path)], input=source, text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(path))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.lib.reset()

    def test_chest_keeps_drive_and_gain_does_not_fill_deferred_queue(self):
        l = self.lib
        l.drive(1)
        l.request(2, 64)
        for i in range(180):
            l.request(4, (20 << 8) | (i % 128))
            l.service()
        self.assertEqual(l.readout(0), 1)
        self.assertEqual(l.readout(1), 0)
        self.assertEqual(l.readout(3), 0)
        self.assertEqual(l.readout(4), 179 % 128)
        self.assertEqual(l.readout(5), 20)
        l.drive(0)
        l.service()
        self.assertEqual(l.readout(0), 0)
        self.assertEqual(l.readout(7), 64)

    def test_item_cd_queues_but_unrouted_fanfare_waits_for_drive(self):
        l = self.lib
        l.drive(1)
        l.request(1, 34)
        l.request(1, 34)
        l.request(1, 47)
        l.service()
        self.assertEqual(l.readout(2), 1)
        self.assertEqual(l.readout(8), 0)
        self.assertEqual(l.readout(0), 1)
        l.drive(0)
        l.service()
        self.assertEqual(l.readout(8), 1)
        self.assertEqual(l.readout(0), 0)

    def test_minigame_accelerates_only_its_score_and_pop_restores_area(self):
        l = self.lib
        l.area(49)
        l.request(5, 64)
        l.request(7, 0)
        l.service()
        self.assertEqual(l.readout(6), 210 * 256 // 185)
        l.request(6, 0)
        l.service()
        self.assertEqual(l.readout(7), 49)
        self.assertEqual(l.readout(6), 256)
        l.request(7, 0)
        l.service()
        self.assertEqual(l.readout(6), 256)

    def test_loading_defers_stop_and_builtin_theme_survives_push_pop(self):
        l = self.lib
        l.request(5, 64)
        l.service()
        l.loading(1)
        l.request(3, 0)
        l.request(6, 0)
        l.service()
        self.assertEqual(l.readout(0), 2)
        l.loading(0)
        l.service()
        self.assertEqual(l.readout(7), 19)
        self.assertEqual(l.readout(0), 0)

    def test_pitched_sound_uses_resident_bank_while_cd_owns_drive(self):
        l=self.lib
        l.drive(1)
        l.request(2,64)
        l.request(10|(96<<8),0x2820)
        l.service()
        self.assertEqual(l.readout(0),1)
        self.assertEqual(l.readout(9),0x2820)
        self.assertEqual(l.readout(10),96)


if __name__ == '__main__':
    unittest.main()
