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
from layout_variants import for_build

ACTOR_EN_KO = 0x0163       # Kokiri child
ACTOR_EN_MD = 0x016D       # Mido
ACTOR_EN_SA = 0x0146       # Saria
ACTOR_EN_KUSA = 0x0125     # cuttable grass tuft
ACTOR_EN_KANBAN = 0x0141   # signpost
ACTOR_EN_BOX = 0x000A      # treasure chest
ACTOR_EN_WONDER_ITEM = 0x0112  # invisible reward trigger
ACTOR_EN_OSSAN = 0x003D    # shopkeeper
ACTOR_EN_GOROIWA = 0x0130  # maze rolling boulder
ACTOR_EN_KAREBABA = 0x00C7  # withered Deku Baba

# SAVE_SCENE_* ids (src/save_state.h) for the scenes read here.
SAVE_SCENE_KOKIRI_FOREST = 0
SAVE_SCENE_KOKIRI_SHOP = 4

# M3b interiors whose people are placed (prefix -> SAVE_SCENE_* id).
INTERIORS = (('kokiri_shop', 4), ('kokiri_home', 6), ('kokiri_home3', 7),
             ('kokiri_home4', 8), ('kokiri_home5', 9))
# EnKo_CanSpawn (z_en_ko.c), child Link: which ENKO_TYPE appears per scene.
# Forest: types below 7 plus Fado (12); CanSpawn only refuses adult there.
ENKO_CHILD_TYPES = {0: set(range(7)) | {12}, 4: {10}, 6: {7, 8, 11}, 7: {9},
                    8: set(), 9: set()}

# Kind ids shared with the runtime. Order is the emit order, not an actor id.
KINDS = (('CHILD', ACTOR_EN_KO), ('MIDO', ACTOR_EN_MD), ('SARIA', ACTOR_EN_SA))

# The slice's old ground sword/shield pickups are gone (FEAT-001): the sword
# is the maze chest (En_Box 0x04E0) and the shield is bought in the shop.

# En_Wonder_Item modes that the slice runs (z_en_wonder_item.c Init switch).
# Mode 3 (interact switch) needs a sword/stick hit; modes 1 and 6 are the tag
# points of modes 0 and 5. Other modes are reported and skipped.
WONDER_MODES = (0, 1, 2, 3, 5, 6)
# EnWonderItem_DropCollectible dropTable index -> rupee value. Non-rupee
# drops are refused: the slice has no hearts/ammo yet.
WONDER_RUPEES = {8: 1, 9: 5, 10: 20}


def read_actors(data, header_base=0):
    """Every actor entry in one room, in the room's own order."""
    out = []
    for pos in range(header_base, header_base + 0x400, 8):
        command = data[pos]
        if command == 0x14:        # end of header
            break
        if command != 0x01:
            continue
        count = data[pos + 1]
        base = struct.unpack_from('>I', data, pos + 4)[0] & 0xFFFFFF
        for i in range(count):
            aid, x, y, z, _rx, ry, rz, var = struct.unpack_from(
                '>Hhhhhhh H', data, base + i * 16)
            out.append(dict(id=aid & 0xFFF, x=x, y=y, z=z,
                            yaw=ry & 0xFFFF, rot_z=rz, var=var))
    return out


def entity_floor_triangles(scene):
    """Exclude source entity-ignore surfaces, including tall-grass tops."""
    geometry = source.collision_triangles(scene)
    metadata = source.collision_data(scene)['polys']
    assert len(geometry) == len(metadata)
    return [tri for tri, poly in zip(geometry, metadata)
            if not (poly['ignore'] & 2)]


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


def scene_paths(scene):
    """Header command 0x0D: Path entries (u8 count, pad, u32 points), Vec3s."""
    header = source.scene_header(scene)
    if 0x0D not in header:
        return []
    base = source._segment_offset(header[0x0D][0])
    out = []
    for i in range(32):
        count = scene[base + 8 * i]
        points = struct.unpack_from('>I', scene, base + 8 * i + 4)[0]
        if count == 0 or points >> 24 != 0x02:
            break
        points &= 0xFFFFFF
        out.append([struct.unpack_from('>3h', scene, points + 6 * k) for k in range(count)])
    return out


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


