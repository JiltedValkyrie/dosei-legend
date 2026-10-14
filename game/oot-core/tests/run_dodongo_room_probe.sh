#!/usr/bin/env bash
# Isolated source room bake, no disc or generated runtime capacities touched.
set -eu
trap '' HUP
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
export DOSEI_OOT="$OOT"
ROMS=$(python3 "$GAME/../tools/launcher/project_config.py" oot_roms)
python3 - "$GAME" "$OOT" "$ROMS" <<'PY'
from pathlib import Path
import json, sys
game, oot, rom = map(Path, sys.argv[1:])
sys.path.insert(0, str(game/'tools'))
import build_sgl_scene as sgl
import build_hybrid_scene as hybrid
from build_room_scene import pack_room
out = game/'build/dodongo-route/room-probe'
out.mkdir(parents=True, exist_ok=True)
_, head, _, _ = sgl.read_scene(game/'levels/kokiri/assets/static/FOREST.BIN')
actor = sgl.link_actor_budget(game/'build/generated/LINK.BIN')
for room_id in range(2):
    room = 'ddan_boss_room_%d' % room_id
    folder = out/('room%d' % room_id)
    _, vertices, faces, tiles = hybrid.convert(oot, head, actor, folder, rom_dir=rom,
        room=room, prefix='ddan_boss', **hybrid.room_conversion_policy('ddan_boss', room))
    manifest = json.loads((folder/'texture_manifest.json').read_text())
    mesh, pixels, bounds = pack_room(vertices, faces, tiles, manifest['faces'], sgl.face_normal)
    (out/('SGR%d.MSH' % room_id)).write_bytes(mesh)
    (out/('SGR%d.TEX' % room_id)).write_bytes(pixels)
    if room_id == 1:
        tagged = sum(r.get('surface_tag') == 0xDD01 for r in manifest['faces'])
        assert tagged, 'source lava tags lost before staging'
        print('Boss arena lava faces:', tagged)
    print('Boss room%d: %d faces %d tiles %d pixelbytes' % (room_id, len(faces), len(tiles), len(pixels)))
PY
