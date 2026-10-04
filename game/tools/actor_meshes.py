"""Character OBJ exchange: named export, edited (decimated) mesh back in the build.

Offline tool, floats allowed. Export writes the faces the builder is about to
bake -- posed bind pose, model units -- as <name>.obj/.mtl, texture PNGs and a
<name>.actor.json material sidecar. Material names carry equipment group and
drawing limb (Blender keeps them through decimation). On import every corner
takes owner limb and vertex colour from the nearest original corner of the same
group, then gets its limb-local position by inverting that limb's bind pose.
write_model and the clip bakers already consume (local, owner), so animation
follows the edited mesh with no runtime change.
"""
import hashlib
import json
import math
import pathlib

from PIL import Image

import build_authored_scene

ROOT = pathlib.Path(__file__).resolve().parents[1]
ACTORS = ('link', 'zelda', 'impa', 'ganon')
VERSION = 1
TEXTURE_KEYS = ('cms', 'cmt', 'masks', 'maskt', 'scale', 'shifts', 'shiftt', 'uls', 'ult')
FACE_KEYS = ('group', 'limb', 'transparent', 'cull', 'lighting',
             'texture_segment', 'face_detail', 'hair_detail', 'full_texture')


def recipe_path(actor, game=ROOT):
    return pathlib.Path(game) / 'assets/dynamic' / actor / 'source.json'


def default_export(actor, game=ROOT):
    """Named, like Map Workshop LOD0: assets/dynamic/<actor>/LOD0/<actor>.obj."""
    return pathlib.Path(game) / 'assets/dynamic' / actor / 'LOD0' / (actor + '.obj')


def override(actor, game=ROOT):
    """Stored edited OBJ for the build, or None."""
    path = recipe_path(actor, game)
    if not path.is_file():
        return None
    name = json.loads(path.read_text()).get('mesh_override')
    return path.parent / name if name else None


def _uv(face, corner):
    tex = face['texture']
    if not tex:
        return 0.5, 0.5
    uv = [corner[3 + k] * tex['scale'][k] * 2 ** (-tex[shift] if tex[shift] <= 10 else 16 - tex[shift])
          - tex[origin] / 4 for k, shift, origin in ((0, 'shifts', 'uls'), (1, 'shiftt', 'ult'))]
    return uv[0] / tex['width'], 1 - uv[1] / tex['height']


def _settings(face):
    tex = face['texture']
    settings = {k: face.get(k) for k in FACE_KEYS}
    settings['limb'] = face['limb']
    settings['group'] = face.get('group', 'body')
    settings['prim'] = list(face.get('prim') or (255, 255, 255, 255))
    settings['texture'] = ({k: (list(tex[k]) if k == 'scale' else tex[k]) for k in TEXTURE_KEYS}
                           if tex else None)
    return settings


def _settings_key(settings):
    return json.dumps({k: v for k, v in settings.items() if k != 'image'}, sort_keys=True)


def _material_key(face):
    return _settings_key(_settings(face))


