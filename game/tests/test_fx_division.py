"""Exact scaled division at full 32-bit ranges, against host-wide arithmetic."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_fx32 import ROOT, host_flags


PROGRAM = r'''
#include "ultra64.h"
extern "C" int printf(const char*, ...);

static unsigned seed = 0x8ab2c451u;
static unsigned random_word() {
    seed = seed * 1664525u + 1013904223u;
    return seed;
}

/* Wide arithmetic exists only in the host oracle, never runtime code. */
static unsigned reference(unsigned n, int shift, unsigned d) {
    if (d > 0x7fffffffu) d = 0x7fffffffu;
    unsigned long long q = ((unsigned long long)n << shift) / d;
    return q > 0x7fffffffu ? 0x80000000u : (unsigned)q;
}

static int check(unsigned n, int shift, unsigned d) {
    unsigned expected = reference(n, shift, d);
    unsigned got = fx_div_u(n, shift, d);
    if (got > 0x7fffffffu) got = 0x80000000u;
    if (got != expected) {
        printf("scaled %u << %d / %u: %u expected %u\n", n, shift, d, got, expected);
        return 1;
    }
    return 0;
}

static int check_signed(int a, int b) {
    int got = OotFx_Div(a, b);
    int expected;
    if (!b) expected = a < 0 ? -FX_MAX : FX_MAX;
    else {
        unsigned q = reference(fx_abs_u(a), 16, fx_abs_u(b));
        if (q > 0x7fffffffu) q = 0x7fffffffu;
        expected = (a < 0) != (b < 0) ? -(int)q : (int)q;
    }
    if (got != expected) {
        printf("signed %d / %d: %d expected %d\n", a, b, got, expected);
        return 1;
    }
    return 0;
}

int main(int argc, char**) {
    static const unsigned edge[] = {
        0, 1, 2, 3, 0xff, 0x100, 0x101, 0x7fff, 0x8000,
        0xffff, 0x10000, 0x10001, 0x7ffff, 0x80000, 0xfffff,
        0x100000, 0xffffff, 0x1000000, 0x3fffffff, 0x40000000,
        0x7ffffffe, 0x7fffffff, 0x80000000, 0xfffffffe, 0xffffffff
    };
    if (argc == 1) {
        for (unsigned a : edge) for (unsigned b : edge) if (b) {
            for (int shift = 0; shift <= 32; ++shift)
                if (check(a, shift, b)) return 1;
        }
        for (unsigned i = 0; i < 400000; ++i) {
            unsigned a = random_word(), b = random_word() | 1u;
            if (check(a, i % 33, b)) return 1;
        }
        /* Exact quotient and saturation boundaries around each power of two. */
        for (int bit = 0; bit < 31; ++bit) {
            unsigned d = 1u << bit;
            for (int offset = -1; offset <= 1; ++offset) {
                unsigned divisor = d + offset;
                if (!divisor) continue;
                for (unsigned a : edge) {
                    if (check(a, 16, divisor) || check(a, 32, divisor)) return 1;
                }
            }
        }
    } else {
        for (unsigned a : edge) for (unsigned b : edge)
            if (check_signed((int)a, (int)b)) return 1;
        for (unsigned i = 0; i < 400000; ++i) {
            int a = (int)random_word(), b = (int)random_word();
            if (check_signed(a, b)) return 1;
            unsigned mag = random_word(), divisor = random_word() | 1u;
            /* IntDiv receives a signed Fx denominator, unlike fx_div_u. */
            int denominator = (int)divisor;
            unsigned expected = reference(mag, 32, fx_abs_u(denominator));
            if (expected > 0x7fffffffu) expected = 0x7fffffffu;
            bool negative = (i & 1u) != (denominator < 0);
            int got = OotFx_IntDiv(mag, i & 1u, denominator);
            if (got != (negative ? -(int)expected : (int)expected)) return 1;
        }
    }
    return 0;
}
'''


class FxDivision(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        path = Path(cls.folder.name)
        source = path / 'division.cpp'
        source.write_text(PROGRAM)
        cls.exe = path / 'division'
        compiler, cls.env = compiler_env()
        result = subprocess.run(
            [compiler, *host_flags(), '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
             str(source), str(ROOT / 'oot-core/src/oot_math.cpp'),
             str(ROOT / 'oot-core/src/oot_rand.cpp'), '-o', str(cls.exe)],
            env=cls.env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def run_probe(self, *args):
        result = subprocess.run([str(self.exe), *args], env=self.env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_scaled_unsigned_full_range(self):
        self.run_probe()

    def test_runtime_signed_and_integer_division(self):
        self.run_probe('signed')


if __name__ == '__main__':
    unittest.main()
