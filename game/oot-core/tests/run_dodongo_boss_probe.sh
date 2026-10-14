#!/usr/bin/env bash
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
OUT="$GAME/build/dodongo-route/boss-probe"
mkdir -p "$OUT"
python3 - "$GAME" "$OOT" "$OUT" <<'PY'
from pathlib import Path
import sys
game, oot, out = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import dodongo_boss_sources as boss
import child_route_effects as effects
import oot_core_import as imp
stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
for rel in (boss.BOSS_SOURCE, boss.BOSS_HEADER, boss.BOSS_DATA,
            *boss.SUPPORT_SOURCES, *(p[:-2]+'.h' for p in boss.SUPPORT_SOURCES),
            *boss.EFFECT_SOURCES, *(p[:-2]+'.h' for p in boss.EFFECT_SOURCES),
            *effects.SOURCES, *(p[:-2]+'.h' for p in effects.SOURCES)):
    text = (oot/rel).read_text(encoding='utf-8')
    if not hasattr(imp, 'dodongo_boss_sources'):
        text = boss.adapt(rel, text)
    text = imp.fixup(rel, text, stats)
    target = out/'decomp'/rel
    if target.suffix == '.c' and not rel.endswith('.inc.c'): target = target.with_suffix('.cpp')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
assert not stats['problems'], stats['problems']
assert not stats.get('fx_range'), stats.get('fx_range')
print('King Dodongo source imported; no Fx range findings')
PY
python3 "$GAME/tests/test_dodongo_boss_sources.py"
python3 "$GAME/tests/test_child_route_effects.py"
source "$GAME/oot-core/oot-core-flags.sh"
for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp "$OUT"/decomp/src/overlays/effects/*/*.cpp; do
    ${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 -c "$file" \
        -o "$OUT/$(basename "${file%.cpp}").o"
done
python3 - "$OUT" <<'PY'
from pathlib import Path
import re, sys
out = Path(sys.argv[1])
parts = ['#include "oot_prelude.h"', '#include "play_state.h"', '#include "player.h"',
         '#include "save.h"', '#include "z_lib.h"', '#include "interface.h"',
         '#include "libc64/math64.h"', '#include "printf.h"',
         'static s16 sWarpTimerTarget = 100;', 'void func_80B85264(struct ItemBHeart*, PlayState*);']
for actor, names in [('Boss_Dodongo', ('BossDodongo_AteExplosive',)),
                     ('Item_B_Heart', ('ItemBHeart_Update',)),
                     ('Door_Warp1', ('DoorWarp1_PlayerInRange', 'DoorWarp1_ChildWarpOut'))]:
    stem = 'z_' + actor.lower()
    parts.append(f'#include "overlays/actors/ovl_{actor}/{stem}.h"')
    text = (out/f'decomp/src/overlays/actors/ovl_{actor}/{stem}.cpp').read_text()
    for name in names:
        match = re.search(r'^(?:void|s32) ' + name + r'\([^;{}]*\) \{', text, re.M)
        parts.append(text[match.start():text.index('\n}', match.end())+2])
(out/'actions.cpp').write_text('\n'.join(parts)+'\n')
PY
${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 \
    "$HERE/dodongo_boss_fixture.cpp" "$OUT/actions.cpp" -o "$OUT/actions"
"$OUT/actions"
${HOST_CC:-gcc} -std=c99 -Wall -Wextra -Werror -O2 "$HERE/dodongo_lava_fixture.c" -o "$OUT/lava"
"$OUT/lava"
echo 'Real boss skeleton/combat/intro/death source and lava sink compile (host Fx).'
if [ -n "${TARGET_CXX:-}" ]; then
    mkdir -p "$OUT/sh2"
    for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp "$OUT"/decomp/src/overlays/effects/*/*.cpp; do
        "$TARGET_CXX" -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -Os -m2 \
            -fno-threadsafe-statics -fno-use-cxa-atexit -ffunction-sections -fdata-sections \
            -c "$file" -o "$OUT/sh2/$(basename "${file%.cpp}").o"
    done
    "${TARGET_CXX%g++}objdump" -dr "$OUT/sh2"/*.o > "$OUT/disassembly.txt"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/disassembly.txt"
    "${TARGET_CXX%g++}size" "$OUT/sh2"/*.o
fi
