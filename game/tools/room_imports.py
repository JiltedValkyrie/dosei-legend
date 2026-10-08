"""Explicit per-room visual overrides; original collision never changes."""
import json
import os
from pathlib import Path
from PIL import Image
import build_authored_scene as authored
from vdp1_budget import Budget, ACTOR_SCENES

DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / 'assets/room_imports.json'


def selected(prefix, room):
    from layout_variants import build_document
    if build_document() is not None:
        return None  # named layouts start from original ROM visuals
    path = os.environ.get('ROOM_IMPORTS')
    config = Path(path).resolve() if path else DEFAULT_CONFIG
    if not path and not config.exists():
        return None
    entries = json.loads(config.read_text(encoding='utf-8'))
    entry = entries.get('%s_room_%d' % (prefix, room))
    if entry is None:
        return None
    entry = dict(entry)
    entry['forest'] = prefix == 'spot04'
    entry['actors'] = prefix in ACTOR_SCENES
    for key in ('obj', 'atlas', 'uv_from'):
        if key in entry:
            entry[key] = (config.parent / entry[key]).resolve()
    return entry


def convert(entry, actor):
    positions, uvs, raw, mtllib = authored.parse_obj(entry['obj'])
    if not positions or not raw:
        raise ValueError('Room import has no geometry')
    if any(abs(c) > 32767 for p in positions for c in p):
        raise ValueError('Room import outside signed 16-bit coordinates')
    mode = entry.get('uv_mode', 'keep')
    if mode not in ('keep', 'transfer', 'flat'):
        raise ValueError('uv_mode must be keep, transfer or flat')
    if mode == 'transfer':
        source = authored.UvSource(entry['uv_from'])
        for face in raw:
            corners = []
            for vertex, _ in face['corners']:
                uv, distance = source.lookup(positions[vertex])
                if distance > entry.get('uv_tolerance', 24):
                    raise ValueError('UV transfer exceeds tolerance: %.1f units' % distance)
                corners.append((vertex, len(uvs)))
                uvs.append(uv)
            face['corners'] = corners
    atlas = None
    if mode != 'flat':
        path = entry.get('atlas')
        if not path and mtllib:
            names = set(authored.parse_mtl(entry['obj'].parent / mtllib).values())
            if len(names) == 1:
                path = (entry['obj'].parent / mtllib).parent / next(iter(names))
        if not path:
            raise ValueError('Room import needs one atlas or explicit atlas path')
        atlas = Image.open(path).convert('RGBA')
    for face in raw:
        if any(not 0 <= c[0] < len(positions) for c in face['corners']):
            raise ValueError('Invalid OBJ vertex index')
        if len(face['corners']) < 3:
            raise ValueError('Face needs at least three corners')
        if len(face['corners']) == 4 and not authored.convex([positions[c[0]] for c in face['corners']]):
            raise ValueError('Import requires convex quads; split invalid quads in Mesh Workshop')
    faces, records, tiles, tile_ids = [], [], {}, {}
    rgb = entry.get('colour', [140, 120, 80])
    if len(rgb) != 3 or any(not isinstance(v, int) or not 0 <= v <= 255 for v in rgb):
        raise ValueError('colour needs three integers in 0..255')
    colour = 0x8000 | (rgb[0] >> 3) | ((rgb[1] >> 3) << 5) | ((rgb[2] >> 3) << 10)
    for raw_face in raw:
        for corners in authored.triangulate(raw_face, positions):
            indices = [c[0] for c in corners]
            if len(indices) == 3:
                indices.append(indices[-1])
            face = dict(idx=tuple(indices), cull=entry.get('cull', False), mesh=False)
            material = raw_face.get('material')
            if material in ('flags_0', 'flags_1', 'flags_2', 'flags_3'):
                flags = int(material[-1])
                face.update(cull=bool(flags & 2), mesh=bool(flags & 1))
            if mode == 'flat':
                face['colour'] = colour
            else:
                if any(c[1] is None or not 0 <= c[1] < len(uvs) for c in corners):
                    raise ValueError('Missing UVs; choose transfer or flat explicitly')
                uv = [uvs[c[1]] for c in corners]
                width, height = authored.tile_size(uv, atlas.size,
                    [positions[c[0]] for c in corners], entry.get('units_per_texel', 6),
                    entry.get('max_tile', 32))
                clut, pixels = authored.quantize(authored.bake(atlas, uv, width, height), width, height)
                key = (width, height, clut, pixels)
                if key not in tile_ids:
                    offset = len(tiles)
                    tile_ids[key] = offset
                    tiles[offset] = dict(index=offset, width=width, height=height, clut=clut, pixels=pixels)
                face['tex_off'] = tile_ids[key]
            faces.append(face)
            # One room object; per-face depth culling still applies.
            records.append(dict(object=0, indices=indices))
    vertices = [tuple(round(c) for c in p) for p in positions]
    from build_hybrid_scene import halve_texture_tiles
    tiles, halving = halve_texture_tiles(tiles)
    budget = Budget()
    budget.add('import', [(t['width'], t['height']) for t in tiles.values()],len(faces),len(vertices))
    budget.add('link', actor['tiles'], actor['polygons'], actor['vertices'])
    if entry.get('forest') or entry.get('actors'):
        budget.reserve_forest_actors()
    failures = budget.failures()
    if entry.get('forest') or entry.get('actors'):
        from vdp1_budget import FOREST_VRAM_MARGIN
        if budget.vram_bytes + FOREST_VRAM_MARGIN > budget.vram_limit:
            failures.append('Gameplay room import must leave 32 KiB spare after resident actors')
    if failures:
        raise ValueError('; '.join(failures))
    manifest = dict(faces=records, budget=budget.parts,
                    workshop=dict(obj=str(entry['obj']), uv_mode=mode))
    if halving['reductions']:
        # emit_rooms persists the workshop block in rooms_manifest.json.
        manifest['workshop']['texture_halving'] = halving
    return vertices, faces, tiles, manifest
