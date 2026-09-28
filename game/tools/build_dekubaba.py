#!/usr/bin/env python3
"""En_Karebaba (withered Deku Baba) model from object_dekubaba, flat colour.

Character rule (human): no texture except faces; the Deku Baba has no face,
so every material is its texture's average colour (x primitive colour).

z_en_karebaba.c draws three things:
  * the head: gDekuBabaSkel posed by gDekuBabaFastChompAnim through
    SkelAnime_DrawOpa, under the actor matrix (world pos, shape.rot ZYX,
    actor scale);
  * the stem: gDekuBabaStemTop/Middle/BaseDL, each after
    Matrix_Translate(0, 0, -2000), under translate(world) * scale * rotZYX;
  * gDekuBabaBaseLeavesDL at home, and gDekuBabaStickDropDL in DeadItemDrop.

Writes build/cd/DEKUBABA.BIN (big-endian):
  'KBB1', u16 frames, u16 part_count,
  per part: u16 points, u16 polygons, u16 frames_of_points (1 = static),
            then polygons x (4 x u16 vertex indices), polygons x u16 RGB555,
            then frames_of_points x points x (x, -y, z) FIXED 16.16.
  Parts: 0 head, 1 stem top, 2 stem middle, 3 stem base, 4 leaves, 5 stick.
Coordinates are model units x 0.01 (the actor's 0.01 scale), so the runtime
scales by actor_scale / 0.01.

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
UNIT = 0.01
STATIC_DLS = ('gDekuBabaStemTopDL', 'gDekuBabaStemMiddleDL', 'gDekuBabaStemBaseDL',
              'gDekuBabaBaseLeavesDL', 'gDekuBabaStickDropDL')


def offsets(oot):
    root = ET.parse(oot / 'assets/xml/objects/object_dekubaba.xml').getroot()
    return {n.attrib['Name']: int(n.attrib['Offset'], 16)
            for n in root.iter() if 'Offset' in n.attrib and 'Name' in n.attrib}


def colour_of(face):
    texture = face['texture']
    c = texture['colors'][0] if texture and texture['colors'] else (face.get('prim') or (255, 255, 255))
    r, g, b = (max(0, min(255, int(v))) >> 3 for v in c[:3])
    return 0x8000 | (b << 10) | (g << 5) | r


def mesh(faces, key_of):
    """Shared vertex keys and quads (a triangle repeats its last index)."""
    keys, index, polys = [], {}, []
    for face in faces:
        ids = []
        for i in range(len(face['vertices'])):
            k = key_of(face, i)
            if k not in index:
                index[k] = len(keys)
                keys.append(k)
            ids.append(index[k])
        polys.append((ids + [ids[-1]])[:4])
    return keys, polys


def walk(lists, display, limb=0):
    first = len(lists.faces)
    lists.current_limb = limb
    lists.walk(display)
    return lists.faces[first:]


def pack_part(points_frames, polys, colours):
    out = struct.pack('>HHH', len(points_frames[0]), len(polys), len(points_frames))
    for p in polys:
        out += struct.pack('>4H', *p)
    for c in colours:
        out += struct.pack('>H', c)
    for frame in points_frames:
        for x, y, z in frame:
            out += struct.pack('>iii', round(x * UNIT * 65536), round(-y * UNIT * 65536),
                               round(z * UNIT * 65536))
    return out


def build(oot, rom_dir, out):
    data = link.read_object(oot, 'object_dekubaba', rom_dir)
    names = offsets(oot)
    table, count = actor.read_skeleton(data, names['gDekuBabaSkel'])
    limbs, _ = actor.read_limbs(data, table, count)
    anim = names['gDekuBabaFastChompAnim']
    frames, root, rotations = actor.read_animation(data, anim, count, 0)
    link.HEAD_LIMB = -1
    link.LIMB_NONE = 0xFF
    placed = link.walk_skeleton(limbs, rotations, root)

    lists = link.LimbLists(b'', b'')
    lists.segments = {6: data}
    lists.matrix_limbs = [i for i, _, _, d in placed if d]
    head = []
    for index, _, _, display in placed:
        if display:
            for face in walk(lists, display, index):
                face = dict(face)
                face['local'] = [tuple(v[:3]) for v in face['vertices']]
                head.append(face)
    link.apply_primitive_colour(head)
    link.flatten_faces(head)
    keys, polys = mesh(head, lambda f, i: (f['vertex_limbs'][i], f['local'][i]))
    colours = [colour_of(f) for f in head]
    head_frames = []
    for frame in range(frames):
        _, root_f, rot_f = actor.read_animation(data, anim, count, frame)
        poses = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rot_f, root_f)}
        head_frames.append([link.transform(*poses[owner], local) for owner, local in keys])
    blob = pack_part(head_frames, polys, colours)
    parts = 1
    print('Deku Baba head: %d limbs, %d frames, %d points, %d faces'
          % (count, frames, len(keys), len(polys)))
    for name in STATIC_DLS:
        sl = link.LimbLists(b'', b'')
        sl.segments = {6: data}
        sl.matrix_limbs = [0]
        faces = [dict(f) for f in walk(sl, 0x06000000 | names[name], 0)]
        link.apply_primitive_colour(faces)
        link.flatten_faces(faces)
        k, p = mesh(faces, lambda f, i: tuple(f['vertices'][i][:3]))
        blob += pack_part([[list(v) for v in k]], p, [colour_of(f) for f in faces])
        parts += 1
        print('  %-22s %3d points, %3d faces' % (name, len(k), len(p)))
    blob = b'KBB1' + struct.pack('>HH', frames, parts) + blob
    out.mkdir(parents=True, exist_ok=True)
    (out / 'DEKUBABA.BIN').write_bytes(blob)
    print('  DEKUBABA.BIN %d bytes' % len(blob))
    return blob


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path, default=ROOT / 'build/cd')
    args = parser.parse_args()
    build(args.oot, args.rom_dir, args.out)


if __name__ == '__main__':
    main()
