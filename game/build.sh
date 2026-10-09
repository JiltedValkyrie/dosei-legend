#!/usr/bin/env bash
# Build the isolated Jo Engine / SGL Kokiri viewer.
#
# Read local tools and source paths from the root config.ini. SDK inputs remain
# read-only; objects and dependency aliases live under this project's build/.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
config="$here/../tools/launcher/project_config.py"
# Linux (incl. WSL): host bash/make/python3 and Jo's Compiler/LINUX toolchain.
# Windows: MSYS2 and Compiler/WINDOWS, as before.
linux=0
if [ "$(uname -s)" = Linux ]; then
    linux=1
    cygpath() { printf '%s\n' "${@: -1}"; }   # paths are already POSIX
    python="${DOSEI_PYTHON:-python3}"
    sdk="$("$python" "$config" jo_engine)"
    # gcc 9.3 built by tools/toolchain/build-sh-elf-linux.sh matches the
    # Windows compiler. Jo's own Compiler/LINUX gcc 8.2 overflows work RAM.
    sh_elf="${SH_ELF_LINUX:-$(cd "$here/../.." && pwd)/sh-elf-9.3-linux}"
    if [ ! -x "$sh_elf/bin/sh-elf-gcc" ]; then
        echo "Linux sh-elf gcc 9.3 missing at $sh_elf: run tools/toolchain/build-sh-elf-linux.sh" >&2
        exit 1
    fi
    compiler="$sh_elf"
    cc_check="$sh_elf/bin/sh-elf-gcc"
else
    python="$("${DOSEI_PYTHON:-python}" "$config" python)"
    python="$(cygpath -u "$python")"
    sdk="$("$python" "$config" jo_engine)"
    compiler="$(cygpath -u "$sdk")/Compiler/WINDOWS"
    cc_check="$compiler/bin/sh-elf-gcc.exe"
fi
oot="$("$python" "$config" oot_decomp)"
export DOSEI_OOT="$oot"
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
# Human accepted room texture halving for Clean. Preserve explicit overrides;
# standalone tools and other variants retain their mode-0 default.
if [ "$variant" = game-clean ]; then
    export DOSEI_TEX_HALVE="${DOSEI_TEX_HALVE-2}"
fi
# --quick (after --clean/--hires, before make args): skip asset generation and
# reuse build/cd + build/generated from the last full build of this variant.
# For C/C++ (and oot-core) changes only; never for asset/tool changes.
quick=0
if [ "${1:-}" = "--quick" ]; then
    shift
    quick=1
    if [ ! -f "$here/build/generated/scene_table.c" ] || [ ! -f "$here/build/cd/LINK.TEX" ]; then
        echo "--quick needs one full build first" >&2
        exit 1
    fi
fi

if [ ! -x "$cc_check" ]; then
    echo "Jo Engine SDK not found at $compiler" >&2
    exit 1
fi

export PATH="$compiler/Other Utilities:$compiler/bin:$PATH"
mkdir -p "$here/build/cd" "$here/build/generated"
# Retired overlength filenames cannot be addressed by Saturn GFS.
rm -f "$here/build/cd/TREEMOUTH.BIN" "$here/build/cd/BOSSHEART.BIN" \
      "$here/build/cd/BOSSCLEAR.PCM" "$here/build/cd/BOSSCLEAR.LVL"
if [ "$quick" != 1 ]; then
# Freeze the chosen layout once so mid-build GUI changes cannot mix versions.
"$python" "$here/tools/layout_variants.py" --snapshot "$here/build/generated/layout-build.json" --oot "$oot" --rom-dir "$roms"
export DOSEI_LAYOUT_SNAPSHOT="$(cygpath -w "$here/build/generated/layout-build.json")"
cp "$here/disc/ABS.TXT" "$here/disc/BIB.TXT" "$here/disc/CPY.TXT" "$here/build/cd/"

# Regenerate the SGL tables from the original scene, then stage the 4bpp blob
# on the CD image. Both are cheap and keep game.iso consistent with FOREST.BIN.
"$python" "$here/tools/build_sgl_area.py" --source "$sgl_source" --max-polygons "${SGL_MAX_POLYGONS:-3750}" --max-vertices 3200
"$python" "$here/tools/build_link_model.py" --flat --animate --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_adult_link.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_link_gear.py" --oot "$oot" --rom-dir "$roms"   # adult hero gear meshes
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
# Generic banks must match source, converter/material rules and live actor
# budgets. Previously only Ranch refreshed and every other scene stayed stale.
    "$python" "$here/tools/build_all_scenes.py" --oot "$oot" --rom-dir "$roms" --refresh-stale --retail-only
