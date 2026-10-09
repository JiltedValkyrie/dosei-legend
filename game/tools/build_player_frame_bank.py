#!/usr/bin/env python3
"""Prototype the shared real-Player frame bank and its complete RAM budget.

Offline tool (float allowed). Nothing here is loaded by the game yet.

Residency from real triggers, never clip names:
  * z_player.c is split into top-level entities (functions/tables). A clip is
    GLOBAL when reachable from Player_Init/Update/Draw/Destroy without passing
    through the two cutscene action tables (D_80854B18, D_80854E50). Ocarina,
    get-item etc. are therefore resident because ordinary play reaches them.
  * Remaining clips belong to cutscene actions. An action is GLOBAL when any
    actor source, z_player_lib or Player code outside those tables names it
    (actors can start it anywhere). Otherwise it is SCENE-triggered only when
    a scene's own cutscene data cues it (CS_PLAYER_CUE -> sCueToCsActionMap);
    those clips go to that scene's preload pack (behind the loading screen).
  * Anything not classified stays GLOBAL (fail safe).

Encoding: one delta-block per clip (see player_frame_pack.py). Root translation
and the face word stay exact on every source frame. Each rotation channel has
its own quantiser shift. Kept poses are stored as absolute key + signed deltas
inside blocks of 8, so random access stays inside one block. Stride 1/2/3 keeps
every s-th pose (last frame always kept) with shortest-arc interpolation.

Acceptance per clip is measured by forward kinematics on BOTH real skeletons
(object_link_boy/object_link_child limb tables, SkelAnime's
translate * Rz * Ry * Rx order): every limb origin plus a blade point on each
hand must stay within --tol world units (Link scale 0.01) of the source pose
on every frame. The cheapest passing encoding is chosen; clips needing full
precision keep it.
"""
import argparse
import json
import math
import multiprocessing
import os
import re
import struct
from pathlib import Path

import player_frame_pack as fp
import size_player_frames as frames

GAME = Path(__file__).resolve().parent.parent
CHANNELS = 67          # root xyz, 21 limbs x 3 rotations, face word
ROT0, ROT1 = 3, 66     # rotation channel range
LIMBS = 21
CS_TABLES = ('D_80854B18', 'D_80854E50')
ROOTS = ('Player_Init', 'Player_Update', 'Player_Draw', 'Player_Destroy')
# Limb-local anchors from z_player_lib.c (model units). Limb index =
# PLAYER_LIMB_* - 1. Each anchor has a class; the clip's action context
# decides whether that class is gameplay-tight or only visual.
L_HAND, R_HAND, SHEATH, HEAD, R_FOOT, L_FOOT = 15, 18, 19, 10, 5, 8
# sMeleeWeaponLengths per age: child Kokiri 3000; adult Master 4000, Biggoron 5500.
SWORD_LENGTHS = {'child': (3000.0,), 'adult': (4000.0, 5500.0)}
WEAPON_FIXED = [(5000.0, -400.0, 1000.0), (5000.0, 1400.0, -1000.0),   # tips 1, 2
                (0.0, 400.0, 0.0), (0.0, 1400.0, -1000.0), (0.0, -400.0, 1000.0)]  # bases
SHIELD_RH = [(-4500.0, -3000.0, -600.0), (1500.0, -3000.0, -600.0),
             (-4500.0, 3000.0, -600.0), (1500.0, 3000.0, -600.0)]
SHIELD_BACK = [(-3000.0, -3000.0, -900.0), (3000.0, -3000.0, -900.0),
               (-3000.0, 3000.0, -900.0), (3000.0, 3000.0, -900.0)]
FOOT = {'adult': (200.0, 300.0, 0.0), 'child': (200.0, 200.0, 0.0)}
# Always gameplay-tight: limb origins (bodyPartsPos), focus, feet, both shield
# quads (hand shield whenever drawn; the back shield is a real collider too).
ALWAYS_TIGHT = frozenset({'origin', 'focus', 'foot', 'shield'})


