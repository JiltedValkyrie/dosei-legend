"""Bake only gameplay attachment points; no runtime poses or skeleton data."""
import argparse
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import build_actor_model as actor
import build_link_model as link
import field_enemy_sources as field

# Source limbIndex is one-based. Points are in source bone coordinates.
ANCHORS = {
    'object_skb': ((15, (0, 0, 0)), (1, (0, 0, 0))),
    'object_peehat': ((3, (-1000, 0, 0)),),
    'object_po_field': ((7, (0, 0, 0)),),
}


def build(oot, rom_dir, output, anchors=None, sources=None, root_offsets=None):
    anchors = ANCHORS if anchors is None else anchors
    sources = field.SOURCES if sources is None else sources
    source = '\n'.join((oot / path).read_text(encoding='utf-8') for path in sources)
    lines = ['/* Generated gameplay points only: one sample per animation frame. */']
    rows = []
    for obj in anchors:
        lines.append(f'#include "assets/objects/{obj}/{obj}.h"')
        root = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
        data = link.read_object(oot, obj, rom_dir)
        skels = list(root.iter('Skeleton'))
        if len(skels) != 1:
            raise ValueError(f'{obj}: expected one skeleton')
        table, count = actor.read_skeleton(data, int(skels[0].attrib['Offset'], 16))
        limbs, _ = actor.read_limbs(data, table, count)
        for anim in root.iter('Animation'):
            name = anim.attrib['Name']
            if not re.search(r'\b' + name + r'\b', source):
                continue
            off = int(anim.attrib['Offset'], 16)
            frames = struct.unpack_from('>h', data, off)[0]
            values = []
            for frame in range(frames):
                _, translation, rotations = actor.read_animation(data, off, count, frame)
                if root_offsets and obj in root_offsets:
                    translation = tuple(a+b for a, b in zip(translation, root_offsets[obj]))
                poses = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rotations, translation)}
                for limb, point in anchors[obj]:
                    coords = tuple(round(v) for v in link.transform(*poses[limb - 1], point))
                    if any(v < -32768 or v > 32767 for v in coords):
                        raise ValueError(f'{name}: anchor exceeds s16')
                    values.extend(coords)
            lines.append(f'static const s16 points_{name}[] = {{' + ','.join(map(str, values)) + '};')
            rows.append(f'    {{ &{name}, {frames}, {len(anchors[obj])}, points_{name} }},')
    lines += ['static const FieldAnchorClip field_anchor_clips[] = {', *rows, '};']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n')
    print(f'Gameplay anchors: {len(rows)} clips, source-frame attachment points only')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', required=True)
    parser.add_argument('--out', type=Path, default=Path('build/oot-core/field_anchors.inc'))
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out)
