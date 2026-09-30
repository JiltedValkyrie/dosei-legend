"""Per-object ROM mesh replacements, shared by Map Workshop and the baker."""
import hashlib
import json
import math
import re
from pathlib import Path
import shutil
import sys
import tempfile
from PIL import Image

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(GAME.parent/'shared/tools'))
import build_kokiri_scene as source
import build_authored_scene as authored


def fingerprint(folder):
    return hashlib.sha256(b''.join(p.name.encode()+b'\0'+p.read_bytes()
                         for p in sorted(Path(folder).iterdir()) if p.is_file() and p.name!='mesh.json')).hexdigest()


def bundle_path(identity, game=GAME):
    import re
    if not isinstance(identity,str) or not re.fullmatch('[0-9a-f]{64}',identity):
        raise ValueError('Invalid mesh bundle identity')
    folder = Path(game)/'assets/layouts/meshes'/identity
    if not folder.is_dir() or fingerprint(folder)!=identity:
        raise ValueError('Missing or changed mesh bundle: '+identity)
    return folder


def store(obj, game=GAME, confirm_split=None):
    """Normalize references, then copy an immutable bundle before saving any layout."""
    sys.path.insert(0,str(GAME.parent/'tools/mesh-workshop'))
    from mesh_assets import import_obj, parse_obj
    obj = Path(obj).resolve()
    if confirm_split is not None:
        diagnostics={}
        parse_obj(obj,split_incompatible=True,diagnostics=diagnostics,
                  require_quads=False,require_flags=False,allow_tiled_uv=True)
        if diagnostics['split_quads'] and not confirm_split(diagnostics):
            return None
    with tempfile.TemporaryDirectory() as temp:
        normalized = import_obj(dict(id='map',source=str(obj)),obj,Path(game),Path(temp),
                                split_incompatible=True,require_quads=False,require_flags=False,allow_tiled_uv=True)
        metadata=read_material_metadata(obj)
        (normalized/'materials.json').write_text(json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
        material_file=normalized/'mesh.mtl'
        material_file.write_text('# dosei_materials: materials.json\n'+material_file.read_text(encoding='utf-8'),encoding='utf-8')
        identity = fingerprint(normalized)
        destination = Path(game)/'assets/layouts/meshes'/identity
        if not destination.exists():
            destination.parent.mkdir(parents=True,exist_ok=True)
            # A failed copy cannot publish a partial content-addressed directory.
            with tempfile.TemporaryDirectory(dir=destination.parent) as stage:
                staged = Path(stage)/'bundle'
                shutil.copytree(normalized,staged,ignore=shutil.ignore_patterns('mesh.json'))
                staged.replace(destination)
        bundle_path(identity,game)
    return identity


def transform(point, entry):
    yaw = math.radians(entry['yaw'])
    x,y,z = (v*entry['scale'] for v in point)
    position = entry['position']
    return (x*math.cos(yaw)+z*math.sin(yaw)+position[0],y+position[1],
            -x*math.sin(yaw)+z*math.cos(yaw)+position[2])


def replacement_faces(entry, room, obj, game=GAME):
    folder = bundle_path(entry['bundle'],game)
    positions,uvs,faces,mtl = authored.parse_obj(folder/'mesh.obj')
    materials = authored.parse_mtl(folder/mtl)
    metadata=json.loads((folder/'materials.json').read_text(encoding='utf-8')) if (folder/'materials.json').exists() else None
    if metadata is not None: validate_material_metadata(metadata)
    textures = {}
    for material,filename in materials.items():
        path = (folder/filename).resolve()
        if not path.is_relative_to(folder.resolve()): raise ValueError('Texture escapes mesh bundle')
        with Image.open(path) as image:
            image = image.convert('RGBA')
            textures[material] = dict(width=image.width,height=image.height,colors=list(image.getdata()),
                scale=(1,1),shifts=0,shiftt=0,uls=0,ult=0,cms=2,cmt=2,masks=0,maskt=0,
                address=0,material=material,file=str(path))
            if metadata is not None:
                settings=metadata['materials'].get(material,default_material(material))
                textures[material].update({k:settings[k] for k in ('cms','cmt','masks','maskt')})
    result=[]
    for face in faces:
        tex = textures[face['material']]
        flags=int(face['material'][-1]) if face['material'] in ('flags_0','flags_1','flags_2','flags_3') else 0
        settings=metadata['materials'].get(face['material'],default_material(face['material'])) if metadata else None
        if settings: flags=settings['flags']
        for corners in authored.triangulate(face,positions):
            # Hybrid converter consumes triangles and rejoins compatible pairs.
            triangles = [corners[:3]] if len(corners)==3 else [corners[:3],[corners[0],corners[2],corners[3]]]
            for tri in triangles:
                vertices=[]
                for vertex,uv in tri:
                    point=transform(positions[vertex],entry)
                    if any(not math.isfinite(v) or abs(v)>32767 for v in point):
                        raise ValueError('Placed mesh exceeds signed 16-bit world coordinates')
                    u,v=uvs[uv]
                    vertices.append((*point,u*(tex['width'] if metadata else tex['width']-1),(1-v)*(tex['height'] if metadata else tex['height']-1),255,255,255,255))
                result.append(dict(vertices=vertices,texture=tex,lighting=False,prim=tuple(settings['prim']) if settings else (255,255,255,255),
                    transparent=bool(flags&1),cull=bool(flags&2),room=room,object=obj,authored_mesh=True))
    return result


def apply_faces(faces, segments, document, game=GAME):
    replacements=document.get('meshes',{}) if document else {}
    result=list(faces)
    for key,entry in replacements.items():
        room,_,index=key.partition('/object/')
        if room not in segments: continue
        if hashlib.sha256(segments[room]).hexdigest()!=entry['sha256']:
            raise ValueError('Mesh source room changed: '+room)
        obj=int(index)
        original=[f for f in result if f['room']==room and f['object']==obj]
        if not original:
            raise ValueError('Original mesh object not found: '+key)
        result=[f for f in result if not (f['room']==room and f['object']==obj)]
        if entry['bundle']=='original':
            points=[v for f in original for v in f['vertices']]
            pivot=[(min(p[k] for p in points)+max(p[k] for p in points))/2 for k in range(3)]
            for face in original:
                vertices=[(*transform(tuple(v[k]-pivot[k] for k in range(3)),entry),*v[3:]) for v in face['vertices']]
                if any(abs(v)>32767 for p in vertices for v in p[:3]): raise ValueError('Placed mesh exceeds world bounds')
                result.append(dict(face,vertices=vertices))
        else: result.extend(replacement_faces(entry,room,obj,game))
    return result


def triangle_image(face, size=32):
    """Triangle UV patch for host/export; same source UV addressing as the baker."""
    tex=face['texture']; vertices=face['vertices']; pixels=[]
    for y in range(size):
        v=y/(size-1)
        for x in range(size):
            u=x/(size-1); weights=(1-u-v,u,v)
            if u+v>1.001: pixels.append((0,0,0,0)); continue
            if tex:
                uv=[sum(w*p[3+k] for w,p in zip(weights,vertices)) for k in (0,1)]
                s=source.coordinate(uv[0],tex['scale'][0],tex['shifts'],tex['uls'],tex['cms'],tex['masks'],tex['width'])
                t=source.coordinate(uv[1],tex['scale'][1],tex['shiftt'],tex['ult'],tex['cmt'],tex['maskt'],tex['height'])
                colour=tex['colors'][t*tex['width']+s]
            else: colour=(255,255,255,255)
            pixels.append(tuple(round(colour[k]*face['prim'][k]/255) for k in range(4)))
    image=Image.new('RGBA',(size,size)); image.putdata(pixels)
    return image


def default_material(name=''):
    flags=int(name[-1]) if name in ('flags_0','flags_1','flags_2','flags_3') else 0
    return dict(cms=0,cmt=0,masks=0,maskt=0,prim=[255,255,255,255],flags=flags)


def validate_material_metadata(data):
    if not isinstance(data,dict) or set(data)!={'version','materials'} or data['version']!=1 or not isinstance(data['materials'],dict):
        raise ValueError('Invalid material sampler metadata')
    for name,settings in data['materials'].items():
        if not isinstance(name,str) or not isinstance(settings,dict) or set(settings)!=set(default_material()):
            raise ValueError('Invalid material settings')
        for key,limit in (('cms',3),('cmt',3),('masks',15),('maskt',15),('flags',3)):
            if type(settings[key]) is not int or not 0<=settings[key]<=limit: raise ValueError('Invalid material '+key)
        if not isinstance(settings['prim'],(list,tuple)) or len(settings['prim'])!=4 or any(type(v) is not int or not 0<=v<=255 for v in settings['prim']):
            raise ValueError('Invalid primitive tint')
    return data


def read_material_metadata(obj):
    obj=Path(obj)
    candidates=[obj.with_suffix('.materials.json')]
    material_names=[]
    bindings={}
    material_folders={obj.parent}
    for line in obj.read_text(encoding='utf-8-sig').splitlines():
        if line.startswith('usemtl '): material_names.append(line[7:].strip())
        if line.startswith('mtllib '):
            mtl=obj.parent/line[7:].strip()
            material_folders.add(mtl.parent)
            bindings.update({name:(mtl.parent/filename).resolve() for name,filename in authored.parse_mtl(mtl).items()})
            for text in mtl.read_text(encoding='utf-8-sig').splitlines():
                if text.startswith('# dosei_materials: '): candidates.append(mtl.parent/text.split(': ',1)[1])
    for path in candidates:
        if path.is_file():
            data=validate_material_metadata(json.loads(path.read_text(encoding='utf-8')))
            if any(name.startswith('dosei_') and name not in data['materials'] for name in material_names):
                raise ValueError('Exported material missing from sampler sidecar')
            return data
    required={name for name in material_names if name.startswith('dosei_')}
    if required:
        image_keys={}
        def image_key(path):
            if path not in image_keys:
                try:
                    with Image.open(path) as image:
                        rgba=image.convert('RGBA')
                        image_keys[path]=(rgba.size,hashlib.sha256(rgba.tobytes()).digest())
                except (OSError,ValueError):
                    image_keys[path]=None
            return image_keys[path]

        # Blender rewrites MTL and drops custom comments. Recover only through
        # an original MTL with matching image pixels and material names. Blender
        # duplicate suffixes and renamed image copies must not lose samplers.
        matches=[]
        for folder in material_folders:
            for original_mtl in folder.glob('*.mtl'):
                original_bindings={name:(original_mtl.parent/filename).resolve()
                                   for name,filename in authored.parse_mtl(original_mtl).items()}
                aliases={}
                for name in required:
                    original_name=name if name in original_bindings else re.sub(r'\.\d{3,}$','',name)
                    if name not in bindings or original_name not in original_bindings: break
                    key=image_key(bindings[name])
                    if key is None or key!=image_key(original_bindings[original_name]): break
                    aliases[name]=original_name
                if len(aliases)!=len(required): continue
                for text in original_mtl.read_text(encoding='utf-8-sig').splitlines():
                    if not text.startswith('# dosei_materials: '): continue
                    path=original_mtl.parent/text.split(': ',1)[1]
                    if not path.is_file(): continue
                    data=validate_material_metadata(json.loads(path.read_text(encoding='utf-8')))
                    if set(aliases.values())<=data['materials'].keys():
                        matches.append({name:data['materials'][original_name] for name,original_name in aliases.items()})
        if matches and all(match==matches[0] for match in matches):
            return dict(version=1,materials=matches[0])
        if matches: raise ValueError('Conflicting sampler metadata matches these materials/textures. Supply an explicit same-name .materials.json for this OBJ.')
        raise ValueError('Keep the original exported MTL, PNGs and .materials.json together, or copy the sampler JSON beside this OBJ with the same filename stem.')
    return dict(version=1,materials={name:default_material(name) for name in material_names})


def export_faces(faces, destination, pivot=(0,0,0)):
    """Export editable source images and normalized source UVs; never triangle tiles."""
    destination=Path(destination)
    obj=destination if destination.suffix.lower()=='.obj' else destination/'mesh.obj'
    if any(c in obj.stem for c in '#\r\n\t'): raise ValueError('OBJ name cannot contain # or control characters')
    if not faces: raise ValueError('Selected mesh has no source triangles')
    obj.parent.mkdir(parents=True,exist_ok=True)
    mtl=obj.with_suffix('.mtl'); sidecar=obj.with_suffix('.materials.json')
    lines=['# Native Y-up, local coordinates. UVs retain tiling outside 0..1.',f'mtllib {mtl.name}',f'o {obj.stem}']
    material_lines=['# dosei_materials: '+sidecar.name]
    metadata=dict(version=1,materials={})
    images={}; materials={}
    for i,face in enumerate(faces):
        tex=face['texture']
        size=(tex['width'],tex['height']) if tex else (1,1)
        image=Image.new('RGBA',size)
        image.putdata(tex['colors'] if tex else [(255,255,255,255)])
        identity=hashlib.sha256(str(size).encode()+image.tobytes()).hexdigest()
        if identity not in images:
            name=f'{obj.stem}_texture_{identity[:16]}.png'
            image.save(obj.parent/name); images[identity]=name
        settings=default_material()
        if tex: settings.update({k:tex[k] for k in ('cms','cmt','masks','maskt')})
        settings['prim']=list(face['prim'])
        settings['flags']=int(bool(face.get('transparent')))|int(bool(face.get('cull')))*2
        material_key=identity+json.dumps(settings,sort_keys=True)
        if material_key not in materials:
            name=f'dosei_{len(materials):03d}'
            materials[material_key]=name; metadata['materials'][name]=settings
            material_lines += ['newmtl '+name,'Kd '+' '.join(str(v/255) for v in settings['prim'][:3]),'map_Kd '+images[identity],'']
        for p in face['vertices']: lines.append('v '+' '.join(format(p[k]-pivot[k],'.17g') for k in range(3)))
        for p in face['vertices']:
            if tex:
                # Absorb N64 scale/shift/tile origin into continuous UVs, but keep
                # repeat/mirror/clamp and mask periods in the material sidecar.
                uv=[p[3+k]*tex['scale'][k]*2**(-tex[shift] if tex[shift]<=10 else 16-tex[shift])-tex[origin]/4
                    for k,shift,origin in ((0,'shifts','uls'),(1,'shiftt','ult'))]
                u,v=uv[0]/size[0],1-uv[1]/size[1]
            else: u,v=0.5,0.5
            lines.append(f'vt {u:.17g} {v:.17g}')
        lines.append('usemtl '+materials[material_key])
        lines.append('f '+' '.join(f'{i*3+j}/{i*3+j}' for j in (1,2,3)))
    obj.write_text('\n'.join(lines)+'\n',encoding='utf-8')
    mtl.write_text('\n'.join(material_lines)+'\n',encoding='utf-8')
    sidecar.write_text(json.dumps(validate_material_metadata(metadata),indent=2)+'\n',encoding='utf-8')
    return obj


def check_room(document,prefix,room,oot,roms,game=GAME):
    """Run the production room UV converter and capacity checks into temporary files."""
    from build_sgl_scene import read_scene, collect_tiles
    import build_hybrid_scene as hybrid
    data,head,vertices,faces=read_scene(Path(game)/'build/generated/LINK.BIN')
    tiles=collect_tiles(data,head,faces)
    actor=dict(tiles=[(t['width'],t['height']) for t in tiles.values()],
               polygons=len(faces),vertices=len(vertices))
    with tempfile.TemporaryDirectory() as temp:
        hybrid.convert(Path(oot),{},actor,Path(temp),rom_dir=Path(roms),
                       room=f'{prefix}_room_{room}',prefix=prefix,layout=document)
        return json.loads((Path(temp)/'texture_manifest.json').read_text())
