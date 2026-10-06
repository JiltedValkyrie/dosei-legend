"""Source-UV converter: shared repeating quads plus density-budgeted bakes.

Collision is deliberately not regenerated. Render positions remain in source
space until build_sgl_scene.emit() bakes the Saturn Y conversion.
"""
import collections
import os
import json
import math
import pathlib
import struct
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'shared/tools'))
import build_kokiri_scene as source
import build_quads as quads
from vdp1_budget import (Budget, tile_bytes, MAX_POLYGONS, MAX_VERTICES,
                         RUNTIME_SPRITE_BYTES, FOREST_VRAM_MARGIN,
                         FOREST_ACTOR_BYTES, ACTOR_SCENES)

OOT_DEFAULT = pathlib.Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot'))


def load_faces(oot, rom_dir=None, prefix='spot04'):
    """Every display-list face of one scene's rooms, tagged with its room.

    `prefix` selects the scene. It used to be hardcoded to spot04; the slice
    now needs Link's house as well, and every OoT scene is read identically.
    """
    segments = source.extract(oot, rom_dir, prefix=prefix)
    faces = []
    for name, data in segments.items():
        if 'room' in name:
            display = source.DisplayLists(segments[prefix + '_scene'], data)
            if prefix in ('spot09','spot16'): display.include_depth_branches = True
            if prefix == 'ydan':
                # Scene_DrawConfigDekuTree binds segment 8 to the day entrance
                # texture (not a display list). Night is outside this slice.
                import xml.etree.ElementTree as ET
                xml = ET.parse(oot / 'assets/xml/scenes/dungeons/ydan.xml')
                offset = next(int(e.attrib['Offset'], 16) for e in xml.iter('Texture')
                              if e.attrib['Name'] == 'gDekuTreeDayEntranceTex')
                display.segments[8] = segments[prefix + '_scene'][offset:]

            display.room()
            for face in display.faces:
                face['room'] = name
                if face['lighting']:
                    face['vertices'] = [tuple(v[:5]) + tuple(x if x < 128 else x-256
                                                             for x in v[5:8]) + (v[8],)
                                        for v in face['vertices']]
            faces.extend(display.faces)
    return faces


def interpolate(points, u, v):
    weights = ((1-u)*(1-v), u*(1-v), v) if len(points) == 3 else (
        (1-u)*(1-v), u*(1-v), u*v, (1-u)*v)
    return tuple(sum(w*p[k] for w, p in zip(weights, points)) for k in range(9))


def shade(vertex, lighting):
    if lighting:
        normal = [(x if x < 128 else x-256)/127 for x in vertex[5:8]]
        light = .65 + .35 * max(0, sum(x*y for x, y in zip(normal, (.3, .9, .3))))
        return (light,)*3
    return tuple(x/255 for x in vertex[5:8])


def barycentric(point, vertices, axes=(0, 1, 2)):
    a, b, c = vertices
    u = [b[k]-a[k] for k in axes]
    v = [c[k]-a[k] for k in axes]
    p = [point[k]-a[k] for k in axes]
    dot = lambda x, y: sum(i*j for i, j in zip(x, y))
    uu, vv, uv = dot(u,u), dot(v,v), dot(u,v)
    den = uu*vv-uv*uv
    if abs(den) < 1e-9:
        return None
    bweight = (dot(p,u)*vv-dot(p,v)*uv)/den
    cweight = (dot(p,v)*uu-dot(p,u)*uv)/den
    return (1-bweight-cweight, bweight, cweight)


def surface_vertex(group, u, v):
    p = interpolate(group['points'], u, v)
    if 'pair' not in group:
        return p
    # Preserve the original two triangles' UVs and vertex shading, rather
    # than replacing a diagonal seam with an unrelated bilinear UV mapping.
    for face in (group['tri'], group['pair']):
        weights = barycentric(p, face['vertices'])
        if weights is not None and min(weights) >= -1e-6:
            return tuple(sum(w*q[k] for w, q in zip(weights, face['vertices']))
                         for k in range(9))
    raise ValueError('quad bake escaped its original triangles')


