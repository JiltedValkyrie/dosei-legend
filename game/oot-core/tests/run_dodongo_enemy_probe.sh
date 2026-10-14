#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
OUT="$GAME/build/dodongo-route/probe"
mkdir -p "$OUT"
python3 - "$GAME" "$OOT" "$OUT" <<'PY'
from pathlib import Path
import sys
game, oot, out = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import dodongo_enemy_sources as enemies
import oot_core_import as imp
stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
for rel in enemies.SPRITE_SOURCES:
    for path in (rel, rel[:-2]+'.h'):
        text = (oot/path).read_text(encoding='utf-8')
        if not hasattr(imp, 'dodongo_enemy_sources'):
            text = enemies.adapt(path, text)
        text = imp.fixup(path, text, stats)
        target = out/'decomp'/path
        if target.suffix == '.c': target = target.with_suffix('.cpp')
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
assert not stats['problems'], stats['problems']
assert not stats.get('fx_range'), stats.get('fx_range')
print(f'{len(enemies.SPRITE_ACTORS)} source sprite adapters imported; no Fx range findings')
PY
python3 "$GAME/tests/test_dodongo_enemy_sources.py"
source "$GAME/oot-core/oot-core-flags.sh"
for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp; do
    ${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -I"$(dirname "$file")" -O1 -c "$file" \
        -o "$OUT/$(basename "${file%.cpp}").o"
done
python3 - "$OUT" <<'PY'
from pathlib import Path
import re, sys
out = Path(sys.argv[1])
parts = ['#include "oot_prelude.h"', '#include "play_state.h"', '#include "z_lib.h"',
         '#include "z_en_item00.h"', '#include "libc64/math64.h"']
for actor, names in [('En_Dodojr', ('EnDodojr_DropItem', 'EnDodojr_CheckNearbyBombs')),
                     ('En_Dodongo', ('EnDodongo_AteBomb',)),
                     ('En_Shopnuts', ('EnShopnuts_SpawnSalesman',))]:
    stem = 'z_' + actor.lower()
    parts.append(f'#include "overlays/actors/ovl_{actor}/{stem}.h"')
    text = (out/f'decomp/src/overlays/actors/ovl_{actor}/{stem}.cpp').read_text()
    for name in names:
        match = re.search(r'^(?:void|s32) ' + name + r'\([^;{}]*\) \{', text, re.M)
        parts.append(text[match.start():text.index('\n}', match.end())+2])
(out/'actions.cpp').write_text('\n'.join(parts)+'\n')
PY
${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 \
    "$HERE/dodongo_enemy_fixture.cpp" "$OUT/actions.cpp" -o "$OUT/actions"
"$OUT/actions"
ROMS=$(python3 "$GAME/../tools/launcher/project_config.py" oot_roms)
python3 "$GAME/tools/build_dodongo_enemy_anchors.py" --oot "$OOT" --rom-dir "$ROMS" --out "$OUT/dodongo_anchors.inc"
${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 \
    -DOOT_DODONGO_ANCHORS='"'"$OUT/dodongo_anchors.inc"'"' \
    -c "$GAME/oot-core/src/dodongo_enemy_sprite.cpp" -o "$OUT/dodongo_enemy_sprite.o"
echo 'Source actors and semantic contact helper compiled (host Fx).'
if [ -n "${TARGET_CXX:-}" ]; then
    mkdir -p "$OUT/sh2"
    for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp "$GAME/oot-core/src/dodongo_enemy_sprite.cpp"; do
        "$TARGET_CXX" -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -I"$(dirname "$file")" \
            -Os -m2 -fno-threadsafe-statics -fno-use-cxa-atexit -ffunction-sections -fdata-sections \
            -DOOT_DODONGO_ANCHORS='"'"$OUT/dodongo_anchors.inc"'"' \
            -c "$file" -o "$OUT/sh2/$(basename "${file%.cpp}").o"
    done
    "${TARGET_CXX%g++}objdump" -dr "$OUT"/sh2/*.o > "$OUT/sh2/disassembly.txt"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/sh2/disassembly.txt"
    "${TARGET_CXX%g++}size" "$OUT"/sh2/*.o
fi
