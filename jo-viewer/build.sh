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

# Regenerate the SGL tables from the original scene, then stage the 4bpp blob
# on the CD image. Both are cheap and keep game.iso consistent with FOREST.BIN.
python "$here/tools/build_sgl_area.py"
python "$here/tools/build_link_model.py"
python "$here/tools/build_sgl_scene.py"
python "$here/tools/build_demo_assets.py"
cp "$here/generated/kokiri_pixels.bin" "$here/cd/KOKIRI.TEX"
cp "$here/generated/link_pixels.bin" "$here/cd/LINK.TEX"
cp "$here/../title-screen/assets/TITLE_PCM.RAW" "$here/cd/TITLE.PCM"
cp "$here/../title-screen/assets/TITLE_LEVELS.RAW" "$here/cd/TITLE.LVL"
cp "$here/assets/kokiri/KOKIRI_PCM.RAW" "$here/cd/FOREST.PCM"
cp "$here/assets/kokiri/KOKIRI_LEVELS.RAW" "$here/cd/FOREST.LVL"

cd "$here"
make "${mode_args[@]}" "$@"

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
if ! python "$here/tools/build_sgl_area.py" --verify --map "$here/$variant.map"; then
    echo "boundary check failed: removing the image so it cannot be run" >&2
    rm -f "$here/$variant.iso" "$here/$variant.cue" "$here/$variant.elf" "$here/$variant.raw"
    exit 1
fi

echo
echo "built: $here/$variant.iso  (cue: $variant.cue)"
if [ "$variant" = game-hires ]; then
    echo "run  : jo-viewer/run-kronos-hires.bat"
else
    echo "run  : jo-viewer/run-kronos.bat"
fi
