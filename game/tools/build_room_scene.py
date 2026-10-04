"""Bake authored rooms into replaceable CD/VDP1 banks, not one resident forest."""
import collections
import json
import pathlib
import struct

import build_hybrid_scene as hybrid
from vdp1_budget import Budget
import asset_names
from build_sgl_scene import floor_uses_far_sort


def transition_layers(scene):
    """Every source scene header, including null-header fallback layers."""
    from build_actor_manifest import header, alt_headers, layer_header
    main = header(scene, 0, 2)
    count = max(4, len(alt_headers(scene, main, 2)) + 1)
    for layer in range(count):
        base, _ = layer_header(scene, main, 2, layer)
        yield layer, header(scene, base, 2)


def transition_rows(scene):
    for layer, commands in transition_layers(scene):
        for cmd, count, address in commands:
            if cmd != 0x0e:
                continue
            start = address & 0xffffff
            for index in range(count):
                values = struct.unpack_from('>4b5hH', scene, start + index * 16)
                row = dict(zip(('front', 'front_camera', 'back', 'back_camera',
                                'actor', 'x', 'y', 'z', 'yaw', 'params'), values))
                yield dict(row, layer=layer, index=index)


def transition_kind(actor, params):
    if actor == 9:                 # En_Door, types in bits 7..9
        return 24 + ((params >> 7) & 7)
    if actor == 46:                # Door_Shutter, types in bits 6..9
        return 8 + ((params >> 6) & 15)
    if actor == 35:                # En_Holl
        return (params >> 6) & 7
    return 255                    # retained as blocked, never a free portal


def transitions(oot, rom_dir=None, prefix='spot04', room_count=None, strict=True,
                all_layers=False):
    """Shared tunnels, handle doors and shutters, with original gate data.

    Unsupported actor/type records remain closed kind 255 in generic imports;
    the world-route audit names them. No unsupported doorway becomes a tunnel.
    Main-only remains available for existing source/collision checks.
    """
    scene = hybrid.source.extract(oot, rom_dir, prefix=prefix)[prefix + '_scene']
    result = {}
    for row in transition_rows(scene):
        if not all_layers and row['layer']:
            continue
        front, back, actor, params = (row[k] for k in ('front', 'back', 'actor', 'params'))
        if room_count is not None and not all(-1 <= side < room_count for side in (front, back)):
            continue  # audit records missing banks; runtime must not load them
        kind = transition_kind(actor, params)
        if kind == 255 and strict:
            raise ValueError('Unsupported authored transition: %s actor %d params %04X' %
                             (prefix, actor, params))
        keys = ('front', 'back', 'x', 'y', 'z', 'yaw')
        key = tuple(row[k] for k in keys) + (kind, params & 127)
        if key not in result:
            result[key] = dict(zip(keys, key), kind=kind, flag=params & (127 if actor == 9 else 63), layers=0)
        result[key]['layers'] |= 1 << row['layer']
    return list(result.values())


# Runtime record: short cx,cy,cz; ushort radius, lod0_dist, cull_dist;
# uchar lod1_object, lod0_object (0xFF = none); 2 pad. ram_cart.h carve.
LOD_RECORD = struct.Struct('>3h3H2B2x')
LOD_NONE = 0xFF
LOD_MAX_RECORDS = 96  # RAM_CART_MESH_LOD_BYTES / 16
LOD0_OBJECT_BASE = 0x10000  # map_meshes.LOD0_OBJECT_BASE