def anchor_points(age):
    """limb -> [(point, class)]"""
    return {L_HAND: [((l, 400.0, 0.0), 'weapon') for l in SWORD_LENGTHS[age]]
                    + [(p, 'weapon') for p in WEAPON_FIXED]
                    + [((398.0, 1419.0, 244.0), 'held')],
            R_HAND: [(p, 'shield') for p in SHIELD_RH]
                    + [((100.0, 1500.0, 0.0), 'held'), ((100.0, 1640.0, 0.0), 'held')],
            SHEATH: [(p, 'shield') for p in SHIELD_BACK],
            HEAD: [((1100.0, -700.0, 0.0), 'focus')],
            R_FOOT: [(FOOT[age], 'foot'), ((0.0, -300.0, 0.0), 'foot')],
            L_FOOT: [(FOOT[age], 'foot'), ((0.0, -300.0, 0.0), 'foot')]}


SCALE = 0.01                                # Link actor scale, model -> world


# ---------------------------------------------------------------- data
def clip_data(oot, data_name, count):
    text = (oot / 'extracted/ntsc-1.2/assets/misc/link_animetion' /
            (data_name + '.inc.c')).read_text(encoding='utf-8')
    values = [int(v, 16) if 'x' in v else int(v)
              for v in re.findall(r'^\s*(-?(?:0x[0-9A-Fa-f]+|\d+)),', text, re.M)]
    if len(values) != count * CHANNELS:
        raise ValueError(f'{data_name}: {len(values)} values, expected {count * CHANNELS}')
    return [values[i * CHANNELS:(i + 1) * CHANNELS] for i in range(count)]


def skeleton(oot, obj, prefix):
    root = oot / 'extracted/ntsc-1.2/assets/objects' / obj
    names = re.findall(r'&(\w+), // \d+', (root / f'{prefix}Limbs.inc.c').read_text(encoding='utf-8'))
    limbs = []
    for name in names:
        text = (root / (name + '.inc.c')).read_text(encoding='utf-8')
        pos = [int(v) for v in re.findall(r'^\s*(-?\d+), // [xyz]$', text, re.M)]
        child = int(re.search(r'/\* (\d+) \*/[^\n]*// child', text).group(1))
        sibling = int(re.search(r'/\* (\d+) \*/[^\n]*// sibling', text).group(1))
        limbs.append((pos, child, sibling))
    if len(limbs) != LIMBS:
        raise ValueError(f'{obj}: {len(limbs)} limbs')
    return limbs


def ancestors(limbs):
    """limb -> ancestor limbs, root first."""
    out = {}
    def walk(i, chain):
        out[i] = chain
        child, sibling = limbs[i][1], limbs[i][2]
        if child != 255:
            walk(child, chain + [i])
        if sibling != 255:
            walk(sibling, chain)
    walk(0, [])
    return out


# ---------------------------------------------------------------- kinematics
def rot_zyx(x, y, z):
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    # Rz * Ry * Rx
    return [[cz * cy, cz * sy * sx - sz * cx, cz * sy * cx + sz * sx],
            [sz * cy, sz * sy * sx + cz * cx, sz * sy * cx - cz * sx],
            [-sy, cy * sx, cy * cx]]


def mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def apply(m, t, v):
    return [m[i][0] * v[0] + m[i][1] * v[1] + m[i][2] * v[2] + t[i] for i in range(3)]


def anchor_layout(limbs, points):
    """Per anchor, in anchors() order: (class, limbs whose rotation moves it)."""
    chain = ancestors(limbs)
    layout = []
    def walk(i):
        layout.append(('origin', chain[i]))
        for _, cls in points.get(i, ()):
            layout.append((cls, chain[i] + [i]))
        child, sibling = limbs[i][1], limbs[i][2]
        if child != 255:
            walk(child)
        if sibling != 255:
            walk(sibling)
    walk(0)
    return layout


def anchors(limbs, points, frame):
    """Anchor positions (model units, anchor_layout order) and limb origins."""
    out, origins = [], [None] * LIMBS
    k = math.pi / 32768.0
    def walk(i, m, t):
        pos = frame[0:3] if i == 0 else limbs[i][0]
        rx, ry, rz = frame[3 + i * 3:6 + i * 3]
        nt = apply(m, t, pos)
        nm = mul(m, rot_zyx(rx * k, ry * k, rz * k))
        origins[i] = nt
        out.append(nt)
        for p, _ in points.get(i, ()):
            out.append(apply(nm, nt, p))
        child, sibling = limbs[i][1], limbs[i][2]
        if child != 255:
            walk(child, nm, nt)
        if sibling != 255:
            walk(sibling, m, t)
    walk(0, [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0.0, 0.0, 0.0])
    return out, origins


