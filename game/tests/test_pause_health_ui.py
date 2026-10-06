"""Owned-only page assets, confirmation safety and source health fractions."""
import ctypes
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_pause_windows as pause
import build_health_hud as hearts
OOT = Path('D:/Workspace-Claude/game-decomps/n64/oot')
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class Assets(unittest.TestCase):
    def test_every_page_keeps_full_rgb555_and_alpha(self):
        for page in range(6):
            source=pause.page_image(OOT,page,gear=3,stick=True,emerald=True,slingshot=True)
            blob=pause.pack(source)
            self.assertEqual(len(blob),153600)
            self.assertLessEqual(len(blob)+1024,0x26000)
            for (word,), (r,g,b,a) in zip(struct.iter_unpack('>H',blob),source.getdata()):
                self.assertEqual(word != 0,a>=128)
                if a>=128:
                    self.assertEqual((word&31,(word>>5)&31,(word>>10)&31),(r>>3,g>>3,b>>3))
            if page==1: self.assertGreater(len(set(struct.unpack('>76800H',blob))),256)

    def test_system_heading_has_no_save_lettering(self):
        system=pause.page_image(OOT,5)
        save=pause.page_image(OOT,4)
        self.assertNotEqual(system.crop((128,40,192,55)).tobytes(),save.crop((128,40,192,55)).tobytes())
        # The repaired centre frame repeats the same 8-pixel border strip.
        # Source frame colours are interpolated, so compare alpha and allow
        # the small smooth tint change rather than requiring identical RGB.
        for y in range(40,55):
            for x in range(128,184):
                a,b=system.getpixel((x,y)),system.getpixel((x+8,y))
                self.assertEqual(a[3],b[3])
                self.assertLessEqual(max(abs(a[c]-b[c]) for c in range(3)),8)

    def test_equipment_background_never_bakes_child_starter_gear(self):
        # Owned icons belong to the live inventory, including adult/new-file
        # selection. Legacy preview arguments must not leave child icons behind.
        empty = pause.page_image(OOT, 3, dynamic=True).tobytes()
        for gear in (0, 1, 3, 15):
            self.assertEqual(empty, pause.page_image(OOT, 3, gear=gear).tobytes())

    def test_backdrop_keeps_transparent_checkerboard(self):
        blob=pause.pack(pause.page_image(OOT,3,gear=3))
        words=struct.unpack('>76800H',blob)
        self.assertNotEqual(words[0],0)
        self.assertEqual(words[1],0)
        self.assertEqual(words[320],0)
        self.assertNotEqual(words[321],0)

    def test_hearts_include_all_five_fill_levels(self):
        with tempfile.TemporaryDirectory() as tmp:
            hearts.build(OOT, tmp)
            blob = Path(tmp,'HEARTS.BIN').read_bytes()
            self.assertEqual(len(blob),672)
            self.assertEqual(len({blob[32+i*128:32+(i+1)*128] for i in range(5)}),5)


@unittest.skipUnless(GCC.exists(), 'host compiler required')
class State(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        src = Path(cls.tmp.name,'ui.c')
        src.write_text('''#include "pause_window_state.h"
#include "health_hud_state.h"
static pause_window_state_t s;
void reset(void) { s=(pause_window_state_t){0}; }
int step(int x,int y,int p,int b,int a,int owned) { return pause_window_step(&s,x,y,p,b,a,owned); }
int page(void) { return s.page; }
int cursor(void) { return s.cursor[s.page]; }
int prompt(void) { return s.save_prompt; }
int fill(int health,int heart) { return health_hud_fill(health,heart); }
''')
        dll = src.with_suffix('.dll')
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-Wall','-Werror','-I'+str(ROOT/'src'),
                        str(src),str(ROOT/'src/pause_window_state.c'),'-o',str(dll)],check=True,env=env)
        cls.lib = ctypes.CDLL(str(dll))

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()
    def setUp(self): self.lib.reset()

    def test_pages_wrap_and_keep_independent_cursors(self):
        self.lib.step(1,1,0,0,0,0)
        self.assertEqual(self.lib.cursor(),7)
        for page in (1,2,3,5,0):
            self.lib.step(0,0,1,0,0,0)
            self.assertEqual(self.lib.page(),page)
        self.assertEqual(self.lib.cursor(),7)
        self.lib.step(0,0,-1,0,0,0)
        self.assertEqual(self.lib.page(),5)

    def test_save_requires_confirmation_no_does_not_save(self):
        self.assertNotEqual(self.lib.step(0,0,0,1,1,0),5)
        self.assertTrue(self.lib.prompt())
        self.lib.step(1,0,0,0,0,0)
        self.assertNotEqual(self.lib.step(0,0,0,0,1,0),5)
        self.assertFalse(self.lib.prompt())
        self.lib.step(0,0,0,1,0,0)
        self.assertEqual(self.lib.step(0,0,0,0,1,0),5)

    def test_unowned_sword_cannot_equip(self):
        self.lib.step(0,0,-1,0,0,0)
        self.lib.step(0,0,-1,0,0,0)
        self.lib.step(1,0,0,0,0,0)
        self.assertEqual(self.lib.step(0,0,0,0,1,0),2)
        self.assertEqual(self.lib.step(0,0,0,0,1,1),3)

    def test_system_load_and_title_default_no_and_require_explicit_yes(self):
        for choice, result in ((1,6),(2,7)):
            self.lib.reset()
            self.lib.step(0,0,-1,0,0,0)
            for _ in range(choice): self.lib.step(0,1,0,0,0,0)
            self.assertEqual(self.lib.step(0,0,0,0,1,0),1) # opens question
            self.assertEqual(self.lib.step(0,0,0,0,1,0),1) # default No
            self.lib.step(0,0,0,0,1,0)
            self.lib.step(-1,0,0,0,0,0)
            self.assertEqual(self.lib.step(0,0,0,0,1,0),result)

    def test_system_save_still_uses_real_save_request(self):
        self.lib.step(0,0,-1,0,0,0)
        self.lib.step(0,0,0,0,1,0)
        self.assertTrue(self.lib.prompt())
        self.assertEqual(self.lib.step(0,0,0,0,1,0),5)

    def test_back_cancels_discard_confirmation(self):
        self.lib.step(0,0,-1,0,0,0)
        self.lib.step(0,1,0,0,0,0)
        self.lib.step(0,0,0,0,1,0)
        self.lib.step(-1,0,0,0,0,0)
        self.assertEqual(self.lib.step(0,0,0,1,1,0),1)
        self.assertEqual(self.lib.step(0,0,0,0,1,0),1) # reopen, never exits

    def test_damage_and_healing_fraction_boundaries(self):
        expected = [0]+[1]*5+[2]*5+[3]*5+[4]
        for health,want in enumerate(expected):
            self.assertEqual(self.lib.fill(health,0),want)
            self.assertEqual(self.lib.fill(health+32,2),want)
        self.assertEqual([self.lib.fill(40,i) for i in range(3)],[4,4,2])
        self.assertEqual([self.lib.fill(0,i) for i in range(3)],[0,0,0])
        self.assertEqual([self.lib.fill(48,i) for i in range(3)],[4,4,4])

if __name__ == '__main__': unittest.main()
