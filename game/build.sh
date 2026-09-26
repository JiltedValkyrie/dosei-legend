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
"$python" "$here/tools/build_sgl_area.py" --source "$sgl_source" --max-polygons "${SGL_MAX_POLYGONS:-3750}" --max-vertices 3200
"$python" "$here/tools/build_link_model.py" --flat --animate --oot "$oot" --rom-dir "$roms"
quad_args=()
if [ -n "${QUAD_OBJ:-}" ]; then
    quad_args=(--quad-obj "$QUAD_OBJ")
fi
# The level is the original ROM triangles, streamed per room so huts and rooms
# stay separate banks. The single authored mesh is off by default; point
# AUTHORED_OBJ at an OBJ to use that import path instead.
: "${AUTHORED_OBJ:=none}"
if [ "$AUTHORED_OBJ" = none ] || [ ! -f "$here/$AUTHORED_OBJ" ]; then
    AUTHORED_OBJ=
fi
# Settings proven for that mesh: one tile per face at ~10 world units per texel,
# a 2400-entry polygon table (1635 forest + 564 Link) and a draw distance that
# covers the whole town instead of one room bank.
if [ -n "$AUTHORED_OBJ" ]; then
    : "${AUTHORED_UNITS_PER_TEXEL:=10}"
    : "${SGL_MAX_POLYGONS:=2400}"
    : "${FOREST_FAR:=2600}"
    : "${MALLOC_ARENA:=180224}"
    set -- "FOREST_FAR=$FOREST_FAR"            "JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC=$MALLOC_ARENA" "$@"
fi

# The authored mesh replaces the whole resident scene, so it cannot use
# the per-room banks: force the single-scene path whenever AUTHORED_OBJ is set.
if [ -n "${AUTHORED_OBJ:-}" ]; then
    STREAM_ROOMS=0
    # The authored scene overwrites the forest tables anyway, so the base run
    # only has to produce Link and vdp1_layout.h. Use the cheap legacy texture
    # path: the hybrid one would spend (and overrun) the budget on a forest
    # that is about to be replaced.
    TEXTURE_PATH=legacy
fi
if [ "${STREAM_ROOMS:-1}" = 1 ]; then
    quad_args+=(--stream-rooms)
fi
if [ -n "${AUTHORED_OBJ:-}" ]; then
    quad_args+=(--skip-scene)
fi
"$python" "$here/tools/build_sgl_scene.py" --texture-path "${TEXTURE_PATH:-hybrid}" --oot "$oot" --rom-dir "$roms" "${quad_args[@]}"
# Overwrite the generated forest with the authored import. Link's tables and
# vdp1_layout.h come from the run above and are left alone.
if [ -n "${AUTHORED_OBJ:-}" ]; then
    "$python" "$here/tools/build_authored_scene.py" --obj "$AUTHORED_OBJ" ${AUTHORED_UV_FROM:+--uv-from "$AUTHORED_UV_FROM"} ${AUTHORED_ATLAS:+--atlas "$AUTHORED_ATLAS"}          ${AUTHORED_UNITS_PER_TEXEL:+--units-per-texel "$AUTHORED_UNITS_PER_TEXEL"}         ${AUTHORED_MAX_TILE:+--max-tile "$AUTHORED_MAX_TILE"}         ${AUTHORED_SPLIT_SPAN:+--split-span "$AUTHORED_SPLIT_SPAN"}         ${AUTHORED_MAX_DEPTH:+--max-depth "$AUTHORED_MAX_DEPTH"}         ${AUTHORED_POLYGON_CAP:+--polygon-cap "$AUTHORED_POLYGON_CAP"}
fi
"$python" "$here/tools/build_scene_table.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_scene_backdrops.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_actors.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_dialogue.py" --oot "$oot"
"$python" "$here/tools/build_action_audio.py" --oot "$oot"
"$python" "$here/tools/build_opening_audio.py" --oot "$oot"
"$python" "$here/tools/build_demo_assets.py" --oot "$oot"
# The dream's Hyrule Field: flat shaded, no tiles, so it costs no VDP1
# texture VRAM and can be resident during the opening alongside nothing else.
if [ "${STREAM_ROOMS:-1}" = 1 ] && \
   [ -f "$here/levels/hyrule/assets/static/hyrulefield-nightmare.obj" ]; then
    "$python" "$here/tools/build_flat_scene.py" \
        --obj "$here/levels/hyrule/assets/static/hyrulefield-nightmare.obj"
