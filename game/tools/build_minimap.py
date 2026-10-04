"""Overworld minimaps (z_map_exp.c Minimap_Draw) for VDP2 NBG2.

Writes build/cd/MINIMAP.BIN and build/generated/minimap_data.h. One row per
scene that has a map; values come from z_map_data.c (sOwMinimapPosX/Y,
sOwMinimapWidth/Height, sOwCompassInfo), never typed in by hand. Textures are
the ROM's IA4 map_grand_static images, turned into 16-colour 8x8 cells.

MINIMAP.BIN: "KMAP", u16 BE row count, then per row u32 BE offset + u16 BE
bytes of its cells (cell 0 blank), then the Link-marker frames: 9 x 8x8
8-bit dots (8 facings, then the debug enemy dot). Offsets are from the file
start. See src/minimap.c.

Dungeon floors/rooms are not built yet; the row layout leaves room for a
floor index (see docs/MINIMAP_PLAN.md).
"""
import argparse
import re
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]

# save scene, OoT overworld map index (scene id - SCENE_HYRULE_FIELD), texture.
MAPS = (
    ('SAVE_SCENE_KOKIRI_FOREST', 4, 'gKokiriForestMinimapTex'),
)

# R_MINIMAP_COLOR (z_construct.c) modulates the IA intensity.
MAP_COLOUR = (0, 255, 255)
# Minimap_DrawCompassIcons: Link's arrow prim colour; debug dot (not source).
ARROW_COLOUR = (200, 255, 0)
DOT_COLOUR = (255, 40, 40)
LEVELS = (0, 73, 109, 146, 182, 219, 255)       # IA4 intensities, 3 bits


def array(source, name):
    body = source.split(name, 1)[1].split('{', 1)[1].split('};', 1)[0]
    return [int(v) for v in re.findall(r'-?\d+', body)]


def rgb555(r, g, b):
    return 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)


def cells(image):
    """4bpp cells: index 0 transparent, 1..7 the intensity levels."""
    w, h = image.size
    cw, ch = (w + 7) // 8, (h + 7) // 8
    px = image.load()
    out = bytearray(32)                          # cell 0: blank
    for cy in range(ch):
        for cx in range(cw):
            for y in range(8):
                row = 0
                for x in range(8):
                    X, Y = cx * 8 + x, cy * 8 + y
                    idx = 0
                    if X < w and Y < h:
                        r, g, b, a = px[X, Y]
                        if a >= 128:
                            idx = 1 + min(range(len(LEVELS)), key=lambda i: abs(LEVELS[i] - r))
                    row = (row << 4) | idx
                out += row.to_bytes(4, 'big')
    return bytes(out), cw, ch


def marker_frames():
    """Eight 8x8 arrows (facing 0 = +z = screen down, then +45 deg steps
    toward +x = screen right) and one 4x4 debug dot. Index 16 arrow, 17 dot,
    0 transparent. Drawn at 4x and reduced by majority."""
    frames = bytearray()
    import math
    for f in range(8):
        big = Image.new('L', (32, 32), 0)
        a = f * math.pi / 4
        dx, dy = math.sin(a), math.cos(a)
        tip = (16 + dx * 14, 16 + dy * 14)
        left = (16 - dx * 10 - dy * 9, 16 - dy * 10 + dx * 9)
        right = (16 - dx * 10 + dy * 9, 16 - dy * 10 - dx * 9)
        ImageDraw.Draw(big).polygon([tip, left, right], fill=255)
        small = big.resize((8, 8), Image.BOX)
        frames += bytes(16 if small.getpixel((x, y)) >= 96 else 0
                        for y in range(8) for x in range(8))
    frames += bytes(17 if 2 <= x <= 5 and 2 <= y <= 5 else 0
                    for y in range(8) for x in range(8))
    return bytes(frames)


