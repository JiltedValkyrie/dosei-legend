#!/usr/bin/env bash
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
OUT="$GAME/build/dodongo-route/fairy-probe"
mkdir -p "$OUT"
python3 - "$GAME" "$OOT" "$OUT" <<'PY'
from pathlib import Path
import sys,re
game,oot,out=map(Path,sys.argv[1:])
sys.path.insert(0,str(game/'tools'))
import child_fairy_sources as fairy
import child_route_effects as effects
import oot_core_import as imp
sources=fairy.SOURCES+tuple(p for p in effects.SOURCES if p.endswith(('z_eff_ss_extra.c','z_eff_ss_fcircle.c','z_eff_ss_solder_srch_ball.c')))
stats=dict(macros=0,fxl=0,anon=0,mtxf=0,files=0,written=0,problems=[])
for rel in (*sources,*(p[:-2]+'.h' for p in sources)):
    text=imp.fixup(rel,(oot/rel).read_text(encoding='utf-8'),stats)
    target=out/'decomp'/rel
    if target.suffix=='.c':target=target.with_suffix('.cpp')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text)
assert not stats['problems'],stats['problems']
assert not stats.get('fx_range'),stats.get('fx_range')
text=(out/'decomp'/fairy.SOURCES[0]).with_suffix('.cpp').read_text()
parts=[text[:text.index('ActorProfile Bg_Dy_Yoseizo_Profile')]]
for m in re.finditer(r'static (?:s16|u8) (sSpellRewards\w+)\[3\] = \{.*?\n\};',text,re.S):parts.append(m[0])
parts.append('void BgDyYoseizo_SpawnEffectsType(BgDyYoseizo*,PlayState*,s16);\nvoid BgDyYoseizo_UpdatePosY(BgDyYoseizo*,PlayState*);')
name='BgDyYoseizo_Reward_GiveReward'
m=re.search(r'^void '+name+r'\([^;{}]*\) \{',text,re.M)
parts.append(text[m.start():text.index('\n}',m.end())+2])
(out/'reward.cpp').write_text('\n'.join(parts))
print('Fairy + three source effect profiles imported; no Fx range findings')
PY
python3 "$GAME/tests/test_child_fairy_sources.py"
python3 "$GAME/tests/test_child_route_effects.py"
source "$GAME/oot-core/oot-core-flags.sh"
for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp "$OUT"/decomp/src/overlays/effects/*/*.cpp; do
    ${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 -c "$file" -o "$OUT/$(basename "${file%.cpp}").o"
done
${HOST_CXX:-g++} -I"$OUT/decomp/src" -I"$OUT/decomp/src/overlays/actors/ovl_Bg_Dy_Yoseizo" $OOT_CORE_CXXFLAGS -O1 "$HERE/child_fairy_fixture.cpp" "$OUT/reward.cpp" -o "$OUT/reward"
"$OUT/reward"
if [ -n "${TARGET_CXX:-}" ]; then
    mkdir -p "$OUT/sh2"
    for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp "$OUT"/decomp/src/overlays/effects/*/*.cpp; do
        "$TARGET_CXX" -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -Os -m2 -fno-threadsafe-statics \
            -fno-use-cxa-atexit -ffunction-sections -fdata-sections -c "$file" -o "$OUT/sh2/$(basename "${file%.cpp}").o"
    done
    "${TARGET_CXX%g++}objdump" -dr "$OUT/sh2"/*.o > "$OUT/disassembly.txt"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/disassembly.txt"
    "${TARGET_CXX%g++}size" "$OUT/sh2"/*.o
fi