"$python" "$here/tools/build_sgl_scene.py" --texture-path "${TEXTURE_PATH:-hybrid}" --oot "$oot" --rom-dir "$roms" "${quad_args[@]}"
# Overwrite the generated forest with the authored import. Link's tables and
# vdp1_layout.h come from the run above and are left alone.
if [ -n "${AUTHORED_OBJ:-}" ]; then
    "$python" "$here/tools/build_authored_scene.py" --obj "$AUTHORED_OBJ" ${AUTHORED_UV_FROM:+--uv-from "$AUTHORED_UV_FROM"} ${AUTHORED_ATLAS:+--atlas "$AUTHORED_ATLAS"}          ${AUTHORED_UNITS_PER_TEXEL:+--units-per-texel "$AUTHORED_UNITS_PER_TEXEL"}         ${AUTHORED_MAX_TILE:+--max-tile "$AUTHORED_MAX_TILE"}         ${AUTHORED_SPLIT_SPAN:+--split-span "$AUTHORED_SPLIT_SPAN"}         ${AUTHORED_MAX_DEPTH:+--max-depth "$AUTHORED_MAX_DEPTH"}         ${AUTHORED_POLYGON_CAP:+--polygon-cap "$AUTHORED_POLYGON_CAP"}
fi
"$python" "$here/tools/build_scene_table.py" --oot "$oot" --rom-dir "$roms" --require-retail
"$python" "$here/tools/build_area_music.py" --oot "$oot"
cp "$here"/build/generated/owl/OWL*.BIN "$here"/build/generated/owl/OWL*.ANM "$here/build/cd/"
# NPCs ship as sprites only: no mesh NPC BIN/ANM/TRK/SKN build.
"$python" "$here/tools/build_npc_sprites.py" --oot "$oot" --rom-dir "$roms"   # NPC sprite sheets (Clean)
cp "$here"/build/generated/npcs/NPC*.SPR "$here/build/cd/"
# Surface bits now live inside S<n>.COL (KBG2); drop the retired .SUR files.
rm -f "$here"/build/cd/S*.SUR
"$python" "$here/tools/build_scene_backdrops.py" --oot "$oot" --rom-dir "$roms"
# Occlusion masks from the room depth mesh (needs the backdrop above).
"$python" "$here/tools/build_interior_masks.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_world_props.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_shop_props.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_actors.py" --oot "$oot" --rom-dir "$roms"
"$python" "$here/tools/build_dialogue.py" --oot "$oot"
"$python" "$here/tools/build_minimap.py" --oot "$oot"
"$python" "$here/tools/build_pause_windows.py" --oot "$oot" --sdk "$sdk"
"$python" "$here/tools/build_cdda.py"
"$python" "$here/tools/song_dictionary.py"
"$python" "$here/tools/build_action_audio.py" --oot "$oot"
"$python" "$here/tools/build_field_enemy_audio.py" --oot "$oot" --generated "$here/build/generated" --cd "$here/build/cd" --source "$here/../shared/build/audio-source/extracted/assets/audio"
"$python" "$here/tools/build_opening_audio.py" --oot "$oot"
"$python" "$here/tools/build_recomp_assets.py" --oot "$oot"
"$python" "$here/tools/build_fairy.py" --oot "$oot"
# En_Karebaba flat model (M2d.2) -> build/cd/DEKUBABA.BIN
"$python" "$here/tools/build_dekubaba.py" --oot "$oot" --rom-dir "$roms"
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
"$python" "$here/tools/build_npc_sprites.py" --story-only --out "$here/build/cd"
"$python" "$here/tools/build_cutscene_props.py" --oot "$oot" --rom-dir "$roms"
cp "$here/build/generated/BRIDGE.BIN" "$here/build/cd/BRIDGE.BIN"
cp "$here/build/generated/CHAINS.BIN" "$here/build/cd/CHAINS.BIN"
cp "$here/build/generated/GATEFIRE.BIN" "$here/build/cd/GATEFIRE.BIN"
"$python" "$here/tools/build_cutscenes.py" --oot "$oot"
cp "$here/build/generated/"{GODBODY,GODAURA,TRIFORCE,EMERALD}.BIN "$here/build/cd/"
"$python" "$here/tools/build_title_paths.py"
"$python" "$here/tools/build_interior_audio.py" --oot "$oot"
"$python" "$here/tools/build_gohma.py" --oot "$oot"
"$python" "$here/tools/build_field_audio.py" --oot "$oot"
for area_bank in HOUSE SHOP DUNGEON WOODS FAIRY BOSS BOSSCLEAR OWL FAIRYGET FIELD STONE; do
    disc_bank="$area_bank"
    [ "$area_bank" != BOSSCLEAR ] || disc_bank=BOSSCLR
    cp "$here/build/generated/${area_bank}_PCM.RAW" "$here/build/cd/$disc_bank.PCM"
    cp "$here/build/generated/${area_bank}_LEVELS.RAW" "$here/build/cd/$disc_bank.LVL"
