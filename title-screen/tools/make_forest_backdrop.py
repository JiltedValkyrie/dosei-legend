#!/usr/bin/env python3
"""
Builds the Kokiri Forest title-screen backdrop as a vertical gradient, from
the scene's OWN documented lighting data rather than a painted guess or a
borrowed asset.

Why a gradient and not an extracted texture: Kokiri Forest has no skybox.
`spot04_scene.inc.c` sets `SCENE_CMD_SKYBOX_SETTINGS(SKYBOX_UNSET_1D, ...)`,
and the game code explicitly skips drawing anything for that value
(`z_play.c`: `if (skyboxId != SKYBOX_UNSET_1D) { ...draw... }`) - it's an
enclosed forest, so "the sky" is just tree-canopy geometry plus fog/ambient
color, never a background image. There is genuinely nothing to extract for
a literal sky texture here.

Source: `spot04_scene_020001CC_EnvLightSettingsList.inc.c`, entry 1 (of 12
time/event-based lighting sets - this one is the bright, clear "midday"
setting, the obvious choice for a title screen over the dawn/dusk/night/
cutscene-specific entries also present):
    ambientColor { 80, 80, 80 }
    light1Color  { 255, 255, 255 }
    fogColor     { 200, 200, 150 }

fogColor is what distant geometry actually reads as in this scene (it's the
color surfaces fade toward at zFar) - the natural choice for the backdrop's
base tone. light1Color (the sun) lightens the top for a dappled-canopy-glow
feel rather than a flat fog-colored card.
"""
import sys
from pathlib import Path

from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "assets" / "FOREST_BG.TGA"

CANVAS_W, CANVAS_H = 512, 256  # matches VDP2_SCRN_BITMAP_SIZE_512X256

# spot04_scene_020001CC_EnvLightSettingsList.inc.c, entry 1 ("midday").
AMBIENT_COLOR = (80, 80, 80)
LIGHT1_COLOR = (255, 255, 255)
FOG_COLOR = (200, 200, 150)

# Blend weight of light1Color into the top-of-frame color, and how far down
# the canvas the gradient fully settles to fogColor. Purely a look decision,
# not derived from game data - the game has no equivalent "gradient span"
# concept since it never renders a card like this.
TOP_LIGHT_WEIGHT = 0.35
GRADIENT_SPAN = 0.75  # fraction of canvas height to reach pure fogColor


def lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def main():
    top_color = lerp(AMBIENT_COLOR, LIGHT1_COLOR, TOP_LIGHT_WEIGHT)

    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H))
    pixels = canvas.load()

    span_px = CANVAS_H * GRADIENT_SPAN
    for y in range(CANVAS_H):
        t = min(1.0, y / span_px)
        row_color = lerp(top_color, FOG_COLOR, t)
        for x in range(CANVAS_W):
            pixels[x, y] = row_color

    write_tga_uncompressed_top_left(canvas, OUT)
    print(f"wrote {OUT} ({OUT.stat().st_size} bytes)")
    print(f"top color (ambient+light1 blend): {top_color}")
    print(f"bottom color (fogColor): {FOG_COLOR}")


def write_tga_uncompressed_top_left(im, path):
    """Same manual RLE/top-left-origin TGA writer as make_title_bitmap.py -
    see that file for why this can't just be Pillow's own TGA writer."""
    w, h = im.size
    header = bytes([
        0, 0, 10,
        0, 0, 0, 0, 0,
        0, 0, 0, 0,
        w & 0xFF, (w >> 8) & 0xFF,
        h & 0xFF, (h >> 8) & 0xFF,
        24,
        0x20,
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
