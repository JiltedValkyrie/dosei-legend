#!/usr/bin/env python3
"""Export Link's body and every gear display list to Mesh Workshop OBJs.

Real US 1.2 object_link_child / object_link_boy display lists (the same DL
walker as build_link_model.py / build_link_gear.py), posed in the idle frame
on the real skeleton, so held items sit in Link's hand and boots on his feet.
Output: workspace/meshes/link/<child|adult>/<kind>/<item>.obj (+ .mtl, PNGs).
Mesh Workshop lists these as types "Link (Child)" and "Link (Adult)".

Reference/editing exports only: the game build does not read these files.
Far LOD is exported (what the Saturn Link renderer uses); Near only when an
item has no Far list. Items whose list draws outside the skeleton (bottle,
strings, hookshot chain/tip, masks, gauntlet plates, bracelet) are posed on the
limb named in the table below.
"""
import argparse
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

from PIL import Image

import build_link_model as link

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / 'workspace/meshes/link'
L_HAND, R_HAND, SHEATH, HEAD, R_FOOT, L_FOOT, L_ARM = 15, 18, 19, 10, 5, 8, 14

# (kind, item, limb, DL). Limb = PLAYER_LIMB_* - 1. None = whole body.
CHILD = [
    ('body', 'child_link', None, None),
    ('swords', 'kokiri_sword_in_hand', L_HAND, 'gLinkChildLeftFistAndKokiriSwordFarDL'),
    ('swords', 'master_sword_in_hand_child', L_HAND, 'gLinkChildLeftHandHoldingMasterSwordDL'),
    ('swords', 'kokiri_sword_in_sheath', SHEATH, 'gLinkChildSwordAndSheathFarDL'),
    ('sheaths', 'empty_sheath', SHEATH, 'gLinkChildSheathFarDL'),
    ('shields', 'deku_shield_in_hand', R_HAND, 'gLinkChildRightFistAndDekuShieldFarDL'),
    ('shields', 'deku_shield_on_back_with_sword', SHEATH, 'gLinkChildDekuShieldSwordAndSheathFarDL'),
    ('shields', 'deku_shield_on_back', SHEATH, 'gLinkChildDekuShieldAndSheathFarDL'),
    ('shields', 'hylian_shield_on_back_with_sword', SHEATH, 'gLinkChildHylianShieldSwordAndSheathFarDL'),
    ('shields', 'hylian_shield_on_back', SHEATH, 'gLinkChildHylianShieldAndSheathFarDL'),
    ('shields', 'deku_shield_alone', R_HAND, 'gLinkChildDekuShieldDL'),
    ('tools', 'deku_stick', L_HAND, 'gLinkChildLinkDekuStickDL'),
    ('tools', 'boomerang_in_hand', L_HAND, 'gLinkChildLeftFistAndBoomerangFarDL'),
    ('tools', 'slingshot_in_hand', R_HAND, 'gLinkChildRightHandHoldingSlingshotFarDL'),
    ('tools', 'slingshot_string', R_HAND, 'gLinkChildSlingshotStringDL'),
    ('tools', 'fairy_ocarina_in_hand', R_HAND, 'gLinkChildRightHandHoldingFairyOcarinaFarDL'),
    ('tools', 'ocarina_of_time_in_hand', R_HAND, 'gLinkChildRightHandHoldingOOTFarDL'),
    ('tools', 'bottle', L_HAND, 'gLinkChildBottleDL'),
    ('tools', 'goron_bracelet', L_ARM, 'gLinkChildGoronBraceletDL'),
    ('hands', 'left_fist', L_HAND, 'gLinkChildLeftFistFarDL'),
    ('hands', 'left_hand_up', L_HAND, 'gLinkChildLeftHandUpFarDL'),
    ('hands', 'right_hand_closed', R_HAND, 'gLinkChildRightHandClosedFarDL'),
    ('masks', 'keaton_mask', HEAD, 'gLinkChildKeatonMaskDL'),
    ('masks', 'skull_mask', HEAD, 'gLinkChildSkullMaskDL'),
    ('masks', 'spooky_mask', HEAD, 'gLinkChildSpookyMaskDL'),
    ('masks', 'bunny_hood', HEAD, 'gLinkChildBunnyHoodDL'),
    ('masks', 'goron_mask', HEAD, 'gLinkChildGoronMaskDL'),
    ('masks', 'zora_mask', HEAD, 'gLinkChildZoraMaskDL'),
    ('masks', 'gerudo_mask', HEAD, 'gLinkChildGerudoMaskDL'),
    ('masks', 'mask_of_truth', HEAD, 'gLinkChildMaskOfTruthDL'),
]
ADULT = [
    ('body', 'adult_link', None, None),
    ('swords', 'master_sword_in_hand', L_HAND, 'gLinkAdultLeftHandHoldingMasterSwordFarDL'),
    ('swords', 'biggoron_sword_in_hand', L_HAND, 'gLinkAdultLeftHandHoldingBgsFarDL'),
    ('swords', 'giants_knife_broken_in_hand', L_HAND, 'gLinkAdultHandHoldingBrokenGiantsKnifeFarDL'),
    ('swords', 'giants_knife_broken_blade', L_HAND, 'gLinkAdultBrokenGiantsKnifeBladeDL'),
    ('swords', 'master_sword_in_sheath', SHEATH, 'gLinkAdultMasterSwordAndSheathFarDL'),
    ('sheaths', 'empty_sheath', SHEATH, 'gLinkAdultSheathFarDL'),
    ('shields', 'hylian_shield_in_hand', R_HAND, 'gLinkAdultRightHandHoldingHylianShieldFarDL'),
    ('shields', 'mirror_shield_in_hand', R_HAND, 'gLinkAdultRightHandHoldingMirrorShieldFarDL'),
    ('shields', 'hylian_shield_on_back_with_sword', SHEATH, 'gLinkAdultHylianShieldSwordAndSheathFarDL'),
    ('shields', 'hylian_shield_on_back', SHEATH, 'gLinkAdultHylianShieldAndSheathFarDL'),
    ('shields', 'mirror_shield_on_back_with_sword', SHEATH, 'gLinkAdultMirrorShieldSwordAndSheathFarDL'),
    ('shields', 'mirror_shield_on_back', SHEATH, 'gLinkAdultMirrorShieldAndSheathFarDL'),
    ('boots', 'iron_boot_right', R_FOOT, 'gLinkAdultRightIronBootDL'),
    ('boots', 'iron_boot_left', L_FOOT, 'gLinkAdultLeftIronBootDL'),
    ('boots', 'hover_boot_right', R_FOOT, 'gLinkAdultRightHoverBootDL'),
    ('boots', 'hover_boot_left', L_FOOT, 'gLinkAdultLeftHoverBootDL'),
    ('tools', 'megaton_hammer_in_hand', L_HAND, 'gLinkAdultLeftHandHoldingHammerFarDL'),
    ('tools', 'bow_in_hand', R_HAND, 'gLinkAdultRightHandHoldingBowFarDL'),
    ('tools', 'bow_first_person', R_HAND, 'gLinkAdultRightHandHoldingBowFirstPersonDL'),
    ('tools', 'bow_string', R_HAND, 'gLinkAdultBowStringDL'),
    ('tools', 'hookshot_in_hand', R_HAND, 'gLinkAdultRightHandHoldingHookshotFarDL'),
    ('tools', 'hookshot_chain', R_HAND, 'gLinkAdultHookshotChainDL'),
    ('tools', 'hookshot_tip', R_HAND, 'gLinkAdultHookshotTipDL'),
    ('tools', 'hookshot_reticle', R_HAND, 'gLinkAdultHookshotReticleDL'),
    ('tools', 'ocarina_of_time_in_hand', R_HAND, 'gLinkAdultRightHandHoldingOotFarDL'),
    ('tools', 'bottle', L_HAND, 'gLinkAdultBottleDL'),
    ('tools', 'hand_holding_bottle', L_HAND, 'gLinkAdultHandHoldingBottleDL'),
    ('gauntlets', 'left_gauntlet_plate_1', L_HAND, 'gLinkAdultLeftGauntletPlate1DL'),
    ('gauntlets', 'left_gauntlet_plate_2', L_HAND, 'gLinkAdultLeftGauntletPlate2DL'),
    ('gauntlets', 'left_gauntlet_plate_3', L_HAND, 'gLinkAdultLeftGauntletPlate3DL'),
    ('gauntlets', 'right_gauntlet_plate_1', R_HAND, 'gLinkAdultRightGauntletPlate1DL'),
    ('gauntlets', 'right_gauntlet_plate_2', R_HAND, 'gLinkAdultRightGauntletPlate2DL'),
    ('gauntlets', 'right_gauntlet_plate_3', R_HAND, 'gLinkAdultRightGauntletPlate3DL'),
    ('hands', 'left_hand_closed', L_HAND, 'gLinkAdultLeftHandClosedFarDL'),
    ('hands', 'right_hand_closed', R_HAND, 'gLinkAdultRightHandClosedFarDL'),
]
AGES = {'child': ('object_link_child', 'gLinkChildLimbs', CHILD),
        'adult': ('object_link_boy', 'gLinkAdultLimbs', ADULT)}


