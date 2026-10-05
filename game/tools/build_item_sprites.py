#!/usr/bin/env python
"""Bake Link's tools and projectiles into SPR1 sprite sheets (ITM*.SPR).

Geometry comes straight from the original display lists (read from the
verified ROM, decoded by build_link_model/build_kokiri_scene). Rasterising,
palette and the SPR1 container are build_npc_sprites' (see its docstring):
5 yaw directions (front, front-right, right, back-right, back; the runtime
mirrors the other 3), 4bpp, one 15-colour CLUT per sheet.

Units: display-list units times the draw scale (0.01 for actors and Link's
limbs, 0.015 for the hookshot chain link) = world units. The sprite origin
is the draw origin: actor position for projectiles, the hand/foot joint for
held items, so centre_y is relative to that joint.

PITCH-BAND CONVENTION (sheets with pitch_bands = true: ITMARW, ITMHKT,
ITMHKC, ITMBOO, ITMBGS): the SPR1 pose axis is not animation but pitch.
poses = ticks = 5, tick->pose table is identity, pose p = elevation
(-90, -45, 0, +45, +90)[p] degrees: the item's local +Z (its forward /
flight direction) rotated toward +Y (up) by that angle before the yaw
views. Runtime picks pose = round(elevation / 45) + 2 and the direction
from yaw as for NPC sprites. Static sheets: 1 pose, 1 tick.

ITMEXP: EffectSsBomb2 layered explosion, billboard (5 identical dirs),
poses = the 8 texture frames in order, ticks = 8, identity table.

Held items carry manifest "anchor" (sprite origin joint); ITMBGS also
"blade_length" (world units at Link scale; blade lies along +Z).

ITMBOM (EnBom_Draw) is billboarded on N64: every direction is the front cel.
"""
import argparse
import json
import math
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

from PIL import Image

import build_link_model as link
import build_npc_sprites as spr

ROOT = Path(__file__).resolve().parents[1]
PITCHES = (-90, -45, 0, 45, 90)
HAND_TEXTURE = ('Hand', 'Gauntlet')   # texture names of the hand in held-item DLs

# name: (object, [display lists in draw order], scale, max height, options)
# options: pitch (pose = pitch band), strip_hand, billboard, pre (rotation
# applied to the DL before pitching, degrees about x/z, from the draw code).
# Hero gear (held weapons, shield, boots) bakes at 2x linear resolution
# (human request 2026-10-04); projectiles keep the small sheets.
SHEETS = {
    # EnArrow_Draw: SkelAnime_DrawLod(gArrowSkel), near LOD, last frame of
    # gArrow1_Anim (played once on release).
    'ITMARW': ('gameplay_keep', ['gArrowSkel'], 0.01, 32, dict(pitch=True, skel='gArrow1_Anim')),
    # EnBom_Draw: gBombCapDL, then RotateZYX(0x4000,0,0) gBombBodyDL, billboard.
    'ITMBOM': ('gameplay_keep', ['gBombCapDL', ('gBombBodyDL', 90)], 0.01, 32, dict(billboard=True)),
    'ITMCHU': ('gameplay_keep', ['gBombchuDL'], 0.01, 32, {}),
    # EnBoom_Draw: RotateZ(0x1F40) tilt then gBoomerangRefDL (spin not baked).
    'ITMBOO': ('gameplay_keep', ['gBoomerangRefDL'], 0.01, 32, dict(pitch=True, roll=0x1F40 * 360 / 65536)),
    'ITMHKT': ('object_link_boy', ['gLinkAdultHookshotTipDL'], 0.01, 32, dict(pitch=True)),
    # ArmsHook_Draw scales the chain 0.015 in x/y, length in z; one link = 0.015.
    'ITMHKC': ('object_link_boy', ['gLinkAdultHookshotChainDL'], 0.015, 24, dict(pitch=True, chain=True)),
    'ITMBOW': ('object_link_boy', ['gLinkAdultRightHandHoldingBowNearDL'], 0.01, 64, dict(strip_hand=True)),
    'ITMHKS': ('object_link_boy', ['gLinkAdultRightHandHoldingHookshotNearDL'], 0.01, 64, dict(strip_hand=True)),
    # Blade runs along hand-local +X; yaw it onto +Z so pitch bands tilt it.
    'ITMBGS': ('object_link_boy', ['gLinkAdultLeftHandHoldingBgsNearDL'], 0.01, 64,
               dict(pitch=True, strip_hand=True, blade_x=True)),
    'ITMMIR': ('object_link_boy', ['gLinkAdultRightHandHoldingMirrorShieldNearDL'], 0.01, 64, dict(strip_hand=True)),
    'ITMIRB': ('object_link_boy', ['gLinkAdultRightIronBootDL'], 0.01, 48, {}),
    'ITMHOB': ('object_link_boy', ['gLinkAdultRightHoverBootDL'], 0.01, 48, {}),
}

