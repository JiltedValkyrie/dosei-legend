"""Local Hyrule Field ground retopology: square grid panels, same surface.

FIELD_SQUARE_RETOPO_PLAN.md. The ROM ground fan of object 17 around
(0,320,5100) plus its southern neighbour (obj13 src613) is re-tessellated.
Panels are the source triangles themselves, so terrain height, slope, LOD2
sampling and coplanar road/decal overlays are unchanged; only the faces change.

One XZ square grid covers the patch (a grid vertex on the fan centre, columns
on the x=0/+-1472 ridges). Each cell is clipped by every panel; a cell wholly
inside one panel stays one planar quad (an exact XZ square, a parallelogram on
the slope; metrics report how far from square). Ridges cut cells into convex
pieces; grid vertices near a ridge or corner snap onto it, so no needles. All
vertices are keyed by integer XZ, so neighbours share them (no T-junctions).

Along the patch outline the grid crossings are replaced by points ~BOUNDARY
apart; the strip next to the outline is re-triangulated, and each outside
ground neighbour is fanned from its opposite corner to those same points.
Wall/curb faces on the outline are left (reported as unsplit edges).

Rejected first attempt (squares exact in each panel's own plane): every fan
spoke forced ragged seams; at 256 only 48 of 224 pieces were squares. Evidence:
build/square-retopo/preview/rejected-per-plane/.

Collision for the patch is rebuilt from the same welded integer positions:
each quad = two triangles with a fixed 0-2 diagonal. Every replaced polygon
has the same surface/ignore/conveyor word; anything else is refused. SA.COL
(build_scene_table) and SA.OOC (oot_core_import) get identical triangles in
identical slots; build.sh checks both and the STM came from one bundle.

Offline only. Pure Python (WSL build has no numpy).
"""
import argparse
import collections
import hashlib
import json
import math
import pathlib
import re
import sys

GAME = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))
sys.path.insert(0, str(GAME.parent / 'shared/tools'))

# ROM visual source faces -> collision polygon (exact vertex-set match, checked).
PATCH = {613: 436, 738: 589, 739: 590, 740: 591, 741: 592, 742: 593,
         743: 594, 744: 595, 745: 596, 746: 597}
ROOM = 'spot00_room_0'
PATCH_NAME = 'spot00_room_0/retopo/obj17-fan'
SIZES = (368, 256, 184, 128)
GAP = .3        # interior column points keep this many squares from an edge
WELD = .2       # edge points closer than this (in squares) are merged
MIN_STRIP = .35  # the apex strip is at least this tall, else merged down
MAX_SOURCES = 16  # explicit patch bound (plan: no distant growth)
NEAR = 30       # live near threshold (nz30 in the probe rows)
FOCAL = 240     # SGL screen distance, from captured view/screen pairs
SLIVER = 12     # merge cut/band pieces with a smaller XZ angle (degrees)
BOUNDARY = 425  # target spacing of shared points on the patch outline
SNAP = .2       # grid vertices this close (in squares) to a ridge/corner move onto it

# Recorded poses: real slGetMatrix captures from Astra's tr-v10 baseline (q16;
# view = (x, -y, z) * M + T). Used for depth-span pricing and the preview.
POSES = {
    'oot-close': ([37, 185, 4353], [-16593, -11007, 62436, 0, 64540, 11377, 63400, -2881, 16340,
                                    -275397963, 28353763, -61926350]),
    'legacy-far': ([37, 185, 4353], [-16593, 0, 63400, 0, 65536, 0, 63400, 0, 16593,
                                     -275029702, 15400960, -57483626]),
    'walk30': ([-21, 170, 4338], [-16593, -11007, 62436, 0, 64540, 11377, 63400, -2881, 16340,
                                  -275410102, 26714090, -53757973]),
    'corner': ([23, 4, 3407], [-30593, 0, 57956, 0, 65536, 0, 57956, 0, 30593,
                               -193268214, 3538944, -86754082]),
    'corner-turn': ([60, 0, 3367], [46580, 11304, -44693, 0, 63535, 16070, -46100, 11421, -45158,
                                    152428260, -35817134, 173157875]),
    'center': ([1192, 328, 4114], [-14346, -11101, 62974, 0, 64540, 11377, 63946, -2491, 14127,
                                   -245478952, 48776064, -120018735]),
}


# ---------------------------------------------------------------- vectors
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def add(a, b): return tuple(x + y for x, y in zip(a, b))
def mul(a, s): return tuple(x * s for x in a)
def dot(a, b): return sum(x * y for x, y in zip(a, b))
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def length(a): return math.sqrt(dot(a, a))
def unit(a): return mul(a, 1 / length(a))
def ipos(p): return tuple(int(round(v)) for v in p[:3])


