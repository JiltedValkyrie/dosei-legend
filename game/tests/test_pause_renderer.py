"""Actual pause renderer against bounded fake VRAM and SGL registers."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')

@unittest.skipUnless(GCC.exists(),'host compiler required')
class Renderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        code=(ROOT/'src/pause_windows.c').read_text()
        code=re.sub(r'^#include .*$', '',code,flags=re.M)
        code=code.replace('0x25E3C000u','(vram+0x3C000)').replace('0x25E40000u','(vram+0x40000)').replace('0x25E68000u','(vram+0x68000)')
        code=code.replace('((unsigned)cell(tile)-0x25E00000u)','((uintptr_t)cell(tile)-(uintptr_t)vram)')
        a=code.index('static bool read_file(');b=code.index('static bool begin(',a)
        code=code[:a]+r'''static bool read_file(const char *name, void *data, unsigned size) {
    ++reads;
    if (fail_reads) return false;
    if (name[5]=='F') memset(data,255,size);
    else { unsigned i; for(i=0;i<size/2;++i) ((unsigned short *)data)[i]=0x8000+name[5]; }
    return true;
}
'''+code[b:]
        pre=r'''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "pause_window_state.h"
#include "ram_cart.h"
#include "pause_cursor_data.h"
static unsigned char vram[0x80000], cart[RAM_CART_FIXED_BYTES];
static unsigned short regs[6];
static unsigned now,reads,fail_reads;
static int zx,zy,sx,sy,wl,wt,wr,wb;
static struct {pause_window_state_t pause_window;unsigned owned,equipped;} gameplay;
static struct {unsigned stick_owned,slingshot,quest_items; unsigned char c_items[3];} save_state;
#define QUEST_KOKIRI_EMERALD 0
#define GP_SWORD 1
#define GP_SHIELD 2
#define JO_VDP2_CYCB0L regs[0]
#define JO_VDP2_CYCB0U regs[1]
#define JO_VDP2_CYCB1L regs[2]
#define JO_VDP2_CYCB1U regs[3]
#define JO_VDP2_CYCA1L regs[4]
#define JO_VDP2_CYCA1U regs[5]
#define JO_VDP2_CRAM 0
#define VDP2_VRAM_B1 (vram+0x60000)
#define NBG0_MAP (vram+0x76000)
#define COL_TYPE_32768 3
#define COL_TYPE_256 1
#define CHAR_SIZE_1x1 0
#define PNB_1WORD 0x8000
#define PNB_2WORD 0
#define CN_10BIT 0
#define PL_SIZE_1x1 0
#define ZOOM_HALF 1
#define ZOOM_1 0
#define win0_IN 3
#define slCharNbg0(a,b) ((void)0)
#define slPageNbg0(a,b,c) ((void)0)
#define slPlaneNbg0(a) ((void)0)
#define slMapNbg0(a,b,c,d) ((void)0)
#define slZoomModeNbg0(a) ((void)0)
#define slScrWindowModeNbg0(a) ((void)0)
static void slZoomNbg0(int x,int y) {zx=x;zy=y;}
static void slScrPosNbg0(int x,int y) {sx=x;sy=y;}
static void slScrWindow0(int a,int b,int c,int d) {wl=a;wt=b;wr=c;wb=d;}
static unsigned demo_clock(void) {return now;}
void *ram_cart_fixed(unsigned offset,unsigned bytes) {return offset+bytes<=sizeof(cart) ? cart+offset : 0;}
'''
        post=r'''
void reset(void) {
    pause_windows_reset(); memset(&gameplay,0,sizeof(gameplay));
    memset(vram,0x5a,sizeof(vram)); memset(cart,0,sizeof(cart));
    now=reads=fail_reads=0; for(int i=0;i<6;++i) regs[i]=0x1234+i;
}
int step(unsigned tick,int page) {now=tick;gameplay.pause_window.page=page;return pause_windows_update();}
int value(int i) {int v[]={zx,zy,sx,sy,wl,wt,wr,wb,(int)reads,loaded,(int)phase};return v[i];}
int restored(void) {for(unsigned i=0;i<sizeof(vram);++i) if(vram[i]!=0x5a) return 0;return 1;}
int untouched(void) {
    for(unsigned i=0;i<0x3c000;++i) if(vram[i]!=0x5a) return 0;
    for(unsigned i=0x60000;i<0x68000;++i) if(vram[i]!=0x5a) return 0;
    for(unsigned i=0x6d880;i<0x80000;++i) if(vram[i]!=0x5a) return 0;
    return 1;
}
void fail(void) {fail_reads=1;}
void cursor(void) {gameplay.pause_window.cursor[0]=1;}
int pixel_at(int x,int y) {return cell((y/8)*40+x/8)[(y&7)*8+(x&7)];}
'''
        src=Path(cls.tmp.name,'renderer.c');src.write_text(pre+code+post)
        dll=src.with_suffix('.dll');env=dict(os.environ);env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-std=c99','-Wall','-Werror','-Wno-misleading-indentation',
                        '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),str(src),'-o',str(dll)],check=True,env=env)
        cls.lib=ctypes.CDLL(str(dll))
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.lib.reset()
    def test_vram_and_identity_scale_restored_on_close(self):
        self.assertEqual(self.lib.step(0,0),1)
        self.assertEqual([self.lib.value(i) for i in range(4)],[65536,65536,0,0])
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)
        self.assertEqual([self.lib.value(i) for i in range(4)],[65536,65536,0,0])
    def test_both_directions_use_reciprocal_scale_and_finish_at_identity(self):
        for page in (1,5):
            self.lib.reset();self.lib.step(0,0);self.lib.step(1,page)
            self.lib.step(7,page)
            self.assertLess(self.lib.value(0),65536)
            self.assertGreaterEqual(self.lib.value(0),65536*320//384)
            self.assertEqual(self.lib.value(8),2) # no read during departure
            self.lib.step(13,page)
            self.assertEqual(self.lib.value(0),65536*320//384)
            self.assertEqual(self.lib.value(8),3)
            self.lib.step(25,page)
            self.assertEqual([self.lib.value(i) for i in range(4)],[65536,65536,0,0])
            self.assertEqual(self.lib.value(9),page*4)
    def test_failed_page_read_restores_hud_before_reporting_failure(self):
        self.lib.step(0,0);self.lib.step(1,1);self.lib.fail()
        self.assertEqual(self.lib.step(13,1),0)
        self.assertEqual(self.lib.restored(),1)
        self.assertTrue(self.lib.pause_windows_failed())
    def test_cursor_and_text_never_seek_disc(self):
        self.lib.step(0,0);n=self.lib.value(8)
        self.lib.cursor();self.lib.step(1,0)
        self.lib.pause_windows_print(0,0,b'A')
        self.assertEqual(self.lib.pixel_at(0,0),0xffff)
        self.lib.pause_windows_print(0,0,b'\x80')
        self.assertEqual(self.lib.pixel_at(0,0),0x8030)
        self.assertEqual(self.lib.value(8),n)
    def test_visible_room_bitmap_and_font_are_never_overwritten(self):
        self.lib.step(0,0)
        self.assertEqual(self.lib.untouched(),1)
        self.lib.step(1,1);self.lib.step(13,1)
        self.assertEqual(self.lib.untouched(),1)
    def test_fast_page_changes_queue_without_painting_wrong_page_text(self):
        self.lib.step(0,0);self.lib.step(1,1);self.lib.step(13,1)
        self.lib.step(14,2)
        self.assertFalse(self.lib.pause_windows_text_ready())
        self.lib.step(25,2);self.lib.step(26,2);self.lib.step(38,2);self.lib.step(50,2)
        self.assertEqual(self.lib.value(9),8)
        self.assertTrue(self.lib.pause_windows_text_ready())
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)

if __name__=='__main__':unittest.main()
