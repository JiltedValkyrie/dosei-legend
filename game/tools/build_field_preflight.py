"""M7 source ledger and isolated gameplay Field bake; never registers a scene."""
import argparse
import json
from pathlib import Path

import build_actor_manifest as actors
import build_progression_manifest as manifest
import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_sgl_scene as sgl
import build_field_owl as owl

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    parser.add_argument('--rom-dir', type=Path)
    parser.add_argument('--source-tessellation', action='store_true')
    parser.add_argument('--base-tile-limit', type=int, choices=(16,32,64))
    parser.add_argument('--with-owl', action='store_true', help='Bake and reserve both original owl models')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/field-preflight')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    segments = hybrid.source.extract(args.oot, args.rom_dir, prefix='spot00')
    names = actors.table(args.oot / 'include/tables/actor_table.h', 'DEFINE_ACTOR')
    objects = actors.table(args.oot / 'include/tables/object_table.h', 'DEFINE_OBJECT')
    ledger = manifest.scene_manifest('spot00', segments, names, objects,
        manifest.scenes.entrance_table(args.oot), ('SCENE_HYRULE_FIELD', 1))
    for exit in ledger['exits']:
        exit['demo_policy'] = ('return_to_woods' if exit['scene'] == 'SCENE_LOST_WOODS'
                               else 'demo_boundary_required')
    ledger['owls'] = [a for r in ledger['rooms'] for a in r['actors'] if a['name'] == 'En_Owl']
    collision = hybrid.source.collision_data(segments['spot00_scene'])
    (args.out / 'FIELD.COL').write_bytes(manifest.scenes.collision_file(collision))
    ledger['runtime_registered'] = False
    ledger['base_tile_limit'] = args.base_tile_limit
    ledger['source_tessellation'] = args.source_tessellation
    ledger['budget_note'] = 'Link/resident effects only; owl, props and worst-view submission still require measurement.'
    _, head, _, _ = sgl.read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    data, link_head, vertices, faces = sgl.read_scene(ROOT / 'build/generated/LINK.BIN')
    tiles = sgl.collect_tiles(data, link_head, faces)
    actor = dict(tiles=[(t['width'], t['height']) for t in tiles.values()],
                 polygons=len(faces), vertices=len(vertices))
    if args.with_owl:
        ledger['owl_assets'] = owl.build(args.oot, args.rom_dir, args.out/'owl')
        models = ledger['owl_assets']['models']
        actor['tiles'].extend(t for m in models for t in m['tiles'])
        actor['polygons'] += max(m['polygons'] for m in models)
        actor['vertices'] += max(m['vertices'] for m in models)
        ledger['budget_note'] = ('Link, resident effects and both owl texture banks reserved; '
            'one owl skeleton drawn at a time. Other props and worst-view submission remain open.')
    try:
        folder = args.out / 'spot00_room_0'
        _, vertices, faces, tiles = hybrid.convert(args.oot, head, actor, folder,
            rom_dir=args.rom_dir, prefix='spot00', room='spot00_room_0', layout={}, base_tile_limit=args.base_tile_limit, source_tessellation=args.source_tessellation)
        detail = json.loads((folder / 'texture_manifest.json').read_text())
        mesh, pixels, bounds = rooms.pack_room(vertices, faces, tiles, detail['faces'], sgl.face_normal)
        (args.out / 'FIELD.MSH').write_bytes(mesh)
        (args.out / 'FIELD.TEX').write_bytes(pixels)
        ledger['bake'] = dict(status='baked', vertices=len(vertices), polygons=len(faces),
            tiles=len(tiles), objects=len(bounds), mesh_bytes=len(mesh), pixel_bytes=len(pixels),
            budget=detail['budget'], vram_limit=detail['vram_limit'])
    except (ValueError, RuntimeError) as error:
        ledger['bake'] = dict(status='blocked', error=str(error))
    (args.out / 'field_preflight.json').write_text(json.dumps(ledger, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(dict(collision=ledger['collision']['triangles'], exits=ledger['exits'],
                         owls=ledger['owls'], bake=ledger['bake']), indent=2))
    if ledger['bake']['status'] != 'baked':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
