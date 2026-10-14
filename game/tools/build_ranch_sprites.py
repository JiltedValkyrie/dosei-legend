#!/usr/bin/env python3
"""Bake source child/normal horse sprites and one semantic head contact."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import build_actor_model as actor
import build_horse_model as horse
import build_horse_sprites as horses
import build_link_model as link
import build_npc_sprites as sprite
import oot_core_import as imp
import ranch_sources as ranch

GAME = Path(__file__).resolve().parents[1]


def recipe(oot, rom_dir, index):
    obj = ranch.OBJECTS[index]
    data = link.read_object(oot, obj, rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
    skel = next(xml.iter('Skeleton'))
    source = (oot / ranch.SOURCES[index]).read_text(encoding='utf-8')
    names = re.findall(r'&([\w]+)', re.search(r'sAnimations\[\] = \{(.*?)\};', source, re.S)[1])
    offsets = {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in xml.iter('Animation')}
    return obj, data, xml, skel, [(name, offsets[name]) for name in names], .005 if index == 0 else .01


def anchors(oot, rom_dir=None):
    lines = ['/* Generated offline: one head contact, four samples per source clip. */']
    for index, tag in enumerate(('Child', 'Normal')):
        _, data, _, skel, animations, scale = recipe(oot, rom_dir, index)
        limbs = horse.read_limbs(data, int(skel.attrib['Offset'], 16))
        head = 13 if index == 0 else 11
        lines.append(f'static const s16 sRanch{tag}Head[][4][3] = {{')
        for name, offset in animations:
            length = actor.read_animation(data, offset, len(limbs), 0)[0]
            points = []
            for sample in range(4):
                _, root, rotation = actor.read_animation(data, offset, len(limbs), sample * length // 4)
                matrix, origin = horse.limb_matrices(limbs, rotation, root)[head]
                points.append(tuple(round(v * scale) for v in link.transform(matrix, origin, (0, 0, 0))))
            lines.append('    { ' + ', '.join('{ %d, %d, %d }' % p for p in points) + ' }, /* ' + name + ' */')
        lines.append('};')
    return '\n'.join(lines) + '\n'


def bake(oot, rom_dir, work, out, start_index=0, only_objects=None):
    rows = []
    for index, obj in enumerate(ranch.OBJECTS):
        if only_objects is not None and obj not in only_objects:
            continue
        _, data, xml, skel, animations, scale = recipe(oot, rom_dir, index)
        oid = imp.object_ids(oot)[1][obj]
        parsed, limbs, baked, owners, locals_ = horses.prepare_model(
            data, xml, int(skel.attrib['Offset'], 16), animations[0][1], scale,
            'normal', work / (obj + '.BIN'))
        clips = []
        for name, offset in animations:
            length = actor.read_animation(data, offset, len(limbs), 0)[0]
            if length < 1:
                raise ValueError(f'{name}: empty source clip')
            count = min(sprite.GENERIC_POSES, length)
            poses = [horses.pose_points(data, offset, limbs, n * length // count,
                                       baked, owners, locals_, scale) for n in range(count)]
            order = [min(count - 1, tick * count // length) for tick in range(length)]
            clips.append((name, poses, order))
        # One shared geometry/texel across all clips keeps the sprite slot
        # bounded even when the source switches to a rearing/jumping action.
        layout = sprite.layout_of([poses for _, poses, _ in clips], sprite.GENERIC_HEIGHT)
        for name, poses, order in clips:
            file_index = (start_index + len(rows)) % 256
            dest = out / f'G{oid:03X}{file_index:02X}.SPR'
            sprite.write_sprite(parsed, poses, order, dest, work / (dest.stem + '.png'),
                                layout, sprite.GENERIC_POSES)
            rows.append((oid, 0, name, file_index, skel.attrib['Name'], 0))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--out', type=Path, default=GAME / 'build/ranch-sprites')
    parser.add_argument('--anchors', type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    work = args.out / 'work'
    work.mkdir(exist_ok=True)
    if args.anchors:
        args.anchors.parent.mkdir(parents=True, exist_ok=True)
        args.anchors.write_text(anchors(args.oot))
    rows = bake(args.oot, None, work, args.out)
    (args.out / 'generic_sprites.json').write_text(json.dumps(rows) + '\n')
    print(f'{len(rows)} source horse clips, ' + str(sum((args.out / f'G{r[0]:03X}{r[3]:02X}.SPR').stat().st_size for r in rows)) + ' bytes')


if __name__ == '__main__':
    main()
