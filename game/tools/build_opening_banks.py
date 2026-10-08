"""Opening scenery from streamed level geometry and the original house panorama.

Forest banks cover consecutive 100-frame spans of the baked Navi camera.
Only faces that can enter the fog range in that span retain texture tiles;
other visible scenery is a flat fog colour. No alternate authored forest.
"""
import collections
import math
import struct

from PIL import Image
import asset_names

FOG_FAR = 1310
DRAW_FAR = 2620
BANK_FRAMES = 100
FOG_COLOUR = 0x8000 | 27 | (27 << 5) | (19 << 10)


def face_range(points, eye):
    """Conservative distance to the face AABB, including broad ground faces."""
    return sum(max(min(p[k] for p in points) - eye[k], 0,
                   eye[k] - max(p[k] for p in points)) ** 2 for k in (0, 2))


def forest_bank(rooms, track):
    vertices, faces = [], []
    tiles = collections.OrderedDict()
    positions, tile_ids = {}, {}
    views = []
    for eye in track:
        yaw, pitch, roll = (v * math.pi / 32768 for v in eye[3:6])
        sy, cy, sp, cp = math.sin(yaw), math.cos(yaw), math.sin(pitch), math.cos(pitch)
        forward = (sy * cp, sp, cy * cp)
        right, up = (-cy, 0, sy), (-sy * sp, cp, -cy * sp)
        cr, sr = math.cos(roll), math.sin(roll)
        right, up = (tuple(right[k] * cr + up[k] * sr for k in range(3)),
                     tuple(up[k] * cr - right[k] * sr for k in range(3)))
        views.append((eye, forward, right, up, 176 / max(1, eye[6]),
                      136 / max(1, eye[6])))
    for room, (source_vertices, source_faces, source_tiles) in enumerate(rooms):
        for face in source_faces:
            points = [source_vertices[i] for i in face['idx']]
            center = tuple((min(p[k] for p in points) + max(p[k] for p in points)) / 2
                           for k in range(3))
            radius = max(math.dist(center, p) for p in points)
            distance = math.inf
            for eye, forward, right, up, tx, ty in views:
                delta = tuple(center[k] - eye[k] for k in range(3))
                depth = sum(delta[k] * forward[k] for k in range(3))
                if depth + radius < 0:
                    continue
                if abs(sum(delta[k] * right[k] for k in range(3))) > depth * tx + radius * math.sqrt(1 + tx * tx):
                    continue
                if abs(sum(delta[k] * up[k] for k in range(3))) > depth * ty + radius * math.sqrt(1 + ty * ty):
                    continue
                distance = min(distance, face_range(points, eye))
            if distance > DRAW_FAR ** 2:
                continue
            ids = []
            for point in points:
                if point not in positions:
                    positions[point] = len(vertices)
                    vertices.append(point)
                ids.append(positions[point])
            copied = dict(face, idx=tuple(ids))
            if distance > FOG_FAR ** 2:
                copied['colour'] = FOG_COLOUR
            else:
                key = (room, face['tex_off'])
                if key not in tile_ids:
                    tile_ids[key] = len(tiles)
                    tiles[tile_ids[key]] = dict(source_tiles[face['tex_off']],
                                                index=tile_ids[key])
                copied['tex_off'] = tile_ids[key]
            faces.append(copied)
    return vertices, faces, tiles


