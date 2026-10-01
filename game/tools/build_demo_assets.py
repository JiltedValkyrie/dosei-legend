"""Stage existing baseline title/collision assets; no mesh rebuild."""
from pathlib import Path
import argparse
import struct
from PIL import Image
from build_sgl_scene import read_scene

ROOT = Path(__file__).resolve().parents[1]

def rgb555(rgb):
    r, g, b = rgb
    return 0 if not (r or g or b) else 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)


def build_fairy_sprite(wing):
    wing = wing.convert('L').resize((5, 10), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (16, 16))
    pixels = out.load()
    wings = wing.load()
    for y in range(16):
        for x in range(16):
            dx, dy = x - 7.5, y - 7.5
            distance = (dx * dx + dy * dy) ** 0.5
            glow = max(0, int(255 - distance * 42))
            value = glow
            # Mirror the authentic OoT wing on either side of the glow.
            if 1 <= x < 6 and 3 <= y < 13:
                value = max(value, wings[x - 1, y - 3])
            if 10 <= x < 15 and 3 <= y < 13:
                value = max(value, wings[14 - x, y - 3])
            if value < 22:
                pixels[x, y] = (0, 0, 0)
            else:
                pixels[x, y] = (min(255, 80 + value),
                                min(255, 120 + value), 255)
    return out


def build_item_icon(source):
    """One 16x16 RGB555 pickup icon from an original 32x32 item icon.

    The inventory icons are the game's own artwork for exactly these two items,
    so nothing here is drawn by hand. Alpha becomes the sprite's transparent
    colour: VDP1 treats 0x0000 as see-through, so every texel the icon leaves
    clear is forced to black, and any genuinely black icon pixel is nudged up
    one step so it stays visible instead of punching a hole.
    """
    icon = source.convert('RGBA').resize((16, 16), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (16, 16))
    pixels, src = out.load(), icon.load()
    for y in range(16):
        for x in range(16):
            r, g, b, a = src[x, y]
            if a < 96:
                pixels[x, y] = (0, 0, 0)
            else:
                pixels[x, y] = (max(r, 8), max(g, 8), max(b, 8))
    return out


def build_menu_icon(source, size=32):
    """One 32x32 RGB555 menu icon, the size Kaleido's grid actually draws.

    EQUIP_GRID_QUAD_TEX_SIZE is 32 in z_kaleido_scope.h, so the pause grid uses
    the icon at its native resolution -- no downscale, unlike the 16x16 world
    pickup billboards.
    """
    icon = source.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (size, size))
    pixels, src = out.load(), icon.load()
    for y in range(size):
        for x in range(size):
            r, g, b, a = src[x, y]
            if a < 96:
                pixels[x, y] = (0, 0, 0)
            else:
                pixels[x, y] = (max(r, 8), max(g, 8), max(b, 8))
    return out


# The panel is stored far smaller than the original 128x64 and stretched back
# up by VDP1. It is a smooth gradient with no detail to lose, and VDP1 texture
# VRAM is the binding constraint on this project: the tightest resident room
# leaves under 5 KB spare, and a 128x64 RGB555 copy is 16 KB on its own --
# enough to push the forest bank over the budget and fail the scene load.
MESSAGE_BOX_WIDTH = 32
MESSAGE_BOX_HEIGHT = 16


