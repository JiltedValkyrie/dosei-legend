#!/usr/bin/env python3
"""Bake the two original opening horses into per-frame vertex snapshots.

The horse is not a normal skeleton. Ganondorf, Zelda and Impa hang display
lists off limbs and the runtime poses the limbs; the horses use OoT's Skin system,
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
import cutscene_animation
import build_actor_model as actor                               # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

OBJECT = 'object_horse_zelda'
SKIN_LIMB_TYPE_ANIMATED = 4
SKIN_LIMB_TYPE_NORMAL = 11

SKIN_LIMB = '>hhhBBiI'          # jointPos, child, sibling, segmentType, segment
SKIN_LIMB_SIZE = 0x10

# The ride is a gallop; the others are kept selectable for later shots.
DEFAULT_CLIP = 'gHorseZeldaGallopingAnim'


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


def read_skin_vertices(data, limb):
    """index -> (s, t, normX, normY, normZ, alpha) for the body's vertices.

    The display list reads segment 8, which the Skin system fills at runtime
    with one Vtx per entry; these are the parts of that Vtx that do not move.
    """
    total, count, modifications, dlist = struct.unpack_from(
        '>HHII', data, limb['segment'])
    modifications &= 0xFFFFFF
    attributes = {}
    for i in range(count):
        vtx_count, _, _, vertices, _ = struct.unpack_from(
            '>HHHxxII', data, modifications + i * 0x10)
        vertices &= 0xFFFFFF
        for v in range(vtx_count):
            index, s_, t_, nx, ny, nz, alpha = struct.unpack_from(
                '>HhhbbbB', data, vertices + v * 0xA)
            attributes[index] = (s_, t_, nx, ny, nz, alpha)
    return total, attributes


def build_vertex_segment(points, attributes):
    """The Vtx array the body display list expects on segment 8.

    Vtx_t is { s16 ob[3]; u16 flag; s16 tc[2]; u8 cn[4]; } -- 16 bytes.
    """
    out = bytearray()
    for index, point in enumerate(points):
        s_, t_, nx, ny, nz, alpha = attributes.get(index, (0, 0, 0, 0x7F, 0, 255))
        out.extend(struct.pack('>3hH2h4b', point[0], point[1], point[2], 0,
                               s_, t_, nx, ny, nz, alpha - 256 if alpha > 127
                               else alpha))
    return bytes(out)


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


class SkinLists(link.LimbLists):
    """Retain segment-8 source vertices, rather than welding a posed point."""
    def load_vertex(self, index, vertex):
        super().load_vertex(index, vertex)
        if not hasattr(self, 'skin_ids'):
            self.skin_ids = [None] * len(self.cache)
        if self.vertex_address >> 24 != 8:
            raise ValueError('Skin body vertex outside segment 8')
        self.skin_ids[index] = (self.vertex_address & 0xFFFFFF) // 16

    def triangle(self, word, transparent):
        indices = [(word >> shift & 255) // 2 for shift in (16, 8, 0)]
        vertices = [self.cache[i] for i in indices]
        self.faces.append(dict(vertices=vertices,
                               source_vertices=[self.skin_ids[i] for i in indices],
                               vertex_limbs=[0, 0, 0], texture=self.texture(),
                               lighting=bool(self.geom & 0x20000), prim=self.prim,
                               transparent=transparent, cull=bool(self.geom & 0x400),
                               texture_segment=(self.image[0] >> 24) if self.image else None))


def walk_body(data, dlist, segment8):
    """Faces of the animated body, from its own display list.

    The list loads vertices from segment 8, which the Skin system fills at
    runtime; here that segment is the baked frame. Walking the real list keeps
    the original's triangles, texture bindings and UVs instead of inventing a
    mesh from the blend points.
    """
    lists = SkinLists(b'', b'')
    lists.segments = {6: data, 8: segment8}
    lists.matrix_limbs = []
    lists.current_limb = 0
    lists.walk(0x06000000 | dlist)
    return lists.faces


def walk_normal_limbs(data, limbs, matrices):
    """The rigid limbs -- legs, mane, tail -- posed by the skeleton."""
    faces = []
    for index, limb in enumerate(limbs):
        if limb['kind'] != SKIN_LIMB_TYPE_NORMAL or not limb['segment']:
            continue
        if index not in matrices:
            continue
        lists = link.LimbLists(b'', b'')
        lists.segments = {6: data}
        lists.matrix_limbs = []
        lists.current_limb = index
        lists.walk(0x06000000 | limb['segment'])
        matrix, origin = matrices[index]
        for face in lists.faces:
            face = dict(face)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertex_limbs'] = [index + 1] * 3
            # The rigid limbs need the same actor scale the blended body got
            # in bake_frame, or the legs arrive a hundred times the size of
            # the horse they belong to.
            face['vertices'] = [
                tuple(int(round(v * ACTOR_SCALE)) for v in
                      link.transform(matrix, origin, p[:3])) + tuple(p[3:])
                for p in face['vertices']]
            face['limb'] = index
            faces.append(face)
    return faces


def main():
    global OBJECT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--horse', choices=('zelda', 'ganon'), default='zelda')
    parser.add_argument('--clip')
    parser.add_argument('--frames', type=int, default=12)
    parser.add_argument('--stride', type=int, default=2)
    parser.add_argument('--out', type=pathlib.Path,
                        default=ROOT / 'build/generated')
    args = parser.parse_args()

    OBJECT = "object_horse_" + args.horse
    if args.clip is None:
        args.clip = "gHorseZeldaGallopingAnim" if args.horse == "zelda" else "gHorseGanonRearingAnim"
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
    # Emit the mesh: the body's own display list walked against the baked
    # frame, plus the rigid limbs posed by the skeleton. One pose for now --
    # the per-frame gallop is baked above but not yet carried in the file.
    _, attributes = read_skin_vertices(data, limbs[animated[0]])
    _, root0, rot0 = actor.read_animation(
        data, animations[args.clip], len(limbs), 0)
    matrices0 = limb_matrices(limbs, rot0, root0)
    total0, modifs0, dlist0 = read_modifs(data, limbs[animated[0]])
    body = bake_frame(modifs0, matrices0, total0)
    faces = walk_body(data, dlist0, build_vertex_segment(body, attributes))
    faces += walk_normal_limbs(data, limbs, matrices0)
    for face in faces:
        face.setdefault('local', [tuple(v[:3]) for v in face['vertices']])
        face.setdefault('limb', 0)
    link.character_textures.mark_faces(faces,
        args.oot / 'assets/xml/objects' / (OBJECT + '.xml'))
    link.apply_primitive_colour(faces)
    # A body point belongs to one Skin modification (a precise set of
    # weighted bone owners). Rigid points retain original local XYZ and limb.
    # Shared triangle corners can reuse a point without merging distinct bones.
    source_modif = {v: i for i, mod in enumerate(modifs0) for v in mod['indices']}
    for face in faces:
        face['full_texture'] = True
        if 'source_vertices' in face:
            face['local'] = [(source_modif[v], 0, 0) for v in face['source_vertices']]
            face['vertex_limbs'] = [0, 0, 0]
    corner_keys = [(tuple(local), owner) for f in faces
                   for local, owner in zip(f['local'], f['vertex_limbs'])]
    first_corner = {}
    for i, key in enumerate(corner_keys):
        first_corner.setdefault(key, i)
    unique_corners = list(first_corner.values())
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / ('HZELDA.BIN' if args.horse == 'zelda' else 'HGANON.BIN')
    positions, tiles, _, _ = link.write_model(faces, path, skinned=True)
    print('mesh    : %s  %d bytes, %d faces, %d vertices, %d tiles'
          % (path.name, path.stat().st_size, len(faces), len(positions),
             len(tiles)))

    lengths = {n: actor.read_animation(data, offset, len(limbs), 0)[0]
               for n, offset in animations.items()}
    def motion_frames():
        cached = {}
        for clip, source_frame, _ in cutscene_animation.timeline('horse_' + args.horse, lengths):
            key = clip, source_frame
            if key not in cached:
                _, root, rotations = actor.read_animation(data, animations[clip], len(limbs), source_frame)
                matrices = limb_matrices(limbs, rotations, root)
                body = bake_frame(modifs0, matrices, total0)
                moving = walk_body(data, dlist0, build_vertex_segment(body, attributes))
                moving += walk_normal_limbs(data, limbs, matrices)
                if len(moving) != len(faces):
                    raise ValueError('Horse display list topology changed')
                corners = [tuple(v[:3]) for f in moving for v in f['vertices']]
                for i, owner in enumerate(corner_keys):
                    if corners[i] != corners[first_corner[owner]]:
                        raise ValueError('Distinct Skin motion was merged')
                cached[key] = [corners[i] for i in unique_corners]
            yield cached[key]
    cutscene_animation.write_track(path.with_suffix('.ANM'), motion_frames())

    print('baked   : %d vertices per frame, %d frames, %d bytes'
          % (total_points, args.frames, total_points * args.frames * 6))
    print('extent  : %s' % [tuple(e) for e in extent])
    print('motion  : %d of %d frame snapshots differ from the one before'
          % (moved, args.frames * len(baked)))


if __name__ == '__main__':
    main()
