"""Wave 0 Fx32 range checks: attention ranges, cross products, wide audit."""
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import oot_core_import as importer  # noqa: E402
from test_core_bgcheck import compiler_env  # noqa: E402

DECOMP = ROOT / 'build/oot-core/decomp'


def attention_ranges():
    text = (importer.OOT_DEFAULT / 'src/code/z_actor.c').read_text(encoding='utf-8')
    return [int(r) for r in re.findall(r'^\s*ATTENTION_RANGES\((\d+),', text, re.M)]


def host_flags():
    oot = importer.OOT_DEFAULT
    definitions = ('PLATFORM_N64=1 PLATFORM_GC=0 PLATFORM_IQUE=0 OOT_VERSION=NTSC_1_2 '
                   'OOT_REVISION=2 OOT_REGION=REGION_US LIBULTRA_VERSION=LIBULTRA_VERSION_I '
                   'LIBULTRA_PATCH=1 DEBUG_FEATURES=0 NDEBUG F3DEX_GBI_2 NON_MATCHING AVOID_UB '
                   '_LANGUAGE_C _MIPS_SZLONG=32 _MIPS_SZINT=32 _MIPS_SZPTR=32').split()
    includes = [ROOT / 'oot-core/shim', ROOT / 'oot-core/include', DECOMP / 'include',
                DECOMP / 'include/libc', DECOMP / 'src', DECOMP, oot / 'extracted/ntsc-1.2', oot]
    return (['-std=gnu++17', '-O1', '-fno-exceptions', '-fno-rtti', '-fpermissive',
             '-funsigned-char', '-w', '-include', 'oot_prelude.h', '-nostdinc']
            + ['-D' + d for d in definitions] + ['-I' + str(i) for i in includes])


PROGRAM = r'''
#include "ultra64.h"
extern "C" int printf(const char*, ...);
typedef decltype(0.0) hw_double; /* `double` is macro-renamed to Fx */
static int sFail;
#define CHECK(c, ...) do { if (!(c)) { printf(__VA_ARGS__); printf("\n"); sFail++; } } while (0)

static hw_double D(Fx f) { return (hw_double)(decltype(0.0f))f; }

int main() {
    static const int ranges[] = { RANGES };
    for (unsigned i = 0; i < sizeof(ranges) / sizeof(ranges[0]); i++) {
        int r = ranges[i];
        FxSq table = OOT_SQ(r);          /* sAttentionRanges: { SQ(range), ... } */
        FxSq inside = OOT_SQ(Fx(r - 1)) + OOT_SQ(Fx(0));
        FxSq outside = OOT_SQ(Fx(r + 1)) + OOT_SQ(Fx(0));
        CHECK(inside < table, "range %d: r-1 not inside", r);
        CHECK(!(outside < table), "range %d: r+1 not outside", r);
        CHECK(!(OOT_SQ(Fx(r)) < table) && !(OOT_SQ(Fx(r)) > table), "range %d: r != r", r);
        CHECK(OOT_SQ(Fx(r - 1)) < table && OOT_SQ(Fx(r + 1)) > table, "range %d: pending squares", r);
        Fx root = sqrtf(table);
        CHECK(root.v == Fx(r).v, "range %d: root %f", r, D(root));
    }
    /* Integer squares past one Fx root (>= 2^30) still order correctly. */
    FxSq huge = 0x7FFFFFFF;
    CHECK(OOT_SQ(Fx(30000)) < huge && !(huge < OOT_SQ(Fx(30000))), "2^31 integer square");
    CHECK(!(FxSq(-5) > FxSq(0)) && !(FxSq(0) > FxSq(-5)), "negative integer square is empty");

    /* Math3D_Vec3f_Cross example: y must be -90000 (scaled), never 0. */
    Fx x, y, z;
    OotFx_Cross3(Fx(300), Fx(0), Fx(300), Fx(300), Fx(0), Fx(600), &x, &y, &z);
    CHECK(x.v == 0 && z.v == 0 && y.v < 0, "cross direction %f %f %f", D(x), D(y), D(z));
    Fx len = sqrtf(OOT_SQ(x) + OOT_SQ(y) + OOT_SQ(z));
    Fx ny = y / len;
    CHECK(ny.v <= -65530, "normalized y %f", D(ny));
    /* Small (unit) inputs are exact, unscaled. */
    OotFx_Cross3(Fx(1), Fx(0), Fx(0), Fx(0), Fx(1), Fx(0), &x, &y, &z);
    CHECK(x.v == 0 && y.v == 0 && z.v == 65536, "unit cross %f %f %f", D(x), D(y), D(z));
    /* Dynamic poly normal from three wide vertices (Math3D_SurfaceNorm path). */
    OotFx_Cross3(Fx(4000), Fx(10), Fx(-3000), Fx(-2500), Fx(20), Fx(5000), &x, &y, &z);
    len = sqrtf(OOT_SQ(x) + OOT_SQ(y) + OOT_SQ(z));
    hw_double fx = 10.0 * 5000 - (-3000.0) * 20, fy = -3000.0 * -2500 - 4000.0 * 5000,
           fz = 4000.0 * 20 - 10.0 * -2500;
    hw_double fl = __builtin_sqrt(fx * fx + fy * fy + fz * fz);
    CHECK(__builtin_fabs(D(x / len) - fx / fl) < 2e-3 && __builtin_fabs(D(y / len) - fy / fl) < 2e-3 &&
          __builtin_fabs(D(z / len) - fz / fl) < 2e-3,
          "wide normal %f %f %f vs %f %f %f", D(x / len), D(y / len), D(z / len), fx / fl, fy / fl, fz / fl);
    printf("fx32 checks failed: %d\n", sFail);
    return sFail != 0;
}
'''


@unittest.skipUnless((DECOMP / 'include/ultra64.h').exists(), 'oot-core import required')
class Fx32(unittest.TestCase):
    def test_attention_ranges_and_cross_products(self):
        ranges = attention_ranges()
        self.assertGreaterEqual(len(ranges), 10)
        self.assertIn(350, ranges)
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            src = p / 'fx32.cpp'
            src.write_text(PROGRAM.replace('RANGES', ', '.join(map(str, ranges))))
            exe = p / 'fx32.exe'
            subprocess.run([compiler, *host_flags(), str(src), str(ROOT / 'oot-core/src/oot_math.cpp'),
                            str(ROOT / 'oot-core/src/oot_rand.cpp'), '-o', str(exe)],
                           check=True, env=env, capture_output=True)
            run = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_wide_audit_controls(self):
        run = subprocess.run([sys.executable, str(ROOT / 'tools/audit_oot_core_wide.py'), '--self-test'],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout)
        self.assertNotIn('FAIL', run.stdout)


if __name__ == '__main__':
    unittest.main()
