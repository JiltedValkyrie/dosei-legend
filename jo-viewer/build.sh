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
python "$here/tools/build_sgl_scene.py"
cp "$here/generated/kokiri_pixels.bin" "$here/cd/KOKIRI.TEX"

cd "$here"
make "$@"

echo
echo "built: $here/game.iso  (cue: game.cue)"
echo "run  : jo-viewer/run-kronos.bat"
