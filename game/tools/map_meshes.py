"""Per-object ROM mesh replacements, shared by Map Workshop and the baker."""
import hashlib
import json
import math
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


def store(obj, game=GAME):
    """Normalize references, then copy an immutable bundle before saving any layout."""
    sys.path.insert(0,str(GAME.parent/'tools/mesh-workshop'))
    from mesh_assets import import_obj
    obj = Path(obj).resolve()
    with tempfile.TemporaryDirectory() as temp:
        normalized = import_obj(dict(id='map',source=str(obj)),obj,Path(game),Path(temp),
                                split_incompatible=True,require_quads=False,require_flags=False)
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
    textures = {}
    for material,filename in materials.items():
        path = (folder/filename).resolve()
        if not path.is_relative_to(folder.resolve()): raise ValueError('Texture escapes mesh bundle')
        with Image.open(path) as image:
            image = image.convert('RGBA')
            textures[material] = dict(width=image.width,height=image.height,colors=list(image.getdata()),
                scale=(1,1),shifts=0,shiftt=0,uls=0,ult=0,cms=2,cmt=2,masks=0,maskt=0,
                address=0,material=material,file=str(path))
    result=[]
    for face in faces:
        tex = textures[face['material']]
        flags=int(face['material'][-1]) if face['material'] in ('flags_0','flags_1','flags_2','flags_3') else 0
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
                    vertices.append((*point,u*(tex['width']-1),(1-v)*(tex['height']-1),255,255,255,255))
                result.append(dict(vertices=vertices,texture=tex,lighting=False,prim=(255,255,255,255),
                    transparent=bool(flags&1),cull=bool(flags&2),room=room,object=obj))
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


def export_faces(faces, folder, pivot=(0,0,0)):
    """Export a selected object in local coordinates with its own UV atlas."""
    folder=Path(folder); folder.mkdir(parents=True,exist_ok=True)
    if not faces: raise ValueError('Selected mesh has no source triangles')
    cell=34; side=math.ceil(math.sqrt(len(faces)))
    atlas=Image.new('RGBA',(side*cell,side*cell))
    lines=['# Native Y-up units; local coordinates around selected pivot.','mtllib mesh.mtl']
    for i,face in enumerate(faces):
        x,y=(i%side)*cell+1,(i//side)*cell+1
        atlas.paste(triangle_image(face),(x,y))
        for p in face['vertices']: lines.append('v '+' '.join(str(p[k]-pivot[k]) for k in range(3)))
        for u,v in ((0,0),(31,0),(0,31)):
            lines.append(f'vt {(x+u+.5)/atlas.width} {1-(y+v+.5)/atlas.height}')
        flags=int(bool(face.get('transparent')))|int(bool(face.get('cull')))*2
        lines.append(f'usemtl flags_{flags}')
        lines.append('f '+' '.join(f'{i*3+j}/{i*3+j}' for j in (1,2,3)))
    (folder/'mesh.obj').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    (folder/'mesh.mtl').write_text(''.join(f'newmtl flags_{i}\nKd 1 1 1\nmap_Kd atlas.png\n' for i in range(4)),encoding='utf-8')
    atlas.save(folder/'atlas.png')
    return folder/'mesh.obj'


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
