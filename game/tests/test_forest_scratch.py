"""Fast prep scratch must not overwrite persistent gathered-index restoration."""
import re
import unittest

import test_graphics_backend as graphics

ROOT = graphics.ROOT


class ForestScratch(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_prep_draw_lifetimes_across_small_large_and_empty_views(self):
        source = (ROOT / 'src/kokiri_sgl.c').read_text()
        storage = re.search(r'static union \{.*?\} forest_work;.*?forest_prep_fits\[.*?;',
                            source, re.S).group()
        self.run_c(r'''
#include <stdint.h>
#include <assert.h>
#include <string.h>
typedef int32_t POINT[3];
typedef struct { unsigned short Vertices[4]; } POLYGON;
#define FOREST_DRAW_POINTS 512
#define KOKIRI_VERTEX_COUNT 2047
''' + storage + '\n#include "' + (ROOT / 'src/forest_vertex_pack.h').as_posix() + '"\n' + r'''
static POINT source[2047], spill[2047];
static POLYGON polygons[600], original[600];
static unsigned short map[2047], inverse[2047];
int main(void) {
    static const unsigned views[] = {600, 60, 60, 0, 400, 30, 600};
    assert(sizeof(forest_work) == sizeof(POINT) * 512);
    for (unsigned i=0; i<2047; ++i)
        for (unsigned axis=0; axis<3; ++axis) source[i][axis]=i*100+axis;
    for (unsigned i=0; i<600; ++i)
        for (unsigned k=0; k<4; ++k) original[i].Vertices[k]=(i*3+k)%2047;
    memcpy(polygons, original, sizeof(polygons));
    POINT *selected=0;
    unsigned previous=0;
    for (unsigned frame=0; frame<sizeof(views)/sizeof(views[0]); ++frame) {
        /* Previous draw has finished; only the Low-RAM inverse survives. */
        forest_restore_vertices(polygons, previous, inverse);
        assert(!memcmp(polygons, original, sizeof(polygons)));
        for (unsigned i=0; i<2047; ++i) {
            prep_depth[i]=(short)((int)i-1024);
            prep_side[i]=i&3;
        }
        for (unsigned i=0; i<2047; ++i)
            assert(prep_depth[i]==(int)i-1024 && prep_side[i]==(i&3));
        unsigned visible=views[frame];
        unsigned count=forest_gather_vertices_dual(source,2047,polygons,visible,
            forest_draw_points,512,spill,2047,&selected,map,inverse);
        assert(count <= 2047 && (count <= 512 ? selected==forest_draw_points : selected==spill));
        for (unsigned i=0; i<visible; ++i)
            for (unsigned k=0; k<4; ++k)
                assert(!memcmp(selected[polygons[i].Vertices[k]],
                    source[original[i].Vertices[k]],sizeof(POINT)));
        previous=visible;
    }
    forest_restore_vertices(polygons,previous,inverse);
    assert(!memcmp(polygons,original,sizeof(polygons)));
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
