#!/usr/bin/env python3
"""Bake original shop stock GetItem draw recipes, never runtime meshes."""
import argparse
import json
from pathlib import Path

import build_npc_sprites as sprites
import child_route_shops as shops
import oot_core_import as imp


def header(oot):
    recipes = shops.stock_sprite_keys(oot)
    lines = ['/* Generated from source EnGirlA and z_draw; tools/build_shop_sprites.py. */',
             '#ifndef CHILD_ROUTE_SHOP_ITEMS_H', '#define CHILD_ROUTE_SHOP_ITEMS_H',
             '#include "item.h"']
    for obj in sorted(set(row[0] for row in recipes.values())):
        lines.append(f'#include "assets/objects/{obj}/{obj}.h"')
    lines += ['', 'static u32 ChildRouteShop_ItemKey(s16 gid) {', '    switch (gid) {']
    for gid, (_obj, symbol, variant, _lists) in recipes.items():
        lines.append(f'        case {gid}: return (u32)(uintptr_t){symbol} | ({variant}u << 20);')
    lines += ['        default: return 0;', '    }', '}', '#endif', '']
    return '\n'.join(lines)


def bake(oot, rom_dir, work, out, start=0, only_objects=None):
    _enums, object_ids = imp.object_ids(oot)
    keep = sprites.link.read_object(oot, 'gameplay_keep', rom_dir)
    recipes = shops.stock_sprite_keys(oot)
    groups = {}
    for gid, (obj, base, variant, lists) in recipes.items():
        if only_objects is not None and obj not in only_objects:
            continue
        data = sprites.link.read_object(oot, obj, rom_dir)
        binary = work / (gid + '.BIN')
        _owners, local = sprites.static_skin(obj, data, oot / 'assets/xml/objects' / (obj + '.xml'),
                                            keep, lists, binary)
        faces, _, _ = sprites.read_model(binary, None)
        # Source EnGirlA actor scale is 0.25. Bake at that scale so small stock
        # gets useful cels; the view's scale conversion uses this same base.
        poses = [[tuple(v * .25 for v in p) for p in local]]
        groups.setdefault(obj, []).append((gid, base, variant, faces, poses))
    rows = []
    for obj, clips in groups.items():
        layout = sprites.layout_of([clip[4] for clip in clips], sprites.GENERIC_HEIGHT)
        for gid, base, variant, faces, poses in clips:
            index = (start + len(rows)) % 256
            dest = out / ('G%03X%02X.SPR' % (object_ids[obj], index))
            sprites.write_sprite(faces, poses, [0], dest, work / (gid + '.png'), layout, 1)
            rows.append((object_ids[obj], 0, base, index, base, variant))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/child-route-shops'))
    parser.add_argument('--header', type=Path)
    parser.add_argument('--keepers', action='store_true')
    args = parser.parse_args()
    work, out = args.out / 'sprite-work', args.out / 'sprites'
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    if args.header:
        args.header.write_text(header(args.oot))
    rows = []
    if args.keepers:
        sprites.bake_generic(args.oot, args.oot / 'baseroms/ntsc-1.2', work, out, args.out,
                             only_objects=shops.SPRITE_OBJECTS, extra_sources=[shops.KEEPER_SOURCE],
                             extra_objects=shops.SPRITE_OBJECTS, extra_animation_objects=shops.ANIMATION_OBJECTS)
        rows = json.loads((args.out / 'generic_sprites.json').read_text())
    rows += bake(args.oot, args.oot / 'baseroms/ntsc-1.2', work, out, len(rows))
    (args.out / 'generic_sprites.json').write_text(json.dumps(rows) + '\n')
    print('shop sprites:', len(rows), 'sheets,',
          sum((out / ('G%03X%02X.SPR' % (row[0], row[3]))).stat().st_size for row in rows), 'bytes')


if __name__ == '__main__':
    main()
