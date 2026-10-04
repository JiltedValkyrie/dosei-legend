#!/usr/bin/env python3
"""Skinned Saturn models for decomp NPC objects (any actor, no per-actor bake).

For every built data object (oot_core_import.OBJECTS) whose XML names a
Skeleton and that a GENERIC_NPC actor uses, convert every limb display list
with per-vertex limb ownership (build_link_model.LimbLists), flat body colours
and face detail (character_textures rule), and write:

    N<object hex3><n>.BIN   KFR1 model (build_link_model.write_model, skinned)
    N<object hex3><n>.SKN   per vertex: matrix slot + limb-local position
                            (same format as build_npc_models' NPCnn.SKN)

plus build/oot-core/generic_skins.h for the blob: for each limb display list
placeholder (object, index in O<id>_ph.txt) the model and the matrix slot it
fills. At run time the real draw calls those DLs with the limb matrix loaded;
the blob records the matrix per slot, the C side skins the model with them.
Animation, head turns and every pose therefore come from the decomp.

Offline tool: floating point is fine here.
"""
import argparse
import importlib.util
import pathlib
import struct
import sys
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
GAME = HERE.parent

import build_actor_model as actor  # noqa: E402
import build_link_model as link    # noqa: E402

ENDDL = struct.pack('>II', 0xDF000000, 0)


def load_importer():
    spec = importlib.util.spec_from_file_location('oot_core_import', HERE / 'oot_core_import.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def skin_object(oot, rom_dir, obj, oid, n, skel_off, xml_path, ph_names, out, keep):
    data = link.read_object(oot, obj, rom_dir)
    root = ET.parse(xml_path)
    names = {int(e.attrib['Offset'], 16): e.attrib['Name'] for e in root.iter()
             if 'Name' in e.attrib and 'Offset' in e.attrib and not e.attrib['Offset'].startswith('.')}
    table, count = actor.read_skeleton(data, skel_off)
    limbs, addresses = actor.read_limbs(data, table, count)
    head = next((i for i, a in enumerate(addresses) if 'Head' in names.get(a & 0xFFFFFF, '')), None)
    link.HEAD_LIMB, link.LIMB_NONE = (head if head is not None else -1), 0xFF
    placed = link.walk_skeleton(limbs, [(0, 0, 0)] * count, (0, 0, 0))
    poses = {i: (m, o) for i, m, o, _ in placed}
    lists = link.LimbLists(b'', b'')
    # 6 = the object; 4 gameplay_keep; 8/9 eye/mouth frames from the object
    # start (resolved per face by mark_faces); the rest of the runtime
    # segments (env lists) end at once.
    tex = [(e.attrib['Name'], int(e.attrib['Offset'], 16)) for e in root.iter('Texture')
           if not e.attrib.get('Offset', '.').startswith('.')]
    def first(*keys):
        for key in keys:
            for nm, off in tex:
                if key in nm:
                    return off
        return 0
    eyes, mouth = first('EyeOpen', 'Eye'), first('MouthClosed', 'Mouth')
    lists.segments = {6: data, 4: keep, 8: data[eyes:], 9: data[mouth:],
                      10: ENDDL, 11: ENDDL, 12: ENDDL, 13: ENDDL}
    lists.matrix_limbs = [i for i, _, _, d in placed if d]
    faces = []
    for i, _, _, display in placed:
        if not display:
            continue
        lists.prim = (255, 255, 255, 255)
        lists.current_limb = i
        first = len(lists.faces)
        lists.walk(display)
        group = []
        for original in lists.faces[first:]:
            face = dict(original)
            face['local'] = [tuple(v[:3]) for v in face['vertices']]
            face['vertices'] = [link.transform(*poses[owner], v[:3]) + tuple(v[3:])
                                for v, owner in zip(face['vertices'], face['vertex_limbs'])]
            face['limb'] = i
            group.append(face)
        link.character_textures.mark_faces(group, xml_path, head, (8, 9))
        faces.extend(group)
    if not faces:
        raise ValueError('no faces')
    link.apply_primitive_colour(faces)
    faces = link.scale_faces(faces, 0.01)
    stem = 'N%03X%X' % (oid, n)
    _, _, owners, locals_ = link.write_model(faces, out / (stem + '.BIN'), skinned=True)
    slots = [lists.matrix_limbs.index(o) for o in owners]
    skin = struct.pack('>4sII', b'SKN1', len(owners), len(lists.matrix_limbs))
    skin += bytes(slots) + bytes((-len(slots)) % 2)
    skin += b''.join(struct.pack('>3h', *(round(c) for c in loc)) for loc in locals_)
    (out / (stem + '.SKN')).write_bytes(skin)
    rows = []
    for slot, limb in enumerate(lists.matrix_limbs):
        dl = limbs[limb]['far'] & 0xFFFFFF
        name = names.get(dl)
        if name in ph_names:
            rows.append((oid, ph_names.index(name), (oid << 4) | n, slot))
    return stem, len(owners), len(faces), rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, required=True)
    ap.add_argument('--rom-dir', required=True)
    ap.add_argument('--out', type=pathlib.Path, default=GAME / 'build' / 'cd')
    ap.add_argument('--core', type=pathlib.Path, default=GAME / 'build' / 'oot-core')
    args = ap.parse_args()
    imp = load_importer()
    _enum_ids, sym_ids = imp.object_ids(args.oot)
    keep = link.read_object(args.oot, 'gameplay_keep', args.rom_dir)
    # Objects the generic NPCs use: every built object their source names.
    wanted = set()
    for _a, src in imp.GENERIC_NPC_SOURCES:
        text = (args.oot / src).read_text(encoding='utf-8', errors='replace')
        for name in imp.OBJECTS:
            if name.upper() in text.upper():
                wanted.add(name)
    rows, problems, built = [], [], 0
    for name in sorted(wanted):
        oid = sym_ids[name]
        xml_path = args.oot / 'assets' / 'xml' / 'objects' / (name + '.xml')
        ph = (args.core / 'objects' / ('O%03X_ph.txt' % oid))
        if not xml_path.exists() or not ph.exists():
            continue
        ph_names = ph.read_text().split()[1:]
        skels = [s for s in ET.parse(xml_path).iter('Skeleton')
                 if not s.attrib.get('Offset', '.').startswith('.')]
        for n, skel in enumerate(skels[:16]):
            try:
                stem, verts, nfaces, r = skin_object(args.oot, args.rom_dir, name, oid, n,
                                                     int(skel.attrib['Offset'], 16), xml_path,
                                                     ph_names, args.out, keep)
            except Exception as exc:
                problems.append(f'{name} {skel.attrib.get("Name")}: {exc!r}')
                continue
            built += 1
            rows += r
            print(f'skin    : {stem} {name} {skel.attrib.get("Name")} {verts} verts {nfaces} faces')
    lines = ['/* Generated by tools/build_core_skins.py. Do not edit.',
             ' * { object id, placeholder index, model (object << 4 | n), matrix slot } */']
    lines += [f'    {{ 0x{o:03X}, {i}, 0x{m:04X}, {s} }},' for o, i, m, s in rows] or ['    { 0xFFFF, 0, 0, 0 },']
    (args.core / 'generic_skins.h').write_text('\n'.join(lines) + '\n')
    print(f'core skins: {built} built, {len(problems)} left out')
    for p in problems:
        print('  left out:', p)
    return 0


if __name__ == '__main__':
    sys.exit(main())
