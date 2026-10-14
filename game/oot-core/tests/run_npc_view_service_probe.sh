#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/npc-view-service/probe"
mkdir -p "$OUT"
python3 "$GAME/tools/npc_view_sources.py" --out "$OUT/all.cpp"
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -DOOT_CORE_HWFLOAT=0 -O1 -ffunction-sections -fdata-sections -no-pie \
    "$HERE/npc_view_service_fixture.cpp" "$OUT/all.cpp" "$GAME/oot-core/src/oot_math.cpp" \
    -Wl,--gc-sections -o "$OUT/view_probe"
"$OUT/view_probe"
if [ -n "${SH2_CXX:-}" ]; then
    "$SH2_CXX" $OOT_CORE_CXXFLAGS -Os -m2 -mb -fno-threadsafe-statics -fno-use-cxa-atexit \
        -ffunction-sections -fdata-sections -c "$OUT/all.cpp" -o "$OUT/views_sh2.o"
    "${SH2_CXX%g++}objdump" -dr "$OUT/views_sh2.o" > "$OUT/views_sh2.dis"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/views_sh2.dis"
fi
