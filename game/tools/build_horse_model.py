#!/usr/bin/env python3
"""Bake Epona's skin-animated mesh into per-frame vertex snapshots.

The horse is not a normal skeleton. Ganondorf, Zelda and Impa hang display
lists off limbs and the runtime poses the limbs; Epona uses OoT's Skin system,
where the mesh is one soft surface and every vertex is a weighted blend of
several limbs. There is no per-limb display list to pose.

Rather than port that blend to the SH-2, it is evaluated here, once, and what
ships is a table of vertex positions per frame. The runtime then has no
skinning at all -- it swaps a POINT table and draws. The gallop is a short
loop, so the table is small, and this is the cheapest possible runtime for the
most expensive kind of model.

How a position is found, from z_skin.c:56 (Skin_ApplyLimbModifications):

    one transform    the limb matrix times the stored offset
    many transforms  the weighted sum of those, weight = scale / 100

and each modif produces ONE position that every vertex listed in it shares --
the duplicates exist for UV seams, not for different places in space
(z_skin.c:17, Skin_UpdateVertices writes the same pos to each).

Offline tool: floating point is fine here.
"""
import argparse
import pathlib
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_link_model as link                                 # noqa: E402
import build_actor_model as actor                               # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

OBJECT = 'object_horse'
SKIN_LIMB_TYPE_ANIMATED = 4
SKIN_LIMB_TYPE_NORMAL = 11

SKIN_LIMB = '>hhhBBiI'          # jointPos, child, sibling, segmentType, segment
SKIN_LIMB_SIZE = 0x10

# The ride is a gallop; the others are kept selectable for later shots.
DEFAULT_CLIP = 'gEponaGallopingAnim'


def read_spec(oot):
    path = oot / 'assets/xml/objects' / (OBJECT + '.xml')
    if not path.is_file():
        raise SystemExit('object XML not found: %s' % path)
    root = ET.parse(path).getroot()
    skeleton, animations = None, {}
    for node in root.iter():
        offset = node.attrib.get('Offset')
        if offset is None:
            continue
        if node.tag == 'Skeleton' and skeleton is None:
            skeleton = int(offset, 16)
        elif node.tag == 'Animation':
            animations[node.attrib.get('Name', '')] = int(offset, 16)
    if skeleton is None:
        raise SystemExit('no skeleton in %s' % path)
    return skeleton, animations


def read_limbs(data, offset):
    """SkinLimbs off a SkeletonHeader."""
    segment, limb_count = struct.unpack_from('>IB', data, offset)
    table = segment & 0xFFFFFF
    pointers = struct.unpack_from('>%dI' % limb_count, data, table)
    limbs = []
    for pointer in pointers:
        x, y, z, child, sibling, kind, seg = struct.unpack_from(
            SKIN_LIMB, data, pointer & 0xFFFFFF)
        limbs.append(dict(pos=(x, y, z), child=child, sibling=sibling,
                          kind=kind, segment=seg & 0xFFFFFF,
                          near=0, far=0))
    return limbs


def read_modifs(data, limb):
    """The animated limb's blend recipe: one entry per skinned point."""
    total, count, modifications, dlist = struct.unpack_from(
        '>HHII', data, limb['segment'])
    modifications &= 0xFFFFFF
    entries = []
    for i in range(count):
        vtx_count, transform_count, unk4, vertices, transforms = \
            struct.unpack_from('>HHHxxII', data, modifications + i * 0x10)
        vertices &= 0xFFFFFF
        transforms &= 0xFFFFFF
        indices = [struct.unpack_from('>H', data, vertices + v * 0xA)[0]
                   for v in range(vtx_count)]
        blend = []
        for t in range(transform_count):
            limb_index, x, y, z, scale = struct.unpack_from(
                '>BxhhhB', data, transforms + t * 0xA)
            blend.append((limb_index, (x, y, z), scale))
        entries.append(dict(indices=indices, blend=blend))
    return total, entries, dlist & 0xFFFFFF


