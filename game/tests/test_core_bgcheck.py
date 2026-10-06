"""Source collision equivalence and work reduction at reported Cucco scenes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_graphics_backend as graphics

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import oot_core_import as importer
from asset_names import scene_stem


def compiler_env():
    compiler = Path(graphics.GCC).with_name('g++.exe' if os.name == 'nt' else 'g++')
    env = dict(os.environ)
    env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
    return str(compiler), env


class CoreBgcheck(unittest.TestCase):
    @unittest.skipUnless(importer.OOT_DEFAULT.exists(), 'source tree required')
    def test_cucco_sprite_keeps_clocks_and_rng_without_pose_interpolation(self):
        path = importer.OOT_DEFAULT / 'src/overlays/actors/ovl_En_Niw/z_en_niw.c'
        raw = path.read_text(encoding='utf-8')
        first = raw.index('void func_80AB5BF8(')
        original = raw[first:raw.index('\nvoid EnNiw_SpawnAttackCucco(', first)].strip()
        stats = dict(problems=[], macros=0)
        changed = importer.fix_sprite_actors('src/overlays/actors/ovl_En_Niw/z_en_niw.c',
                                             original, stats)
        self.assertEqual(stats['problems'], [])
        changed = changed.replace('#include "sprite_actor.h"', '')
        source = r'''
#include <assert.h>
#include <string.h>
typedef float f32; typedef short s16; typedef int PlayState;
typedef struct {
    struct { int params; } actor;
    short timer1,timer2,unk_298,unk_29C;
    float unk_26C[10],unk_2E0,unk_2DC,unk_2C4,unk_2C8,unk_2CC,unk_2D0,unk_2D4,unk_2D8;
} EnNiw;
static unsigned rng_calls, pose_calls;
static f32 Rand_ZeroFloat(f32 limit) { rng_calls++; return limit * 0.375f; }
static void Math_ApproachF(f32 *v,f32 target,f32 scale,f32 step) {
    pose_calls++; *v += (target-*v)*scale;
}
''' + original.replace('func_80AB5BF8(', 'source_pose(') + '\n' + changed + r'''
int main(void) {
    unsigned total_pose=0;
    for(int param=0;param<=13;param+=13) for(int mode=0;mode<6;mode++) {
        EnNiw old={0}, sprite={0}; old.actor.params=sprite.actor.params=param;
        for(int frame=0;frame<120;frame++) {
            rng_calls=pose_calls=0;
            source_pose(&old,0,mode);
            unsigned old_rng=rng_calls; total_pose+=pose_calls;
            rng_calls=pose_calls=0;
            func_80AB5BF8(&sprite,0,mode);
            assert(pose_calls==0 && rng_calls==old_rng);
            assert(sprite.timer1==old.timer1 && sprite.timer2==old.timer2);
            assert(sprite.unk_298==old.unk_298 && sprite.unk_29C==old.unk_29C);
            assert(sprite.unk_2E0==0 && sprite.unk_2DC==0 && sprite.unk_2C4==0 && sprite.unk_2D8==0);
            if(old.timer1) old.timer1--; if(sprite.timer1) sprite.timer1--;
            if(old.timer2) old.timer2--; if(sprite.timer2) sprite.timer2--;
        }
    }
    assert(total_pose>1000);
}
'''
        graphics.GraphicsBackend.run_c(self, source)

    def test_integer_bounds_keep_edges_and_negative_fractional_positions(self):
        source = r'''
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#define assert(c) do { if (!(c)) { fprintf(stderr,"line %d: %s\n",__LINE__,#c); exit(1); } } while (0)
''' + '#include "' + (ROOT / 'oot-core/include/fx.h').as_posix() + '"\n' + r'''
typedef int32_t s32; typedef uint32_t u32; typedef Fx f32;
struct Vec3s { int16_t x,y,z; };
struct CollisionPoly { uint16_t flags_vIA,flags_vIB,vIC; };
#define COLPOLY_VTX_INDEX(x) ((x)&8191)
''' + '#include "' + (ROOT / 'oot-core/include/bgcheck_bounds.h').as_posix() + '"\n' + r'''
int main() {
    assert(OotCore_BgInt(Fx(-32768.5)) == -32767); /* Q16.16 saturates */
    assert(OotCore_BgInt(Fx(-1.999)) == -1);
    assert(OotCore_BgInt(Fx(-0.001)) == 0);
    assert(OotCore_BgInt(Fx(32767.999)) == 32767);
    assert(OotCore_BgInt(Fx(40000.5)) == 32767);
    assert(OotCore_BgInt(Fx(-40000.5)) == -32767);
    assert(OotCore_BgInt(Fx(1e11)) == 32767);
    Vec3s v[3] = {{-32768,-100,-200},{32767,100,-200},{0,0,200}};
    CollisionPoly p={0x4000,0x2001,2};
    assert(OotCore_BgPolyNear(&p,v,-32768.9,-100.9,-200.9,0.9,7));
    assert(OotCore_BgPolyNear(&p,v,32767.9,100.9,200.9,0.9,7));
    assert(!OotCore_BgPolyNear(&p,v,0,0,230,20,7));
    assert(!OotCore_BgPolyNear(&p,v,0,130,0,20,7));
    assert(OotCore_BgPolyNear(&p,v,0,130,0,20,5));
    assert(OotCore_BgPolyNear(&p,v,1e6,0,0,1e6,7));
    /* Every exact in-range box point must pass, including fractional edges. */
    for(int x=-15;x<=15;x++) for(int y=-15;y<=15;y++) for(int z=-15;z<=15;z++) {
        Vec3s tri[3]={{-10,-10,-10},{10,10,-10},{-10,-10,10}};
        if(x>=-12 && x<=12 && y>=-12 && y<=12 && z>=-12 && z<=12)
            assert(OotCore_BgPolyNear(&p,tri,Fx(x)+Fx(0.75),Fx(y)-Fx(0.75),z,2.9,7));
    }
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p / 'bounds.cpp').write_text(source)
            subprocess.run([compiler, '-std=c++17', '-O2', str(p / 'bounds.cpp'),
                            '-o', str(p / 'bounds.exe')], check=True, env=env)
            subprocess.run([str(p / 'bounds.exe')], check=True, env=env)

    @unittest.skipUnless(importer.OOT_DEFAULT.exists() and
                         (ROOT / 'build/oot-core/decomp/src/code/z_bgcheck.cpp').exists(),
                         'extracted source and oot-core import required')
    def test_source_contacts_match_with_fewer_wall_square_roots(self):
        compiler, env = compiler_env()
        decomp = ROOT / 'build/oot-core/decomp'
        oot = importer.OOT_DEFAULT
        definitions = ('PLATFORM_N64=1 PLATFORM_GC=0 PLATFORM_IQUE=0 OOT_VERSION=NTSC_1_2 '
                       'OOT_REVISION=2 OOT_REGION=REGION_US LIBULTRA_VERSION=LIBULTRA_VERSION_I '
                       'LIBULTRA_PATCH=1 DEBUG_FEATURES=0 NDEBUG F3DEX_GBI_2 NON_MATCHING AVOID_UB '
                       '_LANGUAGE_C _MIPS_SZLONG=32 _MIPS_SZINT=32 _MIPS_SZPTR=32').split()
        includes = [ROOT / 'oot-core/shim', ROOT / 'oot-core/include', decomp / 'include',
                    decomp / 'include/libc', decomp / 'src', decomp,
                    oot / 'extracted/ntsc-1.2', oot]
        flags = ['-std=gnu++17', '-O2', '-fno-exceptions', '-fno-rtti', '-fpermissive',
                 '-funsigned-char', '-w', '-include', 'oot_prelude.h', '-nostdinc',
                 '-ffunction-sections', '-fdata-sections']
        flags += ['-D' + d for d in definitions] + ['-I' + str(i) for i in includes]
        sources = [decomp / s for s in (
            'src/code/sys_math3d.cpp', 'src/code/TwoHeadArena.cpp', 'src/code/z_lib.cpp',
            'src/code/sys_math.cpp', 'src/code/sys_math_atan.cpp', 'src/libc64/math64.cpp',
            'src/libultra/gu/sins.cpp', 'src/libultra/gu/coss.cpp')]
        sources += [ROOT / s for s in (
            'oot-core/src/oot_math.cpp', 'oot-core/src/oot_rand.cpp',
            'oot-core/src/oot_core_link_stubs.cpp', 'oot-core/tests/bgcheck_host_stubs.cpp',
            'oot-core/tests/bgcheck_population_probe.cpp')]
        scenes = json.loads((ROOT / 'build/generated/scene_table.json').read_text())['scenes']
        bg_source = (oot / 'src/code/z_bgcheck.c').read_text(encoding='utf-8')
        stats = dict(problems=[], macros=0, mtxf=0, anon=0, fxl=0)
        # Hold every pre-existing backend fix equal. Only compare the new pass.
        base = importer.fix_macros('src/code/z_bgcheck.c', bg_source, stats)
        variants = [base, importer.fix_bgcheck_bounds('src/code/z_bgcheck.c', base, stats)]
        # Fx32 range rewrites apply to both sides (headers are imported with them).
        variants = [importer.fix_stored_squares('src/code/z_bgcheck.c',
                        importer.fix_cross_products('src/code/z_bgcheck.c',
                            importer.fix_rand_ranges('src/code/z_bgcheck.c', v, stats), stats), stats)
                    for v in variants]
        self.assertEqual(stats['problems'], [])
        outputs = []
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            for row in scenes:
                if row['prefix'] not in ('souko', 'spot01', 'spot20'):
                    continue
                scene = ROOT / 'build/oot-core/scenecol' / (scene_stem(row['index']) + '.cpp')
                generated = p / (row['prefix'] + '.cpp')
                generated.write_text(scene.read_text().replace('const OotSceneBlob oot_scene_blob',
                                                               'const OotSceneBlob probe_' + row['prefix']))
                sources.append(generated)
            objects = []
            for index, source in enumerate(sources):
                obj = p / ('common%d.o' % index)
                subprocess.run([compiler, *flags, '-c', str(source), '-o', str(obj)],
                               check=True, env=env, capture_output=True)
                objects.append(obj)
            for index, variant in enumerate(variants):
                variant = importer.fix_float_literals(variant, stats)
                variant = importer.fix_mtxf(variant, stats)
                variant = variant.replace('sqrtf(', 'OotProbe_Sqrt(')
                variant = ('#include "ultra64.h"\nf32 OotProbe_Sqrt(f32);\n'
                           'f32 OotProbe_Sqrt(const FxSqExpr&);\nf32 OotProbe_Sqrt(const FxSq&);\n' + variant)
                cpp = p / ('bg%d.cpp' % index)
                cpp.write_text(variant, encoding='utf-8')
                obj = p / ('bg%d.o' % index)
                exe = p / ('probe%d.exe' % index)
                subprocess.run([compiler, *flags, '-c', str(cpp), '-o', str(obj)],
                               check=True, env=env, capture_output=True)
                link = ['-Wl,--gc-sections']
                if os.name == 'nt':
                    link += ['-Wl,--image-base=0x400000', '-Wl,--disable-dynamicbase',
                             '-Wl,--disable-high-entropy-va']
                else:
                    link += ['-no-pie']
                subprocess.run([compiler, str(obj), *map(str, objects), *link, '-o', str(exe)],
                               check=True, env=env, capture_output=True)
                outputs.append(subprocess.check_output([str(exe)], env=env, text=True, timeout=45).splitlines())
        self.assertGreater(len(outputs[0]), 1000)
        self.assertEqual(outputs[0][:-1], outputs[1][:-1])
        before, after = [int(out[-1].split()[1]) for out in outputs]
        self.assertLess(after, before // 2)
        print(f'Cucco scene contact probes: {len(outputs[0]) - 4}; wall square roots {before} -> {after}')


if __name__ == '__main__':
    unittest.main()
