"""Bake all M5/M6 room banks into an isolated integration directory.

Uses the game's existing hybrid converter, KRM1 writer and collision exporter.
Does not register unfinished rooms or open absent puzzle gates in player builds.
Failures remain explicit per-room results; successful banks are available for
the dungeon/woods loader integration without repeating source extraction work.
"""
import argparse
import json
from pathlib import Path

import asset_names
import build_hybrid_scene as hybrid
import build_progression_manifest as manifest
import build_room_scene as rooms
import build_sgl_scene as sgl

ROOT = Path(__file__).resolve().parents[1]
# Append-only proposed registration; existing ydan is scene 7.
SCENE_IDS = {'ydan': 7, 'ydan_boss': 9, 'spot10': 8}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/progression-rooms')
    ap.add_argument('--scene', choices=tuple(SCENE_IDS), action='append')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    _, head, _, _ = sgl.read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    actor = sgl.link_actor_budget(ROOT / 'build/generated/LINK.BIN')
    results = []
    for prefix in args.scene or SCENE_IDS:
        scene_id = SCENE_IDS[prefix]
        segments = hybrid.source.extract(args.oot, args.rom_dir, prefix=prefix)
        collision = manifest.scenes.collision_file(
            hybrid.source.collision_data(segments[prefix + '_scene']),
            rooms.transitions(args.oot, args.rom_dir, prefix=prefix,
                              room_count=manifest.SPECS[prefix][1]))
        (args.out / asset_names.scene_asset(scene_id, 'COL')).write_bytes(collision)
        for room_id in range(manifest.SPECS[prefix][1]):
            folder = args.out / ('%s_room_%d' % (prefix, room_id))
            entry = dict(prefix=prefix, scene=scene_id, room=room_id)
            try:
                _, vertices, faces, tiles = hybrid.convert(args.oot, head, actor, folder,
                    rom_dir=args.rom_dir, prefix=prefix, room='%s_room_%d' % (prefix, room_id),
                    layout={})
                detail = json.loads((folder / 'texture_manifest.json').read_text())
                mesh, pixels, bounds = rooms.pack_room(vertices, faces, tiles, detail['faces'], sgl.face_normal)
                mesh_name = asset_names.room_asset(scene_id, room_id, 'MSH')
                pixel_name = asset_names.room_asset(scene_id, room_id, 'TEX')
                (args.out / mesh_name).write_bytes(mesh)
                (args.out / pixel_name).write_bytes(pixels)
                entry.update(status='baked', mesh=mesh_name, pixels=pixel_name,
                    vertices=len(vertices), polygons=len(faces), tiles=len(tiles),
                    objects=len(bounds), mesh_bytes=len(mesh), pixel_bytes=len(pixels),
                    budget=detail['budget'], vram_limit=detail['vram_limit'])
            except (ValueError, RuntimeError) as error:
                entry.update(status='blocked', error=str(error))
            results.append(entry)
            print('%s room %d: %s' % (prefix, room_id, entry['status']), flush=True)
    report = dict(version=1, runtime_registered=False,
        actor_budget_note='Link and existing resident effects only; new enemy/puzzle actors still require reservations.',
        rooms=results)
    (args.out / 'room_preflight.json').write_text(json.dumps(report, indent=2) + '\n')
    failed = [r for r in results if r['status'] != 'baked']
    print('%d/%d room banks baked; %d blocked' % (len(results) - len(failed), len(results), len(failed)))
    if failed:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
