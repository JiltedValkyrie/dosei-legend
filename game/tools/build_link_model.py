#!/usr/bin/env python
"""Extract child Link's model from the US 1.2 ROM into the viewer's mesh format.

Reuses the scene pipeline: ../../shared/tools/build_kokiri_scene.py already
walks F3DEX display lists and bakes per-face 4bpp tiles with CLUTs, so this only
has to supply the skeleton and emit the same KFR1 container (with no collision).
build_sgl_scene.py then converts it exactly like FOREST.BIN.

Skeleton (object_link_child, segment 6):
  gLinkChildLimbs @ 0x2CF18 -- 21 pointers to LodLimb
  LodLimb = { Vec3s jointPos; u8 child; u8 sibling; Gfx* dList[2]; }  (16 bytes)
  dList[1] is the Far LOD used for the body; head uses dList[0] (Near).
  Display lists live in segment 6, with shared textures from gameplay_keep.

Pose: compose the selected animation's root, joint offsets and rotations.
Animated output retains limb-local vertex identity, even where integer bind
positions coincide. The runtime writes fractional 16.16 world positions.
"""

import argparse
import csv
import hashlib
import json
import math
import pathlib
import re
import struct
import sys
import xml.etree.ElementTree as ET

OOT_DEFAULT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')
ROM_MD5 = '57a9719ad547c516342e1a15d5c28c3d'
OBJECT = 'object_link_child'

LIMB_TABLE = 0x2CF18
LIMB_COUNT = 21
LIMB_STRUCT = '>hhhBBII'       # jointPos, child, sibling, near, far
LIMB_NONE = 255
HEAD_LIMB = 10  # zero-based skeleton entry; PLAYER_LIMB_HEAD is 11

# gPlayerAnim_link_normal_waitF_typeA_20f in gameplay_keep: a standing idle.
IDLE_ANIMATION = 0x3200

KFR1_MAGIC = 0x4B465231

_TOOLS = pathlib.Path(__file__).resolve().parents[2] / 'shared' / 'tools'
sys.path.insert(0, str(_TOOLS))

import build_kokiri_scene as scene_tool  # noqa: E402
from flex_vertex_owners import FlexVertexOwners  # noqa: E402
from extract_title_source import yaz0     # noqa: E402


def read_object(oot, name, rom_dir=None):
    config = oot / 'baseroms' / 'ntsc-1.2'
    rom_folder = pathlib.Path(rom_dir) if rom_dir else config
    roms = [p for p in rom_folder.glob('*.z64')
            if hashlib.md5(p.read_bytes()).hexdigest() == ROM_MD5]
    if len(roms) != 1:
        sys.exit('verified US 1.2 ROM (md5 %s) required in %s' % (ROM_MD5, rom_folder))
    rom = roms[0].read_bytes()
    dma = int(re.search(r'dmadata_start: (\w+)',
                        (config / 'config.yml').read_text())[1], 16)
    with (config / 'segments.csv').open() as f:
        for index, row in enumerate(csv.DictReader(f)):
            if row['Name'] != name:
                continue
            start, end, physical, packed = struct.unpack_from(
                '>4I', rom, dma + index * 16)
            data = (yaz0(rom[physical:packed]) if packed
                    else rom[physical:physical + end - start])
            if len(data) != end - start:
                sys.exit('%s: unpacked to %d bytes, expected %d'
                         % (name, len(data), end - start))
            return bytes(data)
    sys.exit('%s not found in segments.csv' % name)


def read_limbs(data):
    pointers = struct.unpack_from('>%dI' % LIMB_COUNT, data, LIMB_TABLE)
    limbs = []
    for pointer in pointers:
        x, y, z, child, sibling, near, far = struct.unpack_from(
            LIMB_STRUCT, data, pointer & 0xFFFFFF)
        limbs.append(dict(pos=(x, y, z), child=child, sibling=sibling,
                          near=near, far=far))
    return limbs


def read_animation(keep, animetion, offset, frame, limb_count):
    """One frame of a LinkAnimation: root translation plus a rotation per limb.

    LinkAnimationHeader at `offset` in gameplay_keep is { s16 frameCount; s16
    pad; void* segment; }. The segment points into link_animetion, where each
    frame is Vec3s[1 + limbCount] followed by a two-byte player face field:
    entry 0 is root translation and entry i+1 is limb i's rotation, in binang
    (0x10000 == 360 degrees). z_skelanime.c's AnimationContext_SetLoadFrame
    includes that trailing field in the DMA stride, even when not using it.
    """
    frames, _, segment = struct.unpack_from('>hhI', keep, offset)
    if frame >= frames:
        sys.exit('frame %d beyond animation length %d' % (frame, frames))
    stride = (limb_count + 1) * 3
    base = (segment & 0xFFFFFF) + frame * (stride * 2 + 2)
    values = struct.unpack_from('>%dh' % stride, animetion, base)
    root = values[0:3]
    rotations = [tuple(values[3 + i * 3:6 + i * 3]) for i in range(limb_count)]
    return frames, root, rotations