def build_message_box(source, width=MESSAGE_BOX_WIDTH, height=MESSAGE_BOX_HEIGHT):
    """The real message panel, gDefaultMessageBackgroundTex.

    An I4 texture: intensity only. In the original it is drawn translucent over
    the scene; VDP1 has no per-texel alpha, so the intensity is mapped to a
    dark neutral ramp. The renderer applies VDP1 mesh dithering to this panel.
    Dialogue uses bright cyan rather than dark blue for contrast.

    The darkest texels are lifted off pure black, because VDP1 treats a zero
    texel as transparent and the panel would be full of holes.
    """
    panel = source.convert('L').resize((width, height), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (width, height))
    pixels, src = out.load(), panel.load()
    for y in range(height):
        for x in range(width):
            level = src[x, y]
            # Neutral charcoal keeps coloured dialogue readable over mesh.
            shade = max(8, level // 8)
            pixels[x, y] = (shade, shade, shade)
    return out


MESSAGE_PROMPT_SIZE = 16


def build_message_prompt(source, size=MESSAGE_PROMPT_SIZE):
    """OoT's continue triangle and end square.

    I4 intensity marks. The shape is the intensity, so it becomes plain white
    and everything around it stays black -- VDP1 drops a zero texel, which is
    what leaves the mark floating on the panel instead of in a box of its own.
    """
    mark = source.convert('L').resize((size, size), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (size, size))
    pixels, src = out.load(), mark.load()
    for y in range(size):
        for x in range(size):
            level = src[x, y]
            pixels[x, y] = (0, 0, 0) if level < 64 else (level, level, level)
    return out


def build_lock_reticle_corner(corner, colour, size=16, outline=None):
    """Rasterize one rotation of gLockOnReticleTriangleDL.

    The source display list is a single untextured right triangle at
    (-31,-31), (32,-31), (-31,32), rendered four times around focus.  Saturn
    uses compact RGB555 sprites, so preserve that geometry and the source
    attention colour while making black texels transparent for VDP1.
    """
    if corner not in range(4):
        raise ValueError('reticle corner must be 0..3')
    vertices = ((2, 2), (12, 2), (2, 12))
    if corner == 1:
        vertices = tuple((size - 1 - x, y) for x, y in vertices)
    elif corner == 2:
        vertices = tuple((size - 1 - x, size - 1 - y) for x, y in vertices)
    elif corner == 3:
        vertices = tuple((x, size - 1 - y) for x, y in vertices)
    out = Image.new('RGB', (size, size))
    pixels = out.load()
    (ax, ay), (bx, by), (cx, cy) = vertices
    area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    for y in range(size):
        for x in range(size):
            ab = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
            bc = (cx - bx) * (y - by) - (cy - by) * (x - bx)
            ca = (ax - cx) * (y - cy) - (ay - cy) * (x - cx)
            if (area > 0 and ab >= 0 and bc >= 0 and ca >= 0) or \
               (area < 0 and ab <= 0 and bc <= 0 and ca <= 0):
                pixels[x, y] = colour
    if outline is not None:
        # A one-texel dark rim keeps a light marker readable on bright scenery.
        # Near-black, not (0,0,0): RGB555 zero is VDP1's transparent code.
        inside = {(x, y) for y in range(size) for x in range(size)
                  if pixels[x, y] == colour}
        for y in range(size):
            for x in range(size):
                if (x, y) not in inside and any(
                        (x + dx, y + dy) in inside
                        for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                    pixels[x, y] = outline
    return out


def build_equip_outline(source, size=32):
    """The real EQUIPPED marker, gEquippedItemOutlineTex.

    An IA8 texture: intensity plus alpha, no colour of its own. Kaleido tints
    it, so the yellow is applied here rather than invented -- transparent texels
    stay black so VDP1 drops them and only the box outline draws.
    """
    mark = source.convert('RGBA').resize((size, size), Image.Resampling.LANCZOS)
    out = Image.new('RGB', (size, size))
    pixels, src = out.load(), mark.load()
    for y in range(size):
        for x in range(size):
            r, _g, _b, a = src[x, y]
            if a < 64:
                pixels[x, y] = (0, 0, 0)
            else:
                level = max(r, 8)
                pixels[x, y] = (level, level, max(8, level // 4))
    return out


def build_rupee_sprite(source, blue=False, red=False):
    """Original IA8 HUD silhouette; green uses OoT's prim/env colours.

    Blue is the slice's recolour for five-rupee billboards. N64 world rupees
    use geometry; these intentionally use the real HUD art as a sprite.
    """
    source = source.convert('RGBA')
    if source.size != (16, 16):
        raise ValueError('Unexpected rupee icon dimensions')
    prim, env = ((100, 180, 255), (0, 0, 80)) if blue else ((200, 255, 100), (0, 80, 0))
    if red: prim, env = (255,100,100), (80,0,0)
    out = Image.new('RGB', source.size)
    out.putdata([(tuple(max(8, e + (p-e)*r//255) for p,e in zip(prim,env))
                  if a >= 64 else (0,0,0)) for r,g,b,a in source.getdata()])
    return out


def main(oot=None):
    baseline = ROOT.parent / 'shared'
    data, header, _, _ = read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    start = header['collision_off']
    size = header['ncollision'] * 36
    collision = data[start:start + size]
    if len(collision) != size or not size:
        raise ValueError('Invalid collision extent')
    (ROOT / 'build/cd/FOREST.COL').write_bytes(collision)
    with Image.open(baseline / 'assets/static/ui/TITLE.TGA') as title:
        if title.size != (512, 256):
            raise ValueError('Unexpected title dimensions')
        pixels = title.convert('RGB').getdata()
        (ROOT / 'build/cd/TITLE.RGB').write_bytes(b''.join(struct.pack('>H', rgb555(p)) for p in pixels))
    (ROOT / 'build/cd/START.RGB').write_bytes((baseline / 'assets/static/ui/PRESS_START.RAW').read_bytes())
    if oot is None:
        oot = Path('D:/Workspace-Claude/game-decomps/n64/oot')
    candidates = sorted(Path(oot).glob(
        'extracted/*/assets/objects/gameplay_keep/gFairyWingTex.i8.png'))
    if not candidates:
        raise FileNotFoundError('extracted OoT fairy wing texture not found')
    with Image.open(candidates[-1]) as wing:
        fairy = build_fairy_sprite(wing)
    fairy.save(ROOT / 'build/generated/fairy-preview.png')
    (ROOT / 'build/cd/FAIRY.RGB').write_bytes(b''.join(
        struct.pack('>H', rgb555(pixel)) for pixel in fairy.getdata()))

    # En_Kusa type 0 draws gFieldBushDL with this original cutout texture.
    grass_path = Path(oot) / 'extracted/ntsc-1.2/assets/objects/gameplay_field_keep/gFieldBushTex.rgba16.png'
    with Image.open(grass_path) as source:
        grass = build_menu_icon(source, 32)
    grass.save(ROOT / 'build/generated/grass-preview.png')
    (ROOT / 'build/cd/GRASS.RGB').write_bytes(b''.join(
        struct.pack('>H', rgb555(pixel)) for pixel in grass.getdata()))

    # Original En_Item00 pickup textures, including previously omitted hearts.
    keep = Path(oot) / 'extracted/ntsc-1.2/assets/objects/gameplay_keep'
    for name, texture in (('DROPHE', 'gDropRecoveryHeartTex'),
                          ('DROPNUT', 'gDropDekuNutTex'),
                          ('DROPSTK', 'gDropDekuStickTex'),
                          ('DROPSED', 'gDropDekuSeedsTex')):
        with Image.open(keep / (texture + '.rgba16.png')) as source:
            # These gameplay_keep sprites are extracted with their rows in the
            # order the original display list samples them, which is bottom-up
            # for a VDP1 sprite.  The heart is the only one whose silhouette
            # makes it obvious (its point lands at the top), but the whole set
            # shares the convention, so all four are flipped, not just it.
            icon = build_item_icon(source.transpose(Image.FLIP_TOP_BOTTOM))
        (ROOT / ('build/cd/%s.RGB' % name)).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in icon.getdata()))

    hud = Path(oot) / 'extracted/ntsc-1.2/assets/textures/parameter_static'
    for name, blue, red in (('RUPEEG',False,False),('RUPEEB',True,False),('RUPEER',False,True)):
        with Image.open(hud / 'gRupeeCounterIconTex.ia8.png') as source:
            icon = build_rupee_sprite(source, blue, red)
        icon.save(ROOT / ('build/generated/%s-preview.png' % name.lower()))
        (ROOT / ('build/cd/%s.RGB' % name)).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in icon.getdata()))
    for digit in range(10):
        with Image.open(hud / ('gCounterDigit%dTex.i8.png' % digit)) as source:
            if source.size != (8,16):
                raise ValueError('Unexpected counter digit dimensions')
            # Intensity also supplies alpha in the original HUD combiner.
            pixels = [(v,v,v) if v >= 32 else (0,0,0) for v in source.convert('L').getdata()]
        (ROOT / ('build/cd/DIGIT%d.RGB' % digit)).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in pixels))

    # Gear pickup icons, from the original inventory artwork for these exact
    # two items. 16x16 RGB555 each, 512 bytes on the disc and in VDP1 VRAM --
    # the cheap visible marker, not a chest actor.
    icons = Path(oot) / 'extracted/ntsc-1.2/assets/textures/icon_item_static'
    for name, texture in (('SWORD', 'gItemIconSwordKokiriTex.rgba32.png'),
                          ('SHIELD', 'gItemIconShieldDekuTex.rgba32.png')):
        path = icons / texture
        if not path.is_file():
            raise FileNotFoundError('extracted OoT item icon missing: %s' % path)
        with Image.open(path) as source:
            icon = build_item_icon(source)
        icon.save(ROOT / ('build/generated/%s-preview.png' % name.lower()))
        (ROOT / ('build/cd/%s.RGB' % name)).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in icon.getdata()))
        # 32x32 copy for the pause grid, at Kaleido's own quad texture size.
        with Image.open(path) as source:
            big = build_menu_icon(source)
        (ROOT / ('build/cd/%sM.RGB' % name[:5])).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in big.getdata()))

    # The real message box, gDefaultMessageBackgroundTex. OoT draws this i4
    # texture as a dark panel behind cutscene and dialogue text. VDP1 has no
    # per-texel alpha, so the intensity becomes a dark blue-black ramp and the
    # panel is drawn solid -- the box reads as the original's, and the text on
    # it is legible over a bright scene, which is the whole point of it.
    box = (Path(oot) / 'extracted/ntsc-1.2/assets/textures/message_static'
           / 'gDefaultMessageBackgroundTex.i4.png')
    if not box.is_file():
        raise FileNotFoundError('extracted OoT message background missing')
    with Image.open(box) as source:
        panel = build_message_box(source)
    panel.save(ROOT / 'build/generated/messagebox-preview.png')
    (ROOT / 'build/cd/MSGBOX.RGB').write_bytes(b''.join(
        struct.pack('>H', rgb555(pixel)) for pixel in panel.getdata()))

    # The prompts that sit at the bottom of a box: OoT's own triangle when
    # another page follows, and its square when the message ends. I4 again, so
    # the intensity becomes a plain white mark.
    for name, texture in (('MSGNEXT', 'gMessageContinueTriangleTex.i4.png'),
                          ('MSGEND', 'gMessageEndSquareTex.i4.png')):
        path = (Path(oot) / 'extracted/ntsc-1.2/assets/textures/message_static'
                / texture)
        if not path.is_file():
            raise FileNotFoundError('extracted OoT message prompt missing: %s'
                                    % path)
        with Image.open(path) as source:
            mark = build_message_prompt(source)
        (ROOT / ('build/cd/%s.RGB' % name)).write_bytes(b''.join(
            struct.pack('>H', rgb555(pixel)) for pixel in mark.getdata()))

    # z_actor.c draws gLockOnReticleTriangleDL four times around focus. Its
    # vertices are source geometry, and its palette is sAttentionColors:
    # hostile yellow, NPC blue, other/POI green. White is the first-person
    # shot ray marker, intentionally separate from dialogue's message glyphs.
    reticles = (('RTEN', (255, 255, 0)), ('RTNP', (150, 150, 255)),
                ('RTPO', (0, 255, 0)), ('RTAI', (255, 255, 255)))
    for prefix, colour in reticles:
        for corner in range(4):
            # The first-person aim marker is white with a dark rim so it
            # reads on both bright and dark scenery.
            reticle = build_lock_reticle_corner(
                corner, colour, outline=(16, 16, 16) if prefix == 'RTAI' else None)
            (ROOT / ('build/cd/%s%02d.RGB' % (prefix, corner))).write_bytes(
                b''.join(struct.pack('>H', rgb555(pixel)) for pixel in reticle.getdata()))

    outline = (Path(oot) / 'extracted/ntsc-1.2/assets/textures/parameter_static'
               / 'gEquippedItemOutlineTex.ia8.png')
    if not outline.is_file():
        raise FileNotFoundError('extracted equipped-item outline missing')
    with Image.open(outline) as source:
        mark = build_equip_outline(source)
    mark.save(ROOT / 'build/generated/equipmark-preview.png')
    (ROOT / 'build/cd/EQUIP.RGB').write_bytes(b''.join(
        struct.pack('>H', rgb555(pixel)) for pixel in mark.getdata()))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--oot', type=Path)
    main(parser.parse_args().oot)
