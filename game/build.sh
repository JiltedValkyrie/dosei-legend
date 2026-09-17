#!/usr/bin/env bash
# Build the isolated Jo Engine / SGL Kokiri viewer.
#
# Read local tools and source paths from the root config.ini. SDK inputs remain
# read-only; objects and dependency aliases live under this project's build/.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
config="$here/../tools/launcher/project_config.py"
python="$("${DOSEI_PYTHON:-python}" "$config" python)"
python="$(cygpath -u "$python")"
sdk="$("$python" "$config" jo_engine)"
compiler="$(cygpath -u "$sdk")/Compiler/WINDOWS"
oot="$("$python" "$config" oot_decomp)"
roms="$("$python" "$config" oot_roms)"
prepared="$("$python" "$config" --prepare)"
mapfile -t dependencies <<< "${prepared//$'\r'/}"
sgl_source="$(cygpath -u "$sdk")/Compiler/COMMON/SGL_302j/LIB_ELF/SGLAREA.O"
variant=game
mode_args=()
if [ "${1:-}" = "--hires" ]; then
    shift
    variant=game-hires
    mode_args=(HIRES=1)
elif [ "${1:-}" = "--clean" ]; then
    shift
    variant=game-clean
    mode_args=(CLEAN_TEST=1)
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
"$python" "$here/tools/build_sgl_area.py" --source "$sgl_source"
"$python" "$here/tools/build_link_model.py" --flat --animate --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_sgl_scene.py" --texture-path "${TEXTURE_PATH:-hybrid}" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_demo_assets.py" --oot "$oot"
"$python" "$here/tools/build_title_paths.py"
cp "$here/build/generated/kokiri_pixels.bin" "$here/build/cd/KOKIRI.TEX"
cp "$here/build/generated/link_pixels.bin" "$here/build/cd/LINK.TEX"
cp "$here/../shared/assets/audio/title/TITLE_PCM.RAW" "$here/build/cd/TITLE.PCM"
cp "$here/../shared/assets/audio/title/TITLE_LEVELS.RAW" "$here/build/cd/TITLE.LVL"
cp "$here/levels/kokiri/assets/audio/KOKIRI_PCM.RAW" "$here/build/cd/FOREST.PCM"
cp "$here/levels/kokiri/assets/audio/KOKIRI_LEVELS.RAW" "$here/build/cd/FOREST.LVL"

cd "$here"
"${dependencies[1]}/usr/bin/make.exe" "${mode_args[@]}" \
    "JO_ENGINE_SRC_DIR=${dependencies[0]}/jo_engine" \
    "COMPILER_DIR=${dependencies[0]}/Compiler" \
    "SHELL=${dependencies[1]}/usr/bin/bash.exe" "PYTHON=$python" "$@"

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
if ! "$python" "$here/tools/build_sgl_area.py" --source "$sgl_source" --verify --map "$here/build/$variant.map"; then
    echo "boundary check failed: removing the image so it cannot be run" >&2
    rm -f "$here/build/$variant.iso" "$here/build/$variant.cue" "$here/build/$variant.elf" "$here/build/$variant.raw"
    exit 1
fi

echo
echo "built: $here/build/$variant.iso  (cue: build/$variant.cue)"
if [ "$variant" = game-clean ]; then
    echo "run  : open game/build/game-clean.cue in Kronos"
elif [ "$variant" = game-hires ]; then
    echo "run  : game/run-kronos-hires.bat"
else
    echo "run  : game/run-kronos.bat"
fi
