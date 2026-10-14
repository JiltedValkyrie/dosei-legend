#!/usr/bin/env bash
# Source/asset staging only: never compile the host, master a disc or launch it.
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
ROMS=$(python3 "$GAME/../tools/launcher/project_config.py" oot_roms)
cd "$GAME"
python3 tools/oot_core_import.py --oot "$OOT"
python3 tools/build_core_meshes.py --oot "$OOT" --rom-dir "$ROMS"
