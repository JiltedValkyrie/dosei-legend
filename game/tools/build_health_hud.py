"""Bake original normal-heart IA textures and OoT's primitive/environment tint."""
from pathlib import Path
import struct
from PIL import Image

NAMES = ('Empty', 'Quarter', 'Half', 'ThreeQuarter', 'Full')


def build(oot, cd):
    root = Path(oot)/'extracted/ntsc-1.2/assets/textures/parameter_static'
    palette = [0]
    for index in range(15):
        rgb = tuple(e + (p-e)*index//14 for e,p in zip((50,40,60),(255,70,50)))
        palette.append(0x8000 | rgb[0]>>3 | (rgb[1]>>3)<<5 | (rgb[2]>>3)<<10)
    pixels = bytearray()
    for name in NAMES:
        im = Image.open(root/('gHeart%sTex.ia8.png'%name)).convert('RGBA')
        if im.size != (16,16): raise ValueError('Heart source dimensions changed')
        indices = [1 + r*14//255 if a>=128 else 0 for r,g,b,a in im.getdata()]
        pixels.extend((indices[i]<<4)|indices[i+1] for i in range(0,256,2))
    Path(cd,'HEARTS.BIN').write_bytes(struct.pack('>16H',*palette)+pixels)

