"""Button HUD timing, shared-plane placement and offline tile budgets."""
import ctypes
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_gameplay_hud as hud
import build_minimap as minimap
from PIL import Image

OOT = Path('D:/Workspace-Claude/game-decomps/n64/oot')
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless((OOT/'extracted/ntsc-1.2').exists(), 'local extracted artwork required')
class HudAssets(unittest.TestCase):
    def test_saved_label_patches_reconstruct_every_mode_and_action(self):
        images = [im for mode in ('saturn','xbox','n64','gamecube','playstation')
                  for analog in (False,True) for im in hud.make_images(OOT,analog=analog,mode=mode)]
        blob, palette, maps = hud.encode(images)
        self.assertLessEqual(len(blob),0x2000)
        cells = [(y,x) for y in range(2) for x in range(11,15)] + [(5,2),(6,2),(5,6),(6,6)]
        for mode in range(10):
            for variant in range(32):
                actual = list(maps[variant])
                patch = maps[mode*32+(16 if variant&16 else 0)]
                for y,x in cells:
                    offset=y*(hud.W//8)+x
                    actual[offset]=patch[offset]
                self.assertEqual(actual,maps[mode*32+variant],(mode,variant))

    def test_analog_label_patch_does_not_change_buttons_or_actions(self):
        digital = hud.make_images(OOT)
        analog = hud.make_images(OOT, analog=True)
        for a,b in zip(digital,analog):
            self.assertNotEqual(a.tobytes(),b.tobytes())
            for y in range(hud.H):
                for x in range(hud.W):
                    if not (240-hud.X <= x < 272-hud.X and y < 16):
                        self.assertEqual(a.getpixel((x,y)),b.getpixel((x,y)))

    def test_all_variants_fit_and_reconstruct_valid_palette_indices(self):
        images = hud.make_images(OOT)
        blob,palette,maps = hud.encode(images)
        self.assertEqual(len(maps),32)
        self.assertLessEqual(len(blob),0x2000)
        self.assertEqual(len(palette),16)
        self.assertEqual(blob[:32],bytes(32))
        for im, mapping in zip(images,maps):
            self.assertEqual(len(mapping),hud.W* hud.H//64)
            for i,tile in enumerate(mapping):
                self.assertLess(tile,len(blob)//32)
                for j in range(64):
                    index = (blob[tile*32+j//2] >> (0 if j&1 else 4)) & 15
                    x,y=(i%(hud.W//8))*8+j%8,(i//(hud.W//8))*8+j//8
                    self.assertEqual(index != 0, im.getpixel((x,y))[3]>=128)
        self.assertNotEqual(maps[0],maps[16])  # equipped sword (offset now 16)
        self.assertNotEqual(maps[0],maps[2])   # Speak
        self.assertNotEqual(maps[0],maps[1])   # Navi

    def test_label_map_fits_its_vdp2_reservation(self):
        """BUTTONS.MAP is uploaded straight into B0 VRAM. Growing the variant
        count silently overran the old 8 KB slot and the game booted to
        'scene load FAILED'; only minimap.c's guard caught it, at runtime."""
        header = (ROOT/'build/generated/gameplay_hud_data.h')
        if not header.is_file():
            self.skipTest('generated HUD header required')
        text = header.read_text()
        map_bytes = int(re.search(r'#define HUD_MAP_BYTES (\d+)', text)[1])
        source = (ROOT/'src/minimap.c').read_text()
        capacity = int(re.search(r'#define HUD_NAMES_CAPACITY (0x[0-9A-Fa-f]+)',
                                 source)[1], 16)
        base = int(re.search(r'#define HUD_NAMES \(\(volatile unsigned short \*\)'
                             r'(0x[0-9A-Fa-f]+)u\)', source)[1], 16)
        self.assertLessEqual(map_bytes, capacity,
                             'BUTTONS.MAP no longer fits its VRAM reservation')
        # The region must not run into the heart atlas above it.
        self.assertLessEqual(base + capacity, 0x25E50000,
                             'HUD label maps collide with the heart cells')

    def test_map_padding_keeps_source_pixel_coordinates_and_cart_budget(self):
        image=Image.open(OOT/'extracted/ntsc-1.2/assets/textures/map_grand_static/gKokiriForestMinimapTex.ia4.png').convert('RGBA')
        padded=Image.new('RGBA',(image.width+2,image.height))
        padded.paste(image,(2,0))
        blob,cw,ch=minimap.cells(padded)
        self.assertEqual((cw,ch),(13,8))
        self.assertLessEqual(len(blob)+6+6+9*64,0x1000)
        self.assertGreaterEqual(160,hud.Y+hud.H) # disjoint page rectangles
        for y in range(image.height):
            for x in range(image.width):
                px=x+2
                tile=1+(y//8)*cw+px//8
                offset=tile*32+(y%8)*4+(px%8)//2
                index=(blob[offset] >> (0 if px&1 else 4))&15
                r,_,_,a=image.getpixel((x,y))
                want=1+min(range(len(minimap.LEVELS)),key=lambda i:abs(minimap.LEVELS[i]-r)) if a>=128 else 0
                self.assertEqual(index,want)
                self.assertEqual(25*8+px,202+x)


@unittest.skipUnless(GCC.exists(),'host compiler required')
class HudState(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path=Path(cls.tmp.name)/'hud.dll'
        source='''#include "gameplay_hud_state.h"
static gameplay_hud_blink_t s;
void reset(void) { s = (gameplay_hud_blink_t){0}; }
int tick(unsigned t,int c,int e) { return gameplay_hud_blink(&s,t,c,e); }
/* all 7 args: enter,chest,talk,sign,grab,carrying,throw_ready */
unsigned action(int en,int ch,int tk,int sg,int gr,int ca,int th) {
    return gameplay_hud_action(en,ch,tk,sg,gr,ca,th);
}
'''
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'src'),'-x','c','-','-o',str(path)],
                       input=source,text=True,check=True,
                       env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH','')))
        cls.lib=ctypes.CDLL(str(path))

    def setUp(self): self.lib.reset()

    def test_half_second_blink_independent_of_draw_frequency(self):
        self.assertEqual(self.lib.tick(100,1,1),1)
        self.assertEqual(self.lib.tick(129,1,1),1)
        self.assertEqual(self.lib.tick(130,1,1),0)
        self.assertEqual(self.lib.tick(160,1,1),1)
        self.assertEqual(self.lib.tick(250,1,1),0)

    def test_suppression_freezes_and_new_call_restarts(self):
        self.lib.tick(0,1,1)
        self.lib.tick(20,1,1)
        self.assertEqual(self.lib.tick(21,1,0),0)
        self.assertEqual(self.lib.tick(999,1,0),0)
        self.assertEqual(self.lib.tick(1000,1,1),1)
        self.assertEqual(self.lib.tick(1010,1,1),0)
        self.assertEqual(self.lib.tick(1011,0,1),0)
        self.assertEqual(self.lib.tick(1012,1,1),1)

    def act(self,en=0,ch=0,tk=0,sg=0,gr=0,ca=0,th=0):
        return self.lib.action(en,ch,tk,sg,gr,ca,th)

    def test_action_matches_existing_handler_precedence(self):
        # All true: enter wins
        self.assertEqual(self.act(en=1,ch=1,tk=1),3)
        # No enter: chest
        self.assertEqual(self.act(ch=1,tk=1),2)
        # No enter/chest: talk
        self.assertEqual(self.act(tk=1),1)
        # Nothing: none
        self.assertEqual(self.act(),0)

    def test_action_new_labels(self):
        # Check (sign) = 4
        self.assertEqual(self.act(sg=1),4)
        # Grab = 5
        self.assertEqual(self.act(gr=1),5)
        # Drop (carrying, not throw_ready) = 6
        self.assertEqual(self.act(ca=1),6)
        # Throw (carrying+throw) = 7
        self.assertEqual(self.act(ca=1,th=1),7)

    def test_action_carry_beats_grab_and_sign(self):
        # Carrying overrides grab and sign
        self.assertEqual(self.act(gr=1,sg=1,ca=1),6)
        self.assertEqual(self.act(gr=1,sg=1,ca=1,th=1),7)

    def test_action_enter_beats_everything(self):
        self.assertEqual(self.act(en=1,ca=1,th=1,gr=1,sg=1,tk=1,ch=1),3)

    def test_hud_variant_count_is_32(self):
        """New 8-action layout doubles variant stride to 32."""
        import sys
        sys.path.insert(0,str(ROOT/'tools'))
        import build_gameplay_hud as hud_mod
        # 8 actions * 2 navi * 2 sword = 32 variants per preset
        self.assertEqual(32, 8 * 2 * 2)


if __name__=='__main__': unittest.main()