def texel_uv(tex, s, t):
    """Vertex s/t -> normalised texture coordinates (same scale/shift rule as
    build_kokiri_scene.coordinate, without clamp/mirror so OBJ repeats)."""
    def axis(value, scale, shift, origin, extent):
        value *= scale * (2 ** (-shift if shift <= 10 else 16 - shift))
        return (value - origin / 4) / extent
    return (axis(s, tex['scale'][0], tex['shifts'], tex['uls'], tex['width']),
            1 - axis(t, tex['scale'][1], tex['shiftt'], tex['ult'], tex['height']))


def write_obj(path, name, faces):
    path.parent.mkdir(parents=True, exist_ok=True)
    stem = path.stem
    textures, mtl = {}, []
    lines = ['# Exported from real OoT US 1.2 display lists (tools/export_link_workshop.py)',
             '# Y up, world units (Link scale 0.01), idle pose. Reference only.',
             f'mtllib {stem}.mtl', f'o {name}']
    vt, vn = 0, 0
    current = None
    for face in faces:
        tex = face.get('texture')
        key = id(tex) if tex else ('flat',) + tuple(face.get('prim') or (255, 255, 255, 255))
        if key not in textures:
            mat = f'm{len(textures)}'
            textures[key] = mat
            mtl.append(f'newmtl {mat}')
            if tex:
                image = Image.new('RGBA', (tex['width'], tex['height']))
                image.putdata([tuple(c) for c in tex['colors']])
                png = f'{stem}_{mat}.png'
                image.save(path.parent / png)
                mtl += ['Kd 1 1 1', f'map_Kd {png}', f'map_d {png}']
            else:
                r, g, b = (c / 255 for c in (face.get('prim') or (255, 255, 255))[:3])
                mtl.append(f'Kd {r:.4f} {g:.4f} {b:.4f}')
        if textures[key] != current:
            current = textures[key]
            lines.append(f'usemtl {current}')
        idx = []
        for v in face['vertices']:
            x, y, z = (c * 0.01 for c in v[:3])
            # Lit faces carry normals in these bytes, not colour.
            r, g, b = (1.0, 1.0, 1.0) if face.get('lighting') else (c / 255 for c in v[5:8])
            lines.append(f'v {x:.4f} {y:.4f} {z:.4f} {r:.3f} {g:.3f} {b:.3f}')
            vn += 1
            if tex:
                u, w = texel_uv(tex, v[3], v[4])
                lines.append(f'vt {u:.5f} {w:.5f}')
                vt += 1
                idx.append(f'{vn}/{vt}')
            else:
                idx.append(f'{vn}')
        lines.append('f ' + ' '.join(idx))
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    (path.parent / f'{stem}.mtl').write_text('\n'.join(mtl) + '\n', encoding='utf-8')
    return len(faces)


