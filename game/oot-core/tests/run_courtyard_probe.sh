#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
OUT="$GAME/build/child-route-courtyard/probe"
mkdir -p "$OUT"
source "$GAME/oot-core/oot-core-flags.sh"
for actor in En_Owl En_Zl4 Demo_Im En_Viewer; do
    stem="z_${actor,,}"
    source_file="$D/src/overlays/actors/ovl_$actor/$stem.cpp"
    ${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -O1 -c "$source_file" -o "$OUT/$stem.o"
    if [ -n "${SH2_CXX:-}" ]; then
        "$SH2_CXX" $OOT_CORE_CXXFLAGS -Os -m2 -mb -c "$source_file" -o "$OUT/${stem}_sh2.o"
        "${SH2_CXX%g++}objdump" -dr "$OUT/${stem}_sh2.o" > "$OUT/${stem}_sh2.dis"
    fi
done
if [ -n "${SH2_CXX:-}" ]; then
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT"/*_sh2.dis
fi
python3 -m unittest discover -s "$GAME/tests" -p test_owl_source.py
python3 -m unittest discover -s "$GAME/tests" -p test_courtyard_source.py
