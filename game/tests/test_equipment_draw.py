"""Run the real equipment selector with indexed polygon/attribute records."""
import ctypes
import os
from pathlib import Path
import re
import subprocess
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
#include "gameplay.h"
#include "link_equipment.h"
typedef unsigned int POLYGON;
typedef unsigned int ATTR;
typedef struct { void *pntbl; unsigned int nbPoint; POLYGON *pltbl; unsigned int nbPolygon; ATTR *attbl; } PDATA;
static POLYGON polygons[1024]; static ATTR attributes[1024];
static PDATA link_pdata = {0,323,polygons,0,attributes};
gameplay_t gameplay;
static PDATA drawn;
static unsigned int submissions;
static void submit(PDATA *p, unsigned int bit) { drawn=*p; ++submissions; }
static void jo_3d_push_matrix(void) {}
static void jo_3d_pop_matrix(void) {}
static void jo_3d_translate_matrix(int x,int y,int z) {}
static void jo_3d_rotate_matrix_y(int y) {}
'''
        wrapper = '''
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
        cls.defines={m[0]:int(m[1]) for m in re.findall(r'#define (LINK_\w+) (\d+)',
                     (GEN/'link_equipment.h').read_text())}

    @classmethod
    def tearDownClass(cls): cls.temp.cleanup()

    def test_all_equipment_combinations_and_reselection(self):
        for mask in (0,1,3,2,0,3,3):
            self.lib.select_gear(mask)
            self.assertEqual(self.lib.calls(),1, 'must transform shared points only once')
            expected=[]
            groups=['BODY','LEFT_SWORD' if mask&1 else 'LEFT_EMPTY',
                    'RIGHT_SHIELD' if mask&2 else 'RIGHT_EMPTY']
            if mask&1: groups.append('SHEATH')
            for group in groups:
                first=self.defines['LINK_'+group+'_FIRST']
                expected.extend(range(first,first+self.defines['LINK_'+group+'_COUNT']))
            actual=[self.lib.polygon(i) for i in range(self.lib.count())]
            self.assertEqual(sorted(actual),sorted(expected))
            self.assertEqual(len(actual),len(set(actual)))
            self.assertLessEqual(len(actual),self.defines['LINK_VISIBLE_POLYGONS'])
            for i,p in enumerate(actual): self.assertEqual(self.lib.attribute(i),p+1000)
