"""Source ItemId icon atlas and current-world-area metadata for pause UI.

One bounded I4 atlas replaces exponential ownership-page variants. Original
item IDs index fixed records; source quest positions and scene area commands
remain offline data, not tables consuming high work RAM.
"""
import re
import struct
from PIL import Image

ICON_SIZE = 28
RECORD_BYTES = 32 + 32 + ICON_SIZE * ICON_SIZE // 2
META_BYTES = 24 * 6 + 124 * 4
SONGS = ("Minuet of Forest", "Bolero of Fire", "Serenade of Water",
         "Requiem of Spirit", "Nocturne of Shadow", "Prelude of Light",
         "Zelda's Lullaby", "Epona's Song", "Saria's Song", "Sun's Song",
         "Song of Time", "Song of Storms")


def numbers(source, name):
    body = source.split(name + '[] = {', 1)[1].split('};', 1)[0]
    return [int(v) for v in re.findall(r'^\s*(-?\d+)\s*,', body, re.M)]


def item_icons(oot):
    src = (oot/'src/code/z_inventory.c').read_text(encoding='utf-8')
    body = src.split('void* gItemIcons[] = {', 1)[1].split('};', 1)[0]
    return re.findall(r'^\s*(g\w+),\s*// (ITEM_\w+)', body, re.M)[:122]


def encode_icon(image):
    image = image.resize((ICON_SIZE, ICON_SIZE), Image.Resampling.LANCZOS)
    pal = image.convert('RGB').quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    rgb = pal.getpalette()[:45]
    palette = [0] + [0x8000 | (rgb[i] >> 3) | (rgb[i+1] >> 3) << 5 |
                     (rgb[i+2] >> 3) << 10 for i in range(0, 45, 3)]
    pixels = [p+1 if rgba[3] >= 128 else 0 for p, rgba in zip(pal.getdata(), image.getdata())]
    return struct.pack('>16H', *palette) + bytes((pixels[i] << 4) | pixels[i+1]
                                                for i in range(0, len(pixels), 2))


def build(oot, cd, out, load_texture):
    textures = oot/'extracted/ntsc-1.2/assets/textures'
    scope = (oot/'src/overlays/misc/ovl_kaleido_scope/z_kaleido_scope.c').read_text(encoding='utf-8')
    collect = (oot/'src/overlays/misc/ovl_kaleido_scope/z_kaleido_collect.c').read_text(encoding='utf-8')
    map_source = (oot/'src/overlays/misc/ovl_kaleido_scope/z_kaleido_map.c').read_text(encoding='utf-8')
    xs, ys = numbers(scope, 'sQuestQuadsX'), numbers(scope, 'sQuestQuadsY')
    song_rgb = [numbers(collect, 'sSongsPrim'+c) for c in ('Red','Green','Blue')]
    blob = bytearray()
    for q in range(24):
        item = 0x66+q if q < 6 else 0x5a+q-6 if q < 18 else 0x6c+q-18
        # Source notes use a narrow 16x24 quad; medallions/stones use 24x24.
        w, h = (16, 24) if 6 <= q < 18 else (24, 24)
        blob += struct.pack('>H4B', item, 160+xs[q], 120-ys[q], w, h)
    ax, ay = numbers(map_source, 'areaBoxPosX'), numbers(map_source, 'areaBoxPosY')
    aw, ah = numbers(map_source, 'areaBoxWidths'), numbers(map_source, 'areaBoxHeights')
    scene_table = (oot/'include/tables/scene_table.h').read_text(encoding='utf-8')
    rows = re.findall(r'/\* 0x([0-9A-Fa-f]+) \*/ DEFINE_SCENE\((\w+),', scene_table)
    centers = [(0, 0)] * 124
    scenes = oot/'extracted/ntsc-1.2/assets/scenes'
    files = {p.name: p for p in scenes.rglob('*_scene.inc.c')}
    for idx, prefix in rows:
        path = files.get(prefix+'.inc.c')
        if path is None:
            continue
        match = re.search(r'SCENE_CMD_MISC_SETTINGS\([^,]+,\s*(\d+)\)', path.read_text(encoding='utf-8'))
        area = int(match[1]) if match else 255
        if area < len(ax):
            # Same 216x128 source image -> 288x171 viewport as world page.
            centers[int(idx,16)] = (16 + (108+ax[area]+aw[area]//2)*288//216,
                                    32 + (61-ay[area]+ah[area]//2)*171//128)
    for center in centers:
        blob += struct.pack('>HH', *center)
    icons = item_icons(oot)
    for item, (texture, token) in enumerate(icons):
        image = load_texture(textures, texture)
        name = token.removeprefix('ITEM_').replace('_', ' ').title()
        if 0x5a <= item < 0x66:
            q = item-0x5a
            name = SONGS[q]
            image.putdata([(r*song_rgb[0][q]//255, g*song_rgb[1][q]//255,
                            b*song_rgb[2][q]//255, a) for r,g,b,a in image.getdata()])
        label = name.encode('ascii')[:31]
        blob += label + bytes(32-len(label)) + encode_icon(image)
    assert len(blob) == META_BYTES + len(icons)*RECORD_BYTES
    (cd/'PAUSEINV.BIN').write_bytes(blob)
    (out/'pause_inventory_data.h').write_text(
        '/* Source ItemId I4 icons, quest layout and scene world areas. */\n'
        f'#define PAUSE_ICON_COUNT {len(icons)}u\n'
        f'#define PAUSE_ICON_RECORD {RECORD_BYTES}u\n'
        f'#define PAUSE_ICON_META {META_BYTES}u\n'
        f'#define PAUSE_ICON_BYTES {len(blob)}u\n')
