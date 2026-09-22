#!/usr/bin/env python3
"""Import a cutscene actor's model and animations from the US 1.2 ROM.

The dream sequence needs Ganondorf, Zelda and Impa. They are flat shaded
except their heads, which keep their real artwork -- the same rule
build_link_model.py applies to Link, and for the same reason: the face is what
reads at any distance, and everything else is cloth the Saturn can draw as one
colour for free.

Two things differ from Link and are why this is a separate tool rather than a
flag on that one:

  * Link's skeleton uses LOD limbs, a 16-byte struct with near and far display
    lists. These actors use Standard limbs: 12 bytes, one display list. The
    limb pointer table is not at a known offset either; it is read out of the
    FlexSkeletonHeader the object's XML names.
  * Link's clips are LinkAnimationHeaders, whose frames are stored whole in a
    separate file. These use AnimationHeader, where each joint's rotation is
    an index into shared frame data and an index below staticIndexMax means a
    constant that is not stored per frame at all.

Everything after the pose -- display-list walking, tile baking, the flat
collapse, the emit -- is build_link_model's, so the two importers cannot drift
apart on the parts that matter.

Per the project rule, per-vertex matrix ownership is preserved: each vertex is
posed by the limb that owned it when the display list ran, not by the limb
that happened to draw it.

Offline tool: floating point is fine here.
"""
import argparse
import pathlib
import struct
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_link_model as link                                 # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Standard limb: jointPos (3 s16), child, sibling, one display list pointer.
STANDARD_LIMB = '>hhhBBI'
STANDARD_LIMB_SIZE = struct.calcsize(STANDARD_LIMB)

# Every one of these actors draws at Actor_SetScale(0.01).
ACTOR_SCALE = 0.01

# The actors the dream needs. `clips` names the animations to bake, by the
# offset their XML gives them; an actor with one animation simply has one.
ACTORS = {
    'zelda': dict(object='object_zl1', xml='object_zl1',
                  head='gChildZelda1HeadLimb'),
    'impa':  dict(object='object_im', xml='object_im', head=None),
    'ganon': dict(object='object_ganon', xml='object_ganon',
                  head='gGanondorfHeadLimb'),
}


def read_spec(oot, name):
    """Skeleton offset, head limb offset and animation offsets from the XML."""
    spec = ACTORS[name]
    path = oot / 'assets/xml/objects' / (spec['xml'] + '.xml')
    if not path.is_file():
        raise SystemExit('object XML not found: %s' % path)
    root = ET.parse(path).getroot()
    skeleton = None
    head = None
    animations = []
    for node in root.iter():
        offset = node.attrib.get('Offset')
        if offset is None:
            continue
        value = int(offset, 16)
        if node.tag == 'Skeleton' and skeleton is None:
            skeleton = value
            if node.attrib.get('LimbType') != 'Standard':
                raise SystemExit('%s: %s limbs are not Standard'
                                 % (name, node.attrib.get('LimbType')))
        elif node.tag == 'Animation':
            animations.append((node.attrib.get('Name', ''), value))
        elif node.tag == 'Limb':
            label = node.attrib.get('Name', '')
            if spec['head'] and label == spec['head']:
                head = value
            elif head is None and 'Head' in label:
                head = value
    if skeleton is None:
        raise SystemExit('%s: no skeleton in %s' % (name, path))
    return skeleton, head, animations


def read_skeleton(data, offset):
    """FlexSkeletonHeader -> the limb pointer table and its length.

    { { void** segment; u8 limbCount; pad[3]; } sh; u8 dListCount; pad[3]; }
    """
    segment, limb_count = struct.unpack_from('>IB', data, offset)
    table = segment & 0xFFFFFF
    if not limb_count or table + limb_count * 4 > len(data):
        raise SystemExit('skeleton at %#x is not a limb table' % offset)
    return table, limb_count


def read_limbs(data, table, count):
    """Standard limbs, shaped the way walk_skeleton expects.

    It asks for `near` and `far`; a Standard limb has one display list, so
    both name it and no limb is silently dropped for lacking an LOD.
    """
    pointers = struct.unpack_from('>%dI' % count, data, table)
    limbs = []
    for pointer in pointers:
        x, y, z, child, sibling, display = struct.unpack_from(
            STANDARD_LIMB, data, pointer & 0xFFFFFF)
        limbs.append(dict(pos=(x, y, z), child=child, sibling=sibling,
                          near=display, far=display))
    return limbs, [p & 0xFFFFFF for p in pointers]


