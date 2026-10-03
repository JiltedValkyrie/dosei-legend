"""Extract the child Kokiri cast with original flex ownership and idle clips.

Source: En_Ko sModelInfo/sOsAnimeLookup (pre-Deku-Tree child column),
En_Md and En_Sa. No AI or replacement character geometry.
"""
import argparse
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import build_actor_model as actor
import build_link_model as link
from cutscene_animation import write_track

KO_CLIPS = (
    ('gKokiriLiftingRockAnim', None), ('gKokiriStandUpAnim', 0),
    ('gKokiriPunchingAnim', None), ('gKokiriBlockingAnim', None),
    ('gKokiriCuttingGrassAnim', None), ('gKokiriStandUpAnim', 1),
    ('gKokiriStandUpAnim', 2), ('gKokiriStandingAnim', None),
    ('gKokiriSittingArmsUpAnim', None), ('gKokiriStandUpAnim', 1),
    ('gKokiriStandUpAnim', 0), ('gKokiriSittingAnim', None),
    ('gKokiriIdleAnim', None),
)


def xml(oot, name):
    path = oot / 'assets/xml/objects' / (name + '.xml')
    root = ET.parse(path)
    offsets = {n.attrib['Name']: int(n.attrib['Offset'], 16)
               for n in root.iter() if 'Name' in n.attrib and 'Offset' in n.attrib}
    return path, root, offsets


class NpcLists(link.LimbLists):
    def triangle(self, word, transparent):
        first = len(self.faces)
        super().triangle(word, transparent)
        for face in self.faces[first:]:
            address = (face.get('texture') or {}).get('address', 0) & 0xFFFFFF
            tint = getattr(self, 'material_tints', {}).get(address)
            if tint and face['texture_segment'] == 6:
                face['prim'] = tint

    def walk(self, address, transparent=False, depth=0):
        # EnKo_SetEnvColor lists only tint the tunic/boots. Convert their
        # material tint into the baker's primitive-colour input.
        if address in getattr(self, 'tints', {}):
            self.prim = self.tints[address]
            return
        return super().walk(address, transparent, depth)


SHOPKEEPER = 15    # EnOssan OSSAN_TYPE_KOKIRI: km1 body + masterkokiri head/anim

# Saria's greeting cutscene poses. EnSa_HandleCutscene indexes sAnimationInfo1
# with the actor cue id, so the ids the script actually uses decide this set:
# gKokiriForestSariaGreetingCs cues 4, 3, 1 and 2. Cue 4 is
# ENSA_ANIM1_MOVE_ARMS_TO_SIDE, whose clip is gSariaWaitArmsToSideAnim -- model
# 1 already carries it, so it is not rebuilt here. The other three are separate
# models sharing model 1's skeleton and textures, loaded only while the
# greeting plays and freed with it: three clips resident through all of
# gameplay would cost heap for a cutscene that runs once per file.
SARIA_CS_CLIPS = {16: 'gSariaLookUpArmExtendedAnim',   # cue 1
                  17: 'gSariaWaveAnim',                # cue 2
                  18: 'gSariaRunAnim'}                 # cue 3
SARIA_CS_CLIPS.update({19:'gSariaWaitOnBridgeAnim',20:'gSariaHoldOcarinaAnim',
                      21:'gSariaGiveLinkOcarinaAnim',22:'gSariaHoldOutOcarinaAnim'})
MODEL_COUNT = 23


