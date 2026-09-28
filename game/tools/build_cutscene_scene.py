#!/usr/bin/env python3
"""Bake the authored cutscene forest into its own VDP1 room bank.

Navi's flight crosses the whole of Kokiri Forest, which the streamed room
banks cannot show: they hold one room at a time and the shot would fly through
missing geometry. The authored `kokiriforest-newGameCs.obj` is the whole zone
at a polygon count a single bank can hold, and it exists only for that shot.

It is emitted as a room bank -- S<scene>R0.MSH / .TEX -- rather than as the
compiled-in resident scene, because only one bank is ever resident:

  * the cutscene loads this bank, so no hut, no other forest room and no other
    streamed asset is in VDP1 VRAM while it plays, and the whole texture
    budget is the cutscene's;
  * gameplay reloads the ordinary streamed rooms afterwards, unchanged;
  * it costs no permanent RAM, only the shared bank buffers that already exist.

Geometry, tiles and atlas baking are build_authored_scene.py's; the binary
layout is build_room_scene.pack_room's. This tool only joins the two, so
neither the import rules nor the bank format live in two places.

It also writes cutscene_bank.json, which build_room_scene.py folds into the
compiled bank capacities -- a bank bigger than those is rejected at load.

Offline tool: floating point is fine here.
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_authored_scene as authored                         # noqa: E402
import build_room_scene as rooms                                # noqa: E402
from build_sgl_scene import face_normal                         # noqa: E402
from PIL import Image                                           # noqa: E402
import asset_names

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Scene 2 is the cutscene forest. Scenes 0 and 1 are Link's house and the
# streamed Kokiri Forest; this one is never entered by walking into it, so it
# needs no scene_table entry, only a bank the cutscene can ask for by number.
CUTSCENE_SCENE_ID = 2


def convert(obj_path, atlas_path, units_per_texel, max_tile, cull):
    """Authored OBJ -> (vertices, faces, tiles), the shapes pack_room wants."""
    positions, uvs, raw_faces, mtllib = authored.parse_obj(obj_path)
    if not positions or not raw_faces:
        raise SystemExit('%s: no geometry' % obj_path)
    if not uvs:
        raise SystemExit('%s: no UVs' % obj_path)

    if atlas_path is None:
        if not mtllib:
            raise SystemExit('%s: no mtllib and no --atlas' % obj_path)
        textures = authored.parse_mtl(obj_path.parent / mtllib)
        names = sorted(set(textures.values()))
        if len(names) != 1:
            raise SystemExit('expected one map_Kd, found %d: %s'
                             % (len(names), names))
        atlas_path = pathlib.Path(names[0])
    if not atlas_path.exists():
        raise SystemExit('atlas not found: %s' % atlas_path)
    atlas = Image.open(atlas_path).convert('RGBA')

    pieces, dropped = [], 0
    for face in raw_faces:
        for corners in authored.triangulate(face, positions):
            if any(c[1] is None for c in corners):
                dropped += 1
                continue
            pieces.append(list(corners))
    if dropped:
        print('  warn  : %d faces dropped for missing UVs' % dropped)

    faces = []
    for corners in pieces:
        index = [c[0] for c in corners]
        if len(index) == 3:
            index.append(index[2])      # SGL draws a triangle as a degenerate quad
        faces.append(dict(idx=tuple(index), uv=[uvs[c[1]] for c in corners],
                          cull=cull, mesh=False))

    tiles, tile_ids = collections.OrderedDict(), {}
    for face in faces:
        width, height = authored.tile_size(face['uv'], atlas.size,
                                           [positions[i] for i in face['idx']],
                                           units_per_texel, max_tile)
        clut, pixels = authored.quantize(
            authored.bake(atlas, face['uv'], width, height), width, height)
        key = (width, height, clut, pixels)
        if key not in tile_ids:
            offset = len(tiles) * 4096      # synthetic id; only identity matters
            tile_ids[key] = offset
            tiles[offset] = dict(index=len(tiles), width=width, height=height,
                                 clut=clut, pixels=pixels)
        face['tex_off'] = tile_ids[key]

    vertices = [tuple(int(round(v)) for v in p) for p in positions]
    print('atlas   : %s %dx%d' % (atlas_path.name, atlas.size[0], atlas.size[1]))
    print('source  : %d vertices, %d faces -> %d polygons, %d unique tiles'
          % (len(positions), len(raw_faces), len(faces), len(tiles)))
    return vertices, faces, tiles


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obj', type=pathlib.Path,
                        default=ROOT / 'levels/kokiri/assets/static'
                                       '/kokiriforest-newGameCs.obj')
    parser.add_argument('--atlas', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path,
                        default=ROOT / 'build/generated')
    parser.add_argument('--scene', type=int, default=CUTSCENE_SCENE_ID)
    # Same defaults the authored forest import is built with.
    parser.add_argument('--units-per-texel', type=float, default=10.0)
    # 16, not the authored forest's 32: at 32 this mesh wants 477 KB of VDP1
    # texture VRAM and the whole area is 445 KB. Halving the tile edge quarters
    # the pixels and brings it to 226 KB, which leaves room for Link and the
    # overlays that stay resident alongside it.
    parser.add_argument('--max-tile', type=int, default=16)
    parser.add_argument('--cull', action='store_true',
                        help='emit Single_Plane (backface culling) faces')
    args = parser.parse_args()

    if not args.obj.is_file():
        raise SystemExit('cutscene mesh not found: %s' % args.obj)
    args.out.mkdir(parents=True, exist_ok=True)

    vertices, faces, tiles = convert(args.obj, args.atlas,
                                     args.units_per_texel, args.max_tile,
                                     args.cull)

    # One object: the bank is drawn whole, with no per-room visibility to
    # resolve, so every face belongs to the same bounding box.
    records = [dict(object=0, indices=list(face['idx'])) for face in faces]
    mesh, pixels, bounds = rooms.pack_room(vertices, faces, tiles, records,
                                           face_normal)

    (args.out / asset_names.room_asset(args.scene, 0, 'MSH')).write_bytes(mesh)
    (args.out / asset_names.room_asset(args.scene, 0, 'TEX')).write_bytes(pixels)

    summary = dict(scene=args.scene, vertices=len(vertices),
                   polygons=len(faces), tiles=len(tiles),
                   pixel_bytes=len(pixels), objects=len(bounds),
                   clut_bytes=len(tiles) * 32, source=args.obj.name)
    # Read by build_room_scene.py when it computes the shared bank capacities.
    # Without this the compiled maximums come from the ROM rooms alone and a
    # larger cutscene bank would be refused at load.
    (args.out / 'cutscene_bank.json').write_text(
        json.dumps(summary, indent=2) + '\n')

    print('bank    : S%dR0  %d polygons  %d vertices  %d tiles'
          % (args.scene, len(faces), len(vertices), len(tiles)))
    print('vram    : %d pixel + %d CLUT = %d bytes'
          % (len(pixels), summary['clut_bytes'],
             len(pixels) + summary['clut_bytes']))


if __name__ == '__main__':
    main()
