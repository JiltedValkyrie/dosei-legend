"""En_Elf (Navi / Kokiri fairies) from gameplay_keep, posed offline.

The N64 fairy is gFairySkel: four textured wing quads (gFairyWing1-4DL,
gFairyWingTex, prim 210,210,255, alpha from the texture) and a billboard
glow (gGlowCircleSmallDL, limb 8, +-500 units scaled 0.012 and pulsed by
EnElf_OverrideLimbDraw). gFairyAnim is 10 frames, played at speed 1.0: one
frame per 30 Hz step. Actor scale 0.008 (ICHAIN_VEC3F_DIV1000 8).

Writes:
  build/cd/FAIRY.BIN   10 frames x 16 SGL POINTs (x, -y, z FIXED, BE): the
                       four wing quads in actor space, vertex order already
                       matched to VDP1's A,B,C,D texture corners.
  build/cd/FAIRY.RGB   16x16 RGB555 glow: small bright core, dithered
                       (checkerboard) glow fading to the outer colour, no
                       solid halo.
  build/generated/fairy-preview.png  close-up + gameplay-size contact sheet.
"""
import argparse
import math
import re
import struct
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ACTOR_SCALE = 0.008
FRAMES = 10
WING_LIMBS = {3: 'gFairyWing1', 6: 'gFairyWing2', 10: 'gFairyWing3', 13: 'gFairyWing4'}
WING_COLOUR = (210, 210, 255)
# Drawn size of the 16x16 glow sprite in world units. The N64 quad is 12
# across but its texture fades well inside that; half keeps the wings clear.
GLOW_UNITS = 12
INNER = (255, 255, 255)          # sInnerColors[0]
OUTER = (0, 0, 255)              # Attention naviOuterColor, no target
# sAttentionColors primary/secondary (z_actor.c): Navi over an NPC / enemy.
# Written as FAIRYN0-2 / FAIRYE0-2 beside the player set FAIRY/FAIRYM/FAIRYS.
ATTENTION_SETS = (('N', (150, 150, 255), (150, 150, 255)),
                  ('E', (255, 255, 0), (200, 155, 0)))


def rgb555(rgb):
    r, g, b = rgb
    return 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)


def numbers(text):
    return [int(v, 0) for v in re.findall(r'-?0x[0-9A-Fa-f]+|-?\d+', text)]


def limb(keep, i):
    text = (keep / ('gFairySkelLimb_%d.inc.c' % i)).read_text()
    body = re.sub(r'//[^\n]*', '', text)
    pos = numbers(body.split('}', 1)[0])[-3:]
    rest = text.split('// jointPos', 1)[1]
    child_m = re.search(r'FAIRY_LIMB_(\d+) - 1, // child', rest)
    sib_m = re.search(r'FAIRY_LIMB_(\d+) - 1, // sibling', rest)
    return dict(pos=pos, child=int(child_m[1]) if child_m else None,
                sibling=int(sib_m[1]) if sib_m else None)


def vertices(keep, name):
    rows = re.findall(r'VTX\(([^)]*)\)', (keep / (name + 'Vtx.inc.c')).read_text())
    return [tuple(numbers(r)[:3]) for r in rows]