def export_obj(faces, obj, actor):
    """Welded by (position, owner): seams stay split, decimation stays sane."""
    obj = pathlib.Path(obj)
    if obj.suffix.lower() != '.obj' or any(c in obj.stem for c in '# \r\n\t'):
        raise ValueError('OBJ name needs .obj and no spaces, # or control characters')
    obj.parent.mkdir(parents=True, exist_ok=True)
    mtl, sidecar = obj.with_suffix('.mtl'), obj.with_suffix('.actor.json')
    images, materials, meta = {}, {}, {}
    vertex_index, vt_index, vn_index = {}, {}, {}
    v_lines, vt_lines, vn_lines, f_lines = [], [], [], []
    current = None
    for face in faces:
        tex = face['texture']
        size = (tex['width'], tex['height']) if tex else (1, 1)
        image = Image.new('RGBA', size)
        image.putdata(tex['colors'] if tex else [(255, 255, 255, 255)])
        identity = hashlib.sha256(str(size).encode() + image.tobytes()).hexdigest()[:16]
        if identity not in images:
            images[identity] = f'{obj.stem}_tex_{identity}.png'
            image.save(obj.parent / images[identity])
        settings = _settings(face)
        settings['image'] = images[identity]
        key = json.dumps(settings, sort_keys=True)
        if key not in materials:
            name = 'm%03d.%s.L%02d' % (len(materials), settings['group'], settings['limb'])
            materials[key] = name
            meta[name] = settings
        if materials[key] != current:
            current = materials[key]
            f_lines.append('usemtl ' + current)
        ids = []
        for corner, owner in zip(face['vertices'], face['vertex_limbs']):
            vk = (tuple(corner[:3]), owner, settings['group'], tuple(corner[5:9]))
            if vk not in vertex_index:
                vertex_index[vk] = len(vertex_index) + 1
                v_lines.append('v ' + ' '.join(format(c, '.9g') for c in corner[:3]))
            uv = _uv(face, corner)
            tk = (uv, identity)
            if tk not in vt_index:
                vt_index[tk] = len(vt_index) + 1
                vt_lines.append('vt %.9g %.9g' % uv)
            ref = '%d/%d' % (vertex_index[vk], vt_index[tk])
            if face.get('lighting'):
                # Lit faces carry N64 signed-byte normals in the colour slots.
                n = tuple((c if c < 128 else c - 256) / 127 for c in corner[5:8])
                if n not in vn_index:
                    vn_index[n] = len(vn_index) + 1
                    vn_lines.append('vn %.6g %.6g %.6g' % n)
                ref += '/%d' % vn_index[n]
            ids.append(ref)
        f_lines.append('f ' + ' '.join(ids))
    head = [f'# {actor}: posed bind pose, model units, Y up. Blender: Forward -Z, Up Y, scale 1.',
            '# Keep material names (group.Llimb) and the .actor.json beside this file.',
            f'mtllib {mtl.name}', f'o {obj.stem}']
    obj.write_text('\n'.join(head + v_lines + vt_lines + vn_lines + f_lines) + '\n', encoding='utf-8')
    mtl.write_text(''.join(f'newmtl {n}\nKd {" ".join(str(c / 255) for c in s["prim"][:3])}\nmap_Kd {s["image"]}\n\n'
                           for n, s in meta.items()), encoding='utf-8')
    sidecar.write_text(json.dumps(dict(version=VERSION, actor=actor, materials=meta), indent=1) + '\n')
    return obj


def _raw_uv(tex, u, v):
    """Inverse of _uv: back to N64 s/t; snap to the fixed-point step the ROM stored."""
    if not tex:
        return 0, 0
    out = []
    for value, extent, k, shift, origin in ((u, tex['width'], 0, 'shifts', 'uls'),
                                            (1 - v, tex['height'], 1, 'shiftt', 'ult')):
        factor = tex['scale'][k] * 2 ** (-tex[shift] if tex[shift] <= 10 else 16 - tex[shift])
        raw = (value * extent + tex[origin] / 4) / factor
        snap = round(raw * 64) / 64    # vertex s/t are S10.5; 1/64 covers it
        out.append(snap if abs(raw - snap) < 1e-4 else raw)
    return tuple(out)


