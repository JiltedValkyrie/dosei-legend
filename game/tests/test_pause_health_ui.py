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
    def test_map_regional_palettes_fit_and_preserve_detail(self):
        source = pause.page_image(OOT, 1)
        blob = pause.pack_map(source)
        self.assertEqual(len(blob), 39952)
        self.assertLessEqual(len(blob), 0xA000)
        palettes = struct.unpack('>176H', blob[:352])
        self.assertEqual(set(blob[352:1552]), set(range(5,16)))
        self.assertGreater(len(set(palettes)), 32)
        old = pause.pack(source)
        old_palette = struct.unpack('>16H', old[:32])
        errors = [0,0]
        for y in range(240):
            for x in range(320):
                pixel = y*320+x
                shift = 0 if x&1 else 4
                index = (blob[1552+pixel//2] >> shift)&15
                self.assertEqual(index != 0, source.getpixel((x,y))[3]>=128)
                bank = blob[352+(y//8)*40+x//8]-5
                words = (palettes[bank*16+index], old_palette[(old[32+pixel//2]>>shift)&15])
                if source.getpixel((x,y))[3]>=128:
                    for version, word in enumerate(words):
                        errors[version] += sum((source.getpixel((x,y))[c] - ((word>>(c*5))&31)*255//31)**2 for c in range(3))
        self.assertLess(errors[0],errors[1])

    def test_owned_gear_only_changes_its_slot(self):
        empty = pause.page_image(OOT, 3)
        sword = pause.page_image(OOT, 3, gear=1)
        self.assertEqual(empty.crop((174,96,202,124)).tobytes(), sword.crop((174,96,202,124)).tobytes())
        self.assertNotEqual(empty.crop((174,64,202,92)).tobytes(), sword.crop((174,64,202,92)).tobytes())

    def test_backdrop_is_dithered_and_cursor_colours_reserved(self):
        blob = pause.pack(pause.page_image(OOT, 3, gear=3))
        self.assertEqual(len(blob), 38432)
        self.assertLessEqual(len(blob), 0xA000)
        self.assertEqual(struct.unpack('>16H', blob[:32])[15], 0xFF50)
        self.assertEqual(struct.unpack('>16H', blob[:32])[14], 0x83FF)
        self.assertNotEqual(blob[32] >> 4, 0)
        self.assertEqual(blob[32] & 15, 0)
        self.assertEqual(blob[32+160] >> 4, 0)
        self.assertNotEqual(blob[32+160] & 15, 0)
        for byte in blob[32:]:
            self.assertIn(byte >> 4, range(0,14))
            self.assertIn(byte & 15, range(0,14))
        self.assertLessEqual(0x6000 + len(blob)-32, 0x10000) # heart cells start here

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
