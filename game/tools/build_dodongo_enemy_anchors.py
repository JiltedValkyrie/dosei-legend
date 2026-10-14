"""Bake bounded gameplay contacts, never a runtime skeleton or bone track.

Recipes name only source collision vertices, bomb mouths, feet and ice-effect
points. Sparse clip samples interpolate in 32-bit model coordinates; attack
windows retain every source frame. Bosses are deliberately absent.
"""
import argparse
import json
import math
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import build_actor_model as actor
import build_link_model as link
from dodongo_enemy_sources import SPRITE_SOURCES

# Source limb indices are one-based. Baby head is read in OverrideLimbDraw,
# before applying limb 4's transform, so its parent transform is the source.
ANCHORS = {
    # Claws, blocking head/chest and weak tail, from EnWf_PostLimbDraw.
    'object_wf': ((15,(0,0,0)), (21,(0,0,0)), (17,(800,0,0)),
                  (12,(0,0,0)), (6,(1200,0,0))),
    'object_vm': ((2, (0, 0, 0)),),
    'object_st': (
        *((1, p) for p in ((1400, -2600, -800), (1400, -1600, 0),
                           (-1400, -2600, -800), (-1400, -1600, 0), (0, 0, -600))),
        (5, (0, 0, 0)), (2, (0, -300, 0)),
    ),
    'object_dodojr': ((-4, (480, 620, 0)),),
    'object_am': tuple((1, p) for p in ((-2500, 0, 0), (2500, 7000, 0),
                                      (-2500, 0, 4000), (2500, 7000, 4000))),
    'object_dodongo': (
        *((limb, (0, 0, 0)) for limb in (15, 14, 13, 21, 28, 6)),
        *((7, p) for p in ((-300, -2500, 0), (-300, 1200, -2700), (3000, 1200, 0),
                           (-300, -2500, 0), (-300, 1200, 2700), (3000, 1200, 0),
                           (-600, 1200, -2800), (-600, 1200, 2800), (3000, 1200, 0),
                           (1800, 1200, 0), (1500, 300, 0))),
        # Source flame quad, EnDodongo_UpdateQuad: frame-dependent x offset.
        *((2, p) for p in ((-1000, -200, 1500), (-1000, -1500, 0),
                           (0, 0, 0), (-1000, -200, -1500))),
    ),
    'object_zf': (
        *((15, p) for p in ((-600, -3000, 1000), (0, 1500, 0),
                            (1500, -3000, 0), (-600, -3000, -1000))),
    ),
}

# Cosmetic feet and ice puffs use one neutral semantic layout. They never
# affect Lizalfos's cylinder damage or sword windows; no pose stream is needed.
ZF_PASSIVE = ((45, (300, 0, 0)), (38, (300, 0, 0)),
              *((limb, (0, 0, 0)) for limb in (9, 10, 25, 16, 23, 48, 14, 39, 43)))


def sample_frames(frames, cap=8, extra=()):
    if frames < 1:
        raise ValueError('animation has no frames')
    return sorted({i * (frames - 1) // (min(frames, cap) - 1)
                   for i in range(min(frames, cap))} | {f for f in extra if 0 <= f < frames}) if frames > 1 else [0]


def parent_map(limbs):
    parents = {}
    def visit(index, parent):
        while index != 255:
            parents[index] = parent
            visit(limbs[index]['child'], index)
            index = limbs[index]['sibling']
    visit(0, None)
    return parents


def refine_samples(full, samples, tolerance=250):
    """Keep coordinates within 2.5 units at the usual actor scale (0.01).

    Only gameplay points are refined, never joint rotations. Every extra sample
    has a measured contact error reason and is counted in the scene budget.
    """
    while True:
        worst_error, worst_frame = 0, None
        for lower, upper in zip(samples, samples[1:]):
            for frame in range(lower + 1, upper):
                for index, actual in enumerate(full[frame]):
                    estimate = full[lower][index] + (full[upper][index] - full[lower][index]) * (
                        frame - lower) / (upper - lower)
                    error = abs(actual - estimate)
                    if error > worst_error:
                        worst_error, worst_frame = error, frame
        if worst_error <= tolerance:
            return samples, worst_error
        samples = sorted(samples + [worst_frame])


