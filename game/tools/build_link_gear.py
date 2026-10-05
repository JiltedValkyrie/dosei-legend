"""Bake adult Link's extra gear as small skinned meshes for the Link renderer.

Biggoron's Sword hand, Mirror Shield hand, Mirror Shield on the back and the
Iron/Hover boot pairs come from the real object_link_boy display lists
(z_player_lib.c gPlayerLeftHandBgsDLs, sBootDListGroups, ...). Each group keeps
its own vertex range so the runtime skins only the gear Link is wearing, with
the same limb-local skin math as Link (link_anim.c skin_vertices), and draws
it in Link's matrix: exact joints, original textures, per-polygon depth.

Outputs (cd): LGEARMSH.BIN (POLYGON then ATTR, indices relative to each
group's first vertex), LGEARTEX.BIN (tile descriptors then CLUTs), LGEAR.TEX
(4bpp pixels), LGEARSKN.BIN:
    'LGR1', u16 vertices, polygons, tiles, pad, u32 pixel bytes,
    GROUPS x { u16 poly_first, poly_count, vert_first, vert_count },
    u8 owners[vertices] (pad to 4), s16 local[vertices][3].
Header (out): link_gear.h.
"""
import argparse
from pathlib import Path
import struct
import tempfile
import xml.etree.ElementTree as ET

import build_link_model as link
import build_sgl_scene as sgl

# (group, limb, display list). Limbs are imported indices (PLAYER_LIMB - 1):
# 15 L hand, 18 R hand, 19 sheath, 5 R foot, 8 L foot. Boots replace the foot
# limb's list only to walk the boot list in that limb's matrix context; the
# foot itself stays in Link's body group (the boots draw in addition).
GROUPS = (
    # Hero weapons keep their original textures (human 2026-10-04); Link's own
    # mesh stays flat-shaded per the character rule, so these replace its hand
    # and back variants for the adult.
    ('left_master', ((15, 'gLinkAdultLeftHandHoldingMasterSwordFarDL'),)),
    ('right_hylian', ((18, 'gLinkAdultRightHandHoldingHylianShieldFarDL'),)),
    ('sheath_master', ((19, 'gLinkAdultMasterSwordAndSheathFarDL'),)),
    ('sheath_hylian', ((19, 'gLinkAdultHylianShieldSwordAndSheathFarDL'),)),
    ('left_bgs', ((15, 'gLinkAdultLeftHandHoldingBgsFarDL'),)),
    ('right_mirror', ((18, 'gLinkAdultRightHandHoldingMirrorShieldFarDL'),)),
    ('sheath_mirror', ((19, 'gLinkAdultMirrorShieldSwordAndSheathFarDL'),)),
    ('boots_iron', ((5, 'gLinkAdultRightIronBootDL'), (8, 'gLinkAdultLeftIronBootDL'))),
    ('boots_hover', ((5, 'gLinkAdultRightHoverBootDL'), (8, 'gLinkAdultLeftHoverBootDL'))),
    # Shield on the back with an empty sheath (no sword owned/equipped).
    ('back_hylian', ((19, 'gLinkAdultHylianShieldAndSheathFarDL'),)),
    ('back_mirror', ((19, 'gLinkAdultMirrorShieldAndSheathFarDL'),)),
)
POINTS_CARVE = 0x2000   # ram_low.h RAM_LOW_LINK_GEAR_POINTS_BYTES (12 B per vertex)


def gear_faces(oot, rom_dir):
    obj = link.read_object(oot, 'object_link_boy', rom_dir)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    anim = link.read_object(oot, 'link_animetion', rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects/object_link_boy.xml')
    table = next(int(e.attrib['Offset'], 0) for e in xml.iter('LimbTable')
                 if e.attrib['Name'] == 'gLinkAdultLimbs')
    limbs = link.read_limbs(obj, table)
    _, root, rotations = link.read_animation(keep, anim, link.IDLE_ANIMATION, 0, 21)
    placed = link.walk_skeleton(limbs, rotations, root)
    rows = tuple((group, limb, symbol) for group, parts in GROUPS for limb, symbol in parts)
    faces, base = link.collect_equipment(obj, keep, placed, oot, 'object_link_boy', rows)
    faces = [f for f in faces if f['group'] != 'body']
    # Hero metal and shield faces keep an 8x8 baked texture per face (VRAM); the hand/gauntlet
    # skin in these lists and the boots stay flat like the rest of Link (boot
    # artwork would add ~200 tiles to each room's actor bank).
    hand = {int(e.attrib['Offset'], 0) for e in xml.iter('Texture')
            if any(k in e.attrib['Name'] for k in ('Hand', 'Gauntlet'))}
    for face in faces:
        image = face.get('image')
        face['full_texture'] = (not face['group'].startswith('boots') and image is not None and
                                (image & 0xFFFFFF) not in hand)
        face['tile_size'] = 8
        # The hand lists leave the skin primitive colour (255,205,225) set;
        # in the original it only tints skin, so metal/shield art stays raw.
        if face['full_texture']:
            face['prim'] = (255, 255, 255, 255)
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, .01)
    _, shift = link.ground_and_centre(link.scale_faces(base, .01))
    for face in faces:
        face['vertices'] = [tuple(v[i] + shift[i] for i in range(3)) + tuple(v[3:])
                            for v in face['vertices']]
    return faces


