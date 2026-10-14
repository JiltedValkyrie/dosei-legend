#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/cutscene-camera/probe"
mkdir -p "$OUT"
python3 "$GAME/tools/onepoint_sources.py" --oot "$OOT" --out "$OUT/onepoint_fixture.cpp"
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -DOOT_CORE_HWFLOAT=0 -O1 -ffunction-sections -fdata-sections -no-pie \
    "$HERE/cutscene_camera_fixture.cpp" "$GAME/oot-core/src/bridge_cutscene_camera.cpp" \
    "$D/src/code/z_cutscene_spline.cpp" "$GAME/oot-core/src/oot_math.cpp" "$OUT/onepoint_fixture.cpp" \
    -Wl,--gc-sections -o "$OUT/cutscene_camera_probe"
"$OUT/cutscene_camera_probe"
if [ -n "${SH2_CXX:-}" ]; then
    "$SH2_CXX" $OOT_CORE_CXXFLAGS -Os -m2 -mb -c \
        "$GAME/oot-core/src/bridge_cutscene_camera.cpp" -o "$OUT/camera_sh2.o"
    "$SH2_CXX" $OOT_CORE_CXXFLAGS -Os -m2 -mb -c \
        "$OUT/onepoint_fixture.cpp" -o "$OUT/onepoint_sh2.o"
    "${SH2_CXX%g++}objdump" -dr "$OUT/camera_sh2.o" > "$OUT/camera_sh2.dis"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/camera_sh2.dis"
    "${SH2_CXX%g++}objdump" -dr "$OUT/onepoint_sh2.o" > "$OUT/onepoint_sh2.dis"
    python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/onepoint_sh2.dis"
fi
