"""Production score timing: one-shot endings, phrase jumps and pitch-only events."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class StoryMusic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = (ROOT/'shared/lib/music/music.c').read_text()
        src = src[:src.index('/* Upload one staged chunk')]
        src = src.replace('#include <jo/jo.h>', '#include <string.h>\ntypedef int jo_file;')
        src = re.sub(r'#define REG\(o\).*', 'static unsigned short registers[1024];\n#define REG(o) registers[(o)/2]', src)
        src += r'''
static const music_pcm_t samples[]={{0,0,100}};
static const music_trigger_t events[]={{0,0,0,100,0},{1,0,255,200,0},{2,1,0,300,0},{4,2,0,400,0}};
static const music_bank_t test={.pcm=samples,.triggers=events,.trigger_count=4,.frames=6,.loop_frame=2,.voices=3};
static unsigned char envelope[18];
static const unsigned short ranges[][2]={{0,2},{2,4},{4,6}};
static unsigned choose(unsigned previous){(void)previous;return 2;}
void reset(void){memset(registers,0,sizeof(registers));memset(active,0,sizeof(active));
 memset(envelope,0,sizeof(envelope));bank=&test;levels=envelope;frame=cursor=ticks=phase=0;
 refresh=60;playing=true;state=MUSIC_IDLE;volume=cdda_volume=15;once_bank=once_resume=0;
 once_done=false;section_bank=0;section_count=0;}
void one_shot(void){music_once(&test,0);}
void phrases(void){music_set_sections(&test,ranges,3,choose);}
void tick(void){music_vblank();}
int value(int which){switch(which){case 0:return frame;case 1:return playing;case 2:return once_done;
 case 3:return active[0];case 4:return SLOT(0,16);case 5:return active[1];case 6:return active[2];default:return ticks;}}
'''
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = Path(cls.tmp.name)/'score.dll'
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC), '-shared', '-O2', '-I'+str(ROOT/'shared/lib/music'),
                        '-x', 'c', '-', '-o', str(path)], input=src, text=True, env=env, check=True)
        cls.lib = ctypes.CDLL(str(path))

    def setUp(self):
        self.lib.reset()

    def test_fanfare_stops_without_restarting(self):
        g=self.lib;g.one_shot()
        for _ in range(8):g.tick()
        self.assertEqual((g.value(0),g.value(1),g.value(2)),(6,0,1))
        self.assertEqual((g.value(3),g.value(5),g.value(6)),(0,0,0))

    def test_ordinary_bank_keeps_its_loop_point(self):
        g=self.lib
        for _ in range(7):g.tick()
        self.assertEqual((g.value(0),g.value(1),g.value(2)),(3,1,0))

    def test_phrase_boundary_jumps_to_selected_resident_events(self):
        g=self.lib;g.phrases();g.tick();g.tick();g.tick()
        self.assertEqual(g.value(0),5)
        self.assertEqual((g.value(3),g.value(5),g.value(6)),(0,0,1))

    def test_pitch_only_event_updates_active_voice(self):
        g=self.lib;g.tick();self.assertEqual(g.value(4),100)
        g.tick();self.assertEqual(g.value(4),200);self.assertEqual(g.value(3),1)


if __name__ == '__main__':
    unittest.main()