# ---------------------------------------------------------------- encoding
STRIDES = (3, 2, 1)


def violations(skels, src, dec, tight, tol, visual_tol):
    """Worst error / limit and per-channel blame for anchors over their limit.

    Blame for an over-limit anchor goes to the rotation channels of the limbs
    that move it: that channel's angular error at that frame times its lever
    (distance from the limb origin to the anchor)."""
    worst, blame = 0.0, [0.0] * 63
    k = math.pi / 32768.0
    for limbs, points, layout in skels:
        for a, b in zip(src, dec):
            if a == b:
                continue
            pa, oa = anchors(limbs, points, a)
            pb, _ = anchors(limbs, points, b)
            for (cls, movers), p, r in zip(layout, pa, pb):
                limit = tol if cls in tight else visual_tol
                d = math.dist(p, r) * SCALE / limit
                if d > worst:
                    worst = d
                if d <= 1.0:
                    continue
                for limb in movers:
                    lever = math.dist(oa[limb], p) * SCALE
                    for axis in range(3):
                        c = limb * 3 + axis
                        blame[c] += abs(fp.wrap(a[3 + c] - b[3 + c])) * k * lever
    return worst, blame


def choose(skels, src, tight, tol, visual_tol):
    """Smallest block within limits. Each round raises precision only on the
    three channels most blamed for over-limit anchors."""
    best = None
    for stride in STRIDES:
        if stride > 1 and len(src) < 3:
            continue
        shifts = [8] * 63
        for _ in range(200):
            exact = stride == 1 and all(s == 0 for s in shifts)
            dec = src if exact else fp.reference(src, shifts, stride)
            worst, blame = (0.0, None) if exact else violations(
                skels, src, dec, tight, tol, visual_tol)
            if worst <= 1.0:
                size = len(fp.pack_clip(src, shifts, stride))
                if best is None or size < best['bytes']:
                    hist = [sum(1 for s in shifts if s == sh) for sh in (8, 6, 4, 2, 0)]
                    best = dict(stride=stride, error=round(worst, 4), bytes=size,
                                shift_hist=hist, shifts=shifts[:])
                break
            ranked = sorted((b, c) for c, b in enumerate(blame) if b > 0 and shifts[c] > 0)
            if not ranked:
                break          # only interpolation error left: try the next stride
            for _, c in ranked[-3:]:
                shifts[c] -= 2
    if best is None:
        raise AssertionError('exact encoding must pass')
    return best


# ---------------------------------------------------------------- residency
ENTITY = re.compile(r'^(?![#/ \t}])[^\n;]*?\b(\w+)\s*(?:\(|\[[^\]]*\]\s*=|\s=)', re.M)


def entities(text):
    """Top-level definitions -> body text (functions and initialised tables)."""
    out = {}
    starts = [(m.start(), m.group(1)) for m in ENTITY.finditer(text)]
    for (pos, name), nxt in zip(starts, starts[1:] + [(len(text), None)]):
        body = text[pos:nxt[0]]
        if '{' in body:
            out.setdefault(name, '')
            out[name] += body
    return out


