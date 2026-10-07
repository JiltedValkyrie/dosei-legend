"""Local project asset inventory and verified mesh publication history."""
import hashlib
import json
import shutil
from pathlib import Path

from mesh_assets import PROJECT, read_mesh


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify(path, magic):
    ext = path.suffix.lower()
    # Link exports (game/tools/export_link_workshop.py): one type per age so
    # the type filter finds every body/sword/shield/boot/tool mesh at once.
    parts = [p.casefold() for p in path.parts]
    if ext == '.obj' and 'meshes' in parts and 'link' in parts:
        age = parts[parts.index('link') + 1] if parts.index('link') + 1 < len(parts) else ''
        if age in ('child', 'adult'):
            return f'Link ({age.title()})'
    if magic == b'KFR1': return 'Mesh'
    if magic == b'KRM1' or ext == '.msh': return 'Room mesh'
    if ext in ('.obj', '.fbx', '.gltf', '.glb', '.dae'): return 'Mesh'
    if ext in ('.anm', '.trk'): return 'Animation'
    if ext in ('.png', '.tga', '.jpg', '.jpeg', '.bmp', '.tex'): return 'Texture'
    if ext in ('.pcm', '.lvl', '.wav', '.aiff', '.ogg', '.seq'): return 'Audio'
    if ext == '.raw': return 'Audio' if 'audio' in path.parts or 'LEVELS' in path.name or 'PCM' in path.name else 'Raw data'
    if ext == '.mtl': return 'Material'
    if ext in ('.col', '.map'): return 'Collision / map'
    if ext in ('.json', '.xml'): return 'Metadata'
    if ext in ('.h', '.c'): return 'Generated data'
    return 'Other'


def catalog(project=PROJECT):
    project = Path(project).resolve()
    repo = project.parent
    roots = [(project / 'assets', 'Source'), (project / 'levels', 'Source'),
             (repo / 'shared/assets', 'Shared'), (project / 'build/generated', 'Generated'),
             (project / 'build/cd', 'Staged'), (repo / 'workspace/meshes', 'Workspace'),
             (project / 'build', 'CD audio')]
    config = project / 'assets/room_imports.json'
    overrides = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
    published = {}
    for room, entry in overrides.items():
        obj = (config.parent / entry['obj']).resolve()
        record = entry.get('publication', {})
        state = 'Assigned' if obj.is_file() else 'Missing'
        if record.get('files'):
            state = 'Published'
            for name, expected in record['files'].items():
                path = obj.parent / name
                if not path.is_file(): state = 'Missing'; break
                if sha(path) != expected: state = 'Modified'
        installed = set([obj.parent / n for n in record.get('files', {})] or [obj])
        related = set(installed)
        if record.get('source'):
            related.add((repo / record['source']).resolve())
        for path in related:
            item_state = state
            if path not in installed and record.get('source') and path == (repo / record['source']).resolve() and path.is_file():
                if sha(path) != record.get('source_sha256'): item_state = 'Modified'
            published.setdefault(path, []).append(dict(room=room, state=item_state,
                published_at=record.get('published_at', '')))
    entries, seen = [], set()
    for root, origin in roots:
        paths = root.glob('TRACK[0-9][0-9].BIN') if origin == 'CD audio' else root.rglob('*')
        for path in sorted(paths):
            if not path.is_file() or path.suffix in ('.pyc', '.tmp') or '__pycache__' in path.parts:
                continue
            path = path.resolve()
            if path in seen: continue
            seen.add(path)
            with path.open('rb') as stream: magic = stream.read(4)
            relative = path.relative_to(repo).as_posix()
            row = dict(id=hashlib.sha256(relative.encode()).hexdigest()[:16], name=path.name,
                       source=relative, path=path, type='Audio' if origin == 'CD audio' else classify(path, magic), origin=origin,
                       size=path.stat().st_size, vertices='', triangles='', error='',
                       exportable=magic == b'KFR1', publication='Staged' if origin in ('Staged', 'CD audio') else 'Not published',
                       published_at='', targets='')
            if magic == b'KFR1':
                try:
                    _, _, vertices, faces = read_mesh(path)
                    row.update(vertices=len(vertices), triangles=len(faces))
                except ValueError as exc:
                    row.update(error=str(exc), exportable=False)
            states = published.get(path, [])
            if not states and row['publication'] != 'Staged' and row['type'] not in ('Mesh', 'Room mesh', 'Texture', 'Material'):
                row['publication'] = 'Not tracked'
            if states:
                row['publication'] = max((s['state'] for s in states), key=lambda s: {'Assigned':0,'Published':1,'Modified':2,'Missing':3}[s])
                row['published_at'] = max(s['published_at'] for s in states)
                row['targets'] = ', '.join(sorted(s['room'] for s in states))
            entries.append(row)
    # Keep missing active overrides visible rather than silently dropping them.
    for path, states in published.items():
        if path in seen or path.is_file(): continue
        relative = path.relative_to(repo).as_posix() if path.is_relative_to(repo) else path.name
        entries.append(dict(id=hashlib.sha256(relative.encode()).hexdigest()[:16], name=path.name,
            source=relative, path=path, type=classify(path, b''), origin='Missing', size=0,
            vertices='', triangles='', error='Published file missing', exportable=False,
            publication='Missing', published_at=max(s['published_at'] for s in states),
            targets=', '.join(sorted(s['room'] for s in states))))
    return entries