NAMES = list(SHEETS) + ['ITMEXP']   # ITMEXP: bake_explosion (textures, no DL mesh)


class ItemLists(link.LimbLists):
    """Record the texture image address each face was drawn with."""
    def triangle(self, word, transparent):
        first = len(self.faces)
        super().triangle(word, transparent)
        for face in self.faces[first:]:
            tile = self.tiles[self.texture_tile] if self.texture_on else {}
            image = self.images.get(tile.get('tmem'))
            face['image'] = image[0] if image else None


def rot_x(points, deg):
    """+Z toward +Y by deg (elevation)."""
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    return [(x, y * c + z * s, z * c - y * s) for x, y, z in points]


def rot_z(points, deg):
    s, c = math.sin(math.radians(deg)), math.cos(math.radians(deg))
    return [(x * c - y * s, x * s + y * c, z) for x, y, z in points]


def skeleton_dls(data, segment, offsets, skel, anim):
    """LOD skeleton -> [(DL address, matrix, origin)] posed at anim's last frame."""
    import build_actor_model as actor
    table, count = actor.read_skeleton(data, offsets[skel])
    limbs = []
    for p in struct.unpack_from('>%dI' % count, data, table):
        x, y, z, child, sibling, near, far = struct.unpack_from(link.LIMB_STRUCT, data, p & 0xFFFFFF)
        limbs.append(dict(pos=(x, y, z), child=child, sibling=sibling, near=near, far=near))
    frames = struct.unpack_from('>h', data, offsets[anim])[0]
    _, root, rot = actor.read_animation(data, offsets[anim], count, frames - 1)
    head, link.HEAD_LIMB = link.HEAD_LIMB, -1
    try:
        placed = link.walk_skeleton(limbs, rot, root)
    finally:
        link.HEAD_LIMB = head
    return [(dl, m, o) for _, m, o, dl in placed if dl]


def chain_link(faces):
    """One link of gLinkAdultHookshotChainDL. The DL is three crossed-plane
    segments over z 0..100 that ArmsHook_Draw stretches to the chain length
    (scale z = len * 0.01), each tiling the 16x32 chain texture ~20 times. Keep
    the first segment's planes (z 67..100) and give them one texture period
    (t 0..32 texels) over the length at the texture's own density across x/y
    (16 texels = 200 units): 400 units, centred on the origin."""
    out = []
    for face in faces:
        if min(v[2] for v in face['vertices']) < 67:
            continue
        face = dict(face)
        face['vertices'] = [(v[0], v[1], round((v[2] - 67) / 33 * 400) - 200, v[3],
                             0 if v[2] < 84 else 32 * 32) + tuple(v[5:]) for v in face['vertices']]
        out.append(face)
    return out


def item_faces(oot, rom_dir, obj, dls, opts, keep):
    """Real DL faces -> (KFR1-baked sprite faces, model-unit points, symbols, hand faces dropped)."""
    data = keep if obj == 'gameplay_keep' else link.read_object(oot, obj, rom_dir)
    xml = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
    offsets = {e.attrib['Name']: int(e.attrib['Offset'], 16) for e in xml.iter()
               if 'Name' in e.attrib and e.attrib.get('Offset', '.')[:2] == '0x'}
    segment = int(next(xml.iter('File')).attrib.get('Segment', '6'), 0)
    hand = {(segment << 24) | off for name, off in offsets.items()
            if name.endswith('Tex') and any(k in name for k in HAND_TEXTURE)}
    enddl = struct.pack('>II', 0xDF000000, 0)
    lists = ItemLists(b'', b'')
    lists.segments = {segment: data, 4: keep}
    for s in range(8, 14):
        lists.segments.setdefault(s, enddl)
    lists.current_limb = 0
    lists.matrix_limbs = [0] * 32   # boots load a leg slot: one rigid frame
    walks = []
    for entry in dls:
        sym, pre = entry if isinstance(entry, tuple) else (entry, 0)
        if opts.get('skel'):
            walks += skeleton_dls(data, segment, offsets, sym, opts['skel'])
            continue
        r = link.rotation_matrix((int(pre * 65536 / 360), 0, 0)) if pre else None
        walks.append(((segment << 24) | offsets[sym], r, (0, 0, 0)))
    faces = []
    for address, matrix, origin in walks:
        first = len(lists.faces)
        lists.walk(address)
        for face in lists.faces[first:]:
            face = dict(face)
            if matrix is not None:
                face['vertices'] = [tuple(round(n) for n in link.transform(matrix, origin, v[:3])) + tuple(v[3:])
                                    for v in face['vertices']]
            faces.append(face)
    if opts.get('chain'):
        faces = chain_link(faces)
    dropped = 0
    if opts.get('strip_hand'):
        kept = [f for f in faces if f.get('image') not in hand]
        dropped = len(faces) - len(kept)
        faces = kept
    for face in faces:
        face['limb'] = 0
        face['full_texture'] = True
        if face.get('texture_segment') == 4:
            face['texture_segment'] = 6
    link.apply_primitive_colour(faces)
    return faces, dropped