done
"$python" "$here/tools/build_cart_tables.py"
if [ "${STREAM_ROOMS:-1}" = 1 ]; then
    # One bank per (scene, room). Only scenes whose rooms are real geometry
    # have banks; OoT interiors are prerendered backdrops and have none.
    # Hyrule Field streams from one KRM2 file; drop its retired KRM1 bank.
    rm -f "$here/build/cd/SAR0.MSH" "$here/build/cd/SAR0.TEX"
    for bank in "$here"/build/generated/S*R*.MSH "$here"/build/generated/S*R*.TEX "$here"/build/generated/Z*R*.MSH "$here"/build/generated/Z*R*.TEX "$here"/build/generated/C*R*.MSH "$here"/build/generated/C*R*.TEX "$here"/build/generated/S*R*.STM "$here"/build/generated/C0R*.MAP "$here"/build/generated/NAVIPOOL.TEX; do
        [ -e "$bank" ] && cp "$bank" "$here/build/cd/"
    done
else
    cp "$here/build/generated/kokiri_pixels.bin" "$here/build/cd/KOKIRI.TEX"
fi
cp "$here/build/generated/link_pixels.bin" "$here/build/cd/LINK.TEX"
cp "$here/build/generated/LINKANIM.BIN" "$here/build/cd/LINKANIM.BIN"
for rider in GANON ZELDA IMPA HZELDA HGANON OWLPERCH OWLFLY; do
    rm -f "$here/build/cd/$rider.ANM" "$here/build/cd/$rider.BIN"
done
rm -f "$here"/build/cd/NPC*.BIN "$here"/build/cd/NPC*.ANM "$here"/build/cd/NPC*.TRK "$here"/build/cd/NPC*.SKN
cp "$here/build/generated/ACTIONS.PCM" "$here/build/cd/ACTIONS.PCM"
cp "$here/build/generated/ADULTACT.PCM" "$here/build/cd/ADULTACT.PCM"
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
# Directory capacity: checked by the makefile before mastering, after the
# core-collision / real-Player retirements below (BUILD.md 50).
"$python" "$here/tools/check_forest_budget.py"
# Field floor (STM) and C collision (COL) must come from one retopo bundle.
"$python" "$here/tools/field_retopo.py" --check-pairing stm,col
fi  # quick

# Density builds must not retain old story meshes under image-scene IDs.
# The tool is a no-op in mode 0; RGB/panorama/collision assets are preserved.
"$python" "$here/tools/prune_obsolete_room_banks.py"
# Small colour tables derive from the staged geometry and original sky images.
# Run for quick builds too: they use the same preserved room banks.
"$python" "$here/tools/build_environment_sky.py" --oot "$oot" \
    --cd "$here/build/cd" --scene-table "$here/build/generated/scene_table.json" \
    --out "$here/build/generated"
# oot-core (fork Phase 0): `./build.sh OOT_CORE=1` mirrors the decomp first.
# Without it, drop a stale OOTCORE.BIN so it never ships on a normal disc.
oot_core=0
for arg in "$@"; do
    [ "$arg" = OOT_CORE=1 ] && oot_core=1
done
core_collision=$oot_core
player_source=$oot_core
for arg in "$@"; do
    [ "$arg" = CORE_COLLISION=0 ] && core_collision=0
    [ "$arg" = PLAYER_SOURCE=0 ] && player_source=0
