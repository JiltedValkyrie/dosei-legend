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
    else { unsigned i; for(i=0;i<size/2;++i) ((unsigned short *)data)[i]=0x8000+name[5];
        if(name[5]=='1' && name[6]!='0') ((unsigned short *)data)[40*320+120]=0x1A;
    }
    return true;
}
'''+code[b:]
        pre=r'''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include "save_state.h"
#include "pause_inventory_data.h"
#include "pause_window_state.h"
#include "ram_cart.h"
#include "pause_cursor_data.h"
#include "dungeon_map_data.h"
static unsigned char vram[0x80000], original_vram[0x80000], cart[RAM_CART_FIXED_BYTES];
static unsigned short regs[6];
static unsigned cycle_regs[4];
static void *sgl_vdp2_shadow(unsigned reg) {return cycle_regs+(reg-0x10)/4;}
static void slScrCycleSet(unsigned a,unsigned b,unsigned c,unsigned d) {
    cycle_regs[0]=a;cycle_regs[1]=b;cycle_regs[2]=c;cycle_regs[3]=d;
}
static unsigned now,reads,fail_reads,heap_calls;
static bool atlas_ready;
static bool minimap_icons_ready(void) {return atlas_ready;}
static int zx,zy,sx,sy,wl,wt,wr,wb;
static struct {pause_window_state_t pause_window;unsigned owned,equipped;} gameplay;
static struct {unsigned oot_scene;} entry={85};
static const void *scene_flow_entry_raw(void) {return &entry;}
#define scene_flow_entry() ((const __typeof__(entry) *)scene_flow_entry_raw())
static unsigned scene_flow_scene(void) {return entry.oot_scene;}
static const char *scene_name(unsigned scene) {return scene==85 ? "Kokiri Forest" : "Other Scene";}
#define jo_malloc(n) (heap_calls++,malloc(n))
#define jo_free free
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
    FILE *f=fopen(ICON_FILE,"rb");
    if(!f || fread(vram+0x52000,1,PAUSE_ICON_BYTES,f)!=PAUSE_ICON_BYTES) exit(1);
    fclose(f); memcpy(original_vram,vram,sizeof(vram));
    memset(&save_state,0,sizeof(save_state));
    atlas_ready=true; now=reads=fail_reads=heap_calls=0; for(int i=0;i<6;++i) regs[i]=0x1234+i;
}
int step(unsigned tick,int page) {now=tick;gameplay.pause_window.page=page;return pause_windows_update();}
int value(int i) {int v[]={zx,zy,sx,sy,wl,wt,wr,wb,(int)reads,loaded,(int)phase,(int)heap_calls};return v[i];}
int restored(void) {return !memcmp(vram,original_vram,sizeof(vram));}
int untouched(void) {
    for(unsigned i=0;i<0x3c000;++i) if(vram[i]!=0x5a) return 0;
    for(unsigned i=0x60000;i<0x68000;++i) if(vram[i]!=0x5a) return 0;
    for(unsigned i=0x6d880;i<0x80000;++i) if(vram[i]!=0x5a) return 0;
    return 1;
}
void dungeon(unsigned floor,unsigned visited,unsigned items) {
    save_state.scene_id=2;save_state.deku_visited_rooms=visited;save_state.deku_dungeon_items=items;
    gameplay.pause_window.cursor[PAUSE_MAP]=floor;
}
int palette(unsigned tag) {return map_colour(tag);}
void fail(void) {fail_reads=1;}
void cursor(void) {gameplay.pause_window.cursor[0]=1;}
int pixel_at(int x,int y) {return cell((y/8)*40+x/8)[(y&7)*8+(x&7)];}
void full_inventory(void) {save_test_max_gear();}
void region(unsigned scene) {entry.oot_scene=scene;}
void age(unsigned child) {save_state.link_age=!!child;}
void missing_atlas(void) {atlas_ready=false;}
int cached_at(int x,int y) {return cache()[y*320+x];}
int item_frame_slot(unsigned action) {return save_c_item_inventory_slot(action);}
'''
        pre='#define ICON_FILE "'+(ROOT/'build/cd/PAUSEINV.BIN').as_posix()+'"\n'+pre
        src=Path(cls.tmp.name,'renderer.c');src.write_text(pre+code+post)
        dll=src.with_suffix('.dll');env=dict(os.environ);env['PATH']=str(GCC.parent)+os.pathsep+env.get('PATH','')
        subprocess.run([str(GCC),'-shared','-std=c99','-Wall','-Werror','-Wno-misleading-indentation',
                        '-I'+str(ROOT/'src'),'-I'+str(ROOT/'build/generated'),str(src),str(ROOT/'src/save_state.c'),'-o',str(dll)],check=True,env=env)
        cls.lib=ctypes.CDLL(str(dll))
        cls.lib.pause_windows_item_name.restype=ctypes.c_char_p
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):self.lib.reset()
    def test_dungeon_floor_variant_and_visited_palette(self):
        self.lib.dungeon(1,1,2)
        self.assertEqual(self.lib.step(0,1),1)
        self.assertEqual(self.lib.value(9),34)
        self.assertEqual(self.lib.palette(10),0xFD40)
        self.assertEqual(self.lib.pixel_at(120,40),0xFD40)
        self.assertEqual(self.lib.palette(1),0xBDEF)
        self.lib.dungeon(1,3,0)
        self.assertEqual(self.lib.palette(1),0xFD40)
        self.assertEqual(self.lib.palette(2),0x8C41)
        self.lib.dungeon(4,1,2)
        self.lib.step(1,1)
        self.assertEqual(self.lib.value(9),37)
        self.assertEqual(self.lib.palette(10),0xBDEF)
        self.assertEqual(self.lib.pixel_at(120,40),0xBDEF)
        self.assertEqual(self.lib.value(10),0) # floors do not turn the carousel
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)

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
            self.assertEqual(self.lib.value(8),2) # font and first page only; atlas reused
            self.lib.step(13,page)
            self.assertEqual(self.lib.value(0),65536*320//384)
            self.assertEqual(self.lib.value(8),3)
            self.lib.step(25,page)
            self.assertEqual([self.lib.value(i) for i in range(4)],[65536,65536,0,0])
            self.assertEqual(self.lib.value(9),page*32)
    def test_failed_page_read_restores_hud_before_reporting_failure(self):
        self.lib.step(0,0);self.lib.step(1,1);self.lib.fail()
        self.assertEqual(self.lib.step(13,1),0)
        self.assertEqual(self.lib.restored(),1)
        self.assertTrue(self.lib.pause_windows_failed())
    def test_unready_atlas_fails_before_overwriting_vram_or_reading_disc(self):
        self.lib.missing_atlas()
        self.assertEqual(self.lib.step(0,0),0)
        self.assertEqual(self.lib.value(8),0)
        self.assertEqual(self.lib.restored(),1)
        self.assertTrue(self.lib.pause_windows_failed())
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)
    def test_pause_reuses_source_atlas_without_allocating_or_reloading(self):
        self.assertEqual(self.lib.step(0,0),1)
        self.assertEqual(self.lib.value(8),2)
        self.assertEqual(self.lib.value(11),0)
        self.assertEqual(self.lib.pause_windows_item_name(8),b'Ocarina Of Time')
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)
        self.assertEqual(self.lib.pause_windows_item_name(8),b'')
        self.assertEqual(self.lib.step(1,0),1)
        self.assertEqual(self.lib.value(8),4)
        self.assertEqual(self.lib.value(11),0)
    def test_cursor_and_text_never_seek_disc(self):
        self.lib.step(0,0);n=self.lib.value(8)
        self.lib.cursor();self.lib.step(1,0)
        self.lib.pause_windows_print(0,0,b'A')
        self.assertEqual(self.lib.pixel_at(0,0),0xffff)
        self.lib.pause_windows_print(0,0,b'\x80')
        self.assertEqual(self.lib.pixel_at(0,0),0x8030)
        self.assertEqual(self.lib.value(8),n)
    def test_all_items_and_quest_bits_render_from_source_save(self):
        self.lib.full_inventory()
        self.assertEqual(self.lib.step(0,0),1)
        # Every source slot in the capped loadout paints its own icon.
        for slot in range(24):
            x,y=66+(slot%6)*32,64+(slot//6)*32
            pixels=[self.lib.cached_at(x+dx,y+dy) for dx in range(28) for dy in range(28)]
            self.assertGreater(len(set(pixels)),2,slot)
        self.assertEqual(self.lib.pause_windows_item_name(8),b'Ocarina Of Time')
        self.lib.step(1,2);self.lib.step(13,2);self.lib.step(25,2)
        import struct
        blob=(ROOT/'build/cd/PAUSEINV.BIN').read_bytes()
        for q in range(24):
            item,x,y,w,h=struct.unpack_from('>H4B',blob,q*6)
            pixels=[self.lib.cached_at(x+dx,y+dy) for dx in range(w) for dy in range(h)]
            self.assertGreater(len(set(pixels)),2,q)
        self.assertEqual(self.lib.item_frame_slot(4),7)
    def test_world_marker_follows_current_source_scene(self):
        import struct
        blob=(ROOT/'build/cd/PAUSEINV.BIN').read_bytes()
        for scene in (85,82,99): # Kokiri, Kakariko, Ranch
            self.lib.reset();self.lib.region(scene);self.lib.step(0,1)
            x,y=struct.unpack_from('>HH',blob,144+scene*4)
            self.assertNotEqual((x,y),(0,0))
            self.assertEqual(self.lib.pixel_at(x+7,y),0xffff)
    def test_shared_bazaar_and_gallery_marker_follow_source_age_exception(self):
        import struct
        blob=(ROOT/'build/cd/PAUSEINV.BIN').read_bytes()
        for scene in (0x2c,0x42):
            for child in (0,1):
                self.lib.reset();self.lib.region(scene);self.lib.age(child);self.lib.step(0,1)
                marker_scene=scene if child else 0x52
                x,y=struct.unpack_from('>HH',blob,144+marker_scene*4)
                self.assertNotEqual((x,y),(0,0))
                self.assertEqual(self.lib.pixel_at(x+7,y),0xffff)
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
        self.assertEqual(self.lib.value(9),64)
        self.assertTrue(self.lib.pause_windows_text_ready())
        self.lib.pause_windows_reset()
        self.assertEqual(self.lib.restored(),1)

if __name__=='__main__':unittest.main()