def limb_matrices(limbs, rotations, root):
    """One matrix and origin per limb, as gSkinLimbMatrices holds."""
    link.LIMB_NONE = 0xFF
    link.HEAD_LIMB = -1
    placed = link.walk_skeleton(limbs, rotations, root)
    return {index: (matrix, origin) for index, matrix, origin, _ in placed}


# En_Horse draws at Actor_SetScale(0.01) (z_en_horse.c:840), so the object's
# own units are a hundred times the world's. Applied here, once, rather than
# leaving a horse that stands seventy times taller than Link.
ACTOR_SCALE = 0.01


def bake_frame(modifs, matrices, total):
    """Every vertex position for one frame, in world units."""
    points = [(0, 0, 0)] * total
    for modif in modifs:
        blend = modif['blend']
        if len(blend) == 1:
            limb_index, offset, _ = blend[0]
            matrix, origin = matrices[limb_index]
            point = link.transform(matrix, origin, offset)
        else:
            point = [0.0, 0.0, 0.0]
            for limb_index, offset, scale in blend:
                matrix, origin = matrices[limb_index]
                moved = link.transform(matrix, origin, offset)
                weight = scale * 0.01
                for k in range(3):
                    point[k] += moved[k] * weight
            point = tuple(point)
        for index in modif['indices']:
            if index < total:
                points[index] = tuple(int(round(v * ACTOR_SCALE))
                                      for v in point)
    return points


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--clip', default=DEFAULT_CLIP)
    parser.add_argument('--frames', type=int, default=12)
    parser.add_argument('--stride', type=int, default=2)
    args = parser.parse_args()

    data = link.read_object(args.oot, OBJECT, args.rom_dir)
    skeleton, animations = read_spec(args.oot)
    if args.clip not in animations:
        raise SystemExit('%s: unknown clip; have %s'
                         % (args.clip, ', '.join(sorted(animations))))
    limbs = read_limbs(data, skeleton)
    animated = [i for i, l in enumerate(limbs)
                if l['kind'] == SKIN_LIMB_TYPE_ANIMATED and l['segment']]
    print('horse   : skeleton %#x, %d limbs, %d animated, %d clips'
          % (skeleton, len(limbs), len(animated), len(animations)))

    total_points = 0
    baked = []
    for limb_index in animated:
        total, modifs, dlist = read_modifs(data, limbs[limb_index])
        total_points += total
        baked.append((limb_index, total, modifs, dlist))
        print('  limb %2d: %d vertices over %d blends, dlist %#x'
              % (limb_index, total, len(modifs), dlist))

    frames_total, root, rotations = actor.read_animation(
        data, animations[args.clip], len(limbs), 0)
    print('clip    : %s, %d frames, sampling %d every %d'
          % (args.clip, frames_total, args.frames, args.stride))

    extent = [[None, None] for _ in range(3)]
    moved = 0
    previous = None
    for step in range(args.frames):
        frame = min(frames_total - 1, step * args.stride)
        _, root, rotations = actor.read_animation(
            data, animations[args.clip], len(limbs), frame)
        matrices = limb_matrices(limbs, rotations, root)
        for limb_index, total, modifs, _ in baked:
            points = bake_frame(modifs, matrices, total)
            if previous is not None and points != previous:
                moved += 1
            previous = points
            for p in points:
                for k in range(3):
                    low, high = extent[k]
                    extent[k] = [p[k] if low is None else min(low, p[k]),
                                 p[k] if high is None else max(high, p[k])]
    print('baked   : %d vertices per frame, %d frames, %d bytes'
          % (total_points, args.frames, total_points * args.frames * 6))
    print('extent  : %s' % [tuple(e) for e in extent])
    print('motion  : %d of %d frame snapshots differ from the one before'
          % (moved, args.frames * len(baked)))


if __name__ == '__main__':
    main()
