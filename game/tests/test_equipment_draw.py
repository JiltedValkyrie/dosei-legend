"""Run the real equipment selector with indexed polygon/attribute records."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
import struct
import tempfile
import unittest

from test_graphics_backend import function

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT/'build/generated'
GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


@unittest.skipUnless(GCC.is_file(), 'host compiler required')
class EquipmentDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        source = ROOT/'src/kokiri_sgl.c'
        text = source.read_text()
        start = text.index('#include "link_equipment.h"')
        # Keep the actual selector and draw function; unrelated texture loading,
        # scene haze and first-person rendering need different fixtures.
        helpers = text[start:text.index('/* ---- Adult hero gear',start)]
        start = text.index('enum { GEAR_LEFT_MASTER')
        helpers += text[start:text.index(';',start)+1]
        helpers += function(source,'static void link_part(')
        draw = function(source,'void                kokiri_link_draw(')
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
#define C_RGB(r,g,b) (0x8000u|(r)|((g)<<5)|((b)<<10))
#define ATTRIBUTE(plane,sort,tex,col,gouraud,attr,dir,option) {plane,sort,tex,attr,col,gouraud,dir}
static bool stick;
static bool ocarina;
static bool sword_out,gear_ready;
static unsigned gear_active,drawn_gear;
static bool recomp_sword_out(void) { return sword_out; }
static void gear_draw(void) { drawn_gear=gear_active; }
static void kokiri_actor_shadow(int x,int y,int z,int radius) {}
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
/* Match SGL's 20-byte POLYGON and 12-byte ATTR so the actual RAM carve
 * checks and record copies remain meaningful on the host. */
typedef struct { int32_t norm[3]; uint16_t Vertices[4]; } POLYGON;
typedef struct { uint8_t flag,sort; uint16_t texno,atrb,colno,gstb,dir; } ATTR;
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
        assert any(cls.adult_tunics), "adult tunic mask empty: tunic colours cannot apply"
        wrapper = ('static const uint16_t adult_groups[9][2]={' +
                   ','.join('{%d,%d}' % pair for pair in cls.adult_groups) + '};\n' +
                   'static const unsigned char adult_tunics[]={' +
                   ','.join(str(byte) for byte in cls.adult_tunics) + '};\n') + '''
void reset_gear(void) {
 memset(&gameplay,0,sizeof gameplay);memset(&save_state,0,sizeof save_state);
 stick=ocarina=gear_ready=false;sword_out=true;gear_active=drawn_gear=0;
 link_age_model=0;filter=draw_filter=filter_calls=0;save_state.link_age=1;
 invalidate_equipped();
}
void choose_age(int adult) {
 link_age_model_t *model=(link_age_model_t *)adult_storage;
 memset(model,0,sizeof adult_storage);model->vertices=ADULT_LINK_VERTEX_COUNT;
 memcpy(model->gear,adult_groups,sizeof adult_groups);
 memcpy((unsigned char *)(model+1)+((model->vertices+3u)&~3u)+model->vertices*sizeof(link_vec3_t),
        adult_tunics,sizeof adult_tunics);
 link_age_model=adult ? model : 0;save_state.link_age=adult ? 0 : 1;invalidate_equipped();
}
void draw_sword(int on) {sword_out=on;}
void source_gear(unsigned sword,unsigned shield,int ready) {
 save_state.equip_sword=sword;save_state.equip_shield=shield;gear_ready=ready;
 invalidate_equipped();
}
unsigned selected_groups(void) {return drawn_gear;}
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
 for(i=0;i<1024;++i) {
  polygons[i].norm[0]=i;
  attributes[i]=(ATTR){0,0,i,0,i+1000,0,2};
 }
 gameplay.equipped=mask; submissions=0; kokiri_link_draw(0,0,0,0);
}
unsigned int calls(void) { return submissions; }
unsigned int count(void) { return drawn.nbPolygon; }
unsigned int polygon(unsigned int i) { return drawn.pltbl[i].norm[0]; }
unsigned int attribute(unsigned int i) { return drawn.attbl[i].colno; }
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
        # z_player_lib sTunicColors: Zora {0,60,100}, Goron {100,20,0},
        # converted to RGB555 by the renderer.
        for tunic,colour in ((1,(7<<5)|(12<<10)),(2,12|(2<<5)),(0,0)):
            self.lib.choose_tunic(tunic)
            self.lib.select_gear(3)
            self.assertEqual(self.actual(),baseline)
            for i,p in enumerate(baseline):
                tinted=tunic and self.adult_tunics[p//8]&(1<<(p%8))
                self.assertEqual(self.lib.attribute(i),(0x8000|colour) if tinted else p+1000)

    def test_sheathed_equipment_and_draw_transition_for_both_ages(self):
        for adult in (False,True):
            self.lib.choose_age(adult)
            for mask in (0,1,3,2):
                self.lib.draw_sword(0)
                self.lib.select_gear(mask)
                groups=['BODY','LEFT_EMPTY',
                        'RIGHT_SHIELD' if mask==2 else 'RIGHT_EMPTY']
                if mask&1: groups.append('SHEATH_SHIELD' if mask&2 else 'SHEATH_SWORD')
                self.assertEqual(self.actual(),self.expected(groups,adult))
                self.assertEqual(self.lib.saved_gear(),mask)
                self.lib.draw_sword(1)
                self.lib.select_gear(mask)
                if mask&1:
                    self.assertNotEqual(self.actual(),self.expected(groups,adult))

    def test_adult_source_sword_and_shield_select_hand_and_back_groups(self):
        self.lib.choose_age(1)
        # Enum values come from the real selector declarations above.
        for sword,left in ((2,0),(3,4)):
            for shield,right,back in ((2,1,3),(3,5,6)):
                self.lib.source_gear(sword,shield,1)
                self.lib.draw_sword(1)
                self.lib.select_gear(3)
                self.assertEqual(self.lib.selected_groups(),(1<<left)|(1<<right))
                self.assertEqual(self.actual(),self.expected(['BODY','SHEATH'],True))
                self.assertEqual(self.lib.saved_gear(),3)
                self.lib.draw_sword(0)
                self.lib.select_gear(3)
                self.assertEqual(self.lib.selected_groups(),1<<back)
                self.assertEqual(self.actual(),self.expected(['BODY','LEFT_EMPTY','RIGHT_EMPTY'],True))
                self.lib.play_ocarina(1)
                self.lib.draw_sword(1)
                self.lib.select_gear(3)
                self.assertEqual(self.lib.selected_groups(),1<<back)
                self.assertEqual(self.actual(),self.expected(['BODY','LEFT_EMPTY','RH_OCARINA'],True))
                self.lib.play_ocarina(0)

    def test_hurt_filter_resets_after_shared_equipment_submission(self):
        for wave,level in ((-65536,1),(0,8),(65536,16)):
            self.lib.hurt(4,0,wave)
            self.lib.select_gear(3)
            self.assertEqual(self.lib.flash(),level)
            self.assertEqual(self.lib.filter_restored(),1)
        self.lib.hurt(4,1,65536)
        self.lib.select_gear(3)
        self.assertEqual(self.lib.flash(),0)
