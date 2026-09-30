"""Read-only source bridge: baked or ROM geometry and layout placements."""
from functools import lru_cache
import re
import struct
import sys
from pathlib import Path

from mesh_assets import PROJECT
from viewport_math import bounds

ROOT = PROJECT.parent
for path in ('game/tools','shared/tools','tools/launcher'):
    sys.path.insert(0,str(ROOT/path))
import build_kokiri_scene as source
import build_actor_manifest as actors
import build_scene_table as scenes
import project_config
import layout_variants as layouts
import map_meshes


def original_mesh(prefix, room, segs, oot, document=None):
    """Decode main-header ROM triangles directly, independent of published banks."""
    display = source.DisplayLists(segs[prefix+'_scene'], segs[f'{prefix}_room_{room}'])
    if prefix == 'ydan':
        import xml.etree.ElementTree as ET
        xml = ET.parse(Path(oot)/'assets/xml/scenes/dungeons/ydan.xml')
        offset = next(int(e.attrib['Offset'],16) for e in xml.iter('Texture')
                      if e.attrib['Name']=='gDekuTreeDayEntranceTex')
        display.segments[8] = segs[prefix+'_scene'][offset:]
    display.room()
    room_name=f'{prefix}_room_{room}'
    for face in display.faces: face['room']=room_name
    raw_faces=map_meshes.apply_faces(display.faces,{room_name:segs[room_name]},document)
    faces = []
    for face in raw_faces:
        texture = face['texture']
        colours = [c for c in texture['colors'] if c[3]] if texture else []
        rgb = tuple(round(sum(c[i] for c in colours)/len(colours)) for i in range(3)) if colours else face['prim'][:3]
        faces.append(dict(points=[tuple(v[:3]) for v in face['vertices']], object=face['object'], colour=rgb,
                          source_face=face))
    return faces


def rooms():
    return [(f"{s['name']} / Room {room}", s['prefix'], index, room)
            for index,s in enumerate(scenes.SCENES) if s['shape']=='mesh' for room in range(s['rooms'])]


def read_room(path):
    """KRM1 baked POINT/POLYGON/ATTR data; undo the baker's Y negation."""
    data = Path(path).read_bytes()
    if len(data)<32: raise ValueError('Truncated room header')
    magic,nv,nf,nt,pixels,no,_,_ = struct.unpack_from('>8I',data)
    expected = 32+nv*12+nf*32+nt*44+((nf+3)&~3)+no*24
    if magic!=0x4b524d31 or not nv or not nf or expected!=len(data):
        raise ValueError('Invalid KRM1 room ranges')
    vertices = [(x/65536,-y/65536,z/65536) for x,y,z in struct.iter_unpack('>3i',data[32:32+nv*12])]
    polygons,attrs = 32+nv*12,32+nv*12+nf*20
    palettes = attrs+nf*12+nt*12
    objects = palettes+nt*32
    colours = []
    for i in range(nt):
        palette = struct.unpack_from('>16H',data,palettes+i*32)
        colours.append(tuple(round(sum(((c>>s)&31)*255/31 for c in palette[1:])/15) for s in (0,5,10)))
    faces = []
    for i in range(nf):
        ids = struct.unpack_from('>4H',data,polygons+i*20+12)
        if max(ids)>=nv or data[objects+i]>=no: raise ValueError('Invalid room vertex/object index')
        _,_,tex,_,colour,_,direction = struct.unpack_from('>BB5H',data,attrs+i*12)
        if direction==4:
            rgb = tuple(round(((colour>>s)&31)*255/31) for s in (0,5,10))
        else:
            if tex>=nt: raise ValueError('Invalid room texture index')
            rgb = colours[tex]
        faces.append(dict(points=[vertices[j] for j in ids[:3 if ids[2]==ids[3] else 4]],
                          object=data[objects+i], colour=rgb))
    return vertices,faces


@lru_cache(maxsize=4)
def segments(oot, roms, prefix):
    return source.extract(Path(oot), Path(roms), prefix=prefix)


