#!/usr/bin/env python
"""Emit the scene table: spawns, doors and per-scene collision.

Everything here comes out of the verified US 1.2 ROM and the decomp's entrance
table. Nothing is authored, and an exit that leads somewhere this slice does
not contain is REPORTED rather than quietly dropped -- otherwise a door that
silently does nothing looks like a collision bug.

How a door works in the original, and therefore here:

  a collision polygon carries SurfaceType.exitIndex (include/bgcheck.h:219)
    -> exitIndex is ONE-BASED into the scene's exit list (header command 0x13)
    -> that gives an entrance id
    -> include/tables/entrance_table.h maps the id to a scene and a SPAWN
    -> header command 0x00 gives that spawn's position and facing

Verified round trip: link_home's exitIndex 2 resolves to 0x211
(ENTR_KOKIRI_FOREST_3, spawn 3 at -31,100,1073 -- the platform outside the
house) and spot04's exitIndex 4 resolves to 0x272 (ENTR_LINKS_HOUSE_1, spawn 1
at -4,0,-114 -- just inside the door). That is the two-way door between them.

A new game starts at link_home spawn 0, (1,0,95) facing 0x8000, which is the
bed. It is a spawn index from the ROM, not a coordinate chosen here.
"""

import argparse
import json
import math
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'shared/tools'))
import build_kokiri_scene as source
import asset_names

# The scenes this slice contains, in runtime order. `save` is the SAVE_SCENE_*
# id in src/save_state.h; `scene` is the decomp SCENE_* name, used to resolve
# entrance destinations back to one of these.
# `shape` is the room's ROOM_SHAPE_TYPE (decomp include/room.h):
#   'mesh'  -- ROOM_SHAPE_TYPE_NORMAL/CULLABLE: real display-list geometry,
#              converted into a VDP1 bank by build_room_scene.py.
#   'image' -- ROOM_SHAPE_TYPE_IMAGE: a prerendered 320x240 backdrop (stored
#              as JFIF JPEG in the room segment) plus a tiny display list. OoT
#              draws its interiors this way, so there is no geometry to
#              convert. The backdrop goes to VDP2 like the title artwork and
#              costs no VDP1 texture space at all.
SCENES = (
    dict(prefix='link_home', rooms=1, shape='image',
         scene='SCENE_LINKS_HOUSE', sfx=0,
         save='SAVE_SCENE_LINKS_HOUSE', name='Link\'s House'),
    dict(prefix='spot04', rooms=3, shape='mesh',
         scene='SCENE_KOKIRI_FOREST', sfx=1,
         save='SAVE_SCENE_KOKIRI_FOREST', name='Kokiri Forest'),
)

# A new file begins here: Link's house, spawn 0 (the bed).
NEW_GAME_SCENE = 0
NEW_GAME_SPAWN = 0


def entrance_table(oot):
    """Entrance id -> (SCENE_* name, spawn index), from the decomp table."""
    path = oot / 'include/tables/entrance_table.h'
    if not path.is_file():
        sys.exit('decomp entrance table not found: %s' % path)
    table = {}
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        head = re.match(r'/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_ENTRANCE\('
                        r'\s*[A-Z0-9_]+\s*,\s*([A-Z0-9_]+)\s*,\s*(\d+)', line)
        if head:
            table[int(head.group(1), 16)] = (head.group(2), int(head.group(3)))
    if not table:
        sys.exit('entrance table parsed as empty -- has its format changed?')
    return table