def _invert(matrix):
    (a, b, c), (d, e, f), (g, h, i) = matrix
    det = a * (e * i - f * h) - b * (d * i - f * g) + c * (d * h - e * g)
    if abs(det) < 1e-12:
        raise ValueError('Singular limb pose')
    return ((e * i - f * h) / det, (c * h - b * i) / det, (b * f - c * e) / det), \
           ((f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det), \
           ((d * h - e * g) / det, (b * g - a * h) / det, (a * e - b * d) / det)


def _apply(matrix, origin, point):
    return tuple(origin[r] + sum(matrix[r][k] * point[k] for k in range(3)) for r in range(3))


def load_obj(obj, actor, original, poses):
    """Rebuild builder faces from an edited OBJ. `original` = faces before override."""
    obj = pathlib.Path(obj)
    sidecar = obj.with_suffix('.actor.json')
    if not sidecar.is_file():
        raise ValueError(f'{sidecar.name} missing: keep it beside the edited OBJ')
    data = json.loads(sidecar.read_text())
    if data.get('version') != VERSION or data.get('actor') != actor:
        raise ValueError(f'{sidecar.name} is not a {actor} character export')
    meta = data['materials']
    positions, uvs, records, _ = build_authored_scene.parse_obj(obj)
    normals, normal_refs = [], []
    for line in obj.read_text(errors='replace').splitlines():
        parts = line.split()
        if parts[:1] == ['vn']:
            normals.append(tuple(float(v) for v in parts[1:4]))
        elif parts[:1] == ['f']:
            refs = [t.split('/') for t in parts[1:]]
            normal_refs.append([int(r[2]) - 1 if len(r) > 2 and r[2] else None for r in refs])
    corners_by_group, corners_by_material = {}, {}
    for face in original:
        group = face.get('group', 'body')
        material = _material_key(face)
        for corner, owner in zip(face['vertices'], face['vertex_limbs']):
            entry = (corner[:3], owner, corner[5:9])
            corners_by_group.setdefault(group, []).append(entry)
            corners_by_material.setdefault(material, []).append(entry)
    inverse = {limb: (_invert(m), o) for limb, (m, o) in poses.items()}
    images, out, cache = {}, [], {}
    for record, nrefs in zip(records, normal_refs):
        name = record['material']
        if name not in meta:
            raise ValueError(f'OBJ line {record["line"]}: unknown material {name!r}; keep exported material names')
        s = meta[name]
        if any(t is None for _, t in record['corners']) and s['texture']:
            raise ValueError(f'OBJ line {record["line"]}: textured face lacks UVs')
        if s['image'] not in images:
            png = obj.parent / s['image']
            if not png.is_file():
                raise ValueError(f'Texture {s["image"]} missing beside OBJ')
            image = Image.open(png).convert('RGBA')
            images[s['image']] = (image.size, list(image.getdata()))
        (width, height), colours = images[s['image']]
        texture = (dict(s['texture'], width=width, height=height, colors=colours,
                        scale=tuple(s['texture']['scale'])) if s['texture'] else None)
        group_pool = corners_by_group.get(s['group'])
        if not group_pool:
            raise ValueError(f'Material {name}: group {s["group"]} not in original {actor}')
        material_pool = corners_by_material.get(_settings_key(s), [])
        built = []
        for (vi, ti), ni in zip(record['corners'], nrefs):
            p = positions[vi]
            normal = normals[ni] if ni is not None and s.get('lighting') else None
            key = (p, name, normal)
            if key not in cache:
                near = []
                for pool in (material_pool, group_pool):
                    if pool:
                        best = min(math.dist(p, c[0]) for c in pool)
                        near = [c for c in pool if math.dist(p, c[0]) <= best + 1e-6]
                        if best < 1e-6:
                            break
                if normal is not None:
                    def miss(c):
                        n = [(v if v < 128 else v - 256) / 127 for v in c[2][:3]]
                        return sum((n[k] - normal[k]) ** 2 for k in range(3))
                    near.sort(key=miss)
                    near = [c for c in near if miss(c) <= miss(near[0]) + 1e-9]
                pick = next((c for c in near if c[1] == s['limb']), near[0])
                matrix, origin = inverse[pick[1]]
                local = tuple(int(round(v)) for v in _apply(matrix, (0, 0, 0),
                              tuple(p[k] - origin[k] for k in range(3))))
                colour = pick[2]
                if normal is not None and not any(math.isclose(a, b, abs_tol=1e-3) for a, b in [(
                        sum(((v if v < 128 else v - 256) / 127 - normal[k]) ** 2
                            for k, v in enumerate(colour[:3])), 0)]):
                    # Edited normal (Blender recomputed it): honour it.
                    colour = tuple(round(max(-1, min(1, c)) * 127) & 255 for c in normal) + tuple(colour[3:])
                cache[key] = (pick[1], local, _apply(*poses[pick[1]], local), colour)
            owner, local, posed, colour = cache[key]
            u, v = uvs[ti] if ti is not None else (0.5, 0.5)
            built.append((owner, local, posed + _raw_uv(texture, u, v) + tuple(colour)))
        for i in range(1, len(built) - 1):    # fan-triangulate quads/ngons
            tri = (built[0], built[i], built[i + 1])
            if len({(b[0], b[1]) for b in tri}) < 3:
                continue
            face = {k: s.get(k) for k in FACE_KEYS}
            face.update(vertices=[b[2] for b in tri], vertex_limbs=[b[0] for b in tri],
                        local=[b[1] for b in tri], texture=texture, prim=tuple(s['prim']))
            for k in ('full_texture', 'hair_detail'):
                if face.get(k) is None:
                    face.pop(k)
            out.append(face)
    if not out:
        raise ValueError(f'{obj.name}: no usable triangles')
    groups = {f.get('group', 'body') for f in original} - {f['group'] for f in out}
    if groups:
        raise ValueError('Edited mesh dropped equipment groups: ' + ', '.join(sorted(groups)))
    # Editors reorder faces by material; equipment ranges must stay contiguous
    # and in source order (first-person gear last).
    order = {g: i for i, g in enumerate(dict.fromkeys(f.get('group', 'body') for f in original))}
    out.sort(key=lambda f: order[f['group']])
    return out


def exchange(actor, faces, poses, export=None, mesh=None, game=ROOT):
    """Builder hook: optional export of current faces, then optional override."""
    if export:
        print('export  : %s' % export_obj(faces, export, actor))
    # mesh='' forces the ROM mesh (export ignores an installed override).
    mesh = mesh if mesh is not None else override(actor, game)
    if mesh:
        edited = load_obj(mesh, actor, faces, poses)
        print('override: %s  %d -> %d faces' % (pathlib.Path(mesh).name, len(faces), len(edited)))
        return edited
    return faces


def _build(actor, game, out, extra):
    """Run the real builder (ROM paths from config.ini) into a scratch folder."""
    import subprocess
    import sys
    sys.path.insert(0, str(pathlib.Path(game).parent / 'tools/launcher'))
    import project_config
    paths = project_config.read_paths()
    tools = pathlib.Path(game) / 'tools'
    common = ['--oot', paths['oot_decomp'], '--rom-dir', paths['oot_roms']]
    if actor == 'link':   # same flags as build.sh
        command = [str(tools / 'build_link_model.py'), '--flat', '--animate',
                   '--out', str(pathlib.Path(out) / 'LINK.BIN')]
    else:
        command = [str(tools / 'build_actor_model.py'), '--actor', actor, '--out', str(out)]
    result = subprocess.run([sys.executable] + command + common + extra, capture_output=True,
                            text=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip().splitlines()[-1])
    return result.stdout


def export_actor(actor, obj, game=ROOT):
    """Unedited character mesh to a named OBJ; build outputs stay untouched."""
    import tempfile
    with tempfile.TemporaryDirectory() as temp:
        _build(actor, game, temp, ['--export-obj', str(obj), '--mesh-obj', ''])
    return pathlib.Path(obj)


def install(actor, obj, game=ROOT):
    """Validate with the real builder, then store under assets/dynamic/<actor>/mesh/."""
    import shutil
    import tempfile
    obj = pathlib.Path(obj)
    with tempfile.TemporaryDirectory() as temp:
        log = _build(actor, game, temp, ['--mesh-obj', str(obj)])
    folder = recipe_path(actor, game).parent / 'mesh'
    stage = folder.with_name('mesh.new')
    shutil.rmtree(stage, ignore_errors=True)
    stage.mkdir(parents=True)
    files = [obj, obj.with_suffix('.mtl'), obj.with_suffix('.actor.json')]
    files += [obj.parent / s['image'] for s in
              json.loads(obj.with_suffix('.actor.json').read_text())['materials'].values()]
    for path in dict.fromkeys(files):
        if path.is_file():
            shutil.copy2(path, stage / path.name)
    shutil.rmtree(folder, ignore_errors=True)
    stage.rename(folder)
    recipe = recipe_path(actor, game)
    data = json.loads(recipe.read_text()) if recipe.is_file() else {}
    data['mesh_override'] = 'mesh/' + obj.name
    recipe.write_text(json.dumps(data, indent=2) + '\n')
    return next((l for l in log.splitlines() if l.startswith('override')), 'override installed')


def restore(actor, game=ROOT):
    """Back to the ROM mesh. Stored edit stays in mesh/ for reference."""
    recipe = recipe_path(actor, game)
    if not recipe.is_file():
        return False
    data = json.loads(recipe.read_text())
    if data.pop('mesh_override', None) is None:
        return False
    recipe.write_text(json.dumps(data, indent=2) + '\n')
    return True
