#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/cutscene-camera/probe"
mkdir -p "$OUT"
python3 "$GAME/tools/onepoint_sources.py" --oot "$OOT" --out "$OUT/onepoint_fixture.cpp"
python3 "$HERE/build_cutscene_script_probe.py" "$OOT" "$OUT/cutscene_script_source.inc"
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -include "$OUT/ultratypes32.h" -DOOT_CORE_HWFLOAT=0 -O1 -ffunction-sections -fdata-sections -no-pie -I"$OUT" \
    "$HERE/cutscene_script_fixture.cpp" "$GAME/oot-core/src/bridge_cutscene_camera.cpp" \
    "$D/src/code/z_cutscene_spline.cpp" "$GAME/oot-core/src/oot_math.cpp" "$OUT/onepoint_fixture.cpp" \
    -Wl,--gc-sections -o "$OUT/cutscene_script_probe"
"$OUT/cutscene_script_probe"
