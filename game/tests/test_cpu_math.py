"""Exercise the actual heading conversion without an emulator."""
from pathlib import Path
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]


class CpuMath(unittest.TestCase):
    run_c = graphics.GraphicsBackend.run_c

    def test_heading_conversion_bounds_and_direction(self):
        self.run_c(r'''
#include <stdint.h>
#include <limits.h>
#include <assert.h>
static int32_t passed_x, passed_z;
static int slAtan(int32_t z, int32_t x) {
    passed_z=z; passed_x=x; return 0xabcdef;
}
''' + graphics.function(ROOT / 'src/demo_camera.c',
                       'uint16_t kokiri_camera_facing') + r'''
static void check(int32_t x, int32_t z) {
    assert(kokiri_camera_facing(x,z)==0xcdef);
    if (x>=-32768 && x<=32767 && z>=-32768 && z<=32767) {
        /* Exact equivalence to the old double-based Q16 conversion. */
        assert(passed_x==(int32_t)(65536.0*x));
        assert(passed_z==(int32_t)(65536.0*z));
    }
    assert(passed_x%65536==0 && passed_z%65536==0);
    if (!x && !z) { assert(!passed_x && !passed_z); return; }
    long double dot=(long double)x*passed_x+(long double)z*passed_z;
    long double cross=(long double)x*passed_z-(long double)z*passed_x;
    if (cross<0) cross=-cross;
    /* Same direction within <1 binang; includes every quadrant and INT_MIN.
     * A wrap or independent component clamp fails this bound. */
    assert(dot>0 && cross<dot/16384);
    assert(!passed_x || ((passed_x<0)==(x<0)));
    assert(!passed_z || ((passed_z<0)==(z<0)));
}
int main(void) {
    const int32_t edges[]={INT32_MIN,INT32_MIN+1,-65537,-65536,-32769,
        -32768,-32767,-256,-1,0,1,256,32767,32768,65535,65536,INT32_MAX};
    unsigned i,j; uint32_t seed=12345;
    for(i=0;i<sizeof(edges)/sizeof(*edges);++i)
        for(j=0;j<sizeof(edges)/sizeof(*edges);++j) check(edges[i],edges[j]);
    for(int32_t v=-32768;v<=32767;++v) {
        check(v,0); check(0,v); check(v,32767); check(-32768,v);
    }
    for(i=0;i<100000;++i) {
        seed=seed*1664525u+1013904223u; int32_t x=(int32_t)seed;
        seed=seed*1664525u+1013904223u; check(x,(int32_t)seed);
    }
    return 0;
}
''')

if __name__ == '__main__':
    unittest.main()
