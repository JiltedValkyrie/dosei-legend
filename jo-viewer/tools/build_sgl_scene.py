#!/usr/bin/env python
"""Convert title-screen/cd/FOREST.BIN (KFR1 v2) into SGL tables for the Jo viewer.

The KFR1 file already stores geometry the way SGL wants it: one shared vertex
pool plus per-face indices, with the third index repeated as the fourth corner
(SGL draws a triangle as a degenerate quad).  So the POINT table is emitted
as-is -- the 1268 shared vertices are NOT expanded to four-per-face.

Record layout, from title-screen/tools/build_kokiri_scene.py:write_scene():
    >4HIIHH  = v0 v1 v2 v2, clut_off(=tex_off+32), tex_off, size, flags
      size  = (px//8) << 8 | px      (16x16 or 32x32 tiles)
      flags = bit0 screen-door mesh, bit1 cull backfaces
Textures are 4bpp, each preceded by a 32-byte (16 x uint16) CLUT.
"""

import argparse
import collections
import math
import pathlib
import struct
import sys

HEADER = '>9I3i4I'
HEADER_FIELDS = ('magic', 'version', 'nverts', 'ntris', 'vertex_off', 'face_off',
                 'texture_off', 'texture_bytes', 'total', 'cx', 'cy', 'cz',
                 'radius', 'commands', 'collision_off', 'ncollision')
FACE = '>4HIIHH'
FACE_SIZE = struct.calcsize(FACE)
KFR1_MAGIC = 0x4B465231


def read_scene(path):
    data = path.read_bytes()
    head = dict(zip(HEADER_FIELDS, struct.unpack_from(HEADER, data, 0)))
    if head['magic'] != KFR1_MAGIC:
        sys.exit('%s: not a KFR1 file (magic %#x)' % (path, head['magic']))
    if head['version'] != 2:
        sys.exit('%s: unsupported KFR1 version %d' % (path, head['version']))
    if head['total'] != len(data):
        sys.exit('%s: header total %d != file size %d'
                 % (path, head['total'], len(data)))

    verts = [struct.unpack_from('>3h', data, head['vertex_off'] + i * 6)
             for i in range(head['nverts'])]

    faces = []
    for i in range(head['ntris']):
        v0, v1, v2, v3, clut_off, tex_off, size, flags = struct.unpack_from(
            FACE, data, head['face_off'] + i * FACE_SIZE)
        if v2 != v3:
            sys.exit('face %d: fourth corner %d != third %d' % (i, v3, v2))
        if clut_off != tex_off + 32:
            sys.exit('face %d: CLUT offset %d != texture offset + 32'
                     % (i, clut_off))
        if max(v0, v1, v2) >= head['nverts']:
            sys.exit('face %d: vertex index out of range' % i)
        # flags bit 0 -> the baseline's mode.mesh_enable (VDP1 screen-door
        # stipple), NOT half-transparency. bit 1 -> cull backfaces: the
        # baseline skips the face when signed screen area <= 0
        # (title-screen/src/scene/kokiri_scene.c:249,265).
        faces.append(dict(idx=(v0, v1, v2, v3), tex_off=tex_off,
                          width=(size >> 8) * 8, height=size & 0xFF,
                          mesh=bool(flags & 1),
                          cull=bool(flags & 2)))
    return data, head, verts, faces


def face_normal(verts, idx):
    """Unit face normal, as SGL 16.16 FIXED, from the stored winding order.

    Computed in the same Y-negated space the POINT table is emitted in, so no
    reflection has to be reasoned about at runtime. SGL decides front/back for
    Single_Plane faces from this vector: a zero normal culls the face, which is
    why every face vanished when the tables still carried { 0, 0, 0 }.
    """
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = (verts[i] for i in idx[:3])
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx = uy * vz - uz * vy
    ny = uz * vx - ux * vz
    nz = ux * vy - uy * vx
    length = math.sqrt(float(nx * nx + ny * ny + nz * nz))
    if length == 0.0:
        return (0, 0, 0)
    # Negated: with the raw cross product of the stored winding, SGL culled
    # almost the whole scene at the spawn pose, leaving only a sliver of
    # ground. Flipping it is what makes Single_Plane keep the faces the
    # baseline keeps. Determined in Kronos, not derived -- SGL's front-face
    # convention relative to this winding is not documented in the SDK headers.
    scale = -65536.0 / length
    return (int(round(nx * scale)), int(round(ny * scale)),
            int(round(nz * scale)))