def build(oot, out_cd, out_gen):
    data = (oot / 'src/code/z_map_data.c').read_text()
    pos_x, pos_y = array(data, 'sOwMinimapPosX'), array(data, 'sOwMinimapPosY')
    width, height = array(data, 'sOwMinimapWidth'), array(data, 'sOwMinimapHeight')
    compass = array(data, 'sOwCompassInfo')
    tex_dir = oot / 'extracted/ntsc-1.2/assets/textures/map_grand_static'
    rows, blobs = [], []
    for save, index, tex in MAPS:
        image = Image.open(tex_dir / (tex + '.ia4.png')).convert('RGBA')
        if image.size != (width[index], height[index]):
            raise SystemExit('%s is %s, map data says %dx%d'
                             % (tex, image.size, width[index], height[index]))
        # Fixed screen-coordinate NBG2 page shared with the button HUD.
        # Preserve source positions that fall between cell boundaries.
        padded = Image.new('RGBA', (image.width + pos_x[index] % 8,
                                    image.height + pos_y[index] % 8))
        padded.paste(image, (pos_x[index] % 8, pos_y[index] % 8))
        blob, cw, ch = cells(padded)
        if len(blob) > 0x2000:
            raise ValueError('Minimap overlaps gameplay HUD cells')
        if not (0 <= pos_x[index] and 64 <= pos_y[index] and
                pos_x[index] + image.width <= 320 and pos_y[index] + image.height <= 240):
            raise ValueError('Minimap must fit below the gameplay button strip')
        rows.append(dict(save=save, w=width[index], h=height[index], cw=cw, ch=ch,
                         x=pos_x[index], y=pos_y[index],
                         compass=compass[index * 4:index * 4 + 4], bytes=len(blob)))
        blobs.append(blob)
    markers = marker_frames()
    head = 6 + 6 * len(rows)
    blob = bytearray(b'KMAP') + len(rows).to_bytes(2, 'big')
    offset = head
    for row, cells_blob in zip(rows, blobs):
        row['offset'] = offset
        blob += offset.to_bytes(4, 'big') + len(cells_blob).to_bytes(2, 'big')
        offset += len(cells_blob)
    for cells_blob in blobs:
        blob += cells_blob
    marker_offset = len(blob)
    blob += markers
    if len(blob) > 0x1000:
        raise ValueError('MINIMAP.BIN exceeds its cart carve')
    out_cd.mkdir(parents=True, exist_ok=True)
    (out_cd / 'MINIMAP.BIN').write_bytes(blob)

    palette = [0, rgb555(0, 0, 0)] + [rgb555(*(c * v // 255 for c in MAP_COLOUR))
                                      for v in LEVELS[1:]]
    h = ['/* Generated by tools/build_minimap.py from z_map_data.c. */',
         '#ifndef MINIMAP_DATA_H', '#define MINIMAP_DATA_H', '#include <stdint.h>',
         '#include "save_state.h"', '',
         'typedef struct {',
         '    uint8_t  save_scene;          /* SAVE_SCENE_* */',
         '    uint8_t  cells_w, cells_h;    /* 8x8 cells, cell 0 blank first */',
         '    uint16_t width, height;       /* sOwMinimapWidth/Height */',
         '    int16_t  x, y;                /* sOwMinimapPosX/Y, 320x240 */',
         '    int16_t  scale_x, scale_y, off_x, off_y;   /* sOwCompassInfo */',
         '    uint32_t offset;              /* cells in MINIMAP.BIN */',
         '    uint16_t bytes;',
         '} minimap_row_t;', '',
         '#define MINIMAP_ROW_COUNT %d' % len(rows),
         '#define MINIMAP_FILE_BYTES %d' % len(blob),
         '#define MINIMAP_MARKER_OFFSET %d' % marker_offset,
         '#define MINIMAP_MARKER_FRAMES 9',
         '#define MINIMAP_DOT_FRAME 8',
         'static const minimap_row_t minimap_rows[MINIMAP_ROW_COUNT] = {']
    for r in rows:
        h.append('    { %s, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d, %d },' % (
            r['save'], r['cw'], r['ch'], r['w'], r['h'], r['x'], r['y'],
            *r['compass'], r['offset'], r['bytes']))
    h += ['};',
          '/* NBG2 palette: 0 clear, 1 black, 2..7 R_MINIMAP_COLOR x intensity. */',
          'static const uint16_t minimap_palette[8] = {%s};'
          % ', '.join('0x%04X' % c for c in palette),
          '/* Marker palette entries 16 (Link arrow), 17 (debug dot). */',
          'static const uint16_t minimap_marker_palette[2] = {0x%04X, 0x%04X};'
          % (rgb555(*ARROW_COLOUR), rgb555(*DOT_COLOUR)),
          '#endif', '']
    out_gen.mkdir(parents=True, exist_ok=True)
    (out_gen / 'minimap_data.h').write_text('\n'.join(h))
    print('Minimap: %d map(s), %d bytes' % (len(rows), len(blob)))
    from build_gameplay_hud import build as build_hud
    build_hud(oot, out_cd, out_gen)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    parser.add_argument('--cd', type=Path, default=ROOT / 'build/cd')
    parser.add_argument('--out', type=Path, default=ROOT / 'build/generated')
    args = parser.parse_args()
    build(args.oot, args.cd, args.out)