def build(oot, rom_dir, out, cd):
    out.mkdir(parents=True, exist_ok=True)
    cd.mkdir(parents=True, exist_ok=True)
    faces = gear_faces(oot, rom_dir)
    polygons, attributes, owners, locals_ = bytearray(), bytearray(), bytearray(), []
    pixels, descriptors, palettes = bytearray(), bytearray(), bytearray()
    ranges, tile_count, poly_total, vert_total = [], 0, 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        for group, _parts in GROUPS:
            chosen = [dict(f) for f in faces if f['group'] == group]
            if not chosen:
                raise ValueError('Link gear group has no faces: ' + group)
            path = Path(tmp) / (group + '.BIN')
            _, _, group_owners, group_local = link.write_model(chosen, path, skinned=True, character=False)
            data, head, vertices, records = sgl.read_scene(path)
            tiles = sgl.collect_tiles(data, head, records)
            baked = [(x, -y, z) for x, y, z in vertices]
            # Flat-colour faces become plain VDP1 polygons (texno 0xFFFF, colno
            # = RGB555; kokiri_sgl.c gear_load rewrites the ATTR): no tile, no
            # VRAM, no sprite slot. Only real artwork keeps a tile.
            remap = {}
            for face in records:
                tile = tiles[face['tex_off']]
                flat = tile['width'] == 8 and tile['height'] == 2 and set(tile['pixels']) <= {0x11}
                polygons.extend(struct.pack('>3i4H', *sgl.face_normal(baked, face['idx']), *face['idx']))
                if flat:
                    attributes.extend(struct.pack('>BB5H', 1, 0x67, 0xFFFF, 0x88, tile['clut'][1] | 0x8000, 0, 4))
                    continue
                key = face['tex_off']
                if key not in remap:
                    remap[key] = tile_count + len(remap)
                    descriptors.extend(struct.pack('>HHII', tile['width'], tile['height'],
                                                   len(pixels), len(tile['pixels'])))
                    pixels.extend(tile['pixels'])
                    pixels.extend(bytes((-len(pixels)) % 8))
                    palettes.extend(struct.pack('>16H', *tile['clut']))
                attributes.extend(struct.pack('>BB5H', 1, 0x67, remap[key],
                                              0x88 | (0x100 if face['mesh'] else 0), 0, 0, 2))
            ranges.append((poly_total, len(records), vert_total, len(group_owners)))
            owners.extend(group_owners)
            locals_.extend(group_local)
            poly_total += len(records)
            vert_total += len(group_owners)
            tile_count += len(remap)
    skin = bytearray(struct.pack('>4sHHHHI', b'LGR1', vert_total, poly_total, tile_count, 0, len(pixels)))
    for row in ranges:
        skin.extend(struct.pack('>4H', *row))
    skin.extend(owners)
    skin.extend(bytes((-len(skin)) % 4))
    for point in locals_:
        skin.extend(struct.pack('>3h', *point))
    # Worst simultaneous set: one left hand, one right hand, one back, boots.
    n = {g: r[3] for (g, _), r in zip(GROUPS, ranges)}
    peak = (max(n['left_master'], n['left_bgs']) + max(n['right_hylian'], n['right_mirror']) +
            max(n['sheath_master'], n['sheath_hylian'], n['sheath_mirror'], n['back_hylian'], n['back_mirror']) +
            max(n['boots_iron'], n['boots_hover']))
    if peak * 12 > POINTS_CARVE:
        raise ValueError('Link gear exceeds its pose-point carve')
    (cd / 'LGEARMSH.BIN').write_bytes(polygons + attributes)
    (cd / 'LGEARTEX.BIN').write_bytes(descriptors + palettes)
    (cd / 'LGEAR.TEX').write_bytes(pixels)
    (cd / 'LGEARSKN.BIN').write_bytes(skin)
    values = dict(VERTEX_COUNT=vert_total, POLYGON_COUNT=poly_total, TILE_COUNT=tile_count,
                  PIXEL_BYTES=len(pixels), MESH_BYTES=len(polygons) + len(attributes),
                  TEX_BYTES=len(descriptors) + len(palettes), SKIN_BYTES=len(skin))
    (out / 'link_gear.h').write_text('/* Generated by tools/build_link_gear.py: adult gear meshes. */\n' +
        '\n'.join('#define LINK_GEAR_%s %du' % row for row in values.items()) +
        '\n#define LINK_GEAR_GROUPS %du\n' % len(GROUPS))
    print('Link gear:', values, 'groups', ranges)
    return values


if __name__ == '__main__':
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=root / 'build/generated')
    ap.add_argument('--cd', type=Path, default=root / 'build/cd')
    args = ap.parse_args()
    build(args.oot, args.rom_dir, args.out, args.cd)
