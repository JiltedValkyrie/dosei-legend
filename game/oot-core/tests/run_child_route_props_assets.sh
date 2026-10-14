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
import sys,re
game, oot, rom = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import build_npc_sprites as sprites
import build_core_meshes as meshes
import build_shop_props as props
import child_route_props as route
out=game/'build/dodongo-route/prop-assets'
for folder in (out, out/'work', out/'sheets'): folder.mkdir(parents=True,exist_ok=True)
sprites.bake_generic(oot,rom,out/'work',out/'sheets',out,only_objects=route.SPRITE_OBJECTS)
dlists=meshes.xml_dlists(oot)
built=set()
for actor, rel in route.DRAW_SOURCES:
    names=set(re.findall(r'\b\w+\b',(oot/rel).read_text(encoding='utf-8')))
    wanted=sorted(names & dlists.keys())
    if not wanted: raise ValueError('No source prop mesh: '+actor)
    for symbol in wanted:
        if symbol in built: continue
        obj,offset=dlists[symbol]
        props.static_mesh(oot,rom,obj,symbol,out/(symbol+'.MSH'),cutout=True)
        built.add(symbol)
print('Child route props:',len(built),'required meshes, one falling-rock sprite')
PY
