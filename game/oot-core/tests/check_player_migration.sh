#!/usr/bin/env bash
# Syntax gate only: no live blob, profile replacement, assets or disc writes.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
: "${OOT:?Set OOT to the extracted decomp root}"
OUT=${PLAYER_MIGRATION_OUT:-$GAME/build/player-migration}
python3 "$GAME/tools/stage_player_migration.py" --oot "$OOT" --out "$OUT"
source "$GAME/oot-core/oot-core-flags.sh"
OOT_CORE_CXXFLAGS=${OOT_CORE_CXXFLAGS//"$D"/"$OUT/decomp"}
failed=0
for rel in src/code/z_player_call src/code/z_player_lib src/overlays/actors/ovl_player_actor/z_player; do
    name=${rel##*/}
    if "${HOST_CXX:-g++}" $OOT_CORE_CXXFLAGS -fsyntax-only -fmax-errors=12 \
        "$OUT/decomp/$rel.cpp" > "$OUT/$name.log" 2>&1; then
        printf '%s: syntax PASS\n' "$name"
    else
        printf '%s: syntax FAIL (%s)\n' "$name" "$OUT/$name.log"
        failed=1
    fi
done
[ "${TARGET:-0}" = 1 ] && [ "$failed" = 0 ] || exit "$failed"
# TARGET=1: isolated SH-2 objects with the makefile's target flags, then the
# wide-helper audit and symbol/size map. Nothing is linked into the live blob.
SH=${SH_ELF_LINUX:-$(cd "$GAME/../.." && pwd)/sh-elf-9.3-linux}/bin/sh-elf
mkdir -p "$OUT/sh2"
for rel in src/code/z_player_call src/code/z_player_lib src/overlays/actors/ovl_player_actor/z_player; do
    name=${rel##*/}
    if "$SH-g++" $OOT_CORE_CXXFLAGS -fno-threadsafe-statics -fno-use-cxa-atexit -Os -m2 \
        -ffunction-sections -fdata-sections -c "$OUT/decomp/$rel.cpp" -o "$OUT/sh2/$name.o" \
        > "$OUT/sh2/$name.log" 2>&1; then
        printf '%s: SH-2 compile PASS\n' "$name"
    else
        printf '%s: SH-2 compile FAIL (%s)\n' "$name" "$OUT/sh2/$name.log"
        rm -f "$OUT/sh2/$name.o"
        failed=1
    fi
done
[ "$failed" = 0 ] || exit 1
"$SH-objdump" -d "$OUT"/sh2/*.o > "$OUT/sh2/player.dis"
python3 "$GAME/tools/audit_oot_core_wide.py" "$OUT/sh2/player.dis" || failed=1
python3 "$GAME/tools/player_migration_symbols.py" --objdir "$OUT/sh2" \
    --nm "$SH-nm" --size "$SH-size" --gc-ld "$SH-ld" --out "$OUT/symbols.json" || failed=1
# HOOKS=1: size missing engine hooks and real Link skeleton blobs (no link).
if [ "${HOOKS:-0}" = 1 ] && [ "$failed" = 0 ]; then
    python3 "$GAME/tools/size_player_hooks.py" --cxx "$SH-g++"         --cxxflags "$OOT_CORE_CXXFLAGS -fno-threadsafe-statics -fno-use-cxa-atexit -Os -m2 -ffunction-sections -fdata-sections"         --ld "$SH-ld" --nm "$SH-nm" --size "$SH-size" --objdump "$SH-objdump" --oot "$OOT"         --symbols "$OUT/symbols.json" --out "$OUT/hooks" || failed=1
fi
# FRAMES=1: budget the real Player animation frame bank (no link).
if [ "${FRAMES:-0}" = 1 ] && [ "$failed" = 0 ]; then
    python3 "$GAME/tools/size_player_frames.py" --oot "$OOT" --objdump "$SH-objdump"         --out "$OUT/frames.json" || failed=1
fi
exit "$failed"
