"""Dirty HUD banks match full composition through pulse/state/reload changes."""
import unittest
from test_graphics_backend import ROOT, function
import test_graphics_backend as backend


class DirtyHearts(unittest.TestCase):
    run_c = backend.GraphicsBackend.run_c

    def test_display_matches_full_composition_and_preserves_active_bank(self):
        path = ROOT/'src/health_hud.c'
        source = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
static unsigned short vram[0x1800],names[2048];
static unsigned short cpu_atlas[320];
#define HEART_CELLS (vram+16)
#define HEART_ATLAS (vram+0x400)
#define HEART_SOURCE cpu_atlas
#define HEART_BACK_CELLS (vram+0x800)
#define HEART_MAP names
#define MAGIC_CELLS (vram+0x1000)
#define MAGIC_BACK_CELLS (vram+0x1400)
#define HUD_CELLS 90
static unsigned char meter_end[128],meter_mid[16],meter_fill[7],magic_capacity;
static bool ready=true;
static int last_key=-2;
static unsigned front,tick;
static struct {unsigned health,health_capacity;unsigned char source_magic_level,source_magic;} save_state;
static unsigned recomp_clock(void) {return tick;}
'''
        source += (ROOT/'src/health_hud_state.h').read_text()
        for marker in ('void health_hud_reset(', 'static void hud_pixel(',
                       'static void magic_meter(', 'static void heart_draw(', 'void health_hud_draw('):
            source += function(path,marker)
        source += r'''
/* Independent slow reference: reconstruct every pixel from the atlas each
 * time. No retained base, dirty rectangle, per-bank key or pulse history. */
