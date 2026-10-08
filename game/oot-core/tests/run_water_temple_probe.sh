#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/water-temple/actions"
mkdir -p "$OUT"
python3 - "$GAME" "$OOT" "$OUT" <<'PY'
from pathlib import Path
import re, sys
game, oot, out = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import oot_core_import as imp
rel = 'src/overlays/actors/ovl_Bg_Mizu_Water/z_bg_mizu_water.c'
stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
text = imp.fixup(rel, (oot/rel).read_text(), stats)
header = str(Path(rel).with_suffix('.h'))
(out/'z_bg_mizu_water.h').write_text(imp.fixup(header, (oot/header).read_text(), stats))
parts = ['#include "z_bg_mizu_water.h"', '#include "play_state.h"',
         '#include "one_point_cutscene.h"', '#include "rumble.h"',
         '#include "sfx.h"', '#include "z_lib.h"',
         'void BgMizuWater_WaitForAction(BgMizuWater*, PlayState*);',
         'void BgMizuWater_ChangeWaterLevel(BgMizuWater*, PlayState*);']
parts.append(text[text.index('typedef struct WaterLevel'):text.index('ActorProfile')])
parts.append(re.search(r'static u32 sWaterBoxIndices\[\].*?;', text, re.S)[0])
for name in ['GetWaterLevelActionIndex', 'SetWaterBoxesHeight', 'WaitForAction', 'ChangeWaterLevel']:
    match = re.search(r'^(?:u32|void) BgMizuWater_' + name + r'\([^;{}]*\) \{', text, re.M)
    parts.append(text[match.start():text.index('\n}', match.end())+2])
assert not stats['problems'], stats['problems']
(out/'actions.cpp').write_text('\n'.join(parts)+'\n')
PY
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -I"$OUT" -O1 -ffunction-sections -fdata-sections -no-pie \
    "$HERE/water_temple_fixture.cpp" "$OUT/actions.cpp" "$GAME/oot-core/src/oot_math.cpp" \
    -Wl,--gc-sections -o "$OUT/water_temple_probe"
"$OUT/water_temple_probe"

# Sprite anchor helper with the adapted (pointer-table) actor headers.
INC="$OUT/sprite-inc"
python3 - "$GAME" "$OOT" "$INC" <<'PY'
from pathlib import Path
import re, sys
game, oot, inc = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import oot_core_import as imp
stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
for actor in ('En_Tite', 'En_Firefly', 'En_Ny'):
    rel = f'src/overlays/actors/ovl_{actor}/z_{actor.lower()}.h'
    dest = inc/rel[len('src/'):]
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(imp.fixup(rel, (oot/rel).read_text(), stats))
assert not stats['problems'], stats['problems']
names = re.findall(r'&(\w+),', (game/'build/oot-core/water_anchors.inc').read_text())
(inc/'anim_defs.inc').write_text(''.join(f'AnimationHeader {n};\n' for n in names))
PY
${HOST_CXX:-g++} -I"$INC" $OOT_CORE_CXXFLAGS -O1 -no-pie \
    "$HERE/water_sprite_fixture.cpp" "$GAME/oot-core/src/water_enemy_sprite.cpp" \
    -o "$OUT/water_sprite_probe"
"$OUT/water_sprite_probe"