def fixed_camera(scene):
    """The prerendered room's fixed camera: pos, rot and fov.

    A ROOM_SHAPE_TYPE_IMAGE room shows one prerendered picture, so the camera
    must sit exactly where that picture was rendered from or nothing lines up.
    OoT keeps camera data in the CollisionHeader's bgCamList (include/bgcheck.h:
    header+0x20), each entry `u16 setting, s16 count, Vec3s* data`, the data
    being BgCamFuncData: pos, rot, fov, flags.

    APPROXIMATION, and labelled as one: this takes the FIRST entry that has
    data. Every polygon in Link's house carries bgCamIndex 2, which is an empty
    entry, so the per-polygon index is not what selects the view for a
    prerendered room -- the scene's camera type (misc-settings command 0x19,
    0x20 here) is. The exact selection rule in Camera_Prerend* has not been
    traced yet. Entry 0 is used because its values match the backdrop: a ~70
    degree downward pitch from 345 units up, which is the view that picture
    shows. If an interior ever looks wrong, this is the first thing to check.
    """
    for pos in range(0, 0x400, 8):
        if scene[pos] == 0x14:
            break
        if scene[pos] != 3:
            continue
        header = _segment_offset_local(scene[pos:pos + 8])
        table = struct.unpack_from('>I', scene, header + 0x20)[0] & 0xFFFFFF
        if not table:
            return None
        for index in range(8):
            setting, count, pointer = struct.unpack_from('>hhI', scene,
                                                         table + 8 * index)
            if not pointer or (pointer >> 24) != 2:
                continue
            at = pointer & 0xFFFFFF
            values = struct.unpack_from('>9h', scene, at)
            return dict(index=index, setting=setting & 0xFFFF,
                        x=values[0], y=values[1], z=values[2],
                        pitch=values[3], yaw=values[4], roll=values[5],
                        fov=values[6])
        return None
    return None


def _segment_offset_local(command):
    return int.from_bytes(command[4:8], 'big') & 0xFFFFFF


def collision_records(surfaces):
    """The 36-byte collision records the runtime already expects.

    Same layout as FOREST.COL so shared/lib/collision needs no change:
    vertex[3][3], normal[3], minimum[3], maximum[3], all int16.
    """
    data = bytearray()
    for poly in surfaces:
        abc = poly['vertices']
        minimum = [min(v[k] for v in abc) for k in range(3)]
        maximum = [max(v[k] for v in abc) for k in range(3)]
        values = [n for v in abc for n in v] + poly['normal'] + minimum + maximum
        data.extend(struct.pack('>18h', *values))
    return bytes(data)


# Wall flags per WALL_TYPE, from the decomp's D_80119D90 table
# (src/code/z_bgcheck.c:69). Link climbs a wall carrying WALL_FLAG_3 (a
# ladder), WALL_FLAG_1 or WALL_FLAG_2 -- func_8083EC18, z_player.c:7491.
# Crawlspaces have their own pair of flags.
WALL_FLAGS = (
    0,                  # WALL_TYPE_0  ordinary wall
    0x01,               # WALL_TYPE_1  WALL_FLAG_0
    0x01 | 0x02,        # WALL_TYPE_2  WALL_FLAG_0 | WALL_FLAG_1   climbable
    0x01 | 0x04,        # WALL_TYPE_3  WALL_FLAG_0 | WALL_FLAG_2   climbable
    0x08,               # WALL_TYPE_4  WALL_FLAG_3                 ladder
    0x10,               # WALL_TYPE_5  WALL_FLAG_CRAWLSPACE_1
    0x20,               # WALL_TYPE_6  WALL_FLAG_CRAWLSPACE_2
    0x40,               # WALL_TYPE_7  WALL_FLAG_6
)

# One byte per collision triangle, in S<scene>.SUR.
SURFACE_CLIMBABLE  = 0x01   # WALL_FLAG_1/2/3: vines, climbable walls, ladders
SURFACE_LADDER     = 0x02   # WALL_FLAG_3 specifically
SURFACE_CRAWLSPACE = 0x04


