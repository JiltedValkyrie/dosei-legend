"""Scene side-frustum cull (kokiri_sgl.c side_out) never drops a visible polygon.

The production function is extracted and run on random cameras (yaw, pitch
up to +-33 degrees, three screen distances) and random quads; every quad it
culls is sampled densely and projected with the real pitched camera in
floating point. A visible sample is a failure.
"""
from pathlib import Path
import unittest

import test_graphics_backend as backend

ROOT = Path(__file__).resolve().parents[1]


class SideCull(unittest.TestCase):
    run_c = backend.GraphicsBackend.run_c

    def test_culled_quads_are_never_visible(self):
        side_out = backend.function(ROOT / 'src/kokiri_sgl.c', 'static int side_out(')
        side_out = backend.function(ROOT / 'src/kokiri_sgl.c', 'static short side_mask(') + side_out
        self.run_c(r'''
#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <stdlib.h>
typedef int32_t POINT[3];
static POINT points[4];
static struct { POINT *pntbl; } kokiri_pdata = { points };
static struct { int32_t x, y, z; } recomp_camera;
static short prep_depth[4];
static unsigned char prep_side[4];
static int side_cull_dist, side_sin_q8, side_cos_q8;
''' + side_out + r'''
static unsigned rng = 12345u;
static int rnd(int lo, int hi) { rng = rng * 1103515245u + 12345u; return lo + (int)((rng >> 8) % (unsigned)(hi - lo + 1)); }
int main(void) {
    const double tau = 6.283185307179586;
    long culled = 0, total = 0;
    int trial, q, k, u, v, sign;
    for (trial = 0; trial < 3000; ++trial) {
        int yaw = rnd(0, 65535), pitch = rnd(-6000, 6000), dist = (int[]){200, 240, 320}[rnd(0, 2)];
        int32_t s = (int32_t)(sin(yaw / 65536.0 * tau) * 65536), c = (int32_t)(cos(yaw / 65536.0 * tau) * 65536);
        int32_t ps = (int32_t)(sin(pitch / 65536.0 * tau) * 65536), pc = (int32_t)(cos(pitch / 65536.0 * tau) * 65536);
        double pr = pitch / 65536.0 * tau;
        recomp_camera.x = rnd(-2000, 2000); recomp_camera.y = rnd(-200, 400); recomp_camera.z = rnd(-2000, 2000);
        side_sin_q8 = ((ps < 0 ? -ps : ps) + 255) >> 8;
        side_cos_q8 = pc >> 8;
        side_cull_dist = dist;
        for (q = 0; q < 20; ++q) {
            int bx = recomp_camera.x + rnd(-1500, 1500), by = recomp_camera.y + rnd(-900, 1200), bz = recomp_camera.z + rnd(-1500, 1500);
            static const unsigned short corner[4] = {0, 1, 2, 3};
            int visible = 0;
            for (k = 0; k < 4; ++k) {
                int x = bx + rnd(-150, 150), y = by + rnd(-150, 150), z = bz + rnd(-150, 150);
                int dx = x - recomp_camera.x, dz = z - recomp_camera.z;
                points[k][0] = x * 65536; points[k][1] = -y * 65536; points[k][2] = z * 65536;
                prep_depth[k] = (short)(((int64_t)dx * s + (int64_t)dz * c) >> 16);
                prep_side[k] = side_mask(prep_depth[k], y-recomp_camera.y,
                    (short)(((int64_t)dx * c - (int64_t)dz * s) >> 16));
            }
            ++total;
            if (!side_out(corner, prep_side)) continue;
            ++culled;
            for (u = 0; u <= 8; ++u) for (v = 0; v <= 8; ++v) {
                double a[3], b[3], pnt[3], dx, dy, dz, zf, xr, zt;
                for (k = 0; k < 3; ++k) {
                    double c0 = points[0][k] / 65536.0, c1 = points[1][k] / 65536.0;
                    double c2 = points[2][k] / 65536.0, c3 = points[3][k] / 65536.0;
                    if (k == 1) { c0 = -c0; c1 = -c1; c2 = -c2; c3 = -c3; }
                    a[k] = c0 + (c1 - c0) * u / 8.0;
                    b[k] = c3 + (c2 - c3) * u / 8.0;
                    pnt[k] = a[k] + (b[k] - a[k]) * v / 8.0;
                }
                dx = pnt[0] - recomp_camera.x; dy = pnt[1] - recomp_camera.y; dz = pnt[2] - recomp_camera.z;
                zf = (dx * s + dz * c) / 65536.0;
                xr = (dx * c - dz * s) / 65536.0;
                for (sign = -1; sign <= 1; sign += 2) {
                    zt = zf * cos(pr) + sign * dy * sin(pr);
                    if (zt > 1.0 && fabs(xr) * dist <= zt * 160.0 + 1.0) visible = 1;
                }
            }
            assert(!visible);
        }
    }
    assert(culled > total / 2);   /* the cull does real work */
    return 0;
}
''')


if __name__ == '__main__':
    unittest.main()
