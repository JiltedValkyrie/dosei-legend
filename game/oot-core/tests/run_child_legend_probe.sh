#!/usr/bin/env bash
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
OUT="$GAME/build/dodongo-route/legend-probe"
mkdir -p "$OUT"
python3 - "$GAME" "$OOT" "$OUT" <<'PY'
from pathlib import Path
import sys
game,oot,out=map(Path,sys.argv[1:])
sys.path.insert(0,str(game/'tools'))
import child_legend_sources as legend
import oot_core_import as imp
stats=dict(macros=0,fxl=0,anon=0,mtxf=0,files=0,written=0,problems=[])
for rel in (*legend.SOURCES,*(p[:-2]+'.h' for p in legend.SOURCES)):
    text=imp.fixup(rel,(oot/rel).read_text(encoding='utf-8'),stats)
    target=out/'decomp'/rel
    if target.suffix=='.c':target=target.with_suffix('.cpp')
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text)
assert not stats['problems'],stats['problems']
assert not stats.get('fx_range'),stats.get('fx_range')
print('Legend source import: no Fx range findings')
PY
python3 "$GAME/tests/test_child_legend_sources.py"
source "$GAME/oot-core/oot-core-flags.sh"
for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp; do
    ${HOST_CXX:-g++} -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -O1 -c "$file" -o "$OUT/$(basename "${file%.cpp}").o"
done
if [ -n "${TARGET_CXX:-}" ]; then
    mkdir -p "$OUT/sh2"
    for file in "$OUT"/decomp/src/overlays/actors/*/*.cpp; do
        "$TARGET_CXX" -I"$OUT/decomp/src" $OOT_CORE_CXXFLAGS -Os -m2 -fno-threadsafe-statics \
            -fno-use-cxa-atexit -ffunction-sections -fdata-sections -c "$file" -o "$OUT/sh2/$(basename "${file%.cpp}").o"
    done
    "${TARGET_CXX%g++}objdump" -dr "$OUT/sh2"/*.o > "$OUT/disassembly.txt"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/disassembly.txt"
    "${TARGET_CXX%g++}size" "$OUT/sh2"/*.o
fi
