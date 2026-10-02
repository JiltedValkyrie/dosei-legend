#!/usr/bin/env python
"""Convert the level's static FOREST.BIN (KFR1 v2) into SGL tables for the Jo game.

The KFR1 file already stores geometry the way SGL wants it: one shared vertex
pool plus per-face indices, with the third index repeated as the fourth corner
(SGL draws a triangle as a degenerate quad).  So the POINT table is emitted
as-is -- the 1268 shared vertices are NOT expanded to four-per-face.

Record layout, from shared/tools/build_kokiri_scene.py:write_scene():
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


def floor_uses_far_sort(baked, indices, normal):
    """Mark large upward ground faces; runtime retains the above-eye guard."""
    corners = [baked[i] for i in indices]
    extent = max(max(c[k] for c in corners) - min(c[k] for c in corners)
                 for k in (0, 2))
    return normal[1] <= -int(.85 * 65536) and extent > 64


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


def replace_with_checker(tiles):
    """Swap every tile for the same checkerboard.

    Diagnostic only. A regular grid makes the mapping legible: even squares mean
    the texture is being sampled as intended and any distortion is the affine
    stretch VDP1 always applies, while a smeared or folded grid means the corner
    mapping itself is wrong.
    """
    clut = tuple([0x0000] + [0x8000 | (31 << (5 * c)) for c in range(3)] * 5)
    for tile in tiles.values():
        w, h = tile['width'], tile['height']
        pixels = bytearray()
        for y in range(h):
            row = []
            for x in range(w):
                # 4x4 checker, with a distinct colour every other block so
                # rotation and folding are visible as well as stretching.
                block = ((x >> 2) + (y >> 2))
                row.append(1 + (block % 3) if (block & 1) else 0)
            for x in range(0, w, 2):
                pixels.append((row[x] << 4) | row[x + 1])
        tile['clut'] = clut
        tile['pixels'] = bytes(pixels)


def emit(head, verts, faces, tiles, out_dir, name='kokiri'):
    out_dir.mkdir(parents=True, exist_ok=True)

    def fix(text):
        """Resolve the @n@/@N@ name tokens. Unlike %s they cannot
        collide with the %-formatting the emitted lines already use."""
        return text.replace('@n@', name).replace('@N@', name.upper())

    banner = '/* Generated by game/tools/build_sgl_scene.py -- do not edit. */'

    # --- POINT table: shared vertices, SGL FIXED (16.16) ----------------
    # Y is negated here rather than reflected at runtime with slScale(1,-1,1).
    # Both give SGL the same view-space coordinates, but baking it keeps the
    # modelview matrix a pure translation, so face normals need no reasoning
    # about how a reflection transforms them. The camera translation in
    # main.c is unchanged: eye.y - y is exactly (-y) + eye.y.
    baked = [(x, -y, z) for x, y, z in verts]
    if name == 'link':
        # Link's table is skinned: link_anim.c rewrites every vertex from the
        # baked clips before the first submission, so an initialiser here would
        # be overwritten without ever being drawn. Leaving it uninitialised puts
        # it in .bss instead of .data, which matters because the whole image
        # sits below SGL's work area -- the initialiser is ~4 KB of the budget
        # the clip data needs. It is also not static: the skinner is another
        # translation unit.
        lines = [banner, '', '#include <jo/jo.h>', '#include "@n@_scene.h"', '',
                 '/* Skinned at runtime by link_anim.c; see link_clips.h. */',
                 'POINT @n@_points[@N@_VERTEX_COUNT];', '']
    else:
        lines = [banner, '', '#include <jo/jo.h>', '#include "@n@_scene.h"', '',
                 'static POINT @n@_points[@N@_VERTEX_COUNT] = {']
        for x, y, z in baked:
            lines.append('    { toFIXED(%d), toFIXED(%d), toFIXED(%d) },' % (x, y, z))
        lines += ['};', '']

    # --- POLYGON + ATTR tables -----------------------------------------
    # Link's two tables are read only when his equipment changes (kokiri_sgl.c
    # copies them into the hot equipped_* lists), so they live on the cart:
    # @n@_mesh.c holds them in one const struct, the makefile objcopies its
    # .rodata to LINKMESH.BIN, and kokiri_scene_load() points link_pdata at
    # the cart copy. 18 KB of work RAM back (BUG-039).
    cart = name == 'link'
    scene_lines = lines
    if cart:
        lines = [banner, '', '#include <jo/jo.h>', '#include "@n@_scene.h"', '',
                 '/* Never linked: objcopied to LINKMESH.BIN (see makefile). */',
                 'const struct { POLYGON p[@N@_POLYGON_COUNT]; ATTR a[@N@_POLYGON_COUNT]; }',
                 '    @n@_mesh_tables = {', '{']
    else:
        lines.append('static POLYGON @n@_polygons[@N@_POLYGON_COUNT] = {')
    for face in faces:
        nx, ny, nz = face_normal(baked, face['idx'])
        lines.append('    { { %d, %d, %d }, { %d, %d, %d, %d } },'
                     % ((nx, ny, nz) + face['idx']))
    lines += ['},' if cart else '};', '']

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
    # Sort rule: SGL keeps ONE depth key per polygon, so a large floor quad
    # reaching away from the camera gets a centre depth NEARER than the actor
    # standing in the middle of it, and paints over his legs. Marking big
    # up-facing ground faces SORT_MAX keys them on their far corner instead,
    # which puts them behind everything standing on them. Only the mark is
    # made here; kokiri_sgl.c restores SORT_CEN for any marked plane that is
    # not below the eye, because a deck above the camera must still occlude.
    # Small horizontal faces keep SORT_CEN: their centre is already close to
    # their true depth, and leaving them alone limits how many floor/floor
    # pairs this rule can reorder against each other.
    FLOOR_SORT_SPAN = 64
    floor_sorted = 0
    lines.append('{' if cart else 'static ATTR @n@_attributes[@N@_POLYGON_COUNT] = {')
    for face in faces:
        # Animated Link's POINTs rotate with each limb but these normals are
        # still the bind-pose normals. Single_Plane would cull live faces from
        # stale directions, opening holes in his body. No runtime lighting
        # uses them; draw both sides until posed normals are supplied.
        plane = 'Single_Plane' if face['cull'] and name != 'link' else 'Dual_Plane'
        atrb = 'CL16Look | No_Gouraud | ECdis'
        if face['mesh']:
            atrb += ' | MESHon'
        sort = 'SORT_CEN'
        if name != 'link':
            if floor_uses_far_sort(baked, face['idx'], face_normal(baked, face['idx'])):
                sort = 'SORT_MAX'
                floor_sorted += 1
        lines.append('    ATTRIBUTE(%s, %s | UsePalette | UseNearClip, %d, '
                     'No_Palet, No_Gouraud, %s, sprNoflip, No_Option),'
                     % (plane, sort, tiles[face['tex_off']]['index'], atrb))
    lines += ['}};' if cart else '};', '']
    if cart:
        (out_dir / fix('@n@_mesh.c')).write_text(fix('\n'.join(lines)))
        lines = scene_lines
    if name != 'link':
        print('  floors  : %d of %d faces keyed SORT_MAX (span > %d)'
              % (floor_sorted, len(faces), FLOOR_SORT_SPAN))

    tables = ('0', '0') if cart else ('@n@_polygons', '@n@_attributes')
    lines += ['PDATA @n@_pdata = {',
              '    @n@_points, @N@_VERTEX_COUNT,',
              '    %s, @N@_POLYGON_COUNT,' % tables[0],
              '    %s' % tables[1],
              '};', '']
    (out_dir / fix('@n@_scene.c')).write_text(fix('\n'.join(lines)))

    # --- texture blob + per-tile descriptors ----------------------------
    blob = bytearray()
    descs = []
    for tile in tiles.values():
        if tile['width'] % 8 or not 8 <= tile['width'] <= 504 or not 1 <= tile['height'] <= 255:
            raise ValueError('invalid VDP1 texture dimensions')
        if len(tile['pixels']) != tile['width'] * tile['height'] // 2:
            raise ValueError('tile pixel count does not match its descriptor')
        descs.append('    { %d, %d, %d, %d },'
                     % (tile['width'], tile['height'], len(blob),
                        len(tile['pixels'])))
        blob.extend(tile['pixels'])
        blob.extend(bytes((-len(blob)) % 8))

    tex = [banner, '', '#include "@n@_scene.h"', '',
           'const @n@_tile @n@_tiles[@N@_TILE_COUNT] = {']
    tex += descs
    tex += ['};', '',
            'const unsigned short @n@_cluts[@N@_TILE_COUNT][16] = {']
    for tile in tiles.values():
        tex.append('    { ' + ' '.join('0x%04X,' % c for c in tile['clut']) + ' },')
    tex += ['};', '']
    if cart:
        # Link's tile descriptors and CLUTs are read only by mesh_load() at
        # scene load: one const struct, objcopied to LINKTEX.BIN (makefile)
        # and loaded into the cart, like LINKMESH (BUG-043).
        cluts = tex[tex.index('const unsigned short @n@_cluts[@N@_TILE_COUNT][16] = {') + 1:-2]
        tables = [banner, '', '#include "@n@_scene.h"', '',
                  '/* Never linked: objcopied to LINKTEX.BIN (see makefile). */',
                  'const struct { @n@_tile t[@N@_TILE_COUNT]; unsigned short c[@N@_TILE_COUNT][16]; }',
                  '    @n@_tex_tables = {', '{'] + descs + ['},', '{'] + cluts + ['}};', '']
        (out_dir / fix('@n@_tex.c')).write_text(fix('\n'.join(tables)))
        tex = [banner, '', "/* Link's tables moved to @n@_tex.c (cart, LINKTEX.BIN). */", '']
    (out_dir / fix('@n@_textures.c')).write_text(fix('\n'.join(tex)))
    (out_dir / fix('@n@_pixels.bin')).write_bytes(bytes(blob))

    header = [banner, '',
              '#ifndef __@N@_SCENE_H__',
              '# define __@N@_SCENE_H__',
              '',
              '# include <jo/jo.h>       /* PDATA and the other SGL types */',
              '',
              '# define @N@_VERTEX_COUNT    %d' % len(verts),
              '# define @N@_POLYGON_COUNT   %d' % len(faces),
              '# define @N@_TILE_COUNT      %d' % len(tiles),
              '# define @N@_PIXEL_BYTES     %d' % len(blob),
              '',
              '/* Source-space bounding sphere, native world scale. */',
              '# define @N@_CENTER_X        %d' % head['cx'],
              '# define @N@_CENTER_Y        %d' % head['cy'],
              '# define @N@_CENTER_Z        %d' % head['cz'],
              '# define @N@_RADIUS          %d' % head['radius'],
              '',
              'typedef struct',
              '{',
              '    unsigned short  width;',
              '    unsigned short  height;',
              '    unsigned int    offset;     /* byte offset into the 4bpp blob */',
              '    unsigned int    length;',
              '}                   @n@_tile;',
              '',
              'extern PDATA                 @n@_pdata;']
    if name == 'link':
        header += ['/* pltbl/attbl start 0: kokiri_scene_load() loads them to the cart. */',
                   '# define @N@_MESH_FILE        "LINKMESH.BIN"',
                   '# define @N@_MESH_BYTES       (@N@_POLYGON_COUNT * (sizeof(POLYGON) + sizeof(ATTR)))',
                   '# define @N@_TEX_FILE         "LINKTEX.BIN"',
                   '# define @N@_TEX_BYTES        (@N@_TILE_COUNT * (sizeof(@n@_tile) + 32))',
                   '/* Rewritten in place by the runtime skinner; see link_anim.h. */',
                   'extern POINT                 @n@_points[@N@_VERTEX_COUNT];']
    if name != 'link':
        header += ['extern const @n@_tile     @n@_tiles[@N@_TILE_COUNT];',
                   'extern const unsigned short  @n@_cluts[@N@_TILE_COUNT][16];']
    header += [
              '',
              '#endif /* !__@N@_SCENE_H__ */',
              '']
    (out_dir / fix('@n@_scene.h')).write_text(fix('\n'.join(header)))
    return len(blob)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--scene', type=pathlib.Path,
                    default=root / 'levels/kokiri/assets/static/FOREST.BIN')
    ap.add_argument('--out', type=pathlib.Path, default=root / 'build/generated')
    ap.add_argument('--model', type=pathlib.Path, default=root / 'build/generated' / 'LINK.BIN',
                    help='actor mesh in the same KFR1 container; skipped if absent')
    ap.add_argument('--diagnostic-tiles', action='store_true',
                    help='replace every scene tile with a checkerboard, to make '
                         'the texture mapping itself visible in-game')
    ap.add_argument('--texture-path', choices=('legacy', 'patches', 'hybrid'), default='hybrid')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--rom-dir', type=pathlib.Path)
    ap.add_argument('--quad-obj', type=pathlib.Path,
                    help='workshop OBJ topology; retain original N64 textures and collision')
    ap.add_argument('--stream-rooms', action='store_true', help='separate authored room banks')
    ap.add_argument('--skip-scene', action='store_true',
                    help='emit only Link and vdp1_layout.h; the forest tables '
                         'are supplied by build_authored_scene.py instead, so '
                         'the generated scene must not spend the budget')
    args = ap.parse_args()
    if args.quad_obj and args.texture_path != 'hybrid':
        ap.error('--quad-obj requires --texture-path hybrid')
    if args.stream_rooms and args.texture_path != 'hybrid':
        ap.error('--stream-rooms requires --texture-path hybrid')
    if args.texture_path == 'legacy':
        (args.out / 'texture_manifest.json').unlink(missing_ok=True)

    from vdp1_budget import Budget, TEXTURE_BASE, VDP1_USER_AREA
    budget = Budget()
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / 'vdp1_layout.h').write_text(
        '/* Generated: command table below textures, never subtracted twice. */\n'
        '#define GAME_TEXTURE_BASE 0x%X\n#define GAME_TEXTURE_BYTES %d\n'
        % (TEXTURE_BASE, VDP1_USER_AREA))

    total_polygons = 0
    for source, name in ((args.scene, 'kokiri'), (args.model, 'link')):
        if args.skip_scene and name == 'kokiri':
            print('kokiri  : skipped, authored scene supplies the forest')
            continue
        if not source.is_file():
            print('%-8s: %s not present, skipped' % (name, source))
            continue
        data, head, verts, faces = read_scene(source)
        tiles = collect_tiles(data, head, faces)
        if name == 'kokiri' and args.texture_path != 'legacy':
            from build_hybrid_scene import convert
            actor = dict(tiles=[], polygons=0, vertices=0)
            if args.model.is_file():
                ad, ah, av, af = read_scene(args.model)
                at = collect_tiles(ad, ah, af)
                actor = dict(tiles=[(t['width'],t['height']) for t in at.values()],
                             polygons=len(af), vertices=len(av))
            if args.stream_rooms:
                from build_room_scene import emit_rooms
                emit_rooms(args,head,actor,face_normal)
                continue
            head, verts, faces, tiles = convert(args.oot, head, actor, args.out,
                                               args.texture_path == 'patches', rom_dir=args.rom_dir,
                                               quad_obj=args.quad_obj, source_path=args.scene)
        if args.diagnostic_tiles and name == 'kokiri':
            replace_with_checker(tiles)
        blob_bytes = emit(head, verts, faces, tiles, args.out, name)
        total_polygons += len(faces)
        budget.add(name, [(t['width'],t['height']) for t in tiles.values()], len(faces), len(verts))

        cull = sum(1 for f in faces if f['cull'])
        mesh = sum(1 for f in faces if f['mesh'])
        print('%-8s: %s' % (name, source))
        print('  vertices: %d (shared, not expanded)' % len(verts))
        print('  polygons: %d  culled/Single_Plane %d  screen-door %d'
              % (len(faces), cull, mesh))
        print('  tiles   : %d unique, 4bpp pixels %d bytes (%.1f KB)'
              % (len(tiles), blob_bytes, blob_bytes / 1024.0))

    # Everything submitted in one frame shares SGL's per-frame polygon budget,
    # so the work area (tools/build_sgl_area.py) must cover this total.
    print('frame   : %d polygons across all meshes' % total_polygons)
    if budget.failures():
        sys.exit('; '.join(budget.failures()))
    print('out     : %s' % args.out)


if __name__ == '__main__':
    main()
