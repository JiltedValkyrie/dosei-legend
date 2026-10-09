#!/usr/bin/env bash
# Collision port checks on Kokiri Forest. Linux/WSL g++.
# 1. Parity: identical query inputs through the C library (S1.COL), the Fx core
#    (Saturn arithmetic) and the same core source on host floats (hw);
#    compare_bg_port.py reports C vs hw, fx vs hw and C vs fx per query.
# 2. Dyna contract: owner-local poly ids, removal, slot reuse, flat normals.
# 3. Shim: one bg_* scenario (platform, rotated ramp, rotated box, rider over
#    moving + turning frames, disable/enable, removal, slot reuse) built with
#    the C library and with src/bg_core_shim.c over the real core.
# 4. Link wrappers (CORE_COLLISION): kokiri_collision_floor/clear/spawn/
#    move_actor/fall/jump/move from the C library vs src/bg_core_link.c over
#    the shim; compare_bg_link.py classifies the differences.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
CXX=${HOST_CXX:-g++}
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT=$GAME/build/oot-core/host
mkdir -p "$OUT"
LIB=$GAME/../shared/lib/collision
# Core-collision disc builds park the C .COL files in build/disc-retired.
S1COL=$GAME/build/cd/S1.COL
[ -f "$S1COL" ] || S1COL=$GAME/build/disc-retired/S1.COL
gcc -O1 -c "$LIB/kokiri_collision.c" -o "$OUT/kokiri_collision.o"
CORE="$D/src/code/z_bgcheck.cpp $D/src/code/sys_math3d.cpp $D/src/code/TwoHeadArena.cpp $D/src/code/z_lib.cpp"
CORE="$CORE $D/src/code/sys_math.cpp $D/src/code/sys_math_atan.cpp $D/src/libc64/math64.cpp"
CORE="$CORE $D/src/libultra/gu/sins.cpp $D/src/libultra/gu/coss.cpp $D/src/code/z_skin_matrix.cpp"
CORE="$CORE $D/src/code/z_bg_collect.cpp $D/src/code/z_bg_item.cpp $GAME/oot-core/src/oot_math.cpp $GAME/oot-core/src/oot_rand.cpp"
CORE="$CORE $GAME/build/oot-core/scenecol/S1.cpp $GAME/oot-core/src/oot_core_bg.cpp"
STUBS="$GAME/oot-core/src/oot_core_link_stubs.cpp $HERE/bgcheck_host_stubs.cpp"
FLAGS="$OOT_CORE_CXXFLAGS -DBG_REAL_SKIN_MATRIX -I$LIB -O1"

for mode in fx hw; do
    extra=""
    [ $mode = hw ] && extra="-DOOT_CORE_HWFLOAT=1"
    $CXX $FLAGS $extra $CORE "$HERE/bg_port_probe.cpp" -no-pie $STUBS \
        -x none "$OUT/kokiri_collision.o" -o "$OUT/bg_port_probe_$mode"
    "$OUT/bg_port_probe_$mode" "$S1COL" > "$OUT/bg_port_$mode.txt"
done
${PY:-python3} "$HERE/compare_bg_port.py" "$OUT/bg_port_fx.txt" "$OUT/bg_port_hw.txt"

$CXX $FLAGS $CORE "$HERE/bg_dyna_probe.cpp" -no-pie $STUBS -o "$OUT/bg_dyna_probe"
"$OUT/bg_dyna_probe"

gcc -O1 -I"$LIB" "$HERE/bg_shim_scenario.c" "$HERE/bg_shim_scene_c.c" "$LIB/kokiri_collision.c" \
    -o "$OUT/bg_shim_c"
"$OUT/bg_shim_c" "$S1COL" > "$OUT/bg_shim_c.txt"
gcc -O1 -c -I"$LIB" -I"$GAME/oot-core/include" "$HERE/bg_shim_scenario.c" -o "$OUT/bg_shim_scenario.o"
gcc -O1 -c -I"$LIB" -I"$GAME/oot-core/include" "$GAME/src/bg_core_shim.c" -o "$OUT/bg_core_shim.o"
$CXX $FLAGS $CORE "$HERE/bg_shim_scene_core.cpp" -no-pie $STUBS \
    -x none "$OUT/bg_shim_scenario.o" "$OUT/bg_core_shim.o" -o "$OUT/bg_shim_core"
"$OUT/bg_shim_core" > "$OUT/bg_shim_core.txt"
${PY:-python3} "$HERE/compare_bg_shim.py" "$OUT/bg_shim_c.txt" "$OUT/bg_shim_core.txt"

gcc -O1 -I"$LIB" "$HERE/bg_link_scenario.c" "$HERE/bg_shim_scene_c.c" "$LIB/kokiri_collision.c"     -o "$OUT/bg_link_c"
"$OUT/bg_link_c" "$S1COL" > "$OUT/bg_link_c.txt"
for f in bg_link_scenario.c; do
    gcc -O1 -c -DCORE_COLLISION -I"$LIB" -I"$GAME/oot-core/include" "$HERE/$f" -o "$OUT/${f%.c}.o"
done
for f in bg_core_shim.c bg_core_link.c; do
    gcc -O1 -c -DCORE_COLLISION -I"$LIB" -I"$GAME/oot-core/include" -I"$GAME/src" "$GAME/src/$f"         -o "$OUT/link_${f%.c}.o"
done
$CXX $FLAGS $CORE "$HERE/bg_shim_scene_core.cpp" -no-pie $STUBS     -x none "$OUT/bg_link_scenario.o" "$OUT/link_bg_core_shim.o" "$OUT/link_bg_core_link.o" -o "$OUT/bg_link_core"
"$OUT/bg_link_core" > "$OUT/bg_link_core.txt"
${PY:-python3} "$HERE/compare_bg_link.py" "$OUT/bg_link_c.txt" "$OUT/bg_link_core.txt"

# BENCH=1: host cost of the same Kokiri queries, C library vs core (fx).
if [ "${BENCH:-0}" = 1 ]; then
    gcc -O2 -c "$LIB/kokiri_collision.c" -o "$OUT/kokiri_collision_o2.o"
    $CXX ${FLAGS/-O1/-O2} $CORE "$HERE/bg_bench.cpp" -no-pie $STUBS \
        -x none "$OUT/kokiri_collision_o2.o" -o "$OUT/bg_bench"
    "$OUT/bg_bench" "$S1COL"
fi
