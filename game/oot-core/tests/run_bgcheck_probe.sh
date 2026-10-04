#!/usr/bin/env bash
# Real z_bgcheck + scene collision blob on the host, Fx vs float. Linux/WSL g++.
# Usage: tests/run_bgcheck_probe.sh [scenecol cpp, default S1 = Kokiri Forest]
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
CXX=${HOST_CXX:-g++}
# Default Linux g++ has 64-bit long; MinGW (HOST_CXX=.../mingw64/bin/g++) matches SH-2 32-bit long.
LDX="-no-pie $GAME/oot-core/src/oot_core_link_stubs.cpp $HERE/bgcheck_host_stubs.cpp"
SAN="-g -fsanitize=address"
case "$CXX" in *mingw*) LDX="$GAME/oot-core/src/oot_core_link_stubs.cpp $HERE/bgcheck_host_stubs.cpp -Wl,--image-base=0x400000 -Wl,--disable-dynamicbase -Wl,--disable-high-entropy-va"; SAN="-g"; export PATH=$(dirname "$CXX"):$PATH;; esac
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT=$GAME/build/oot-core/host
mkdir -p "$OUT"
SCENE=${1:-$GAME/build/oot-core/scenecol/S1.cpp}
SRCS="$D/src/code/z_bgcheck.cpp $D/src/code/sys_math3d.cpp $D/src/code/TwoHeadArena.cpp $D/src/code/z_lib.cpp \
 $D/src/code/sys_math.cpp $D/src/code/sys_math_atan.cpp $D/src/libc64/math64.cpp $D/src/libultra/gu/sins.cpp \
 $D/src/libultra/gu/coss.cpp $GAME/oot-core/src/oot_math.cpp $GAME/oot-core/src/oot_rand.cpp $SCENE $HERE/bgcheck_probe.cpp"
for mode in fx hw; do
    extra=""
    [ $mode = hw ] && extra="-DOOT_CORE_HWFLOAT=1"
    $CXX $OOT_CORE_CXXFLAGS $extra -O1 $SAN $SRCS -o "$OUT/bgcheck_probe_$mode" $LDX
    "$OUT/bgcheck_probe_$mode" > "$OUT/bgcheck_probe_$mode.txt" || echo "$mode probe crashed"
done
${PY:-python3} "$HERE/compare_probe.py" "$OUT/bgcheck_probe_hw.txt" "$OUT/bgcheck_probe_fx.txt"
