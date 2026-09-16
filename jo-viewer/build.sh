#!/usr/bin/env bash
# Build the isolated Jo Engine / SGL Kokiri viewer.
#
# The bundled toolchain lives in the shared SDK at ../../joengine and must be on
# PATH for make/mkisofs/JoEngineCueMaker. Objects still land in this project's
# obj/ tree -- see the makefile for why that needs overriding.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
compiler="$here/../../joengine/Compiler/WINDOWS"

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
make "$@"

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
python "$here/tools/build_sgl_area.py" --verify

echo
echo "built: $here/game.iso  (cue: game.cue)"
echo "run  : jo-viewer/run-kronos.bat"