def residency(oot, clip_names):
    rel = 'src/overlays/actors/ovl_player_actor/z_player.c'
    text = (oot / rel).read_text(encoding='utf-8')
    ents = entities(text)
    ident = re.compile(r'\b\w+\b')
    refs = {n: set(ident.findall(b)) for n, b in ents.items()}
    def reach(starts, blocked):
        seen, todo = set(), list(starts)
        while todo:
            n = todo.pop()
            if n in seen or n in blocked or n not in refs:
                continue
            seen.add(n)
            todo += [r for r in refs[n] if r in refs]
        return seen
    glob_ents = reach(ROOTS, set(CS_TABLES))
    global_clips = {c for e in glob_ents for c in refs[e] if c in clip_names}
    lib = (oot / 'src/code/z_player_lib.c').read_text(encoding='utf-8')
    global_clips |= {c for c in clip_names if re.search(r'\b' + c + r'\b', lib)}

    # Cutscene action -> clips only those actions need.
    action_clips = {}
    for table in CS_TABLES:
        for line in ents.get(table, '').splitlines():
            m = re.search(r'\{\s*-?\d+\s*,\s*&?(\w+)\s*\},\s*// (PLAYER_CSACTION_\w+)', line)
            if not m:
                continue
            target, action = m.groups()
            found = {target} if target in clip_names else {
                c for e in reach([target], set(CS_TABLES)) for c in refs[e] if c in clip_names}
            action_clips.setdefault(action, set()).update(found - global_clips)

    # Global start sites: Player code outside the cutscene tables, player lib,
    # and every non-actor translation unit. Actor files are scene-scoped below.
    outside = re.sub(r'static struct_80854B18 D_808\w+\[PLAYER_CSACTION_MAX\] = \{.*?\n\};', '',
                     text, flags=re.S)
    cue_map_m = re.search(r'sCueToCsActionMap\[PLAYER_CUEID_MAX\] = \{(.*?)\n\};', text, re.S)
    outside = outside.replace(cue_map_m.group(0), '')
    globally_started = set(re.findall(r'PLAYER_CSACTION_\w+', outside + lib))
    cue_to_action = {}
    for line in cue_map_m.group(1).splitlines():
        m = re.search(r'-?(PLAYER_CSACTION_\w+),\s*// (PLAYER_CUEID_\w+)', line)
        if m:
            cue_to_action[m.group(2)] = m.group(1)
    action_files = {}
    file_ids, file_spawns = {}, {}
    for path in (oot / 'src').rglob('*.c'):
        if path.name in ('z_player.c', 'z_player_lib.c'):
            continue
        body = path.read_text(encoding='utf-8', errors='replace')
        actions = set(re.findall(r'PLAYER_CSACTION_\w+', body))
        cues = re.findall(r'CS_PLAYER_CUE\((PLAYER_CUEID_\w+)', body)
        actions |= {cue_to_action[c] for c in cues if c in cue_to_action}
        posix = path.as_posix()
        if '/overlays/actors/' not in posix:
            globally_started |= actions
            continue
        ids = set(re.findall(r'ACTOR_[A-Z0-9_]+', body[:4000]))
        ids = {i for i in ids if i not in ('ACTOR_ID_MAX', 'ACTOR_EN_ITEM00')}
        # Profile id is the first ACTOR_ enum in the file header area.
        prof = re.search(r'/\*\*/ (ACTOR_[A-Z0-9_]+),', body)
        file_ids[path] = {prof.group(1)} if prof else ids
        file_spawns[path] = set(re.findall(
            r'Actor_Spawn\([\s\S]{0,220}?(ACTOR_[A-Z0-9_]+)', body))
        for act in actions:
            action_files.setdefault(act, set()).add(path)

    scene_root = oot / 'extracted/ntsc-1.2/assets/scenes'
    actor_scenes = {}
    scenes = {}
    for path in scene_root.rglob('*'):
        if path.suffix not in ('.c',) and not path.name.endswith('.inc.c'):
            continue
        rel = path.relative_to(scene_root)
        if len(rel.parts) < 2:
            continue
        scene = rel.parts[1]
        body = path.read_text(encoding='utf-8', errors='replace')
        for aid in set(re.findall(r'\b(ACTOR_[A-Z0-9_]+)\b', body)):
            actor_scenes.setdefault(aid, set()).add(scene)
        cues = re.findall(r'CS_PLAYER_CUE\((PLAYER_CUEID_\w+)', body)
        if cues:
            scenes.setdefault(scene, set()).update(cue_to_action.get(c) for c in cues)

    # Scenes of an actor file. None means not proven (stay resident).
    file_scene_cache = {}

    def scenes_of(path, stack):
        if path in file_scene_cache:
            return file_scene_cache[path]
        if path in stack:
            return None
        owned = file_ids.get(path, set())
        found = set()
        unknown = False
        for i in owned:
            if i in actor_scenes:
                found |= actor_scenes[i]
            else:
                unknown = True
        if unknown:
            parents = [p for p, sp in file_spawns.items() if owned & sp and p != path]
            if not parents:
                file_scene_cache[path] = None
                return None
            found = set()
            for parent in parents:
                got = scenes_of(parent, stack | {path})
                if got is None:
                    file_scene_cache[path] = None
                    return None
                found |= got
            if not found:
                file_scene_cache[path] = None
                return None
        file_scene_cache[path] = found
        return found

    resident = set(global_clips)
    for action, clips in action_clips.items():
        if action in globally_started:
            resident |= clips
    packs = {}
    scene_actions = {s: set(a) for s, a in scenes.items()}
    for action, files in action_files.items():
        if action in globally_started:
            continue
        clip_set = action_clips.get(action, set())
        if not clip_set:
            continue
        union, proven = set(), True
        for path in files:
            got = scenes_of(path, set())
            if got is None:
                proven = False
                break
            union |= got
        if not proven or not union:
            resident |= clip_set
            continue
        for scene in union:
            scene_actions.setdefault(scene, set()).add(action)
    for scene, actions in scene_actions.items():
        clips = set()
        for a in actions:
            if a in globally_started:
                continue
            clips |= action_clips.get(a, set())
        clips -= resident
        if clips:
            packs[scene] = clips
    classified = resident | {c for v in packs.values() for c in v}
    unclassified = set(clip_names) - classified
    started_any = set(globally_started) | {a for v in scene_actions.values() for a in v}
    started_any |= set(action_files)
    unreachable = {c for a, cs in action_clips.items() if a not in started_any for c in cs}
    unreachable -= classified
    resident |= unclassified - unreachable
    return resident, packs, unreachable


