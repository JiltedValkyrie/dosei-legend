"""Run the real equipment selector with indexed polygon/attribute records."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT/'build/generated'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class EquipmentDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        text = (ROOT/'src/kokiri_sgl.c').read_text()
        start = text.index('#include "link_equipment.h"')
        helpers = text[start:text.index('void                kokiri_scene_draw',start)]
        start = text.index('void                kokiri_link_draw')
        draw = text[start:text.index('/* Base child-day actor list',start)]
        adapter = '''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "gameplay.h"
#include "save_state.h"
#include "link_equipment.h"
#define LINK_FRAMES_FROM_DISC
#include "link_age.h"
#include "adult_link.h"
#include "ram_low.h"
static unsigned int fake_low[RAM_LOW_USED_BYTES/4];
#undef RAM_LOW
#define RAM_LOW(offset) ((void *)((unsigned char *)fake_low + (offset)))
typedef int FIXED;
typedef unsigned short ANGLE;
#define CUTSCENE_NIGHTMARE 0
#define Dual_Plane 1
#define SORT_CEN 3
#define UseNearClip 64
#define No_Gouraud 0
#define ECdis 128
#define sprPolygon 4
#define No_Option 0
#define C_RGB(r,g,b) ((r)|((g)<<5)|((b)<<10))
#define ATTRIBUTE(plane,sort,tex,col,gouraud,attr,dir,option) (0x80000000u|(col))
static bool stick;
static bool ocarina;
static unsigned filter,draw_filter,filter_calls;
static int cosine;
static unsigned oot_core_ocarina_state(void) { return ocarina ? 1 : 0; }
static void kokiri_camera_sincos(unsigned angle,int32_t *sn,int32_t *cs) { (void)angle;*sn=0;*cs=cosine; }
static void kokiri_hit_filter(unsigned value) {filter=value;++filter_calls;}
static bool player_items_stick(void) { return stick; }
static bool cutscene_is_playing(void) { return false; }
static unsigned cutscene_id(void) { return 0; }
static void slScale(int x,int y,int z) {}
static void slRotY(ANGLE y) {}
typedef unsigned int POLYGON;
typedef unsigned int ATTR;
typedef struct { void *pntbl; unsigned int nbPoint; POLYGON *pltbl; unsigned int nbPolygon; ATTR *attbl; } PDATA;
static POLYGON polygons[1024]; static ATTR attributes[1024];
static PDATA link_pdata = {0,323,polygons,0,attributes};
gameplay_t gameplay;
save_state_t save_state;
const link_age_model_t *link_age_model;
static uint32_t adult_storage[2048];
static PDATA drawn;
static unsigned int submissions;
static void submit(PDATA *p, unsigned int bit) { drawn=*p;draw_filter=filter;++submissions; }
static void jo_3d_push_matrix(void) {}
static void jo_3d_pop_matrix(void) {}
static void jo_3d_translate_matrix(int x,int y,int z) {}
static void jo_3d_rotate_matrix_y(int y) {}
'''
        skin = (ROOT/'build/cd/ADULTSKN.BIN').read_bytes()
        cls.adult_vertices = struct.unpack_from('>I', skin, 8)[0]
        cls.adult_polygons = struct.unpack_from('>I', skin, 12)[0]
        cls.adult_groups = [struct.unpack_from('>2H', skin, 40 + i * 4) for i in range(9)]
        mask_start = 244 + ((cls.adult_vertices + 3) & ~3) + cls.adult_vertices * 6
        cls.adult_tunics = skin[mask_start:]
        wrapper = ('static const uint16_t adult_groups[9][2]={' +
                   ','.join('{%d,%d}' % pair for pair in cls.adult_groups) + '};\n' +
                   'static const unsigned char adult_tunics[]={' +
                   ','.join(str(byte) for byte in cls.adult_tunics) + '};\n') + '''
void reset_gear(void) {
 memset(&gameplay,0,sizeof gameplay);memset(&save_state,0,sizeof save_state);
 stick=ocarina=false;link_age_model=0;filter=draw_filter=filter_calls=0;
 invalidate_equipped();
}
void choose_age(int adult) {
 link_age_model_t *model=(link_age_model_t *)adult_storage;
 memset(model,0,sizeof adult_storage);model->vertices=ADULT_LINK_VERTEX_COUNT;
 memcpy(model->gear,adult_groups,sizeof adult_groups);
 memcpy((unsigned char *)(model+1)+((model->vertices+3u)&~3u)+model->vertices*sizeof(link_vec3_t),
        adult_tunics,sizeof adult_tunics);
 link_age_model=adult ? model : 0;invalidate_equipped();
}
void play_ocarina(int on) {ocarina=on;}
void choose_tunic(unsigned tunic) {save_state.tunic=tunic;}
void hurt(int timer,int dead,int wave) {gameplay.hurt_flash_timer=timer;gameplay.dead=dead;cosine=wave;}
unsigned flash(void) {return draw_filter;}
unsigned filter_restored(void) {return filter==0;}
unsigned saved_gear(void) {return gameplay.equipped;}
unsigned points(void) {return drawn.nbPoint;}
void hold_stick(int on) { stick = on; }
void select_gear(unsigned int mask) {
 unsigned int i;
 for(i=0;i<1024;++i) { polygons[i]=i; attributes[i]=i+1000; }
 gameplay.equipped=mask; submissions=0; kokiri_link_draw(0,0,0,0);
}
unsigned int calls(void) { return submissions; }
unsigned int count(void) { return drawn.nbPolygon; }
unsigned int polygon(unsigned int i) { return drawn.pltbl[i]; }
unsigned int attribute(unsigned int i) { return drawn.attbl[i]; }
'''
        output = Path(cls.temp.name)/'gear.dll'
        env = dict(os.environ, PATH=str(GCC.parent)+os.pathsep+os.environ.get('PATH',''))
        subprocess.run([str(GCC),'-shared','-O2','-I'+str(ROOT/'src'),'-I'+str(GEN),
                        '-x','c','-','-o',str(output)],input=adapter+helpers+draw+wrapper,
                       text=True,env=env,check=True)
        cls.lib=ctypes.CDLL(str(output))
        cls.lib.attribute.restype=ctypes.c_uint
        cls.defines={m[0]:int(m[1]) for m in re.findall(r'#define (LINK_\w+) (\d+)',
                     (GEN/'link_equipment.h').read_text())}

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def setUp(self): self.lib.reset_gear()

    def expected(self, groups, adult=False):
        names=['BODY','LEFT_EMPTY','LEFT_SWORD','RIGHT_EMPTY','RIGHT_SHIELD',
               'SHEATH','SHEATH_SWORD','SHEATH_SHIELD','RH_OCARINA']
        result=[]
        for group in groups:
            if adult:
                first,count=self.adult_groups[names.index(group)]
            else:
                first=self.defines['LINK_'+group+'_FIRST']
                count=self.defines['LINK_'+group+'_COUNT']
            result.extend(range(first,first+count))
        return result

    def actual(self): return [self.lib.polygon(i) for i in range(self.lib.count())]

    def test_all_equipment_combinations_and_reselection(self):
        for adult in (False,True,False):
            self.lib.choose_age(adult)
            for mask in (0,1,3,2,0,3,3):
                self.lib.select_gear(mask)
                self.assertEqual(self.lib.calls(),1, 'must transform shared points only once')
                groups=['BODY','LEFT_SWORD' if mask&1 else 'LEFT_EMPTY',
                        'RIGHT_SHIELD' if mask&2 else 'RIGHT_EMPTY']
                if mask&1: groups.append('SHEATH')
                actual=self.actual()
                self.assertEqual(sorted(actual),sorted(self.expected(groups,adult)))
                self.assertEqual(len(actual),len(set(actual)))
                self.assertLessEqual(len(actual),self.defines['LINK_VISIBLE_POLYGONS'])
                self.assertEqual(self.lib.points(), self.adult_vertices if adult else self.defines['LINK_BASE_VERTICES'])
                for i,p in enumerate(actual): self.assertEqual(self.lib.attribute(i),p+1000)

    def test_held_stick_hides_sword_without_changing_saved_equipment(self):
        self.lib.hold_stick(1)
        self.lib.select_gear(3)
        without=[self.lib.polygon(i) for i in range(self.lib.count())]
        self.lib.hold_stick(0)
        self.lib.select_gear(2)
        self.assertEqual(without,[self.lib.polygon(i) for i in range(self.lib.count())])
        self.lib.select_gear(3)
        self.assertGreater(self.lib.count(),len(without))

    def test_ocarina_uses_right_hand_and_back_sheath_for_both_ages(self):
        for adult in (False,True):
            self.lib.choose_age(adult)
            for mask in (0,1,3,2,3):
                self.lib.play_ocarina(1)
                self.lib.select_gear(mask)
                groups=['BODY','LEFT_EMPTY','RH_OCARINA']
                if mask&1: groups.append('SHEATH_SHIELD' if mask&2 else 'SHEATH_SWORD')
                self.assertEqual(self.actual(),self.expected(groups,adult))
                self.assertEqual(self.lib.saved_gear(),mask)
                self.assertEqual(self.lib.calls(),1)
                self.lib.play_ocarina(0)
                self.lib.select_gear(mask)
                self.assertNotEqual(self.actual(),self.expected(groups,adult))

    def test_adult_tunic_materials_rebuild_without_changing_geometry(self):
        self.lib.choose_age(1)
        self.lib.select_gear(3)
        baseline=self.actual()
        for tunic,colour in ((1,31<<10),(2,25),(0,0)):
            self.lib.choose_tunic(tunic)
            self.lib.select_gear(3)
            self.assertEqual(self.actual(),baseline)
            for i,p in enumerate(baseline):
                tinted=tunic and self.adult_tunics[p//8]&(1<<(p%8))
                self.assertEqual(self.lib.attribute(i),(0x80000000|colour) if tinted else p+1000)

    def test_hurt_filter_resets_after_shared_equipment_submission(self):
        for wave,level in ((-65536,1),(0,8),(65536,16)):
            self.lib.hurt(4,0,wave)
            self.lib.select_gear(3)
            self.assertEqual(self.lib.flash(),level)
            self.assertEqual(self.lib.filter_restored(),1)
        self.lib.hurt(4,1,65536)
        self.lib.select_gear(3)
        self.assertEqual(self.lib.flash(),0)
