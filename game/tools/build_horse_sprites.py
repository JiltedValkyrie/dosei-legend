#!/usr/bin/env python3
"""Bake gameplay horses' original Skin data offline into bounded sprite sheets.

This prepares packages, not runtime actor implementations. Outputs stay in the
offline cache until original gameplay is imported through bounded 32-bit math,
head/hoof/rider anchors replace pose reads, and scene population budgets pass.
All animation frames retain their original clock; sampled visuals may repeat.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import xml.etree.ElementTree as ET

import build_actor_model as actor
import build_horse_model as horse
import build_link_model as link
import build_npc_sprites as sprite
import oot_core_import as imp

GAME = Path(__file__).resolve().parents[1]
RECIPES = (
    ('ACTOR_EN_HORSE_LINK_CHILD', 'En_Horse_Link_Child', 'object_horse_link_child', 'normal', 0.005),
    ('ACTOR_EN_HORSE_NORMAL', 'En_Horse_Normal', 'object_horse_normal', 'normal', 0.01),
    ('ACTOR_EN_HORSE', 'En_Horse', 'object_horse', 'epona', 0.01),
    ('ACTOR_EN_HORSE', 'En_Horse', 'object_hni', 'ingo', 0.01),
    ('ACTOR_EN_HORSE', 'En_Horse', 'object_hni', 'gerudo_saddle', 0.01),
)
MAX_HEIGHT = 40
MAX_POSES = 4


def pose_points(data, anim, limbs, frame, baked, owners, locals_, scale):
    _, root, rotations = actor.read_animation(data, anim, len(limbs), frame)
    matrices = horse.limb_matrices(limbs, rotations, root)
    bodies = {limb: horse.bake_frame(modifs, matrices, count)
              for limb, count, modifs, _ in baked}
    points = []
    for owner, local in zip(owners, locals_):
        if owner < 0:
            limb = -owner - 1
            points.append(bodies[limb][int(local[0])])
        else:
            points.append(tuple(round(v * scale) for v in link.transform(*matrices[owner - 1], local)))
    return points


def body_identity(faces, limb):
    """A blend point keeps its source vertex and animated limb identity.

    Position-only welding would merge vertices that meet now but split later.
    Distinct animated limbs may each have a vertex 0, so owner is part of key.
    """
    for face in faces:
        face['local'] = [(v, 0, 0) for v in face['source_vertices']]
        face['vertex_limbs'] = [-limb - 1] * len(face['source_vertices'])
        face['limb'] = limb


def prepare_model(data, root, skeleton, animation, scale, variant, path):
    horse.ACTOR_SCALE = scale
    limbs = horse.read_limbs(data, skeleton)
    baked = [(i, *horse.read_modifs(data, limb)) for i, limb in enumerate(limbs)
             if limb['kind'] == horse.SKIN_LIMB_TYPE_ANIMATED and limb['segment']]
    _, rt, rot = actor.read_animation(data, animation, len(limbs), 0)
    matrices = horse.limb_matrices(limbs, rot, rt)
    faces = []
    for limb, count, modifs, dlist in baked:
        _, attrs = horse.read_skin_vertices(data, limbs[limb])
        body = horse.bake_frame(modifs, matrices, count)
        body_faces = horse.walk_body(data, dlist, horse.build_vertex_segment(body, attrs))
        body_identity(body_faces, limb)
        faces.extend(body_faces)
    eye = next((int(n.attrib['Offset'], 16) for n in root.iter('Texture')
                if 'EyeOpenTex' in n.attrib.get('Name', '')), None)
    segments = {8: data[eye:]} if eye is not None else {}
    overrides = {}
    if variant == 'gerudo_saddle':
        dl = next(n for n in root.iter('DList') if n.attrib['Name'] == 'gHorseIngoGerudoSaddleDL')
        overrides[30] = int(dl.attrib['Offset'], 16)
    faces += horse.walk_normal_limbs(data, limbs, matrices, segments, overrides)
    if not faces:
        raise ValueError('horse contains no decoded geometry')
    for face in faces:
        face['full_texture'] = True
    link.apply_primitive_colour(faces)
    _, _, owners, locals_ = link.write_model(faces, path, skinned=True, character=False)
    parsed, _, _ = sprite.read_model(path, None)
    return parsed, limbs, baked, owners, locals_


def bake_recipe(oot, rom_dir, out, work, recipe):
    enum, overlay, obj, variant, scale = recipe
    source = f'src/overlays/actors/ovl_{overlay}/z_{overlay.lower()}.c'
    text = (oot / source).read_text(encoding='utf-8')
    root = ET.parse(oot / 'assets/xml/objects' / (obj + '.xml'))
    data = link.read_object(oot, obj, rom_dir)
    oid = imp.object_ids(oot)[1][obj]
    skel = next(root.iter('Skeleton'))
    animations = [(n.attrib['Name'], int(n.attrib['Offset'], 16)) for n in root.iter('Animation')
                  if re.search(r'\b' + re.escape(n.attrib['Name']) + r'\b', text)]
    if not animations:
        raise ValueError(f'{enum}/{obj}: no source animation references')
    parsed, limbs, baked, owners, locals_ = prepare_model(data, root, int(skel.attrib['Offset'], 16),
                                                        animations[0][1], scale, variant,
                                                        work / f'{obj}-{variant}.BIN')
    clips = []
    for name, offset in animations:
        length = actor.read_animation(data, offset, len(limbs), 0)[0]
        if length <= 0:
            raise ValueError(f'{name}: invalid source frame count {length}')
        count = min(MAX_POSES, length)
        frames = [i * length // count for i in range(count)]
        poses = [pose_points(data, offset, limbs, f, baked, owners, locals_, scale) for f in frames]
        clips.append((name, length, frames, poses))
    rows = []
    for index, (name, ticks, frames, poses) in enumerate(clips):
        # Object-local stable indices; extra saddle occupies a separate group.
        key = index + (0x40 if variant == 'gerudo_saddle' else 0)
        dest = out / f'H{oid:03X}{key:02X}.SPR'
        order = [min(len(poses) - 1, t * len(poses) // ticks) for t in range(ticks)]
        # High jumps have authored root travel. Their large bounds must not
        # shrink idle/walk horses; SPR carries each clip's world-space pivot.
        layout = sprite.layout_of([poses], MAX_HEIGHT)
        sprite.write_sprite(parsed, poses, order, dest, work / (dest.stem + '.png'), layout, MAX_POSES)
        blob = dest.read_bytes()
        width, height, dirs, pose_count, clock = struct.unpack_from('>5H', blob, 4)
        expected = ((52 + clock * 2 + 3) & ~3) + width * height // 2 * dirs * pose_count
        if len(blob) != expected or clock != ticks or not any(blob[-width * height // 2:]):
            raise ValueError(f'{dest.name}: malformed/empty baked sprite')
        rows.append({'actor': enum, 'object': obj, 'object_id': oid, 'variant': variant,
                     'clip': name, 'package': dest.name, 'frames': frames,
                     'ticks': ticks, 'width': width, 'height': height, 'directions': dirs,
                     'poses': pose_count, 'cart_bytes': len(blob) + 1,
                     'vdp1_instance_bytes': ((width * height // 2 + 31) & ~31) + 32,
                     'source': source, 'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
                     'object_sha256': hashlib.sha256(data).hexdigest(),
                     'package_sha256': hashlib.sha256(blob).hexdigest(),
                     'baked': True, 'runtime_imported': False, 'staged': False})
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--rom-dir', type=Path)
    parser.add_argument('--out', type=Path, default=GAME / 'build/generated/horse-sprites')
    parser.add_argument('--work', type=Path, default=GAME / 'build/generated/horse-sprite-work')
    parser.add_argument('--actor', action='append', default=[])
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    rows = []
    for recipe in RECIPES:
        if not args.actor or recipe[0] in args.actor:
            rows.extend(bake_recipe(args.oot, args.rom_dir, args.out, args.work, recipe))
    (args.out / 'manifest.json').write_text(json.dumps({'format_version': 1, 'recipes': rows}, indent=2) + '\n')
    print(f'{len(rows)} horse sprite clips; offline only, runtime gameplay import still blocked')


if __name__ == '__main__':
    main()