def actor_entries(data):
    out = []
    for command,count,pointer in actors.header(data,0,3):
        if command!=1: continue
        start = pointer & 0xffffff
        if start+count*16>len(data): raise ValueError('Truncated source actor list')
        for i in range(count):
            aid,x,y,z,rx,ry,rz,params = struct.unpack_from('>H6hH',data,start+i*16)
            out.append(dict(actor_id=aid&0xfff, spawn_flags=aid>>12, position=(x,y,z),
                            rotation=(rx,ry,rz), params=params, offset=start+i*16))
    return out


@lru_cache(maxsize=256)
def category(oot, name):
    folder = Path(oot)/'src/overlays/actors'/('ovl_'+name)
    for path in folder.glob('*.c'):
        found = re.search(r'(?:ActorProfile|ActorInit)\s+\w+\s*=\s*\{[^}]*?ACTORCAT_(\w+)',path.read_text(errors='replace'),re.S)
        if found: return found[1]
    return 'UNKNOWN'


def load_room(prefix, scene_index, room, project=PROJECT, paths=None, document=None):
    paths = paths or project_config.read_paths(project.parent)
    mesh_path = project/'build/generated'/f'S{scene_index}R{room}.MSH'
    result = dict(version=1, prefix=prefix, room=room, entities=[], faces=[], warnings=[],
                  mesh_source=str(mesh_path), metadata_source='Verified US 1.2 ROM; main header only')
    if document is None and mesh_path.is_file():
        vertices,faces = read_room(mesh_path)
        result['bounds'] = bounds(vertices)
        for obj in sorted({f['object'] for f in faces}):
            eid = f'{prefix}/room/{room}/mesh/{obj}'
            subset = [f for f in faces if f['object']==obj]
            result['entities'].append(dict(id=eid, label=f'Mesh object {obj}', kind='Mesh',
                bounds=bounds(p for f in subset for p in f['points']), details=dict(source=str(mesh_path), polygons=len(subset))))
            result['faces'].extend(dict(f, entity=eid, layer='Mesh') for f in subset)
    elif document is None:
        result['warnings'].append('No baked mesh: run Clean once. Showing original metadata/collision only.')
    try:
        segs = segments(str(paths['oot_decomp']),str(paths['oot_roms']),prefix)
        if document is not None:
            faces = original_mesh(prefix, room, segs, paths['oot_decomp'],document)
            box = bounds(p for f in faces for p in f['points'])
            result['bounds'] = box
            result['mesh_source'] = 'Original ROM display lists (main header)'
            for obj in sorted({f['object'] for f in faces}):
                eid=f'{prefix}/room/{room}/mesh/{obj}'
                subset=[f for f in faces if f['object']==obj]
                key=f'{prefix}_room_{room}/object/{obj}'
                replacement=document.get('meshes',{}).get(key)
                result['entities'].append(dict(id=eid,label=f'Mesh object {obj}'+(' (replaced)' if replacement else ''),kind='Mesh',
                    bounds=bounds(p for f in subset for p in f['points']),details=dict(source=result['mesh_source'],
                    polygons=len(subset),mesh_key=key,replacement=replacement,
                    code=[str(ROOT/'game/tools/build_hybrid_scene.py'),str(ROOT/'game/src/kokiri_sgl.c'),str(ROOT/'shared/tools/build_kokiri_scene.py')],
                    note='Room mesh objects are ROM display-list groups, not necessarily individual props.')))
                result['faces'].extend(dict(f,entity=eid,layer='Mesh') for f in subset)
            # Fail the selected variant load on stale/invalid edits, never show it as original.
            segs = layouts.apply(segs, document)
        scene = segs[prefix+'_scene']
        room_data = segs[f'{prefix}_room_{room}']
        raw_room = segments(str(paths['oot_decomp']),str(paths['oot_roms']),prefix)[f'{prefix}_room_{room}']
        import hashlib
        result['source_sha256'] = hashlib.sha256(raw_room).hexdigest()
        names = actors.table(Path(paths['oot_decomp'])/'include/tables/actor_table.h','DEFINE_ACTOR')
        for i,entry in enumerate(actor_entries(room_data)):
            name = names.get(entry['actor_id'], f"Actor 0x{entry['actor_id']:03X}")
            cat = category(str(paths['oot_decomp']),name)
            kind = 'Enemy' if cat in ('ENEMY','BOSS') else 'Actor'
            details = dict(entry, actor_name=name, category=cat,
                           note='Original placement marker; no behavior/model simulation or runtime-support claim.')
            details['editable'] = prefix=='spot04' and entry['actor_id'] in layouts.EDITABLE
            actor_folder=Path(paths['oot_decomp'])/'src/overlays/actors'/('ovl_'+name)
            details['code']=[str(p) for p in sorted(actor_folder.glob('*.c'))]
            details['code'].append(str(ROOT/'game/tools/build_actors.py'))
            runtime={0x125:['gameplay.c','kokiri_sgl.c'],0x141:['world_signs.c'],
                     0x00A:['gameplay.c'],0xC7:['karebaba.c','karebaba_draw.c']}
            details['code'] += [str(ROOT/'game/src'/p) for p in runtime.get(entry['actor_id'],[])]
            result['entities'].append(dict(id=f'{prefix}/room/{room}/actor/{i}',
                label=f'{name} [{i}]',kind=kind, position=entry['position'],details=details))
        collision = source.collision_surfaces(scene)
        collision_id = prefix+'/collision'
        result['entities'].append(dict(id=collision_id, label='Scene collision',kind='Collision',
            bounds=bounds(p for poly in collision for p in poly['vertices']),
            details=dict(polygons=len(collision),scope='Whole scene, not just selected room')))
        result['faces'].extend(dict(points=p['vertices'],colour=(65,190,220),entity=collision_id,layer='Collision') for p in collision)
        exits = source.exit_list(scene,max((p['exit'] for p in collision),default=0))
        entrance_names = scenes.entrance_table(Path(paths['oot_decomp']))
        for slot in sorted({p['exit'] for p in collision if p['exit']}):
            triangles = [p['vertices'] for p in collision if p['exit']==slot]
            eid = f'{prefix}/exit/{slot}'
            entrance = exits[slot-1]
            result['entities'].append(dict(id=eid,label=f'Exit {slot} -> 0x{entrance:04X}',kind='Exit',
                bounds=bounds(p for tri in triangles for p in tri), details=dict(exit_index=slot,
                entrance=entrance,target=entrance_names.get(entrance,'Unknown'),scope='Scene exit collision surfaces')))
            result['faces'].extend(dict(points=tri,colour=(255,175,55),entity=eid,layer='Exit') for tri in triangles)
        for i,spawn in enumerate(source.spawn_points(scene)):
            result['entities'].append(dict(id=f'{prefix}/spawn/{i}',label=f'Player spawn {i}',kind='Spawn',
                position=(spawn['x'],spawn['y'],spawn['z']),details=dict(spawn,scope='Scene spawn, room association not inferred')))
        for command,count,pointer in actors.header(scene,0,2):
            if command!=0x0e: continue
            for i in range(count):
                front,fc,back,bc,aid,x,y,z,yaw,params = struct.unpack_from('>4b5hH',scene,(pointer&0xffffff)+i*16)
                if room not in (front,back): continue
                result['entities'].append(dict(id=f'{prefix}/transition/{i}',label=f'Transition {front} -> {back}',
                    kind='Transition',position=(x,y,z),details=dict(actor_id=aid,params=params,yaw=yaw,
                    front_room=front,back_room=back,front_camera=fc,back_camera=bc,
                    note='Transition actor marker; exact trigger volume not inferred.')))
        if 'bounds' not in result: result['bounds'] = bounds(p for poly in collision for p in poly['vertices'])
    except (OSError, ValueError, KeyError, AssertionError, struct.error) as exc:
        if document is not None: raise ValueError('Original/alternate load failed: '+str(exc)) from exc
        result['warnings'].append('Original metadata unavailable: '+str(exc)+'. Check launcher Config paths.')
    result.setdefault('bounds',((-100,-100,-100),(100,100,100)))
    for entity in result['entities']:
        entity['details']['original_label']=entity['label']
        if document is not None: entity['label']=document.get('labels',{}).get(entity['id'],entity['label'])
    return result