def collect_tiles(data, head, faces):
    """One entry per distinct texture offset, in first-use order."""
    tiles = collections.OrderedDict()
    for face in faces:
        off = face['tex_off']
        tile = tiles.get(off)
        if tile is None:
            base = head['texture_off'] + off
            clut = struct.unpack_from('>16H', data, base)
            pixel_bytes = face['width'] * face['height'] // 2
            pixels = data[base + 32:base + 32 + pixel_bytes]
            if len(pixels) != pixel_bytes:
                sys.exit('texture at %d truncated' % off)
            tiles[off] = dict(index=len(tiles), width=face['width'],
                              height=face['height'], clut=clut, pixels=pixels)
        elif (tile['width'], tile['height']) != (face['width'], face['height']):
            sys.exit('texture at %d used at two different sizes' % off)
    return tiles


def emit(head, verts, faces, tiles, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    banner = '/* Generated by jo-viewer/tools/build_sgl_scene.py -- do not edit. */'

    # --- POINT table: shared vertices, SGL FIXED (16.16) ----------------
    # Y is negated here rather than reflected at runtime with slScale(1,-1,1).
    # Both give SGL the same view-space coordinates, but baking it keeps the
    # modelview matrix a pure translation, so face normals need no reasoning
    # about how a reflection transforms them. The camera translation in
    # main.c is unchanged: eye.y - y is exactly (-y) + eye.y.
    baked = [(x, -y, z) for x, y, z in verts]
    lines = [banner, '', '#include <jo/jo.h>', '#include "kokiri_scene.h"', '',
             'static POINT kokiri_points[KOKIRI_VERTEX_COUNT] = {']
    for x, y, z in baked:
        lines.append('    { toFIXED(%d), toFIXED(%d), toFIXED(%d) },' % (x, y, z))
    lines += ['};', '']

    # --- POLYGON table: real unit normals, required by Single_Plane -----
    lines.append('static POLYGON kokiri_polygons[KOKIRI_POLYGON_COUNT] = {')
    for face in faces:
        nx, ny, nz = face_normal(baked, face['idx'])
        lines.append('    { { %d, %d, %d }, { %d, %d, %d, %d } },'
                     % ((nx, ny, nz) + face['idx']))
    lines += ['};', '']

    # --- ATTR table -----------------------------------------------------
    # Field layout mirrors jo_3d_set_mesh_polygon_texture() in
    # ../../joengine/jo_engine/3d.c:341-350, which is the reference for how
    # this SGL build expects a textured polygon to be described:
    #   sort = SORT_CEN | ((sprNoflip >> 16) & 0x1c) | No_Option
    #   atrb = (colour mode | No_Gouraud) | ((sprNoflip >> 24) & 0xc0)
    # and paletted modes additionally set UsePalette in sort.
    #
    # These tiles carry 16-colour lookup tables in VDP1 VRAM, so CL16Look is
    # required. CL16Bnk would interpret colno as a CRAM colour-bank selector.
    # colno holds the per-tile lookup-table address, patched in at load time
    # (the address is not known until the CLUTs are uploaded to VRAM).
    # UseNearClip hands the near plane to SGL instead of the libyaul CPU clipper.
    #
    # Culling: the baseline culls a face when flags bit 1 is set, so that bit
    # maps to Single_Plane ("single-sided"), and a clear bit to Dual_Plane
    # ("no front/back decision"). An earlier revision had this inverted.
    #
    # Transparency: the baseline sets mode.mesh_enable from bit 0, which is
    # VDP1 screen-door stipple -> MESHon, not CL_Trans half-transparency. It
    # also sets end_code_disable unconditionally -> ECdis on every face. The
    # baseline additionally turns mesh on for distance fade, which is a runtime
    # depth test this fixed-view viewer does not implement.
    lines.append('static ATTR kokiri_attributes[KOKIRI_POLYGON_COUNT] = {')
    for face in faces:
        plane = 'Single_Plane' if face['cull'] else 'Dual_Plane'
        atrb = 'CL16Look | No_Gouraud | ECdis'
        if face['mesh']:
            atrb += ' | MESHon'
        lines.append('    ATTRIBUTE(%s, SORT_CEN | UsePalette | UseNearClip, %d, '
                     'No_Palet, No_Gouraud, %s, sprNoflip, No_Option),'
                     % (plane, tiles[face['tex_off']]['index'], atrb))
    lines += ['};', '']

    lines += ['PDATA kokiri_pdata = {',
              '    kokiri_points, KOKIRI_VERTEX_COUNT,',
              '    kokiri_polygons, KOKIRI_POLYGON_COUNT,',
              '    kokiri_attributes',
              '};', '']
    (out_dir / 'kokiri_scene.c').write_text('\n'.join(lines))

    # --- texture blob + per-tile descriptors ----------------------------
    blob = bytearray()
    descs = []
    for tile in tiles.values():
        descs.append('    { %d, %d, %d, %d },'
                     % (tile['width'], tile['height'], len(blob),
                        len(tile['pixels'])))
        blob.extend(tile['pixels'])

    tex = [banner, '', '#include "kokiri_scene.h"', '',
           'const kokiri_tile kokiri_tiles[KOKIRI_TILE_COUNT] = {']
    tex += descs
    tex += ['};', '',
            'const unsigned short kokiri_cluts[KOKIRI_TILE_COUNT][16] = {']
    for tile in tiles.values():
        tex.append('    { ' + ' '.join('0x%04X,' % c for c in tile['clut']) + ' },')
    tex += ['};', '']
    (out_dir / 'kokiri_textures.c').write_text('\n'.join(tex))
    (out_dir / 'kokiri_pixels.bin').write_bytes(bytes(blob))

    header = [banner, '',
              '#ifndef __KOKIRI_SCENE_H__',
              '# define __KOKIRI_SCENE_H__',
              '',
              '# include <jo/jo.h>       /* PDATA and the other SGL types */',
              '',
              '# define KOKIRI_VERTEX_COUNT    %d' % len(verts),
              '# define KOKIRI_POLYGON_COUNT   %d' % len(faces),
              '# define KOKIRI_TILE_COUNT      %d' % len(tiles),
              '# define KOKIRI_PIXEL_BYTES     %d' % len(blob),
              '',
              '/* Source-space bounding sphere, native world scale. */',
              '# define KOKIRI_CENTER_X        %d' % head['cx'],
              '# define KOKIRI_CENTER_Y        %d' % head['cy'],
              '# define KOKIRI_CENTER_Z        %d' % head['cz'],
              '# define KOKIRI_RADIUS          %d' % head['radius'],
              '',
              'typedef struct',
              '{',
              '    unsigned short  width;',
              '    unsigned short  height;',
              '    unsigned int    offset;     /* byte offset into the 4bpp blob */',
              '    unsigned int    length;',
              '}                   kokiri_tile;',
              '',
              'extern PDATA                 kokiri_pdata;',
              'extern const kokiri_tile     kokiri_tiles[KOKIRI_TILE_COUNT];',
              'extern const unsigned short  kokiri_cluts[KOKIRI_TILE_COUNT][16];',
              '',
              '#endif /* !__KOKIRI_SCENE_H__ */',
              '']
    (out_dir / 'kokiri_scene.h').write_text('\n'.join(header))
    return len(blob)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scene', type=pathlib.Path,
                    default=root.parent / 'title-screen' / 'cd' / 'FOREST.BIN')
    ap.add_argument('--out', type=pathlib.Path, default=root / 'generated')
    args = ap.parse_args()

    data, head, verts, faces = read_scene(args.scene)
    tiles = collect_tiles(data, head, faces)
    blob_bytes = emit(head, verts, faces, tiles, args.out)

    cull = sum(1 for f in faces if f['cull'])
    mesh = sum(1 for f in faces if f['mesh'])
    print('scene   : %s' % args.scene)
    print('vertices: %d (shared, not expanded)' % len(verts))
    print('polygons: %d  culled/Single_Plane %d  screen-door %d'
          % (len(faces), cull, mesh))
    print('tiles   : %d unique, 4bpp pixels %d bytes (%.1f KB)'
          % (len(tiles), blob_bytes, blob_bytes / 1024.0))
    print('cluts   : %d x 32 bytes = %d bytes' % (len(tiles), len(tiles) * 32))
    print('out     : %s' % args.out)


if __name__ == '__main__':
    main()
