#!/usr/bin/env python3
"""Bake a flat-shaded OBJ into a textureless VDP1 room bank.

The dream sequence rides across Hyrule Field to the castle drawbridge. That
environment is flat shaded by design: every face is one solid colour, so the
bank carries no tiles, no CLUTs and no pixel blob at all, and costs nothing of
the 445 KB VDP1 texture area. Polygons are cheap on this machine; textures are
not, and the forest fly-through proved it -- 1,795 tiles rendered corrupted at
21 FPS, where this mesh draws 1,074 untextured polygons for zero VRAM.

Input is an OBJ whose MTL gives each material a Kd colour, which is what
tools/extract_scene_obj.py writes and what Blender round-trips. Quads are kept
as quads: SGL draws one, and merging triangles into them is the single largest
saving available here.

The bank format is build_room_scene.pack_room's, with the tile table, the CLUT
table and the pixel file empty. The loader accepts a bank with no tiles and
skips the texture upload entirely.

Offline tool: floating point is fine here.
"""
import argparse
import collections
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from build_sgl_scene import face_normal                         # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Scene 3 is the dream's Hyrule Field. It has no scene_table entry: it is
# never walked into, only flown over, so the cutscene asks for the bank by
# number and nothing else can reach it.
FLAT_SCENE_ID = 3

# ATTR.atrb bits 3..5 select the colour mode; the textured path uses CL16Look
# for its 4bpp tiles. A flat polygon takes its colour straight from colno as a
# 15-bit RGB value, which is CL32KRGB. Bit 7 is kept exactly as the textured
# path sets it. ATTR.dir carries the sprite function: FUNC_Polygon, not the
# textured FUNC_Texture.
CL32KRGB = 5 << 3
ATTR_BASE = 0x80
FUNC_POLYGON = 4


def rgb555(colour):
    """Saturn 15-bit colour with the opaque bit set.

    A zero word is transparent to VDP1, so a pure black face would punch a
    hole in the sky; the opaque bit is what keeps night-time geometry solid.
    """
    r, g, b = (min(31, max(0, int(c) >> 3)) for c in colour)
    return 0x8000 | (b << 10) | (g << 5) | r


def parse_mtl(path):
    """material name -> (r, g, b) from Kd."""
    colours, current = {}, None
    if not path.is_file():
        raise SystemExit('material library not found: %s' % path)
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'newmtl':
            current = parts[1]
        elif parts[0] == 'Kd' and current:
            colours[current] = tuple(round(float(v) * 255) for v in parts[1:4])
    return colours


def parse_obj(path):
    """Positions and faces, each face tagged with its material."""
    positions, faces, current, mtllib = [], [], None, None
    for line in path.read_text().splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'v':
            positions.append(tuple(float(v) for v in parts[1:4]))
        elif parts[0] == 'mtllib':
            mtllib = parts[1]
        elif parts[0] == 'usemtl':
            current = parts[1]
        elif parts[0] == 'f':
            index = [int(c.split('/')[0]) for c in parts[1:]]
            # OBJ indices are 1-based and may be negative (relative).
            index = [i - 1 if i > 0 else len(positions) + i for i in index]
            faces.append(dict(index=index, material=current))
    return positions, faces, mtllib


def pack(vertices, faces):
    """The KFR1 bank layout, with no tiles, CLUTs or pixels."""
    baked = [(x, -y, z) for x, y, z in vertices]
    low = [int(round(min(p[k] for p in vertices))) for k in range(3)]
    high = [int(round(max(p[k] for p in vertices))) for k in range(3)]
    bounds = [tuple(low) + tuple(high)]         # one object: drawn whole

    data = bytearray(struct.pack('>8I', 0x4b524d31, len(vertices), len(faces),
                                 0, 0, len(bounds), 0, 0))
    for p in baked:
        data.extend(struct.pack('>3i', *(int(round(v)) * 65536 for v in p)))
    for face in faces:
        data.extend(struct.pack('>3i4H', *face_normal(baked, face['idx']),
                                *face['idx']))
    for face in faces:
        data.extend(struct.pack('>BB5H', 0 if face['cull'] else 1, 0x67,
                                0, ATTR_BASE | CL32KRGB, face['colour'], 0,
                                FUNC_POLYGON))
    data.extend(bytes(0 for _ in faces))        # every face in object 0
    data.extend(bytes((-len(faces)) % 4))
    for b in bounds:
        data.extend(struct.pack('>6i', *b))
    return bytes(data), bounds


def convert(obj_path, cull):
    positions, raw_faces, mtllib = parse_obj(obj_path)
    if not positions or not raw_faces:
        raise SystemExit('%s: no geometry' % obj_path)
    colours = parse_mtl(obj_path.parent / (mtllib or (obj_path.stem + '.mtl')))

    faces, arity, skipped = [], collections.Counter(), 0
    for face in raw_faces:
        index = list(face['index'])
        arity[len(index)] += 1
        if len(index) == 3:
            index.append(index[2])      # SGL draws a triangle as a flat quad
        elif len(index) != 4:
            # An n-gon fans; the OBJ this is built for has none, but a hand
            # edit could introduce one and dropping it silently would lose
            # geometry without saying so.
            for i in range(1, len(index) - 1):
                faces.append(dict(idx=(index[0], index[i], index[i + 1],
                                       index[i + 1]),
                                  colour=rgb555(colours.get(face['material'],
                                                            (255, 255, 255))),
                                  cull=cull))
            continue
        rgb = colours.get(face['material'])
        if rgb is None:
            skipped += 1
            rgb = (255, 255, 255)
        faces.append(dict(idx=tuple(index), colour=rgb555(rgb), cull=cull))

    if skipped:
        print('  warn  : %d faces had no material colour and are white'
              % skipped)
    print('source  : %d vertices, %d faces %s -> %d polygons, %d colours'
          % (len(positions), len(raw_faces), dict(sorted(arity.items())),
             len(faces), len(set(f['colour'] for f in faces))))
    return positions, faces


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obj', type=pathlib.Path, required=True)
    parser.add_argument('--out', type=pathlib.Path,
                        default=ROOT / 'build/generated')
    parser.add_argument('--scene', type=int, default=FLAT_SCENE_ID)
    parser.add_argument('--cull', action='store_true',
                        help='emit Single_Plane (backface culling) faces')
    args = parser.parse_args()

    if not args.obj.is_file():
        raise SystemExit('mesh not found: %s' % args.obj)
    args.out.mkdir(parents=True, exist_ok=True)

    vertices, faces = convert(args.obj, args.cull)
    mesh, bounds = pack(vertices, faces)
    (args.out / ('S%dR0.MSH' % args.scene)).write_bytes(mesh)

    summary = dict(scene=args.scene, vertices=len(vertices),
                   polygons=len(faces), tiles=0, pixel_bytes=0,
                   objects=len(bounds), source=args.obj.name)
    (args.out / 'flat_bank.json').write_text(json.dumps(summary, indent=2)
                                             + '\n')
    print('bank    : S%dR0  %d polygons  %d vertices  %d bytes'
          % (args.scene, len(faces), len(vertices), len(mesh)))
    print('vram    : 0 bytes -- flat shaded, no tiles and no pixel file')
    print('bounds  : %s .. %s' % (list(bounds[0][:3]), list(bounds[0][3:])))


if __name__ == '__main__':
    main()
