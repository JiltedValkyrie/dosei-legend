#!/usr/bin/env bash
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
ROMS=$(python3 "$GAME/../tools/launcher/project_config.py" oot_roms)
python3 - "$GAME" "$OOT" "$ROMS" <<'PY'
from pathlib import Path
import sys
game,oot,rom=map(Path,sys.argv[1:])
sys.path.insert(0,str(game/'tools'))
import build_npc_sprites as sprites
import build_shop_props as props
import child_fairy_sources as fairy
out=game/'build/dodongo-route/fairy-assets'
for p in (out,out/'work',out/'sheets'):p.mkdir(parents=True,exist_ok=True)
rows=sprites.bake_generic(oot,rom,out/'work',out/'sheets',out,only_objects=fairy.SPRITE_OBJECTS)
props.static_mesh(oot,rom,'object_dy_obj','gGreatFairySpiralBeamDL',out/'beam.MSH',cutout=True)
print('Fairy sprite clips:',len(rows),'source refill beam mesh passes')
PY
