"""Bake source-scheduled sky colours and each scene's dominant floor colour.

This is a Saturn background approximation, not a reproduction of OoT's textured
skybox. The upper colour is the average of the source skybox's top face. The
lower colour is an area-weighted mode of opaque RGB555 texels on upward-facing
staged geometry. Camera position, texture count and triangle subdivision do not
weight the result. No image or mesh scanning occurs at runtime.
"""
import argparse
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import struct

from PIL import Image

from asset_names import room_asset
from environment_source import sky_schedule

SKY_NAMES = ('Sunrise', 'Day', 'Sunset', 'Night', 'SunriseOvercast',
             'DayOvercast', 'SunsetOvercast', 'NightOvercast', 'Holy0', 'Holy1')
SKY_FALLBACK = 0x8000 | (151 >> 3) | ((157 >> 3) << 5) | ((108 >> 3) << 10)
GROUND_FALLBACK = 0x8000 | (222 >> 3) | ((221 >> 3) << 5) | ((155 >> 3) << 10)
POINT = struct.Struct('>3i')
POLYGON = struct.Struct('>3i4H')
ATTR = struct.Struct('>BB5H')
PIECE = struct.Struct('>6i8HII')


def rgb555(rgb):
    return 0x8000 | (rgb[0] >> 3) | ((rgb[1] >> 3) << 5) | ((rgb[2] >> 3) << 10)


