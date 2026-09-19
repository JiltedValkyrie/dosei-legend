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


def build_rupee_sprite(source, blue=False):
    """Original IA8 HUD silhouette; green uses OoT's prim/env colours.

    Blue is the slice's recolour for five-rupee billboards. N64 world rupees
    use geometry; these intentionally use the real HUD art as a sprite.
    """
    source = source.convert('RGBA')
    if source.size != (16, 16):
        raise ValueError('Unexpected rupee icon dimensions')
    prim, env = ((100, 180, 255), (0, 0, 80)) if blue else ((200, 255, 100), (0, 80, 0))
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

    hud = Path(oot) / 'extracted/ntsc-1.2/assets/textures/parameter_static'
    for name, blue in (('RUPEEG', False), ('RUPEEB', True)):
        with Image.open(hud / 'gRupeeCounterIconTex.ia8.png') as source:
            icon = build_rupee_sprite(source, blue)
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
