"""Tracked, ROM-relative layout variants. Source ROM bytes are never modified."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import struct
import tempfile

GAME = Path(__file__).resolve().parents[1]
ORIGINAL = 'original'
# First proven placement path: these tables are emitted by build_actors.py.
EDITABLE = {0x125, 0x141, 0x00A}  # grass, signposts, chests


# Mesh keys for per-object replacement/LOD. spot00 = Hyrule Field.
MESH_KEY = r'(spot04_room_[0-2]|ydan_room_0|spot00_room_0)/object/(0|[1-9][0-9]*)'
# Runtime stores distances as unsigned 16-bit; keep below signed range too.
LOD_DISTANCE_MAX = 32767


def directory(game=GAME): return Path(game)/'assets/layouts'


def slug(name):
    if not isinstance(name, str) or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,47}', name):
        raise ValueError('Name needs 1-48 lowercase letters, numbers, hyphens or underscores')
    return name


def empty(): return {'version': 1, 'base': 'ntsc-1.2', 'rooms': {}}


def validate(document):
    if not isinstance(document, dict) or not {'version','base','rooms'} <= set(document) or set(document)-{'version','base','rooms','meshes','labels','lods'}:
        raise ValueError('Invalid layout document fields')
    if document['version'] != 1 or document['base'] != 'ntsc-1.2' or not isinstance(document['rooms'], dict):
        raise ValueError('Unsupported layout version/base')
    for room, record in document['rooms'].items():
        if not re.fullmatch(r'spot04_room_[0-2]', room):
            raise ValueError('Only Kokiri Forest placement edits are supported: '+room)
        if not isinstance(record, dict) or set(record) != {'sha256', 'actors'}:
            raise ValueError('Invalid room override')
        if not re.fullmatch('[0-9a-f]{64}', record['sha256']) or not isinstance(record['actors'], dict):
            raise ValueError('Invalid room fingerprint/actors')
        for index, actor in record['actors'].items():
            if not re.fullmatch(r'0|[1-9][0-9]*', index) or int(index)>255:
                raise ValueError('Invalid source actor index')
            if not isinstance(actor, dict) or set(actor) != {'actor_id', 'position', 'yaw'}:
                raise ValueError('Only position and yaw edits are supported')
            if actor['actor_id'] not in EDITABLE:
                raise ValueError('Actor has no supported editable bake path')
            if not isinstance(actor['position'], (list, tuple)) or len(actor['position']) != 3:
                raise ValueError('Position requires XYZ')
            if any(type(v) is not int or not -32768 <= v <= 32767 for v in [*actor['position'], actor['yaw']]):
                raise ValueError('XYZ and yaw must be signed 16-bit integers')
    labels=document.get('labels',{})
    if not isinstance(labels,dict): raise ValueError('Invalid Outliner names')
    for key,name in labels.items():
        if not isinstance(key,str) or not re.fullmatch(r'(spot04|spot00|ydan)/room/[0-9]+/(mesh|actor)/[0-9]+',key):
            raise ValueError('Invalid named object ID')
        if not isinstance(name,str) or not name.strip() or len(name)>96 or not name.isprintable():
            raise ValueError('Object name must be 1-96 printable characters')
    meshes=document.get('meshes',{})
    if not isinstance(meshes,dict): raise ValueError('Invalid mesh mapping')
    for key,entry in meshes.items():
        if not re.fullmatch(MESH_KEY,key):
            raise ValueError('Invalid mesh object key')
        if not isinstance(entry,dict) or set(entry)!={'sha256','bundle','position','yaw','scale'}:
            raise ValueError('Invalid mesh replacement fields')
        if not isinstance(entry['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',entry['sha256']) or (entry['bundle']!='original' and (not isinstance(entry['bundle'],str) or not re.fullmatch('[0-9a-f]{64}',entry['bundle']))):
            raise ValueError('Invalid mesh fingerprint')
        if not isinstance(entry['position'],(list,tuple)) or len(entry['position'])!=3:
            raise ValueError('Mesh position needs XYZ')
        if any(type(v) not in (int,float) or not math.isfinite(v) for v in [*entry['position'],entry['yaw'],entry['scale']]):
            raise ValueError('Mesh transform must be finite numbers')
        if not 0.001<=entry['scale']<=1000 or any(abs(v)>32767 for v in entry['position']):
            raise ValueError('Mesh transform outside supported range')
    lods=document.get('lods',{})
    if not isinstance(lods,dict): raise ValueError('Invalid LOD mapping')
    for key,entry in lods.items():
        if not isinstance(key,str) or not re.fullmatch(MESH_KEY,key):
            raise ValueError('Invalid LOD mesh key')
        if not isinstance(entry,dict) or set(entry)!={'sha256','bundle','position','lod0_distance','cull_distance'}:
            raise ValueError('Invalid LOD fields')
        if not isinstance(entry['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',entry['sha256']):
            raise ValueError('Invalid LOD fingerprint')
        if entry['bundle'] is not None and (not isinstance(entry['bundle'],str) or not re.fullmatch('[0-9a-f]{64}',entry['bundle'])):
            raise ValueError('Invalid LOD0 bundle')
        if not isinstance(entry['position'],(list,tuple)) or len(entry['position'])!=3 or            any(type(v) not in (int,float) or not math.isfinite(v) or abs(v)>32767 for v in entry['position']):
            raise ValueError('LOD0 position needs finite XYZ inside world bounds')
        near,far=entry['lod0_distance'],entry['cull_distance']
        if type(near) is not int or type(far) is not int or not 0<=near<=LOD_DISTANCE_MAX or not 1<=far<=LOD_DISTANCE_MAX:
            raise ValueError('LOD distances must be integers 0..%d (cull at least 1)' % LOD_DISTANCE_MAX)
        if near>far: raise ValueError('LOD0 distance cannot exceed cull distance')
    return document


def atomic_json(path, document):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix='.'+path.name, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(document, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary): os.unlink(temporary)


def names(game=GAME):
    return sorted(p.stem for p in (directory(game)/'variants').glob('*.json'))


def load(name, game=GAME):
    if name == ORIGINAL: return empty()
    return validate(json.loads((directory(game)/'variants'/(slug(name)+'.json')).read_text(encoding='utf-8')))


def save(name, document, game=GAME):
    if name == ORIGINAL: raise ValueError('Original ROM is immutable; use another name')
    atomic_json(directory(game)/'variants'/(slug(name)+'.json'), validate(document))


def selection(game=GAME):
    path = directory(game)/'selection.json'
    if not path.exists(): return None  # existing Workshop mesh publishing remains compatible
    value = json.loads(path.read_text(encoding='utf-8'))
    if set(value) != {'version', 'layout'} or value['version'] != 1: raise ValueError('Invalid layout selection')
    return None if value['layout'] is None else slug(value['layout'])


def choose(name, game=GAME):
    if name is not None: load(name, game)
    atomic_json(directory(game)/'selection.json', {'version':1, 'layout':name})


def build_document(game=GAME):
    snapshot = os.environ.get('DOSEI_LAYOUT_SNAPSHOT')
    if snapshot:
        data = json.loads(Path(snapshot).read_text(encoding='utf-8'))
        return None if data['layout'] is None else validate(data['document'])
    name = selection(game)
    return None if name is None else load(name, game)


def actor_list(data):
    for offset in range(0, min(len(data), 0x400), 8):
        if data[offset] == 0x14: return None
        if data[offset] == 1:
            count = data[offset+1]
            base = struct.unpack_from('>I', data, offset+4)[0] & 0xffffff
            if base+count*16 > len(data): raise ValueError('Truncated actor list')
            return base, count
    return None


def apply(segments, document):
    """Copy only edited room bytes; preserve original flags/params/other headers."""
    validate(document)
    result = dict(segments)
    for name, record in document['rooms'].items():
        if name not in segments: continue
        original = segments[name]
        if hashlib.sha256(original).hexdigest() != record['sha256']:
            raise ValueError('Original ROM room changed; rebase variant: '+name)
        info = actor_list(original)
        if not info: raise ValueError('Room has no main actor list: '+name)
        base, count = info
        changed = bytearray(original)
        for index, actor in record['actors'].items():
            if int(index) >= count: raise ValueError('Actor index outside original list')
            offset = base+int(index)*16
            aid = struct.unpack_from('>H', original, offset)[0] & 0xfff
            if aid != actor['actor_id']: raise ValueError('Actor identity mismatch')
            if aid == 0x125 and actor['yaw'] != struct.unpack_from('>h',original,offset+10)[0]:
                raise ValueError('Grass runtime does not use source yaw; only position edits are supported')
            struct.pack_into('>3h', changed, offset+2, *actor['position'])
            struct.pack_into('>h', changed, offset+10, actor['yaw'])
        result[name] = bytes(changed)
    return result


def for_build(segments):
    document = build_document()
    return segments if document is None else apply(segments, document)


def validate_environment(document):
    if any(os.environ.get(k) not in (None,'','none') for k in ('ROOM_IMPORTS','QUAD_OBJ','AUTHORED_OBJ')):
        raise ValueError('Named layout conflicts with legacy mesh overrides; clear override environment variables')
    if (document.get('meshes') or document.get('lods')) and (os.environ.get('TEXTURE_PATH','hybrid')!='hybrid' or os.environ.get('STREAM_ROOMS','1')!='1'):
        raise ValueError('Per-object mesh layouts require TEXTURE_PATH=hybrid and STREAM_ROOMS=1')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--rom-dir', type=Path, required=True)
    args = parser.parse_args()
    name = selection()
    document = None if name is None else load(name)
    if name is not None:
        validate_environment(document)
        import sys
        sys.path.insert(0, str(GAME.parent/'shared/tools'))
        import build_kokiri_scene as source
        prefixes={'spot04'} if document['rooms'] else set()
        prefixes.update(k.split('_room_')[0] for k in [*document.get('meshes',{}),*document.get('lods',{})])
        for prefix in prefixes:
            original = source.extract(args.oot,args.rom_dir,prefix=prefix)
            apply(original, document)
        for entry in document.get('meshes',{}).values():
            from map_meshes import bundle_path
            if entry['bundle']!='original': bundle_path(entry['bundle'])
        for entry in document.get('lods',{}).values():
            from map_meshes import bundle_path
            if entry['bundle'] is not None: bundle_path(entry['bundle'])
    atomic_json(args.snapshot, {'layout':name, 'document':document})
    print('Layout build source:', name or 'legacy Workshop selection')


if __name__ == '__main__': main()