def runtime_matrix_as_identity():
    """Bunny-hood ears (segment 0x0B) and the hookshot reticle (segment 0x01)
    multiply matrices built at run time. For a static export keep the limb
    matrix (identity extra): ears sit at the hood base, reticle at the hand."""
    original = link.LimbLists.matrix
    def matrix(self, word, address):
        if word == 0xDA380001 and address >> 24 in (0x01, 0x0B):
            return None
        return original(self, word, address)
    link.LimbLists.matrix = matrix


def export(oot, rom_dir, out):
    runtime_matrix_as_identity()
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    anim = link.read_object(oot, 'link_animetion', rom_dir)
    _, root, rotations = link.read_animation(keep, anim, link.IDLE_ANIMATION, 0, 21)
    results = []
    for age, (obj_name, table_name, items) in AGES.items():
        data = link.read_object(oot, obj_name, rom_dir)
        xml = ET.parse(oot / 'assets/xml/objects' / (obj_name + '.xml'))
        table = next(int(e.attrib['Offset'], 0) for e in xml.iter('LimbTable')
                     if e.attrib['Name'] == table_name)
        offsets = {e.attrib['Name']: int(e.attrib['Offset'], 0) for e in xml.iter('DList')}
        limbs = link.read_limbs(data, table)
        placed = link.walk_skeleton(limbs, rotations, root)
        for kind, item, limb, symbol in items:
            target = out / age / kind / f'{item}.obj'
            try:
                if limb is None:
                    faces = link.collect_faces(data, keep, placed)
                else:
                    selected = [(i, m, o, (0x06000000 | offsets[symbol]) if i == limb else dl)
                                for i, m, o, dl in placed]
                    faces = [f for f in link.collect_faces(data, keep, selected) if f['limb'] == limb]
                if not faces:
                    raise ValueError('no triangles')
                count = write_obj(target, item, faces)
                results.append((age, kind, item, count, ''))
            except Exception as exc:  # report, keep exporting the rest
                results.append((age, kind, item, 0, f'{type(exc).__name__}: {exc}'))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=link.OOT_DEFAULT)
    parser.add_argument('--rom-dir')
    parser.add_argument('--out', type=Path, default=OUT)
    args = parser.parse_args()
    results = export(args.oot, args.rom_dir, args.out)
    failed = [r for r in results if r[4]]
    for age, kind, item, count, error in results:
        print(f'{age:5} {kind:9} {item:36} {count:5} tris {error}')
    print(f'{len(results) - len(failed)} exported, {len(failed)} failed -> {args.out}')
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
