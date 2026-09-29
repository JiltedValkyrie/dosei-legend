"""Non-destructive mesh exchange. This does not emit triangle-only runtime BINs."""
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import uuid

from PIL import Image

PROJECT = Path(__file__).resolve().parents[2] / 'game'
WORKSPACE = PROJECT.parent / 'workspace/meshes'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_mesh(path):
    data = Path(path).read_bytes()
    if len(data) < 64:
        raise ValueError('Truncated mesh header')
    h = struct.unpack_from('>9I3i4I', data)
    magic, version, nv, nf, vo, fo, to, nt, total = h[:9]
    if magic != 0x4B465231 or version != 2:
        raise ValueError('Only KFR1 version 2 scene meshes are supported')
    if not (0 < nv < 65536 and 0 < nf < 10000 and total == len(data)
            and vo == 64 and vo + nv * 6 <= fo and fo + nf * 20 <= h[14]
            and h[14] + h[15] * 36 <= to and to + nt == total):
        raise ValueError('Invalid mesh ranges')
    vertices = [struct.unpack_from('>3h', data, vo + i * 6) for i in range(nv)]
    faces = [struct.unpack_from('>4HIIHH', data, fo + i * 20) for i in range(nf)]
    for f in faces:
        size = f[6] & 255
        if (max(f[:4]) >= nv or f[2] != f[3] or size not in (16, 32)
                or ((f[6] >> 8) & 63) * 8 != size or f[7] & ~3
                or f[5] + 32 > nt or f[4] + size * size // 2 > nt):
            raise ValueError('Unsupported face, flags or texture range')
    return data, h, vertices, faces


def catalog(project=PROJECT):
    """Discover supported scene containers, not executables or collision-only files."""
    entries = []
    roots = [project / 'levels', project / 'assets', project / 'build/generated']
    # Retain the small fixture layout used by the importer unit tests.
    if project != PROJECT:
        roots.append(project / 'cd')
    for path in sorted(p for root in roots for p in root.rglob('*')):
        if not path.is_file() or path.suffix.lower() != '.bin':
            continue
        with path.open('rb') as stream:
            if stream.read(4) != b'KFR1':
                continue
        relative = path.relative_to(project).as_posix()
        # Keep existing local Forest editing revisions/preferences reachable
        # after moving the source from title-screen/cd into the level tree.
        identity = 'cd/FOREST.BIN' if relative == 'levels/kokiri/assets/static/FOREST.BIN' else relative
        entry = dict(id=hashlib.sha256(identity.encode()).hexdigest()[:12],
                     name=path.stem, source=relative)
        try:
            _, _, vertices, faces = read_mesh(path)
            entry.update(vertices=len(vertices), triangles=len(faces), error='')
        except ValueError as exc:
            entry.update(vertices=0, triangles=0, error=str(exc))
        entries.append(entry)
    return entries


def revision(root, entry, kind):
    folder = root / entry['id'] / kind / (datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    folder.mkdir(parents=True)
    return folder


def export_obj(entry, project=PROJECT, workspace=WORKSPACE):
    source = project / entry['source']
    data, header, vertices, faces = read_mesh(source)
    # Convert collapsed-sprite UVs to ordinary triangular OBJ UVs. Preview is
    # resampled, not pixel-identical to Saturn's rasterization. Originals stay intact.
    side = math.ceil(math.sqrt(len(faces)))
    cell, inner = 36, 32
    atlas = Image.new('RGBA', (side * cell, side * cell), (0, 0, 0, 0))
    obj = ['# Y up; native scene units. Blender import/export: Forward -Z, Up Y, scale 1.',
           'mtllib mesh.mtl', 'o ' + entry['name']]
    obj += ['v %d %d %d' % v for v in vertices]
    uv_lines, face_lines = [], []
    for i, f in enumerate(faces):
        size, flags = f[6] & 255, f[7]
        palette = struct.unpack_from('>16H', data, header[6] + f[5])
        pixels = data[header[6] + f[4]:header[6] + f[4] + size * size // 2]
        tile = Image.new('RGBA', (inner, inner))
        for y in range(inner):
            c = y / (inner - 1)
            for x in range(inner):
                b = x / (inner - 1)
                u = min(1, b / (1 - c)) if c < 1 else 0
                texel = round(c * (size - 1)) * size + round(u * (size - 1))
                packed = pixels[texel // 2]
                index = (packed & 15) if texel & 1 else packed >> 4
                color = palette[index]
                tile.putpixel((x, y), tuple(round(((color >> s) & 31) * 255 / 31)
                                          for s in (0, 5, 10)) + (255 if index else 0,))
        ox, oy = (i % side) * cell + 2, (i // side) * cell + 2
        atlas.paste(tile, (ox, oy))
        for x, y in ((0, 0), (inner - 1, 0), (0, inner - 1)):
            uv_lines.append('vt %.9f %.9f' % ((ox + x + .5) / atlas.width,
                                             1 - (oy + y + .5) / atlas.height))
        face_lines += [f'usemtl flags_{flags}', 'f ' + ' '.join(
            f'{f[j] + 1}/{i * 3 + j + 1}' for j in range(3))]
    folder = revision(workspace, entry, 'exports')
    (folder / 'mesh.obj').write_text('\n'.join(obj + uv_lines + face_lines) + '\n')
    (folder / 'mesh.mtl').write_text('\n'.join(
        f'newmtl flags_{flags}\nKd 1 1 1\nmap_Kd atlas.png\n' for flags in range(4)))
    atlas.save(folder / 'atlas.png')
    (folder / 'source.json').write_text(json.dumps(dict(source=entry['source'],
        sha256=digest(source), vertices=len(vertices), triangles=len(faces),
        note='Preview UV bake; preserve material names/UV seams. Runtime collision unchanged.'), indent=2))
    return folder / 'mesh.obj'


def _index(text, count):
    i = int(text)
    i = i - 1 if i > 0 else count + i
    if not text or int(text) == 0 or not 0 <= i < count:
        raise ValueError('OBJ index outside available data')
    return i


def _validate_polygon(points):
    def sub(a, b): return tuple(x - y for x, y in zip(a, b))
    def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
    def dot(a, b): return sum(x*y for x, y in zip(a, b))
    normal = cross(sub(points[1], points[0]), sub(points[2], points[0]))
    length = math.sqrt(dot(normal, normal))
    if length < 1e-8:
        raise ValueError('Degenerate face')
    if len(points) == 4:
        # Absolute tolerance is in native scene units. No hidden triangulation.
        if abs(dot(normal, sub(points[3], points[0]))) / length > .05:
            raise ValueError('Non-planar quad; keep it as triangles')
        for i in range(4):
            turn = cross(sub(points[(i+1) % 4], points[i]), sub(points[(i+2) % 4], points[(i+1) % 4]))
            if dot(normal, turn) <= 1e-8:
                raise ValueError('Concave, crossed or degenerate quad')


def _split_quad(points):
    """Choose an interior diagonal in the dominant projection; never repair bowties.

    Corner indices are returned so UVs and materials survive without interpolation.
    Non-planar surfaces are necessarily interpreted as two planar triangles.
    """
    normal = [0., 0., 0.]
    for p, q in zip(points, points[1:] + points[:1]):
        normal[0] += (p[1] - q[1]) * (p[2] + q[2])
        normal[1] += (p[2] - q[2]) * (p[0] + q[0])
        normal[2] += (p[0] - q[0]) * (p[1] + q[1])
    axis = max(range(3), key=lambda i: abs(normal[i]))
    if abs(normal[axis]) < 1e-8:
        raise ValueError('Cannot split crossed or degenerate quad safely')
    p = [tuple(v[i] for i in range(3) if i != axis) for v in points]

    def turn(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])

    def intersects(a, b, c, d):
        ts = (turn(a, b, c), turn(a, b, d), turn(c, d, a), turn(c, d, b))
        if ts[0] * ts[1] < 0 and ts[2] * ts[3] < 0:
            return True
        for t, v, x, y in ((ts[0], c, a, b), (ts[1], d, a, b),
                            (ts[2], a, c, d), (ts[3], b, c, d)):
            if abs(t) < 1e-8 and all(min(x[i], y[i])-1e-8 <= v[i] <= max(x[i], y[i])+1e-8 for i in (0, 1)):
                return True
        return False

    if intersects(p[0], p[1], p[2], p[3]) or intersects(p[1], p[2], p[3], p[0]):
        raise ValueError('Cannot split crossed quad safely')
    area = sum(p[i][0]*p[(i+1) % 4][1]-p[(i+1) % 4][0]*p[i][1] for i in range(4))
    choices = []
    for triangles, diagonal in ((((0, 1, 2), (0, 2, 3)), (0, 2)),
                                (((0, 1, 3), (1, 2, 3)), (1, 3))):
        if all(turn(*(p[i] for i in t)) * (1 if area > 0 else -1) > 1e-8 for t in triangles):
            for t in triangles:
                _validate_polygon([points[i] for i in t])
            length = sum((a-b)**2 for a, b in zip(points[diagonal[0]], points[diagonal[1]]))
            choices.append((length, triangles))
    if not choices:
        raise ValueError('Cannot find a non-degenerate interior quad diagonal')
    return min(choices)[1]


def parse_obj(path, *, split_incompatible=False, diagnostics=None, require_quads=True, require_flags=True):
    vertices, uvs, faces, libraries = [], [], [], []
    split_lines = []
    material = None
    for line_no, raw in enumerate(Path(path).read_text(encoding='utf-8-sig').splitlines(), 1):
        parts = raw.split('#', 1)[0].split()
        if not parts:
            continue
        try:
            tag, args = parts[0], parts[1:]
            if tag == 'v':
                if len(args) != 3: raise ValueError('Expected three vertex coordinates')
                v = tuple(map(float, args))
                if not all(math.isfinite(x) and -32768 <= x <= 32767 for x in v):
                    raise ValueError('Vertex exceeds native signed-16-bit coordinates')
                vertices.append(v)
            elif tag == 'vt':
                if len(args) not in (2, 3): raise ValueError('Expected UV coordinates')
                uv = tuple(map(float, args[:2]))
                if not all(math.isfinite(x) and 0 <= x <= 1 for x in uv):
                    raise ValueError('UVs must stay in the exported atlas [0,1]')
                uvs.append(uv)
            elif tag == 'mtllib': libraries.append(' '.join(args))
            elif tag == 'usemtl':
                material = ' '.join(args)
                if require_flags and material not in ('flags_0', 'flags_1', 'flags_2', 'flags_3'):
                    raise ValueError('Preserve exported flags_0 through flags_3 material names')
                if not require_flags and len(args)!=1: raise ValueError('Material names cannot contain spaces')
            elif tag == 'f':
                if len(args) not in (3, 4): raise ValueError('Only triangles and quads accepted; split n-gons explicitly')
                if material is None: raise ValueError('Face has no exported material')
                corners = []
                for token in args:
                    fields = token.split('/')
                    if len(fields) < 2 or not fields[1]: raise ValueError('Every corner needs a UV')
                    corners.append((_index(fields[0], len(vertices)), _index(fields[1], len(uvs))))
                points = [vertices[v] for v, _ in corners]
                try:
                    _validate_polygon(points)
                except ValueError:
                    if not split_incompatible or len(corners) != 4:
                        raise
                    triangles = _split_quad(points)
                    faces.extend((material, [corners[i] for i in t]) for t in triangles)
                    split_lines.append(line_no)
                else:
                    faces.append((material, corners))
            elif tag not in ('vn', 'o', 'g', 's'):
                raise ValueError('Unsupported OBJ statement: ' + tag)
        except (ValueError, IndexError) as exc:
            raise ValueError(f'Line {line_no}: {exc}') from exc
    if not vertices or not faces or len(vertices) >= 65536 or len(faces) >= 10000:
        raise ValueError('Empty mesh or scene capacity exceeded')
    if require_quads and not any(len(c) == 4 for _, c in faces) and not split_lines:
        raise ValueError('No quads found. Disable Triangulate Faces when exporting from Blender.')
    if diagnostics is not None:
        diagnostics.update(split_quads=len(split_lines), split_lines=split_lines)
    return vertices, uvs, faces, libraries


def import_obj(entry, path, project=PROJECT, workspace=WORKSPACE, *, split_incompatible=False, require_quads=True, require_flags=True):
    path = Path(path).resolve()
    diagnostics = {}
    vertices, uvs, faces, libraries = parse_obj(path, split_incompatible=split_incompatible,
                                              diagnostics=diagnostics, require_quads=require_quads,require_flags=require_flags)
    # Read only explicitly referenced MTLs/textures; write a self-contained bundle.
    materials = {}
    for library in libraries:
        mtl = path.parent / library
        current = None
        for raw in mtl.read_text(encoding='utf-8-sig').splitlines():
            parts = raw.strip().split(maxsplit=1)
            if len(parts) != 2: continue
            if parts[0] == 'newmtl': current = parts[1]
            elif parts[0] == 'map_Kd' and current:
                texture = mtl.parent / parts[1]
                with Image.open(texture) as img: img.verify()
                materials[current] = texture
    used = sorted({m for m, _ in faces})
    if any(m not in materials for m in used):
        raise ValueError('Missing diffuse texture. Export OBJ materials alongside the OBJ; no map_Kd options supported.')
    folder = revision(workspace, entry, 'imports')
    lines = ['# Validated editing mesh. Use Mesh Workshop to install for a game room.', 'mtllib mesh.mtl']
    lines += ['v ' + ' '.join(format(x, '.9g') for x in v) for v in vertices]
    lines += ['vt ' + ' '.join(format(x, '.9g') for x in uv) for uv in uvs]
    for material, corners in faces:
        lines += ['usemtl ' + material, 'f ' + ' '.join(f'{v+1}/{uv+1}' for v, uv in corners)]
    (folder / 'mesh.obj').write_text('\n'.join(lines) + '\n')
    mtl_lines = []
    for material in used:
        name = digest(materials[material]) + materials[material].suffix.lower()
        if not (folder / name).exists(): shutil.copyfile(materials[material], folder / name)
        mtl_lines.append(f'newmtl {material}\nKd 1 1 1\nmap_Kd {name}\n')
    (folder / 'mesh.mtl').write_text('\n'.join(mtl_lines))
    metadata = dict(source=entry['source'], source_sha256=digest(project / entry['source']),
                    input_sha256=digest(path), vertices=len(vertices),
                    triangles=sum(len(c) == 3 for _, c in faces), quads=sum(len(c) == 4 for _, c in faces),
                    runtime_ready=False, reason='Stored editing revision; use in game to validate budget and install a room override')
    metadata.update(diagnostics, split_incompatible=split_incompatible)
    (folder / 'mesh.json').write_text(json.dumps(metadata, indent=2))
    settings = load_settings(workspace)
    settings.setdefault('meshes', {}).setdefault(entry['id'], {})['candidate'] = str(folder.relative_to(workspace))
    save_settings(settings, workspace)
    return folder


def load_settings(workspace=WORKSPACE):
    path = workspace / 'preferences.json'
    return json.loads(path.read_text()) if path.exists() else {'prefer_quads': True, 'meshes': {}}


def save_settings(settings, workspace=WORKSPACE):
    workspace.mkdir(parents=True, exist_ok=True)
    temp = workspace / ('preferences-' + uuid.uuid4().hex + '.tmp')
    temp.write_text(json.dumps(settings, indent=2))
    temp.replace(workspace / 'preferences.json')


def build_selection(entry, project=PROJECT, workspace=WORKSPACE):
    """Legacy catalog selection; runtime room overrides use room_imports.json."""
    settings = load_settings(workspace)
    candidate = settings.get('meshes', {}).get(entry['id'], {}).get('candidate')
    reason = 'Original triangles selected'
    if settings.get('prefer_quads'):
        reason = 'Prefer quads: no imported candidate'
        if candidate:
            reason = 'Candidate stored; use in game to install for a room'
    return {'source': str(project / entry['source']), 'using_quads': False, 'reason': reason}