def clip_context(oot, clip_names):
    """clip -> (ages, extra gameplay-tight classes).

    Uncertain stays strict (Astra review): weapon and held-actor anchors are
    tight for every clip reachable from ordinary Player actions, because the
    melee weapon and held actor persist across actions. Only clips reachable
    solely through the cutscene action tables are relaxed; that is a candidate
    rule still pending call/state-flow proof (weapon collider off during
    cutscene actions). Clips also named in z_player_lib stay strict.
    Ages come from sAgeProperties (age-only clips use one skeleton)."""
    rel = 'src/overlays/actors/ovl_player_actor/z_player.c'
    text = (oot / rel).read_text(encoding='utf-8')
    ents = entities(text)
    ident = re.compile(r'\b\w+\b')
    refs = {n: set(ident.findall(b)) for n, b in ents.items()}
    seen, todo = set(), list(ROOTS)
    while todo:
        n = todo.pop()
        if n in seen or n in CS_TABLES or n not in refs:
            continue
        seen.add(n)
        todo += [r for r in refs[n] if r in refs]
    ordinary = {c for n in seen for c in refs[n] if c in clip_names}
    lib = (oot / 'src/code/z_player_lib.c').read_text(encoding='utf-8')
    (adult_block, child_block), rest = frames.age_blocks(text)
    out = {}
    for clip in clip_names:
        word = re.compile(r'\b' + re.escape(clip) + r'\b')
        relaxed = clip not in ordinary and not word.search(lib)
        cls = frozenset() if relaxed else frozenset({'weapon', 'held'})
        a, c, o = word.search(adult_block), word.search(child_block), word.search(rest)
        ages = ('adult',) if a and not c and not o else ('child',) if c and not a and not o             else ('adult', 'child')
        out[clip] = (ages, cls)
    return out


_W = {}


def _init_worker(oot):
    for age, obj, prefix in (('adult', 'object_link_boy', 'gLinkAdult'),
                             ('child', 'object_link_child', 'gLinkChild')):
        limbs, points = skeleton(oot, obj, prefix), anchor_points(age)
        _W[age] = (limbs, points, anchor_layout(limbs, points))