def quantize(pixels, width, height):
    rgb = Image.new('RGB', (width, height))
    rgb.putdata([p[:3] for p in pixels])
    indexed = rgb.quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                           dither=Image.Dither.NONE)
    palette = indexed.getpalette()
    palette += [0] * max(0, 45-len(palette))
    clut = (0,) + tuple(0x8000 | (palette[i*3] >> 3) |
                         ((palette[i*3+1] >> 3) << 5) |
                         ((palette[i*3+2] >> 3) << 10) for i in range(15))
    indices = [i+1 if p[3] >= 64 else 0 for i, p in zip(indexed.tobytes(), pixels)]
    packed = bytes((indices[i] << 4) | indices[i+1] for i in range(0, len(indices), 2))
    return clut, packed


def flat_surface(group):
    """Parked experiment: normal level groups retain their original textures."""
    if not group.get('flat_shaded', False):
        return False
    n = quads.normal(group['points'])
    length = math.sqrt(sum(v*v for v in n))
    return length > 0 and abs(n[1]) >= .85 * length


def flat_colour(group):
    """One source-derived colour; no UV ramp or baked texture pattern."""
    tex = group['texture']
    samples = [c for c in tex['colors'] if c[3] >= 64] if tex else [(255,)*4]
    if not samples:
        return (0, 0, 0, 0)
    original = group['tri']['vertices']
    lights = [shade(p, group['tri']['lighting']) for p in original]
    prim = group['tri']['prim']
    return tuple(max(0, min(255, round(
        sum(c[k] for c in samples)/len(samples) *
        sum(s[k] for s in lights)/len(lights) * prim[k]/255)))
        for k in range(3)) + (255,)


def has_cutout(group):
    tex = group['texture']
    return bool(tex and any(c[3] < 64 for c in tex['colors']))


def flat_tile_size(group, width, height):
    """Only a fully covered flat tile can discard its original UV coverage."""
    if flat_surface(group) and not has_cutout(group):
        return (8, 1)
    return (width, height)


def render_tile(group, width, height, shared=False):
    flat = flat_colour(group) if flat_surface(group) else None
    if flat is not None and not has_cutout(group):
        return quantize([flat] * (width*height), width, height)
    tex = group['texture']
    pixels = []
    # Shared tiles keep one coarse static light level per surface. A gradient
    # would make every repetition unique again; bake paths retain gradients.
    shades = [shade(p, group['tri']['lighting']) for p in group['points']]
    uniform = tuple(round(sum(s[k] for s in shades)/len(shades)*8)/8 for k in range(3))
    # G_SETPRIMCOLOR was parsed and then dropped, so every surface OoT tints
    # through the combiner baked at full white. The worst of these are the
    # grayscale intensity decals lying on the play-area ground: with prim
    # (155,140,52,179) discarded they became bright white screen-door sheets
    # sweeping over the near view, and the shadow decals with prim (0,0,0)
    # turned white as well. Multiplying is the common OoT cycle
    # (TEXEL0 * PRIM); it is an approximation of the combiner, not a full
    # implementation, and it only ever darkens toward the authored colour.
    prim = tuple(c/255.0 for c in group['tri']['prim'][:3])
    for y in range(height):
        for x in range(width):
            # Sample centres on direct/repeating tiles: sampling both ends of
            # [0,64] would duplicate texel zero and omit a texel at the seam.
            u, v = ((x+.5)/width, (y+.5)/height) if shared else (
                x/max(1, width-1), y/max(1, height-1))
            p = interpolate(group['points'], u, v) if shared else surface_vertex(group, u, v)
            if tex:
                s = source.coordinate(p[3], tex['scale'][0], tex['shifts'], tex['uls'],
                                      tex['cms'], tex['masks'], tex['width'])
                t = source.coordinate(p[4], tex['scale'][1], tex['shiftt'], tex['ult'],
                                      tex['cmt'], tex['maskt'], tex['height'])
                colour = tex['colors'][t*tex['width']+s]
            else:
                colour = (255, 255, 255, 255)
            if flat is not None:
                # Flatten RGB, not coverage. Intensity decals use their source
                # alpha as a cutout mask; filling those holes creates a whole
                # stippled sheet even though the material still has MESHon.
                pixels.append(flat[:3] + (colour[3],))
                continue
            light = uniform if shared else shade(p, group['tri']['lighting'])
            pixels.append(tuple(max(0, min(255, round(colour[k]*light[k]*prim[k])))
                                for k in range(3)) + (colour[3],))
    return quantize(pixels, width, height)


