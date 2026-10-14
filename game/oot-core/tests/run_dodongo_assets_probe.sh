#!/usr/bin/env bash
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
ROMS=$(python3 "$GAME/../tools/launcher/project_config.py" oot_roms)
python3 "$GAME/tools/build_dodongo_boss_meshes.py" --oot "$OOT" --rom-dir "$ROMS" \
    --core "$GAME/build/oot-core" --out "$GAME/build/dodongo-route/boss-meshes"
python3 - "$GAME" "$OOT" "$ROMS" <<'PY'
from pathlib import Path
from collections import Counter
import sys
game, oot, rom = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import build_hybrid_scene as h
from build_dodongo_fire_sprites import bake
bake(oot,rom,game/'build/dodongo-route/boss-meshes',game/'build/dodongo-route/boss-meshes')
from build_child_warp_mesh import bake as bake_warp
bake_warp(oot,rom,game/'build/dodongo-route/boss-meshes/portal.MSH')
faces = h.load_faces(oot, rom, 'ddan_boss')
print('Boss source lava triangles:', sum(bool(f.get('surface_tag')) for f in faces))
assert sum(bool(f.get('surface_tag')) for f in faces) == 24
PY