def read_animation(data, offset, limb_count, frame):
    """One frame of an AnimationHeader.

    { s16 frameCount; s16 pad; void* frameData; JointIndex* jointIndices;
      s16 staticIndexMax; }

    Each joint has three u16 indices into frameData. An index below
    staticIndexMax names a value that never changes and is stored once;
    anything else is a per-frame run, read at index + frame. Joint 0 is the
    root translation, so there are limbCount + 1 of them.
    """
    frames, _, frame_data, joint_indices, static_max = struct.unpack_from(
        '>hhIIh', data, offset)
    if frames <= 0:
        raise SystemExit('animation at %#x has no frames' % offset)
    frame = min(frame, frames - 1)
    frame_data &= 0xFFFFFF
    joint_indices &= 0xFFFFFF

    def value(index):
        at = index if index < static_max else index + frame
        return struct.unpack_from('>h', data, frame_data + at * 2)[0]

    values = []
    for joint in range(limb_count + 1):
        x, y, z = struct.unpack_from('>3H', data, joint_indices + joint * 6)
        values.append((value(x), value(y), value(z)))
    return frames, values[0], values[1:]


def build(oot, rom_dir, name, out, frame, clip_frames, stride, flat):
    spec = ACTORS[name]
    data = link.read_object(oot, spec['object'], rom_dir)
    skeleton, head_offset, animations = read_spec(oot, name)
    table, limb_count = read_skeleton(data, skeleton)
    limbs, addresses = read_limbs(data, table, limb_count)

    head_index = addresses.index(head_offset) if head_offset in addresses else -1
    print('%-7s %s: skeleton %#x, %d limbs, head limb %s, %d animations'
          % (name, spec['object'], skeleton, limb_count,
             head_index if head_index >= 0 else 'none', len(animations)))
    if not animations:
        print('  warn  : no animations; the model will be posed but static')

    # Pose the bind frame from the first animation, as Link's importer does.
    if animations:
        _, root, rotations = read_animation(data, animations[0][1],
                                            limb_count, frame)
    else:
        root, rotations = (0, 0, 0), [(0, 0, 0)] * limb_count

    # walk_skeleton reads these two as module state.
    link.HEAD_LIMB = head_index
    link.LIMB_NONE = 0xFF
    placed = link.walk_skeleton(limbs, rotations, root)

    lists = link.LimbLists(b'', b'')
    lists.segments = {6: data}
    faces = []
    lists.matrix_limbs = [i for i, _, _, display in placed if display]
    poses = {i: (matrix, origin) for i, matrix, origin, _ in placed}
    for index, matrix, origin, display in placed:
        if not display:
            continue
        first = len(lists.faces)
        lists.current_limb = index
        lists.walk(display)
        for face in lists.faces[first:]:
            # Per-vertex matrix ownership: each vertex is posed by the limb
            # that owned it when the list ran, not by the drawing limb.
            moved = [link.transform(*poses[owner], v[:3]) + tuple(v[3:])
                     for v, owner in zip(face['vertices'], face['vertex_limbs'])]
            face = dict(face)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertices'] = moved
            face['limb'] = index
            faces.append(face)

    if not faces:
        raise SystemExit('%s: no geometry walked' % name)
    link.apply_primitive_colour(faces)
    flattened = link.flatten_faces(faces) if flat else 0
    # These actors draw at Actor_SetScale(0.01) -- z_en_zl1.c:100 and the rest
    # agree -- so the object's units are a hundred times the world's, exactly
    # as Epona's are. Unscaled, Zelda would stand taller than the castle.
    faces = link.scale_faces(faces, ACTOR_SCALE)
    faces = link.drop_degenerate(faces)
    print('  model : %d faces, %d flattened (head keeps its artwork)'
          % (len(faces), flattened))

    # One KFR1 file per actor, the same container FOREST.BIN and LINK.BIN use,
    # so the mesh workshop can open them and the loader already understands the
    # shape. Written skinned: a vertex keeps its owning limb, or the shoulder
    # and the upper arm weld together the moment an animation moves them.
    out.mkdir(parents=True, exist_ok=True)
    path = out / ('%s.BIN' % name.upper())
    positions, tiles, skin_limbs, skin_locals = link.write_model(
        faces, path, skinned=True)
    print('  out   : %s  %d bytes, %d vertices, %d tiles'
          % (path.name, path.stat().st_size, len(positions), len(tiles)))
    return faces, limbs, animations, data, limb_count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--actor', action='append', choices=sorted(ACTORS),
                        help='repeatable; default is every dream actor')
    parser.add_argument('--out', type=pathlib.Path,
                        default=ROOT / 'build/generated')
    parser.add_argument('--frame', type=int, default=0,
                        help='animation frame to bind the model in')
    parser.add_argument('--clip-frames', type=int, default=16)
    parser.add_argument('--stride', type=int, default=2)
    parser.add_argument('--flat', action='store_true', default=True)
    args = parser.parse_args()

    for name in (args.actor or sorted(ACTORS)):
        build(args.oot, args.rom_dir, name, args.out, args.frame,
              args.clip_frames, args.stride, args.flat)


if __name__ == '__main__':
    main()
