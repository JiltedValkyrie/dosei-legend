"""Production CD state handling and music gain, with mocked drive/registers."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path(shutil.which('gcc') or 'C:/msys64/mingw64/bin/gcc.exe')
SDK = ROOT.parent.parent / 'joengine/Compiler/COMMON/SGL_302j/INC'


@unittest.skipUnless(GCC.exists() and SDK.exists(), 'host compiler and SDK required')
class CddaMix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        complete = (ROOT.parent / 'shared/lib/music/music.c').read_text()
        source = complete
        source = source[:source.index('/* Upload one staged chunk')]
        # The streaming transport is outside this register/drive fixture;
        # its separate GFS tests own reads, seeks, and read-ahead release.
        start = source.index('typedef struct {\n    GfsHn')
        end = source.index('static bool swap_failed;', start)
        source = source[:start] + source[end:]
        source = source.replace('#include <jo/jo.h>', '#include <stdint.h>\ntypedef struct { int size; } jo_file;')
        source = source.replace('#define REG(o) (*(volatile unsigned short *)(0x25b00000UL + (o)))',
                                'static unsigned short regs[0x500/2];\n#define REG(o) regs[(o)/2]')
        tempo = complete.index('void music_source_tempo(')
        source += complete[tempo:complete.index('\n}', tempo) + 2]
        harness = source + r'''
#include <string.h>
#include <SEGA_CDC.H>
static int cd_status, cd_track, cd_error, play_error, play_calls, muted_on_play;
static int end_type;
Sint32 CDC_CdPlay(CdcPly *p) {
 ++play_calls; cd_track=CDC_PLY_STNO(p);end_type=CDC_PLY_ETYPE(p);
 muted_on_play=(SLOT(0,12)==255); return play_error;
}
Sint32 CDC_GetCurStat(CdcStat *s) {
 memset(s,0,sizeof(*s));CDC_STAT_STATUS(s)=cd_status;CDC_STAT_TNO(s)=cd_track;
 return cd_error;
}
unsigned int music_vblank_count(void) { return vblanks; }
bool music_busy(void) { return state != MUSIC_IDLE; }
#include "cdda.c"
void reset(int hz) {
 memset(regs,0,sizeof(regs));memset(active,0,sizeof(active));
 refresh=hz;playing=false;state=MUSIC_IDLE;volume=15;menu_duck=false;
 cdda_muted=false;cdda_volume=15;cdda_restore=0;vblanks=0;
 source_volume=source_start=source_target=15;source_fade=source_step=0;
 singing_voice=singing_melody=spatial_volume=127;spatial_pan=64;singing_alone=false;
 memset(channel_attenuation,0,sizeof channel_attenuation);
 memset(voice_channels,0,sizeof voice_channels);
 requested_track=active_track=0;saw_play=false;last_play_tick=0;
 cd_status=CDC_ST_PAUSE;cd_track=0;cd_error=play_error=play_calls=muted_on_play=0;
 active[0]=true;voice_levels[0]=40;active[1]=true;voice_levels[1]=80;
 SLOT(31,12)=73;SLOT(16,0x16)=0xABFF;set_volume(15);
}
void tick(int n) { while(n--) music_vblank(); }
static const music_bank_t empty_score = { .frames=10000 };
void score_start(void) {
 bank=&empty_score;playing=true;frame=cursor=ticks=phase=0;levels_live=false;
 once_bank=once_resume=0;once_done=false;source_tempo=256;
}
int score_frames(void) { return ticks; }
int resume_pinned(void) {
 static music_bank_t other;
 music_once(&other,&empty_score);bank=&other;
 return music_bank_referenced(&empty_score);
}
void status(int s,int track) { cd_status=s;cd_track=track;cdda_service(); }
void busy(int yes) { state=yes ? MUSIC_SWAP : MUSIC_IDLE; }
void fail(int yes) { play_error=yes ? -1 : 0; }
int level(void) { return SLOT(0,12); }
int effects(void) { return SLOT(31,12); }
int send(void) { return SLOT(16,0x16); }
int calls(void) { return play_calls; }
int muted(void) { return cdda_muted; }
int onset(void) { return muted_on_play; }
int disc_end(void) { return end_type == CDC_PTYPE_DFL; }
void source_channels(void) { voice_channels[0]=1;voice_channels[1]=14; }
int melody_level(void) { return SLOT(1,12); }
/* Envelope tables are 32 KB chunks: a frame row may straddle two of them. */
int level_chunk_row(void) {
 static unsigned char a[LEVEL_CHUNK], b[64];
 static const music_bank_t three = { .frames=20000, .voices=3 };
 unsigned i;
 for(i=0;i<sizeof a;++i)a[i]=(unsigned char)(i*7u);
 for(i=0;i<sizeof b;++i)b[i]=(unsigned char)(200u+i);
 bank=&three;levels[0]=a;levels[1]=b;levels_live=true;
 memset(active,0,sizeof active);active[0]=active[1]=active[2]=true;
 frame=10922;cursor=0;score_tick();               /* bytes 32766, 32767 | 32768 */
 i=voice_levels[0]==(unsigned char)(32766u*7u) && voice_levels[1]==(unsigned char)(32767u*7u) &&
   voice_levels[2]==200 && frame==10923;
 levels_live=false;voice_levels[0]=1;score_tick();  /* gated: no read */
 i=i && voice_levels[0]==1;
 levels[0]=levels[1]=0;bank=0;
 return (int)i;
}
'''
        # cdda.h includes the generated track table; build it into the
        # temporary directory so the test does not depend on a prior build.
        generated = Path(cls.temp.name) / 'generated'
        subprocess.run([sys.executable, str(ROOT / 'tools/build_cdda.py'),
                        '--header', str(generated / 'cdda_tracks.h'),
                        '--tracks-only'], check=True)
        dll = Path(cls.temp.name) / 'cdda.dll'
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-fPIC', '-O2', '-idirafter', str(SDK),
                        '-I', str(ROOT / 'src'), '-I', str(ROOT.parent / 'shared/lib/music'),
                        '-I', str(generated),
                        '-x', 'c', '-', '-o', str(dll)], input=harness,
                       text=True, check=True, env=env)
        cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_mute_then_exact_half_second_restore_ntsc_and_pal(self):
        for hz in (60, 50):
            with self.subTest(hz=hz):
                self.lib.reset(hz)
                self.lib.cdda_play(2)
                self.assertEqual(self.lib.onset(), 1)
                self.assertEqual(self.lib.level(), 255)
                self.lib.status(4, 2)  # seek is not completion
                self.lib.tick(5)
                self.assertEqual(self.lib.level(), 255)
                self.lib.status(3, 2)
                self.lib.tick(100)
                self.assertEqual(self.lib.level(), 255)
                self.lib.status(1, 2)
                self.assertEqual(self.lib.level(), 255)
                previous = 255
                for frame in range(hz // 2):
                    self.lib.tick(1)
                    level = self.lib.level()
                    self.assertLessEqual(level, previous)
                    if frame < hz // 2 - 1:
                        self.assertGreater(level, 40)
                    previous = level
                self.assertEqual(self.lib.level(), 40)
                self.assertEqual(self.lib.effects(), 73)
                self.assertEqual(self.lib.send(), 0xABFF)

    def test_level_rows_cross_chunk_boundaries(self):
        self.lib.reset(60)
        self.assertEqual(self.lib.level_chunk_row(), 1)

    def test_pause_duck_composes_with_restore(self):
        self.lib.reset(60)
        self.lib.music_menu_duck(True)
        self.lib.cdda_play(3)
        self.lib.status(3, 3)
        self.lib.status(1, 3)
        self.lib.tick(30)
        self.assertEqual(self.lib.level(), 56)
        self.assertEqual(self.lib.effects(), 73)

    def test_waits_for_music_load_before_issuing_cd_command(self):
        self.lib.reset(60)
        self.lib.busy(1)
        self.lib.cdda_play(2)
        self.assertEqual(self.lib.calls(), 0)
        self.lib.busy(0)
        self.lib.cdda_service()
        self.assertEqual(self.lib.calls(), 1)
        self.assertEqual(self.lib.level(), 255)

    def test_failed_command_and_data_track_interruption_release_mute(self):
        self.lib.reset(60)
        self.lib.fail(1)
        self.lib.cdda_play(2)
        self.lib.tick(30)
        self.assertEqual(self.lib.level(), 40)
        self.lib.fail(0)
        self.lib.cdda_play(2)
        self.lib.status(3, 2)
        self.lib.status(3, 1)
        self.lib.tick(30)
        self.assertEqual(self.lib.level(), 40)

    def test_new_track_restarts_mute_during_restore(self):
        self.lib.reset(60)
        self.lib.cdda_play(2)
        self.lib.status(3, 2)
        self.lib.status(1, 2)
        self.lib.tick(10)
        self.lib.cdda_play(4)
        self.assertEqual(self.lib.level(), 255)
        self.lib.status(3, 4)
        self.lib.tick(30)
        self.assertEqual(self.lib.level(), 255)
        self.lib.status(1, 4)
        self.lib.tick(30)
        self.assertEqual(self.lib.level(), 40)

    def test_last_track_uses_leadout_and_releases_fanfare_wait(self):
        self.lib.reset(60)
        self.lib.cdda_play(2)
        self.assertEqual(self.lib.disc_end(), 0)
        self.lib.cdda_play(6)
        self.assertEqual(self.lib.calls(), 1)  # pending item cannot cut chest
        self.lib.status(3, 2)
        self.lib.status(1, 2)
        self.assertEqual(self.lib.disc_end(), 1)
        self.lib.status(3, 6)
        self.assertTrue(self.lib.cdda_busy())
        self.lib.status(1, 6)
        self.assertFalse(self.lib.cdda_busy())

    def test_chest_cue_completes_before_item_and_duplicates_do_not_restart(self):
        self.lib.reset(60)
        self.lib.cdda_play(2)
        self.lib.status(3, 2)
        self.lib.cdda_play(2)
        self.lib.cdda_play(6)
        self.lib.cdda_play(6)
        self.lib.tick(520)  # full 8.56-second cue plus sector padding
        self.lib.status(3, 2)
        self.assertEqual(self.lib.calls(), 1)
        self.assertTrue(self.lib.cdda_busy())
        self.lib.status(1, 2)
        self.assertEqual(self.lib.calls(), 2)
        self.assertEqual(self.lib.muted(), 1)
        self.lib.status(3, 6)
        self.lib.status(1, 6)
        self.assertFalse(self.lib.cdda_busy())

    def test_source_volume_fade_composes_with_cdda_and_preserves_sfx(self):
        for hz in (50, 60):
            self.lib.reset(hz)
            self.lib.music_source_volume(0, 20)
            self.lib.tick(hz // 2)
            self.assertGreater(self.lib.level(), 40)
            self.lib.tick(hz - hz // 2)
            self.assertEqual(self.lib.level(), 255)
            self.lib.music_source_volume(127, 0)
            self.assertEqual(self.lib.level(), 40)
            self.assertEqual(self.lib.effects(), 73)

    def test_source_tempo_advances_score_clock_at_both_refresh_rates(self):
        for hz in (50, 60):
            self.lib.reset(hz)
            self.lib.score_start()
            self.lib.music_source_tempo(210 * 256 // 185)
            self.lib.tick(hz * 10)
            self.assertEqual(self.lib.score_frames(), 600 * (210 * 256 // 185) // 256)
            self.assertEqual(self.lib.resume_pinned(), 1)

    def test_malon_channels_duck_independently_without_muting_effects(self):
        self.lib.reset(60)
        self.lib.source_channels()
        self.lib.music_source_singing(127, 0, 0)
        self.assertEqual(self.lib.level(), 40)
        self.assertEqual(self.lib.melody_level(), 255)
        self.lib.music_source_singing(0, 127, 0)
        self.assertEqual(self.lib.level(), 255)
        self.assertEqual(self.lib.melody_level(), 80)
        self.lib.music_source_singing(127, 127, 1)
        self.assertEqual(self.lib.melody_level(), 255)
        self.assertEqual(self.lib.effects(), 73)


if __name__ == '__main__':
    unittest.main()