def rgb888(colour):
    return [((colour >> shift) & 31) * 255 // 31 for shift in (0, 5, 10)]


def sky_colours(directory):
    """Face five is the upward XZ skybox plane in z_vr_box.c (face index 4)."""
    directory = Path(directory)
    colours, report = [], []
    for name in SKY_NAMES:
        paths = sorted(directory.glob('g%sSkybox5Tex.*.png' % name))
        if len(paths) > 1:
            raise ValueError('Ambiguous source top sky face: ' + name)
        row = dict(name=name, fallback=not paths)
        colour = SKY_FALLBACK
        if paths:
            path = paths[0]
            with Image.open(path) as image:
                rgba = image.convert('RGBA')
                pixels = [p for p in getattr(rgba, 'get_flattened_data', rgba.getdata)() if p[3]]
            if not pixels:
                raise ValueError('Empty source sky image: ' + str(path))
            rgba = [sum(p[k] * p[3] for p in pixels) for k in range(3)]
            alpha = sum(p[3] for p in pixels)
            colour = rgb555([(v + alpha // 2) // alpha for v in rgba])
            row.update(file=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        row.update(rgb555=colour, rgb888=rgb888(colour))
        colours.append(colour)
        report.append(row)
    return colours, report


def _span(data, at, count, what):
    if at < 0 or count < 0 or at > len(data) or count > len(data) - at:
        raise ValueError('Truncated ' + what)
    return memoryview(data)[at:at + count]


def _tile_histogram(width, height, offset, length, palette, pool):
    if not width or not height or width * height % 2 or length < width * height // 2:
        raise ValueError('Invalid ground texture dimensions')
    raw = _span(pool, offset, width * height // 2, 'ground texture pixels')
    counts = Counter()
    for value, count in Counter(raw).items():
        for index in (value >> 4, value & 15):
            # All staged textured room attributes enable transparent index 0.
            if index:
                counts[palette[index] | 0x8000] += count
    return counts, width * height


def geometry_histogram(data, point_at, npoints, nfaces, tiles, pool):
    """Weight upward faces by XZ area, excluding walls, ceilings and index 0.

    Geometry uses inverted Y. A normal Y <= -0.5 covers walkable slopes while
    rejecting vertical walls. XZ weighting reflects map footprint and remains
    additive when the importer subdivides a floor. Floating point is offline.
    """
    poly_at = point_at + npoints * POINT.size
    attr_at = poly_at + nfaces * POLYGON.size
    _span(data, point_at, npoints * POINT.size + nfaces * (POLYGON.size + ATTR.size), 'geometry')
    points = [POINT.unpack_from(data, point_at + i * POINT.size) for i in range(npoints)]
    histogram, cached = Counter(), {}
    faces, area_total = 0, 0.0
    for index in range(nfaces):
        poly = POLYGON.unpack_from(data, poly_at + index * POLYGON.size)
        if poly[1] > -32768:
            continue
        if any(v >= npoints for v in poly[3:]):
            raise ValueError('Ground face vertex out of range')
        corners = [points[v] for v in poly[3:]]
        area2 = abs(sum(a[0] * b[2] - b[0] * a[2]
                        for a, b in zip(corners, corners[1:] + corners[:1]))) / 4294967296.0
        if not area2:
            continue
        attr = ATTR.unpack_from(data, attr_at + index * ATTR.size)
        if (attr[6] & 7) == 4:  # Untextured VDP1 polygon.
            histogram[attr[4] | 0x8000] += area2
        else:
            tile = attr[2]
            if tile >= len(tiles):
                raise ValueError('Ground face tile out of range')
            if tile not in cached:
                cached[tile] = _tile_histogram(*tiles[tile], pool)
            counts, pixels = cached[tile]
            for colour, count in counts.items():
                histogram[colour] += area2 * count / pixels
        faces += 1
        area_total += area2 / 2
    return histogram, faces, area_total


def mesh_histogram(mesh, pixels):
    """Read the existing KRM1 room bank without importing a renderer."""
    header = struct.unpack_from('>8I', _span(mesh, 0, 32, 'KRM1 header'))
    if header[0] != 0x4B524D31 or header[4] != len(pixels):
        raise ValueError('Invalid KRM1 mesh/pixel bank')
    _, points, faces, count = header[:4]
    tile_at = 32 + points * 12 + faces * 32
    palette_at = tile_at + count * 12
    _span(mesh, tile_at, count * 44, 'KRM1 tiles')
    tiles = []
    for i in range(count):
        tile = struct.unpack_from('>HHII', mesh, tile_at + i * 12)
        palette = struct.unpack_from('>16H', mesh, palette_at + i * 32)
        tiles.append((*tile, palette))
    return geometry_histogram(mesh, 32, points, faces, tiles, pixels)


def field_histogram(data):
    """Use full cells and original object LOD1 only; avoid duplicated far LODs."""
    h = struct.unpack_from('>16I', _span(data, 0, 64, 'KRM2 header'))
    if h[0] != 0x4B524D32 or h[1] != 1 or h[7] != len(data) or h[12] + h[4] != len(data):
        raise ValueError('Invalid KRM2 bank')
    tile_at = 64 + h[5] * 8
    palette_at = tile_at + h[3] * 16
    piece_at = palette_at + h[3] * 32
    _span(data, tile_at, h[3] * 48 + h[2] * PIECE.size, 'KRM2 tables')
    pool = _span(data, h[12], h[4], 'KRM2 pixels')
    tiles = []
    for i in range(h[3]):
        tile = struct.unpack_from('>HHIIHH', data, tile_at + i * 16)
        palette = struct.unpack_from('>16H', data, palette_at + i * 32)
        tiles.append((*tile[:4], palette))
    histogram, faces, area = Counter(), 0, 0.0
    for i in range(h[2]):
        piece = PIECE.unpack_from(data, piece_at + i * PIECE.size)
        if piece[11] not in (0, 2):
            continue
        colours, n, a = geometry_histogram(data, piece[14], piece[8], piece[9], tiles, pool)
        histogram.update(colours)
        faces += n
        area += a
    return histogram, faces, area


def scene_ground(cd, scene):
    cd = Path(cd)
    histogram, faces, area, files, missing = Counter(), 0, 0.0, [], []
    for room in range(scene['rooms']):
        stm = cd / room_asset(scene['index'], room, 'STM')
        msh = cd / room_asset(scene['index'], room, 'MSH')
        tex = cd / room_asset(scene['index'], room, 'TEX')
        if stm.exists():
            colours, n, a = field_histogram(stm.read_bytes())
            files.append(stm.name)
        elif msh.exists() and tex.exists():
            colours, n, a = mesh_histogram(msh.read_bytes(), tex.read_bytes())
            files.extend((msh.name, tex.name))
        else:
            missing.append(room)
            continue
        histogram.update(colours)
        faces += n
        area += a
    # Tie-break on colour is explicit and independent of file/face ordering.
    colour = max(histogram, key=lambda c: (histogram[c], -c)) if histogram else GROUND_FALLBACK
    total = sum(histogram.values())
    return colour, dict(index=scene['index'], prefix=scene['prefix'], rgb555=colour,
                        rgb888=rgb888(colour), floor_faces=faces, footprint_area=area,
                        dominant_fraction=histogram[colour] / total if total else 0,
                        files=files, missing_rooms=missing, fallback=not bool(histogram))


def scene_fog(oot, prefix, fallback):
    """Base scene fog palette; alternate weather/story palettes remain future work."""
    root = Path(oot) / 'extracted/ntsc-1.2'
    files = sorted((root / 'assets/scenes').rglob(prefix + '_scene.c'))
    if len(files) != 1:
        return [fallback] * 4
    text = files[0].read_text(encoding='utf-8')
    match = re.search(r'EnvLightSettings\s+[^=]+?=\s*\{\s*#include "([^"]+)"', text)
    if not match:
        return [fallback] * 4
    lights = (root / match[1]).read_text(encoding='utf-8')
    colours = [rgb555(tuple(map(int, row))) for row in re.findall(
        r'\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\},\s*// fogColor', lights)]
    if not colours:
        raise ValueError('No source fog colours: ' + prefix)
    commands = files[0].with_name(prefix + '_scene.inc.c').read_text(encoding='utf-8')
    timed = 'LIGHT_MODE_TIME' in commands
    if timed and len(colours) < 4:
        raise ValueError('Incomplete source day palette: ' + prefix)
    return colours[:4] if timed else [colours[0]] * 4


def bake(oot, cd, scene_table, out, sky_dir=None):
    oot, cd, out = Path(oot), Path(cd), Path(out)
    scenes = json.loads(Path(scene_table).read_text())['scenes']
    if [s['index'] for s in scenes] != list(range(len(scenes))):
        raise ValueError('Expected contiguous scene table indices')
    schedule = sky_schedule(oot)
    sky, sky_report = sky_colours(sky_dir or oot / 'extracted/ntsc-1.2/assets/textures/skyboxes')
    ground, ground_report = [], []
    for scene in scenes:
        colour, row = scene_ground(cd, scene)
        ground.append(colour)
        ground_report.append(row)
    lines = ['/* Generated by build_environment_sky.py. Source timing; approximate gradient. */',
             '#ifndef DOSEI_ENVIRONMENT_SKY_DATA_H', '#define DOSEI_ENVIRONMENT_SKY_DATA_H',
             '#define ENVIRONMENT_SKY_SCENES %du' % len(ground),
             '#define ENVIRONMENT_SKY_COLOURS %du' % len(sky),
             'static const environment_sky_entry_t environment_sky_schedule[4][9] = {']
    for rows in schedule:
        lines.append('    {')
        lines.extend('        {%d, %d, %d, %d, %d},' % tuple(row) for row in rows)
        lines.append('    },')
    lines += ['};', 'static const unsigned short environment_sky_sources[ENVIRONMENT_SKY_COLOURS] = {',
              '    ' + ', '.join('0x%04X' % c for c in sky), '};',
              'static const unsigned short environment_sky_ground[ENVIRONMENT_SKY_SCENES] = {']
    lines.extend('    0x%04X, /* %d %s */' % (c, s['index'], s['prefix']) for c, s in zip(ground, scenes))
    lines += ['};', 'static const unsigned short environment_map_fog[ENVIRONMENT_SKY_SCENES][4] = {']
    lines.extend('    {%s}, /* %s */' % (', '.join('0x%04X' % c for c in scene_fog(oot, row['prefix'], colour)), row['prefix'])
                 for row, colour in zip(scenes, ground))
    lines += ['};', '#endif', '']
    out.mkdir(parents=True, exist_ok=True)
    (out / 'environment_sky_data.h').write_text('\n'.join(lines))
    report = dict(method='Top-face mean of source sky PNGs; area-weighted opaque RGB555 floor mode; lower half flat floor colour.',
                  limits=['Gradient is not the original textured skybox.',
                          'Runtime ground and curtain tint use base scene fog colours, not exact N64 lighting.',
                          'Time tint interpolates four six-hour anchors; alternate weather/story light palettes are not selected.',
                          'Missing/no-floor scenes use the old lower-gradient colour.',
                          'Missing source sky PNGs use the old upper-gradient colour.',
                          'Only the default staged room banks contribute to scene ground colour.'],
                  schedule_source=str(oot / 'src/code/z_kankyo.c'), sky=sky_report, scenes=ground_report,
                  table_bytes=4 * 9 * 8 + len(sky) * 2 + len(ground) * 10)
    (out / 'environment_sky_report.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--cd', type=Path, default=Path('build/cd'))
    parser.add_argument('--scene-table', type=Path, default=Path('build/generated/scene_table.json'))
    parser.add_argument('--out', type=Path, default=Path('build/generated'))
    parser.add_argument('--sky-dir', type=Path)
    args = parser.parse_args()
    report = bake(args.oot, args.cd, args.scene_table, args.out, args.sky_dir)
    print('sky: %d B tables, %d scenes, %d ground fallbacks, %d sky fallbacks' %
          (report['table_bytes'], len(report['scenes']), sum(r['fallback'] for r in report['scenes']),
           sum(r['fallback'] for r in report['sky'])))


if __name__ == '__main__':
    main()