def frame_points(obj, limbs, parents, translation, rotations, frame):
    poses = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rotations, translation)}
    values = []
    for index, (limb, original) in enumerate(ANCHORS[obj]):
        point = original
        if obj == 'object_dodongo' and index in (17, 18, 20):
            point = (point[0] - math.sin((frame - 28) * 0.08) * 5500, point[1], point[2])
        bone = limb - 1 if limb > 0 else parents[-limb - 1]
        coords = point if bone is None else link.transform(*poses[bone], point)
        coords = tuple(round(v) for v in coords)
        if any(v < -32768 or v > 32767 for v in coords):
            raise ValueError(f'{obj} frame {frame}: semantic point exceeds s16')
        values.extend(coords)
    return values


def build(oot, rom_dir, output):
    source = '\n'.join((oot / p).read_text(encoding='utf-8') for p in SPRITE_SOURCES)
    lines = ['/* Generated offline semantic contacts; no bone or pose payload. */']
    rows, report = [], []
    byte_count = 0
    shared = {}
    for obj in ANCHORS:
        lines.append(f'#include "assets/objects/{obj}/{obj}.h"')
        root = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
        data = link.read_object(oot, obj, rom_dir)
        for skeleton in root.iter('Skeleton'):
            skel_name = skeleton.attrib['Name']
            if not re.search(r'\b' + skel_name + r'\b', source):
                continue
            table, count = actor.read_skeleton(data, int(skeleton.attrib['Offset'], 16))
            limbs, _ = actor.read_limbs(data, table, count)
            parents = parent_map(limbs)
            for animation in root.iter('Animation'):
                name = animation.attrib['Name']
                if not re.search(r'\b' + name + r'\b', source):
                    continue
                if obj == 'object_zf' and name != 'gZfSlashAnim':
                    if name == 'gZfIdleAnim' and skel_name == 'gLizalfosSkel':
                        offset = int(animation.attrib['Offset'], 16)
                        _, translation, rotations = actor.read_animation(data, offset, count, 0)
                        poses = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rotations, translation)}
                        values = [round(v) for limb, point in ZF_PASSIVE
                                  for v in link.transform(*poses[limb - 1], point)]
                        lines.append('static const s16 dodongo_zf_passive[][3] = {' + ','.join(
                            '{' + ','.join(map(str, values[i:i+3])) + '}' for i in range(0, len(values), 3)) + '};')
                        byte_count += len(values) * 2
                    continue
                offset = int(animation.attrib['Offset'], 16)
                frames = struct.unpack_from('>h', data, offset)[0]
                # Source attack registration is 29<frame<43 / 14<=frame<=20.
                extra = (range(29, 44) if name == 'gDodongoBreatheFireAnim' else
                         range(14, 21) if name == 'gZfSlashAnim' else ())
                samples = sample_frames(frames, extra=extra)
                full = []
                for frame in range(frames):
                    _, translation, rotations = actor.read_animation(data, offset, count, frame)
                    points = frame_points(obj, limbs, parents, translation, rotations, frame)
                    full.append(points)
                samples, worst_error = refine_samples(full, samples)
                values = [v for frame in samples for v in full[frame]]
                symbol = f'points_{skel_name}_{name}'
                key = (tuple(samples), tuple(values))
                cost = 0
                if key in shared:
                    symbol = shared[key]
                else:
                    shared[key] = symbol
                    lines.append(f'static const u16 {symbol}_frames[] = {{' + ','.join(map(str, samples)) + '};')
                    lines.append(f'static const s16 {symbol}[] = {{' + ','.join(map(str, values)) + '};')
                    cost = len(samples) * 2 + len(values) * 2
                rows.append(f'    {{ &{name}, &{skel_name}, {frames}, {len(samples)}, '
                            f'{len(ANCHORS[obj])}, {symbol}_frames, {symbol} }},')
                byte_count += cost
                report.append(dict(object=obj, skeleton=skel_name, animation=name, frames=frames,
                                   samples=len(samples), points=len(ANCHORS[obj]), bytes=cost,
                                   max_model_coordinate_error=round(worst_error, 2)))
    lines += ['static const DodongoAnchorClip dodongo_anchor_clips[] = {', *rows, '};']
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text('\n'.join(lines) + '\n')
    output.with_suffix('.json').write_text(json.dumps(dict(sample_bytes=byte_count, clips=report), indent=2) + '\n')
    print(f'Dodongo contacts: {len(rows)} clips, {byte_count} sample bytes; boss poses untouched')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/oot-core/dodongo_anchors.inc'))
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out)
