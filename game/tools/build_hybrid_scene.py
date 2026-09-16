"""Source-UV converter: shared repeating quads plus density-budgeted bakes.

Collision is deliberately not regenerated. Render positions remain in source
space until build_sgl_scene.emit() bakes the Saturn Y conversion.
"""
import collections
import json
import math
import pathlib
import struct
import sys

from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'shared/tools'))
import build_kokiri_scene as source
import build_quads as quads
from vdp1_budget import Budget, tile_bytes

OOT_DEFAULT = pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot')


def load_faces(oot, rom_dir=None):
    segments = source.extract(oot, rom_dir)
    faces = []
    for name, data in segments.items():
        if 'room' in name:
            display = source.DisplayLists(segments['spot04_scene'], data)
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


def render_tile(group, width, height, shared=False):
    tex = group['texture']
    pixels = []
    # Shared tiles keep one coarse static light level per surface. A gradient
    # would make every repetition unique again; bake paths retain gradients.
    shades = [shade(p, group['tri']['lighting']) for p in group['points']]
    uniform = tuple(round(sum(s[k] for s in shades)/len(shades)*8)/8 for k in range(3))
    for y in range(height):
        for x in range(width):
            # Sample centres on direct/repeating tiles: sampling both ends of
            # [0,64] would duplicate texel zero and omit a texel at the seam.
            u, v = ((x+.5)/width, (y+.5)/height) if shared else (
                x/(width-1), y/(height-1))
            p = interpolate(group['points'], u, v) if shared else surface_vertex(group, u, v)
            if tex:
                s = source.coordinate(p[3], tex['scale'][0], tex['shifts'], tex['uls'],
                                      tex['cms'], tex['masks'], tex['width'])
                t = source.coordinate(p[4], tex['scale'][1], tex['shiftt'], tex['ult'],
                                      tex['cmt'], tex['maskt'], tex['height'])
                colour = tex['colors'][t*tex['width']+s]
            else:
                colour = (255, 255, 255, 255)
            light = uniform if shared else shade(p, group['tri']['lighting'])
            pixels.append(tuple(max(0, min(255, round(colour[k]*light[k]))) for k in range(3))
                          + (colour[3],))
    return quantize(pixels, width, height)


def convert(oot, head, actor, out_dir, patches_only=False, rom_dir=None):
    groups = quads.build(load_faces(oot, rom_dir))
    split = max((g for g in groups if g['kind'] == quads.SPLIT), key=lambda g:g['size'])
    ground = min((g for g in groups if g['kind'] == quads.BAKE and
                  abs(quads.normal(g['points'])[1]) > .85 * math.sqrt(sum(
                      n*n for n in quads.normal(g['points'])))),
                 key=lambda g:sum((sum(p[k] for p in g['points'])/len(g['points']) -
                                   (-300,0,0)[k])**2 for k in range(3)))
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
        if g['kind'] == quads.BAKE and g['size'] > 400 and abs(n[1]) > .85*math.sqrt(sum(x*x for x in n)):
            center = [sum(p[k] for p in g['points'])/len(g['points']) for k in range(3)]
            if not patches_only or g['source'] == ground['source']:
                candidates.append(((center[0]+300)**2+center[2]**2, i))
    selected = {i for _,i in sorted(candidates)[:50]}
    groups = [piece for i,g in enumerate(groups) for piece in (split_ground(g) if i in selected else [g])]

    positions, position_ids, faces, tiles, tile_ids, records = [], {}, [], collections.OrderedDict(), {}, []

    def add_tile(group, w, h, shared):
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
    budget.add('shared', [(t['width'], t['height']) for t in tiles.values()], 0, 0)
    # Start with 16x16 bakes. Spend remaining space on the worst *directional*
    # density, not a blanket resolution increase. Always keep a 4 KiB margin.
    available = budget.vram_limit-budget.texture_bytes-4096
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
    remaining = budget.vram_limit - sum(tile_bytes(t['width'],t['height'])
                                        for t in tiles.values()) - actor_bytes(actor) - 4096
    floors = []
    for i, (group, tile) in enumerate(pieces):
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
                            room=group['tri']['room'], indices=ids,
                            cull=face['cull'], mesh=face['mesh']))

    budget = Budget()
    budget.add('forest', [(t['width'],t['height']) for t in tiles.values()], len(faces), len(positions))
    budget.add('link', actor['tiles'], actor['polygons'], actor['vertices'])
    print(budget.report(), flush=True)
    if budget.failures():
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
        '/* Diagnostic camera only; never enabled in normal builds. */\n'
        '#define PROBE_GROUND_X %d\n#define PROBE_GROUND_Y %d\n#define PROBE_GROUND_Z %d\n'
        '#define PROBE_TREE_X %d\n#define PROBE_TREE_Y %d\n#define PROBE_TREE_Z %d\n'
        % tuple(ground_center + tree_center))
    (out_dir/'texture_manifest.json').write_text(json.dumps(dict(
        mode='patches' if patches_only else 'hybrid', budget=budget.parts,
        vram_limit=budget.vram_limit, vertices=positions, faces=records, chunks=chunks,
        patches=patches, sizes=dict(collections.Counter('%dx%d' % (t['width'],t['height'])
                                                       for t in tiles.values()))), indent=2)+'\n')
    return head, positions, faces, tiles


def actor_bytes(actor):
    return sum(tile_bytes(w,h) for w,h in actor['tiles'])


def split_ground(group):
    """Four smaller surfaces, retaining the original triangle interpolation."""
    p = group['points']
    if len(p) == 3:
        a,b,c = p
        midpoint = lambda x,y: tuple((i+j)/2 for i,j in zip(x,y))
        ab,bc,ca = midpoint(a,b),midpoint(b,c),midpoint(c,a)
        parts = ([a,ab,ca],[ab,b,bc],[ca,bc,c],[ab,bc,ca])
    else:
        parts = []
        for y in (0,.5):
            for x in (0,.5):
                parts.append([surface_vertex(group,u,v) for u,v in
                              ((x,y),(x+.5,y),(x+.5,y+.5),(x,y+.5))])
    return [dict(group,points=points,size=quads.span(points)) for points in parts]
