"""Saved label/jump settings, menu gain composition and frozen render clock."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


def function(source, name):
    match = re.search(r'(?:static )?(?:unsigned int|void)\s+'+name+r'\([^)]*\)\s*\{', source)
    end = match.end()
    depth = 1
    while depth:
        if source[end] == '{': depth += 1
        if source[end] == '}': depth -= 1
        end += 1
    return source[match.start():end]


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class Preferences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        audio = (ROOT.parent/'shared/lib/music/music.c').read_text()
        demo = (ROOT/'src/demo.c').read_text()
        src = '''#include <stdbool.h>
#include <stdint.h>
static unsigned short regs[32][16];
#define SLOT(s,o) regs[s][(o)/2]
#define MUSIC_MAX_VOICES 24
static bool menu_duck,active[24];
static unsigned char volume=15,voice_levels[24];
'''
        src += re.search(r'^#define CD_SEND.*$', audio, re.M)[0]+'\n'
        src += function(audio,'faded_level')+'\n'+function(audio,'music_menu_duck')
        src += '''
void audio_reset(void) {
 unsigned i,j; menu_duck=false; volume=15;
 for(i=0;i<32;++i) for(j=0;j<16;++j) regs[i][j]=0xA5FF;
 for(i=0;i<24;++i) { active[i]=true; voice_levels[i]=20; }
}
unsigned level(unsigned n) { return faded_level(n); }
unsigned reg(unsigned s,unsigned o) { return SLOT(s,o); }
void fade(unsigned v) { volume=v; }
unsigned fade_level(void) { return volume; }
static unsigned clock_now; static bool paused;
unsigned demo_clock(void) { return clock_now; }
bool gameplay_is_paused(void) { return paused; }
void clock_feed(unsigned now,bool p) { clock_now=now; paused=p; }
'''
        src += function(demo,'demo_world_clock')
        c = Path(cls.tmp.name,'prefs.c'); c.write_text(src)
        dll = c.with_suffix('.dll')
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-Wall','-Werror','-I'+str(ROOT/'src'),
                        '-I'+str(ROOT.parent/'shared/lib/camera'),
                        '-I'+str(ROOT.parent/'shared/lib/collision'),
                        str(c),str(ROOT/'src/ui_preferences.c'),'-o',str(dll)],check=True,env=env)
        cls.lib = ctypes.CDLL(str(dll))
        cls.lib.ui_button_label.restype = ctypes.c_char_p
        cls.lib.ui_label_name.restype = ctypes.c_char_p
        cls.lib.ui_preferences_unpack.restype = ctypes.c_bool

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self):
        self.lib.ui_preferences_reset()
        self.lib.audio_reset()

    def test_all_label_and_jump_choices_round_trip(self):
        block = (ctypes.c_uint8*8)()
        for labels in range(5):
            for jump in range(8):
                self.lib.ui_preferences_reset()
                for _ in range(labels): self.lib.ui_preferences_cycle(False)
                for _ in range(jump): self.lib.ui_preferences_cycle(True)
                self.lib.ui_preferences_pack(block)
                self.lib.ui_preferences_reset()
                self.assertTrue(self.lib.ui_preferences_unpack(block,8))
                self.assertEqual(self.lib.ui_labels(),labels)
                self.assertEqual(self.lib.ui_jump_binding(),jump)

    def test_corrupt_or_unknown_settings_do_not_replace_live_values(self):
        block = (ctypes.c_uint8*8)()
        self.lib.ui_preferences_cycle(False)
        self.lib.ui_preferences_pack(block)
        original = bytes(block)
        for i in range(8):
            bad = (ctypes.c_uint8*8).from_buffer_copy(original)
            bad[i] ^= 0x80
            self.assertFalse(self.lib.ui_preferences_unpack(bad,8))
            self.assertEqual(self.lib.ui_labels(),1)
        self.assertFalse(self.lib.ui_preferences_unpack(block,7))

    def test_presets_and_reset_do_not_change_default_jump(self):
        expected = [(b'X',b'A',b'Start'),(b'X',b'A',b'Menu'),
                    (b'B',b'A',b'Start'),(b'B',b'A',b'Start'),
                    (b'Square',b'Cross',b'Options')]
        for sword,action,start in expected:
            self.assertEqual(self.lib.ui_button_label(4,True),sword)
            self.assertEqual(self.lib.ui_button_label(2,True),action)
            self.assertEqual(self.lib.ui_button_label(8,True),start)
            self.assertEqual(self.lib.ui_jump_mask(),0x20) # Y stays usable in N64 mode
            self.lib.ui_preferences_cycle(False)
        self.lib.ui_preferences_cycle(True)
        self.lib.ui_preferences_reset()
        self.assertEqual(self.lib.ui_labels(),0)
        self.assertEqual(self.lib.ui_jump_mask(),0x20)

    def test_duck_composes_with_fade_and_restores_without_touching_sfx(self):
        self.lib.fade(7)
        before = self.lib.level(20)
        self.lib.music_menu_duck(True)
        self.assertEqual(self.lib.level(20),before+16)
        self.assertEqual(self.lib.fade_level(),7)
        self.assertEqual(self.lib.reg(16,0x16),0xA5DF) # CD send -6 dB, direct send preserved
        for slot in range(24,32): self.assertEqual(self.lib.reg(slot,12),0xA5FF)
        self.assertEqual(self.lib.level(250),255)
        self.lib.music_menu_duck(False)
        self.assertEqual(self.lib.level(20),before)
        self.assertEqual(self.lib.reg(16,0x16),0xA5FF)

    def test_world_animation_clock_freezes_without_catchup(self):
        self.lib.clock_feed(100,False)
        first = self.lib.demo_world_clock()
        self.lib.clock_feed(105,False)
        self.assertEqual(self.lib.demo_world_clock(),first+5)
        self.lib.clock_feed(110,True)
        frozen = self.lib.demo_world_clock()
        self.lib.clock_feed(999,True)
        self.assertEqual(self.lib.demo_world_clock(),frozen)
        self.lib.clock_feed(1000,False)
        self.assertEqual(self.lib.demo_world_clock(),frozen)
        self.lib.clock_feed(1005,False)
        self.assertEqual(self.lib.demo_world_clock(),frozen+5)

if __name__ == '__main__': unittest.main()
