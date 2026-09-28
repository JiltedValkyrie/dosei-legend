#!/usr/bin/env python
"""Kokiri Shop props, original display lists in native world units.

En_Tana params 0 (z_en_tana.c): gShopDungenWoodenShelvesDL from
object_shop_dungen, Actor_SetScale 1.0, so its vertices are world units
already. Textured: props are not characters (character texture rule).
"""
import argparse
import pathlib
import struct
import xml.etree.ElementTree as ET

import build_link_model as link


# En_GirlA shelf items in the Kokiri Shop (sShopkeeperStores[0]); the GID
# display list each one's GetItem_Draw uses (z_draw.c sDrawItemTable).
# EnGirlA_Update2: Actor_SetScale 0.25. Segment 8 is a texture-scroll list in
# GetItem_DrawRecoveryHeart/DrawDekuNuts: baked primary-texture scroll tracks.
ITEMS = (
    ('ITEMSHLD.BIN', 'object_gi_shield_1', 'gGiDekuShieldDL'),
    ('ITEMNUTS.BIN', 'object_gi_nuts', 'gGiNutDL'),
    ('ITEMSTCK.BIN', 'object_gi_stick', 'gGiStickDL'),
    ('ITEMSEED.BIN', 'object_gi_seed', 'gGiSeedDL'),
    ('ITEMARR5.BIN', 'object_gi_arrow', 'gGiArrowSmallDL'),
    ('ITEMARRM.BIN', 'object_gi_arrow', 'gGiArrowMediumDL'),
    ('ITEMHART.BIN', 'object_gi_heart', 'gGiRecoveryHeartDL'),
)
ITEM_SCALE = 0.25


class PropLists(link.LimbLists):
    """Only faces after the source segment-8 scroll list animate (nut cap)."""
    scrolling = False
    def walk(self,address,transparent=False,depth=0):
        if address == 0x08000000:
            self.scrolling = True
        return super().walk(address,transparent,depth)
    def triangle(self,word,transparent):
        first=len(self.faces)
        super().triangle(word,transparent)
        for face in self.faces[first:]:face['scrolling']=self.scrolling

def static_mesh(oot, rom_dir, obj, symbol, dest, scale=1.0, setup=None, extra=(), flat=False):
    data = link.read_object(oot, obj, rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
    offsets = {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in xml.iter('DList')}
    lists = PropLists(b'', b'')
    segment = int(next(xml.iter("File")).attrib.get("Segment", "6"), 0)
    lists.segments = {segment: data, 8: struct.pack('>II', 0xDF000000, 0)}
    if symbol in ('gGiNutDL','gGiRecoveryHeartDL') or obj == 'object_kanban':
        lists.segments[4] = link.read_object(oot, 'gameplay_keep', rom_dir)
    lists.current_limb = 0
    lists.matrix_limbs = []
    if setup: lists.walk((segment << 24) | offsets[setup])
    lists.walk((segment << 24) | offsets[symbol])
    for tail in extra: lists.walk((segment << 24) | offsets[tail])
    for face in lists.faces:
        face['limb'] = 0
        face['full_texture'] = not flat
    # Props keep gameplay_keep textures; the character tint helper deliberately
    # flattens segment-4 materials, which would erase the heart's scrolling art.
    for face in lists.faces:
        if face.get('texture_segment') == 4: face['texture_segment'] = 6
    link.apply_primitive_colour(lists.faces)
    if flat: link.flatten_faces(lists.faces)
    faces = link.scale_faces(lists.faces, scale) if scale != 1.0 else lists.faces
    positions, tiles, _owners, _locals = link.write_model(faces, dest, character=False)
    if not flat and symbol in ('gGiNutDL', 'gGiRecoveryHeartDL'):
        # Bake the source scrolling UVs per face, preserving its UV mapping;
        # rotating a baked triangle's pixels would produce false edge seams.
        # Saturn baker keeps the primary texture; N64 two-cycle combine remains
        # the existing material approximation, not a second texture layer.
        frames = 32
        animated = [(i, f) for i, f in enumerate(faces) if f.get('scrolling')]
        if not animated: raise ValueError('source item has no segment-8 faces')
        scroll = bytearray(struct.pack('>III', 0x4B545331, frames, len(animated)))
        scroll.extend(struct.pack('>%dI' % len(animated), *(i for i,f in animated)))
        for frame in range(frames):
            for _, face in animated:
                moved = dict(face)
                moved['texture'] = dict(face['texture'])
                ds, dt = ((6*frame,6*frame) if symbol == 'gGiNutDL' else (0,-3*frame))
                moved['texture']['uls'] += (ds%32)*4
                moved['texture']['ult'] += (dt%32)*4
                scroll.extend(link.scene_tool.bake(moved,16))
        dest.with_suffix('.SCR').write_bytes(scroll)
    print('prop    : %s %s %d faces, %d tiles, %d bytes'
          % (dest.name, symbol, len(lists.faces), len(tiles), dest.stat().st_size))


def shop_cursor(oot, dest):
    """EnOssan_DrawCursor: gSelectionCursorTex (IA4 16x16) mirrored both ways
    into 32x32, PRIM (0,80,255,255) x intensity (N64 CURSOR_COLOR). Four
    baked steps of EnOssan_UpdateCursorAnim's tween t = 0, .25, .5, .75
    (ColChanMix toward (0,80,0,0)); the runtime fades the last ones with
    VDP1 half transparency. Big-endian RGB555, MSB = opaque."""
    from PIL import Image
    tex = Image.open(oot / 'extracted/ntsc-1.2/assets/objects/gameplay_keep/'
                     'gSelectionCursorTex.ia4.png').convert('RGBA')
    out = bytearray()
    for t in (0.0, 0.25, 0.5, 0.75):
        r, g, b = (0 + (0 - 0) * t, 80 + (80 - 80) * t, 255 + (0 - 255) * t)
        for y in range(32):
            for x in range(32):
                sx = x if x < 16 else 31 - x
                sy = y if y < 16 else 31 - y
                i, _, _, alpha = tex.getpixel((sx, sy))
                if alpha < 128:
                    out += bytes(2)
                    continue
                c = [round(v * i / 255 / 255 * 31) for v in (r, g, b)]
                out += struct.pack('>H', 0x8000 | c[2] << 10 | c[1] << 5 | c[0])
    dest.write_bytes(bytes(out))
    print('prop    : %s selection cursor, 4 x 32x32 RGB' % dest.name)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'build/cd')
    args = ap.parse_args()
    static_mesh(args.oot, args.rom_dir, 'object_shop_dungen',
                'gShopDungenWoodenShelvesDL', args.out / 'SHELVES.BIN')
    for name, obj, symbol in ITEMS:
        static_mesh(args.oot, args.rom_dir, obj, symbol, args.out / name, ITEM_SCALE, flat=True)
    shop_cursor(args.oot, args.out / 'CURSOR.RGB')


if __name__ == '__main__':
    main()
