"""Bake every OoT scene's rooms into VDP1 banks (all-scenes preflight).

Reads the decomp scene table (include/tables/scene_table.h) for every scene,
then runs the same converter as build_progression_rooms.py on each room.
Image-shaped rooms (prerendered backdrops) are reported as 'image', not baked
here: build_scene_backdrops.py owns them. A room that fails is 'blocked' with
its error; nothing is skipped silently. Output: build/all-scenes/ +
scene_preflight.json. Not registered in the runtime by this script.
"""
import argparse
import json
import re
import traceback
from pathlib import Path

import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_sgl_scene as sgl

ROOT = Path(__file__).resolve().parents[1]
SCENE_LINE = re.compile(r'/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_SCENE\(\s*(\w+)_scene\s*,\s*\w+\s*,\s*(\w+)')
ROOM_SHAPE_IMAGE = 1


def scene_list(oot):
    out = []
    for line in (oot / 'include/tables/scene_table.h').read_text(encoding='utf-8').splitlines():
        m = SCENE_LINE.search(line)
        if m:
            out.append(dict(id=int(m.group(1), 16), prefix=m.group(2), scene=m.group(3)))
    if not out:
        raise SystemExit('scene table parsed as empty')
    return out


def room_shape(room_data):
    """Room header command 0x0A (SCENE_CMD_ROOM_SHAPE): segment pointer -> type byte."""
    for at in range(0, min(0x400, len(room_data)), 8):
        cmd = room_data[at]
        if cmd == 0x14:
            break
        if cmd == 0x0A:
            ptr = int.from_bytes(room_data[at + 4:at + 8], 'big') & 0xFFFFFF
            return room_data[ptr] if ptr < len(room_data) else None
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=Path(__import__('os').environ.get('DOSEI_OOT')
                    or 'D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/all-scenes')
    ap.add_argument('--only', action='append', help='scene prefix (repeatable)')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Generic import mode (shared/tools/build_kokiri_scene.py): room G_MTX
    # kept at identity, G_BRANCH_Z near geometry walked. Both APPROXIMATE.
    hybrid.source.DisplayLists.generic_scene = True
    hybrid.source.DisplayLists.include_depth_branches = True
    _, head, _, _ = sgl.read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    data, ah, av, af = sgl.read_scene(ROOT / 'build/generated/LINK.BIN')
    tiles = sgl.collect_tiles(data, ah, af)
    actor = dict(tiles=[(t['width'], t['height']) for t in tiles.values()],
                 polygons=len(af), vertices=len(av))
    report = args.out / 'scene_preflight.json'
    old = json.loads(report.read_text()) if args.only and report.exists() else []
    results = [r for r in old if r['prefix'] not in args.only] if args.only else []
    for sc in scene_list(args.oot):
        prefix = sc['prefix']
        if args.only and prefix not in args.only:
            continue
        try:
            segments = hybrid.source.extract(args.oot, args.rom_dir, prefix=prefix)
        except Exception as error:  # noqa: BLE001 - report every failure
            results.append(dict(sc, room=None, status='blocked', error='extract: %s' % error))
            print('%s: extract blocked: %s' % (prefix, error), flush=True)
            continue
        names = sorted((n for n in segments if n.startswith(prefix + '_room_')),
                       key=lambda n: int(n.rsplit('_', 1)[1]))
        for name in names:
            room_id = int(name.rsplit('_', 1)[1])
            entry = dict(sc, room=room_id)
            shape = room_shape(segments[name])
            if shape == ROOM_SHAPE_IMAGE:
                entry.update(status='image')
            else:
                folder = args.out / name
                try:
                    _, vertices, faces, rtiles = hybrid.convert(args.oot, head, actor, folder,
                        rom_dir=args.rom_dir, prefix=prefix, room=name, layout={})
                    detail = json.loads((folder / 'texture_manifest.json').read_text())
                    mesh, pixels, bounds = rooms.pack_room(vertices, faces, rtiles, detail['faces'],
                                                          sgl.face_normal)
                    (folder / 'room.msh').write_bytes(mesh)
                    (folder / 'room.tex').write_bytes(pixels)
                    entry.update(status='baked', vertices=len(vertices), polygons=len(faces),
                                 tiles=len(rtiles), mesh_bytes=len(mesh), pixel_bytes=len(pixels))
                except Exception as error:  # noqa: BLE001
                    entry.update(status='blocked', error='%s: %s' % (type(error).__name__, error),
                                 where=traceback.format_exc().strip().splitlines()[-2].strip())
            results.append(entry)
            print('%s room %d: %s%s' % (prefix, room_id, entry['status'],
                  ' (%s)' % entry['error'] if 'error' in entry else ''), flush=True)
        (args.out / 'scene_preflight.json').write_text(json.dumps(results, indent=1) + '\n')
    counts = {}
    for r in results:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    print('rooms:', counts)


if __name__ == '__main__':
    main()