def rot(axis, a):
    c, s = math.cos(a), math.sin(a)
    if axis == 'x':
        return [[1, 0, 0, 0], [0, c, -s, 0], [0, s, c, 0], [0, 0, 0, 1]]
    if axis == 'y':
        return [[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]]
    return [[c, -s, 0, 0], [s, c, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def apply(m, v):
    return tuple(sum(m[i][k] * (v[k] if k < 3 else 1) for k in range(4)) for i in range(3))


def pose(keep):
    limbs = [limb(keep, i) for i in range(14)]
    joints = [tuple(numbers(b)[:3]) for b in
              re.findall(r'\{([^}]*)\}', re.sub(r'//[^\n]*', '',
                         (keep / 'gFairyJointIndices.inc.c').read_text()))]
    data = numbers(re.sub(r'//[^\n]*', '', (keep / 'gFairyFrameData.inc.c').read_text()))
    static_max = 3                              # gFairyAnim staticIndexMax
    value = lambda idx, f: data[idx] if idx < static_max else data[idx + f]
    wings = {3: vertices(keep, 'gFairyWing1'), 6: vertices(keep, 'gFairyWing2'),
             10: vertices(keep, 'gFairyWing3'), 13: vertices(keep, 'gFairyWing4')}
    frames = []
    for f in range(FRAMES):
        out = {}
        root = [value(i, f) for i in joints[0]]

        def draw(i, parent):
            while i is not None:
                L = limbs[i]
                p = [L['pos'][k] + (root[k] if i == 0 else 0) for k in range(3)]
                r = [value(j, f) * math.pi / 32768 for j in joints[i + 1]]
                m = mul(parent, [[1, 0, 0, p[0]], [0, 1, 0, p[1]], [0, 0, 1, p[2]], [0, 0, 0, 1]])
                m = mul(mul(mul(m, rot('z', r[2])), rot('y', r[1])), rot('x', r[0]))
                if i in wings:
                    out[i] = [apply(m, v) for v in wings[i]]
                draw(L['child'], m)
                i = L['sibling']
        draw(0, [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]])
        frames.append([[tuple(c * ACTOR_SCALE for c in v) for v in out[w]]
                       for w in sorted(wings)])
    return frames


def corners(quad, name):
    """VDP1 maps texture A(0,0) B(w,0) C(w,h) D(0,h). Order the quad's
    vertices by their source UVs so the texture lands as on the N64."""
    if name in ('gFairyWing1',):            # v3 (0,0) v2 (32,0) v1 (32,64) v0 (0,64)
        return [quad[3], quad[2], quad[1], quad[0]]
    if name in ('gFairyWing2',):            # v0 (0,0) v1 (32,0) v2 (32,64) v3 (0,64)
        return [quad[0], quad[1], quad[2], quad[3]]
    if name in ('gFairyWing3',):            # v3 (~0,0) v0 (~32,0) v1 (~32,64) v2 (0,64)
        return [quad[3], quad[0], quad[1], quad[2]]
    return [quad[0], quad[3], quad[2], quad[1]]   # Wing4 mirrors Wing3


BAYER = ((0, 8, 2, 10), (12, 4, 14, 6), (3, 11, 1, 9), (15, 7, 13, 5))
GLOW_STEPS = 3          # L .. SL cross-fade (gGlowCircleSmallDL, ENV_ALPHA)


def glow_profile(keep, name):
    """Intensity across the radius of one half-circle glow texture: index 0
    is the centre, 1.0 the rim (texel 31 is the centre column)."""
    im = Image.open(keep / (name + '.i8.png')).convert('L')
    w, h = im.size
    row = [im.getpixel((x, h // 2)) / 255 for x in range(w)]
    def at(r):
        if r >= 1.0:
            return 0.0
        pos = (w - 1) * (1.0 - r)
        k = int(pos)
        return row[k] + (row[min(k + 1, w - 1)] - row[k]) * (pos - k)
    return at


def glow_textures(keep, inner=INNER, outer=OUTER):
    """gGlowCircleSmallDL on the whole 16x16 (12 units: +-500 x 0.012).
    Cycle 1: lerp(L, SL, env alpha); cycle 2: colour (C - outer) * C + outer,
    alpha C. Alpha becomes an ordered dither; three steps of the cross-fade."""
    big, small = glow_profile(keep, 'gCircleGlowLTex'), glow_profile(keep, 'gCircleGlowSLTex')
    out = []
    for step in range(GLOW_STEPS):
        w = step / (GLOW_STEPS - 1)
        pix = []
        for y in range(16):
            for x in range(16):
                r = math.hypot(x - 7.5, y - 7.5) / 8.0
                c = big(r) * (1 - w) + small(r) * w
                # Cycle 2 with prim = inner: (texel * prim - env) * texel + env.
                colour = tuple(round(255 * ((c * i / 255 - o / 255) * c + o / 255))
                               for i, o in zip(inner, outer))
                # Solid only inside SL's full-bright core (N64 alpha ~1 there);
                # the rest of the alpha ramp becomes dither density.
                on = small(r) >= 0.97 or c * max(0.0, 1.0 - r * 1.15) * 16 > BAYER[y & 3][x & 3] + 0.5
                pix.append(rgb555(tuple(max(0, min(255, v)) for v in colour)) if on and c > 0.02 else 0)
        out.append(pix)
    return out


def sparkle_texture(keep):
    """gEffSparklesDL: colour lerp(env=outer, prim=inner, texel), alpha
    texel * prim alpha. 8x8 of the 16x16 I4 star; alpha as ordered dither."""
    src = Image.open(keep / 'gEffSparklesTex.i4.png').convert('L').resize((8, 8), Image.Resampling.BOX)
    pix = []
    for y in range(8):
        for x in range(8):
            t = src.getpixel((x, y)) / 255
            colour = tuple(round(OUTER[k] + (INNER[k] - OUTER[k]) * t) for k in range(3))
            on = t >= 0.6 or t * 16 > BAYER[y & 3][x & 3] + 0.5
            pix.append(rgb555(colour) if on and t > 0.05 else 0)
    return pix


def preview(frames, glow, path):
    """Contact sheet: each frame front-on at 8 px/unit (close-up) and 1.5
    px/unit (normal gameplay distance)."""
    sheet = Image.new('RGB', (FRAMES * 200, 260), (40, 70, 40))
    draw = ImageDraw.Draw(sheet)
    glow_img = Image.new('RGBA', (16, 16))
    for i, c in enumerate(glow):
        if c:
            r, g, b = (c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3
            glow_img.putpixel((i % 16, i // 16), (r, g, b, 255))
    for f, quads in enumerate(frames):
        for scale, oy, size, yaw in ((8, 100, 200, 0.0), (8, 100, 200, 1.1), (1.5, 225, 40, 0.6)):
            layer = Image.new('RGBA', (200, 200 if size == 200 else 60), (0, 0, 0, 0))
            cx, cy = 100, layer.size[1] // 2
            for quad in quads:
                pts = [(cx + (v[0] * math.cos(yaw) + v[2] * math.sin(yaw)) * scale,
                        cy - v[1] * scale) for v in quad]
                ImageDraw.Draw(layer).polygon(pts, fill=WING_COLOUR + (120,),
                                              outline=(255, 255, 255, 160))
            g = glow_img.resize((max(1, round(GLOW_UNITS * scale)),) * 2, Image.Resampling.NEAREST)
            layer.alpha_composite(g, (cx - g.size[0] // 2, cy - g.size[1] // 2))
            if yaw == 1.1:
                sheet.paste(layer.resize((100, 100)), (f * 200 + 100, 0), layer.resize((100, 100)))
            else:
                sheet.paste(layer, (f * 200, oy - layer.size[1] // 2), layer)
        draw.text((f * 200 + 4, 2), 'frame %d' % f, fill=(255, 255, 255))
    sheet.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    args = parser.parse_args()
    keep = args.oot / 'extracted/ntsc-1.2/assets/objects/gameplay_keep'
    frames = pose(keep)
    blob = bytearray()
    names = [WING_LIMBS[w] for w in sorted(WING_LIMBS)]
    for quads in frames:
        for quad, name in zip(quads, names):
            for x, y, z in corners(quad, name):
                blob += struct.pack('>iii', round(x * 65536), round(-y * 65536), round(z * 65536))
    cd = ROOT / 'build/cd'
    cd.mkdir(parents=True, exist_ok=True)
    (cd / 'FAIRY.BIN').write_bytes(blob)
    glows = glow_textures(keep)
    for name, glow in zip(('FAIRY.RGB', 'FAIRYM.RGB', 'FAIRYS.RGB'), glows):
        (cd / name).write_bytes(b''.join(struct.pack('>H', p) for p in glow))
    glow = glows[0]
    for tag, inner, outer in ATTENTION_SETS:
        for step, pix in enumerate(glow_textures(keep, inner, outer)):
            (cd / ('FAIRY%s%d.RGB' % (tag, step))).write_bytes(
                b''.join(struct.pack('>H', p) for p in pix))
    (cd / 'SPARKLE.RGB').write_bytes(b''.join(struct.pack('>H', p) for p in sparkle_texture(keep)))
    from PIL import Image as _I
    sheet = _I.new('RGB', (16 * 3 * 10, 160), (40, 70, 40))
    for i, g in enumerate(glows):
        im = _I.new('RGB', (16, 16), (40, 70, 40))
        for k, c in enumerate(g):
            if c:
                im.putpixel((k % 16, k // 16), ((c & 31) << 3, (c >> 5 & 31) << 3, (c >> 10 & 31) << 3))
        sheet.paste(im.resize((160, 160), _I.NEAREST), (i * 160, 0))
    sheet.save(ROOT / 'build/generated/glow-x10.png')
    gen = ROOT / 'build/generated'
    gen.mkdir(parents=True, exist_ok=True)
    preview(frames, glow, gen / 'fairy-preview.png')
    span = max(abs(c) for q in frames for quad in q for v in quad for c in v)
    print('Fairy: %d frames, wing reach %.1f units, %d bytes' % (FRAMES, span, len(blob)))


if __name__ == '__main__':
    main()