def kfr_faces(faces, tmp):
    """Bake through the KFR1 writer (same tiles VDP1 maps) and read it back."""
    link.write_model(faces, tmp, character=False)
    sprite_faces, _, _ = spr.read_model(tmp, None)
    data = tmp.read_bytes()
    nverts, vo = struct.unpack_from('>I', data, 8)[0], struct.unpack_from('>I', data, 16)[0]
    pts = [struct.unpack_from('>3h', data, vo + 6 * i) for i in range(nverts)]
    tmp.unlink()
    return sprite_faces, pts


def bake_sheet(name, oot, rom_dir, out, preview_dir, keep):
    obj, dls, scale, max_h, opts = SHEETS[name]
    faces, dropped = item_faces(oot, rom_dir, obj, dls, opts, keep)
    if not faces:
        raise ValueError('%s: no faces' % name)
    sfaces, pts = kfr_faces(faces, preview_dir / ('_%s.BIN' % name))
    pts = [tuple(v * scale for v in p) for p in pts]
    if opts.get('blade_x'):
        pts = [(-z, y, x) for x, y, z in pts]
    if opts.get('roll'):
        pts = rot_z(pts, opts['roll'])
    pitch = bool(opts.get('pitch'))
    poses = [rot_x(pts, a) for a in PITCHES] if pitch else [pts]
    if pitch:
        # Centred on the origin: any pitch and yaw fits one square cel.
        radius = max(math.dist((0, 0, 0), p) for p in pts)
        texel = max(0.25, 2 * radius / (max_h - 3))
        size = int(math.ceil(2 * radius / texel)) + 2
        layout = ((size + 7) & ~7, min(size, max_h), texel, 0.0, radius)
    else:
        # layout_of with a finer texel floor (items are far smaller than NPCs).
        ys = [p[1] for p in pts]
        radius = max(math.hypot(p[0], p[2]) for p in pts)
        texel = max(0.1, (max(ys) - min(ys)) / (max_h - 3), 2 * radius / (max_h - 3))
        layout = ((int(math.ceil(2 * radius / texel)) + 2 + 7) & ~7,
                  int(math.ceil((max(ys) - min(ys)) / texel)) + 2, texel,
                  (min(ys) + max(ys)) / 2, max(ys))
    dest = out / (name + '.SPR')
    preview = preview_dir / (name + '_sprites.png')
    if opts.get('billboard'):
        orig = spr.view
        spr.view = lambda points, phi: orig(points, 0.0)
        try:
            spr.write_sprite(sfaces, poses, list(range(len(poses))), dest, preview, layout)
        finally:
            spr.view = orig
    else:
        spr.write_sprite(sfaces, poses, list(range(len(poses))), dest, preview, layout)
    data = dest.read_bytes()
    w, h, dirs, np_ = struct.unpack_from('>4H', data, 4)
    cy, tq = struct.unpack_from('>hH', data, 14)
    return dict(symbol=dls[0][0] if isinstance(dls[0], tuple) else dls[0],
                symbols=[d[0] if isinstance(d, tuple) else d for d in dls],
                object=obj, w=w, h=h, poses=np_, dirs=dirs, texel_q8=tq,
                centre_y_q4=cy, pitch_bands=pitch, bytes=len(data),
                hand_faces_stripped=dropped, billboard=bool(opts.get('billboard')),
                **anchor_of(name, pts))


