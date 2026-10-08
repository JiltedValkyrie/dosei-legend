"""Execute source projectile movement through the actual core init register."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_fx32 import ROOT, DECOMP, host_flags, compiler_env, importer
from test_graphics_backend import function


def extract(text, marker):
    start = text.index(marker)
    end = text.index('{', start) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


@unittest.skipUnless((DECOMP / 'include/ultra64.h').exists() and importer.OOT_DEFAULT.exists(),
                     'local decomp and oot-core import required')
class CoreUpdateRate(unittest.TestCase):
    def test_real_actor_motion_uses_initialized_source_rate(self):
        bodies = []
        for rel, markers in (
            ('src/code/z_construct.c', ['void Regs_InitDataImpl(void)']),
            ('src/code/z_lib.c', ['f32 Math_CosS(', 'f32 Math_SinS(', 's32 Math_ScaledStepToS(']),
            ('src/code/z_actor.c', ['void Actor_UpdatePos(', 'void Actor_UpdateVelocityXZGravity(',
                                  'void Actor_MoveXZGravity(', 'void Actor_SetProjectileSpeed(']),
        ):
            raw = (importer.OOT_DEFAULT / rel).read_text(encoding='utf-8')
            stats = dict(macros=0, fxl=0, anon=0, mtxf=0, problems=[])
            imported = importer.fixup(rel, raw, stats)
            bodies.extend(extract(imported, marker) for marker in markers)
        source = r'''
#include "ultra64.h"
#include "actor.h"
#include "regs.h"
#include "save.h"
#include "sequence.h"
#include "ocarina.h"
#include "interface.h"
#include "play_state.h"
#include "z_lib.h"
#include "oot_core_host.h"
extern "C" int printf(const char*, ...);
#define CHECK(c) do { if (!(c)) { printf("line %d: %s\n",__LINE__,#c); return 1; } } while (0)
typedef void (*OotCoreCtor)(void);
static OotCoreCtor oot_core_ctors_start[1];
static OotCoreCtor* oot_core_ctors_end = oot_core_ctors_start;
static RegEditor sRegEditor;
RegEditor* gRegEditor = &sRegEditor;
SaveContext gSaveContext;
const OotCoreHost* gOotCoreHost;
uintptr_t gSegments[16];
''' + '\n'.join(bodies) + '\n' + function(ROOT / 'oot-core/src/oot_core_api.cpp',
                                                    'static void oot_core_init(') + r'''
static Actor shot(int speed) {
    Actor actor = {};
    actor.world.pos = {1000,150,2000};
    actor.minVelocityY = -150;
    Actor_SetProjectileSpeed(&actor,speed);
    return actor;
}
int main() {
    /* The actual scene-register setup never initializes GameState's rate.
     * Reproduce the shipped failure with actual imported motion functions. */
    Regs_InitDataImpl();
    CHECK(R_UPDATE_RATE == 0);
    Actor frozen = shot(150);
    Actor_MoveXZGravity(&frozen);
    CHECK(frozen.world.pos.z == 2000 && frozen.velocity.z > 149);
    s16 frozenTurn = 0;
    Math_ScaledStepToS(&frozenTurn,1000,100);
    CHECK(frozenTurn == 0);

    oot_core_init(NULL);
    CHECK(R_UPDATE_RATE == 3);
    Regs_InitDataImpl(); /* scene reinitialization must preserve source rate */
    CHECK(R_UPDATE_RATE == 3);
    const int speeds[]={150,80,20};
    for (int speed : speeds) {
        Actor actor = shot(speed); /* arrow, seed, hook respectively */
        for (int tick=0;tick<3;++tick) Actor_MoveXZGravity(&actor);
        Fx expected = Fx(2000) + actor.velocity.z * FXL(1.5f) * 3;
        CHECK(actor.world.pos.z == expected);
        CHECK(actor.world.pos.z > 2000 + speed*4);
        CHECK(actor.world.pos.x == 1000 && actor.world.pos.y == 150);
    }
    Actor rising = shot(20);
    rising.world.rot.x = -0x2000;
    Actor_SetProjectileSpeed(&rising,20);
    rising.gravity = -1;
    rising.colChkInfo.displacement = {2,3,-4};
    Fx initialY = rising.velocity.y;
    Actor_MoveXZGravity(&rising);
    CHECK(rising.world.pos.x == 1002);
    CHECK(rising.world.pos.y == Fx(150) + (initialY-1)*FXL(1.5f) + 3);
    CHECK(rising.world.pos.z == Fx(2000) + rising.velocity.z*FXL(1.5f) - 4);
    s16 turn = 0;
    Math_ScaledStepToS(&turn,1000,100);
    CHECK(turn == 150);
    return 0;
}
'''
        compiler, env = compiler_env()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)
            cpp = path / 'rate.cpp'
            exe = path / 'rate.exe'
            cpp.write_text(source, encoding='utf-8')
            result = subprocess.run([compiler, *host_flags(), str(cpp),
                                     str(DECOMP / 'src/libultra/gu/sins.cpp'),
                                     str(DECOMP / 'src/libultra/gu/coss.cpp'),
                                     str(ROOT / 'oot-core/src/oot_math.cpp'), '-o', str(exe)],
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(exe)], env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
