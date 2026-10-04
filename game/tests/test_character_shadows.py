"""Grounded mesh shadow behavior; no emulator required."""
from pathlib import Path
import unittest
import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]

class CharacterShadows(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_ground_projection_culling_height_and_budget(self):
        self.run_c(r'''
#include <assert.h>
typedef int POINT[3];
typedef struct { int normal[3],vertices[4]; } POLYGON;
typedef int ATTR;
typedef struct { POINT *points;int count;POLYGON *faces;int polygons;ATTR *attrs; } PDATA;
typedef struct { int x,y,z; } bg_vec_t;
#define ATTRIBUTE(...) 0
#define BG_Y_MIN -32000
static int visible=1,ground=20,queries,draws,pushes,pops,ty,scale;
static int npc_sprite_in_view(int x,int y,int z,unsigned r) { return visible; }
static int bg_floor(const bg_vec_t *p,int ignore,void *hit) { ++queries;return ground; }
static void slPushMatrix(void) { ++pushes; }
static void slPopMatrix(void) { ++pops; }
static void slTranslate(int x,int y,int z) { ty=y; }
static void slScale(int x,int y,int z) { scale=x/65536;assert(x==z); }
static void submit(PDATA *p,unsigned bit) { ++draws;assert(p->count==12 && p->polygons==5); }
''' + graphics.function(ROOT/'src/kokiri_sgl.c',
            'void __attribute__((optimize("Os"))) kokiri_actor_shadow(') + r'''
int main(void) {
    kokiri_actor_shadow(0,20,0,18);
    assert(draws==1 && ty==-22*65536 && scale==18);
    kokiri_actor_shadow(0,276,0,18);
    assert(draws==2 && ty==-22*65536 && scale==13);
    kokiri_actor_shadow(0,20,0,200);
    assert(draws==3 && scale==64);
    ground=BG_Y_MIN;kokiri_actor_shadow(0,20,0,18);assert(draws==3);
    ground=40;kokiri_actor_shadow(0,20,0,18);assert(draws==3);
    ground=20;kokiri_actor_shadow(0,533,0,18);assert(draws==3);
    visible=0;queries=0;kokiri_actor_shadow(0,20,0,18);assert(!queries);
    visible=1;kokiri_actor_shadow(0,20,0,0);assert(!queries);
    assert(pushes==3 && pops==3);
    return 0;
}
''')

if __name__ == '__main__':
    unittest.main()
