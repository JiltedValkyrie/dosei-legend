#!/usr/bin/env python
"""Extract Kokiri Forest actor placements from the original US 1.2 scene.

Only placement data is taken: actor id, position, facing and the spawn
parameter word. Behaviour is not derived from here -- these tables say WHERE
the game puts each actor and WHICH one it is, so nothing downstream has to
invent a position.

Room header command 0x01 is the actor list: a count plus a segment pointer to
16-byte entries, `>H hhh hhh H` = id, x, y, z, rotX, rotY, rotZ, params. The
low 12 bits of the id select the actor; the top bits are spawn flags.

Ground height is CHECKED, not silently corrected. OoT actors settle onto the
floor at runtime, so an authored Y can sit a little above or below our
collision mesh. The report prints every actor whose floor differs from its
authored Y so a bad placement is visible instead of quietly moved.
"""

import argparse
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'shared/tools'))
import build_kokiri_scene as source

ACTOR_EN_KO = 0x0163       # Kokiri child
ACTOR_EN_MD = 0x016D       # Mido
ACTOR_EN_SA = 0x0146       # Saria
ACTOR_EN_KUSA = 0x0125     # cuttable grass tuft
ACTOR_EN_KANBAN = 0x0141   # signpost

# Kind ids shared with the runtime. Order is the emit order, not an actor id.
KINDS = (('CHILD', ACTOR_EN_KO), ('MIDO', ACTOR_EN_MD), ('SARIA', ACTOR_EN_SA))

# Gear pickups. Kokiri Forest has neither sword nor shield lying on the ground
# in the original -- the sword is in the training ground chest and the shield is
# bought -- so WHICH item sits here is the slice's choice. Where it sits is not:
# both reuse spots the original already drops a ground collectible on
# (En_Item00, actor 0x0015, in spot04_room_0), so they are reachable, on real
# floor, and either side of the spawn. The height is re-snapped to our own
# collision mesh and the build fails if there is no floor under one.
PICKUPS = (
    ('SWORD',  -537, 1, 194),      # En_Item00 west of spawn
    ('SHIELD',   35, 1, -418),     # En_Item00 north of spawn
)


def read_actors(data):
    """Every actor entry in one room, in the room's own order."""
    out = []
    for pos in range(0, 0x400, 8):
        command = data[pos]
        if command == 0x14:        # end of header
            break
        if command != 0x01:
            continue
        count = data[pos + 1]
        base = struct.unpack_from('>I', data, pos + 4)[0] & 0xFFFFFF
        for i in range(count):
            aid, x, y, z, _rx, ry, _rz, var = struct.unpack_from(
                '>Hhhhhhh H', data, base + i * 16)
            out.append(dict(id=aid & 0xFFF, x=x, y=y, z=z,
                            yaw=ry & 0xFFFF, var=var))
    return out


def floor_under(triangles, x, z, y):
    """Highest walkable collision floor at or below y+tolerance, or None.

    Mirrors the runtime's rule rather than a generic raycast: a triangle counts
    as floor when its normal points up, which is what kokiri_collision_floor()
    walks. Kept in source space; the Saturn Y negation happens later.
    """
    best = None
    for tri in triangles:
        # collision_triangles() returns one flat tuple per triangle:
        # 9 vertex components, 3 normal components, then the 6 bounds.
        ax, ay, az, bx, _by, bz, cx, _cy, cz = tri[:9]
        nx, ny, nz = tri[9:12]
        if ny <= 0:
            continue
        # Point-in-triangle on the XZ plane, integer cross products.
        d1 = (x - bx) * (az - bz) - (ax - bx) * (z - bz)
        d2 = (x - cx) * (bz - cz) - (bx - cx) * (z - cz)
        d3 = (x - ax) * (cz - az) - (cx - ax) * (z - az)
        if (d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0):
            continue
        if ny == 0:
            continue
        # Plane height at (x,z) from the stored unit normal and a vertex.
        height = ay + ((ax - x) * nx + (az - z) * nz) / float(ny)
        if height <= y + 30 and (best is None or height > best):
            best = height
    return best


