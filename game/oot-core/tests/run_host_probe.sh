#!/usr/bin/env bash
# Build the math probe twice on the host (Fx and real float) and diff.
# Needs: python game/tools/oot_core_import.py already run; MSYS2 mingw64 g++.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
CXX=${HOST_CXX:-/c/msys64/mingw64/bin/g++}
source "$GAME/oot-core/oot-core-flags.sh"
OUT=$GAME/build/oot-core/host
mkdir -p "$OUT"
SRCS="$D/src/code/z_lib.cpp $D/src/code/sys_math.cpp $D/src/code/sys_math_atan.cpp $D/src/code/sys_math3d.cpp \
 $D/src/libc64/math64.cpp $D/src/libultra/gu/sins.cpp $D/src/libultra/gu/coss.cpp \
 $GAME/oot-core/src/oot_math.cpp $GAME/oot-core/src/oot_rand.cpp $GAME/oot-core/src/oot_core_link_stubs.cpp $HERE/math_probe.cpp"
for mode in fx hw; do
    extra=""
    [ $mode = hw ] && extra="-DOOT_CORE_HWFLOAT=1"
    PATH=/c/msys64/mingw64/bin:$PATH $CXX $OOT_CORE_CXXFLAGS $extra -O2 $SRCS -o "$OUT/math_probe_$mode.exe"
    PATH=/c/msys64/mingw64/bin:$PATH "$OUT/math_probe_$mode.exe" > "$OUT/math_probe_$mode.txt"
done
${PY:-python3} "$HERE/compare_probe.py" "$OUT/math_probe_hw.txt" "$OUT/math_probe_fx.txt"
