"""Exact Player affine transforms, origin reads and importer call ownership."""
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_graphics_backend import function
from test_fx32 import ROOT, host_flags, importer
from test_player_fast_angles import body


PROGRAM = r'''
#include "sys_matrix.h"
#include "z_lib.h"
#include "player_anchor_matrix.h"
extern "C" int printf(const char*, ...);
static MtxF* sCurrentMatrix;
static unsigned fallbacks, seed=0x25371639u;
#define CHECK(c) do {if(!(c)){printf("line %d: %s\n",__LINE__,#c);return 1;}}while(0)
static unsigned random_word(){seed=seed*1664525u+1013904223u;return seed;}
static void identity(MtxF* m) {
    for(int c=0;c<4;++c)for(int r=0;r<4;++r)m->mf[c][r]=Fx::raw(c==r?65536:0);
}
static int equal(const MtxF& a,const MtxF& b) {
    for(int c=0;c<4;++c)for(int r=0;r<4;++r)if(a.mf[c][r].v!=b.mf[c][r].v)return 0;
    return 1;
}
'''


PROBES = r'''
/* Define after production callers so only their real forward declaration
 * makes them compile; an early fixture definition must not hide a missing
 * declaration in the target translation unit. */
MtxF* Matrix_GetCurrent() {return sCurrentMatrix;}
static int transforms() {
    unsigned fast=0,slow=0;
    for(unsigned i=0;i<250000;++i) {
        MtxF initial,expected,actual;identity(&initial);
        for(int c=0;c<3;++c)for(int r=0;r<3;++r)
            initial.mf[c][r]=Fx::raw((int)(random_word()%131073u)-65536);
        for(int r=0;r<3;++r)initial.mf[3][r]=Fx::raw((int)random_word());
        Vec3f p={Fx::raw((int)random_word()),Fx::raw((int)random_word()),Fx::raw((int)random_word())};
        Vec3s rot={(s16)random_word(),(s16)random_word(),(s16)random_word()};
        if(i%3==0)rot.x=0;if(i%5==0)rot.y=0;if(i%7==0)rot.z=0;
        /* Exact boundaries and all unsupported input categories. */
        if(i%11==0)initial.mf[i%3][(i/3)%3]=Fx::raw(65537);
        if(i%13==0)initial.mf[0][3]=Fx::raw(1);
        if(i%17==0)initial.mf[3][3]=Fx::raw(65535);
        if(i%19==0)p.x=Fx::raw((int)0x80000000u);
        if(i%23==0)initial.mf[2][2]=Fx::raw(0x7fffffff);
        expected=actual=initial;
        sCurrentMatrix=&expected;Reference_Transform(&p,&rot);
        fallbacks=0;sCurrentMatrix=&actual;OotCore_PlayerTranslateRotateZYX(&p,&rot);
        CHECK(equal(expected,actual));
        if(fallbacks)++slow;else ++fast;
    }
    CHECK(fast>100000 && slow>10000);
    printf("Player transforms: 250000 exact matrices, %u fast/%u fallback\n",fast,slow);
    return 0;
}
static int chains() {
    unsigned fast=0;
    for(unsigned i=0;i<20000;++i) {
        MtxF expected,actual;identity(&expected);
        for(int c=0;c<3;++c)expected.mf[c][c]=Fx::raw(i%2?655:-655);
        for(int r=0;r<3;++r)expected.mf[3][r]=Fx::raw((int)random_word());
        actual=expected;
        for(unsigned limb=0;limb<22;++limb) {
            Vec3f p={Fx((int)(random_word()%12001)-6000),Fx((int)(random_word()%12001)-6000),
                     Fx((int)(random_word()%12001)-6000)};
            Vec3s rot={(s16)random_word(),(s16)random_word(),(s16)random_word()};
            sCurrentMatrix=&expected;Reference_Transform(&p,&rot);
            fallbacks=0;sCurrentMatrix=&actual;OotCore_PlayerTranslateRotateZYX(&p,&rot);
            CHECK(equal(expected,actual));CHECK(!fallbacks);++fast;
        }
    }
    printf("Player transform chains: %u consecutive limb matrices exact\n",fast);
    return 0;
}
static int origins() {
    Vec3f zero={Fx(0),Fx(0),Fx(0)};
    for(unsigned i=0;i<100000;++i) {
        MtxF m;Vec3f expected,actual;
        for(int c=0;c<4;++c)for(int r=0;r<4;++r)m.mf[c][r]=Fx::raw((int)random_word());
        if(i%7==0)m.mf[3][i%3]=Fx::raw((int)0x80000000u);
        sCurrentMatrix=&m;Matrix_MultVec3f(&zero,&expected);OotCore_PlayerMatrixOrigin(&actual);
        CHECK(expected.x.v==actual.x.v && expected.y.v==actual.y.v && expected.z.v==actual.z.v);
    }
    printf("Player origins: 100000 exact zero-vector transforms including raw boundaries\n");
    return 0;
}
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    return argv[1][0]=='t'?transforms():(argv[1][0]=='c'?chains():origins());
}
'''