def grass_rupee_slots(oot, param):
    """Rupee-only subset of EnKusa_DropCollectible / Item_DropCollectibleRandom.

    Non-rupee and FLEXIBLE slots stay empty until health/ammo exist. Type 1
    grass only drops seeds/hearts. Selection is slice PRNG, not OoT RNG parity.
    """
    if param & 3 == 1:
        return [0] * 16
    if param & 3 not in (0, 2):
        raise ValueError('Unsupported grass type')
    table = (param >> 8) & 15
    if table >= 13:
        table = 0
    text = (oot / 'src/code/z_en_item00.c').read_text()
    block = text.split('static u8 sItemDropIds[] = {', 1)[1].split('};', 1)[0]
    ids = re.findall(r'\bITEM00_[A-Z_]+\b', block)
    row = ids[table*16:(table+1)*16]
    if len(row) != 16:
        raise ValueError('Incomplete OoT collectible table')
    values = {'ITEM00_RUPEE_GREEN': 1, 'ITEM00_RUPEE_BLUE': 5}
    if any('RUPEE' in item and item not in values for item in row):
        raise ValueError('New rupee colour needs sprite support')
    return [values.get(item, 0) for item in row]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'build/generated')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', type=pathlib.Path)
    args = ap.parse_args()

    segments = source.extract(args.oot, args.rom_dir)
    triangles = source.collision_triangles(segments['spot04_scene'])

    people, grass, signs, rupees = [], [], [], []
    for name in sorted(segments):
        if 'room' not in name:
            continue
        room = int(name.rsplit('_', 1)[1])
        for actor in read_actors(segments[name]):
            actor['room'] = room
            if actor['id'] == 0x0015 and actor['var'] & 255 in (0, 1):
                height = floor_under(triangles, actor['x'], actor['z'], actor['y'])
                if height is None:
                    raise ValueError('Rupee has no collision floor')
                rupees.append(dict(actor, y=round(height), value=(1, 5)[actor['var'] & 255]))
            if actor['id'] == ACTOR_EN_KO:
                people.append(dict(actor, kind='CHILD'))
            elif actor['id'] == ACTOR_EN_MD:
                people.append(dict(actor, kind='MIDO'))
            elif actor['id'] == ACTOR_EN_SA:
                people.append(dict(actor, kind='SARIA'))
            elif actor['id'] == ACTOR_EN_KUSA:
                grass.append(actor)
            elif actor['id'] == ACTOR_EN_KANBAN:
                signs.append(actor)

    # Mido and Saria before the children so a fixed-size near list that runs
    # out still keeps the two named characters the slice needs for dialogue.
    people.sort(key=lambda a: ({'MIDO': 0, 'SARIA': 1, 'CHILD': 2}[a['kind']],
                               a['x'], a['z']))

    pickups = []
    for item, x, y, z in PICKUPS:
        height = floor_under(triangles, x, z, y)
        if height is None:
            sys.exit('pickup %s at (%d,%d) has no collision floor below it'
                     % (item, x, z))
        pickups.append(dict(item=item, x=x, y=int(round(height)), z=z))

    off_floor = []
    for actor in people + grass:
        height = floor_under(triangles, actor['x'], actor['z'], actor['y'])
        actor['floor'] = height
        if height is None or abs(height - actor['y']) > 8:
            off_floor.append(actor)

    args.out.mkdir(parents=True, exist_ok=True)
    banner = '/* Generated by game/tools/build_actors.py -- do not edit. */'
    header = [banner, '', '#ifndef KOKIRI_ACTORS_H', '# define KOKIRI_ACTORS_H',
              '# include <stdint.h>', '',
              '/* Placement only, straight from the US 1.2 room actor lists. */',
              '# define KOKIRI_NPC_COUNT   %d' % len(people),
              '# define KOKIRI_GRASS_COUNT %d' % len(grass),
              '# define KOKIRI_SIGN_COUNT  %d' % len(signs),
              '# define KOKIRI_PICKUP_COUNT %d' % len(pickups),
              '# define KOKIRI_RUPEE_COUNT %d' % len(rupees), '']
    for i, (name, aid) in enumerate(KINDS):
        header.append('# define KOKIRI_NPC_%-6s %d  /* actor 0x%04X */'
                      % (name, i, aid))
    header += ['',
               'typedef struct {',
               '    int16_t  x, y, z;',
               '    uint16_t yaw;      /* binang, straight from rotY */',
               '    uint16_t param;    /* the room list spawn word */',
               '    uint8_t  kind;     /* KOKIRI_NPC_* */',
               '    uint8_t  room;',
               '} kokiri_npc_t;', '',
               'typedef struct { int16_t x, y, z; uint8_t room; } kokiri_prop_t;',
               '',
               'extern const kokiri_npc_t  kokiri_npcs[KOKIRI_NPC_COUNT];',
               'extern const kokiri_prop_t kokiri_grass[KOKIRI_GRASS_COUNT];',
               'extern const kokiri_prop_t kokiri_signs[KOKIRI_SIGN_COUNT];',
               '',
               '/* item is a GP_* bit from src/gameplay.h; y is the verified floor. */',
               'typedef struct { int16_t x, y, z; uint8_t item; } kokiri_pickup_t;',
               'extern const kokiri_pickup_t kokiri_pickups[KOKIRI_PICKUP_COUNT];',
               'typedef struct { int16_t x, y, z; uint16_t param; uint8_t room, value; } kokiri_rupee_t;',
               'extern const kokiri_rupee_t kokiri_rupees[KOKIRI_RUPEE_COUNT];',
               'extern const uint8_t kokiri_grass_rupees[KOKIRI_GRASS_COUNT][16];',
               '#endif', '']
    (args.out / 'kokiri_actors.h').write_text('\n'.join(header))

    body = [banner, '', '#include "kokiri_actors.h"', '#include "gameplay.h"', '',
            'const kokiri_npc_t kokiri_npcs[KOKIRI_NPC_COUNT] = {']
    for a in people:
        body.append('    { %d, %d, %d, %u, 0x%04X, KOKIRI_NPC_%s, %d },'
                    % (a['x'], a['y'], a['z'], a['yaw'], a['var'],
                       a['kind'], a['room']))
    body += ['};', '', 'const kokiri_prop_t kokiri_grass[KOKIRI_GRASS_COUNT] = {']
    for a in grass:
        body.append('    { %d, %d, %d, %d },' % (a['x'], a['y'], a['z'], a['room']))
    body += ['};', '', 'const kokiri_prop_t kokiri_signs[KOKIRI_SIGN_COUNT] = {']
    for a in signs:
        body.append('    { %d, %d, %d, %d },' % (a['x'], a['y'], a['z'], a['room']))
    body += ['};', '',
             'const kokiri_pickup_t kokiri_pickups[KOKIRI_PICKUP_COUNT] = {']
    for a in pickups:
        body.append('    { %d, %d, %d, GP_%s },' % (a['x'], a['y'], a['z'], a['item']))
    body += ['};', '']
    body += ['const kokiri_rupee_t kokiri_rupees[KOKIRI_RUPEE_COUNT] = {']
    for a in rupees:
        body.append('    { %d, %d, %d, 0x%04X, %d, %d },' %
                    (a['x'], a['y'], a['z'], a['var'], a['room'], a['value']))
    body += ['};', 'const uint8_t kokiri_grass_rupees[KOKIRI_GRASS_COUNT][16] = {']
    for a in grass:
        body.append('    { %s }, /* EnKusa params 0x%04X */' %
                    (', '.join(map(str, grass_rupee_slots(args.oot, a['var']))), a['var']))
    body += ['};', '']
    print('rupees  : %d original room placements; source grass drop slots' % len(rupees))
    (args.out / 'kokiri_actors.c').write_text('\n'.join(body))

    print('pickups : %s'
          % ', '.join('%s at (%d,%d,%d)' % (a['item'], a['x'], a['y'], a['z'])
                      for a in pickups))
    print('actors  : %d people (%d Kokiri, Mido %d, Saria %d), %d grass, %d signs'
          % (len(people),
             sum(1 for a in people if a['kind'] == 'CHILD'),
             sum(1 for a in people if a['kind'] == 'MIDO'),
             sum(1 for a in people if a['kind'] == 'SARIA'),
             len(grass), len(signs)))
    if off_floor:
        print('  %d placements are not within 8 units of a collision floor:'
              % len(off_floor))
        for a in off_floor[:12]:
            print('    id 0x%04X at (%d,%d,%d) room %d floor %s'
                  % (a['id'], a['x'], a['y'], a['z'], a['room'],
                     'none' if a['floor'] is None else '%.1f' % a['floor']))
    else:
        print('  every placement sits on a collision floor within 8 units')


if __name__ == '__main__':
    main()
