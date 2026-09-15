#!/usr/bin/env python3
"""
Composites the real OoT (ntsc-1.1) title-screen textures, as extracted by the
zeldaret/oot decomp build, into a single 512x256 truecolor TGA that the Saturn
side loads verbatim as a VDP2 "normal bitmap" (see vdp2-normal-bitmap example).

Source layout/coords come from the actor that draws them on N64
(src/overlays/actors/ovl_En_Mag/z_en_mag.c): everything is a 2D screen-space
blit against a 320x240 frame, no 3D geometry involved. This script just
reproduces that static composition once, host-side, instead of redoing the
layering on Saturn hardware.

Deliberately skipped for this first pass (see z_en_mag.c EnMag_DrawInner):
- gTitleDiskTex        (64DD indicator, NTSC cart doesn't have one)
- gTitleTitleJPNTex    (Japanese-language logo, this is an NTSC-US build)
- flame/mask glow effect and PRESS START blink (dynamic, need a second
  VDP2 layer on the Saturn side - not part of the static background bitmap)
"""
import sys
from pathlib import Path

from PIL import Image

DECOMP = Path(r"D:\Workspace-Claude\game-decomps\n64\oot\extracted\ntsc-1.1\assets\objects\object_mag")
FONT_DECOMP = Path(r"D:\Workspace-Claude\game-decomps\n64\oot\extracted\ntsc-1.1\assets\textures\nes_font_static")
OUT = Path(__file__).resolve().parent.parent / "assets" / "TITLE.TGA"
PRESS_START_OUT = Path(__file__).resolve().parent.parent / "assets" / "PRESS_START.RAW"

CANVAS_W, CANVAS_H = 512, 256  # matches VDP2_SCRN_BITMAP_SIZE_512X256
FRAME_W, FRAME_H = 320, 240    # native N64 output the coords below assume

# "PRESS START" layout, straight from z_en_mag.c EnMag_DrawInner /
# EnMag_DrawCharTexture: pressStartFontIndices = P R E S S S T A R T, drawn
# via the general message-font glyphs (nes_font_static), each glyph loaded as
# a 16x16 I4 texture but blitted scaled to YREG(2) = 16 * (YREG(1)/100) with
# YREG(1)=63 -> ~10x10px, advancing YREG(8)=7px per char (+YREG(9)=5px extra
# gap after the 5th char, i.e. between "PRESS" and "START"), starting at
# YREG(7)=119. Text color (YREG(4..6)) = (255,30,30); 1px black drop shadow
# offset (+1,+1), drawn first. Y = YREG(10)+171 (main) / +172 (shadow) = 174/175.
PRESS_START_LETTERS = "PRESSSTART"
PRESS_START_GLYPH_FILES = {
    "P": "gMsgChar50LatinCapitalLetterPTex.i4.png",
    "R": "gMsgChar52LatinCapitalLetterRTex.i4.png",
    "E": "gMsgChar45LatinCapitalLetterETex.i4.png",
    "S": "gMsgChar53LatinCapitalLetterSTex.i4.png",
    "T": "gMsgChar54LatinCapitalLetterTTex.i4.png",
    "A": "gMsgChar41LatinCapitalLetterATex.i4.png",
}
GLYPH_SRC_SIZE = 16
GLYPH_DRAW_SIZE = 10  # round(16 * 63/100)
CHAR_ADVANCE = 7
WORD_GAP = 5
TEXT_X0 = 119
TEXT_Y0 = 174
TEXT_COLOR = (255, 30, 30)
SHADOW_COLOR = (0, 0, 0)
# Patch bounding box (with a 1px margin), in the same N64 320x240 coord space
PATCH_X0, PATCH_Y0 = 118, 173
PATCH_W, PATCH_H = 84, 14


def load(name):
    return Image.open(DECOMP / name).convert("RGBA")