def rotation_matrix(rot):
    """Binang Euler triple -> 3x3, applied Z then Y then X (OoT's ZYX order)."""
    def sc(value):
        angle = value * math.tau / 65536.0
        return math.sin(angle), math.cos(angle)

    sx, cx = sc(rot[0])
    sy, cy = sc(rot[1])
    sz, cz = sc(rot[2])
    rx = ((1, 0, 0), (0, cx, -sx), (0, sx, cx))
    ry = ((cy, 0, sy), (0, 1, 0), (-sy, 0, cy))
    rz = ((cz, -sz, 0), (sz, cz, 0), (0, 0, 1))
    return matmul(matmul(rz, ry), rx)


def matmul(a, b):
    return tuple(tuple(sum(a[r][k] * b[k][c] for k in range(3)) for c in range(3))
                 for r in range(3))


def transform(matrix, origin, point):
    return tuple(origin[i] + sum(matrix[i][k] * point[k] for k in range(3))
                 for i in range(3))


def walk_skeleton(limbs, rotations, root, index=0, parent=None, out=None):
    """Depth-first over child/sibling, composing each limb's posed transform.

    Mirrors SkelAnime's hierarchical draw: every limb translates by its jointPos
    in the parent's frame, then rotates. Without these rotations the limbs pile
    up at the origin -- their display lists are authored in limb-local space.
    """
    if out is None:
        out = []
    identity = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    if parent is None:
        parent = (identity, (0, 0, 0))
    while index != LIMB_NONE and index < len(limbs):
        limb = limbs[index]
        matrix, origin = parent
        # The animation supplies the root's translation; the rest use jointPos.
        offset = root if index == 0 else limb['pos']
        here = transform(matrix, origin, offset)
        local = matmul(matrix, rotation_matrix(rotations[index]))
        # Gameplay camera is close to Link: use the original near head mesh,
        # not the distant-face LOD. Body stays far to retain Saturn budgets.
        display = limb['near'] if index == HEAD_LIMB else limb['far']
        out.append((index, local, here, display))
        if limb['child'] != LIMB_NONE:
            walk_skeleton(limbs, rotations, root, limb['child'], (local, here), out)
        index = limb['sibling']
    return out


# z_player_lib.c binds these two segments per frame from the face-animation
# tables; both point into the link object itself, so a static dump just has to
# pick a frame. Without them Link's whole face decodes white.
EYES_OPEN_OFFSET = 0x0000     # gLinkChildEyesOpenTex
MOUTH_CLOSED_OFFSET = 0x4000  # gLinkChildMouthClosedTex
GAMEPLAY_KEEP_SEGMENT = 4
# Segments the face textures arrive on. Those keep their artwork when Link is
# flat shaded; everything else collapses to one colour per face.
FACE_SEGMENTS = (8, 9)