def area2(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def angles(poly):
    """Interior angles (degrees) of a 2D polygon, CCW."""
    out = []
    n = len(poly)
    for i in range(n):
        a, b, c = poly[i-1], poly[i], poly[(i+1) % n]
        u, v = sub(a, b), sub(c, b)
        lu, lv = length(u), length(v)
        if not lu or not lv:
            out.append(0.)
            continue
        cosv = max(-1., min(1., dot(u, v) / (lu * lv)))
        ang = math.degrees(math.acos(cosv))
        out.append(ang if area2(a, b, c) >= 0 else 360 - ang)
    return out


# ---------------------------------------------------------------- source
def load_source(oot, rom_dir):
    import build_hybrid_scene as hybrid
    import build_kokiri_scene as source
    faces = hybrid.load_faces(oot, rom_dir, prefix='spot00')
    segments = source.extract(oot, rom_dir, prefix='spot00')
    return faces, segments


def face_hash(face):
    """Stable identity of a ROM face: positions, UVs, shading, texture address."""
    tex = face['texture'] or {}
    data = [[round(v, 4) for v in p] for p in face['vertices']]
    key = json.dumps([data, tex.get('address'), tex.get('width'), tex.get('height'),
                      list(face['prim']), face['lighting'], face['cull'], face['transparent'],
                      face['object']])
    return hashlib.sha256(key.encode()).hexdigest()


def collision_hash(polys):
    return hashlib.sha256(json.dumps([[list(map(list, p['vertices'])), p['surface'], p['ignore'],
                                       p['conveyor']] for p in polys]).encode()).hexdigest()


def check_patch(faces, collision):
    """Verify every patch face/poly pairing and the uniform surface word."""
    errors = []
    for src, poly in PATCH.items():
        face = faces[src]
        if face['room'] != ROOM:
            errors.append('source %d not in %s' % (src, ROOM))
        vs = {ipos(v) for v in face['vertices']}
        cs = {tuple(v) for v in collision['polys'][poly]['vertices']}
        if vs != cs:
            errors.append('source %d does not match collision poly %d' % (src, poly))
        order = [ipos(v) for v in face['vertices']]
        corder = [tuple(v) for v in collision['polys'][poly]['vertices']]
        if order != corder:
            errors.append('source %d winding differs from poly %d' % (src, poly))
    words = {(collision['polys'][p]['surface'], collision['polys'][p]['ignore'],
              collision['polys'][p]['conveyor']) for p in PATCH.values()}
    if len(words) != 1:
        errors.append('patch mixes surface words %s; split at that boundary' % sorted(words))
    if len(PATCH) > MAX_SOURCES:
        errors.append('patch exceeds %d source faces' % MAX_SOURCES)
    if errors:
        raise ValueError('; '.join(errors))
    return words.pop()


# ---------------------------------------------------------------- panels
def edge_key(a, b):
    a, b = ipos(a), ipos(b)
    return (a, b) if a < b else (b, a)


def panel_edges(face):
    v = [ipos(p) for p in face['vertices']]
    return [edge_key(v[i], v[(i+1) % 3]) for i in range(3)]


class Panel:
    """One source triangle: its exact plane over XZ and its XZ outline."""

    def __init__(self, src, face):
        self.src, self.face = src, face
        self.pts = [ipos(p) for p in face['vertices']]
        n = cross(sub(self.pts[1], self.pts[0]), sub(self.pts[2], self.pts[0]))
        if abs(n[1]) <= .85 * length(n):
            raise ValueError('source %d is not ground (slope over 32 degrees)' % src)
        self.n, self.d = n, dot(n, self.pts[0])
        xz = [(p[0], p[2]) for p in self.pts]
        # Pieces are built CCW in (x, z); flip restores the source winding.
        self.flip = area_poly(xz) < 0
        self.xz = xz[::-1] if self.flip else xz
        self.edges = panel_edges(face)

    def y(self, x, z):
        return (self.d - self.n[0]*x - self.n[2]*z) / self.n[1]

    def on_edge(self, x, z, tol=1e-6):
        """The 3D source edge through XZ point (x, z), if any."""
        for a, b in self.edges:
            d = (b[0]-a[0], b[2]-a[2])
            t = ((x-a[0])*d[0] + (z-a[2])*d[1]) / (d[0]*d[0] + d[1]*d[1])
            if -tol <= t <= 1 + tol and abs((x-a[0])*d[1] - (z-a[2])*d[0]) <= tol * length(d):
                return (a, b), t
        return None, None


class Point:
    """One output vertex, shared by every piece that uses its integer XZ."""
    __slots__ = ('pos', 'key')

    def __init__(self, key, pos): self.key, self.pos = key, pos


class Registry:
    def __init__(self): self.points = {}

    def get(self, x, z, panel):
        key = (int(round(x)), int(round(z)))
        if key not in self.points:
            edge, t = panel.on_edge(x, z)
            # On a ridge both planes agree only along the 3D edge itself.
            y = (edge[0][1] + (edge[1][1]-edge[0][1]) * t) if edge else panel.y(x, z)
            self.points[key] = Point(key, (float(key[0]), float(round(y)), float(key[1])))
        return self.points[key]

    def on(self, a, b, t):
        """A point at parameter t along the 3D edge a->b."""
        x, z = a[0] + (b[0]-a[0]) * t, a[2] + (b[2]-a[2]) * t
        key = (int(round(x)), int(round(z)))
        if key not in self.points:
            self.points[key] = Point(key, (float(key[0]), float(round(a[1] + (b[1]-a[1]) * t)),
                                           float(key[1])))
        return self.points[key]


def xz(pt): return (pt.pos[0], pt.pos[2])


def clip(poly, x0, x1, z0, z1):
    """Convex XZ polygon clipped to an axis-aligned cell (Sutherland-Hodgman)."""
    for axis, bound, low in ((0, x0, True), (0, x1, False), (1, z0, True), (1, z1, False)):
        if low:
            keep = lambda p, axis=axis, bound=bound: p[axis] >= bound - 1e-9
        else:
            keep = lambda p, axis=axis, bound=bound: p[axis] <= bound + 1e-9
        out = []
        for i in range(len(poly)):
            p, q = poly[i-1], poly[i]
            if keep(q):
                if not keep(p):
                    out.append(cut(p, q, axis, bound))
                out.append(q)
            elif keep(p):
                out.append(cut(p, q, axis, bound))
        poly = out
        if not poly:
            return []
    return poly


def cut(p, q, axis, bound):
    t = (bound - p[axis]) / (q[axis] - p[axis])
    r = [p[0] + (q[0]-p[0]) * t, p[1] + (q[1]-p[1]) * t]
    r[axis] = bound
    return tuple(r)


def snap_grid(panels, size, origin):
    """Grid vertices within SNAP of a source corner or ridge, moved onto it.

    Without this a ridge passing just beside a grid vertex leaves a needle
    piece. A moved vertex makes its cells ordinary convex quads, not squares.
    """
    gx, gz = origin
    corners = {(q[0], q[2]) for p in panels.values() for q in p.pts}
    edges = {e for p in panels.values() for e in p.edges}
    xs = [c[0] for c in corners]
    zs = [c[1] for c in corners]
    limit = SNAP * size
    out = {}
    for i in range(math.floor((min(xs)-gx)/size) - 1, math.ceil((max(xs)-gx)/size) + 2):
        for j in range(math.floor((min(zs)-gz)/size) - 1, math.ceil((max(zs)-gz)/size) + 2):
            v = (gx + i*size, gz + j*size)
            near = min(corners, key=lambda c: math.dist(c, v))
            if math.dist(near, v) <= limit:
                if near != v:
                    out[(i, j)] = near
                continue
            best = None
            for a, b in edges:
                a2, b2 = (a[0], a[2]), (b[0], b[2])
                d = (b2[0]-a2[0], b2[1]-a2[1])
                t = ((v[0]-a2[0])*d[0] + (v[1]-a2[1])*d[1]) / (d[0]*d[0] + d[1]*d[1])
                if not 0 < t < 1:
                    continue
                q = (a2[0] + d[0]*t, a2[1] + d[1]*t)
                dist = math.dist(q, v)
                if dist > 1e-9 and dist <= limit and (best is None or dist < best[0]):
                    best = (dist, q)
            if best:
                out[(i, j)] = best[1]
    return out


def clip_convex(poly, clipper):
    """Convex polygon clipped by a convex CCW polygon (Sutherland-Hodgman)."""
    for k in range(len(clipper)):
        a, b = clipper[k], clipper[(k+1) % len(clipper)]
        side = lambda p, a=a, b=b: area2(a, b, p)
        out = []
        for i in range(len(poly)):
            p, q = poly[i-1], poly[i]
            sp, sq = side(p), side(q)
            if sq >= -1e-9:
                if sp < -1e-9:
                    out.append(lerp2(p, q, sp / (sp - sq)))
                out.append(q)
            elif sp >= -1e-9:
                out.append(lerp2(p, q, sp / (sp - sq)))
        poly = out
        if not poly:
            return []
    return poly


def lerp2(p, q, t):
    return (p[0] + (q[0]-p[0]) * t, p[1] + (q[1]-p[1]) * t)


# ---------------------------------------------------------------- tessellation
def tessellate(faces, size, boundary=425, sources=None, origin=(0, 5100)):
    """Shared XZ square grid, clipped at every source ridge.

    `origin` puts a grid vertex on the fan centre and grid columns on the
    x=0 / x=+-1472 ridges. Pieces fully inside one panel are planar
    parallelograms whose XZ footprint is the grid square. Along the outer
    boundary the grid crossings are replaced by points about `boundary`
    apart, so outside neighbours fan into a few wide triangles, not needles.
    """
    sources = sorted(sources or PATCH)
    panels = {s: Panel(s, faces[s]) for s in sources}
    owners = collections.defaultdict(list)
    for s, p in panels.items():
        for e in p.edges:
            owners[e].append(s)
    outer = {e for e, o in owners.items() if len(o) == 1}
    reg = Registry()
    pieces = collections.defaultdict(list)
    gx, gz = origin
    snapped = snap_grid(panels, size, origin)

    def grid(i, j):
        return snapped.get((i, j), (gx + i*size, gz + j*size))
    for s, p in panels.items():
        xs = [q[0] for q in p.xz]
        zs = [q[1] for q in p.xz]
        for i in range(math.floor((min(xs)-gx)/size) - 1, math.ceil((max(xs)-gx)/size) + 1):
            for j in range(math.floor((min(zs)-gz)/size) - 1, math.ceil((max(zs)-gz)/size) + 1):
                cell = [grid(i, j), grid(i+1, j), grid(i+1, j+1), grid(i, j+1)]
                poly = clip_convex(p.xz, cell)
                pts = dedupe([reg.get(x, z, p) for x, z in poly])
                if len(pts) < 3 or area_poly([xz(q) for q in pts]) < 1:
                    continue
                square = all(k not in snapped for k in ((i, j), (i+1, j), (i+1, j+1), (i, j+1)))
                full = square and len(pts) == 4 and {q.key for q in pts} == {
                    (int(round(c[0])), int(round(c[1]))) for c in cell}
                pieces[s].append(dict(source=s, kind='square' if full else 'cut', points=pts))
    # Outer boundary: equally spaced shared points per outline edge.
    kept = {}
    for e in outer:
        if boundary:
            # Vertices other faces already have inside this edge (curb lip at
            # 4330, say) are kept first, closing those pre-existing T-junctions.
            extra = sorted({t for t in edge_vertices(faces, e, sources)}, key=float)
            n = max(0, round(length(sub(e[1], e[0])) / boundary) - 1)
            spaced = [k / (n + 1) for k in range(1, n + 1)]
            span = length(sub(e[1], e[0]))
            ts = extra + [t for t in spaced if all(abs(t - x) * span > boundary / 3 for x in extra)]
            kept[e] = [reg.on(e[0], e[1], t) for t in sorted(ts)]
        else:
            kept[e] = None
    exceptions = []
    out = []
    for s, p in panels.items():
        mine = [e for e in p.edges if e in outer and kept[e] is not None]
        if not mine:
            out.extend(pieces[s])
            continue
        ends = {(a[0], a[2]) for e in mine for a in e}

        def touches(piece, mine=mine, ends=ends):
            return any(q.key in ends or any(on_segment(xz(q), e) for e in mine)
                       for q in piece['points'])
        band = [q for q in pieces[s] if touches(q)]
        rest = [q for q in pieces[s] if not touches(q)]
        loops = union_loops(band)
        if len(loops) != 1:
            exceptions.append(dict(kind='band-not-simple', source=s, loops=len(loops)))
            out.extend(pieces[s])
            continue
        loop = rebuild_loop(loops[0], mine, kept)
        out.extend(rest)
        out.extend(polygon_pieces(loop, s, 'band'))
    pieces = []
    for piece in out:
        if piece['kind'] == 'cut':
            pieces.extend(polygon_pieces(piece['points'], piece['source'], 'cut'))
        else:
            pieces.append(piece)
    pieces, slivers = clean_slivers(pieces)
    exceptions.extend(dict(kind='sliver', source=q['source'], angle=round(a, 2)) for q, a in slivers)
    for piece in pieces:
        if panels[piece['source']].flip:
            piece['points'] = piece['points'][::-1]
    if not boundary:
        kept = {e: sorted({q.key: q for piece in pieces for q in piece['points']
                           if on_segment(xz(q), e)}.values(),
                          key=lambda q: dot(sub(q.pos, e[0]), sub(e[1], e[0])))
                for e in outer}
    boundary_pts = [(e, list(enumerate(kept[e]))) for e in outer]
    return dict(size=size, pieces=pieces, panels=panels, owners=owners, outer=outer,
                boundary=boundary_pts, exceptions=exceptions,
                t_junctions=t_junctions(pieces), registry=reg)


def min_angle(piece):
    return min(angles([xz(q) for q in piece['points']]))


def clean_slivers(pieces, limit=SLIVER):
    """Merge a thin ridge/band piece into a same-panel neighbour, then re-split.

    Returns (pieces, [(piece, angle)] still under the limit)."""
    pieces = list(pieces)
    tried = set()
    while True:
        bad = sorted(((min_angle(q), i) for i, q in enumerate(pieces)
                      if q['kind'] != 'square' and id(q) not in tried), key=lambda x: x[0])
        bad = [b for b in bad if b[0] < limit]
        if not bad:
            break
        angle, i = bad[0]
        piece = pieces[i]
        keys = {(a.key, b.key) for a, b in zip(piece['points'], piece['points'][1:] + piece['points'][:1])}
        best = None
        for k, other in enumerate(pieces):
            if k == i or other['source'] != piece['source']:
                continue
            pts = other['points']
            if not any((b.key, a.key) in keys for a, b in zip(pts, pts[1:] + pts[:1])):
                continue
            loops = union_loops([piece, other])
            if len(loops) != 1 or loops[0] is None:
                continue
            try:
                parts = polygon_pieces(loops[0], piece['source'], 'cut')
            except ValueError:
                continue
            score = min(min_angle(q) for q in parts)
            if score > angle and (best is None or score > best[0]):
                best = (score, k, parts)
        if best is None:
            tried.add(id(piece))
            continue
        _, k, parts = best
        pieces = [q for n, q in enumerate(pieces) if n not in (i, k)] + parts
    return pieces, [(q, min_angle(q)) for q in pieces if q['kind'] != 'square' and min_angle(q) < limit]


def on_segment(p, e, tol=.75):
    a, b = (e[0][0], e[0][2]), (e[1][0], e[1][2])
    d = (b[0]-a[0], b[1]-a[1])
    L2 = d[0]*d[0] + d[1]*d[1]
    t = ((p[0]-a[0])*d[0] + (p[1]-a[1])*d[1]) / L2
    if t <= 1e-9 or t >= 1 - 1e-9:
        return False
    return abs((p[0]-a[0])*d[1] - (p[1]-a[1])*d[0]) / math.sqrt(L2) <= tol


def union_loops(pieces):
    edges = {}
    for piece in pieces:
        pts = piece['points']
        for i in range(len(pts)):
            edges[(pts[i].key, pts[(i+1) % len(pts)].key)] = pts[(i+1) % len(pts)]
    nxt = collections.defaultdict(list)
    for (a, b), pb in edges.items():
        if (b, a) not in edges:
            nxt[a].append(pb)
    if any(len(v) != 1 for v in nxt.values()):
        return [None, None]
    loops, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        loop, cur = [], start
        while cur not in seen:
            seen.add(cur)
            pt = nxt[cur][0]
            loop.append(pt)
            cur = pt.key
        loops.append(loop[-1:] + loop[:-1])
    return loops


def rebuild_loop(loop, edges, kept):
    """Replace every crossing on an outer edge by that edge's kept points."""
    out = [q for q in loop if not any(on_segment(xz(q), e) for e in edges)]
    final = []
    for i, q in enumerate(out):
        final.append(q)
        r = out[(i+1) % len(out)]
        for e in edges:
            ends = [(a[0], a[2]) for a in e]
            if {q.key, r.key} == set(ends):
                final.extend(kept[e] if q.key == ends[0] else kept[e][::-1])
    return final


def t_junctions(pieces, tol=.75):
    """Vertices lying strictly inside another piece's edge (raster-crack risk)."""
    points = {q.key for piece in pieces for q in piece['points']}
    grid = collections.defaultdict(list)
    for k in points:
        grid[(k[0] // 64, k[1] // 64)].append(k)
    hits = []
    for piece in pieces:
        pts = piece['points']
        for i in range(len(pts)):
            a, b = pts[i].key, pts[(i+1) % len(pts)].key
            e = ((a[0], 0, a[1]), (b[0], 0, b[1]))
            for gx_ in range(min(a[0], b[0]) // 64 - 1, max(a[0], b[0]) // 64 + 2):
                for gz_ in range(min(a[1], b[1]) // 64 - 1, max(a[1], b[1]) // 64 + 2):
                    for k in grid.get((gx_, gz_), ()):
                        if k not in (a, b) and on_segment(k, e, tol):
                            hits.append((piece['source'], a, b, k))
    return hits


def dedupe(poly):
    out = []
    for q in poly:
        if not out or out[-1] is not q:
            out.append(q)
    while len(out) > 1 and out[0] is out[-1]:
        out.pop()
    return out


def polygon_pieces(poly, src, kind):
    """Triangulate (max-min-angle DP) then pair triangles into convex quads."""
    poly = dedupe(poly)
    pts2 = [xz(q) for q in poly]
    if len(poly) < 3 or area_poly(pts2) <= 0:
        raise ValueError('source %d: %s polygon has no positive area' % (src, kind))
    if len(poly) == 3 or (len(poly) == 4 and quad_ok(pts2)):
        return [dict(source=src, kind=kind, points=poly)]
    tris = triangulate(pts2)
    used, out, cands = set(), [], []
    for i in range(len(tris)):
        for k in range(i + 1, len(tris)):
            quad = merge(tris[i], tris[k])
            if quad and quad_ok([pts2[v] for v in quad]):
                cands.append((min(angles([pts2[v] for v in quad])), i, k, quad))
    for _, i, k, quad in sorted(cands, reverse=True):
        if i in used or k in used:
            continue
        used.update((i, k))
        out.append(dict(source=src, kind=kind, points=[poly[v] for v in quad]))
    out.extend(dict(source=src, kind=kind, points=[poly[v] for v in t])
               for i, t in enumerate(tris) if i not in used)
    return out


def area_poly(pts):
    return sum(pts[i][0]*pts[(i+1) % len(pts)][1] - pts[(i+1) % len(pts)][0]*pts[i][1]
               for i in range(len(pts))) / 2


def quad_ok(q, low=25, high=155):
    if len(q) != 4:
        return False
    a = angles(q)
    return all(low <= x <= high for x in a) and area_poly(q) > 0


def triangulate(pts):
    """Simple CCW polygon -> triangles maximising the smallest angle."""
    n = len(pts)
    ok = [[False] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            if j - i == 1 or (i == 0 and j == n - 1):
                ok[i][j] = True
                continue
            a, b = pts[i], pts[j]
            if not inside(((a[0]+b[0])/2, (a[1]+b[1])/2), pts):
                continue
            ok[i][j] = not any(segments_cross(a, b, pts[k], pts[(k+1) % n]) for k in range(n)
                               if len({i, j, k, (k+1) % n}) == 4)
    best = {}
    for gap in range(2, n):
        for i in range(0, n - gap):
            j = i + gap
            result = (-1., None)
            for k in range(i + 1, j):
                if not ok[i][k] or not ok[k][j] or area2(pts[i], pts[k], pts[j]) <= 1e-6:
                    continue
                left = best[(i, k)] if k - i > 1 else (180., [])
                right = best[(k, j)] if j - k > 1 else (180., [])
                if left[1] is None or right[1] is None:
                    continue
                score = min(min(angles([pts[i], pts[k], pts[j]])), left[0], right[0])
                if score > result[0]:
                    result = (score, left[1] + right[1] + [(i, k, j)])
            best[(i, j)] = result
    score, tris = best[(0, n - 1)]
    if tris is None:
        raise ValueError('polygon could not be triangulated')
    return tris


def inside(p, poly):
    c = False
    for i in range(len(poly)):
        a, b = poly[i], poly[(i+1) % len(poly)]
        if (a[1] > p[1]) != (b[1] > p[1]):
            x = a[0] + (p[1]-a[1]) * (b[0]-a[0]) / (b[1]-a[1])
            if p[0] < x:
                c = not c
    return c


def segments_cross(a, b, c, d):
    d1, d2 = area2(a, b, c), area2(a, b, d)
    d3, d4 = area2(c, d, a), area2(c, d, b)
    return d1 * d2 < -1e-9 and d3 * d4 < -1e-9


def merge(t1, t2):
    shared = set(t1) & set(t2)
    if len(shared) != 2:
        return None
    a = next(v for v in t1 if v not in shared)
    b = next(v for v in t2 if v not in shared)
    i = t1.index(a)
    s1, s2 = t1[(i+1) % 3], t1[(i+2) % 3]
    return [a, s1, b, s2]


# ---------------------------------------------------------------- outputs
def attributes(face, pos):
    """Full 9-tuple at pos from the parent face's own (affine) mapping."""
    import build_hybrid_scene as hybrid
    w = hybrid.barycentric(pos, face['vertices'])
    if w is None:
        raise ValueError('degenerate parent face')
    v = face['vertices']
    return tuple(pos[:3]) + tuple(sum(wi * q[k] for wi, q in zip(w, v)) for k in range(3, 9))


def segment_t(p, e, tol=1.):
    """Parameter of 3D point p strictly inside segment e, or None."""
    a, b = e
    d = sub(b, a)
    t = dot(sub(p, a), d) / dot(d, d)
    if not 1e-6 < t < 1 - 1e-6:
        return None
    return t if length(sub(p, add(a, mul(d, t)))) <= tol else None


def edge_vertices(faces, e, sources):
    """Parameters of non-patch room vertices lying inside outline edge e."""
    out = set()
    for i, f in enumerate(faces):
        if f['room'] != ROOM or i in sources:
            continue
        for v in f['vertices']:
            t = segment_t(ipos(v), e)
            if t is not None:
                out.add(round(t, 9))
    return out


def neighbour_splits(faces, result):
    """Every outside face with an edge on (or collinear inside) the outline is
    fanned to the shared outline points: ground, curb risers and walls alike,
    each in its own plane with its own UVs and flags. Visual only; collision
    T-junctions are harmless and stay untouched."""
    patch = set(PATCH)
    splits, left = collections.defaultdict(list), []
    for key, pts in result['boundary']:
        pts = [pt for _, pt in pts]
        used = False
        for i, f in enumerate(faces):
            if f['room'] != ROOM or i in patch:
                continue
            v = [ipos(p) for p in f['vertices']]
            for k in range(3):
                p, q = v[k], v[(k+1) % 3]
                on = lambda x: x in key or segment_t(x, key) is not None
                if not (on(p) and on(q)):
                    continue
                used = True
                inside = [pt for pt in pts if segment_t(ipos(pt.pos), (p, q)) is not None]
                if inside:
                    splits[i].append(dict(edge=(p, q), points=inside))
        if pts and not used:
            left.append(dict(face=None, edge=key, points=len(pts), reason='no visual face shares this edge'))
    return splits, left


def fan(face, edge_splits):
    """Triangles of an outside face fanned to inserted boundary points."""
    verts = [tuple(v) for v in face['vertices']]
    if len(edge_splits) != 1:
        raise ValueError('outside face borders the patch on %d edges' % len(edge_splits))
    split = edge_splits[0]
    ring = []
    for k in range(3):
        a, b = verts[k], verts[(k+1) % 3]
        ring.append(a)
        if {ipos(a), ipos(b)} == set(split['edge']):
            d = sub(b[:3], a[:3])
            for pt in sorted(split['points'], key=lambda pt: dot(sub(pt.pos, a[:3]), d)):
                t = dot(sub(pt.pos, a[:3]), d) / dot(d, d)
                ring.append(tuple(pt.pos) + tuple(a[k2] + (b[k2]-a[k2])*t for k2 in range(3, 9)))
    apex = next(v for v in verts if ipos(v) not in split['edge'])
    i = ring.index(apex)
    ring = ring[i:] + ring[:i]
    return [[ring[0], ring[k], ring[k+1]] for k in range(1, len(ring) - 1)]


def build(faces, collision, size, boundary=BOUNDARY):
    word = check_patch(faces, collision)
    result = tessellate(faces, size, boundary)
    splits, left = neighbour_splits(faces, result)
    out_faces = []
    for piece in result['pieces']:
        face = faces[piece['source']]
        corners = [attributes(face, ipos(q.pos)) for q in piece['points']]
        out_faces.append(dict(source=piece['source'], kind=piece['kind'], vertices=corners))
    fans = {}
    for i, edges in splits.items():
        fans[i] = [[tuple(map(float, ipos(v))) + tuple(v[3:]) for v in tri]
                   for tri in fan(faces[i], edges)]
    return dict(size=size, boundary=boundary, word=word, result=result, faces=out_faces,
                fans=fans, left=left)


def collision_triangles(model):
    """Two triangles per quad (fixed 0-2 diagonal), source winding kept."""
    tris = []
    for f in model['faces']:
        v = [ipos(p) for p in f['vertices']]
        tris.extend([v] if len(v) == 3 else [[v[0], v[1], v[2]], [v[0], v[2], v[3]]])
    return tris


# ---------------------------------------------------------------- metrics
def view(matrix, p):
    x, y, z = p[0], -p[1], p[2]
    return tuple((x*matrix[a] + y*matrix[3+a] + z*matrix[6+a] + matrix[9+a]) / 65536 for a in range(3))


def near_pixels(matrix, polys):
    """Screen pixels covered by faces that cross the near plane.

    Risk measure: if SGL rejects a face with any corner behind near, this
    area shows sky instead of floor. Not proof that SGL drops every such face.
    """
    total = 0.
    for verts in polys:
        v = [view(matrix, p) for p in verts]
        if min(q[2] for q in v) >= NEAR or max(q[2] for q in v) < NEAR:
            continue
        front = []
        for i in range(len(v)):
            a, b = v[i-1], v[i]
            if (a[2] >= NEAR) != (b[2] >= NEAR):
                t = (NEAR - a[2]) / (b[2] - a[2])
                front.append(tuple(a[k] + (b[k]-a[k]) * t for k in range(3)))
            if b[2] >= NEAR:
                front.append(b)
        scr = [(q[0] * FOCAL / q[2], q[1] * FOCAL / q[2]) for q in front]
        scr = clip(scr, -160, 160, -120, 120) if len(scr) >= 3 else []
        if len(scr) >= 3:
            total += abs(area_poly(scr))
    return round(total)


def metrics(model, faces):
    out = dict(size=model['size'])
    kinds = collections.Counter(f['kind'] for f in model['faces'])
    out['faces'] = dict(kinds)
    out['quads'] = sum(len(f['vertices']) == 4 for f in model['faces'])
    out['triangles'] = sum(len(f['vertices']) == 3 for f in model['faces'])
    sq = [f for f in model['faces'] if f['kind'] == 'square']
    xz_err = side_ratio = angle_err = planar = 0.
    for f in sq:
        p = [ipos(v) for v in f['vertices']]
        xz_err = max(xz_err, max(abs(abs(p[(i+1) % 4][k] - p[i][k]) - (model['size'] if
                                     p[(i+1) % 4][k] != p[i][k] else 0))
                                 for i in range(4) for k in (0, 2)))
        sides = [length(sub(p[(i+1) % 4], p[i])) for i in range(4)]
        side_ratio = max(side_ratio, max(sides) / min(sides) - 1)
        for i in range(4):
            u, w = sub(p[i-1], p[i]), sub(p[(i+1) % 4], p[i])
            angle_err = max(angle_err, abs(90 - math.degrees(math.acos(
                max(-1, min(1, dot(u, w) / (length(u) * length(w))))))))
        n = unit(cross(sub(p[1], p[0]), sub(p[3], p[0])))
        planar = max(planar, abs(dot(sub(p[2], p[0]), n)))
    # XZ footprints are exact grid squares; in 3D they are planar
    # parallelograms on the source slope, so report how far from square.
    out['square_xz_error'] = xz_err
    out['square_side_ratio_pct'] = round(100 * side_ratio, 2)
    out['square_angle_error_deg'] = round(angle_err, 3)
    out['square_planarity'] = round(planar, 3)
    out['t_junctions'] = len(model['result']['t_junctions'])
    worst_t = 180.
    worst_q = (180., 0.)
    height_err = 0.
    area_new = 0.
    for f in model['faces']:
        p = [ipos(v) for v in f['vertices']]
        parent = faces[f['source']]
        pn = unit(cross(sub(parent['vertices'][1][:3], parent['vertices'][0][:3]),
                        sub(parent['vertices'][2][:3], parent['vertices'][0][:3])))
        for q in p:
            height_err = max(height_err, abs(dot(sub(q, parent['vertices'][0][:3]), pn)))
        e1 = unit(sub(p[1], p[0]))
        e2 = unit(cross(pn, e1))
        q2 = [(dot(sub(q, p[0]), e1), dot(sub(q, p[0]), e2)) for q in p]
        a = angles(q2)
        if dot(cross(sub(p[1], p[0]), sub(p[2], p[0])), pn) <= 0:
            raise ValueError('piece of source %d flipped winding' % f['source'])
        area_new += abs(area_poly(q2))
        if len(p) == 3:
            worst_t = min(worst_t, min(a))
        else:
            worst_q = (min(worst_q[0], min(a)), max(worst_q[1], max(a)))
    out['worst_triangle_angle_deg'] = round(worst_t, 2)
    out['worst_quad_angles_deg'] = [round(x, 2) for x in worst_q]
    out['max_plane_distance'] = round(height_err, 3)
    area_old = 0.
    for s in PATCH:
        v = [ipos(x) for x in faces[s]['vertices']]
        area_old += length(cross(sub(v[1], v[0]), sub(v[2], v[0]))) / 2
    out['area_old'], out['area_new'] = round(area_old), round(area_new)
    out['fans'] = {str(i): len(t) for i, t in model['fans'].items()}
    fan_min = 180.
    for tris in model['fans'].values():
        for t in tris:
            p = [v[:3] for v in t]
            e1 = unit(sub(p[1], p[0]))
            n = unit(cross(sub(p[1], p[0]), sub(p[2], p[0])))
            e2 = cross(n, e1)
            fan_min = min(fan_min, min(angles([(dot(sub(q, p[0]), e1), dot(sub(q, p[0]), e2)) for q in p])))
    out['fan_worst_angle_deg'] = round(fan_min, 2) if model['fans'] else None
    out['fan_added_faces'] = sum(len(t) - 1 for t in model['fans'].values())
    out['net_visual_faces'] = len(model['faces']) - len(PATCH) + out['fan_added_faces']
    out['collision_triangles'] = len(collision_triangles(model))
    out['collision_net'] = out['collision_triangles'] - len(PATCH)
    out['unsplit_boundary'] = model['left']
    out['exceptions'] = model['result']['exceptions']
    depth = {}
    for name, (_, matrix) in POSES.items():
        ratios, near, visible = [], 0, 0
        for f in model['faces']:
            z = [view(matrix, v)[2] for v in f['vertices']]
            if max(z) < NEAR:
                continue
            visible += 1
            if min(z) < NEAR:
                near += 1
                continue
            ratios.append(max(z) / min(z))
        old = []
        for s in PATCH:
            z = [view(matrix, v)[2] for v in faces[s]['vertices']]
            old.append('near' if min(z) < NEAR <= max(z) else round(max(z) / min(z), 2) if min(z) >= NEAR else 'behind')
        depth[name] = dict(in_front=visible, crossing_near=near,
                           near_screen_px=near_pixels(matrix, [f['vertices'] for f in model['faces']]),
                           original_near_screen_px=near_pixels(matrix, [faces[s]['vertices'] for s in PATCH]),
                           worst_ratio=round(max(ratios), 2) if ratios else None,
                           median_ratio=round(sorted(ratios)[len(ratios)//2], 3) if ratios else None,
                           original=old)
    out['depth'] = depth
    return out


# ---------------------------------------------------------------- preview
def preview(model, faces, collision, path_top, path_view, pose='oot-close'):
    from PIL import Image, ImageDraw
    import build_field_chunks as chunks
    pts = [ipos(v) for f in model['faces'] for v in f['vertices']]
    x0, x1 = min(p[0] for p in pts) - 600, max(p[0] for p in pts) + 600
    z0, z1 = min(p[2] for p in pts) - 600, max(p[2] for p in pts) + 600
    scale = 900 / max(x1 - x0, z1 - z0)
    W, H = int((x1 - x0) * scale) + 1, int((z1 - z0) * scale) + 1
    img = Image.new('RGB', (W, H), (24, 24, 28))
    d = ImageDraw.Draw(img)
    to = lambda p: ((p[0] - x0) * scale, (z1 - p[2]) * scale)
    surf_colour = {}
    palette = [(70, 120, 70), (140, 110, 60), (90, 90, 150), (150, 70, 70), (120, 120, 120), (60, 130, 140)]
    for i, poly in enumerate(collision['polys']):
        v = poly['vertices']
        if not any(x0 <= q[0] <= x1 and z0 <= q[2] <= z1 for q in v):
            continue
        key = (poly['surface'], poly['ignore'], poly['conveyor'])
        c = surf_colour.setdefault(key, palette[len(surf_colour) % len(palette)])
        d.polygon([to(q) for q in v], fill=tuple(x // 2 for x in c), outline=c)
    colours = dict(square=(110, 200, 110), cut=(230, 180, 70), band=(200, 120, 200), fan=(90, 160, 230))
    for f in model['faces']:
        d.polygon([to(v) for v in f['vertices']], fill=colours[f['kind']], outline=(10, 10, 10))
    for tris in model['fans'].values():
        for t in tris:
            d.polygon([to(v) for v in t], outline=colours['fan'])
    for e in model['left']:
        d.line([to(e['edge'][0]), to(e['edge'][1])], fill=(255, 60, 60), width=3)
    # Field cell (piece) borders: origin = min x/z over every room vertex.
    room = [ipos(v) for f in faces if f['room'] == ROOM for v in f['vertices']]
    ox, oz = min(p[0] for p in room), min(p[2] for p in room)
    step = 1 << chunks.CELL_SHIFT
    gx = ox + ((x0 - ox) // step) * step
    while gx <= x1:
        d.line([to((gx, 0, z0)), to((gx, 0, z1))], fill=(220, 220, 255), width=1)
        gx += step
    gz = oz + ((z0 - oz) // step) * step
    while gz <= z1:
        d.line([to((x0, 0, gz)), to((x1, 0, gz))], fill=(220, 220, 255), width=1)
        gz += step
    for name, (link, _) in POSES.items():
        x, y = to(link)
        d.ellipse([x - 4, y - 4, x + 4, y + 4], outline=(255, 255, 255))
        d.text((x + 6, y - 6), name, fill=(255, 255, 255))
    d.text((6, 6), 'size %d: squares green, ridge cuts amber, boundary band violet, outside fans blue, '
           'unsplit wall/curb edges red; collision surfaces dim' % model['size'], fill=(255, 255, 255))
    img.save(path_top)
    # Oblique wireframe from a recorded camera, both geometries.
    _, matrix = POSES[pose]
    img = Image.new('RGB', (640, 480), (24, 24, 28))
    d = ImageDraw.Draw(img)

    def proj(p):
        v = view(matrix, p)
        return (320 + v[0] * FOCAL * 2 / v[2], 240 + v[1] * FOCAL * 2 / v[2]) if v[2] >= NEAR else None
    polys = []
    for f in model['faces']:
        polys.append((f['vertices'], colours[f['kind']]))
    for s in PATCH:
        polys.append((faces[s]['vertices'], (255, 80, 80)))
    for verts, c in polys:
        q = [proj(v) for v in verts]
        if None in q:
            continue
        d.polygon(q, outline=c)
    d.text((6, 6), '%s camera: new pieces (colour) over original fan (red)' % pose, fill=(255, 255, 255))
    img.save(path_view)


# ---------------------------------------------------------------- bundle
def bundle_files(model, faces, collision):
    """Frozen geometry for the layout patch (content-addressed by map_meshes)."""
    def vert(v):
        return [int(round(x)) for x in v[:3]] + [round(x, 6) for x in v[3:]]
    data = dict(
        version=1, room=ROOM, size=model['size'], boundary=model['boundary'],
        sources={str(s): face_hash(faces[s]) for s in sorted(PATCH)},
        collision={str(p): s for s, p in sorted(PATCH.items())},
        collision_sha256=collision_hash([collision['polys'][p] for p in sorted(PATCH.values())]),
        surface=list(model['word']),
        faces=[dict(source=f['source'], kind=f['kind'], vertices=[vert(v) for v in f['vertices']])
               for f in model['faces']],
        fans={str(i): dict(source_sha256=face_hash(faces[i]),
                           triangles=[[vert(v) for v in t] for t in tris])
              for i, tris in sorted(model['fans'].items())},
        collision_triangles=collision_triangles(model))
    return {'patch.json': json.dumps(data, indent=1) + '\n'}


def store_bundle(files, game=GAME):
    """Publish an immutable bundle folder; identity = map_meshes.fingerprint."""
    import shutil
    import tempfile
    from map_meshes import fingerprint, bundle_path
    root = pathlib.Path(game) / 'assets/layouts/meshes'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as stage:
        staged = pathlib.Path(stage) / 'bundle'
        staged.mkdir()
        for name, text in files.items():
            (staged / name).write_text(text, encoding='utf-8', newline='\n')
        identity = fingerprint(staged)
        if not (root / identity).exists():
            shutil.copytree(staged, pathlib.Path(stage) / 'final')
            (pathlib.Path(stage) / 'final').replace(root / identity)
    bundle_path(identity, game)
    return identity


def load_bundle(identity, game=GAME):
    from map_meshes import bundle_path
    data = json.loads((bundle_path(identity, game) / 'patch.json').read_text(encoding='utf-8'))
    if data.get('version') != 1 or data.get('room') != ROOM:
        raise ValueError('unsupported retopo bundle ' + identity)
    return data


def patches_for(document, prefix, game=GAME):
    out = []
    for key, entry in sorted(((document or {}).get('patches') or {}).items()):
        if key.split('_room_')[0] == prefix:
            out.append((key, entry, load_bundle(entry['bundle'], game)))
    return out


def check_sources(data, faces, segments, entry):
    room = data['room']
    if hashlib.sha256(segments[room]).hexdigest() != entry['sha256']:
        raise ValueError('retopo source room changed: ' + room)
    for src, digest in list(data['sources'].items()) + [(k, v['source_sha256'])
                                                         for k, v in data['fans'].items()]:
        if face_hash(faces[int(src)]) != digest:
            raise ValueError('retopo source face %s changed; regenerate the bundle' % src)


def tile_size(vertices, tex):
    """Square power-of-two tile keeping >= 1.5 tile pixels per source texel."""
    import build_quads as quads
    if not tex:
        return 8
    uv = [quads.effective_uv(v, tex) for v in vertices]
    texels = max(math.dist(uv[i], uv[(i+1) % len(uv)]) for i in range(len(uv)))
    size = 8
    while size < 1.5 * texels and size < 32:
        size *= 2
    return size


def apply_patches(groups, faces, segments, document, prefix='spot00', game=GAME):
    """Mark replaced groups; the baker sizes them exactly as before, then
    replace_pieces() swaps in the retopo faces. Unrelated tile sizes therefore
    cannot move: the parents still take part in the greedy texture pass."""
    import build_quads as quads
    patches = patches_for(document, prefix, game)
    if not patches:
        return groups
    for key, entry, data in patches:
        check_sources(data, faces, segments, entry)
        children = collections.defaultdict(list)
        for f in data['faces']:
            src = f['source']
            parent = faces[src]
            vertices = [tuple(float(x) for x in v) for v in f['vertices']]
            tri = dict(parent, vertices=vertices, retopo=True)
            children[src].append(dict(kind=quads.BAKE, repeat=(1, 1), tri=tri, points=vertices,
                                      texture=parent['texture'], size=quads.span(vertices),
                                      source=[src], retopo=True, far_sort=True,
                                      retopo_tile=tile_size(vertices, parent['texture'])))
        for i, fan_data in data['fans'].items():
            i = int(i)
            parent = faces[i]
            for t in fan_data['triangles']:
                vertices = [tuple(float(x) for x in v) for v in t]
                children[i].append(dict(kind=quads.BAKE, repeat=(1, 1), tri=dict(parent, vertices=vertices),
                                        points=vertices, texture=parent['texture'], size=quads.span(vertices),
                                        source=[i], retopo_fan=quads.span(parent['vertices'])))
        replaced = set(children)
        found = set()
        for g in groups:
            hit = set(g['source']) & replaced
            if not hit:
                continue
            found |= hit
            kids = [c for s in sorted(hit) for c in children[s]]
            # A partner rejoined into the same quad keeps its own triangle.
            for other in sorted(set(g['source']) - replaced):
                face = faces[other]
                kids.append(dict(kind=quads.BAKE, repeat=(1, 1), tri=face, points=list(face['vertices']),
                                 texture=face['texture'], size=quads.span(face['vertices']),
                                 source=[other], retopo_orphan=g['size']))
            g['retopo_drop'] = kids
        if found != replaced:
            raise ValueError('%s: source faces %s not in the converted groups'
                             % (key, sorted(replaced - found)))
    return groups


def replace_pieces(pieces, tiles, add_tile):
    """After sizing: drop marked parents, add their children with own tiles."""
    out, done = [], set()
    for group, tile in pieces:
        kids = group.get('retopo_drop')
        if kids is None:
            out.append((group, tile))
            continue
        if id(kids) in done:
            continue
        done.add(id(kids))
        parent = tiles[tile]
        for kid in kids:
            if kid.get('retopo_tile'):
                w = h = kid['retopo_tile']
            else:
                # Same texel density as the parent's tile along each axis.
                scale = kid['size'] / (kid.get('retopo_fan') or kid.get('retopo_orphan') or kid['size'])
                w = min(parent['width'], 1 << max(3, math.ceil(math.log2(max(1, parent['width'] * scale)))))
                h = min(parent['height'], 1 << max(0, math.ceil(math.log2(max(1, parent['height'] * scale)))))
                w = max(8, (w + 7) // 8 * 8)
            out.append((kid, add_tile(kid, w, h, False)))
    return out


def patch_collision(collision, prefix, document=None, game=GAME):
    """Replace the patch polygons in place (later indices keep their slots)."""
    from layout_variants import build_document
    document = build_document(game) if document is None else document
    patches = patches_for(document, prefix, game)
    if not patches:
        return collision, None
    polys = list(collision['polys'])
    info = []
    for key, entry, data in patches:
        removed = sorted(int(p) for p in data['collision'])
        if collision_hash([polys[p] for p in removed]) != data['collision_sha256']:
            raise ValueError('%s: collision polygons changed; regenerate the bundle' % key)
        surface, ignore, conveyor = data['surface']
        new = []
        for tri in data['collision_triangles']:
            q15, _ = plane_q15(tri)
            new.append(dict(vertices=[tuple(v) for v in tri],
                            normal=[round(q / 2) for q in q15],
                            surface=surface, ignore=ignore, conveyor=conveyor))
        for slot, poly in zip(removed, new):
            polys[slot] = poly
        polys.extend(new[len(removed):])
        info.append(dict(key=key, removed=len(removed), added=len(new), total=len(polys)))
    return dict(collision, polys=polys), info


def plane_q15(tri):
    """One quantization for both backends: Q15 unit normal from the welded
    integer triangle, OoT plane distance from that Q15 normal. SA.COL stores
    round(q15 / 2) (the same Q14 rule build_kokiri_scene applies to the ROM);
    SA.OOC gets q15 exactly through snormal_literal()."""
    n = unit(cross(sub(tri[1], tri[0]), sub(tri[2], tri[0])))
    q15 = [round(x * 32767) for x in n]
    return q15, -round(dot(q15, tri[0]) / 32767)


def snormal_literal(q):
    """COLPOLY_SNORMAL(x) is (s16)(x * SHT_MAX): truncation toward zero.
    Half a step beyond q makes the cast land exactly on q."""
    return (q + (.5 if q > 0 else -.5 if q < 0 else 0)) / 32767


def check_normal_convention(collision):
    """ROM normals follow (v1-v0) x (v2-v0); new polygons rely on that."""
    for p in PATCH.values():
        poly = collision['polys'][p]
        v = poly['vertices']
        n = cross(sub(v[1], v[0]), sub(v[2], v[0]))
        if dot(n, poly['normal']) <= 0:
            raise ValueError('collision poly %d normal disagrees with its winding' % p)


POLY_ENTRY = re.compile(r'^    \{\n(.*?)^    \}, // (\d+)\n', re.M | re.S)
VTX_ENTRY = re.compile(r'^    \{\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\}, // (\d+)$', re.M)


def scenecol_patch(scene_c, out_dir, document=None, game=GAME):
    """Patched PolyList/VtxList includes for the oot-core scene blob.

    Returns {original include line: replacement include line} or {}. The
    unchanged polygons keep their original text; the replaced slots and the
    appended polygons use the same triangles as SA.COL (same order)."""
    from layout_variants import build_document
    prefix = scene_c.stem.split('_scene')[0]
    document = build_document(game) if document is None else document
    patches = patches_for(document, prefix, game)
    if not patches:
        return {}
    folder = scene_c.parent
    text = scene_c.read_text(encoding='utf-8')
    poly_inc = re.search(r'^#include "([^"]+_PolyList\.inc\.c)"$', text, re.M).group(1)
    vtx_inc = re.search(r'^#include "([^"]+_VtxList\.inc\.c)"$', text, re.M).group(1)
    poly_text = (folder / pathlib.Path(poly_inc).name).read_text(encoding='utf-8')
    vtx_text = (folder / pathlib.Path(vtx_inc).name).read_text(encoding='utf-8')
    entries = [(m.group(0), int(m.group(2))) for m in POLY_ENTRY.finditer(poly_text)]
    if [i for _, i in entries] != list(range(len(entries))):
        raise ValueError('%s: unexpected PolyList layout' % poly_inc)
    vertices = [tuple(int(m.group(k)) for k in (1, 2, 3)) for m in VTX_ENTRY.finditer(vtx_text)]
    blocks = [b for b, _ in entries]
    index = {}
    for i, v in enumerate(vertices):
        index.setdefault(v, i)

    def vid(v):
        v = tuple(v)
        if v not in index:
            index[v] = len(vertices)
            vertices.append(v)
        return index[v]
    for key, entry, data in patches:
        removed = sorted(int(p) for p in data['collision'])
        surface, ignore, conveyor = data['surface']
        new = []
        for tri in data['collision_triangles']:
            q15, dist = plane_q15(tri)
            n = [snormal_literal(q) for q in q15]
            ids = [vid(v) for v in tri]
            new.append('    {\n        %d, // type\n        {\n'
                       '            COLPOLY_VTX(%d, %d),\n            COLPOLY_VTX(%d, %d),\n'
                       '            COLPOLY_VTX(%d, 0),\n        }, // vtxData\n        {\n'
                       '            COLPOLY_SNORMAL(%.9f),\n            COLPOLY_SNORMAL(%.9f),\n'
                       '            COLPOLY_SNORMAL(%.9f),\n        }, // normal\n'
                       '        %d, // dist\n' % (surface, ids[0], ignore, ids[1], conveyor,
                                                    ids[2], n[0], n[1], n[2], dist))
        for slot, block in zip(removed, new):
            blocks[slot] = block + '    }, // %d\n' % slot
        for block in new[len(removed):]:
            blocks.append(block + '    }, // %d\n' % len(blocks))
    if len(vertices) > 0x1FFF:
        raise ValueError('patched VtxList exceeds the 13-bit vertex index')
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    poly_name = prefix + '_retopo_PolyList.inc.c'
    vtx_name = prefix + '_retopo_VtxList.inc.c'
    write_if_changed(out_dir / poly_name, ''.join(blocks))
    write_if_changed(out_dir / vtx_name, ''.join('    { %6d, %6d, %6d }, // %d\n' % (v + (i,))
                                                 for i, v in enumerate(vertices)))
    return {'#include "%s"' % poly_inc: '#include "%s"' % poly_name,
            '#include "%s"' % vtx_inc: '#include "%s"' % vtx_name}


def write_if_changed(path, text):
    path = pathlib.Path(path)
    if not path.exists() or path.read_text(encoding='utf-8') != text:
        path.write_text(text, encoding='utf-8', newline='\n')


# ---------------------------------------------------------------- pairing
def record(part, document, prefix='spot00', game=GAME):
    """Which retopo bundles one consumer baked: stm, col or ooc."""
    ids = sorted(entry['bundle'] for key, entry in ((document or {}).get('patches') or {}).items()
                 if key.split('_room_')[0] == prefix)
    folder = pathlib.Path(game) / 'build/generated'
    folder.mkdir(parents=True, exist_ok=True)
    write_if_changed(folder / ('retopo-%s.json' % part), json.dumps(dict(prefix=prefix, bundles=ids)) + '\n')
    return ids


def check_pairing(parts=('stm', 'col'), game=GAME):
    """Refuse a disc whose Field floor, C collision and oot-core collision
    came from different retopo bundles (or one with and one without)."""
    seen = {}
    for part in parts:
        path = pathlib.Path(game) / 'build/generated' / ('retopo-%s.json' % part)
        if not path.exists():
            raise SystemExit('retopo pairing: %s missing; run a full build' % path.name)
        seen[part] = json.loads(path.read_text(encoding='utf-8'))['bundles']
    if len({tuple(v) for v in seen.values()}) != 1:
        raise SystemExit('retopo pairing mismatch: %s' % seen)
    print('retopo pairing: %s agree on %s' % ('/'.join(parts), seen[parts[0]] or 'original ground'))


# ---------------------------------------------------------------- budget
def field_budget(oot, rom_dir, document):
    """The real Field bake (convert + pieces + sweep) into a temporary STM."""
    import tempfile
    import build_field_chunks as field
    from build_sgl_scene import link_actor_budget
    from build_field_owl import build as build_owl
    actor = link_actor_budget(GAME / 'build/generated/LINK.BIN')
    with tempfile.TemporaryDirectory() as temp:
        temp = pathlib.Path(temp)
        models = build_owl(oot, rom_dir, temp / 'owl')['models']
        owl_actor = dict(tiles=[t for m in models for t in m['tiles']],
                         polygons=max(m['polygons'] for m in models),
                         vertices=max(m['vertices'] for m in models))
        result = field.bake(oot, rom_dir, {}, actor, owl_actor, document, temp / 'SAR0.STM',
                            temp / 'report.json')
        blob = (temp / 'SAR0.STM').read_bytes()
    return result, blob


def stm_pieces(blob):
    """Per-piece content hashes of a KRM2 file, tile ids resolved to pixels."""
    import build_field_chunks as field
    h, buckets, tiles, pieces = field.unpack(blob)
    pool = h[12]
    pixels = [blob[pool + t[2]: pool + t[2] + t[3]] for t in tiles]
    clut_at = field.HEADER.size + field.BUCKET.size * h[5] + field.TILE.size * h[3]
    cluts = [blob[clut_at + 32 * i: clut_at + 32 * (i + 1)] for i in range(h[3])]
    out = []
    for p in pieces:
        at = p['offset']
        geometry = p['points'] * 12 + p['polys'] * 20
        digest = hashlib.sha256(blob[at: at + geometry])
        for k in range(p['polys']):
            attr = blob[at + geometry + 12 * k: at + geometry + 12 * (k + 1)]
            texno = int.from_bytes(attr[2:4], 'big')
            digest.update(attr[:2] + attr[4:] + bytes(tiles[texno][:0]) +
                          tiles[texno][0].to_bytes(2, 'big') + tiles[texno][1].to_bytes(2, 'big') +
                          pixels[texno] + cluts[texno])
        out.append(dict(kind=p['kind'], bounds=list(p['bounds']), points=p['points'],
                        polys=p['polys'], sha256=digest.hexdigest()))
    return out


def stm_faces(blob):
    """Every face of every piece as (piece, world corners, sort/flags, tile hash)."""
    import build_field_chunks as field
    h, _, tiles, pieces = field.unpack(blob)
    pool = h[12]
    clut_at = field.HEADER.size + field.BUCKET.size * h[5] + field.TILE.size * h[3]
    out = collections.Counter()
    for n, p in enumerate(pieces):
        at = p['offset']
        pts = [tuple(int.from_bytes(blob[at + 12*i + 4*k: at + 12*i + 4*k + 4], 'big', signed=True) >> 16
                     for k in range(3)) for i in range(p['points'])]
        pts = [(x, -y, z) for x, y, z in pts]
        poly_at = at + 12 * p['points']
        attr_at = poly_at + 20 * p['polys']
        for k in range(p['polys']):
            idx = [int.from_bytes(blob[poly_at + 20*k + 12 + 2*j: poly_at + 20*k + 14 + 2*j], 'big')
                   for j in range(4)]
            attr = blob[attr_at + 12*k: attr_at + 12*(k+1)]
            t = tiles[int.from_bytes(attr[2:4], 'big')]
            texel = hashlib.sha256(blob[pool + t[2]: pool + t[2] + t[3]] +
                                   blob[clut_at + 32 * int.from_bytes(attr[2:4], 'big'):][:32] +
                                   bytes([t[0] >> 8, t[0] & 255, t[1]])).hexdigest()[:16]
            out[(n, p['kind'], tuple(pts[i] for i in idx), attr[:2] + attr[4:], texel)] += 1
    return out


def freeze_report(base_blob, new_blob, faces, model):
    """Classify every STM face difference: patch, fan, or unrelated."""
    before, after = stm_faces(base_blob), stm_faces(new_blob)
    removed, added = before - after, after - before
    patch_points = {retopo_key(faces[s]['vertices']) for s in PATCH}
    fan_points = {retopo_key(faces[i]['vertices']) for i in model['fans']}
    new_points = {retopo_key(f['vertices']) for f in model['faces']}
    new_points |= {retopo_key(t) for tris in model['fans'].values() for t in tris}
    sources = {retopo_key(f['vertices']) for f in faces if f['room'] == ROOM}
    report = collections.Counter()
    unrelated = []
    pairs = []
    for (piece, kind, corners, attr, texel), n in removed.items():
        key = frozenset(corners)
        tag = 'patch' if key in patch_points else 'fan-parent' if key in fan_points else None
        if tag is None and len(key) == 4 and any(f <= key for f in fan_points):
            # A fanned face had been rejoined with a partner into one quad.
            tag = 'fan-pair-parent'
            pairs.append(key)
        report['removed-' + (tag or 'unrelated')] += n
        if tag is None:
            unrelated.append(('removed', piece, kind, corners))
    for (piece, kind, corners, attr, texel), n in added.items():
        key = frozenset(corners)
        tag = 'new' if key in new_points else None
        if tag is None and key in sources and any(key <= p for p in pairs):
            tag = 'orphan-partner'
        report['added-' + (tag or 'unrelated')] += n
        if tag is None:
            unrelated.append(('added', piece, kind, corners))
    return dict(report), unrelated[:20]


def retopo_key(vertices):
    return frozenset(retopo_corner(v) for v in vertices)


def retopo_corner(v):
    return tuple(int(round(x)) for x in v[:3])


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--oot', type=pathlib.Path)
    parser.add_argument('--rom-dir', type=pathlib.Path)
    parser.add_argument('--check-pairing', metavar='PARTS',
                        help='comma list of stm,col,ooc records that must agree; no bake')
    parser.add_argument('--out', type=pathlib.Path, default=GAME / 'build/square-retopo/preview')
    parser.add_argument('--sizes', default=','.join(map(str, SIZES)))
    parser.add_argument('--boundary', type=int, default=BOUNDARY)
    parser.add_argument('--bundle', type=int, metavar='SIZE',
                        help='store the bundle for SIZE and write the layout variant')
    parser.add_argument('--variant', default='field-square-v001')
    parser.add_argument('--base', default='kokiri0-v002', help='variant the patch is added to')
    parser.add_argument('--budget', action='store_true',
                        help='real Field bake for --base and each size (needs build/generated/LINK.BIN)')
    args = parser.parse_args()
    if args.check_pairing:
        check_pairing(tuple(args.check_pairing.split(',')))
        return
    if not args.oot or not args.rom_dir:
        parser.error('--oot and --rom-dir are required')
    import build_kokiri_scene as source
    import layout_variants
    faces, segments = load_source(args.oot, args.rom_dir)
    collision = source.collision_data(segments['spot00_scene'])
    check_normal_convention(collision)
    args.out.mkdir(parents=True, exist_ok=True)
    sizes = [args.bundle] if args.bundle else list(map(int, args.sizes.split(',')))
    report = {}
    base = layout_variants.load(args.base)
    baseline = None
    for size in sizes:
        model = build(faces, collision, size, args.boundary)
        report[size] = metrics(model, faces)
        preview(model, faces, collision, args.out / ('top-%d.png' % size), args.out / ('view-%d.png' % size))
        if args.bundle or args.budget:
            identity = store_bundle(bundle_files(model, faces, collision))
            document = dict(base, patches={PATCH_NAME: dict(
                sha256=hashlib.sha256(segments[ROOM]).hexdigest(), bundle=identity)})
            layout_variants.validate(document)
            report[size]['bundle'] = identity
            if args.bundle:
                layout_variants.save(args.variant, document)
                print('stored bundle %s; variant %s (selection unchanged)' % (identity, args.variant))
            if args.budget:
                if baseline is None:
                    result, baseline = field_budget(args.oot, args.rom_dir, base)
                    report['baseline'] = result
                result, blob = field_budget(args.oot, args.rom_dir, document)
                old, new = stm_pieces(baseline), stm_pieces(blob)
                changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
                freeze, unrelated = freeze_report(baseline, blob, faces, model)
                report[size]['bake'] = dict(result, changed_pieces=changed, pieces=len(new),
                                            baseline_pieces=len(old), freeze=freeze,
                                            unrelated=unrelated)
                if unrelated:
                    raise SystemExit('size %d: unrelated Field faces changed: %s' % (size, unrelated))
        print(json.dumps({k: v for k, v in report[size].items()
                          if k not in ('depth', 'unsplit_boundary', 'exceptions')}, default=str), flush=True)
    (args.out / ('budget.json' if args.budget else 'geometry.json')).write_text(
        json.dumps(report, indent=1, default=str) + '\n')


if __name__ == '__main__':
    main()
