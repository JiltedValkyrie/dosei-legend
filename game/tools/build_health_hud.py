"""Bake original normal-heart IA textures and OoT's primitive/environment tint.

HEARTS.BIN: 16-colour CLUT, five 16x16 4bpp hearts, then the magic meter
(Magic_DrawMeter): gMagicMeterEndTex 8x16 and one column of the uniform
gMagicMeterMidTex as one CLUT index per byte, then the 7 fill rows of
gMagicMeterFillTex. Hearts use indices 1-11; the meter owns 12-15.
"""
from pathlib import Path
import struct
from PIL import Image

NAMES = ('Empty', 'Quarter', 'Half', 'ThreeQuarter', 'Full')
HEART_SHADES = 11
# Overlay combiner: env + (prim - env) * I. Border prim white, env (100,50,50);
# fill prim R_MAGIC_FILL_COLOR (0,200,0), env black (z_construct.c).
METER_DARK, METER_BORDER, METER_FILL, METER_FILL_EDGE = 12, 13, 14, 15
METER_RGB = ((100, 50, 50), (255, 255, 255), (0, 200, 0), (0, 130, 0))
BYTES = 32 + 5 * 128 + 8 * 16 + 16 + 7


def rgb555(rgb):
    return 0x8000 | rgb[0] >> 3 | (rgb[1] >> 3) << 5 | (rgb[2] >> 3) << 10


def build(oot, cd):
    root = Path(oot)/'extracted/ntsc-1.2/assets/textures/parameter_static'
    palette = [0]
    for index in range(HEART_SHADES):
        rgb = tuple(e + (p-e)*index//(HEART_SHADES-1) for e,p in zip((50,40,60),(255,70,50)))
        palette.append(rgb555(rgb))
    palette += [rgb555(c) for c in METER_RGB]
    pixels = bytearray()
    for name in NAMES:
        im = Image.open(root/('gHeart%sTex.ia8.png'%name)).convert('RGBA')
        if im.size != (16,16): raise ValueError('Heart source dimensions changed')
        indices = [1 + r*(HEART_SHADES-1)//255 if a>=128 else 0 for r,g,b,a in im.getdata()]
        pixels.extend((indices[i]<<4)|indices[i+1] for i in range(0,256,2))

    def border(name, size):
        im = Image.open(root/(name + '.ia8.png')).convert('LA')
        if im.size != size: raise ValueError(name + ' dimensions changed')
        return im
    end = border('gMagicMeterEndTex', (8, 16))
    mid = border('gMagicMeterMidTex', (24, 16))
    fill = border('gMagicMeterFillTex', (8, 8))
    cls = lambda la: 0 if la[1] < 128 else METER_BORDER if la[0] >= 128 else METER_DARK
    pixels += bytes(cls(end.getpixel((x, y))) for y in range(16) for x in range(8))
    if any(mid.getpixel((x, y)) != mid.getpixel((0, y)) for y in range(16) for x in range(24)):
        raise ValueError('Magic meter middle is no longer uniform per row')
    pixels += bytes(cls(mid.getpixel((0, y))) for y in range(16))
    # Fill rectangle spans y+3..y+9: texture rows 0-6.
    pixels += bytes(METER_FILL if fill.getpixel((0, y))[0] >= 0xC0 else METER_FILL_EDGE
                    for y in range(7))
    blob = struct.pack('>16H',*palette)+pixels
    assert len(blob) == BYTES
    Path(cd,'HEARTS.BIN').write_bytes(blob)
