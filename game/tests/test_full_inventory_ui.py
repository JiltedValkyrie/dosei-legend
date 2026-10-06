"""Full source inventory/quest data and tear-free HUD regression checks."""
from pathlib import Path
import struct
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from pause_inventory_assets import ICON_SIZE,RECORD_BYTES,META_BYTES,item_icons
import test_graphics_backend as backend


class Assets(unittest.TestCase):
    def test_source_icon_ids_and_world_regions(self):
        blob=(ROOT/'build/cd/PAUSEINV.BIN').read_bytes()
        self.assertEqual(len(blob),META_BYTES+122*RECORD_BYTES)
        for item in range(122):
            record=blob[META_BYTES+item*RECORD_BYTES:META_BYTES+(item+1)*RECORD_BYTES]
            self.assertIn(0,record[:32])
            self.assertNotEqual(record[:1],b'\0')
            self.assertEqual(record[32:34],b'\0\0')
            self.assertTrue(any(record[64:]))
        for q in range(24):
            item,x,y,w,h=struct.unpack_from('>H4B',blob,q*6)
            self.assertEqual(item,0x66+q if q<6 else 0x5a+q-6 if q<18 else 0x6c+q-18)
            self.assertLessEqual(x+w,320)
            self.assertLessEqual(y+h,240)
        # Source misc-settings area follows interior parents, not just outdoor maps.
        def center(scene): return struct.unpack_from('>HH',blob,144+scene*4)
        self.assertEqual(center(0x4c),center(0x63)) # Ranch house / Ranch
        self.assertEqual(center(0x37),center(0x52)) # Impa house / Kakariko
        self.assertEqual(len({center(i) for i in (0x51,0x52,0x55,0x63)}),4)


class Hearts(unittest.TestCase):
    run_c=backend.GraphicsBackend.run_c
    def test_old_front_pixels_survive_full_back_buffer_composition(self):
        # Production drawing function on fake bounded VRAM. A changed pulse
        # must leave every currently displayed pixel intact until map swap.
        draw=backend.function(ROOT/'src/health_hud.c','void health_hud_draw(')
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
static unsigned short vram[0x1800],names[2048],saved[960];
#define HEART_CELLS (vram+16)
#define HEART_ATLAS (vram+0x400)
#define HEART_BACK_CELLS (vram+0x800)
#define HEART_MAP names
static bool ready=true;
static int last_key=-2;
static unsigned front,tick;
static struct {unsigned health,health_capacity;} save_state;
static unsigned recomp_clock(void) {return tick;}
'''+(ROOT/'src/health_hud_state.h').read_text()+draw+r'''
int main(void) {
    unsigned i,previous;
    memset(vram,0xa5,sizeof(vram));
    for(i=0;i<320;++i) HEART_ATLAS[i]=0x1234;
    save_state.health=save_state.health_capacity=320;
    health_hud_draw(true);
    for(i=0;i<60;++i) assert(names[(2+i/15)*64+2+i%15]==(0x4000|(0x11000/32+i)));
    memcpy(saved,HEART_BACK_CELLS,sizeof(saved));
    tick=3; health_hud_draw(true);
    assert(!memcmp(saved,HEART_BACK_CELLS,sizeof(saved)));
    assert(front==0);
    for(i=0;i<60;++i) assert(names[(2+i/15)*64+2+i%15]==(0x4000|(0x10000/32+i)));
    previous=front; health_hud_draw(true); assert(previous==front);
    for(i=0;i<320;++i) assert(HEART_ATLAS[i]==0x1234);
    for(i=0;i<16;++i) assert(vram[i]==0xa5a5);
    assert(vram[0x800+960]==0xa5a5);
    health_hud_draw(false);
    for(i=0;i<60;++i) assert(names[(2+i/15)*64+2+i%15]==0x2000/32);
    save_state.health=1; health_hud_draw(true);
    return 0;
}
''')


if __name__=='__main__': unittest.main()