done
# Files the core-collision / real-Player disc no longer reads are parked in
# build/disc-retired (the GFS directory holds 1536 entries). Restore them
# first: the Field pairing check and the host probes read the .COL files.
mkdir -p "$here/build/disc-retired"
for f in "$here"/build/disc-retired/*; do [ -e "$f" ] && mv -f "$f" "$here/build/cd/"; done || true
if [ "$oot_core" = 1 ]; then
    # Real Player frame bank (PLAYER_SOURCE): ids feed the importer's anim
    # headers, ALL.PFB becomes PLAYANIM.PFB. Rebuilt when its tools change.
    bank="$here/build/player-migration/bank_full"
    if [ ! -f "$bank/ALL.PFB" ] || [ "$here/tools/build_player_frame_bank.py" -nt "$bank/ALL.PFB" ] ||
       [ "$here/tools/player_frame_pack.py" -nt "$bank/ALL.PFB" ] || [ "$here/tools/build_link_model.py" -nt "$bank/ALL.PFB" ]; then
        "$python" "$here/tools/build_player_frame_bank.py" --oot "$oot" \
            --objdump "$sh_elf/bin/sh-elf-objdump" \
            --out "$here/build/player-migration/frame_bank_full.json" --bank "$bank"
    fi
    "$python" "$here/tools/oot_core_import.py" --oot "$oot"
    "$python" "$here/tools/build_field_enemy_anchors.py" --oot "$oot" --rom-dir "$roms"
    # oot-core scene collision (SA.OOC) must match the Field STM/COL bundle.
    "$python" "$here/tools/field_retopo.py" --check-pairing stm,col,ooc
    # Phase 2 draw shim meshes (K/Q*.MSH) + build/oot-core/generic_meshes.h.
    "$python" "$here/tools/build_core_meshes.py" --oot "$oot" --rom-dir "$roms"
    # Sprite NPCs have no runtime skin models or limb draw registry.
    printf '/* Sprite-only NPCs: no skinned draw entries. */\n { 0xFFFF, 0, 0, 0 },\n' > "$here/build/oot-core/generic_skins.h"
    rm -f "$here"/build/cd/N????.BIN "$here"/build/cd/N????.SKN
    # Sprite sheets + symbol manifest; make resolves keys after object linking.
    rm -f "$here"/build/cd/G?????.SPR "$here"/build/cd/G?????.SP2
    "$python" "$here/tools/build_npc_sprites.py" --oot "$oot" --rom-dir "$roms" --generic-only --out "$here/build/generated/generic-sprites"
    # Link's tools (arrows, bombs, Bombchu, boomerang, hookshot, held gear, boots).
    "$python" "$here/tools/build_item_sprites.py" --oot "$oot" --rom-dir "$roms" --out "$here/build/cd"
else
    rm -f "$here/build/cd/OOTCORE.BIN"
fi
[ "$core_collision" = 1 ] && { mv -f "$here"/build/cd/*.COL "$here/build/disc-retired/" 2>/dev/null || true; }
[ "$player_source" = 1 ] && mv -f "$here/build/cd/LINKANIM.BIN" "$here/build/cd/ADULTANM.BIN" \
    "$here/build/disc-retired/" 2>/dev/null || true
# jo_engine_makefile picks its toolchain from $(OS), which does not reach make
# from every shell that can run this script; it then falls back to the LINUX
# binaries and dies with "Exec format error". Compiler/WINDOWS is already
# required above, so name that toolchain outright instead of letting make guess.
if [ "$linux" = 1 ]; then
    # CC/CONV override Jo's Compiler/LINUX (gcc 8.2) choice.
    make "${mode_args[@]}" \
        "JO_ENGINE_SRC_DIR=${dependencies[0]}/jo_engine" \
        "COMPILER_DIR=${dependencies[0]}/Compiler" \
        "CC=$sh_elf/bin/sh-elf-gcc" "CONV=$sh_elf/bin/sh-elf-objcopy" \
        "PYTHON=$python" "$@"
else
"${dependencies[1]}/usr/bin/make.exe" "${mode_args[@]}" \
    "JO_ENGINE_SRC_DIR=${dependencies[0]}/jo_engine" \
    "COMPILER_DIR=${dependencies[0]}/Compiler" \
    "SHELL=${dependencies[1]}/usr/bin/bash.exe" "PYTHON=$python" \
    "CC=$compiler/bin/sh-elf-gcc.exe" "CONV=$compiler/bin/sh-elf-objcopy.exe" \
    "CUE_MAKER=JoEngineCueMaker.exe" "$@"
fi

# The work area is laid out from the top of work RAM downwards, so .bss must
# end below its base. Only the map just produced can prove that.
if ! "$python" "$here/tools/build_sgl_area.py" --source "$sgl_source" --max-polygons "${SGL_MAX_POLYGONS:-3750}" --max-vertices 3200 --verify --map "$here/build/$variant.map"; then
    echo "boundary check failed: removing the image so it cannot be run" >&2
    rm -f "$here/build/$variant.iso" "$here/build/$variant.cue" "$here/build/$variant.elf" "$here/build/$variant.raw"
    exit 1
fi

echo
if [ "$variant" = game-clean ]; then
    "$python" "$here/tools/map_build_status.py" --game "$here"
fi
echo "built: $here/build/$variant.iso  (cue: build/$variant.cue)"
if [ "$variant" = game-clean ]; then
    echo "run  : open game/build/game-clean.cue in Kronos"
elif [ "$variant" = game-hires ]; then
    echo "run  : game/run-kronos-hires.bat"
else
    echo "run  : game/run-kronos.bat"
fi
