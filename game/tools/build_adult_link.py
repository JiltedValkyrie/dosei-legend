"""Bake the real adult Link model for the existing shared Link renderer.

Geometry, limb ownership and bind offsets come from object_link_boy. Shared
player clips retain their unscaled adult root translations. The current action
list remains the gameplay backend's list; child-only crawl/climb action parity
is separate from this model/era switch.
"""
import argparse
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import build_link_model as link
import build_sgl_scene as sgl

GEAR = tuple((row[0], row[1], symbol) for row, symbol in zip(link.GEAR_LISTS, (
    'gLinkAdultLeftHandClosedFarDL', 'gLinkAdultLeftHandHoldingMasterSwordFarDL',
    'gLinkAdultRightHandClosedFarDL', 'gLinkAdultRightHandHoldingHylianShieldFarDL',
    'gLinkAdultSheathFarDL', 'gLinkAdultMasterSwordAndSheathFarDL',
    'gLinkAdultHylianShieldSwordAndSheathFarDL', 'gLinkAdultRightHandHoldingOotFarDL')))


def build(oot, rom_dir, out, cd):
    out.mkdir(parents=True, exist_ok=True)
    cd.mkdir(parents=True, exist_ok=True)
    obj = link.read_object(oot, 'object_link_boy', rom_dir)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    anim = link.read_object(oot, 'link_animetion', rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects/object_link_boy.xml')
    table = next(int(e.attrib['Offset'], 0) for e in xml.iter('LimbTable')
                 if e.attrib['Name'] == 'gLinkAdultLimbs')
    limbs = link.read_limbs(obj, table)
    _, root, rotations = link.read_animation(keep, anim, link.IDLE_ANIMATION, 0, 21)
    placed = link.walk_skeleton(limbs, rotations, root)
    faces, base = link.collect_equipment(obj, keep, placed, oot, 'object_link_boy', GEAR)
    link.character_textures.mark_faces(faces, oot / 'assets/xml/objects/object_link_boy.xml',
                                      link.HEAD_LIMB, link.FACE_SEGMENTS)
    link.flatten_faces(faces)
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, .01)
    _, shift = link.ground_and_centre(link.scale_faces(base, .01))
    for face in faces:
        face['vertices'] = [tuple(v[i] + shift[i] for i in range(3)) + tuple(v[3:])
                            for v in face['vertices']]
    path = out / 'ADULT.BIN'
    positions, _, owners, local = link.write_model(faces, path, skinned=True)
    data, head, vertices, records = sgl.read_scene(path)
    tiles = sgl.collect_tiles(data, head, records)
    from build_hybrid_scene import halve_texture_tiles
    import json
    tiles, halving = halve_texture_tiles(tiles, kind='actor')
    if halving['reductions']:
        (out / 'adult_texture_halving.json').write_text(json.dumps(halving, indent=2) + '\n')
    baked = [(x, -y, z) for x, y, z in vertices]
    mesh = bytearray()
    for face in records:
        mesh.extend(struct.pack('>3i4H', *sgl.face_normal(baked, face['idx']), *face['idx']))
    for face in records:
        mesh.extend(struct.pack('>BB5H', 1, 0x67, tiles[face['tex_off']]['index'],
                                0x88 | (0x100 if face['mesh'] else 0), 0, 0, 2))
    pixels, descriptors, palettes = bytearray(), bytearray(), bytearray()
    for tile in tiles.values():
        descriptors.extend(struct.pack('>HHII', tile['width'], tile['height'], len(pixels), len(tile['pixels'])))
        pixels.extend(tile['pixels'])
        pixels.extend(bytes((-len(pixels)) % 8))
        palettes.extend(struct.pack('>16H', *tile['clut']))
    (cd / 'ADLTMESH.BIN').write_bytes(mesh)
    (cd / 'ADLTTEX.BIN').write_bytes(descriptors + palettes)
    (cd / 'ADULT.TEX').write_bytes(pixels)

    offsets = link.resolve_animations(oot, keep, link.IDLE_ANIMATION)
    layout, rows = [], []
    for name, symbol, first, count, stride in link.CLIPS:
        _, sampled = link.read_animation_frames(keep, anim, offsets[symbol], first, count, stride, 21)
        layout.append((len(rows), len(sampled)))
        rows.extend((root, rot) if name == 'fall' else (r, rot) for r, rot in sampled)
    digest = link.write_frame_file(cd / 'ADULTANM.BIN', rows, 21, layout)
    groups = ['body'] + [g for g, _, _ in GEAR]
    ranges = []
    for group in groups:
        indices = [i for i, face in enumerate(faces) if face['group'] == group]
        if indices != list(range(indices[0], indices[-1] + 1)):
            raise ValueError('Non-contiguous adult equipment: ' + group)
        ranges.append((indices[0], len(indices)))
    counts = dict(zip(groups, (count for _, count in ranges)))
    visible = counts['body'] + max(counts['left_empty'], counts['left_sword']) + \
        max(counts['right_empty'], counts['right_shield'], counts['rh_ocarina']) + \
        max(counts['sheath'], counts['sheath_sword'], counts['sheath_shield'])
    skin = bytearray(40)
    for first, count in ranges:
        skin.extend(struct.pack('>HH', first, count))
    for limb in limbs:
        skin.extend(struct.pack('>BB3h', limb['child'], limb['sibling'], *limb['pos']))
    skin.extend(bytes(owners))
    skin.extend(bytes((-len(skin)) % 4))
    for point in local:
        skin.extend(struct.pack('>3h', *point))
    mask = bytearray((len(faces) + 7) // 8)
    # Adult tunic material: prim = sTunicColors Kokiri (30,105,27), not the
    # child's (80,188,8). An empty mask silently disables tunic colours.
    for i, face in enumerate(faces):
        if tuple(face.get('prim', ())[:3]) == (30, 105, 27):
            mask[i // 8] |= 1 << (i % 8)
    if not any(mask):
        raise ValueError('Adult Link source tunic material missing')
    skin.extend(mask)
    struct.pack_into('>8I3hH', skin, 0, 0x4C415331, len(skin), len(positions), len(faces),
                     len(tiles), len(pixels), digest, len(rows), *shift, visible)
    if len(mesh) + 1 > 0x6400 or len(descriptors + palettes) + 1 > 0x2000 or len(skin) + 1 > 0x2000:
        raise ValueError('Adult Link exceeds the shared model/texture/skin carve')
    if len(positions) * 12 > 0x2000 or visible * 20 > 0x3000 or visible * 12 > 0x2000:
        raise ValueError('Adult Link exceeds shared pose/equipment buffers')
    (cd / 'ADULTSKN.BIN').write_bytes(skin)
    values = dict(VERTEX_COUNT=len(positions), POLYGON_COUNT=len(faces), TILE_COUNT=len(tiles),
                  PIXEL_BYTES=len(pixels), MESH_BYTES=len(mesh), TEX_BYTES=len(descriptors + palettes),
                  SKIN_BYTES=len(skin), VISIBLE_POLYGONS=visible, FRAME_COUNT=len(rows), FRAMES_DIGEST=digest)
    (out / 'adult_link.h').write_text('/* Generated real object_link_boy layout; shared renderer. */\n' +
        '\n'.join('#define ADULT_LINK_%s %du' % row for row in values.items()) + '\n')
    print('Adult Link:', values, 'shift', shift)
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