def lod_table(vertices, records, lods, object_ids):
    """Integer per-mesh LOD rows. lods: {source object: settings}.

    Source-space (Y up) centre and bounding radius over both LOD sets, so one
    distance test chooses between them. Runtime uses object ids, not
    first/count ranges: its visibility partition reorders polygons."""
    import math
    rows = []
    for obj in sorted(lods, key=int):
        setting = lods[obj]; obj = int(obj)
        if obj not in object_ids:
            raise ValueError('LOD object %d has no faces in this room' % obj)
        near = obj + LOD0_OBJECT_BASE
        if setting.get('lod0_faces') and near not in object_ids:
            raise ValueError('LOD0 for object %d produced no faces' % obj)
        members = [r for r in records if r['object'] in (obj, near)]
        points = [vertices[v] for r in members for v in r['indices']]
        low = [min(p[k] for p in points) for k in range(3)]
        high = [max(p[k] for p in points) for k in range(3)]
        centre = [(a + b) // 2 for a, b in zip(low, high)]
        radius = max(math.isqrt(sum((p[k]-centre[k])**2 for k in range(3))) + 1 for p in points)
        near_dist, cull = setting['lod0_distance'], setting['cull_distance']
        if not (0 <= near_dist <= cull <= 32767) or radius > 32767:
            raise ValueError('LOD distances/radius out of range for object %d' % obj)
        rows.append(dict(object=obj, centre=centre, radius=radius,
                         lod0_distance=near_dist if near in object_ids else 0,
                         cull_distance=cull, lod1=object_ids[obj],
                         lod0=object_ids.get(near, LOD_NONE)))
    if len(rows) > LOD_MAX_RECORDS:
        raise ValueError('%d LOD meshes exceed the %d-record cart carve' % (len(rows), LOD_MAX_RECORDS))
    return rows


def pack_lods(rows):
    return b''.join(LOD_RECORD.pack(*r['centre'], r['radius'], r['lod0_distance'],
                                    r['cull_distance'], r['lod1'], r['lod0']) for r in rows)


def pack_room(vertices, faces, tiles, records, normal, lods=None):
    """Big-endian Saturn POINT/POLYGON/ATTR buffers, tile table and palettes."""
    baked = [(x,-y,z) for x,y,z in vertices]
    objects = collections.defaultdict(list)
    for i, record in enumerate(records):
        objects[record['object']].append(i)
    object_ids = {old:i for i,old in enumerate(sorted(objects))}
    bounds = []
    for old in sorted(objects):
        points = [vertices[v] for i in objects[old] for v in records[i]['indices']]
        bounds.append(tuple(min(p[k] for p in points) for k in range(3)) +
                      tuple(max(p[k] for p in points) for k in range(3)))
    if len(bounds) > LOD_NONE:
        raise ValueError('%d mesh objects exceed the 8-bit object id' % len(bounds))
    lod_rows = lod_table(vertices, records, lods or {}, object_ids)
    pixels = b''.join(t['pixels'] + bytes((-len(t['pixels']))%8) for t in tiles.values())
    data = bytearray(struct.pack('>8I',0x4b524d31,len(vertices),len(faces),len(tiles),
                                 len(pixels),len(bounds),len(lod_rows),0))
    for p in baked:
        data.extend(struct.pack('>3i',*(v*65536 for v in p)))
    for f in faces:
        data.extend(struct.pack('>3i4H',*normal(baked,f['idx']),*f['idx']))
    for f in faces:
        # Preserve the same floor tag as the resident scene exporter.
        # Runtime switches tagged overhead planes back to centre sorting.
        sort = 0x66 if floor_uses_far_sort(baked, f['idx'], normal(baked, f['idx'])) else 0x67
        if 'colour' in f:
            data.extend(struct.pack('>BB5H', 0 if f['cull'] else 1, sort,
                                    0, 0xA8, f['colour'], 0, 4))
            continue
        # SGL 3.02j ATTR: flag, sort, texno, atrb, colno, gstb, dir.
        # Matches ATTRIBUTE(... SORT_CEN|UsePalette|UseNearClip, sprNoflip).
        data.extend(struct.pack('>BB5H',0 if f['cull'] else 1,sort,
                                tiles[f['tex_off']]['index'],0x88 | (0x100 if f['mesh'] else 0),0,0,2))
    offset = 0
    for t in tiles.values():
        data.extend(struct.pack('>HHII',t['width'],t['height'],offset,len(t['pixels'])))
        offset += (len(t['pixels'])+7)//8*8
    for t in tiles.values():
        data.extend(struct.pack('>16H',*t['clut']))
    data.extend(bytes(object_ids[r['object']] for r in records))
    data.extend(bytes((-len(records))%4))
    for b in bounds:
        data.extend(struct.pack('>6i',*b))
    data.extend(pack_lods(lod_rows))
    return bytes(data), pixels, bounds


def emit_rooms(args, head, actor, normal):
    """One replaceable bank per (scene, room), plus the shared capacities.

    Only ONE bank is resident at a time, so the compiled capacities are the
    maximum across every bank rather than a sum. Banks are named S<scene>R<room>
    so a scene added later needs no runtime change, only a table entry.
    """
    from build_scene_table import SCENES

    out = args.out
    summaries = []
    forest_rooms = []
    portals = []
    for scene_id, entry in enumerate(SCENES):
        prefix = entry['prefix']
        room_actor=actor
        if prefix=='spot00':
            from build_field_owl import build as build_owl
            models=build_owl(args.oot,args.rom_dir,out/'owl')['models']
            room_actor=dict(tiles=list(actor['tiles'])+[t for m in models for t in m['tiles']],
                polygons=actor['polygons']+max(m['polygons'] for m in models),
                vertices=actor['vertices']+max(m['vertices'] for m in models))
        scene_portals = transitions(args.oot, args.rom_dir, prefix=prefix, room_count=entry['rooms'],
                                    strict=not entry.get('generic'), all_layers=True)
        for portal in scene_portals:
            portals.append(dict(portal, scene=scene_id))
        if entry['shape'] != 'mesh':
            # A prerendered-backdrop interior (ROOM_SHAPE_TYPE_IMAGE) has no
            # display-list geometry to convert, so it gets no VDP1 bank. Its
            # backdrop is staged by build_scene_backdrops.py instead.
            continue
        for room_id in range(entry['rooms']):
            room = '%s_room_%d' % (prefix, room_id)
            if entry.get('generic'):
                # All-scenes registration: bank baked by build_all_scenes.py.
                from build_scene_table import ALL_SCENES_DIR, _room_header
                baked = ALL_SCENES_DIR / room
                (out / asset_names.room_asset(scene_id, room_id, 'MSH')).write_bytes(
                    (baked / 'room.msh').read_bytes())
                (out / asset_names.room_asset(scene_id, room_id, 'TEX')).write_bytes(
                    (baked / 'room.tex').read_bytes())
                summaries.append(dict(scene=scene_id, prefix=prefix, id=room_id,
                                      budget=[], workshop=None, **_room_header(baked / 'room.msh')))
                continue
            folder = out / ('s%dr%d' % (scene_id, room_id))
            from room_imports import selected, convert as convert_import
            override = selected(prefix, room_id)
            if prefix == 'spot00' and room_id == 0 and not override:
                # Hyrule Field streams pieces by distance from the RAM cart
                # (build_field_chunks.py, runtime field_stream.h): no KRM1 bank.
                import build_field_chunks as field
                from layout_variants import build_document
                owl_actor = dict(tiles=[t for m in models for t in m['tiles']],
                                 polygons=max(m['polygons'] for m in models),
                                 vertices=max(m['vertices'] for m in models))
                stale = [out / asset_names.room_asset(scene_id, room_id, ext) for ext in ('MSH', 'TEX')]
                for path in stale:
                    path.unlink(missing_ok=True)
                result = field.bake(args.oot, args.rom_dir, head, actor, owl_actor,
                                    build_document(),
                                    out / asset_names.room_asset(scene_id, room_id, 'STM'),
                                    out / 'field_stream_report.json', room=room)
                summaries.append(dict(scene=scene_id, prefix=prefix, id=room_id,
                                      vertices=max(result['worst']['points'], result['owl_worst']['points']),
                                      polygons=max(result['worst']['polys'], result['owl_worst']['polys']),
                                      tiles=result['slots'], pixel_bytes=0,
                                      objects=max(result['worst']['pieces'], result['owl_worst']['pieces']),
                                      budget=[], workshop=None, streamed=True))
                continue
            if override:
                vertices, faces, tiles, manifest = convert_import(override, room_actor)
                print('room import:', room, override['obj'], flush=True)
            else:
                _, vertices, faces, tiles = hybrid.convert(
                    args.oot, head, room_actor, folder, rom_dir=args.rom_dir,
                    quad_obj=args.quad_obj, source_path=args.scene, room=room,
                    prefix=prefix,base_tile_limit=32 if prefix=='spot00' else None,
                    source_tessellation=prefix=='spot00',
                    wall_split_limit=3 if prefix=='spot00' else None)
                manifest = json.loads((folder / 'texture_manifest.json').read_text())
            if prefix == 'spot04':
                forest_rooms.append((vertices, faces, tiles))
            lods = manifest.get('lods', {})
            mesh, pixels, bounds = pack_room(vertices, faces, tiles,
                                             manifest['faces'], normal, lods)
            if lods:
                near = [r for r in manifest['faces'] if r['object'] >= LOD0_OBJECT_BASE]
                near_points = {v for r in near for v in r['indices']}
                print('  LOD %s: %d meshes, LOD0 %d polys / %d verts (+%d B POLYGON+ATTR, '
                      '+%d B POINT), table %d B in cart carve'
                      % (room, len(lods), len(near), len(near_points), len(near)*32,
                         len(near_points)*12, len(lods)*LOD_RECORD.size), flush=True)
            (out / asset_names.room_asset(scene_id, room_id, 'MSH')).write_bytes(mesh)
            (out / asset_names.room_asset(scene_id, room_id, 'TEX')).write_bytes(pixels)
            summaries.append(dict(scene=scene_id, prefix=prefix, id=room_id,
                                  vertices=len(vertices), polygons=len(faces),
                                  tiles=len(tiles), pixel_bytes=len(pixels),
                                  objects=len(bounds),
                                  budget=manifest['budget'],
                                  workshop=manifest['workshop']))
    # Opening banks share these buffers and the source room artwork. Include
    # their actual capacities, never an old authored cutscene mesh manifest.
    sized = list(summaries)
    from build_opening_banks import emit_opening_banks
    sized.extend(emit_opening_banks(args.oot, out, forest_rooms, normal))

    from build_emerald_story import emit as emit_emerald
    sized.extend(emit_emerald(args.oot,args.rom_dir,out,head,actor,forest_rooms,normal))

    # Story banks used to overwrite real generic scenes 20/21/23/25/26/28.
    # Check identities AND final headers after every emitter has run; a valid
    # individual bake is not evidence that its destination survived staging.
    bank_names = set()
    for row in sized:
        filename = asset_names.room_asset(row['scene'],row['id'],'MSH')
        if filename in bank_names:
            raise ValueError('Duplicate gameplay/story bank destination: '+filename)
        bank_names.add(filename)
        if row.get('streamed'):
            continue
        with (out/filename).open('rb') as stream:
            actual = struct.unpack('>6I',stream.read(24))[1:]
        expected = tuple(row[k] for k in ('vertices','polygons','tiles','pixel_bytes','objects'))
        if actual != expected:
            raise ValueError('Room bank overwritten after bake: %s %s != %s' % (filename,actual,expected))

    maximum = lambda key: max(r[key] for r in sized)
    definitions = dict(VERTEX_COUNT=maximum('vertices'),
                       POLYGON_COUNT=maximum('polygons'),
                       TILE_COUNT=maximum('tiles'),
                       PIXEL_BYTES=maximum('pixel_bytes'),
                       OBJECT_COUNT=maximum('objects'))
    header = ['/* Generated room-bank capacities; only one bank is resident. */',
              '#ifndef KOKIRI_SCENE_H', '#define KOKIRI_SCENE_H',
              '#include <jo/jo.h>', '#include "ram_low.h"',
              '#define KOKIRI_STREAM_ROOMS 1']
    header += ['#define KOKIRI_%s %d' % item for item in definitions.items()]
    header += ['#define KOKIRI_CENTER_X %d'%head['cx'],'#define KOKIRI_CENTER_Y %d'%head['cy'],
               '#define KOKIRI_CENTER_Z %d'%head['cz'],'#define KOKIRI_RADIUS %d'%head['radius'],
               'typedef struct { unsigned short width,height; unsigned int offset,length; } kokiri_tile;',
               'typedef struct { int minimum[3],maximum[3]; } kokiri_object;',
               '/* An En_Holl tunnel between two rooms of ONE scene. `scene` is',
               '   which scene it belongs to; a portal never crosses scenes. */',
               'typedef struct { short front,back,x,y,z,yaw; unsigned char scene,kind,flag; unsigned int layers; } kokiri_portal;',
               'extern PDATA kokiri_pdata;',
               'extern kokiri_tile *kokiri_tiles;',
               'extern unsigned short (*kokiri_cluts)[16];',
               'bool kokiri_bank_allocate(void);',
               '#define kokiri_objects ((unsigned char *)RAM_LOW(RAM_LOW_ROOM_OBJECTS_OFFSET))',
               '#define kokiri_bounds ((kokiri_object *)RAM_LOW(RAM_LOW_ROOM_BOUNDS_OFFSET))',
               'typedef char room_objects_fit[KOKIRI_POLYGON_COUNT+3 <= RAM_LOW_ROOM_OBJECTS_BYTES ? 1 : -1];',
               'typedef char room_bounds_fit[KOKIRI_OBJECT_COUNT*sizeof(kokiri_object) <= RAM_LOW_ROOM_BOUNDS_BYTES ? 1 : -1];',
               '#define KOKIRI_PORTAL_COUNT %d'%max(len(portals), 1),
               'extern const kokiri_portal kokiri_portals[KOKIRI_PORTAL_COUNT];','#endif']
    (out/'kokiri_scene.h').write_text('\n'.join(header)+'\n')
    code = ['#include "kokiri_scene.h"',
            'PDATA kokiri_pdata;',
            'bool kokiri_bank_allocate(void) {',
            '    if (kokiri_pdata.pntbl) return true;',
            '    POINT *points = jo_malloc(sizeof(POINT) * KOKIRI_VERTEX_COUNT);',
            '    POLYGON *polygons = jo_malloc(sizeof(POLYGON) * KOKIRI_POLYGON_COUNT);',
            '    ATTR *attributes = jo_malloc(sizeof(ATTR) * KOKIRI_POLYGON_COUNT);',
            '    kokiri_tiles = jo_malloc(sizeof(kokiri_tile) * KOKIRI_TILE_COUNT);',
            '    kokiri_cluts = jo_malloc(32 * KOKIRI_TILE_COUNT);',
            '    if (!points || !polygons || !attributes || !kokiri_tiles || !kokiri_cluts) {',
            '        if (points) jo_free(points); if (polygons) jo_free(polygons);',
            '        if (attributes) jo_free(attributes);',
            '        if (kokiri_tiles) jo_free(kokiri_tiles);',
            '        if (kokiri_cluts) jo_free(kokiri_cluts);',
            '        kokiri_tiles = 0; kokiri_cluts = 0; return false;',
            '    }',
            '    kokiri_pdata.pntbl = points; kokiri_pdata.pltbl = polygons;',
            '    kokiri_pdata.attbl = attributes; return true;',
            '}',
            'const kokiri_portal kokiri_portals[KOKIRI_PORTAL_COUNT] = {']
    code += ['    {%d,%d,%d,%d,%d,%d,%d,%d,%d,%du},'
             % tuple(p[k] for k in ('front','back','x','y','z','yaw','scene','kind','flag','layers'))
             for p in portals]
    if not portals:
        code += ['    {0,0,0,0,0,0,0,0},']
    code += ['};']
    (out/'kokiri_scene.c').write_text('\n'.join(code)+'\n')
    (out/'kokiri_textures.c').write_text('#include "kokiri_scene.h"\n'
        'kokiri_tile *kokiri_tiles;\n'
        'unsigned short (*kokiri_cluts)[16];\n')
    # Shared diagnostic landmark remains the village clearing: spot04 room 0.
    probe = out / ('s%dr0' % next(i for i, e in enumerate(SCENES)
                                  if e['prefix'] == 'spot04'))
    (out/'texture_probe.h').write_bytes((probe/'texture_probe.h').read_bytes())
    (out/'rooms_manifest.json').write_text(json.dumps(
        dict(rooms=summaries, portals=portals), indent=2)+'\n')
    print('rooms: %d banks across %d scenes; worst bank %d polygons / %d '
          'vertices / %d tiles / %d texture bytes'
          % (len(summaries), len(SCENES), maximum('polygons'),
             maximum('vertices'), maximum('tiles'), maximum('pixel_bytes')),
          flush=True)
    for r in summaries:
        print('  S%dR%d %-10s %4d polygons %4d vertices %4d tiles %6d bytes'
              % (r['scene'], r['id'], r['prefix'], r['polygons'],
                 r['vertices'], r['tiles'], r['pixel_bytes']), flush=True)
    return summaries
