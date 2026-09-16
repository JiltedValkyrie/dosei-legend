#!/usr/bin/env python
"""Extract child Link's model from the US 1.2 ROM into the viewer's mesh format.

Reuses the scene pipeline: ../../shared/tools/build_kokiri_scene.py already
walks F3DEX display lists and bakes per-face 4bpp tiles with CLUTs, so this only
has to supply the skeleton and emit the same KFR1 container (with no collision).
build_sgl_scene.py then converts it exactly like FOREST.BIN.

Skeleton (object_link_child, segment 6):
  gLinkChildLimbs @ 0x2CF18 -- 21 pointers to LodLimb
  LodLimb = { Vec3s jointPos; u8 child; u8 sibling; Gfx* dList[2]; }  (16 bytes)
  dList[1] is the Far LOD, which is what we take: it is the low-poly variant and
  18 of the 21 limbs have one. All of them live in segment 6, so nothing from
  gameplay_keep is needed.

Pose: limbs are drawn in the bind pose, accumulating only jointPos down the
hierarchy with no rotations. Each limb's display list is authored in its own
local space, so this is the pose the vertices were modelled in.
"""

import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import struct
import sys

OOT_DEFAULT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
ROM_MD5 = '57a9719ad547c516342e1a15d5c28c3d'
OBJECT = 'object_link_child'

LIMB_TABLE = 0x2CF18
LIMB_COUNT = 21
LIMB_STRUCT = '>hhhBBII'       # jointPos, child, sibling, near, far
LIMB_NONE = 255

# gPlayerAnim_link_normal_waitF_typeA_20f in gameplay_keep: a standing idle.
IDLE_ANIMATION = 0x3200

KFR1_MAGIC = 0x4B465231

_TOOLS = pathlib.Path(__file__).resolve().parents[2] / 'shared' / 'tools'
sys.path.insert(0, str(_TOOLS))

import build_kokiri_scene as scene_tool  # noqa: E402
from extract_title_source import yaz0     # noqa: E402


def read_object(oot, name):
    config = oot / 'baseroms' / 'ntsc-1.2'
    roms = [p for p in config.glob('*.z64')
            if hashlib.md5(p.read_bytes()).hexdigest() == ROM_MD5]
    if len(roms) != 1:
        sys.exit('verified US 1.2 ROM (md5 %s) required in %s' % (ROM_MD5, config))
    rom = roms[0].read_bytes()
    dma = int(re.search(r'dmadata_start: (\w+)',
                        (config / 'config.yml').read_text())[1], 16)
    with (config / 'segments.csv').open() as f:
        for index, row in enumerate(csv.DictReader(f)):
            if row['Name'] != name:
                continue
            start, end, physical, packed = struct.unpack_from(
                '>4I', rom, dma + index * 16)
            data = (yaz0(rom[physical:packed]) if packed
                    else rom[physical:physical + end - start])
            if len(data) != end - start:
                sys.exit('%s: unpacked to %d bytes, expected %d'
                         % (name, len(data), end - start))
            return bytes(data)
    sys.exit('%s not found in segments.csv' % name)


def read_limbs(data):
    pointers = struct.unpack_from('>%dI' % LIMB_COUNT, data, LIMB_TABLE)
    limbs = []
    for pointer in pointers:
        x, y, z, child, sibling, near, far = struct.unpack_from(
            LIMB_STRUCT, data, pointer & 0xFFFFFF)
        limbs.append(dict(pos=(x, y, z), child=child, sibling=sibling,
                          near=near, far=far))
    return limbs


def read_animation(keep, animetion, offset, frame, limb_count):
    """One frame of a LinkAnimation: root translation plus a rotation per limb.

    LinkAnimationHeader at `offset` in gameplay_keep is { s16 frameCount; s16
    pad; void* segment; }. The segment points into link_animetion, where each
    frame is a flat Vec3s[1 + limbCount]: entry 0 is the root translation and
    entry i+1 is limb i's rotation, in binang (0x10000 == 360 degrees).
    """
    frames, _, segment = struct.unpack_from('>hhI', keep, offset)
    if frame >= frames:
        sys.exit('frame %d beyond animation length %d' % (frame, frames))
    stride = (limb_count + 1) * 3
    base = (segment & 0xFFFFFF) + frame * stride * 2
    values = struct.unpack_from('>%dh' % stride, animetion, base)
    root = values[0:3]
    rotations = [tuple(values[3 + i * 3:6 + i * 3]) for i in range(limb_count)]
    return frames, root, rotations


def rotation_matrix(rot):
    """Binang Euler triple -> 3x3, applied Z then Y then X (OoT's ZYX order)."""
    def sc(value):
        angle = value * math.tau / 65536.0
        return math.sin(angle), math.cos(angle)

    sx, cx = sc(rot[0])
    sy, cy = sc(rot[1])
    sz, cz = sc(rot[2])
    rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    return matmul(matmul(rz, ry), rx)


def matmul(a, b):
    return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
                 for r in range(3))