fi
# The dream's original textured riders and separate animated horses. Their geometry is read
# into the cart at cutscene time and their tiles into the bank space the flat
# field leaves empty, so they cost nothing while the game is not dreaming.
"$python" "$here/tools/build_actor_model.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_horse_model.py" --oot "$oot" --rom-dir "$roms" --horse zelda
"$python" "$here/tools/build_horse_model.py" --oot "$oot" --rom-dir "$roms" --horse ganon
"$python" "$here/tools/build_cutscene_props.py" --oot "$oot" --rom-dir "$roms"
cp "$here/build/generated/BRIDGE.BIN" "$here/build/cd/BRIDGE.BIN"
cp "$here/build/generated/CHAINS.BIN" "$here/build/cd/CHAINS.BIN"
"$python" "$here/tools/build_cutscenes.py" --oot "$oot"
"$python" "$here/tools/build_title_paths.py"
if [ "${STREAM_ROOMS:-1}" = 1 ]; then
    # One bank per (scene, room). Only scenes whose rooms are real geometry
    # have banks; OoT interiors are prerendered backdrops and have none.
    for bank in "$here"/build/generated/S*R*.MSH "$here"/build/generated/S*R*.TEX "$here"/build/generated/S2R*.MAP "$here"/build/generated/NAVIPOOL.TEX; do
        [ -e "$bank" ] && cp "$bank" "$here/build/cd/"
    done
else
    cp "$here/build/generated/kokiri_pixels.bin" "$here/build/cd/KOKIRI.TEX"
fi
cp "$here/build/generated/link_pixels.bin" "$here/build/cd/LINK.TEX"
for rider in GANON ZELDA IMPA HZELDA HGANON; do
    cp "$here/build/generated/$rider.ANM" "$here/build/cd/$rider.ANM"
    [ -f "$here/build/generated/$rider.BIN" ] &&         cp "$here/build/generated/$rider.BIN" "$here/build/cd/$rider.BIN"
done
cp "$here/build/generated/ACTIONS.PCM" "$here/build/cd/ACTIONS.PCM"
cp "$here/build/generated/OPENING.PCM" "$here/build/cd/OPENING.PCM"
cp "$here"/build/generated/SFX*.PCM "$here/build/cd/"
cp "$here/../shared/assets/audio/title/TITLE_PCM.RAW" "$here/build/cd/TITLE.PCM"
cp "$here/../shared/assets/audio/title/TITLE_LEVELS.RAW" "$here/build/cd/TITLE.LVL"
cp "$here/levels/kokiri/assets/audio/KOKIRI_PCM.RAW" "$here/build/cd/FOREST.PCM"
cp "$here/levels/kokiri/assets/audio/KOKIRI_LEVELS.RAW" "$here/build/cd/FOREST.LVL"
# The opening cutscenes' scores. Built by tools/build_cutscene_audio.py; a bank
# whose sequence the player cannot build yet simply has no files here, and the
# cutscene leaves the current score alone rather than substituting another.
for cs_bank in CSGANON CSNAVI CSDEKU; do
    if [ -f "$here/assets/audio/cutscenes/${cs_bank}_PCM.RAW" ]; then
        cp "$here/assets/audio/cutscenes/${cs_bank}_PCM.RAW" "$here/build/cd/$cs_bank.PCM"
        cp "$here/assets/audio/cutscenes/${cs_bank}_LEVELS.RAW" "$here/build/cd/$cs_bank.LVL"
    fi
done

cd "$here"
# jo_engine_makefile picks its toolchain from $(OS), which does not reach make
# from every shell that can run this script; it then falls back to the LINUX
# binaries and dies with "Exec format error". Compiler/WINDOWS is already
# required above, so name that toolchain outright instead of letting make guess.
"${dependencies[1]}/usr/bin/make.exe" "${mode_args[@]}" \
    "JO_ENGINE_SRC_DIR=${dependencies[0]}/jo_engine" \
    "COMPILER_DIR=${dependencies[0]}/Compiler" \
    "SHELL=${dependencies[1]}/usr/bin/bash.exe" "PYTHON=$python" \
    "CC=$compiler/bin/sh-elf-gcc.exe" "CONV=$compiler/bin/sh-elf-objcopy.exe" \
    "CUE_MAKER=JoEngineCueMaker.exe" "$@"

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
if ! "$python" "$here/tools/build_sgl_area.py" --source "$sgl_source" --max-polygons "${SGL_MAX_POLYGONS:-3750}" --max-vertices 3200 --verify --map "$here/build/$variant.map"; then
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
