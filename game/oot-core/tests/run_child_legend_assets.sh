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
game,oot,rom=map(Path,sys.argv[1:])
sys.path.insert(0,str(game/'tools'))
import child_legend_sources as legend
import build_child_legend_sprites as gods
import build_core_meshes as meshes
import build_shop_props as props
out=game/'build/dodongo-route/legend-assets'
for p in (out,out/'work',out/'sheets'):p.mkdir(parents=True,exist_ok=True)
rows=gods.bake(oot,rom,out/'work',out/'sheets')
assert len(rows)==4
dlists=meshes.xml_dlists(oot)
built=set()
for actor,rel in legend.DRAW_SOURCES:
    text=legend.adapt(rel,(oot/rel).read_text(encoding='utf-8'))
    for symbol in sorted(set(re.findall(r'\b\w+\b',text)) & dlists.keys()):
        if symbol in built:continue
        obj,offset=dlists[symbol]
        extra={'texture8':'gDust5Tex'} if symbol=='gEffDustDL' else {}
        props.static_mesh(oot,rom,obj,symbol,out/(symbol+'.MSH'),cutout=True,**extra)
        built.add(symbol)
assert 'gGoldenGoddessBodyDL' not in built and 'gGoldenGoddessAuraDL' not in built
print('Legend sprites:',len(rows),'required effect/prop meshes:',len(built))
PY