def surface_records(surfaces):
    """How Link may interact with each collision triangle.

    Rides ALONGSIDE the geometry rather than changing it: S<scene>.COL keeps
    the exact 36-byte records shared/lib/collision already reads, and this is a
    parallel byte array in the same triangle order.

    Without it the ladder up to Link's house is just a wall, so jumping down
    strands the player outside with no way back in, and the crawlspace to the
    sword maze is impassable. Both exist in the ROM: Kokiri Forest has two
    ladder triangles and eight crawlspace triangles.

    The footstep material rides in the high nibble. The slice currently plays
    one footstep sound for the whole forest; this is the data that fixes it.
    """
    data = bytearray()
    for poly in surfaces:
        wall = poly['wall_type']
        flags = WALL_FLAGS[wall] if wall < len(WALL_FLAGS) else 0
        byte = 0
        if flags & (0x02 | 0x04 | 0x08):
            byte |= SURFACE_CLIMBABLE
        if flags & 0x08:
            byte |= SURFACE_LADDER
        if flags & (0x10 | 0x20):
            byte |= SURFACE_CRAWLSPACE
        byte |= (poly['material'] & 0x0F) << 4
        data.append(byte)
    return bytes(data)


def scene_doors(index, prefix, scene, entrances, by_scene_name, report):
    """Every usable door out of one scene, as its real collision triangles."""
    surfaces = source.collision_surfaces(scene)
    highest = max(poly['exit'] for poly in surfaces)
    if not highest:
        return []
    # The exit list stores no count, so the highest exitIndex any polygon
    # carries is exactly how far it is safe to read.
    exits = source.exit_list(scene, highest)
    doors = []
    for poly in surfaces:
        slot = poly['exit']
        if not slot:
            continue
        entrance = exits[slot - 1]
        if entrance not in entrances:
            report.append('%s exitIndex %d: entrance 0x%03X is not in the '
                          'decomp table' % (prefix, slot, entrance))
            continue
        target, spawn = entrances[entrance]
        if target not in by_scene_name:
            report.append('%s exitIndex %d leads to %s, which this slice does '
                          'not contain -- door left inert'
                          % (prefix, slot, target))
            continue
        abc = poly['vertices']
        doors.append(dict(scene=index, entrance=entrance,
                          target=by_scene_name[target], spawn=spawn,
                          y=sum(v[1] for v in abc) // 3,
                          xz=[(v[0], v[2]) for v in abc],
                          target_name=target))
    return doors