static void full_reference(unsigned short *cells,unsigned short *magic) {
    static const unsigned char sample11[11]={0,1,2,4,5,7,8,10,11,13,14};
    unsigned char sample[16];
    unsigned capacity=save_state.health_capacity/16,health=save_state.health;
    unsigned pulse=(tick/3)%10,size=11+(pulse>5?pulse-5:5-pulse);
    if(capacity>20)capacity=20;
    if(health>capacity*16)health=capacity*16;
    unsigned beating=health?(health-1)/16:~0u;
    memset(cells,0,960*2);memset(magic,0,480*2);
    for(unsigned h=0;h<capacity;++h)
        if(h!=beating)heart_draw(cells,health,h,11,sample11);
    magic_meter(cells,magic,capacity);
    for(unsigned i=0;i<size;++i)sample[i]=i*16/size;
    if(beating<capacity)heart_draw(cells,health,beating,size,size==11?sample11:sample);
}
static void verify(bool visible) {
    unsigned short old_cells[960],old_magic[480],expected[960],meter[480];
    unsigned previous=front;
    memcpy(old_cells,front?HEART_BACK_CELLS:HEART_CELLS,sizeof(old_cells));
    memcpy(old_magic,front?MAGIC_BACK_CELLS:MAGIC_CELLS,sizeof(old_magic));
    health_hud_draw(visible);
    if(previous!=front || !visible) {
        assert(!memcmp(old_cells,previous?HEART_BACK_CELLS:HEART_CELLS,sizeof(old_cells)));
        assert(!memcmp(old_magic,previous?MAGIC_BACK_CELLS:MAGIC_CELLS,sizeof(old_magic)));
    }
    if(visible) {
        full_reference(expected,meter);
        assert(!memcmp(expected,front?HEART_BACK_CELLS:HEART_CELLS,sizeof(expected)));
        assert(!memcmp(meter,front?MAGIC_BACK_CELLS:MAGIC_CELLS,sizeof(meter)));
    }
    for(unsigned i=0;i<90;++i) {
        unsigned tile=i<60?(front?0x11000u:0x10000u)/32+i:
                                   (front?0x11780u:0x10b00u)/32+i-60;
        assert(names[(2+i/15)*64+2+i%15]==(visible?(0x4000u|tile):0x2000u/32));
    }
    for(unsigned i=0;i<16;++i)assert(vram[i]==0xa5a5);
    assert(vram[0x800+960]==0xa5a5);
}
int main(void) {
    memset(vram,0xa5,sizeof(vram));
    /* Asymmetric transparent edges expose ghosts from shrinking hearts,
     * overlap with neighbours, and all five quarter-heart source images. */
    for(unsigned i=0;i<320;++i)HEART_SOURCE[i]=HEART_ATLAS[i]=(unsigned short)((i*1709u)^(i>>2));
    for(unsigned i=0;i<128;++i)meter_end[i]=i%3?13:0;
    for(unsigned i=0;i<16;++i)meter_mid[i]=i%4?12:0;
    for(unsigned i=0;i<7;++i)meter_fill[i]=14;
    save_state.health=save_state.health_capacity=48;
    for(unsigned k=0;k<30;++k){tick=k*3;verify(true);verify(true);}
    /* Every pulse location and every fill fraction, both heart rows, then
     * shrinking capacity. Magic crosses the heart-bank boundary at row10. */
    for(unsigned capacity=0;capacity<=21;++capacity) {
        save_state.health_capacity=capacity*16;
        for(unsigned health=0;health<=capacity*16;health+=5) {
            save_state.health=health;
            save_state.source_magic_level=capacity%3;
            magic_capacity=(capacity%3)*48;
            save_state.source_magic=(health/5)%(magic_capacity+1u);
            for(unsigned p=0;p<4;++p){tick+=3;verify(true);}
        }
    }
    /* Consumption and capacity growth with the pulse repeatedly changing
     * direction; the offscreen bank must catch up to the latest magic. */
    save_state.health_capacity=save_state.health=320;
    save_state.source_magic_level=2;
    for(unsigned capacity=0;capacity<=96;capacity+=8) {
        magic_capacity=capacity;
        for(unsigned amount=0;amount<=capacity;++amount) {
            save_state.source_magic=amount;tick+=3;verify(true);
        }
    }
    for(unsigned k=0;k<100;++k) {
        save_state.source_magic=99-k;tick+=3;verify(true);
    }
    /* Hidden->visible keeps valid banks; reset invalidates BOTH banks even
     * when its first draw is hidden (scene/pause restoration). */
    for(unsigned k=0;k<5;++k){tick+=3;verify(false);}
    tick+=3;verify(true);
    for(unsigned k=0;k<4;++k) {
        health_hud_reset();
        memset(HEART_CELLS,0x77,1920);memset(HEART_BACK_CELLS,0x33,1920);
        memset(MAGIC_CELLS,0x55,960);memset(MAGIC_BACK_CELLS,0x11,960);
        if(k&1)verify(false);
        for(unsigned p=0;p<4;++p){tick+=3;verify(true);}
    }
    /* Verify reduced bus writes, not merely equal final pixels: poison the
     * inactive banks. A pulse may touch only its nine maximum-footprint cells;
     * unchanged magic must not be rewritten. This case intentionally ignores
     * poisoned stationary cells, then resets before testing visuals again. */
    save_state.health=save_state.health_capacity=48;
    save_state.source_magic_level=0;magic_capacity=0;save_state.source_magic=0;
    for(unsigned p=0;p<4;++p){tick+=3;verify(true);}
    unsigned next=front^1u;
    unsigned short *back=next?HEART_BACK_CELLS:HEART_CELLS;
    unsigned short *back_magic=next?MAGIC_BACK_CELLS:MAGIC_CELLS;
    memset(back,0x66,1920);memset(back_magic,0x77,960);
    tick+=3;health_hud_draw(true);assert(front==next);
    /* Third heart centre (34,10): max footprint cells x3..5,y0..2. */
    for(unsigned cell=0;cell<60;++cell)for(unsigned w=0;w<16;++w)
        if(cell%15<3 || cell%15>5 || cell/15>2)assert(back[cell*16+w]==0x6666);
    for(unsigned w=0;w<480;++w)assert(back_magic[w]==0x7777);
    health_hud_reset();tick+=3;verify(true);tick+=3;verify(true);
    return 0;
}
'''
        self.run_c(source)
