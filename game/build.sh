#!/usr/bin/env bash
# Build the isolated Jo Engine / SGL Kokiri viewer.
#
# The bundled toolchain lives in the shared SDK at ../../joengine and must be on
# PATH for make/mkisofs/JoEngineCueMaker. Objects still land in this project's
# obj/ tree -- see the makefile for why that needs overriding.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compiler="$here/../../joengine/Compiler/WINDOWS"
variant=game
mode_args=()
if [ "${1:-}" = "--hires" ]; then
    shift
    variant=game-hires
    mode_args=(HIRES=1)
fi

if [ ! -x "$compiler/bin/sh-elf-gcc.exe" ]; then
    echo "Jo Engine SDK not found at $compiler" >&2
    exit 1
fi

export PATH="$compiler/Other Utilities:$compiler/bin:$PATH"
mkdir -p "$here/build/cd" "$here/build/generated"
cp "$here/disc/ABS.TXT" "$here/disc/BIB.TXT" "$here/disc/CPY.TXT" "$here/build/cd/"

# Regenerate the SGL tables from the original scene, then stage the 4bpp blob
# on the CD image. Both are cheap and keep game.iso consistent with FOREST.BIN.
python "$here/tools/build_sgl_area.py"
python "$here/tools/build_link_model.py"
python "$here/tools/build_sgl_scene.py"
python "$here/tools/build_demo_assets.py"
cp "$here/build/generated/kokiri_pixels.bin" "$here/build/cd/KOKIRI.TEX"
cp "$here/build/generated/link_pixels.bin" "$here/build/cd/LINK.TEX"
cp "$here/../shared/assets/audio/title/TITLE_PCM.RAW" "$here/build/cd/TITLE.PCM"
cp "$here/../shared/assets/audio/title/TITLE_LEVELS.RAW" "$here/build/cd/TITLE.LVL"
cp "$here/levels/kokiri/assets/audio/KOKIRI_PCM.RAW" "$here/build/cd/FOREST.PCM"
cp "$here/levels/kokiri/assets/audio/KOKIRI_LEVELS.RAW" "$here/build/cd/FOREST.LVL"

cd "$here"
make "${mode_args[@]}" "$@"

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
if ! python "$here/tools/build_sgl_area.py" --verify --map "$here/build/$variant.map"; then
    echo "boundary check failed: removing the image so it cannot be run" >&2
    rm -f "$here/build/$variant.iso" "$here/build/$variant.cue" "$here/build/$variant.elf" "$here/build/$variant.raw"
    exit 1
fi

echo
echo "built: $here/build/$variant.iso  (cue: build/$variant.cue)"
if [ "$variant" = game-hires ]; then
    echo "run  : game/run-kronos-hires.bat"
else
    echo "run  : game/run-kronos.bat"
fi
