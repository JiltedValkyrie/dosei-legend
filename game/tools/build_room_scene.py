"""Bake authored rooms into replaceable CD/VDP1 banks, not one resident forest."""
import collections
import json
import pathlib
import struct

import build_hybrid_scene as hybrid
from vdp1_budget import Budget


def transitions(oot, rom_dir=None):
    scene = hybrid.source.extract(oot, rom_dir)['spot04_scene']
    for offset in range(0, 0x400, 8):
        command = scene[offset:offset+8]
        if command[0] == 0x14:
            break
        if command[0] == 0x0e:
            start = int.from_bytes(command[4:], 'big') & 0xffffff
            result = []
            for i in range(command[1]):
                front,_,back,_,actor,x,y,z,yaw,params = struct.unpack_from('>4b5hH',scene,start+i*16)
                if actor != 35 or (params >> 6) & 7 != 4:
                    raise ValueError('Unsupported authored room transition')
                result.append(dict(front=front,back=back,x=x,y=y,z=z,yaw=yaw))
            return result
    raise ValueError('Scene has no room transitions')


def pack_room(vertices, faces, tiles, records, normal):
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
    pixels = b''.join(t['pixels'] + bytes((-len(t['pixels']))%8) for t in tiles.values())
    data = bytearray(struct.pack('>8I',0x4b524d31,len(vertices),len(faces),len(tiles),
                                 len(pixels),len(bounds),0,0))
    for p in baked:
        data.extend(struct.pack('>3i',*(v*65536 for v in p)))
    for f in faces:
        data.extend(struct.pack('>3i4H',*normal(baked,f['idx']),*f['idx']))
    for f in faces:
        # SGL 3.02j ATTR: flag, sort, texno, atrb, colno, gstb, dir.
        # Matches ATTRIBUTE(... SORT_CEN|UsePalette|UseNearClip, sprNoflip).
        data.extend(struct.pack('>BB5H',0 if f['cull'] else 1,0x67,
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
    return bytes(data), pixels, bounds


def emit_rooms(args, head, actor, normal):
    out = args.out
    summaries = []
    for room_id in range(3):
        room = 'spot04_room_%d' % room_id
        folder = out / ('room%d' % room_id)
        _,vertices,faces,tiles = hybrid.convert(args.oot,head,actor,folder,
            rom_dir=args.rom_dir,quad_obj=args.quad_obj,source_path=args.scene,room=room)
        manifest = json.loads((folder/'texture_manifest.json').read_text())
        mesh,pixels,bounds = pack_room(vertices,faces,tiles,manifest['faces'],normal)
        (out/('R%d.MSH'%room_id)).write_bytes(mesh)
        (out/('R%d.TEX'%room_id)).write_bytes(pixels)
        summaries.append(dict(id=room_id,vertices=len(vertices),polygons=len(faces),
                              tiles=len(tiles),pixel_bytes=len(pixels),objects=len(bounds),
                              budget=manifest['budget'],workshop=manifest['workshop']))
    portal = transitions(args.oot,args.rom_dir)
    maximum = lambda key: max(r[key] for r in summaries)
    definitions = dict(VERTEX_COUNT=maximum('vertices'), POLYGON_COUNT=maximum('polygons'),
                       TILE_COUNT=maximum('tiles'),PIXEL_BYTES=maximum('pixel_bytes'),
                       OBJECT_COUNT=maximum('objects'))
    header = ['/* Generated room-bank capacities; only one bank is resident. */',
              '#ifndef KOKIRI_SCENE_H','#define KOKIRI_SCENE_H','#include <jo/jo.h>',
              '#define KOKIRI_STREAM_ROOMS 1']
    header += ['#define KOKIRI_%s %d' % item for item in definitions.items()]
    header += ['#define KOKIRI_CENTER_X %d'%head['cx'],'#define KOKIRI_CENTER_Y %d'%head['cy'],
               '#define KOKIRI_CENTER_Z %d'%head['cz'],'#define KOKIRI_RADIUS %d'%head['radius'],
               'typedef struct { unsigned short width,height; unsigned int offset,length; } kokiri_tile;',
               'typedef struct { int minimum[3],maximum[3]; } kokiri_object;',
               'typedef struct { short front,back,x,y,z,yaw; } kokiri_portal;',
               'extern PDATA kokiri_pdata;',
               'extern kokiri_tile kokiri_tiles[KOKIRI_TILE_COUNT];',
               'extern unsigned short kokiri_cluts[KOKIRI_TILE_COUNT][16];',
               'extern unsigned char kokiri_objects[KOKIRI_POLYGON_COUNT+3];',
               'extern kokiri_object kokiri_bounds[KOKIRI_OBJECT_COUNT];',
               '#define KOKIRI_PORTAL_COUNT %d'%len(portal),
               'extern const kokiri_portal kokiri_portals[KOKIRI_PORTAL_COUNT];','#endif']
    (out/'kokiri_scene.h').write_text('\n'.join(header)+'\n')
    code = ['#include "kokiri_scene.h"',
            'static POINT points[KOKIRI_VERTEX_COUNT];',
            'static POLYGON polygons[KOKIRI_POLYGON_COUNT];',
            'static ATTR attributes[KOKIRI_POLYGON_COUNT];',
            'PDATA kokiri_pdata = {points,0,polygons,0,attributes};',
            'unsigned char kokiri_objects[KOKIRI_POLYGON_COUNT+3];',
            'kokiri_object kokiri_bounds[KOKIRI_OBJECT_COUNT];',
            'const kokiri_portal kokiri_portals[KOKIRI_PORTAL_COUNT] = {']
    code += ['    {%d,%d,%d,%d,%d,%d},'%tuple(p[k] for k in ('front','back','x','y','z','yaw')) for p in portal]
    code += ['};']
    (out/'kokiri_scene.c').write_text('\n'.join(code)+'\n')
    (out/'kokiri_textures.c').write_text('#include "kokiri_scene.h"\n'
        'kokiri_tile kokiri_tiles[KOKIRI_TILE_COUNT];\n'
        'unsigned short kokiri_cluts[KOKIRI_TILE_COUNT][16];\n')
    # Shared diagnostic landmark remains the village clearing.
    (out/'texture_probe.h').write_bytes((out/'room0/texture_probe.h').read_bytes())
    (out/'rooms_manifest.json').write_text(json.dumps(dict(rooms=summaries,portals=portal),indent=2)+'\n')
    print('rooms: %d banks; max resident forest %d polygons / %d vertices / %d tiles'
          %(len(summaries),maximum('polygons'),maximum('vertices'),maximum('tiles')),flush=True)
    return summaries
