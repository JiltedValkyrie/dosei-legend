"""Source room/actor graph for M5/M6; never implies runtime actor support.

Reads the child-day headers independently of runtime scene registration. Keeps
transition actor params and camera sides intact: a shutter is not an En_Holl.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

import build_actor_manifest as actors
import build_scene_table as scenes

SPECS = {
    'ydan': ('SCENE_DEKU_TREE', 12),
    'ydan_boss': ('SCENE_DEKU_TREE_BOSS', 2),
    'spot10': ('SCENE_LOST_WOODS', 10),
}


def commands(data, segment, base=0):
    """Bounded scene commands, rejecting wrong-segment/truncated records."""
    for at in range(base, min(base + 0x400, len(data)), 8):
        if at + 8 > len(data):
            raise ValueError('truncated header')
        cmd, count = data[at:at + 2]
        pointer = struct.unpack_from('>I', data, at + 4)[0]
        yield cmd, count, pointer
        if cmd == 0x14:
            return
    raise ValueError('unterminated header')


def records(data, pointer, count, fmt, segment):
    size = struct.calcsize(fmt)
    start = pointer & 0xFFFFFF
    if pointer >> 24 != segment or start + count * size > len(data):
        raise ValueError('invalid segment pointer or record count')
    return [struct.unpack_from(fmt, data, start + i * size) for i in range(count)]


def room_records(data, names, object_names):
    result = dict(actors=[], objects=[])
    for cmd, count, pointer in commands(data, 3):
        if cmd == 1:
            for aid, x, y, z, rx, ry, rz, params in records(data, pointer, count, '>HhhhhhhH', 3):
                result['actors'].append(dict(id=aid & 0xFFF, raw_id=aid,
                    name=names.get(aid & 0xFFF, 'UNKNOWN'), position=[x, y, z],
                    rotation=[rx, ry, rz], params=params))
        elif cmd == 0x0B:
            result['objects'] = [dict(id=v[0], name=object_names.get(v[0], 'UNKNOWN'))
                                 for v in records(data, pointer, count, '>H', 3)]
    return result


def scene_manifest(prefix, segments, names, object_names, entrances):
    scene_name, expected_rooms = SPECS[prefix]
    scene = segments[prefix + '_scene']
    room_names = sorted((n for n in segments if n.startswith(prefix + '_room_')),
                        key=lambda n: int(n.rsplit('_', 1)[1]))
    if [int(n.rsplit('_', 1)[1]) for n in room_names] != list(range(expected_rooms)):
        raise ValueError('%s: missing or unexpected source rooms' % prefix)
    result = dict(prefix=prefix, scene=scene_name, layer='child day',
                  source_hashes={n: hashlib.sha256(v).hexdigest() for n, v in sorted(segments.items())},
                  rooms=[], transitions=[], spawns=[], exits=[])
    header = list(commands(scene, 2))
    spawn_records = next((records(scene, p, n, '>HhhhhhhH', 2)
                          for c, n, p in header if c == 0), [])
    spawn_list = next((p for c, n, p in header if c == 6), None)
    if spawn_list is None:
        raise ValueError('missing entrance list')
    for actor_index, room in records(scene, spawn_list, len(spawn_records), '>BB', 2):
        if actor_index >= len(spawn_records) or room >= expected_rooms:
            raise ValueError('invalid spawn mapping')
        v = spawn_records[actor_index]
        result['spawns'].append(dict(room=room, actor_index=actor_index,
            position=list(v[1:4]), yaw=v[5] & 0xFFFF, params=v[7]))
    for c, n, p in header:
        if c != 14:
            continue
        for index, v in enumerate(records(scene, p, n, '>bbbbHhhhhH', 2)):
            front, fc, back, bc, aid, x, y, z, yaw, params = v
            if not all(-1 <= room < expected_rooms for room in (front, back)):
                raise ValueError('transition references missing room')
            result['transitions'].append(dict(index=index, front=front, back=back,
                cameras=[fc, bc], actor=names.get(aid & 0xFFF, 'UNKNOWN'),
                id=aid & 0xFFF, position=[x, y, z], yaw=yaw, params=params,
                kind=(params >> 6) & 7 if aid & 0xFFF == 35 else None))
    collision = scenes.source.collision_data(scene)
    surfaces = scenes.source.collision_surfaces(scene)
    exit_count = max((p['exit'] for p in surfaces), default=0)
    for slot, entrance in enumerate(scenes.source.exit_list(scene, exit_count), 1):
        if entrance not in entrances:
            raise ValueError('unknown exit entrance 0x%04X' % entrance)
        target, spawn = entrances[entrance]
        result['exits'].append(dict(slot=slot, entrance=entrance, scene=target,
            spawn=spawn, polygons=[i for i, p in enumerate(surfaces) if p['exit'] == slot]))
    result['collision'] = dict(triangles=len(collision['polys']),
        surfaces=len(collision['surfaces']), water=collision['water'], bgcams=collision['bgcams'])
    for name in room_names:
        result['rooms'].append(dict(id=int(name.rsplit('_', 1)[1]),
            source_bytes=len(segments[name]), **room_records(segments[name], names, object_names)))
    return result


def markdown(data):
    lines = ['# M5/M6 source room ledger', '',
        'Generated from US 1.2 child-day headers. Source presence is not runtime support.',
        'Full coordinates, rotations, object dependencies, collision cameras/water and',
        'source fingerprints: `game/build/generated/progression_manifest.json`.', '',
        'Door_Shutter gates require their actor state; never treat them as open tunnels.',
        'M6 Sacred Forest Meadow and M7 Field destinations remain integration boundaries.', '']
    for scene in data['scenes']:
        lines += ['## ' + scene['prefix'], '',
            '%d rooms; %d collision triangles.' % (len(scene['rooms']), scene['collision']['triangles']), '',
            '| Spawn | Room | Position | Yaw |', '|---|---|---|---|']
        for i, s in enumerate(scene['spawns']):
            lines.append('| %d | %d | %s | %04X |' % (i, s['room'], s['position'], s['yaw']))
        lines += ['', '| Transition | Rooms | Actor | Params | Kind |', '|---|---|---|---|---|']
        for t in scene['transitions']:
            lines.append('| %d | %d / %d | %s | %04X | %s |' %
                (t['index'], t['front'], t['back'], t['actor'], t['params'], t['kind']))
        lines += ['', '| Exit slot | Entrance | Destination | Spawn |', '|---|---|---|---|']
        for e in scene['exits']:
            lines.append('| %d | %04X | %s | %d |' % (e['slot'], e['entrance'], e['scene'], e['spawn']))
        for r in scene['rooms']:
            lines += ['', '### Room %d' % r['id'], '',
                'Objects: ' + ', '.join(o['name'] for o in r['objects']), '',
                '| Actor | Params | Position |', '|---|---|---|']
            for a in r['actors']:
                lines.append('| %s | %04X | %s |' % (a['name'], a['params'], a['position']))
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1] / 'build/generated/progression_manifest.json')
    ap.add_argument('--notes', type=Path)
    args = ap.parse_args()
    names = actors.table(args.oot / 'include/tables/actor_table.h', 'DEFINE_ACTOR')
    objects = actors.table(args.oot / 'include/tables/object_table.h', 'DEFINE_OBJECT')
    entrances = scenes.entrance_table(args.oot)
    data = dict(version=1, scenes=[scene_manifest(p, scenes.source.extract(args.oot, args.rom_dir, prefix=p),
                 names, objects, entrances) for p in SPECS])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    if args.notes:
        args.notes.write_text(markdown(data), encoding='utf-8')
    print('M5/M6: %d scenes, %d rooms, %d transitions' % (len(data['scenes']),
        sum(len(s['rooms']) for s in data['scenes']), sum(len(s['transitions']) for s in data['scenes'])))


if __name__ == '__main__':
    main()