class PlayerAnchorMatrix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        src = ROOT / 'oot-core/src/oot_core_draw.cpp'
        matrix = ROOT / 'build/oot-core/decomp/src/code/sys_matrix.cpp'
        zlib = ROOT / 'build/oot-core/decomp/src/code/z_lib.cpp'
        source = PROGRAM
        source += src.read_text().split('#include "player_anchor_matrix.h"', 1)[1].split(
            '#if !OOT_CORE_HWFLOAT', 1)[0]
        original = function(matrix, 'void Matrix_TranslateRotateZYX(')
        source += original.replace('Matrix_TranslateRotateZYX(', 'Reference_Transform(') + '\n'
        source += original.replace('{', '{ ++fallbacks;', 1) + '\n'
        source += function(matrix, 'void Matrix_MultVec3f(') + '\n'
        for marker in ('f32 Math_SinS(', 'f32 Math_CosS('):
            source += function(zlib, marker) + '\n'
        for marker in ('static inline FX_INL fx_raw PlayerAnchor_Mul(',
                       'static bool PlayerAnchor_Bounded(',
                       'void OotCore_PlayerTranslateRotateZYX(',
                       'void OotCore_PlayerMatrixOrigin('):
            source += function(src, marker) + '\n'
        source += PROBES
        path = folder / 'matrix.cpp'
        path.write_text(source)
        cls.exe = folder / 'matrix'
        compiler, cls.env = compiler_env()
        result = subprocess.run(
            [compiler, *host_flags(), '-fsanitize=undefined', '-fno-sanitize-recover=undefined',
             '-ffunction-sections', '-fdata-sections',
             str(path), str(ROOT / 'build/oot-core/decomp/src/libultra/gu/sins.cpp'),
             str(ROOT / 'build/oot-core/decomp/src/libultra/gu/coss.cpp'),
             str(ROOT / 'oot-core/src/oot_math.cpp'), '-Wl,--gc-sections', '-o', str(cls.exe)],
            env=cls.env, text=True, capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    def probe(self, mode):
        result = subprocess.run([str(self.exe), mode], env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_affine_bounds_and_source_fallback_exact(self):
        self.probe('transforms')

    def test_full_limb_chains_preserve_source_rounding(self):
        self.probe('chains')

    def test_zero_vector_origin_exact(self):
        self.probe('origins')

    def test_importer_only_changes_anchor_math_and_rejects_source_drift(self):
        rel = 'src/code/z_player_lib.c'
        original = (importer.OOT_DEFAULT / rel).read_text()
        changed = importer.fix_player_anchor_matrices(rel, original, {})
        for name, transforms, origins in (('func_8008F87C', 2, 2), ('Player_PostLimbDrawGameplay', 1, 2)):
            span = body(changed, name)
            self.assertEqual(span.count('OotCore_PlayerTranslateRotateZYX('), transforms)
            self.assertEqual(span.count('OotCore_PlayerMatrixOrigin('), origins)
        restored = changed.replace('#include "player_anchor_matrix.h"\n', '', 1)
        restored = restored.replace('OotCore_PlayerTranslateRotateZYX(', 'Matrix_TranslateRotateZYX(')
        restored = restored.replace('OotCore_PlayerMatrixOrigin(', 'Matrix_MultVec3f(&sZeroVec, ')
        self.assertEqual(restored, original)
        with self.assertRaisesRegex(ValueError, 'Player anchor matrix call sites changed'):
            importer.fix_player_anchor_matrices(rel, original.replace('Matrix_TranslateRotateZYX(pos, rot);', ''), {})