def build(oot, rom_dir, out, model):
    saria_cs = SARIA_CS_CLIPS.get(model)
    slot = model           # the NPC<nn> the file is written as
    if saria_cs:
        model = 1          # same skeleton, head limb, torso and textures
    ko = model - 2     # 13 = the shopkeeper (never an ENKO_TYPE)
    girl = ko in (1, 5, 6, 9, 10, 12)
    obj = ('object_md' if model == 0 else 'object_sa' if model == 1 else
           'object_kw1' if girl else 'object_km1')
    path, nodes, offsets = xml(oot, obj)
    data = link.read_object(oot, obj, rom_dir)
    skeleton = next(nodes.iter('Skeleton'))
    table, count = actor.read_skeleton(data, int(skeleton.attrib['Offset'], 16))
    limbs, addresses = actor.read_limbs(data, table, count)
    if model < 2:
        head = addresses.index(offsets['gMidoHeadLimb' if model == 0 else 'gSariaHeadLimb'])
        # EnMd MIDO_LIMB_TORSO; EnSa one-based limb 9 (gSariaRightChestLimb).
        torso = addresses.index(offsets['gMidoTorsoLimb']) if model == 0 else 8
        clip, static = (saria_cs if saria_cs else
                        'gMidoIdleAnim' if model == 0 else
                        'gSariaWaitArmsToSideAnim'), None
        animation_data, animation_offsets = data, offsets
    else:
        head = 14  # EnKo_OverrideLimbDraw's one-based limb 15
        torso = 7  # ... and limb 8 (interactInfo.torsoRot)
        if model == SHOPKEEPER:
            # EnOssan_InitKokiriShopkeeper: object_masterkokiri_Anim_0004A8.
            clip, static = 'object_masterkokiri_Anim_0004A8', None
            animation_data = link.read_object(oot, 'object_masterkokiri', rom_dir)
            _, _, animation_offsets = xml(oot, 'object_masterkokiri')
        else:
            clip, static = KO_CLIPS[ko]
            animation_data = link.read_object(oot, 'object_os_anime', rom_dir)
            _, _, animation_offsets = xml(oot, 'object_os_anime')
        limbs[head]['near'] = limbs[head]['far'] = 0x06000000 + offsets[
            'object_kw1_DL_002C10' if girl else 'gKm1DL']
    if slot in (20,21,22):
        hand=addresses.index(offsets['gSariaRightHandLimb'])
        limbs[hand]['near']=limbs[hand]['far']=0x06000000+offsets['gSariaRightHandAndOcarinaDL']
    head_data, head_path, head_offsets = data, path, offsets
    if ko == 12:
        head_path, _, head_offsets = xml(oot, 'object_fa')
        head_data = link.read_object(oot, 'object_fa', rom_dir)
        limbs[head]['near'] = limbs[head]['far'] = 0x06000000 + head_offsets['gFaDL']
    if model == SHOPKEEPER:
        # EnOssan_OverrideLimbDrawKokiriShopkeeper: limb 15 -> head object.
        head_path, _, head_offsets = xml(oot, 'object_masterkokirihead')
        head_data = link.read_object(oot, 'object_masterkokirihead', rom_dir)
        limbs[head]['near'] = limbs[head]['far'] = 0x06000000 + head_offsets['gKokiriShopkeeperHeadDL']
    expressions = ({8: 'gMidoEyeOpenTex'} if model == 0 else
                   {8: 'gSariaEyeOpenTex', 9: 'gSariaEyeOpenTex',
                    10: 'gSariaMouthClosedTex'} if model == 1 else
                   {10: 'gFaEyeOpenTex' if ko == 12 else 'gKw1EyeOpenTex'} if girl else
                   {10: 'gKokiriShopkeeperEyeDefaultTex'} if model == SHOPKEEPER else {})
    if slot == 19:
        expressions[8]=expressions[9]='gSariaEyeSadTex'
    link.HEAD_LIMB, link.LIMB_NONE = head, 0xFF
    anim_offset = animation_offsets[clip]
    frames, root, rotations = actor.read_animation(animation_data, anim_offset, count, static or 0)
    placed = link.walk_skeleton(limbs, rotations, root)
    poses = {i: (matrix, origin) for i, matrix, origin, _ in placed}
    lists = NpcLists(b'', b'')
    # func_80034B28 supplies render-mode state only, not geometry/materials.
    lists.segments = {6: data, 12: struct.pack('>II', 0xDF000000, 0)}
    if model >= 2:
        lists.tints = {0x08000000: (70, 190, 60, 255) if girl else (0, 130, 70, 255),
                       0x09000000: (100, 30, 0, 255) if girl else (110, 170, 20, 255)}
        # EnKo uses ENV colour, while these lists can overwrite PRIM with
        # white. Bind the source cloth/leather materials explicitly so that
        # per-limb state resets cannot turn shorts or hats white.
        lists.material_tints = {offset: lists.tints[0x08000000 if 'Tunic' in name else 0x09000000]
                                for name, offset in offsets.items()
                                if 'Tex' in name and ('Tunic' in name or 'Boot' in name)}
    for segment, symbol in expressions.items():
        lists.segments[segment] = head_data[head_offsets[symbol]:]
    lists.matrix_limbs = [i for i, _, _, display in placed if display]
    before = link.LimbLists.unresolved
    faces = []
    for i, _, _, display in placed:
        if not display:
            continue
        lists.segments[6] = head_data if i == head else data
        material_tints = getattr(lists, 'material_tints', {})
        if i == head and ko == 12: lists.material_tints = {}
        lists.prim = (255, 255, 255, 255)
        lists.current_limb = i
        first = len(lists.faces)
        lists.walk(display)
        lists.material_tints = material_tints
        group = []
        for original in lists.faces[first:]:
            face = dict(original)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertices'] = [link.transform(*poses[owner], v[:3]) + tuple(v[3:])
                                for v, owner in zip(face['vertices'], face['vertex_limbs'])]
            face['limb'] = i
            group.append(face)
        link.character_textures.mark_faces(group, head_path if i == head else path,
                                           head, expressions)
        faces.extend(group)
    if link.LimbLists.unresolved != before or lists.external_lists:
        raise ValueError(f'{obj}: unresolved texture/display segments {lists.external_lists}')
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, 0.01)
    dest = out / ('NPC%02d.BIN' % slot)
    positions, tiles, owners, locals_ = link.write_model(faces, dest, skinned=True)
    source_frames = [static] if static is not None else range(2, 15) if ko == 3 else range(frames)

    def track():
        for frame in source_frames:
            _, root, rotations = actor.read_animation(animation_data, anim_offset, count, frame)
            pose = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rotations, root)}
            yield [tuple(v * .01 for v in link.transform(*pose[owner], local))
                   for owner, local in zip(owners, locals_)]

    write_track(dest.with_suffix('.ANM'), track())
    # Runtime skinning (oot-core): per vertex, the slot of its limb in the
    # flex skeleton's matrix array (SkelAnime_DrawFlex writes one Mtx per limb
    # with a display list, depth first: lists.matrix_limbs order) and its
    # limb-local position in object units. The decomp draw supplies the
    # matrices, so every animation and head/torso turn is the real one.
    slots = [lists.matrix_limbs.index(owner) for owner in owners]
    skin = struct.pack('>4sII', b'SKN1', len(owners), len(lists.matrix_limbs))
    skin += bytes(slots) + bytes((-len(slots)) % 2)
    skin += b''.join(struct.pack('>3h', *(round(c) for c in local)) for local in locals_)
    dest.with_suffix('.SKN').write_bytes(skin)
    # The source head override rotates in the head parent's frame BEFORE
    # applying the head joint translation/rotation. Retain that frame, not
    # a guessed world-up pivot, for integer runtime tracking.
    parents = {}
    for i, limb in enumerate(limbs):
        child = limb['child']
        while child != 0xFF:
            parents[child] = i
            child = limbs[child]['sibling']
    # Torso override rotates the torso limb's whole subtree (head included)
    # in the torso parent's frame; the head override applies first.
    subtree, stack = set(), [torso]
    while stack:
        limb = stack.pop()
        subtree.add(limb)
        stack += [c for c, parent in parents.items() if parent == limb]
    flags = bytes(int(owner == head) | 2 * int(owner in subtree) for owner in owners)
    flags += bytes((-len(flags)) % 4)
    tracking = struct.pack('>4sIII', b'NTR2', len(owners), len(source_frames),
                           9 * 64 if model == 1 else 12 * 64) + flags
    for frame in source_frames:
        _, root, rotations = actor.read_animation(animation_data, anim_offset, count, frame)
        pose = {i: (m, o) for i, m, o, _ in link.walk_skeleton(limbs, rotations, root)}
        matrix, origin = pose[parents[head]]
        focus = link.transform(*pose[head], (400 if model < 2 else 0, 0, 0))
        values = [round(v * 16384) for row in matrix for v in row]
        values += [round(v * .01 * 64) for v in origin + focus]
        matrix, origin = pose[parents[torso]]
        values += [round(v * 16384) for row in matrix for v in row]
        values += [round(v * .01 * 64) for v in origin]
        tracking += struct.pack('>27h', *values)
    dest.with_suffix('.TRK').write_bytes(tracking)
    return dict(model=slot, object=obj, clip=clip, source_frames=list(source_frames),
                vertices=len(positions), faces=len(faces), tiles=len(tiles),
                mesh_bytes=dest.stat().st_size, animation_bytes=dest.with_suffix('.ANM').stat().st_size,
                head=head, head_vertices=sum(owner == head for owner in owners),
                torso=torso, torso_vertices=sum(owner in subtree for owner in owners))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'build/generated/npcs')
    ap.add_argument('--model', type=int, action='append')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    rows = [build(args.oot, args.rom_dir, args.out, model) for model in
            (args.model if args.model is not None else range(MODEL_COUNT))]
    (args.out / 'manifest.json').write_text(json.dumps(rows, indent=2) + '\n')


if __name__ == '__main__':
    main()
