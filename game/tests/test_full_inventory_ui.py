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
        draw=(backend.function(ROOT/'src/health_hud.c','static void hud_pixel(')+
              backend.function(ROOT/'src/health_hud.c','static void magic_meter(')+
              backend.function(ROOT/'src/health_hud.c','void health_hud_draw('))
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
static unsigned short vram[0x1800],names[2048],saved[960];
#define HEART_CELLS (vram+16)
#define HEART_ATLAS (vram+0x400)
#define HEART_BACK_CELLS (vram+0x800)
#define HEART_MAP names
#define MAGIC_CELLS (vram+0x1000)
#define MAGIC_BACK_CELLS (vram+0x1400)
#define HUD_CELLS 90
static unsigned char meter_end[128], meter_mid[16], meter_fill[7], magic_capacity;
static bool ready=true;
static int last_key=-2;
static unsigned front,tick;
static struct {unsigned health,health_capacity;unsigned char source_magic_level,source_magic;} save_state;
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
    for(i=0;i<90;++i) assert(names[(2+i/15)*64+2+i%15]==0x2000/32);
    save_state.health=1; health_hud_draw(true);
    /* Magic_DrawMeter: double meter below two heart rows (y 42 -> region 26),
     * fill from x 26 (region 10), 0x60 wide; one heart row moves it to 34. */
    for(i=0;i<128;++i) meter_end[i]=13; for(i=0;i<16;++i) meter_mid[i]=12;
    for(i=0;i<7;++i) meter_fill[i]=14;
    memset(vram+0x1000,0,0x800*2);
    save_state.health=save_state.health_capacity=320;
    save_state.source_magic_level=2; save_state.source_magic=40; magic_capacity=0x60; tick=6;
    health_hud_draw(true);
    {
        volatile unsigned short *m=front?MAGIC_BACK_CELLS:MAGIC_CELLS;
        #define PX(x,y) ((((x)/8+((y)/8)*15)<60?0:(m[(((y)/8)*15+(x)/8-60)*16+((y)%8)*2+(x)%8/4]>>((3-(x)%4)*4)))&15)
        assert(PX(2,33)==13);          /* left end */
        assert(PX(10+39,32)==14);      /* last full unit (y 26+3+3) */
        assert(PX(10+40,32)==12);      /* empty meter body */
        assert(PX(10+96,33)==13);      /* right end */
        assert(PX(10+96+8,33)==0);
        for(i=60;i<90;++i) assert(names[(2+i/15)*64+2+i%15]==(0x4000|((front?0x11780u:0x10B00u)/32+i-60)));
    }
    save_state.health_capacity=160; save_state.source_magic=0; tick=9; health_hud_draw(true);
    return 0;
}
''')


class MagicMeter(unittest.TestCase):
    run_c=backend.GraphicsBackend.run_c
    def test_source_grow_fill_consume_flash_and_reset(self):
        # z_parameter.c Magic_Update: capacity +8, fill +4 (gauge sound),
        # consume 2 per frame with a white/grey border until Magic_Reset.
        src=(ROOT/'src/health_hud.c').read_text()
        state=src[src.index('enum { MAGIC_IDLE'):src.index(';', src.index('static short border_rgb'))+1]
        fn=lambda name: backend.function(ROOT/'src/health_hud.c',name)
        self.run_c(r'''
#include <assert.h>
#include <stdbool.h>
#include <string.h>
static unsigned short cram[1024];
#define JO_VDP2_CRAM cram
#define METER_BORDER_CRAM 13
static bool ready=true;
static struct {unsigned char source_magic_level,source_magic;} save_state;
static unsigned sfx,sfx_calls;
static void action_audio_decomp_sfx(unsigned id){sfx=id;++sfx_calls;}
'''+state+fn('static void border_upload(')+fn('static void border_white(')+
            fn('void __attribute__((optimize("Os"))) health_hud_magic_start(')+fn('bool health_hud_magic_idle(')+
            fn('bool health_hud_magic_available(')+fn('bool health_hud_magic_consume(')+
            fn('void health_hud_magic_reset(')+fn('void __attribute__((optimize("Os"))) health_hud_magic_update(')+r'''
int main(void) {
    int i, frames=0;
    save_state.source_magic_level=2; save_state.source_magic=90;
    health_hud_magic_start();
    assert(magic_capacity==0 && save_state.source_magic==0 && !health_hud_magic_idle());
    while(magic_state==MAGIC_STEP_CAPACITY){health_hud_magic_update();++frames;}
    assert(magic_capacity==0x60 && frames==13);          /* 12 steps of 8, then switch */
    while(!health_hud_magic_idle()){health_hud_magic_update();}
    assert(save_state.source_magic==90 && sfx==0x481F-0x800 && sfx_calls==23);
    assert(health_hud_magic_consume(8) && !health_hud_magic_consume(4));
    health_hud_magic_update();                           /* CONSUME_SETUP */
    for(i=0;i<4;++i) health_hud_magic_update();          /* 2 per frame */
    assert(save_state.source_magic==82 && magic_state==MAGIC_METER_FLASH_1);
    for(i=0;i<8;++i) health_hud_magic_update();
    assert(cram[832+13]!=0 && !health_hud_magic_idle()); /* still flashing */
    health_hud_magic_reset(); health_hud_magic_update();
    assert(health_hud_magic_idle() && cram[832+13]==0xFFFF);
    assert(!health_hud_magic_available(83) && health_hud_magic_available(82));
    save_state.source_magic_level=0; save_state.source_magic=5; health_hud_magic_start();
    assert(health_hud_magic_idle() && save_state.source_magic==5 && !health_hud_magic_available(1));
    return 0;
}
''')

if __name__=='__main__': unittest.main()