# Held-item sprite origin = the joint whose matrix the original DL is drawn
# with (z_player_lib.c hand/foot limb), in that limb's frame.
ANCHORS = {
    'ITMBOW': 'right hand joint (PLAYER_LIMB_R_HAND), hand-limb frame',
    'ITMHKS': 'right hand joint (PLAYER_LIMB_R_HAND), hand-limb frame',
    'ITMBGS': 'left hand joint (PLAYER_LIMB_L_HAND); blade along +Z (hand-local +X yawed onto +Z)',
    'ITMMIR': 'right hand joint (PLAYER_LIMB_R_HAND), hand-limb frame',
    'ITMIRB': 'right lower-leg joint (DL matrix slot 3), limb frame',
    'ITMHOB': 'right lower-leg joint (DL matrix slot 3), limb frame',
}


def anchor_of(name, pts):
    if name not in ANCHORS:
        return {}
    out = dict(anchor=ANCHORS[name])
    if name == 'ITMBGS':
        out['blade_length'] = round(max(p[2] for p in pts), 2)   # world units, Link scale 0.01
    return out


# EffectSsBomb2 layered draw (z_eff_ss_bomb2.c): gEffBombExplosionVtx quad
# (-31..32), 8 ia16 32x32 textures, combiner (PRIM-ENV)*I+ENV, alpha
# PRIM_A*A; base layer plus two layers, each RotateZ(life*0.02+180 rad) and
# Scale 0.925 then 0.775 more (cumulative). EnBom spawns scale 100,
# scaleStep 19 (shape.rot.z 0). texIndex = (23-life)/3: 8 frames -> 8 poses,
# one per texture, sampled at its middle tick. Update then life-- then draw.
EXP_MAX_H = 48
EXP_TEX = 0x7F80
EXP_QUAD = (-31, 32)