def _encode(job):
    data, src, ages, tight, tol, visual_tol = job
    skels = [_W[a] for a in ages]
    return data, choose(skels, src, tight, tol, visual_tol)


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=os.environ.get('OOT'))
    parser.add_argument('--objdump', required=True)
    parser.add_argument('--player-gc', type=Path,
                        default=GAME / 'build/player-migration/gc/source_profile.o')
    parser.add_argument('--tol', type=float, default=0.5,
                        help='max anchor error, world units (Link scale 0.01)')
    parser.add_argument('--visual-tol', type=float, default=2.0,
                        help='limit for anchors the action cannot use for gameplay')
    parser.add_argument('--current', type=int, default=423472,
                        help='bytes of the existing LINKANIM heap block reused')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/frame_bank.json')
    parser.add_argument('--bank', type=Path, default=GAME / 'build/player-migration/bank')
    args = parser.parse_args()
    if args.oot is None:
        raise SystemExit('set OOT or --oot')
    heads, counts = frames.headers(args.oot), frames.frame_counts(args.oot)
    # The GC probe object is optional: the source text scan below covers
    # every clip the Player and the Saturn C clips name.
    refs = frames.relocated(args.objdump, args.player_gc) if args.player_gc.exists() else set()
    # Fail safe (Player cutover, 2026-10-09): the GC probe's relocations
    # missed clips the linked Player reaches through age/action tables (child
    # ladder, chest, guard, jump slash...). Every header the Player sources
    # name, and every clip the Saturn C cutscenes pose (build_link_model
    # CLIPS), is in the bank: a missing id is a fatal error at runtime.
    text = ''
    for rel in ('src/code/z_player_lib.c', 'src/overlays/actors/ovl_player_actor/z_player.c'):
        text += (args.oot / rel).read_text(encoding='utf-8')
    text += (GAME / 'tools/build_link_model.py').read_text(encoding='utf-8')
    named = set(re.findall(r'\bgPlayerAnim_\w+', text))
    reach = sorted(h for h in heads if h in refs or h in named)
    resident_h, packs_h, unreachable_h = residency(args.oot, set(reach))
    context = clip_context(args.oot, set(reach))
    per_data = {}
    for h in reach:
        ages, cls = context[h]
        old = per_data.get(heads[h], ((), frozenset()))
        per_data[heads[h]] = (tuple(sorted(set(old[0]) | set(ages))), old[1] | cls)
    sources = {d: clip_data(args.oot, d, counts[d]) for d in per_data}
    jobs = [(d, sources[d], ages, ALWAYS_TIGHT | cls, args.tol, args.visual_tol)
            for d, (ages, cls) in sorted(per_data.items())]
    with multiprocessing.Pool(initializer=_init_worker, initargs=(args.oot,)) as pool:
        chosen = dict(pool.map(_encode, jobs, chunksize=4))

    enc, blocks, mismatches, refs_by_data = {}, {}, [], {}
    for data in sorted(per_data):
        src, choice = sources[data], chosen[data]
        choice['ages'], choice['tight'] = per_data[data][0], sorted(ALWAYS_TIGHT | per_data[data][1])
        block = fp.pack_clip(src, choice.pop('shifts'), choice['stride'])
        ref = fp.reference(src, list(block[fp.SHIFTS:fp.SHIFTS + 63]), choice['stride'])
        # Byte round trip: every frame decoded from the emitted bytes.
        if [fp.unpack_frame(block, i) for i in range(len(src))] != ref:
            mismatches.append(data)
        if any(r[0:3] != s[0:3] or r[66] != s[66] for r, s in zip(ref, src)):
            mismatches.append(data + ' (root/face)')
        blocks[data] = block
        refs_by_data[data] = ref
        enc[data] = dict(frames=len(src), raw=len(src) * 134, **choice)

    # One global id per data array; every bank file carries the ids it holds,
    # so resident and scene packs share one id space. Importer writes the id
    # into LinkAnimationHeader.segment (ids.json).
    gid = {d: i for i, d in enumerate(sorted(per_data))}

    def pack_file(datas):
        """'PFB2', u32 count, u32 offset[count], u16 id[count] (pad 4), blocks,
        4 B tail pad (32-bit field window). Offsets from file start."""
        head_len = 8 + 4 * len(datas) + ((2 * len(datas) + 3) & ~3)
        body, offsets = b'', []
        for d in datas:
            offsets.append(head_len + len(body))
            body += blocks[d]
        ids = struct.pack('>%dH' % len(datas), *[gid[d] for d in datas])
        ids += bytes(-len(ids) % 4)
        return (b'PFB2' + struct.pack('>I', len(datas)) +
                struct.pack('>%dI' % len(datas), *offsets) + ids + body + bytes(4))

    def emit(name, hs):
        datas = sorted({heads[h] for h in hs}, key=lambda d: gid[d])
        out = pack_file(datas)
        (args.bank / name).write_bytes(out)
        return len(out), datas

    args.bank.mkdir(parents=True, exist_ok=True)
    def expect(path, datas):
        path.write_bytes(b''.join(struct.pack('>67h', *f) for d in datas for f in refs_by_data[d]))

    resident_len, resident_datas = emit('RESIDENT.PFB', resident_h)
    expect(args.bank / 'RESIDENT.EXPECT', resident_datas)
    pack_len = {}
    for scene, hs in sorted(packs_h.items()):
        length, datas = emit(f'S_{scene}.PFB', hs)
        pack_len[scene] = length
        expect(args.bank / f'S_{scene}.EXPECT', datas)
    all_datas = sorted(per_data, key=lambda d: gid[d])
    all_bytes = pack_file(all_datas)
    (args.bank / 'ALL.PFB').write_bytes(all_bytes)
    expect(args.bank / 'ALL.EXPECT', all_datas)
    all_len = len(all_bytes)
    (args.bank / 'ids.json').write_text(json.dumps(
        {h: gid[heads[h]] for h in reach}, indent=0, sort_keys=True) + chr(10), encoding='utf-8')
    (args.bank / 'scene_packs.json').write_text(json.dumps(
        {s: sorted(gid[heads[h]] for h in hs) for s, hs in packs_h.items()},
        indent=0, sort_keys=True) + chr(10), encoding='utf-8')
    # Adapter slot table: one block pointer per global id.
    lookup = 4 * len(gid)
    scratch = 2 * 2 * 67 * 2 + 2 * 67 * 2     # 2 users x (2 poses) + output, s16
    ranked = sorted(pack_len.values(), reverse=True) + [0, 0]
    worst_scene = resident_len + ranked[0] + lookup + scratch
    transition = resident_len + ranked[0] + ranked[1] + lookup + scratch
    range_total = sum(e['bytes'] for e in enc.values())
    report = dict(
        status='delta blocks emitted; per-channel shifts; scene residency from spawn lists. '
               'Loader and Player cutover not started. Fit is the gate.',
        tolerance_world_units=args.tol, visual_tolerance_world_units=args.visual_tol,
        anchors='limb origins + z_player_lib weapon tips (3000/4000/5500) and bases, '
                'held actor, shield quads (hand/back), focus, feet',
        clips=len(reach), data_arrays=len(enc), round_trip_mismatches=mismatches,
        raw_reachable_bytes=sum(e['raw'] for e in enc.values()),
        packed_delta_block_bytes=range_total, all_file_bytes=all_len,
        resident_clips=len(resident_h), resident_file_bytes=resident_len,
        scene_pack_files={s: pack_len[s] for s in sorted(pack_len)},
        unreachable_clips=sorted(unreachable_h),
        lookup_table_bytes=lookup, decoder_scratch_bytes=scratch,
        worst_scene_bytes=worst_scene, transition_peak_bytes=transition,
        existing_allocation_bytes=args.current,
        fits_existing_allocation=transition <= args.current,
        encodings={f'stride{st}': sum(1 for e in enc.values() if e['stride'] == st)
                   for st in STRIDES},
        channel_shifts={
            '8': sum(e['shift_hist'][0] for e in enc.values()),
            '10': sum(e['shift_hist'][1] for e in enc.values()),
            '12': sum(e['shift_hist'][2] for e in enc.values()),
            '14': sum(e['shift_hist'][3] for e in enc.values()),
            '16': sum(e['shift_hist'][4] for e in enc.values())},
        context=dict(weapon_tight=sum(1 for _, c in per_data.values() if 'weapon' in c),
                     held_tight=sum(1 for _, c in per_data.values() if 'held' in c),
                     adult_only=sum(1 for a, _ in per_data.values() if a == ('adult',)),
                     child_only=sum(1 for a, _ in per_data.values() if a == ('child',))),
        # Same lifecycle stage (normal play in the worst scene): the old system
        # holds LINKANIM plus C collision (94,854 scene + 16,384 index + 18,432
        # dyna carve); the new one holds this bank and uses core collision.
        steady_old_bytes=args.current + 129670, steady_new_bytes=worst_scene,
        per_clip={h: enc[heads[h]] for h in reach})
    args.out.write_text(json.dumps(report, indent=1) + chr(10), encoding='utf-8')
    for key in ('clips', 'round_trip_mismatches', 'raw_reachable_bytes',
                'packed_delta_block_bytes', 'resident_clips', 'resident_file_bytes',
                'all_file_bytes', 'lookup_table_bytes', 'decoder_scratch_bytes',
                'worst_scene_bytes', 'transition_peak_bytes', 'existing_allocation_bytes',
                'fits_existing_allocation', 'steady_old_bytes', 'steady_new_bytes', 'context'):
        print(f'{key}: {report[key]}')
    print('packs:', report['scene_pack_files'])
    print('encodings:', report['encodings'])
    print('channel_shifts:', report['channel_shifts'])


if __name__ == '__main__':
    main()
