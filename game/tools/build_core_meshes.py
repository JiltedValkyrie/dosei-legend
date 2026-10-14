#!/usr/bin/env python3
"""Prebuilt Saturn meshes for the oot-core Phase 2 draw shim.

For every actor in oot_core_import.GENERIC_DRAW, find the placeholder display
lists its source names (gameplay_keep / field / dungeon keep placeholders in
keep_ph.txt, data-object placeholders in objects/O<id>_ph.txt) and convert each
DList with build_shop_props.static_mesh at scale 1: the draw item's transform
carries the actor's scale (oot_core_draw.cpp). Output names follow the draw
item key:

    K<index hex3>.MSH          keep placeholder <index>
    Q<object hex3><index hex2>.MSH   object <object>, placeholder <index>

and build/oot-core/generic_meshes.h lists them for the blob (mesh_list).
A DL the converter cannot handle is reported and left out (not drawn).

Offline tool: floating point is fine here.
"""
import argparse
import importlib.util
import pathlib
import re
import sys
import xml.etree.ElementTree as ET
import child_route_props
import child_minigame_sources
import child_legend_sources

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

GAME = HERE.parent


def load_importer():
    spec = importlib.util.spec_from_file_location('oot_core_import', HERE / 'oot_core_import.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def xml_dlists(oot):
    """DList name -> (xml object name, offset)."""
    out = {}
    for xml in (oot / 'assets' / 'xml' / 'objects').glob('*.xml'):
        try:
            root = ET.parse(xml).getroot()
        except ET.ParseError:
            continue
        for node in root.iter('DList'):
            try:
                if xml.stem == 'object_kingdodongo':
                    from build_dodongo_boss_meshes import source_offset
                    offset = source_offset(node)
                else:
                    offset = int(node.attrib['Offset'], 16)
                out.setdefault(node.attrib['Name'], (xml.stem, offset))
            except (KeyError, ValueError):
                continue  # version-conditional offsets: not a fixed DList
    from child_legend_keep import DLISTS
    out.update({name:('gameplay_keep',0) for name in DLISTS})
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, required=True)
    ap.add_argument('--rom-dir', required=True)
    ap.add_argument('--out', type=pathlib.Path, default=GAME / 'build' / 'cd')
    ap.add_argument('--core', type=pathlib.Path, default=GAME / 'build' / 'oot-core')
    args = ap.parse_args()

    imp = load_importer()
    keep = (args.core / 'keep_ph.txt').read_text().split()
    objects = {}  # object id -> (object name, [placeholder names])
    for f in sorted((args.core / 'objects').glob('O*_ph.txt')):
        lines = f.read_text().split()
        objects[int(f.stem[1:4], 16)] = (lines[0], lines[1:])
    dlists = xml_dlists(args.oot)

    import build_shop_props as props

    wanted = []  # (kind, object id, index, symbol, xml object)
    for actor, source in imp.GENERIC_DRAW_SOURCES:
        if actor == 'ACTOR_BOSS_DODONGO':
            # Its geometry is referenced by skeleton limbs, not source text.
            # A dedicated strict bake below covers every live limb.
            continue
        text = (args.oot / source).read_text(encoding='utf-8', errors='replace')
        text = child_legend_sources.adapt(source, text)
        text = child_minigame_sources.adapt(source, text)
        names = set(re.findall(r'\b[A-Za-z_]\w*\b', text))
        for i, n in enumerate(keep):
            if n in names and n in dlists:
                wanted.append((0, 0, i, n, dlists[n][0], actor))
        for oid, (oname, phs) in objects.items():
            for i, n in enumerate(phs):
                if n in names and n in dlists:
                    wanted.append((1, oid, i, n, oname, actor))
    built, rows, problems = {}, [], []
    for kind, oid, index, symbol, obj, actor in wanted:
        key = (kind, oid, index)
        if key in built:
            if built[key]:
                rows.append(f'    {{ {kind}, 0x{oid:03X}, {index}, {actor} }}, /* {symbol} */')
            continue
        built[key] = False
        name = ('K%03X.MSH' % index) if kind == 0 else ('Q%03X%02X.MSH' % (oid, index))
        if index > 0xFF and kind == 1:
            problems.append(f'{symbol}: object placeholder index {index} over 0xFF')
            continue
        try:
            if symbol == 'gWarpPortalDL':
                from build_child_warp_mesh import bake as bake_warp
                bake_warp(args.oot, args.rom_dir, args.out / name)
            elif actor == 'ACTOR_DEMO_KANKYO' and symbol == 'gEffDustDL':
                props.static_mesh(args.oot, args.rom_dir, obj, symbol, args.out/name,
                                  cutout=True, texture8='gDust5Tex')
            else:
                props.static_mesh(args.oot, args.rom_dir, obj, symbol, args.out / name, 1.0, cutout=True)
        except Exception as exc:  # converter limits: report, leave out
            if actor in ('ACTOR_BOSS_DODONGO', 'ACTOR_BG_BREAKWALL',
                         'ACTOR_DOOR_WARP1', 'ACTOR_ITEM_B_HEART', 'ACTOR_EN_BOMBF',
                         'ACTOR_DEMO_EFFECT', 'ACTOR_DEMO_KANKYO', 'ACTOR_EN_DY_EXTRA') or actor in dict(child_route_props.DRAW_SOURCES) or actor in dict(child_minigame_sources.DRAW_SOURCES):
                raise ValueError('Required boss arena mesh failed: ' + symbol) from exc
            problems.append(f'{symbol} ({obj}): {exc!r}')
            continue
        built[key] = True
        rows.append(f'    {{ {kind}, 0x{oid:03X}, {index}, {actor} }}, /* {symbol} -> {name} */')
    if 'ACTOR_BOSS_DODONGO' in imp.GENERIC_DRAW:
        import build_dodongo_boss_meshes as boss
        for entry in boss.build(args.oot, args.rom_dir, args.out, args.core):
            kind, oid, index = (entry[k] for k in ('kind', 'object', 'index'))
            built[(kind, oid, index)] = True
            rows.append(f'    {{ {kind}, 0x{oid:03X}, {index}, ACTOR_BOSS_DODONGO }}, '
                        f'/* {entry["symbol"]} -> {entry["file"]} */')
    header = ['/* Generated by tools/build_core_meshes.py. Do not edit.',
              ' * { kind, object, index, actor using it } */']
    header += rows if rows else ['    { 0xFFFF, 0, 0, -1 }, /* none */']
    (args.core / 'generic_meshes.h').write_text('\n'.join(header) + '\n')
    print(f'core meshes: {sum(built.values())} built, {len(problems)} left out')
    for p in problems:
        print('  left out:', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