def transform(matrix, origin, point):
    return tuple(origin[i] + sum(matrix[i][k] * point[k] for k in range(3))
                 for i in range(3))


def walk_skeleton(limbs, rotations, root, index=0, parent=None, out=None):
    """Depth-first over child/sibling, composing each limb's posed transform.

    Mirrors SkelAnime's hierarchical draw: every limb translates by its jointPos
    in the parent's frame, then rotates. Without these rotations the limbs pile
    up at the origin -- their display lists are authored in limb-local space.
    """
    if out is None:
        out = []
    identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    if parent is None:
        parent = (identity, (0, 0, 0))
    while index != LIMB_NONE and index < len(limbs):
        limb = limbs[index]
        matrix, origin = parent
        # The animation supplies the root's translation; the rest use jointPos.
        offset = root if index == 0 else limb['pos']
        here = transform(matrix, origin, offset)
        local = matmul(matrix, rotation_matrix(rotations[index]))
        out.append((index, local, here, limb['far']))
        if limb['child'] != LIMB_NONE:
            walk_skeleton(limbs, rotations, root, limb['child'], (local, here), out)
        index = limb['sibling']
    return out


# z_player_lib.c binds these two segments per frame from the face-animation
# tables; both point into the link object itself, so a static dump just has to
# pick a frame. Without them Link's whole face decodes white.
EYES_OPEN_OFFSET = 0x0000     # gLinkChildEyesOpenTex
MOUTH_CLOSED_OFFSET = 0x4000  # gLinkChildMouthClosedTex
GAMEPLAY_KEEP_SEGMENT = 4


class LimbLists(scene_tool.DisplayLists):
    """Display lists for one limb, tolerant of runtime-assigned segments.

    Player draw code binds gameplay_keep at segment 4 and the current eye and
    mouth textures at 8 and 9, so a static dump must supply all three; we bind
    the neutral open-eyes and closed-mouth frames. Anything still unresolved
    falls back to the primitive colour rather than aborting the walk.
    """

    unresolved = 0

    def texture(self):
        try:
            return super().texture()
        except AssertionError:
            LimbLists.unresolved += 1
            return None

    def triangle(self, word, transparent):
        """Record which segment each face's texture came from.

        Faces tinted by the tunic's primitive colour are flat-shaded materials;
        when their texture resolves out of gameplay_keep it is the wrong image
        and its transparent texels punch black holes through the green. Knowing
        the source segment lets apply_primitive_colour() keep those flat.
        """
        before = len(self.faces)
        super().triangle(word, transparent)
        if len(self.faces) > before:
            self.faces[-1]['texture_segment'] = (
                (self.image[0] >> 24) if self.image else None)


def collect_faces(data, keep, placed):
    """Walk each limb's Far display list, posing its vertices into model space.

    One walker is shared across every limb, in draw order, because RDP state --
    above all the loaded TLUT -- persists between limb display lists in the real
    draw. A fresh walker per limb starts with the default white palette, so any
    limb that does not reload the TLUT itself decodes as untextured white.
    """
    # Segment 4 is gameplay_keep, which Player binds alongside the link object
    # (z_player_lib.c). Link's hair texture lives there, so without it the hair
    # decodes white.
    lists = LimbLists(b'', b'')
    lists.segments = {4: keep,
                      6: data,
                      8: data[EYES_OPEN_OFFSET:],
                      9: data[MOUTH_CLOSED_OFFSET:]}
    faces = []
    for index, matrix, origin, far in placed:
        if not far:
            continue
        first = len(lists.faces)
        lists.walk(far)
        for face in lists.faces[first:]:
            moved = [transform(matrix, origin, v[:3]) + tuple(v[3:])
                     for v in face['vertices']]
            face = dict(face)
            face['vertices'] = moved
            face['limb'] = index
            faces.append(face)
    return faces