def explosion_frames():
    def lerp(a, b, d):
        return b if d == 0 else a + int((b - a) / d)
    life, scale, prim, env = 24, 100, [255, 255, 255, 255], [0, 0, 200]
    frames = {}
    while life > 0:
        tex = int((23 - life) / 3)   # C truncation: life 24 -> 0
        scale += 19
        if 13 < life < 23:
            d = life - 13
            prim = [lerp(prim[i], t, d) for i, t in enumerate((255, 255, 150, 255))]
            env = [lerp(env[i], t, d) for i, t in enumerate((150, 0, 0))]
        elif -1 < life < 14:
            d = life + 1
            prim = [lerp(prim[i], t, d) for i, t in enumerate((50, 50, 50, 150))]
            env = [lerp(env[i], t, d) for i, t in enumerate((10, 10, 10))]
        life -= 1
        frames.setdefault(tex, []).append((life, scale, list(prim), list(env)))
    return [f[len(f) // 2] for _, f in sorted(frames.items())]


def bake_explosion(out, preview_dir, keep, name='ITMEXP'):
    frames = explosion_frames()
    big = max(f[1] for f in frames) * 0.01 * (EXP_QUAD[1] - EXP_QUAD[0])
    texel = big / (EXP_MAX_H - 2)
    width = (int(math.ceil(big / texel)) + 2 + 7) & ~7
    height = min(EXP_MAX_H, int(math.ceil(big / texel)) + 2)
    sup = spr.SUPER
    images = []
    for t, (life, scale, prim, env) in enumerate(frames):
        tex = keep[EXP_TEX + t * 0x800: EXP_TEX + (t + 1) * 0x800]
        k = scale * 0.01
        layers = [(k, 0.0)]
        rot, sc = 0.0, 1.0
        for step in (0.925, 0.775):
            rot += life * 0.02 + 180.0
            sc *= step
            layers.append((k * sc, rot))
        acc = Image.new('RGBA', (width * sup, height * sup))
        for lk, angle in layers:
            layer = Image.new('RGBA', acc.size)
            ca, sa = math.cos(-angle), math.sin(-angle)
            for py in range(acc.height):
                wy = (acc.height / 2 - py - 0.5) * texel / sup
                for px in range(acc.width):
                    wx = (px + 0.5 - acc.width / 2) * texel / sup
                    qx, qy = (wx * ca - wy * sa) / lk, (wx * sa + wy * ca) / lk
                    if not (EXP_QUAD[0] <= qx < EXP_QUAD[1] and EXP_QUAD[0] <= qy < EXP_QUAD[1]):
                        continue
                    u = min(31, int((qx - EXP_QUAD[0]) * 32 / 63))
                    v = min(31, int((EXP_QUAD[1] - qy) * 32 / 63))
                    i, a = tex[(v * 32 + u) * 2], tex[(v * 32 + u) * 2 + 1]
                    col = tuple((prim[c] - env[c]) * i // 255 + env[c] for c in range(3))
                    layer.putpixel((px, py), col + (prim[3] * a // 255,))
            acc.alpha_composite(layer)
        img = acc.resize((width, height), Image.BOX)
        img.putalpha(img.getchannel('A').point(lambda a: 255 if a >= 40 else 0))
        images.append(img)
    dest = out / (name + '.SPR')
    data = pack_sprite([[img] * spr.DIRS for img in images], width, height, 0.0, texel, 0, dest,
                       preview_dir / (name + '_sprites.png'))
    return dict(symbol='gEffBombExplosion1Tex', object='gameplay_keep',
                symbols=['gEffBombExplosion%dTex' % (i + 1) for i in range(8)]
                + ['gEffBombExplosion2DL', 'gEffBombExplosion3DL'],
                w=width, h=height, poses=len(images), dirs=spr.DIRS, texel_q8=round(texel * 256),
                centre_y_q4=0, pitch_bands=False, bytes=len(data), billboard=True,
                ticks=len(images), note='EffectSsBomb2 layered; poses = texture frames in order')


def pack_sprite(images, width, height, centre_y, texel, focus_y, dest, preview_path):
    """build_npc_sprites.write_sprite's palette/container for prebuilt cels."""
    flat = [c for row in images for c in row]
    sheet = Image.new('RGB', (width, height * len(flat)))
    for n, img in enumerate(flat):
        sheet.paste(img.convert('RGB'), (0, n * height))
    quant = sheet.quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    pal = quant.getpalette()[:45]
    clut = [0] + [(1 << 15) | (pal[i * 3] >> 3) | ((pal[i * 3 + 1] >> 3) << 5) |
                  ((pal[i * 3 + 2] >> 3) << 10) for i in range(15)]
    cels = bytearray()
    for n, img in enumerate(flat):
        alpha = img.getchannel('A')
        for y in range(height):
            row = [quant.getpixel((x, n * height + y)) + 1 if alpha.getpixel((x, y)) else 0
                   for x in range(width)]
            for x in range(0, width, 2):
                cels.append(row[x] << 4 | row[x + 1])
    order = list(range(len(images)))
    data = struct.pack('>4s5HhHh', b'SPR1', width, height, spr.DIRS, len(images), len(order),
                       round(centre_y * 16), round(texel * 256), focus_y)
    data += struct.pack('>16H', *clut)
    data += struct.pack('>%dH' % len(order), *order) + bytes((-2 * len(order)) % 4)
    data += cels
    dest.write_bytes(data)
    preview = Image.new('RGBA', (width * spr.DIRS, height * len(images)))
    for p, row in enumerate(images):
        for d, img in enumerate(row):
            preview.paste(img, (d * width, p * height))
    preview.save(preview_path)
    print('  sprite: %s %dx%d, %d poses x %d dirs, %d bytes' %
          (dest.name, width, height, len(images), spr.DIRS, len(data)))
    return data


def vram_bytes(entry):
    cel = entry['w'] * entry['h'] // 2
    return entry['poses'] * entry['dirs'] * ((cel + 31) & ~31) + 32


def build(oot, rom_dir, out, only=None, preview_dir=None, manifest=None):
    oot = Path(oot)
    out = Path(out)
    preview_dir = Path(preview_dir or ROOT / 'build/generated/sprites')
    manifest = Path(manifest or ROOT / 'build/generated/item_sprites.json')
    out.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    keep = link.read_object(oot, 'gameplay_keep', rom_dir)
    result = {}
    if only and manifest.exists():
        result = json.loads(manifest.read_text(encoding='utf-8'))
    for name in only or NAMES:
        result[name] = (bake_explosion(out, preview_dir, keep) if name == 'ITMEXP'
                        else bake_sheet(name, oot, rom_dir, out, preview_dir, keep))
    result['_convention'] = ('pitch_bands: pose p = elevation (-90,-45,0,45,90)[p] deg of item +Z '
                             'toward +Y; ticks=5 identity. dirs: 5 yaw views, runtime mirrors 3.')
    manifest.write_text(json.dumps(result, indent=1) + '\n', encoding='utf-8')
    total = sum(vram_bytes(e) for k, e in result.items() if not k.startswith('_'))
    print('item sprites: %d sheets, resident VRAM %d bytes' % (len(NAMES), total))
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--oot', type=Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/cd')
    ap.add_argument('--only', action='append', choices=sorted(NAMES))
    args = ap.parse_args()
    build(args.oot, args.rom_dir, args.out, args.only)


if __name__ == '__main__':
    main()