def main():
    here = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=pathlib.Path, default=here / 'build/generated')
    ap.add_argument('--cd', type=pathlib.Path, default=here / 'build/cd')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', default=None)
    args = ap.parse_args()

    entrances = entrance_table(args.oot)
    by_scene_name = {entry['scene']: i for i, entry in enumerate(SCENES)}

    args.out.mkdir(parents=True, exist_ok=True)
    args.cd.mkdir(parents=True, exist_ok=True)

    report, spawns, doors, summaries, cameras = [], [], [], [], []
    for index, entry in enumerate(SCENES):
        segments = source.extract(args.oot, args.rom_dir, prefix=entry['prefix'],
                                  expect=entry['rooms'] + 1)
        scene = segments[entry['prefix'] + '_scene']
        surfaces = source.collision_surfaces(scene)
        records = collision_records(surfaces)
        (args.cd / asset_names.scene_asset(index, 'COL')).write_bytes(records)
        flags = surface_records(surfaces)
        (args.cd / asset_names.scene_asset(index, 'SUR')).write_bytes(flags)
        first_spawn = len(spawns)
        for spawn in source.spawn_points(scene):
            spawns.append(dict(scene=index, **spawn))
        camera = fixed_camera(scene) if entry['shape'] == 'image' else None
        if entry['shape'] == 'image' and not camera:
            report.append('%s is a prerendered room but has no bgCam data; '
                          'its camera will fall back to the follow camera'
                          % entry['prefix'])
        cameras.append(camera)
        scene_doors_found = scene_doors(index, entry['prefix'], scene,
                                        entrances, by_scene_name, report)
        doors.extend(scene_doors_found)
        summaries.append(dict(index=index, prefix=entry['prefix'],
                              climbable=sum(1 for b in flags if b & SURFACE_CLIMBABLE),
                              ladders=sum(1 for b in flags if b & SURFACE_LADDER),
                              crawlspaces=sum(1 for b in flags if b & SURFACE_CRAWLSPACE),
                              rooms=entry['rooms'], triangles=len(surfaces),
                              spawns=len(spawns) - first_spawn,
                              doors=len(scene_doors_found),
                              first_spawn=first_spawn))

    # A spawn sitting on a doorway would send the player straight back through
    # it. The runtime guards against the loop by requiring Link to step off a
    # door before it can fire again, but a spawn that close is still worth
    # seeing, because it means arrival lands on the threshold.
    def inside(door, x, z):
        sign = 0
        for i in range(3):
            j = (i + 1) % 3
            ax, az = door['xz'][i]
            bx, bz = door['xz'][j]
            cross = (bx - ax) * (z - az) - (bz - az) * (x - ax)
            if cross == 0:
                continue
            here = 1 if cross > 0 else -1
            if sign == 0:
                sign = here
            elif here != sign:
                return False
        return True

    for spawn in spawns:
        for door in doors:
            if door['scene'] != spawn['scene']:
                continue
            if abs(spawn['y'] - door['y']) > 60:
                continue
            if inside(door, spawn['x'], spawn['z']):
                report.append('scene %d spawn at (%d,%d,%d) stands ON the door '
                              'to %s -- arrival lands on the threshold'
                              % (spawn['scene'], spawn['x'], spawn['y'],
                                 spawn['z'], door['target_name']))

    banner = '/* Generated by game/tools/build_scene_table.py -- do not edit. */'
    header = [banner, '', '#ifndef SCENE_TABLE_H', '# define SCENE_TABLE_H',
              '# include <stdint.h>', '',
              '/* Scenes, spawns and doors, all read from the US 1.2 ROM. A door',
              '   is a real collision triangle carrying SurfaceType.exitIndex;',
              '   see build_scene_table.py for the resolution chain. */',
              '# define SCENE_COUNT       %d' % len(SCENES),
              '# define SCENE_SPAWN_COUNT %d' % len(spawns),
              '# define SCENE_DOOR_COUNT  %d' % max(len(doors), 1),
              '# define SCENE_NEW_GAME_SCENE %d' % NEW_GAME_SCENE,
              '# define SCENE_NEW_GAME_SPAWN %d' % NEW_GAME_SPAWN, '']
    for index, entry in enumerate(SCENES):
        header.append('# define SCENE_%s %d'
                      % (entry['prefix'].upper().replace('-', '_'), index))
    header += ['',
               '/* A prerendered interior shows one fixed picture, so its',
               '   camera is fixed too. `image` is 0 for an ordinary scene',
               '   rendered with the follow camera. */',
               'typedef struct {',
               '    uint8_t  image;       /* 1 = prerendered backdrop room */',
               '    int16_t  cam_x, cam_y, cam_z;',
               '    uint16_t cam_pitch, cam_yaw;',
               '    int16_t  cam_fov;     /* hundredths of a degree */',
               '    /* SGL screen distance for that fov, computed offline:',
               '       half the 240-line picture over tan(fov/2). The SH-2 has',
               '       no FPU, so the tangent is never taken at runtime. */',
               '    int16_t  cam_dist;',
               '    uint8_t  rooms;       /* room banks on the disc */',
               '    uint8_t  first_spawn; /* index into scene_spawns */',
               '    uint8_t  spawns;',
               '    uint8_t  save_scene;  /* SAVE_SCENE_* for the flag store */',
               '    uint8_t  sfx_bank;    /* build_action_audio AREA_BANKS index */',
               '} scene_entry_t;', '',
               'typedef struct {',
               '    int16_t  x, y, z;',
               '    uint16_t yaw;         /* binang, straight from the ROM */',
               '    uint8_t  scene;',
               '} scene_spawn_t;', '',
               '/* A doorway, as its original collision triangle. XZ decides',
               '   whether Link is standing on it; `y` is the floor height, so',
               '   a door cannot fire from a different storey. */',
               'typedef struct {',
               '    int16_t  x[3], z[3];',
               '    int16_t  y;',
               '    uint8_t  scene;       /* the side Link must be on */',
               '    uint8_t  target;      /* scene to load */',
               '    uint8_t  spawn;       /* spawn within that scene */',
               '} scene_door_t;', '',
               'extern const scene_entry_t scene_entries[SCENE_COUNT];',
               'extern const scene_spawn_t scene_spawns[SCENE_SPAWN_COUNT];',
               'extern const scene_door_t  scene_doors[SCENE_DOOR_COUNT];',
               '#endif', '']
    (args.out / 'scene_table.h').write_text('\n'.join(header))

    body = [banner, '', '#include "scene_table.h"', '#include "save_state.h"', '',
            'const scene_entry_t scene_entries[SCENE_COUNT] = {']
    for entry, summary, camera in zip(SCENES, summaries, cameras):
        cam = camera or dict(x=0, y=0, z=0, pitch=0, yaw=0, fov=0)
        half = cam['fov'] / 200.0            # fov is hundredths of a degree
        dist = 0
        if half > 0:
            dist = int(round(120.0 / math.tan(math.radians(half))))
        body.append('    { %d, %d, %d, %d, 0x%04X, 0x%04X, %d, %d, %d, %d, %d, %s, %d },'
                    % (1 if entry['shape'] == 'image' else 0,
                       cam['x'], cam['y'], cam['z'],
                       cam['pitch'] & 0xFFFF, cam['yaw'] & 0xFFFF, cam['fov'],
                       dist, entry['rooms'], summary['first_spawn'],
                       summary['spawns'], entry['save'], entry['sfx']))
    body += ['};', '', 'const scene_spawn_t scene_spawns[SCENE_SPAWN_COUNT] = {']
    for spawn in spawns:
        body.append('    { %d, %d, %d, 0x%04X, %d },'
                    % (spawn['x'], spawn['y'], spawn['z'], spawn['yaw'],
                       spawn['scene']))
    body += ['};', '', 'const scene_door_t scene_doors[SCENE_DOOR_COUNT] = {']
    for door in doors:
        xs = ','.join(str(x) for x, _ in door['xz'])
        zs = ','.join(str(z) for _, z in door['xz'])
        body.append('    { {%s}, {%s}, %d, %d, %d, %d },'
                    % (xs, zs, door['y'], door['scene'], door['target'],
                       door['spawn']))
    if not doors:
        body.append('    { {0,0,0}, {0,0,0}, 0, 0, 0, 0 },')
    body += ['};', '', '/* END OF FILE */', '']
    (args.out / 'scene_table.c').write_text('\n'.join(body))

    (args.out / 'scene_table.json').write_text(json.dumps(
        dict(scenes=summaries, doors=[{k: v for k, v in d.items()
                                       if k != 'xz'} for d in doors],
             notes=report), indent=2) + '\n')

    print('scenes  : %d, %d spawns, %d doors' % (len(SCENES), len(spawns),
                                                 len(doors)))
    for entry, summary in zip(SCENES, summaries):
        print('  %-10s %d room(s), %4d collision, %d spawn(s), %d door(s), '
              '%d climbable (%d ladder), %d crawlspace'
              % (entry['prefix'], summary['rooms'], summary['triangles'],
                 summary['spawns'], summary['doors'], summary['climbable'],
                 summary['ladders'], summary['crawlspaces']))
    for entry, camera in zip(SCENES, cameras):
        if camera:
            print('  camera: %-10s bgCam[%d] setting 0x%02X pos (%d,%d,%d) '
                  'pitch %d yaw %d fov %.2f deg'
                  % (entry['prefix'], camera['index'], camera['setting'],
                     camera['x'], camera['y'], camera['z'],
                     camera['pitch'], camera['yaw'], camera['fov'] / 100.0))
    for door in doors:
        print('  door: scene %d -> %s spawn %d (entrance 0x%03X)'
              % (door['scene'], door['target_name'], door['spawn'],
                 door['entrance']))
    print('  new game starts at scene %d spawn %d'
          % (NEW_GAME_SCENE, NEW_GAME_SPAWN))
    for note in dict.fromkeys(report):
        print('  note: %s' % note)


if __name__ == '__main__':
    main()