def apply_primitive_colour(faces):
    """Fold each face's primitive colour into its texels before baking.

    OoT tints Link's tunic through the primitive colour rather than the texture,
    which is how Goron and Zora tunics recolour the same art. The Kokiri tunic
    is prim (80,188,8) over a grey cloth texture, so a baker that ignores prim
    -- as the shared scene baker does, since scene faces are almost all white
    -- renders the tunic, hat and shoulders plain white.

    Untextured faces are given a 1x1 texture of the prim colour: clamped
    sampling makes every texel that colour, which is what the flat-shaded hat
    and tunic pieces should be.
    """
    tinted = 0
    for face in faces:
        prim = face.get('prim') or (255, 255, 255, 255)
        texture = face['texture']
        tinted_flat = (prim[:3] != (255, 255, 255)
                       and face.get('texture_segment') == GAMEPLAY_KEEP_SEGMENT)
        if prim[:3] == (255, 255, 255) and texture:
            continue
        if texture and not tinted_flat:
            colours = [(c[0] * prim[0] // 255, c[1] * prim[1] // 255,
                        c[2] * prim[2] // 255, c[3]) for c in texture['colors']]
            face['texture'] = dict(texture, colors=colours)
        else:
            face['texture'] = dict(width=1, height=1, colors=[prim],
                                   scale=(1.0, 1.0), shifts=0, shiftt=0,
                                   uls=0, ult=0, cms=2, cmt=2, masks=0, maskt=0)
        tinted += 1
    return tinted


def scale_faces(faces, scale):
    for face in faces:
        face['vertices'] = [
            (int(round(v[0] * scale)), int(round(v[1] * scale)),
             int(round(v[2] * scale))) + tuple(v[3:])
            for v in face['vertices']]
    return faces


def drop_degenerate(faces):
    kept = []
    for face in faces:
        if len({v[:3] for v in face['vertices']}) == 3:
            kept.append(face)
    return kept


def ground_and_centre(faces):
    """Put the feet on y=0 and centre x/z, so the model sits on its position."""
    points = [v[:3] for f in faces for v in f['vertices']]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    shift = (-(low[0] + high[0]) // 2, -low[1], -(low[2] + high[2]) // 2)
    for face in faces:
        face['vertices'] = [tuple(v[i] + shift[i] for i in range(3)) + tuple(v[3:])
                            for v in face['vertices']]
    return faces


def write_model(faces, out_path):
    """Same KFR1 v2 container as FOREST.BIN, with no collision triangles."""
    positions = list(dict.fromkeys(v[:3] for f in faces for v in f['vertices']))
    lookup = {p: i for i, p in enumerate(positions)}
    centre = tuple((min(p[i] for p in positions) + max(p[i] for p in positions)) // 2
                   for i in range(3))
    radius = math.ceil(max(math.dist(p, centre) for p in positions))

    texture = bytearray()
    records = bytearray()
    tiles = {}
    for face in faces:
        tile = scene_tool.bake(face, 16)
        if tile not in tiles:
            tiles[tile] = len(texture)
            texture.extend(tile)
        offset = tiles[tile]
        ids = [lookup[v[:3]] for v in face['vertices']]
        records.extend(struct.pack('>4HIIHH', *ids, ids[2], offset + 32, offset,
                                   (16 // 8) << 8 | 16,
                                   int(face['transparent']) | (int(face['cull']) << 1)))

    vertex_data = b''.join(struct.pack('>3h', *p) for p in positions)
    vertex_data += bytes((-len(vertex_data)) % 4)
    vo = 64
    fo = vo + len(vertex_data)
    co = fo + len(records)
    to = (co + 7) & ~7
    total = to + len(texture)
    header = struct.pack('>9I3i4I', KFR1_MAGIC, 2, len(positions), len(faces),
                         vo, fo, to, len(texture), total, *centre, radius,
                         len(faces) + 3, co, 0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(header + vertex_data + records + bytes(to - co) + texture)
    return positions, tiles


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    recipe = json.loads((root / 'assets/dynamic/link/source.json').read_text())
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=OOT_DEFAULT)
    ap.add_argument('--out', type=pathlib.Path, default=root / 'build/generated' / 'LINK.BIN')
    ap.add_argument('--scale', type=float, default=recipe['scale'],
                    help='model units -> world units')
    ap.add_argument('--animation', type=lambda v: int(v, 0), default=int(recipe['animation'], 0),
                    help='LinkAnimationHeader offset in gameplay_keep')
    ap.add_argument('--frame', type=int, default=recipe['frame'])
    args = ap.parse_args()

    data = read_object(args.oot, OBJECT)
    keep = read_object(args.oot, 'gameplay_keep')
    animetion = read_object(args.oot, 'link_animetion')
    limbs = read_limbs(data)
    frames, root, rotations = read_animation(keep, animetion, args.animation,
                                             args.frame, LIMB_COUNT)
    placed = walk_skeleton(limbs, rotations, root)
    faces = collect_faces(data, keep, placed)
    tinted = apply_primitive_colour(faces)
    faces = scale_faces(faces, args.scale)
    faces = drop_degenerate(faces)
    faces = ground_and_centre(faces)
    positions, tiles = write_model(faces, args.out)

    points = [v[:3] for f in faces for v in f['vertices']]
    extent = [(min(p[i] for p in points), max(p[i] for p in points))
              for i in range(3)]
    print('object  : %s (%d bytes)' % (OBJECT, len(data)))
    print('pose    : %#06x frame %d of %d' % (args.animation, args.frame, frames))
    print('limbs   : %d placed, %d with a Far display list'
          % (len(placed), sum(1 for *_, far in placed if far)))
    print('faces   : %d  vertices %d  tiles %d'
          % (len(faces), len(positions), len(tiles)))
    print('prim    : %d faces tinted by primitive colour (tunic/hat)' % tinted)
    print('extent  : x %s  y %s  z %s' % tuple(extent))
    print('height  : %d world units' % (extent[1][1] - extent[1][0]))
    print('out     : %s' % args.out)


if __name__ == '__main__':
    main()