def house_panorama(oot, asset="LHVR", sides=4, rot_y=0.0, reduction_report=None):
    """z_vr_box.c: SKYBOX_HOUSE_LINK, sSkybox256FaceParams and 63x31 tiles.

    Four pre-rendered CI8 side images, each with its own RGBA16 palette.
    The cube follows the camera; it is not a new 3D model of the furniture.
    """
    from build_hybrid_scene import quantize
    root = oot / 'extracted/ntsc-1.2/baserom'
    pixels = (root / ('vr_' + asset + '_static')).read_bytes()
    palette = (root / ('vr_' + asset + '_pal_static')).read_bytes()
    if len(pixels) != sides * 256 * 256 or len(palette) != sides * 256 * 2:
        raise ValueError('Unexpected Link house panorama dimensions')
    vertices, faces, tiles = [], [], collections.OrderedDict()
    starts = [(-126, -126, 63), (126, -126, 63),
              (126, 126, -63), (-126, 126, -63)]
    for side, (x, z, step) in enumerate(starts[:sides]):
        colours = struct.unpack_from('>256H', palette, side * 512)
        rgba = [(((c >> 11) & 31) * 255 // 31,
                 ((c >> 6) & 31) * 255 // 31,
                 ((c >> 1) & 31) * 255 // 31, 255) for c in colours]
        image = Image.new('RGBA', (256, 256))
        image.putdata([rgba[i] for i in pixels[side * 65536:(side + 1) * 65536]])
        for row in range(8):
            for col in range(4):
                patch = image.crop((col * 63, row * 31, col * 63 + 64, row * 31 + 32))
                clut, packed = quantize(list(patch.getdata()), 64, 32)
                tile = len(tiles)
                tiles[tile] = dict(index=tile, width=64, height=32,
                                   clut=clut, pixels=packed)
                first = len(vertices)
                for u, v in ((col, row), (col + 1, row),
                             (col + 1, row + 1), (col, row + 1)):
                    p = (x + step * u, 124 - 31 * v, z) if side % 2 == 0 else (
                         x, 124 - 31 * v, z + step * u)
                    if rot_y:
                        # skyboxCtx->rot.y (z_vr_box.c), Matrix_RotateY.
                        c, s_ = math.cos(rot_y), math.sin(rot_y)
                        p = (p[0] * c + p[2] * s_, p[1], -p[0] * s_ + p[2] * c)
                    vertices.append(tuple(round(k * 16) for k in p))
                faces.append(dict(idx=tuple(range(first, first + 4)),
                                  tex_off=tile, cull=False, mesh=False))
    from build_hybrid_scene import halve_texture_tiles
    tiles, halving = halve_texture_tiles(tiles)
    if reduction_report is not None:
        reduction_report.update(halving)
    return vertices, faces, tiles


def emit_flight_cache(out):
    """Share identical tiles across flight banks; keep original VRAM layouts."""
    pool, offsets = bytearray(), {}
    for bank in range(10):
        mesh = (out / asset_names.room_asset(asset_names.STORY_BANK_NAVI, bank, 'MSH')).read_bytes()
        pixels = (out / asset_names.room_asset(asset_names.STORY_BANK_NAVI, bank, 'TEX')).read_bytes()
        header = struct.unpack_from('>8I', mesh)
        refs = bytearray()
        for tile in range(header[3]):
            _, _, offset, length = struct.unpack_from('>HHII', mesh,
                32 + header[1]*12 + header[2]*32 + tile*12)
            blob = pixels[offset:offset + length]
            if len(blob) != length:
                raise ValueError('Truncated flight texture')
            if blob not in offsets:
                offsets[blob] = len(pool)
                pool.extend(blob)
                pool.extend(bytes((-len(pool)) % 8))
            refs.extend(struct.pack('>I', offsets[blob]))
        (out / asset_names.room_asset(asset_names.STORY_BANK_NAVI, bank, 'MAP')).write_bytes(refs)
    (out / 'NAVIPOOL.TEX').write_bytes(pool)
    print('Opening shared texture cache: %d bytes' % len(pool))


def emit_opening_banks(oot, out, rooms, normal):
    from build_room_scene import pack_room
    import build_cutscenes as cutscenes
    from vdp1_budget import VDP1_USER_AREA, RUNTIME_SPRITE_BYTES, bank_bytes
    summaries = []

    def emit(scene, room, content):
        vertices, faces, tiles = content
        records = [dict(object=0, indices=list(f['idx'])) for f in faces]
        mesh, pixels, bounds = pack_room(vertices, faces, tiles, records, normal)
        # Reserve resident Link and all overlays, including the message panel.
        used = bank_bytes(len(pixels), len(tiles))
        if used + RUNTIME_SPRITE_BYTES + 20000 + 2048 > VDP1_USER_AREA:
            raise ValueError('Opening S%dR%d exceeds texture budget: %d' %
                             (scene, room, used))
        if len(vertices) > 3200 or len(faces) + 564 > 3750:
            raise ValueError('Opening bank exceeds SGL geometry capacity')
        (out / asset_names.room_asset(scene, room, 'MSH')).write_bytes(mesh)
        (out / asset_names.room_asset(scene, room, 'TEX')).write_bytes(pixels)
        summaries.append(dict(scene=scene, id=room, vertices=len(vertices),
                              polygons=len(faces), tiles=len(tiles),
                              pixel_bytes=len(pixels), objects=len(bounds)))
        print('opening: S%dR%d %d faces / %d tiles / %d VRAM bytes' %
              (scene, room, len(faces), len(tiles), used), flush=True)

    entry = dict(next(e for e in cutscenes.CUTSCENES if e['key'] == 'NAVI_FLY'))
    entry['path'] = oot / entry['path'].relative_to(cutscenes.OOT)
    track = cutscenes.read_cutscene(entry)['track']
    if len(track) > BANK_FRAMES * 10:
        raise ValueError('Navi track exceeds single-digit room bank names')
    for room, start in enumerate(range(0, len(track), BANK_FRAMES)):
        emit(asset_names.STORY_BANK_NAVI, room, forest_bank(rooms, track[start:start + BANK_FRAMES]))
    halving = {}
    emit(asset_names.STORY_BANK_PANORAMA, 0, house_panorama(oot, reduction_report=halving))
    if halving['reductions']:
        summaries[-1]['texture_halving'] = halving
    emit_flight_cache(out)
    import json
    (out / 'opening_banks.json').write_text(json.dumps(summaries, indent=2) + '\n')
    return summaries
