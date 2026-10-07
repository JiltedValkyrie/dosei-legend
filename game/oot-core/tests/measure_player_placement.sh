#!/usr/bin/env bash
# Isolated retention measurement; does not build or stage a playable disc.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
: "${OOT:?Set OOT to the extracted decomp root}"
source "$GAME/oot-core/oot-core-flags.sh"
SH=${SH_ELF_LINUX:-$(cd "$GAME/../.." && pwd)/sh-elf-9.3-linux}/bin/sh-elf
python3 "$GAME/tools/measure_player_placement.py" --cxx "$SH-g++" \
    --cxxflags "$OOT_CORE_CXXFLAGS -fno-threadsafe-statics -fno-use-cxa-atexit -Os -m2 -ffunction-sections -fdata-sections" \
    --ld "$SH-ld" --nm "$SH-nm" --size "$SH-size"
