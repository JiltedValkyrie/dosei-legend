#!/usr/bin/env python3
"""Extract an OoT scene's geometry to a flat-shaded OBJ for touch-up.

The opening's dream sequence rides across Hyrule Field to the castle
drawbridge, and that environment is to be flat shaded: no textures, as many
polygons as it likes. This writes the scene's display-list geometry as an OBJ
with one material per distinct colour, so it can be opened in Blender,
trimmed to what the shot actually sees, and re-imported through the authored
path that already feeds tools/build_cutscene_scene.py.

Colour per face is the original's own: the average of its texture's opaque
texels, multiplied by the face's vertex lighting and its primitive colour --
the same derivation build_hybrid_scene.flat_colour uses. So a flat-shaded
castle keeps the colours the castle actually has, rather than invented ones.

Blender import/export: Forward -Z, Up Y, scale 1, no extra axis rotation.
That matches the mesh workshop and the authored forest, so a mesh moved
between them keeps its coordinates.

Offline tool: floating point is fine here.
"""
import argparse
import collections
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_hybrid_scene as hybrid                             # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[1]


def face_colour(face):
    """One colour for a face: its texture's average, lit, times its prim.

    Mirrors build_hybrid_scene.flat_colour but takes a raw display-list face
    rather than a UV group, because nothing here bakes a texture.
    """
    texture = face.get('texture')
    samples = [c for c in texture['colors'] if c[3] >= 64] if texture else []
    if not samples:
        samples = [(255, 255, 255, 255)]
    lights = [hybrid.shade(v, face['lighting']) for v in face['vertices']]
    prim = face.get('prim') or (255, 255, 255, 255)
    return tuple(max(0, min(255, round(
        sum(c[k] for c in samples) / len(samples) *
        sum(s[k] for s in lights) / len(lights) * prim[k] / 255)))
        for k in range(3))


def extract(oot, rom_dir, prefix, out, night):
    faces = hybrid.load_faces(oot, rom_dir, prefix=prefix)
    if not faces:
        raise SystemExit('%s: no display-list geometry' % prefix)

    # Deduplicate positions so Blender sees a welded mesh rather than loose
    # triangles; the display lists repeat corners heavily.
    positions, index_of = [], {}
    materials = collections.OrderedDict()
    grouped = collections.defaultdict(list)
    rooms = collections.Counter()

    for face in faces:
        colour = face_colour(face)
        if night:
            # The dream is at night. Darkened here rather than in the game so
            # what is touched up is what ships.
            colour = tuple(max(0, round(c * NIGHT_SCALE[k])) for k, c in
                           enumerate(colour))
        name = 'c%02X%02X%02X' % colour
        materials.setdefault(name, colour)
        corners = []
        for vertex in face['vertices']:
            key = tuple(int(round(v)) for v in vertex[:3])
            if key not in index_of:
                index_of[key] = len(positions)
                positions.append(key)
            corners.append(index_of[key] + 1)       # OBJ is 1-based
        if len(set(corners)) < 3:
            continue                                 # degenerate after welding
        grouped[name].append(corners)
        rooms[face.get('room', '?')] += 1

    obj = ['# %s, flat shaded, extracted from the US 1.2 ROM.' % prefix,
           '# Y up; native scene units. Blender import/export: '
           'Forward -Z, Up Y, scale 1.',
           '# One material per colour; no textures and no UVs by design.',
           'mtllib %s.mtl' % prefix]
    obj += ['v %d %d %d' % p for p in positions]
    for name in materials:
        obj.append('usemtl %s' % name)
        for corners in grouped[name]:
            obj.append('f ' + ' '.join(str(c) for c in corners))

    mtl = ['# Flat colours taken from the original faces: the average of each',
           '# texture\'s opaque texels, lit, times its primitive colour.']
    for name, colour in materials.items():
        mtl += ['', 'newmtl %s' % name,
                'Kd %.6f %.6f %.6f' % tuple(c / 255 for c in colour),
                'Ka 0.000000 0.000000 0.000000',
                'Ks 0.000000 0.000000 0.000000',
                'illum 1', 'd 1.000000']

    out.mkdir(parents=True, exist_ok=True)
    (out / ('%s.obj' % prefix)).write_text('\n'.join(obj) + '\n')
    (out / ('%s.mtl' % prefix)).write_text('\n'.join(mtl) + '\n')

    low = [min(p[k] for p in positions) for k in range(3)]
    high = [max(p[k] for p in positions) for k in range(3)]
    print('scene   : %s' % prefix)
    print('rooms   : %s' % dict(rooms))
    print('geometry: %d vertices, %d faces, %d colours'
          % (len(positions), sum(len(f) for f in grouped.values()),
             len(materials)))
    print('bounds  : %s .. %s' % (low, high))
    print('out     : %s' % (out / ('%s.obj' % prefix)))


# A plain night tint: the dream is at night, and the ROM's daytime colours are
# far too bright for it. Blue is kept highest so the darkness reads as night
# rather than as underexposure.
NIGHT_SCALE = (0.32, 0.36, 0.55)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=pathlib.Path,
                        default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--prefix', default='spot00',
                        help='scene to extract, e.g. spot00 (Hyrule Field)')
    parser.add_argument('--out', type=pathlib.Path,
                        default=ROOT / 'levels/hyrule/assets/static')
    parser.add_argument('--night', action='store_true',
                        help='tint for the dream sequence, which is at night')
    args = parser.parse_args()
    extract(args.oot, args.rom_dir, args.prefix, args.out, args.night)


if __name__ == '__main__':
    main()