def paste_grayscale_as_tint(canvas, im, xy, rgb):
    """i8 N64 textures are luminance-as-alpha (white text, black = transparent).
    Recolor the white text to `rgb` and use luminance as the alpha mask."""
    im = im.convert("L")
    r, g, b = rgb
    tinted = Image.merge("RGBA", (
        im.point(lambda v: r * v // 255),
        im.point(lambda v: g * v // 255),
        im.point(lambda v: b * v // 255),
        im,
    ))
    canvas.paste(tinted, xy, tinted)


def main():
    if not DECOMP.is_dir():
        sys.exit(f"decomp extracted assets not found at {DECOMP} - has `make setup` run there?")

    frame = Image.new("RGBA", (FRAME_W, FRAME_H), (0, 0, 0, 255))

    shield = load("gTitleZeldaShieldLogoTex.rgba32.png")
    assert shield.size == (160, 160), shield.size
    frame.paste(shield, (160 - 80, 100 - 80), shield)

    legend = load("gTitleTheLegendOfTextTex.i8.png")
    assert legend.size == (72, 8), legend.size
    paste_grayscale_as_tint(frame, legend, (154, 73), (255, 230, 140))

    ocarina = load("gTitleOcarinaOfTimeTMTextTex.i8.png")
    assert ocarina.size == (96, 8), ocarina.size
    paste_grayscale_as_tint(frame, ocarina, (152, 127), (255, 230, 140))

    copyright_ = load("gTitleCopyright1998Tex.ia8.png")
    assert copyright_.size == (128, 16), copyright_.size
    frame.paste(copyright_, (94, 198), copyright_)

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), (0, 0, 0))
    canvas.paste(frame.convert("RGB"), (0, 0))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    write_tga_uncompressed_top_left(canvas, OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")

    make_press_start_patch()


def make_press_start_patch():
    """The blinking "PRESS START" prompt has to live outside the static
    background bitmap so the Saturn side can toggle it on/off - see main.c,
    which blits this raw RGB555 patch straight into the same VRAM bitmap over
    a fixed rectangle rather than needing a second scroll layer."""
    patch = Image.new("RGBA", (PATCH_W, PATCH_H), (0, 0, 0, 255))

    def draw_word(color, dx, dy):
        x = TEXT_X0 + dx
        for i, ch in enumerate(PRESS_START_LETTERS):
            glyph = Image.open(FONT_DECOMP / PRESS_START_GLYPH_FILES[ch]).convert("L")
            assert glyph.size == (GLYPH_SRC_SIZE, GLYPH_SRC_SIZE), glyph.size
            glyph = glyph.resize((GLYPH_DRAW_SIZE, GLYPH_DRAW_SIZE), Image.BOX)
            r, g, b = color
            tinted = Image.merge("RGBA", (
                glyph.point(lambda v: r * v // 255),
                glyph.point(lambda v: g * v // 255),
                glyph.point(lambda v: b * v // 255),
                glyph,
            ))
            patch.paste(tinted, (x - PATCH_X0, TEXT_Y0 + dy - PATCH_Y0), tinted)
            x += CHAR_ADVANCE
            if i == 4:
                x += WORD_GAP

    draw_word(SHADOW_COLOR, 1, 1)
    draw_word(TEXT_COLOR, 0, 0)

    r, g, b, _a = patch.split()
    pixels565 = []
    for pr, pg, pb in zip(r.tobytes(), g.tobytes(), b.tobytes()):
        rgb555 = 0x8000 | ((pr >> 3) << 10) | ((pg >> 3) << 5) | (pb >> 3)
        pixels565.append(rgb555)

    with open(PRESS_START_OUT, "wb") as f:
        for v in pixels565:
            # sh2eb (big-endian SH2) reads this as raw uint16_t, no format
            # parser involved (unlike the TGA above) - must be big-endian.
            f.write(v.to_bytes(2, "big"))
    print(f"wrote {PRESS_START_OUT} ({PRESS_START_OUT.stat().st_size} bytes, {PATCH_W}x{PATCH_H} "
          f"RGB555 at N64-space origin {PATCH_X0},{PATCH_Y0})")


def write_tga_uncompressed_top_left(im, path):
    """Match the exact on-disk shape of the known-good reference asset used
    by the vdp2-normal-bitmap example (assets/BITMAP.TGA): RLE-compressed
    truecolor (image type 10), top-left origin (descriptor bit 5 set).

    This isn't optional polish - libyaul's tga_image_decode apparently
    doesn't handle uncompressed (type 2) truecolor correctly (verified by
    testing: it produced shattered/tiled garbage on Saturn, consistent with
    an RLE decoder misreading raw pixel bytes as RLE packet headers), and
    Pillow's own TGA writer defaults to bottom-left origin. So both the RLE
    packing and the origin flag are written by hand here rather than left to
    Pillow.
    """
    w, h = im.size
    header = bytes([
        0, 0, 10,             # id length, color map type, image type (10 = RLE truecolor)
        0, 0, 0, 0, 0,        # color map spec (unused)
        0, 0, 0, 0,           # x/y origin
        w & 0xFF, (w >> 8) & 0xFF,
        h & 0xFF, (h >> 8) & 0xFF,
        24,                   # bits per pixel
        0x20,                 # image descriptor: bit5 set = top-left origin
    ])
    r, g, b = im.split()
    bgr = Image.merge("RGB", (b, g, r))
    pixels = bgr.tobytes()

    with open(path, "wb") as f:
        f.write(header)
        for row in range(h):
            f.write(_rle_encode_row(pixels[row * w * 3:(row + 1) * w * 3], w))
        f.write(b"\x00" * 8 + b"TRUEVISION-XFILE.\x00")


def _rle_encode_row(row_bytes, width):
    """TGA RLE packet stream for one scanline of 24bpp pixels (RLE packets
    never cross scanlines, the conventional/safe TGA encoder behavior)."""
    px = [row_bytes[i * 3:i * 3 + 3] for i in range(width)]
    out = bytearray()
    i = 0
    while i < width:
        run = 1
        while i + run < width and run < 128 and px[i + run] == px[i]:
            run += 1
        if run >= 2:
            out.append(0x80 | (run - 1))
            out += px[i]
            i += run
        else:
            j = i
            count = 0
            while j < width and count < 128:
                if j + 1 < width and px[j] == px[j + 1]:
                    break
                count += 1
                j += 1
            out.append(count - 1)
            for k in range(i, j):
                out += px[k]
            i = j
    return bytes(out)


if __name__ == "__main__":
    main()
