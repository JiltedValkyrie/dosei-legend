"""Production CD state handling and music gain, with mocked drive/registers."""
import ctypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')
SDK = ROOT.parent.parent / 'joengine/Compiler/COMMON/SGL_302j/INC'


@unittest.skipUnless(GCC.exists() and SDK.exists(), 'host compiler and SDK required')
class CddaMix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = (ROOT.parent / 'shared/lib/music/music.c').read_text()
        source = source[:source.index('/* Upload one staged chunk')]
        source = source.replace('#include <jo/jo.h>', '#include <stdint.h>\ntypedef struct { int size; } jo_file;')
        source = source.replace('#define REG(o) (*(volatile unsigned short *)(0x25b00000UL + (o)))',
                                'static unsigned short regs[0x500/2];\n#define REG(o) regs[(o)/2]')
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
 requested_track=active_track=0;saw_play=false;last_play_tick=0;
 cd_status=CDC_ST_PAUSE;cd_track=0;cd_error=play_error=play_calls=muted_on_play=0;
 active[0]=true;voice_levels[0]=40;active[1]=true;voice_levels[1]=80;
 SLOT(31,12)=73;SLOT(16,0x16)=0xABFF;set_volume(15);
}
void tick(int n) { while(n--) music_vblank(); }
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
'''
        # cdda.h includes the generated track table; build it into the
        # temporary directory so the test does not depend on a prior build.
        generated = Path(cls.temp.name) / 'generated'
        subprocess.run([sys.executable, str(ROOT / 'tools/build_cdda.py'),
                        '--header', str(generated / 'cdda_tracks.h'),
                        '--tracks-only'], check=True)
        dll = Path(cls.temp.name) / 'cdda.dll'
        env = dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', ''))
        subprocess.run([str(GCC), '-shared', '-O2', '-idirafter', str(SDK),
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
        self.assertEqual(self.lib.disc_end(), 1)
        self.lib.status(3, 6)
        self.assertTrue(self.lib.cdda_busy())
        self.lib.status(1, 6)
        self.assertFalse(self.lib.cdda_busy())


if __name__ == '__main__':
    unittest.main()
