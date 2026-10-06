"""Production chest/CD freeze sequencing and VDP1 tint lifetime, without emulator."""
import ctypes as C
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
GCC=Path('C:/msys64/mingw64/bin/gcc.exe')
def function(text, marker):
    start=text.index(marker); brace=text.index('{',start); depth=1; end=brace+1
    while depth:
        depth+=(text[end]=='{')-(text[end]=='}');end+=1
    return text[start:end]
@unittest.skipUnless(GCC.exists(),'host compiler required')
class Presentation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        recomp=(ROOT/'src/recomp.c').read_text(encoding='utf-8')
        draw=(ROOT/'src/kokiri_sgl.c').read_text(encoding='utf-8')
        freeze=recomp[recomp.index('    if(frozen_fanfare) {'):recomp.index('    jo_img patch;',recomp.index('    if(frozen_fanfare) {'))]
        source=r'''#include <stdbool.h>
#include <stdint.h>
#include <string.h>
static unsigned ticks,chest_start,fanfare_start,previous_tick;
static uint8_t chest_scene;
static bool frozen_fanfare,item_fanfare_pending,busy;
static unsigned played,restored,camera_steps,combat_input;
static struct {unsigned get_item,get_item_age;} gameplay;
static struct {bool visible;} level_select;
#define NA_BGM_ITEM_GET 34
#define NA_BGM_GREAT_FAIRY 40
bool cdda_busy(void){return busy;}
bool music_play(unsigned song){played=song;busy=true;return true;}
void player_input_reset(void){}
void combat_input_cancel(void *p){(void)p;}
void chest_scene_step(void){++camera_steps;}
void snap_camera_to_link(void){++restored;}
''' + function(recomp,'bool recomp_chest_opening(void)') + function(recomp,'unsigned recomp_chest_frame(void)') + r'''
void advance(unsigned now,int playing){ticks=now;busy=playing;
''' + freeze + r'''
}
void reset_chest(void){ticks=chest_start=fanfare_start=0;chest_scene=1;frozen_fanfare=true;item_fanfare_pending=true;played=restored=0;gameplay.get_item=1;gameplay.get_item_age=0;}
unsigned state(unsigned n){return n==0?frozen_fanfare:n==1?played:n==2?restored:n==3?gameplay.get_item_age:previous_tick;}
#define CL_Gouraud 4
#define No_Gouraud 0
#define FALSE 0
typedef struct {unsigned atrb,gstb;} ATTR;
typedef struct {int nbPolygon;ATTR *attbl;} PDATA;
static unsigned hit_filter,texture_base=0x20000,hit_table_offset=0x1000;
static unsigned kokiri_rejected,kokiri_accepted_mask,submitted,seen_mode,seen_table;
static int accept=1;
int slPutPolygon(PDATA *p){seen_mode=p->attbl[0].atrb;seen_table=p->attbl[0].gstb;return accept;}
''' + function(draw,'static void         submit(') + r'''
unsigned draw_test(unsigned level,unsigned accepts,unsigned field){ATTR a={0x100,0};PDATA p={1,&a};hit_filter=level;accept=accepts;submit(&p,8);return field==0?seen_mode:field==1?seen_table:field==2?a.atrb:a.gstb;}
'''
        out=Path(cls.tmp.name)/'presentation.dll'
        env=dict(os.environ,PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-x','c','-','-o',str(out)],input=source,text=True,check=True,env=env)
        cls.lib=C.CDLL(str(out))
        cls.lib.recomp_chest_opening.restype=C.c_bool
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_chest_pose_waits_for_song_then_queues_item_once_and_releases(self):
        g=self.lib;g.reset_chest();g.advance(120,1)
        self.assertTrue(g.recomp_chest_opening());self.assertEqual(g.recomp_chest_frame(),40)
        self.assertEqual(g.state(1),0)
        g.advance(520,0)
        self.assertFalse(g.recomp_chest_opening());self.assertEqual(g.recomp_chest_frame(),132)
        self.assertEqual(g.state(1),34);self.assertEqual(g.state(2),1)
        g.advance(580,1);self.assertEqual(g.state(3),30)
        self.assertTrue(g.state(0))
        g.advance(760,0);self.assertFalse(g.state(0));self.assertEqual(g.state(4),760)
    def test_failed_cd_start_still_runs_opening_animation_before_item(self):
        g=self.lib;g.reset_chest();g.advance(3,0)
        self.assertTrue(g.recomp_chest_opening());self.assertEqual(g.state(1),0)
        g.advance(396,0);self.assertEqual(g.state(1),34)
    def test_tint_table_address_and_attributes_restored_even_when_rejected(self):
        g=self.lib
        for accepted in (0,1):
            for tint in (1,16,17,32):
                self.assertEqual(g.draw_test(tint,accepted,0),0x104)
                self.assertEqual(g.draw_test(tint,accepted,1),0x21000//8+tint-1)
                self.assertEqual(g.draw_test(tint,accepted,2),0x100)
                self.assertEqual(g.draw_test(tint,accepted,3),0)
        self.assertEqual(g.draw_test(0,1,0),0x100)
if __name__=='__main__':unittest.main()