def obj_file(entry):
    path = entry.get('path')
    return bool(path and Path(path).suffix.lower() == '.obj' and Path(path).is_file())


def can_export(entry):
    return bool(entry.get('exportable') or obj_file(entry))


def can_replace(entry):
    return obj_file(entry) and entry.get('origin') in ('Workspace', 'Source', 'Shared')


def mesh_bundle(obj_path):
    """OBJ plus the MTL, diffuse images, and same-stem JSON sidecars beside it."""
    obj_path = Path(obj_path)
    files = [obj_path]
    mtls = []
    for line in obj_path.read_text(encoding='utf-8', errors='replace').splitlines():
        if line.lower().startswith('mtllib '):
            for name in line.split()[1:]:
                mtl = (obj_path.parent / name).resolve()
                if mtl.is_file() and obj_path.parent.resolve() in mtl.parents:
                    mtls.append(mtl)
    files.extend(mtls)
    for mtl in mtls:
        for line in mtl.read_text(encoding='utf-8', errors='replace').splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0].lower() == 'map_kd':
                image = (mtl.parent / parts[-1]).resolve()
                if image.is_file() and mtl.parent.resolve() in image.parents:
                    files.append(image)
    for extra in obj_path.parent.glob(obj_path.stem + '*.json'):
        if extra.is_file():
            files.append(extra.resolve())
    unique = []
    seen = set()
    for path in files:
        path = path.resolve()
        if path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def copy_mesh_bundle(src, dest):
    """Copy an OBJ bundle to dest. Sidecars keep their names beside the new OBJ."""
    src, dest = Path(src), Path(dest)
    if src.resolve() == dest.resolve():
        raise ValueError('Choose a different file. This OBJ is already here.')
    dest.parent.mkdir(parents=True, exist_ok=True)
    written = [dest]
    shutil.copy2(src, dest)
    for path in mesh_bundle(src):
        if path.resolve() == src.resolve():
            continue
        target = dest.parent / path.name
        if target.resolve() == path.resolve():
            written.append(target)
            continue
        shutil.copy2(path, target)
        written.append(target)
    return written


def select_rows(entries, query='', kind='All types', status='All states', sort='source', reverse=False):
    words = query.casefold().split()
    rows = [e for e in entries if (kind == 'All types' or e['type'] == kind)
            and (status == 'All states' or e['publication'] == status)
            and all(word in ' '.join(str(e[k]) for k in ('source', 'type', 'targets', 'origin', 'publication', 'published_at')).casefold() for word in words)]
    return sorted(rows, key=lambda e: (e[sort] if sort == 'size' else str(e[sort]).casefold(), e['source']), reverse=reverse)