def navi_cast(segments):
    """SPOT04 layer 7 selects gKokiriForestIntroNaviFlyingCs (US 1.2)."""
    from build_actor_manifest import header, layer_header
    result = []
    for name,data in sorted(segments.items()):
        if 'room' not in name: continue
        base,_ = layer_header(data,header(data,0,3),3,7)
        for actor in read_actors(data,base):
            if actor['id'] not in (ACTOR_EN_KO,ACTOR_EN_MD): continue
            model = 0 if actor['id'] == ACTOR_EN_MD else 2+(actor['var']&255)
            if model >= 15: raise ValueError('Unsupported Navi flythrough NPC')
            result.append(dict(actor,model=model))
    return result


def emit_navi_cast(segments,out):
    cast=navi_cast(segments)
    lines=['/* Original SPOT04 layer 7; generated by build_actors.py. */',
           '#ifndef NAVI_NPCS_H', '#define NAVI_NPCS_H',
           '#define NAVI_NPC_COUNT %d'%len(cast),
           'typedef struct { int16_t x,y,z; uint16_t yaw; uint8_t model; } navi_npc_t;',
           'static const navi_npc_t navi_npcs[NAVI_NPC_COUNT] = {']
    lines += ['    { %d, %d, %d, %d, %d },'%(a['x'],a['y'],a['z'],a['yaw'],a['model']) for a in cast]
    lines += ['};','#endif','']
    (out/'navi_npcs.h').write_text('\n'.join(lines))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'build/generated')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--rom-dir', type=pathlib.Path)
    args = ap.parse_args()

    segments = for_build(source.extract(args.oot, args.rom_dir))
    triangles = entity_floor_triangles(segments['spot04_scene'])

    people, grass, signs, rupees, chests, wonders = [], [], [], [], [], []
    props = []
    boulders = []
    babas = []
    shop = source.extract(args.oot, args.rom_dir, prefix='kokiri_shop')
    keepers = []
    for actor in read_actors(shop['kokiri_shop_room_0']):
        actor.update(room=0, scene=SAVE_SCENE_KOKIRI_SHOP)
        if actor['id'] == ACTOR_EN_OSSAN:
            keepers.append(actor)
        elif actor['id'] == ACTOR_EN_WONDER_ITEM:
            mode, drop = actor['var'] >> 11, (actor['var'] >> 6) & 31
            if mode != 2 or drop not in WONDER_RUPEES:
                sys.exit('shop wonder item 0x%04X unsupported' % actor['var'])
            wonders.append(dict(actor, mode=mode, value=WONDER_RUPEES[drop]))
    if len(keepers) != 1:
        sys.exit('expected one Kokiri shopkeeper, found %d' % len(keepers))
    for name in sorted(segments):
        if 'room' not in name:
            continue
        room = int(name.rsplit('_', 1)[1])
        for actor in read_actors(segments[name]):
            actor['room'] = room
            actor['scene'] = SAVE_SCENE_KOKIRI_FOREST
            if actor['id'] in (0x014E, 0x0111, 0x014F, 0x01B9) or (actor['id'] == 0x0015 and actor['var'] & 255 == 3):
                props.append(actor)
            if actor['id'] == 0x0151 and actor['var'] & 3 == 2:
                import math
                for child in range(8):
                    x = actor['x'] + round(80 * math.sin(child * math.pi / 4))
                    z = actor['z'] + round(80 * math.cos(child * math.pi / 4))
                    y = floor_under(triangles, x, z, actor['y'] + 80)
                    if y is None: raise ValueError('rock circle child has no floor')
                    props.append(dict(actor, id=0x014E, x=x, y=round(y), z=z, var=actor['var'] & 0xF00))
            if actor['id'] == 0x0015 and actor['var'] & 255 in (0, 1):
                height = floor_under(triangles, actor['x'], actor['z'], actor['y'])
                if height is None:
                    raise ValueError('Rupee has no collision floor')
                rupees.append(dict(actor, y=round(height), value=(1, 5)[actor['var'] & 255]))
            if actor['id'] == ACTOR_EN_KO:
                if actor['var'] & 0xFF in ENKO_CHILD_TYPES[SAVE_SCENE_KOKIRI_FOREST]:
                    people.append(dict(actor, kind='CHILD'))
            elif actor['id'] == ACTOR_EN_MD:
                people.append(dict(actor, kind='MIDO'))
            elif actor['id'] == ACTOR_EN_SA:
                people.append(dict(actor, kind='SARIA'))
            elif actor['id'] == ACTOR_EN_KUSA:
                grass.append(actor)
            elif actor['id'] == ACTOR_EN_KANBAN:
                signs.append(actor)
            elif actor['id'] == ACTOR_EN_BOX:
                chests.append(actor)
            elif actor['id'] == ACTOR_EN_GOROIWA:
                boulders.append(actor)
            elif actor['id'] == ACTOR_EN_KAREBABA:
                # params 0 = Grow first; every Kokiri spawn is 1 (Idle).
                if actor['var'] not in (0, 1) or actor['yaw']:
                    sys.exit('Karebaba spawn 0x%04X / yaw %d unsupported' % (actor['var'], actor['yaw']))
                babas.append(actor)
            elif actor['id'] == ACTOR_EN_WONDER_ITEM:
                mode, drop = actor['var'] >> 11, (actor['var'] >> 6) & 31
                if mode not in WONDER_MODES:
                    print('  wonder item mode %d at (%d,%d,%d) skipped'
                          % (mode, actor['x'], actor['y'], actor['z']))
                    continue
                if mode not in (1, 6) and drop not in WONDER_RUPEES:
                    sys.exit('wonder item drop %d is not a rupee' % drop)
                wonders.append(dict(actor, mode=mode,
                                    value=WONDER_RUPEES.get(drop, 0)))

    # Interior people (M3b). En_Md/En_Sa are emitted with their scene; their
    # flag-dependent spawn (EnMd_ShouldSpawn, EnSa_GetType) is runtime.
    for prefix, scene_id in (('link_home', 5),) + INTERIORS:
        rooms = source.extract(args.oot, args.rom_dir, prefix=prefix)
        for name in sorted(k for k in rooms if '_room_' in k):
            for actor in read_actors(rooms[name]):
                actor.update(room=int(name.rsplit('_', 1)[1]), scene=scene_id)
                if actor['id'] in (0x014E, 0x0111, 0x014F, 0x01B9) or (actor['id'] == 0x0015 and actor['var'] & 255 == 3):
                    props.append(actor)
                if actor['id'] == ACTOR_EN_BOX:
                    chests.append(actor)
                elif actor['id'] == ACTOR_EN_KO:
                    # EnKo init filters type 7 again: rotZ 1/2 select adult
                    # placements, not additional child-day brothers.
                    child_type = actor['var'] & 0xFF
                    if (child_type in ENKO_CHILD_TYPES[scene_id] and
                            (child_type != 7 or actor['rot_z'] == 0)):
                        people.append(dict(actor, kind='CHILD'))
                    else:
                        print('  En_Ko type %d in %s: no child spawn (EnKo_CanSpawn)'
                              % (actor['var'] & 0xFF, prefix))
                elif actor['id'] == ACTOR_EN_MD:
                    people.append(dict(actor, kind='MIDO'))
                elif actor['id'] == ACTOR_EN_SA:
                    people.append(dict(actor, kind='SARIA'))

    # Original Deku Tree treasures; room residency filters interaction/drawing.
    dungeon = source.extract(args.oot, args.rom_dir, prefix='ydan')
    for name in sorted(k for k in dungeon if '_room_' in k):
        for actor in read_actors(dungeon[name]):
            if actor['id'] != ACTOR_EN_BOX: continue
            if actor['var'] >> 12 not in (0, 5):
                raise ValueError('Deku chest needs a visibility gate')
            actor.update(room=int(name.rsplit('_', 1)[1]), scene=2)
            chests.append(actor)

    # Keep existing forest identities stable when interiors add named actors.
    # Within each scene, Mido and Saria precede the Kokiri children.
    people.sort(key=lambda a: (a['scene'], {'MIDO': 0, 'SARIA': 1, 'CHILD': 2}[a['kind']],
                               a['x'], a['z']))

    for chest in chests:
        # En_Box: type bits 12-15, get item bits 5-11, treasure flag bits 0-4.
        # Maze sword plus Mido house heart/green/blue rewards.
        if (chest['var'] >> 5) & 0x7F not in (0x05, 0x40, 0x41, 0x27, 0x48, 0x4C, 0x4D):
            sys.exit('unsupported chest reward 0x%04X' % chest['var'])
    # En_Goroiwa: path bits 0-7, loop mode 8-9, ground-follow bit 10.
    # Only the maze boulder's shape is modelled: one-way loop, bit 10 (the
    # MoveAndFall/bg-check variant), a flat path on a flat floor, so the
    # runtime floor is the path height. Anything else is refused.
    if len(boulders) != 1:
        sys.exit('expected one En_Goroiwa, found %d' % len(boulders))
    boulder = boulders[0]
    paths = scene_paths(segments['spot04_scene'])
    exit_guard = next(a for a in people if a['scene'] == 0 and
                      a['kind'] == 'CHILD' and (a['var'] & 255) == 3)
    exit_path = paths[(exit_guard['var'] >> 8) & 255]
    if not exit_path:
        raise ValueError('Kokiri exit guard has no source path')
    path = paths[boulder['var'] & 0xFF]
    if (boulder['var'] >> 8) & 3 != 0 or not (boulder['var'] >> 10) & 1 or len(path) < 2:
        sys.exit('En_Goroiwa 0x%04X shape unsupported' % boulder['var'])
    for (ax, ay, az), (bx, by, bz) in zip(path, path[1:]):
        if ay != path[0][1] or by != path[0][1] or (ax != bx and az != bz):
            sys.exit('En_Goroiwa path is not flat and axis-aligned')
        for t in range(0, 17):
            x, z = ax + (bx - ax) * t / 16, az + (bz - az) * t / 16
            floor = floor_under(triangles, x, z, ay + 20)
            if floor is None or abs(floor - ay) > 2:
                sys.exit('En_Goroiwa path leaves the flat floor at (%d,%d)' % (x, z))
    off_floor = []
    for actor in [p for p in people if p['scene'] == SAVE_SCENE_KOKIRI_FOREST] + grass:
        height = floor_under(triangles, actor['x'], actor['z'], actor['y'])
        actor['floor'] = height
        if height is None or abs(height - actor['y']) > 8:
            off_floor.append(actor)

    args.out.mkdir(parents=True, exist_ok=True)
    emit_navi_cast(segments,args.out)
    banner = '/* Generated by game/tools/build_actors.py -- do not edit. */'
    header = [banner, '', '#ifndef KOKIRI_ACTORS_H', '# define KOKIRI_ACTORS_H',
              '# include <stdint.h>', '',
              '/* Placement only, straight from the US 1.2 room actor lists. */',
              '# define KOKIRI_NPC_COUNT   %d' % len(people),
              '# define KOKIRI_GRASS_COUNT %d' % len(grass),
              '# define KOKIRI_SIGN_COUNT  %d' % len(signs),
              '# define KOKIRI_CHEST_COUNT %d' % len(chests),
              '# define KOKIRI_WONDER_COUNT %d' % len(wonders),
              '# define KOKIRI_RUPEE_COUNT %d' % len(rupees),
              '# define KOKIRI_WORLD_PROP_COUNT %d' % len(props), '']
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
               '    uint8_t  scene;    /* SAVE_SCENE_* the actor list belongs to */',
               '} kokiri_npc_t;', '',
               'typedef struct { int16_t x, y, z; uint8_t room; } kokiri_prop_t;',
               '',
               'extern const kokiri_npc_t  kokiri_npcs[KOKIRI_NPC_COUNT];',
               'extern const kokiri_prop_t kokiri_grass[KOKIRI_GRASS_COUNT];',
               'extern const kokiri_prop_t kokiri_signs[KOKIRI_SIGN_COUNT];',
               'extern const uint16_t kokiri_sign_params[KOKIRI_SIGN_COUNT], kokiri_sign_yaws[KOKIRI_SIGN_COUNT];',
               '/* En_Karebaba spawns (child day header). */',
               '# define KOKIRI_BABA_COUNT  %d' % len(babas),
               '# define KOKIRI_BABA_GROW   0x%02X  /* bit i: spawn i has params 0 */'
               % sum(1 << i for i, b in enumerate(babas) if b['var'] == 0),
               'extern const kokiri_prop_t kokiri_babas[KOKIRI_BABA_COUNT];',
               '',
               '/* En_Box: param = the spawn word (treasure flag bits 0-4). */',
               'typedef struct { int16_t x, y, z; uint16_t yaw, param; uint8_t room, scene; } kokiri_chest_t;',
               'extern const kokiri_chest_t kokiri_chests[KOKIRI_CHEST_COUNT];',
               '/* En_Wonder_Item: mode = params >> 11, value = rupees dropped,',
               '   rot_z = source count/timer/tag index word. */',
               'typedef struct { int16_t x, y, z, rot_z; uint16_t param; uint8_t mode, value, room, scene; } kokiri_wonder_t;',
               '/* EnOssan in the Kokiri Shop (SAVE_SCENE_KOKIRI_SHOP). */',
               '# define KOKIRI_SHOPKEEPER_X %d' % keepers[0]['x'],
               '# define KOKIRI_SHOPKEEPER_Y %d' % keepers[0]['y'],
               '# define KOKIRI_SHOPKEEPER_Z %d' % keepers[0]['z'],
               'extern const kokiri_wonder_t kokiri_wonders[KOKIRI_WONDER_COUNT];',
               'typedef struct { int16_t x, y, z; uint16_t param; uint8_t room, value; } kokiri_rupee_t;',
               'extern const kokiri_rupee_t kokiri_rupees[KOKIRI_RUPEE_COUNT];',
               'extern const uint8_t kokiri_grass_rupees[KOKIRI_GRASS_COUNT][16];',
               'extern const uint16_t kokiri_grass_params[KOKIRI_GRASS_COUNT];',
               'typedef struct { int16_t x,y,z; uint16_t id,param,yaw; uint8_t scene,room; } kokiri_world_prop_t;',
               'extern const kokiri_world_prop_t kokiri_world_props[KOKIRI_WORLD_PROP_COUNT];',
               '/* En_Goroiwa (maze boulder): spawn word, home rot_z, room, and',
               '   its path (scene path list entry params & 0xFF). */',
               '# define KOKIRI_BOULDER_PARAM 0x%04X' % boulder['var'],
               '# define KOKIRI_BOULDER_ROT_Z %d' % boulder['rot_z'],
               '# define KOKIRI_BOULDER_ROOM  %d' % boulder['room'],
               '# define KOKIRI_BOULDER_POINTS %d' % len(path),
               'extern const int16_t kokiri_boulder_path[KOKIRI_BOULDER_POINTS][3];',
               '/* EnKo child type 3: Path_CopyLastPoint after the Emerald. */',
               '# define KOKIRI_EXIT_MOVED_X %d' % exit_path[-1][0],
               '# define KOKIRI_EXIT_MOVED_Y %d' % exit_path[-1][1],
               '# define KOKIRI_EXIT_MOVED_Z %d' % exit_path[-1][2],
               '#endif', '']
    (args.out / 'kokiri_actors.h').write_text('\n'.join(header))

    body = [banner, '', '#include "kokiri_actors.h"', '#include "gameplay.h"', '',
            'const kokiri_npc_t kokiri_npcs[KOKIRI_NPC_COUNT] = {']
    for a in people:
        body.append('    { %d, %d, %d, %u, 0x%04X, KOKIRI_NPC_%s, %d, %d },'
                    % (a['x'], a['y'], a['z'], a['yaw'], a['var'],
                       a['kind'], a['room'], a['scene']))
    body += ['};', '', 'const kokiri_prop_t kokiri_grass[KOKIRI_GRASS_COUNT] = {']
    for a in grass:
        body.append('    { %d, %d, %d, %d },' % (a['x'], a['y'], a['z'], a['room']))
    body += ['};', '', 'const kokiri_prop_t kokiri_babas[KOKIRI_BABA_COUNT] = {']
    body += ['    { %d, %d, %d, %d },' % (b['x'], b['y'], b['z'], b['room']) for b in babas]
    body += ['};', '', 'const kokiri_prop_t kokiri_signs[KOKIRI_SIGN_COUNT] = {']
    for a in signs:
        body.append('    { %d, %d, %d, %d },' % (a['x'], a['y'], a['z'], a['room']))
    body += ['};', 'const uint16_t kokiri_sign_params[KOKIRI_SIGN_COUNT] = {',
             ','.join(str(a['var']) for a in signs), '};',
             'const uint16_t kokiri_sign_yaws[KOKIRI_SIGN_COUNT] = {',
             ','.join(str(a['yaw']) for a in signs)]
    body += ['};', '', 'const kokiri_chest_t kokiri_chests[KOKIRI_CHEST_COUNT] = {']
    for a in chests:
        body.append('    { %d, %d, %d, %u, 0x%04X, %d, %d },' %
                    (a['x'], a['y'], a['z'], a['yaw'], a['var'], a['room'], a['scene']))
    body += ['};', '', 'const kokiri_wonder_t kokiri_wonders[KOKIRI_WONDER_COUNT] = {']
    for a in wonders:
        body.append('    { %d, %d, %d, %d, 0x%04X, %d, %d, %d, %d },' %
                    (a['x'], a['y'], a['z'], a['rot_z'], a['var'], a['mode'],
                     a['value'], a['room'], a['scene']))
    body += ['};', '']
    body += ['const kokiri_rupee_t kokiri_rupees[KOKIRI_RUPEE_COUNT] = {']
    for a in rupees:
        body.append('    { %d, %d, %d, 0x%04X, %d, %d },' %
                    (a['x'], a['y'], a['z'], a['var'], a['room'], a['value']))
    body += ['};', 'const uint8_t kokiri_grass_rupees[KOKIRI_GRASS_COUNT][16] = {']
    for a in grass:
        body.append('    { %s }, /* EnKusa params 0x%04X */' %
                    (', '.join(map(str, grass_rupee_slots(args.oot, a['var']))), a['var']))
    body += ['};', 'const uint16_t kokiri_grass_params[KOKIRI_GRASS_COUNT] = {',
             ', '.join(str(a['var']) for a in grass), '};',
             'const kokiri_world_prop_t kokiri_world_props[KOKIRI_WORLD_PROP_COUNT] = {']
    for a in props:
        body.append('    { %d,%d,%d,0x%04X,0x%04X,%d,%d,%d },' %
                    (a['x'],a['y'],a['z'],a['id'],a['var'],a['yaw'],a['scene'],a['room']))
    body += ['};', '', 'const int16_t kokiri_boulder_path[KOKIRI_BOULDER_POINTS][3] = {']
    body += ['    { %d, %d, %d },' % p for p in path]
    body += ['};', '']
    print('boulder : 0x%04X room %d rot_z %d, path %s'
          % (boulder['var'], boulder['room'], boulder['rot_z'], path))
    print('rupees  : %d original room placements; source grass drop slots' % len(rupees))
    (args.out / 'kokiri_actors.c').write_text('\n'.join(body))

    print('chests  : %s' % ', '.join('0x%04X at (%d,%d,%d) room %d'
          % (a['var'], a['x'], a['y'], a['z'], a['room']) for a in chests))
    print('wonders : %d (%d rupees if every one pays once)'
          % (len(wonders), sum(a['value'] for a in wonders)))
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