def convert(oot, head, actor, out_dir, patches_only=False, rom_dir=None,
            quad_obj=None, source_path=None, room=None, prefix='spot04', layout=None, base_tile_limit=None, source_tessellation=False,
            wall_split_limit=None, streamed=False):
    """streamed=True: the caller (build_field_chunks.sweep) streams pieces and
    checks the table/vertex/VRAM budget per Link position, so the whole-scene
    union is allowed to exceed what one frame can hold."""
    source_faces = load_faces(oot, rom_dir, prefix=prefix)
    from layout_variants import build_document
    document = build_document() if layout is None else layout
    if document and document.get('meshes'):
        from map_meshes import apply_faces
        source_faces = apply_faces(source_faces,source.extract(oot,rom_dir,prefix=prefix),document)
    lod_settings = {}
    if document and document.get('lods'):
        from map_meshes import apply_lods
        source_faces, lod_settings = apply_lods(source_faces,source.extract(oot,rom_dir,prefix=prefix),document)
    preferred, workshop = [], None
    if quad_obj:
        from workshop_quads import preferred_pairs
        preferred, workshop = preferred_pairs(quad_obj, source_faces, source_path)
        print('workshop: %d source-compatible quads, %d incompatible, %d bent/concave'
              % (workshop['accepted_pairs'], workshop['material_or_uv_rejected'],
                 workshop['split_incompatible']), flush=True)
    groups = quads.build(source_faces, preferred)
    if document and document.get('patches'):
        # Local retopology (field_retopo.py): parents stay in the sizing passes
        # below, so no unrelated tile changes; replace_pieces swaps them after.
        from field_retopo import apply_patches
        groups = apply_patches(groups, source_faces, source.extract(oot, rom_dir, prefix=prefix),
                               document, prefix)
        if prefix == 'spot00' and any(g.get('retopo_drop') for g in groups):
            from field_ground_grid import extend
            from build_field_chunks import LANDMARKS
            groups = extend(groups, {i for _, _, ids in LANDMARKS for i in ids})
    # Bake tiled UVs into the authored face instead of adding repeat/height
    # subdivisions. Retopology belongs to the imported mesh's author.
    for group in groups:
        if group['tri'].get('authored_mesh'):
            group['kind'] = quads.BAKE
    if room is not None:
        groups = [g for g in groups if g['tri']['room'] == room]
    # Table budget policy for big scenes: a wall/cliff repeating texture split
    # into more than `wall_split_limit` pieces is baked as one face instead.
    # Ground keeps its splits (affine warp is worst underfoot).
    if wall_split_limit is not None:
        for g in groups:
            n = quads.normal(g['points'])
            ru, rv = g['repeat']
            if (g['kind'] == quads.SPLIT and ru * rv > wall_split_limit and
                    abs(n[1]) <= .85 * math.sqrt(sum(x*x for x in n))):
                g['kind'], g['repeat'] = quads.BAKE, (1, 1)
    split = max((g for g in groups if g['kind'] == quads.SPLIT),
                key=lambda g:g['size'], default=max(groups,key=lambda g:g['size']))
    # Diagnostic landmark only: the flattest quad nearest the village
    # clearing, used for texture_probe.h. A scene with no baked ground quad --
    # a small interior, for instance -- falls back to the largest group rather
    # than aborting the build over a probe coordinate.
    ground = min((g for g in groups if g['kind'] == quads.BAKE and
                  abs(quads.normal(g['points'])[1]) > .85 * math.sqrt(sum(
                      n*n for n in quads.normal(g['points'])))),
                 key=lambda g:sum((sum(p[k] for p in g['points'])/len(g['points']) -
                                   (-300,0,0)[k])**2 for k in range(3)),
                 default=max(groups, key=lambda g: g['size']))
    # Patch mode retains original triangles elsewhere, useful for a visual A/B.
    if patches_only:
        selected = set(split['source'] + ground['source'])
        groups = [g for g in groups if set(g['source']) <= selected]
        for i, face in enumerate(load_faces(oot, rom_dir)):
            if i not in selected:
                groups.append(dict(kind=quads.BAKE, repeat=(1,1), tri=face,
                                   points=face['vertices'], texture=face['texture'],
                                   size=quads.span(face['vertices']), source=[i]))

    # Limited close-ground subdivision addresses the large perspective/near
    # crossings the density-only change does not fix. Fifty surfaces add at
    # most 150 polygons / 250 points; the final combined budget still gates it.
    candidates = []
    for i,g in enumerate(groups):
        n = quads.normal(g['points'])
        if not g['tri'].get('authored_mesh') and g['kind'] == quads.BAKE and g['size'] > 400 and abs(n[1]) > .85*math.sqrt(sum(x*x for x in n)):
            center = [sum(p[k] for p in g['points'])/len(g['points']) for k in range(3)]
            if not patches_only or g['source'] == ground['source']:
                candidates.append(((center[0]+300)**2+center[2]**2, i))
    selected = {i for _,i in sorted(candidates)[:50]}
    if room is not None:
        groups = [part for g in groups for part in ([g] if source_tessellation else room_ground(g))]
        # Isolated near-camera split experiment, opt-in only. DOSEI_SPLIT_TEST
        # holds source triangle ids ("580,581"); the one group built from
        # exactly those triangles is replaced by its 2x2 children. Everything
        # else, including that group's parent tile in a normal build, is
        # untouched, so split off/on discs differ only in this surface.
        target = os.environ.get('DOSEI_SPLIT_TEST')
        if target:
            want = [int(v) for v in target.split(',') if v.strip()]
            picked = [g for g in groups if list(g['source']) == want and
                      len(g['points']) == 4]
            # Rooms are converted one at a time, so no match here is normal
            # and only means this room is untouched. A surface the ordinary
            # ground pass already subdivided arrives as several pieces; all of
            # them are refined, which is what "one more level on this surface"
            # means once the baseline already split it.
            if picked:
                divisions = int(os.environ.get('DOSEI_SPLIT_DIVISIONS', '2'))
                chosen = set(id(g) for g in picked)
                groups = [part for g in groups for part in
                          (split_ground(g, divisions) if id(g) in chosen else [g])]
                print('split test: %s source %s, %d piece(s) -> %d children'
                      % (room, want, len(picked), len(picked)*divisions*divisions),
                      flush=True)
    else:
        groups = [piece for i,g in enumerate(groups) for piece in (
            split_ground(g, 8 if g['source'] == ground['source'] else 2)
            if i in selected else [g])]

    positions, position_ids, faces, tiles, tile_ids, records = [], {}, [], collections.OrderedDict(), {}, []

    def add_tile(group, w, h, shared):
        # Explicit offline policy for large scenes. Resample the same UV patch;
        # geometry, winding, source object identity and collision stay intact.
        if shared and base_tile_limit is not None:
            w, h = min(w, base_tile_limit), min(h, base_tile_limit)
        w, h = flat_tile_size(group, w, h)
        clut, pixels = render_tile(group, w, h, shared)
        key = (w, h, clut, pixels)
        if key not in tile_ids:
            i = len(tiles)
            tile_ids[key] = i
            tiles[i] = dict(index=i, width=w, height=h, clut=clut, pixels=pixels)
        return tile_ids[key]

    pieces, bakes = [], []
    for group in groups:
        if group['kind'] == quads.BAKE:
            bakes.append(group)
            continue
        points_list = quads.subdivide(group) if group['kind'] == quads.SPLIT else [group['points']]
        tex = group['texture']
        bounded = []
        for points in points_list:
            # Tall quads can cover the view with every corner off-screen.
            # Split the long vertical edge once; each half samples its own
            # half of the same source tile (no stretching or extra repeats).
            a,b,c,d = points
            if max(abs(a[1]-d[1]),abs(b[1]-c[1])) > 400:
                mid_ad = tuple((x+y)/2 for x,y in zip(a,d))
                mid_bc = tuple((x+y)/2 for x,y in zip(b,c))
                bounded.extend(([a,b,mid_bc,mid_ad],[mid_ad,mid_bc,c,d]))
            elif max(abs(a[1]-b[1]),abs(d[1]-c[1])) > 400:
                mid_ab = tuple((x+y)/2 for x,y in zip(a,b))
                mid_dc = tuple((x+y)/2 for x,y in zip(d,c))
                bounded.extend(([a,mid_ab,mid_dc,d],[mid_ab,b,c,mid_dc]))
            else:
                bounded.append(points)
        for points in bounded:
            piece = dict(group, points=points)
            # Preserve the original UV orientation; transposed quads use a
            # transposed tile. No runtime arbitrary-UV support is assumed.
            sideways = abs(points[0][3]-points[1][3]) < .001
            uv = [quads.effective_uv(p,tex) for p in points]
            axis = 1 if sideways else 0
            w = max(1,round(abs(uv[1][axis]-uv[0][axis])))
            h = max(1,round(abs(uv[3][1-axis]-uv[0][1-axis])))
            w = max(8, (w+7)//8*8)
            tile = add_tile(piece, w, h, True)
            pieces.append((piece, tile))

    budget = Budget()
    budget.add('link', actor['tiles'], actor['polygons'], actor['vertices'])
    if prefix in ACTOR_SCENES:
        budget.reserve_forest_actors()
    budget.add('shared', [(t['width'], t['height']) for t in tiles.values()], 0, 0)
    if room is not None:
        bakes = refine_room_ground(bakes, pieces, actor,
                                   budget.vram_limit-budget.vram_bytes-FOREST_VRAM_MARGIN)
    # Start with 16x16 bakes. Spend remaining space on the worst *directional*
    # density, not a blanket resolution increase. Keep room for new effects.
    available = budget.vram_limit-budget.vram_bytes-FOREST_VRAM_MARGIN
    sizes = [[16,16] for g in bakes]
    available -= len(bakes)*tile_bytes(16,16)
    if available < 0:
        raise ValueError('base hybrid texture set exceeds VRAM by %d bytes' % -available)
    spans = []
    for group in bakes:
        p = group['points']
        spans.append((max(math.dist(p[0][:3],p[1][:3]),
                          math.dist(p[2][:3],p[3][:3]) if len(p)==4 else 0),
                      max(math.dist(p[0][:3],p[-1][:3]), math.dist(p[1][:3],p[2][:3]))))
    while True:
        choices = [(spans[i][axis]/size[axis], i, axis) for i, size in enumerate(sizes)
                   for axis in (0,1) if size[axis] < 128 and
                   size[0]*size[1]//2 <= available and
                   (not patches_only or bakes[i]['source'] == ground['source'])]
        if not choices:
            break
        density, i, axis = max(choices)
        if density < 4:
            break
        available -= sizes[i][0]*sizes[i][1]//2
        sizes[i][axis] *= 2
    for group, (w,h) in zip(bakes, sizes):
        pieces.append((group, add_tile(group, w, h, False)))

    # Real deduplication often frees tens of KiB beyond the conservative first
    # pass. Spend that on walkable ground near the starting play area, rather
    # than leaving the close-view patch at the old effective density.
    # Counts the runtime RGB555 sprites too. This pass re-totals the tiles by
    # hand instead of reading Budget.texture_bytes, so it used to miss anything
    # that is not a tile and spend VRAM the sprite loader was going to need.
    remaining = (budget.vram_limit - sum(tile_bytes(t['width'], t['height'])
                                         for t in tiles.values())
                 - actor_bytes(actor) - RUNTIME_SPRITE_BYTES - FOREST_VRAM_MARGIN
                 - (FOREST_ACTOR_BYTES if prefix in ACTOR_SCENES else 0))
    floors = []
    for i, (group, tile) in enumerate(pieces):
        if flat_surface(group):
            continue  # Flat colour cannot benefit from a bigger texture.
        n = quads.normal(group['points'])
        if group['kind'] != quads.BAKE or group['size'] < 200 or abs(n[1]) < .85*math.sqrt(sum(x*x for x in n)):
            continue
        center = [sum(p[k] for p in group['points'])/len(group['points']) for k in range(3)]
        distance = (center[0]+300)**2 + center[2]**2
        floors.append((distance, i))
    for _, i in sorted(floors):
        group, old_tile = pieces[i]
        t = tiles[old_tile]
        size = min(128, max(64, 2**math.ceil(math.log2(max(1,group['size']/6)))))
        w, h = max(size,t['width']), max(size,t['height'])
        cost = tile_bytes(w,h)
        if (w,h) == (t['width'],t['height']) or cost > remaining:
            continue
        before = len(tiles)
        tile = add_tile(group,w,h,False)
        pieces[i] = (group,tile)
        if len(tiles) > before:
            remaining -= cost
    if any(g.get('retopo_drop') for g, _ in pieces):
        from field_retopo import replace_pieces
        pieces = replace_pieces(pieces, tiles, add_tile)
    # Remove superseded tiles; compact IDs keep Jo's shared sprite table small.
    used = set(tile for _, tile in pieces)
    mapping = {old:new for new,old in enumerate(sorted(used))}
    tiles = collections.OrderedDict((mapping[i],dict(t,index=mapping[i]))
                                     for i,t in tiles.items() if i in used)
    pieces = [(g,mapping[t]) for g,t in pieces]

    for group, tile in pieces:
        ids = []
        for p in group['points']:
            pos = tuple(round(x) for x in p[:3])
            if pos not in position_ids:
                position_ids[pos] = len(positions)
                positions.append(pos)
            ids.append(position_ids[pos])
        if len(ids) == 3:
            ids.append(ids[-1])
        face = dict(idx=tuple(ids), tex_off=tile, cull=group['tri']['cull'],
                    mesh=group['tri']['transparent'])
        faces.append(face)
        records.append(dict(source=group['source'], kind=group['kind'], tile=tile,
                            object=group['tri'].get('object',0),
                            room=group['tri']['room'], indices=ids,
                            flat_shaded=flat_surface(group),
                            cull=face['cull'], mesh=face['mesh'],
                            far_sort=bool(group.get('far_sort'))))

    budget = Budget()
    budget.add('forest', [(t['width'],t['height']) for t in tiles.values()], len(faces), len(positions))
    budget.add('link', actor['tiles'], actor['polygons'], actor['vertices'])
    if prefix in ACTOR_SCENES:
        budget.reserve_forest_actors()
    print(budget.report(), flush=True)
    if budget.failures() and not streamed:
        raise ValueError('; '.join(budget.failures()))
    # Export connected render components/bounds for later hut/tree visibility.
    # This metadata never removes or partitions the resident collision mesh.
    neighbors = collections.defaultdict(list)
    for i, record in enumerate(records):
        for vertex in record['indices']:
            neighbors[(record['room'], vertex)].append(i)
    unseen, chunks = set(range(len(records))), []
    while unseen:
        pending, members = [min(unseen)], []
        while pending:
            i = pending.pop()
            if i not in unseen:
                continue
            unseen.remove(i)
            members.append(i)
            for v in records[i]['indices']:
                pending.extend(j for j in neighbors[(records[i]['room'],v)] if j in unseen)
        points = [positions[v] for i in members for v in records[i]['indices']]
        chunks.append(dict(id=len(chunks), faces=sorted(members),
                           minimum=[min(p[k] for p in points) for k in range(3)],
                           maximum=[max(p[k] for p in points) for k in range(3)]))
    patches = {}
    for label, group in (('ground', ground), ('treeline', split)):
        patches[label] = dict(source=group['source'], points=group['points'],
                              kind=group['kind'], span=group['size'],
                              polygons=[i for i,r in enumerate(records) if r['source']==group['source']])
    out_dir.mkdir(parents=True, exist_ok=True)
    ground_center = [round(sum(p[k] for p in ground['points'])/len(ground['points'])) for k in range(3)]
    tree_center = [round(sum(p[k] for p in split['points'])/len(split['points'])) for k in range(3)]
    (out_dir/'texture_probe.h').write_text(
        '/* Authored camera landmarks used by the title tour and diagnostic probe. */\n'
        '#define PROBE_GROUND_X %d\n#define PROBE_GROUND_Y %d\n#define PROBE_GROUND_Z %d\n'
        '#define PROBE_TREE_X %d\n#define PROBE_TREE_Y %d\n#define PROBE_TREE_Z %d\n'
        % tuple(ground_center + tree_center))
    (out_dir/'texture_manifest.json').write_text(json.dumps(dict(
        mode='patches' if patches_only else 'hybrid', workshop=workshop, budget=budget.parts,
        vram_limit=budget.vram_limit, vertices=positions, faces=records, chunks=chunks,
        patches=patches, lods={str(k):v for k,v in lod_settings.get(room,{}).items()} if room else {},
        sizes=dict(collections.Counter('%dx%d' % (t['width'],t['height'])
                                                       for t in tiles.values()))), indent=2)+'\n')
    return head, positions, faces, tiles


def actor_bytes(actor):
    return sum(tile_bytes(w,h) for w,h in actor['tiles'])


def triangle_quads(group):
    """Remove the collapsed texture edge while exactly covering a triangle."""
    a,b,c = group['points']
    def mean(*points):
        return tuple(sum(v[k] for v in points)/len(points) for k in range(9))
    ab,bc,ca,center = mean(a,b),mean(b,c),mean(c,a),mean(a,b,c)
    return [dict(group,points=p,size=quads.span(p)) for p in
            ([a,ab,center,ca],[ab,b,bc,center],[center,bc,c,ca])]


def room_ground(group):
    # Imported meshes already carry the author's chosen tessellation. The
    # ROM floor heuristic can multiply a retopologized floor beyond VRAM.
    if group['tri'].get('authored_mesh'):
        return [group]
    n = quads.normal(group['points'])
    if group['kind'] != quads.BAKE or abs(n[1]) < .85*math.sqrt(sum(x*x for x in n)):
        return [group]
    if group['tri']['transparent']:
        return split_ground(group) if group['size'] > 400 else [group]
    if len(group['points']) == 3 and group['size'] > 128:
        return triangle_quads(group)
    if len(group['points']) == 4 and group['size'] > 300:
        return split_ground(group)
    return [group]


def refine_room_ground(bakes, pieces, actor, texture_budget=None):
    """Use a room's spare geometry capacity for short, regular floor patches."""
    positions = {tuple(round(x) for x in p[:3])
                 for g in bakes + [g for g,_ in pieces] for p in g['points']}
    remaining_polygons = MAX_POLYGONS-actor['polygons']-len(bakes)-len(pieces)-32
    remaining_vertices = MAX_VERTICES-actor['vertices']-len(positions)-16
    # Optional refinement must leave room for every patch's minimum texture,
    # including its palette. Geometry capacity alone is not sufficient.
    remaining_texture = (texture_budget-len(bakes)*tile_bytes(16,16)
                         if texture_budget is not None else float('inf'))
    candidates = []
    for i,g in enumerate(bakes):
        n = quads.normal(g['points'])
        if (len(g['points']) == 4 and g['size'] > 128 and
            not g['tri'].get('authored_mesh') and not g.get('retopo_drop') and
            not g['tri']['transparent'] and
            abs(n[1]) > .85*math.sqrt(sum(x*x for x in n))):
            candidates.append((g['size'],i))
    replacements = {}
    for _,i in sorted(candidates,reverse=True):
        parts = split_ground(bakes[i])
        new_positions = {tuple(round(x) for x in p[:3]) for g in parts for p in g['points']} - positions
        extra_texture=(len(parts)-1)*tile_bytes(16,16)
        if remaining_polygons < 3 or len(new_positions) > remaining_vertices or extra_texture > remaining_texture:
            continue
        replacements[i] = parts
        remaining_polygons -= 3
        remaining_vertices -= len(new_positions)
        remaining_texture -= extra_texture
        positions.update(new_positions)
    return [g for i,bake in enumerate(bakes) for g in replacements.get(i,[bake])]


def split_ground(group, divisions=2):
    """Smaller surfaces, retaining the original triangle interpolation."""
    p = group['points']
    if len(p) == 3:
        if divisions != 2:
            raise ValueError('triangle ground only supports two divisions')
        a,b,c = p
        midpoint = lambda x,y: tuple((i+j)/2 for i,j in zip(x,y))
        ab,bc,ca = midpoint(a,b),midpoint(b,c),midpoint(c,a)
        parts = ([a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca])
    else:
        parts = []
        for iy in range(divisions):
            for ix in range(divisions):
                x, y = ix/divisions, iy/divisions
                parts.append([surface_vertex(group,u,v) for u,v in
                              ((x,y),(x+1/divisions,y),
                               (x+1/divisions,y+1/divisions),
                               (x,y+1/divisions))])
    return [dict(group,points=points,size=quads.span(points)) for points in parts]