class LimbLists(FlexVertexOwners, scene_tool.DisplayLists):
    """Display lists for one limb, tolerant of runtime-assigned segments.

    Player draw code binds gameplay_keep at segment 4 and the current eye and
    mouth textures at 8 and 9, so a static dump must supply all three; we bind
    the neutral open-eyes and closed-mouth frames. Anything still unresolved
    falls back to the primitive colour rather than aborting the walk.
    """

    unresolved = 0

    def texture(self):
        try:
            return super().texture()
        except AssertionError:
            LimbLists.unresolved += 1
            return None

    def triangle(self, word, transparent):
        """Record which segment each face's texture came from.

        Faces tinted by the tunic's primitive colour are flat-shaded materials;
        when their texture resolves out of gameplay_keep it is the wrong image
        and its transparent texels punch black holes through the green. Knowing
        the source segment lets apply_primitive_colour() keep those flat.
        """
        indices = [(word >> shift & 255) // 2 for shift in (16, 8, 0)]
        vertices = [self.cache[i] for i in indices]
        owners = [self.vertex_limbs[i] for i in indices]
        assert all(v is not None for v in vertices) and None not in owners
        if len({(owner, v[:3]) for owner, v in zip(owners, vertices)}) < 3:
            return
        self.faces.append(dict(vertices=vertices, vertex_limbs=owners,
                               texture=self.texture(), lighting=bool(self.geom & 0x20000),
                               prim=self.prim, transparent=transparent, cull=bool(self.geom & 0x400),
                               texture_segment=(self.image[0] >> 24) if self.image else None))


def collect_faces(data, keep, placed):
    """Walk selected limb display lists, posing each vertex with its own bone.

    One walker is shared across every limb, in draw order, because RDP state --
    above all the loaded TLUT -- persists between limb display lists in the real
    draw. A fresh walker per limb starts with the default white palette, so any
    limb that does not reload the TLUT itself decodes as untextured white.
    """
    # Segment 4 is gameplay_keep, which Player binds alongside the link object
    # (z_player_lib.c). Link's hair texture lives there, so without it the hair
    # decodes white.
    lists = LimbLists(b'', b'')
    lists.segments = {4: keep,
                      6: data,
                      8: data[EYES_OPEN_OFFSET:],
                      9: data[MOUTH_CLOSED_OFFSET:]}
    faces = []
    lists.matrix_limbs = [i for i, _, _, display in placed if display]
    poses = {i: (matrix, origin) for i, matrix, origin, _ in placed}
    for index, matrix, origin, far in placed:
        if not far:
            continue
        first = len(lists.faces)
        # The skeleton loads the owning matrix before calling this list.
        lists.current_limb = index
        lists.walk(far)
        for face in lists.faces[first:]:
            moved = [transform(*poses[owner], v[:3]) + tuple(v[3:])
                     for v, owner in zip(face['vertices'], face['vertex_limbs'])]
            face = dict(face)
            # Keep the untransformed limb-local coordinates alongside the posed
            # ones. The posed vertices drive texture baking and the bind-pose
            # extent exactly as before; the locals are what the runtime skinner
            # re-poses every frame, so they must survive unscaled and uncentred.
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertices'] = moved
            face['limb'] = index
            faces.append(face)
    return faces


def apply_primitive_colour(faces):
    """Fold each face's primitive colour into its texels before baking.

    OoT tints Link's tunic through the primitive colour rather than the texture,
    which is how Goron and Zora tunics recolour the same art. The Kokiri tunic
    is prim (80,188,8) over a grey cloth texture, so a baker that ignores prim
    -- as the shared scene baker does, since scene faces are almost all white
    -- renders the tunic, hat and shoulders plain white.

    Untextured faces are given a 1x1 texture of the prim colour: clamped
    sampling makes every texel that colour, which is what the flat-shaded hat
    and tunic pieces should be.
    """
    tinted = 0
    for face in faces:
        prim = face.get('prim') or (255, 255, 255, 255)
        texture = face['texture']
        tinted_flat = (prim[:3] != (255, 255, 255)
                       and face.get('texture_segment') == GAMEPLAY_KEEP_SEGMENT)
        if prim[:3] == (255, 255, 255) and texture:
            continue
        if texture and not tinted_flat:
            colours = [(c[0] * prim[0] // 255, c[1] * prim[1] // 255,
                        c[2] * prim[2] // 255, c[3]) for c in texture['colors']]
            face['texture'] = dict(texture, colors=colours)
        else:
            face['texture'] = dict(width=1, height=1, colors=[prim],
                                   scale=(1.0, 1.0), shifts=0, shiftt=0,
                                   uls=0, ult=0, cms=2, cmt=2, masks=0, maskt=0)
        tinted += 1
    return tinted


GEAR_LISTS = (
    ('left_empty', 15, 'gLinkChildLeftFistFarDL'),
    ('left_sword', 15, 'gLinkChildLeftFistAndKokiriSwordFarDL'),
    ('right_empty', 18, 'gLinkChildRightHandClosedFarDL'),
    ('right_shield', 18, 'gLinkChildRightFistAndDekuShieldFarDL'),
    ('sheath', 19, 'gLinkChildSheathFarDL'),
)


def collect_equipment(data, keep, placed, oot):
    """z_player_lib.c hand/sheathed-sword DL variants; retain Flex slot layout.

    Replay the whole skeleton for each replacement so preceding material and
    matrix state is real. Only the replaced limb's faces join the resident mesh.
    """
    xml = ET.parse(oot / 'assets/xml/objects/object_link_child.xml')
    offsets = {e.attrib['Name']: int(e.attrib['Offset'], 0)
               for e in xml.iter('DList')}
    source = (oot / 'src/code/z_player_lib.c').read_text()
    base = collect_faces(data, keep, placed)
    faces = [dict(f, group='body') for f in base if f['limb'] not in (15, 18, 19)]
    for group, limb, symbol in GEAR_LISTS:
        if symbol not in source:
            raise ValueError('Player equipment list no longer referenced: ' + symbol)
        selected = [(i, m, o, (0x06000000 | offsets[symbol]) if i == limb else dl)
                    for i, m, o, dl in placed]
        faces.extend(dict(f, group=group) for f in collect_faces(data, keep, selected)
                     if f['limb'] == limb)
    return faces, base


def emit_equipment(out, faces):
    groups = ['body'] + [g for g, _, _ in GEAR_LISTS]
    lines = ['/* Generated: contiguous equipment DL ranges, shared POINT table. */',
             '#ifndef LINK_EQUIPMENT_H', '#define LINK_EQUIPMENT_H']
    for group in groups:
        ids = [i for i, f in enumerate(faces) if f['group'] == group]
        if not ids or ids != list(range(ids[0], ids[-1] + 1)):
            raise ValueError('Non-contiguous gear group: ' + group)
        lines += ['#define LINK_%s_FIRST %d' % (group.upper(), ids[0]),
                  '#define LINK_%s_COUNT %d' % (group.upper(), len(ids))]
    counts = {g: sum(f['group'] == g for f in faces) for g in groups}
    maximum = counts['body'] + max(counts['left_empty'], counts['left_sword']) + \
        max(counts['right_empty'], counts['right_shield']) + counts['sheath']
    lines += ['#define LINK_VISIBLE_POLYGONS %d' % maximum, '#endif']
    (out / 'link_equipment.h').write_text('\n'.join(lines) + '\n')


def flatten_faces(faces):
    """Flatten body materials, preserving the complete head's textures.

    Link is 62 units tall and his median face spans 7 units, so a 16x16 tile
    gives him 0.4 world units per texel -- roughly 35x finer than the scene's
    median face, on a model that is mostly flat-coloured cloth and skin anyway.
    That detail is invisible in play and the VRAM it costs is needed by the
    ground, which is what actually smears.

    Head artwork (including hair/skin, not just eyes/mouth) carries facial shape
    at the close gameplay camera and must not be replaced by per-face averages.
    """
    flattened = 0
    for face in faces:
        if face.get('texture_segment') in FACE_SEGMENTS or face.get('limb') == HEAD_LIMB:
            continue
        texture = face['texture']
        if not texture:
            continue
        colours = texture['colors']
        if not colours:
            continue
        opaque = [c for c in colours if c[3] >= 64] or colours
        n = len(opaque)
        average = tuple(sum(c[i] for c in opaque) // n for i in range(3)) + (255,)
        face['texture'] = dict(width=1, height=1, colors=[average],
                               scale=(1.0, 1.0), shifts=0, shiftt=0,
                               uls=0, ult=0, cms=2, cmt=2, masks=0, maskt=0)
        flattened += 1
    return flattened


def scale_faces(faces, scale):
    for face in faces:
        face['vertices'] = [
            (int(round(v[0] * scale)), int(round(v[1] * scale)),
             int(round(v[2] * scale))) + tuple(v[3:])
            for v in face['vertices']]
    return faces


def drop_degenerate(faces):
    """Drop faces that collapsed to a line or point once scaled to world units.

    Degeneracy is judged on the scaled bind pose, as before. A face kept here
    can still collapse in some animated pose, but VDP1 tolerates that far
    better than the alternative of re-testing every face every frame.
    """
    kept = []
    for face in faces:
        if len({v[:3] for v in face['vertices']}) == 3:
            kept.append(face)
    return kept


def ground_and_centre(faces):
    """Put the feet on y=0 and centre x/z, so the model sits on its position.

    Returns the shift as well: the runtime skinner rebuilds vertices from the
    limb-local data and has to apply the same offset to land in the same place.
    """
    points = [v[:3] for f in faces for v in f['vertices']]
    low = [min(p[i] for p in points) for i in range(3)]
    high = [max(p[i] for p in points) for i in range(3)]
    shift = (-(low[0] + high[0]) // 2, -low[1], -(low[2] + high[2]) // 2)
    for face in faces:
        face['vertices'] = [tuple(v[i] + shift[i] for i in range(3)) + tuple(v[3:])
                            for v in face['vertices']]
    return faces, shift


def write_model(faces, out_path, skinned=False):
    """Same KFR1 v2 container as FOREST.BIN, with no collision triangles.

    When `skinned`, vertices are deduplicated by (local position, limb), not by
    rounded world position. Two limbs' vertices can coincide in the bind pose -- the
    shoulder and upper arm meet exactly -- and merging them there would weld the
    limbs together the moment an animation moves them apart. The cost is a few
    extra vertices; the benefit is that every vertex has one unambiguous owner.
    """
    if skinned:
        # Pair each posed vertex with the limb-local coordinate it came from.
        # collect_faces() kept face['local'] in the same order as the vertices,
        # and every later stage rewrote them in place, so index i still matches.
        keys, locals_by_key = [], {}
        for f in faces:
            for v, loc, owner in zip(f['vertices'], f['local'],
                                     f.get('vertex_limbs', [f['limb']]*3)):
                key = (tuple(loc), owner)
                if key not in locals_by_key:
                    locals_by_key[key] = loc
                    keys.append(key)
        # The integer bind pose is only a container/extent placeholder. Live
        # geometry retains fractional world coordinates in the skinner.
        positions_by_key = {(tuple(loc), owner): v[:3]
                            for f in faces for v, loc, owner in zip(f['vertices'], f['local'],
                                f.get('vertex_limbs', [f['limb']]*3))}
        positions = [positions_by_key[k] for k in keys]
        skin_limbs = [k[1] for k in keys]
        skin_locals = [locals_by_key[k] for k in keys]
        lookup = None   # faces index through key_index below
        key_index = {k: i for i, k in enumerate(keys)}
    else:
        positions = list(dict.fromkeys(v[:3] for f in faces for v in f['vertices']))
        lookup = {p: i for i, p in enumerate(positions)}
        key_index = skin_limbs = skin_locals = None
    centre = tuple((min(p[i] for p in positions) + max(p[i] for p in positions)) // 2
                   for i in range(3))
    radius = math.ceil(max(math.dist(p, centre) for p in positions))

    texture = bytearray()
    records = bytearray()
    tiles = {}
    for face in faces:
        # A face collapsed to one colour needs no resolution: the smallest
        # tile VDP1 addresses carries it exactly as well as a 16x16 would, and
        # the difference is VRAM the ground needs.
        # Human directive: every character -- Link, NPCs and enemies -- is
        # plain-shaded, EXCEPT hair and face. Those live in the head limb's
        # display list, so the head keeps real texture and everything else
        # (tunic, skin, belt, boots, sword, shield) collapses to one colour.
        # Cutout alpha inside a flattened material is lost; nothing outside the
        # head currently relies on it.
        flat = face.get('limb') != HEAD_LIMB
        if flat:
            # One lit colour per flat face, deduplicated after RGB555 conversion.
            # Keep eye/mouth artwork on the normal textured path.
            sample = dict(face)
            corners = face['vertices']
            sample_centre = tuple(sum((v[k] if v[k] < 128 else v[k]-256)
                                      if face['lighting'] and 5 <= k <= 7 else v[k]
                                      for v in corners) / 3 for k in range(9))
            sample['vertices'] = [sample_centre] * 3
            baked = scene_tool.bake(sample, 8)
            colour = struct.unpack_from('>H', baked, 2 * (baked[32] >> 4))[0]
            tile = struct.pack('>16H', 0, colour, *([0] * 14)) + bytes([0x11] * 8)
            width, height = 8, 2
        else:
            # Keep eye/mouth detail at 16; other head materials retain their
            # real texture at 8, instead of one flat color per triangle.
            size = 8 if face.get('limb') == HEAD_LIMB and face.get('texture_segment') not in FACE_SEGMENTS else 16
            tile = scene_tool.bake(face, size)
            width, height = size, size
        if tile not in tiles:
            tiles[tile] = len(texture)
            texture.extend(tile)
        offset = tiles[tile]
        ids = ([key_index[(tuple(loc), owner)] for loc, owner in
                zip(face['local'], face.get('vertex_limbs', [face['limb']]*3))]
               if key_index is not None else [lookup[v[:3]] for v in face['vertices']])
        records.extend(struct.pack('>4HIIHH', *ids, ids[2], offset + 32, offset,
                                   (width // 8) << 8 | height,
                                   int(face['transparent']) | (int(face['cull']) << 1)))

    vertex_data = b''.join(struct.pack('>3h', *p) for p in positions)
    vertex_data += bytes((-len(vertex_data)) % 4)
    vo = 64
    fo = vo + len(vertex_data)
    co = fo + len(records)
    to = (co + 7) & ~7
    total = to + len(texture)
    header = struct.pack('>9I3i4I', KFR1_MAGIC, 2, len(positions), len(faces),
                         vo, fo, to, len(texture), total, *centre, radius,
                         len(faces) + 3, co, 0)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(header + vertex_data + records + bytes(to - co) + texture)
    return positions, tiles, skin_limbs, skin_locals


# Animation clips baked for the slice, as (name, decomp symbol, frame stride).
#
# Offsets are not hardcoded: gameplay_keep's LinkAnimationHeader table is one
# contiguous array in the same order as player_anim_headers.c, so the known
# idle offset (recipe 'animation') anchors every other symbol by index. The
# whole 573-entry table is validated before use -- see resolve_animations().
#
# `stride` decimates long clips. Idle is a 184-frame fidget loop whose first
# 20 frames are the standing breath cycle we want; sampling the rest would cost
# ROM for motion nothing in the slice triggers. Fall is a 37-frame descent that
# reads fine at a third of the rate because the pose barely changes.
CLIPS = (
    # name       symbol                                    first  count stride
    ('idle',    'gPlayerAnim_link_normal_waitF_typeA_20f',      0,   20, 1),
    ('walk',    'gPlayerAnim_link_normal_walk',                 0,   29, 1),
    ('run',     'gPlayerAnim_link_normal_run',                  0,   20, 1),
    ('fall',    'gPlayerAnim_link_normal_fall',                 0,   12, 3),
    ('landing', 'gPlayerAnim_link_normal_landing',              0,   21, 1),
    ('roll',    'gPlayerAnim_link_normal_landing_roll',         0,   32, 1),
    # z_player.c D_80854190[PLAYER_MWA_FORWARD_SLASH_1H], then recovery.
    ('slash',   'gPlayerAnim_link_fighter_normal_kiru',         0,    5, 1),
    ('recover', 'gPlayerAnim_link_fighter_normal_kiru_end',     0,    8, 1),
    # PLAYER_ANIMGROUP_defense / defense_wait, one-handed equipment group.
    ('guard',   'gPlayerAnim_link_normal_defense',              0,    2, 1),
    ('guard_wait', 'gPlayerAnim_link_normal_defense_wait',      0,   20, 1),
    # The opening cutscene's poses, from the player cues in
    # gLinkHouseIntroSleepCs / gLinkHouseIntroWakeUpCs. Mapped to these symbols
    # in z_player.c:15039-15042; see tools/build_cutscenes.py PLAYER_CUES.
    # Decimated hard: they are slow, and the clip tables sit below the same
    # .bss/SGL boundary as everything else.
    ('sleeping',  'gPlayerAnim_clink_op3_wait1',                0,   10, 2),
    ('turn_over', 'gPlayerAnim_clink_op3_negaeri',              0,   12, 3),
    # okiagari is 365 frames and tatiagari 110; sampled sparsely so the pose
    # actually reaches sitting and standing rather than stopping just after it
    # starts to move.
    ('sit_up',    'gPlayerAnim_clink_op3_okiagari',             0,   24, 15),
    ('stand_up',  'gPlayerAnim_clink_op3_tatiagari',            0,   20, 5),
    ('turn_look', 'gPlayerAnim_link_demo_furimuki',             0,   10, 2),
)

# Rotations keep their full 16-bit binang precision. The clip tables share the
# RAM below SGL's work area with .bss, so they are not free; the makefile's
# malloc arena was trimmed to measured demand to pay for them.

IDLE_SYMBOL = 'gPlayerAnim_link_normal_waitF_typeA_20f'


def resolve_animations(oot, keep, idle_offset):
    """Map each decomp animation symbol to its offset in gameplay_keep.

    gameplay_keep holds the LinkAnimationHeaders as one contiguous 8-byte array
    in declaration order, so the recipe's known idle offset fixes the table base
    and every other symbol follows by index. That assumption is checked, not
    trusted: all 573 headers must decode as a plausible frame count, zero pad
    and a segment-7 pointer before any offset derived here is used.
    """
    source = (oot / 'assets/objects/gameplay_keep/player_anim_headers.c').read_text()
    names = re.findall(r'LinkAnimationHeader (\w+) = \{', source)
    if IDLE_SYMBOL not in names:
        sys.exit('%s not found in player_anim_headers.c' % IDLE_SYMBOL)
    base = idle_offset - names.index(IDLE_SYMBOL) * 8
    for index in range(len(names)):
        count, pad, segment = struct.unpack_from('>hhI', keep, base + index * 8)
        if not (0 < count < 1000 and pad == 0 and (segment >> 24) == 7):
            sys.exit('animation header table failed validation at %s (%#x): '
                     'frames=%d pad=%d segment=%#x'
                     % (names[index], base + index * 8, count, pad, segment))
    return {name: base + i * 8 for i, name in enumerate(names)}


def read_animation_frames(keep, animetion, offset, first, count, stride,
                          limb_count):
    """Read `count` frames from one LinkAnimation, every `stride`-th frame.

    Same layout as read_animation(), just kept across a range: entry 0 of each
    frame is the root translation and entry i+1 is limb i's rotation in binang.
    Sampling past the clip wraps, so a decimated loop still closes on itself.
    """
    frames, _, _ = struct.unpack_from('>hhI', keep, offset)
    out = []
    for step in range(count):
        frame = (first + step * stride) % frames
        _, root, rotations = read_animation(keep, animetion, offset, frame,
                                             limb_count)
        out.append((root, rotations))
    return frames, out


def emit_animation(out_dir, clips, limbs, skin_limbs, skin_locals, shift, scale):
    """Write the skinning tables and clip rotations the runtime poses from.

    Rotation data is const: it lives in ROM with the rest of the ELF, not in the
    ~9 KB of .bss left below SGL's work area. Only the posed POINT table is RAM,
    and there is exactly one of it, which is why frames are re-posed at runtime
    instead of pre-baked -- one baked POINT table is 12 bytes a vertex and two
    of them would exhaust the entire remaining budget.
    """
    banner = '/* Generated by game/tools/build_link_model.py -- do not edit. */'
    h = [banner, '', '#ifndef LINK_CLIPS_H', '# define LINK_CLIPS_H', '',
         '# include <stdint.h>', '',
         '# define LINK_LIMB_COUNT      %d' % len(limbs),
         '# define LINK_SKIN_VERTICES   %d' % len(skin_limbs),
         '# define LINK_CLIP_COUNT      %d' % len(clips),
         '# define LINK_ANIM_SHIFT_X    %d' % shift[0],
         '# define LINK_ANIM_SHIFT_Y    %d' % shift[1],
         '# define LINK_ANIM_SHIFT_Z    %d' % shift[2],
         '/* model units -> world units, as 16.16 */',
         '# define LINK_ANIM_SCALE_Q16  %d' % int(round(scale * 65536)), '']
    for index, (name, *_rest) in enumerate(clips):
        h.append('# define LINK_CLIP_%-10s %d' % (name.upper(), index))
    h += ['', 'typedef struct { int16_t x, y, z; } link_vec3_t;',
          'typedef struct { uint8_t child, sibling; link_vec3_t pos; } link_limb_t;',
          'typedef struct { uint16_t first, count; } link_clip_t;', '',
          'extern const link_limb_t  link_limbs[LINK_LIMB_COUNT];',
          'extern const link_clip_t  link_clips[LINK_CLIP_COUNT];',
          '/* Per frame: the root translation, at full precision. */',
          'extern const int16_t      link_root[][3];',
          '/* Per frame: one binang rotation per limb, full precision. */',
          'extern const int16_t      link_rotations[][LINK_LIMB_COUNT * 3];',
          '/* Per skinned vertex: owning limb, and its limb-local position. */',
          'extern const uint8_t      link_vertex_limb[LINK_SKIN_VERTICES];',
          'extern const link_vec3_t  link_vertex_local[LINK_SKIN_VERTICES];',
          '#endif', '']
    (out_dir / 'link_clips.h').write_text('\n'.join(h))

    c = [banner, '', '#include "link_clips.h"', '',
         'const link_limb_t link_limbs[LINK_LIMB_COUNT] = {']
    for limb in limbs:
        c.append('    { %3d, %3d, { %6d, %6d, %6d } },'
                 % (limb['child'], limb['sibling'], *limb['pos']))
    c += ['};', '', 'const link_clip_t link_clips[LINK_CLIP_COUNT] = {']
    first = 0
    rows = []
    # FALL carries authored root travel (2292 -> -3328 model Y). Collision
    # already moves the actor through the jump/fall. Keep its pelvis at the
    # standing reference; retain every limb rotation, not the second trajectory.
    idle_root = next(frames[0][0] for name, *_, frames in clips if name == 'idle')
    for name, _symbol, _start, count, _stride, frames in clips:
        c.append('    { %4d, %3d },   /* %s */' % (first, len(frames), name))
        first += len(frames)
        if name == 'fall':
            rows.extend((idle_root, rotations) for _, rotations in frames)
        else:
            rows.extend(frames)
    c += ['};', '', 'const int16_t link_root[][3] = {']
    for root, _rotations in rows:
        c.append('    { %6d, %6d, %6d },' % tuple(root))
    c += ['};', '', 'const int16_t link_rotations[][LINK_LIMB_COUNT * 3] = {']
    for _root, rotations in rows:
        c.append('    { %s },' % ', '.join('%6d' % v for rot in rotations for v in rot))
    c += ['};', '', 'const uint8_t link_vertex_limb[LINK_SKIN_VERTICES] = {']
    for i in range(0, len(skin_limbs), 16):
        c.append('    ' + ' '.join('%3d,' % v for v in skin_limbs[i:i + 16]))
    c += ['};', '', 'const link_vec3_t link_vertex_local[LINK_SKIN_VERTICES] = {']
    for local in skin_locals:
        c.append('    { %6d, %6d, %6d },' % tuple(local))
    c += ['};', '']
    (out_dir / 'link_clips.c').write_text('\n'.join(c))
    return sum(len(f) for *_r, f in clips)


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    recipe = json.loads((root / 'assets/dynamic/link/source.json').read_text())
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path, default=root / 'build/generated' / 'LINK.BIN')
    ap.add_argument('--scale', type=float, default=recipe['scale'],
                    help='model units -> world units')
    ap.add_argument('--animation', type=lambda v: int(v, 0), default=int(recipe['animation'], 0),
                    help='LinkAnimationHeader offset in gameplay_keep')
    ap.add_argument('--frame', type=int, default=recipe['frame'])
    ap.add_argument('--animate', action='store_true',
                    help='also emit link_anim.c/.h: the skeleton, per-vertex '
                         'limb ownership and the baked locomotion clips that '
                         'the runtime skinner poses each frame')
    ap.add_argument('--flat', action='store_true',
                    help='collapse every face except the eyes and mouth to a '
                         'single colour, freeing VDP1 VRAM for the scene')
    args = ap.parse_args()

    data = read_object(args.oot, OBJECT, args.rom_dir)
    keep = read_object(args.oot, 'gameplay_keep', args.rom_dir)
    animetion = read_object(args.oot, 'link_animetion', args.rom_dir)
    limbs = read_limbs(data)
    frames, root, rotations = read_animation(keep, animetion, args.animation,
                                             args.frame, LIMB_COUNT)
    placed = walk_skeleton(limbs, rotations, root)
    faces, original = collect_equipment(data, keep, placed, args.oot)
    flattened = flatten_faces(faces) if args.flat else 0
    tinted = apply_primitive_colour(faces)
    faces = scale_faces(faces, args.scale)
    if not args.animate:
        faces = drop_degenerate(faces)
    # Held blade changes mesh extents, never Link's collision/bind origin.
    _, shift = ground_and_centre(scale_faces(original, args.scale))
    for face in faces:
        face['vertices'] = [tuple(v[i] + shift[i] for i in range(3)) + tuple(v[3:])
                            for v in face['vertices']]
    positions, tiles, skin_limbs, skin_locals = write_model(
        faces, args.out, skinned=args.animate)
    emit_equipment(args.out.parent, faces)

    clips = baked = 0
    if args.animate:
        offsets = resolve_animations(args.oot, keep, args.animation)
        resolved = []
        for name, symbol, first, count, stride in CLIPS:
            if symbol not in offsets:
                sys.exit('%s: unknown animation symbol' % symbol)
            total, sampled = read_animation_frames(
                keep, animetion, offsets[symbol], first, count, stride,
                LIMB_COUNT)
            resolved.append((name, symbol, first, count, stride, sampled))
            print('clip    : %-8s %3d/%3d frames stride %d  (%#07x)'
                  % (name, len(sampled), total, stride, offsets[symbol]))
        baked = emit_animation(args.out.parent, resolved, limbs, skin_limbs,
                               skin_locals, shift, args.scale)
        clips = len(resolved)

    points = [v[:3] for f in faces for v in f['vertices']]
    extent = [(min(p[i] for p in points), max(p[i] for p in points))
              for i in range(3)]
    print('object  : %s (%d bytes)' % (OBJECT, len(data)))
    print('pose    : %#06x frame %d of %d' % (args.animation, args.frame, frames))
    print('limbs   : %d placed, %d drawn (near head, far body)'
          % (len(placed), sum(1 for *_, far in placed if far)))
    print('faces   : %d  vertices %d  tiles %d'
          % (len(faces), len(positions), len(tiles)))
    print('prim    : %d faces tinted by primitive colour (tunic/hat)' % tinted)
    if args.flat:
        print('flat    : %d faces collapsed to one colour (head artwork kept)'
              % flattened)
    if args.animate:
        # Rotations are const and live in ROM; only the posed POINT table costs
        # the scarce .bss below SGL's work area.
        print('anim    : %d clips, %d frames, %d rodata bytes; %d skinned vertices'
              % (clips, baked, baked * (LIMB_COUNT * 3 + 3) * 2, len(skin_limbs)))
        print('          runtime POINT table %d bytes of .bss'
              % (len(positions) * 12))
    print('extent  : x %s  y %s  z %s' % tuple(extent))
    print('height  : %d world units' % (extent[1][1] - extent[1][0]))
    print('out     : %s' % args.out)


if __name__ == '__main__':
    main()
