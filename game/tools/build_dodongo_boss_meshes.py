"""Inventory and bake every real King Dodongo skeleton display list.

Boss poses remain in source SkelAnime. Each rigid limb is a local-space Saturn
mesh selected by the existing core display-list key; no pose approximation.
The converter fails if one limb is missing. Original N64 models remain offline
inputs and flat character body / detailed face materials remain the policy.
"""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import build_actor_model as actor
import build_link_model as link

OBJECT = 'object_kingdodongo'
SKELETON = 'object_kingdodongo_Skel_01B310'


def source_offset(node):
    """The US1.2 source names resolve XML's later relative-version entries."""
    offset = node.attrib.get('Offset', '')
    if offset.startswith('0x'):
        return int(offset, 16)
    match = re.fullmatch(r'object_kingdodongo_\w+_([0-9A-Fa-f]{6})', node.attrib['Name'])
    if not match:
        raise ValueError('King Dodongo entry needs an explicit source offset: ' + node.attrib['Name'])
    # These source names retain PAL offsets after the title card. US1.2's
    # XML selects 128x80 IA8 instead of PAL's 128x120, removing 5120 bytes.
    # read_object verifies the US1.2 ROM digest before these offsets are used.
    return int(match[1], 16) - 128 * (120 - 80)


def limb_inventory(oot, rom_dir):
    xml = ET.parse(oot / 'assets/xml/objects' / (OBJECT + '.xml'))
    data = link.read_object(oot, OBJECT, rom_dir)
    skeleton = next(n for n in xml.iter('Skeleton') if n.attrib['Name'] == SKELETON)
    table, count = actor.read_skeleton(data, source_offset(skeleton))
    if count != 48:
        raise ValueError('King Dodongo source skeleton changed: %d limbs' % count)
    limbs, _ = actor.read_limbs(data, table, count)
    symbols = {source_offset(n): n.attrib['Name'] for n in xml.iter('DList')}
    result = defaultdict(list)
    for i, limb in enumerate(limbs):
        address = limb['near']
        if not address:
            continue
        if address >> 24 != 6 or (address & 0xffffff) not in symbols:
            raise ValueError('King Dodongo limb %d has unregistered display list %#x' % (i + 1, address))
        result[symbols[address & 0xffffff]].append(i + 1)
    return dict(result)


def bake_limb(oot, rom_dir, symbol, source_limbs, destination):
    xml_path = oot / 'assets/xml/objects' / (OBJECT + '.xml')
    xml = ET.parse(xml_path)
    node = next(n for n in xml.iter('DList') if n.attrib['Name'] == symbol)
    lists = link.LimbLists(b'', b'')
    lists.segments = {6: link.read_object(oot, OBJECT, rom_dir),
                      8: struct.pack('>II', 0xDF000000, 0)}
    lists.texture_on = True
    lists.scale = (65535 / 65536, 65535 / 65536)
    lists.geom = 0x220405  # source Gfx_SetupDL_25Opa
    lists.current_limb = 0
    lists.matrix_limbs = []
    before = link.LimbLists.unresolved
    lists.walk(0x06000000 | source_offset(node))
    if link.LimbLists.unresolved != before or not lists.faces:
        raise ValueError('King Dodongo limb unresolved/empty: ' + symbol)
    # Source PostLimbDraw's head/mouth lives on limb6, adjacent jaw on limb7.
    head = any(i in (6, 7) for i in source_limbs)
    for face in lists.faces:
        face['limb'] = 0
        face['transparent'] = True
    link.character_textures.mark_faces(lists.faces, xml_path, 0 if head else -1)
    link.apply_primitive_colour(lists.faces)
    points, tiles, _, _ = link.write_model(lists.faces, destination, character=True)
    return dict(symbol=symbol, limbs=source_limbs, vertices=len(points),
                polygons=len(lists.faces), tiles=len(tiles), bytes=destination.stat().st_size)


def build(oot, rom_dir, output, core):
    output.mkdir(parents=True, exist_ok=True)
    placeholders = None
    for path in (core / 'objects').glob('O*_ph.txt'):
        names = path.read_text().split()
        if names[0] == OBJECT:
            placeholders = names[1:]
            oid = int(path.stem[1:4], 16)
            break
    if placeholders is None:
        raise ValueError('King Dodongo object must be imported before mesh bake')
    inventory = limb_inventory(oot, rom_dir)
    rows = []
    for symbol, limbs in inventory.items():
        if symbol not in placeholders:
            raise ValueError('King Dodongo limb lacks runtime display-list key: ' + symbol)
        index = placeholders.index(symbol)
        if index > 255:
            raise ValueError('King Dodongo display-list key exceeds filename space')
        name = 'Q%03X%02X.MSH' % (oid, index)
        row = bake_limb(oot, rom_dir, symbol, limbs, output / name)
        rows.append(dict(row, kind=1, object=oid, index=index, file=name))
    # Report beside the core import, never in disc staging (GFS 8.3 names).
    (core / 'kingdodongo_meshes.json').write_text(json.dumps(rows, indent=2) + '\n')
    print('King Dodongo: %d real limb meshes, %d polygons, %d bytes' %
          (len(rows), sum(r['polygons'] for r in rows), sum(r['bytes'] for r in rows)))
    return rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/dodongo-route/boss-meshes'))
    parser.add_argument('--core', type=Path, default=Path('build/oot-core'))
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out, args.core)
