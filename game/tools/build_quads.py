#!/usr/bin/env python
"""Rebuild Kokiri's triangles into Saturn-drawable textured quads.

The scene arrives as 2060 triangles, each carrying its own baked tile. That
spends 369 KB of VDP1 VRAM to buy 16 texels across per triangle, which is why
a single texel covers up to 86 world units -- taller than Link -- and why the
artwork smears at every distance. See docs/TEXTURE_PLAN.md.

The forest's real artwork is only 54 textures totalling 35 KB, and most
triangles were quads before export: 915 adjacent pairs share an edge with
identical UVs. Rejoining them and drawing the shared texture directly is what
recovers the density.

SGL and VDP1 expose no arbitrary per-vertex UVs -- a sprite is mapped corner to
corner -- so source UVs are preserved here and mapped into one of three
Saturn-compatible forms, chosen per quad:

  DIRECT  UVs are an axis-aligned rectangle covering the texture once. Draw the
          shared texture as an ordinary sprite.
  SPLIT   UVs are rectangular but repeat. VDP1 cannot wrap inside one sprite,
          so the quad is cut into N sub-quads that each draw the texture once.
          Repeats are almost all horizontal with integer factors.
  BAKE    UVs are genuinely skewed (282 quads have four distinct s *and* four
          distinct t, so they are arbitrary, not rotated rectangles). These keep
          a per-face bake, sized by how large the face is rather than uniformly.

Nothing here decides the bake sizes; that is the budget's job, so the caller can
trade 64x64 down to 32x32 rather than exceed VRAM.
"""

import collections
import math

DIRECT, SPLIT, BAKE = 'direct', 'split', 'bake'

# Two triangles are treated as one quad when they share an edge whose endpoints
# agree in position *and* UV, and they use the same texture.
ADJACENT_WINDOW = 6          # export order keeps pairs close; don't scan all

# A split costs one polygon per piece, so a quad that wants a very high repeat
# is better baked: the polygons buy little on geometry that is usually far away.
MAX_SPLIT_PIECES = 8


def vertex_key(v):
    return tuple(v)


def same_texture(a, b):
    ta, tb = a['texture'], b['texture']
    if ta is None or tb is None:
        return False
    return ta == tb and all(a.get(k) == b.get(k) for k in
                           ('lighting', 'prim', 'transparent', 'cull', 'room'))


def normal(points):
    a, b, c = points[:3]
    u = [b[k] - a[k] for k in range(3)]
    v = [c[k] - a[k] for k in range(3)]
    return tuple(u[(k+1)%3]*v[(k+2)%3] - u[(k+2)%3]*v[(k+1)%3]
                 for k in range(3))


def joined_points(a, b):
    """Convex coplanar boundary with the original triangle winding intact."""
    edges = [(tuple(p), tuple(q)) for f in (a, b)
             for p, q in zip(f['vertices'], f['vertices'][1:] + f['vertices'][:1])]
    boundary = [(p, q) for p, q in edges if (q, p) not in edges]
    if len(boundary) != 4:
        return None
    points = [boundary[0][0]]
    for _ in range(3):
        following = [q for p, q in boundary if p == points[-1]]
        if len(following) != 1 or following[0] in points:
            return None
        points.append(following[0])
    n = normal(a['vertices'])
    length = math.sqrt(sum(x*x for x in n))
    if not length or any(abs(sum(n[k]*(p[k]-points[0][k]) for k in range(3)))
                         > length * .1 for p in points):
        return None
    for i in range(4):
        corner = normal([points[i], points[(i+1)%4], points[(i+2)%4]])
        if sum(x*y for x, y in zip(n, corner)) <= 0:
            return None
    return points


def effective_uv(p, tex):
    return tuple(p[3+k] * tex['scale'][k] *
                 2**(-tex[shift] if tex[shift] <= 10 else 16-tex[shift]) - tex[origin]/4
                 for k, shift, origin in ((0, 'shifts', 'uls'), (1, 'shiftt', 'ult')))


def span(points):
    return max(math.dist(p[:3], q[:3]) for p in points for q in points)


def classify(points, texture):
    """DIRECT / SPLIT / BAKE, with the repeat counts for SPLIT."""
    uv = [effective_uv(p, texture) for p in points]
    ss = sorted({round(p[0], 2) for p in uv})
    ts = sorted({round(p[1], 2) for p in uv})
    if len(points) != 4 or len(ss) != 2 or len(ts) != 2 or len(set(uv)) != 4:
        return BAKE, (1, 1)
    du = (ss[-1] - ss[0]) / texture['width'] if texture['width'] else 1.0
    dv = (ts[-1] - ts[0]) / texture['height'] if texture['height'] else 1.0
    ru, rv = max(1, int(round(du))), max(1, int(round(dv)))
    # Only accept a split when the repeat really is close to an integer;
    # a fractional repeat would show a seam, so bake it instead.
    if abs(du - ru) > .002 or abs(dv - rv) > .002:
        return BAKE, (1, 1)
    # Clamp cannot repeat; a partial/clamped interval stays on the bake path.
    for k, extent, mode in ((0, texture['width'], texture['cms']),
                             (1, texture['height'], texture['cmt'])):
        if mode & 2 and (min(p[k] for p in uv) < -.02 or
                         max(p[k] for p in uv) > extent + .02):
            return BAKE, (1, 1)
    if ru == 1 and rv == 1:
        return DIRECT, (1, 1)
    if ru * rv > MAX_SPLIT_PIECES:
        return BAKE, (1, 1)
    return SPLIT, (ru, rv)


def build(faces):
    """Group triangles into quads and classify them. Returns a list of dicts."""
    used = set()
    out = []
    for i, a in enumerate(faces):
        if i in used:
            continue
        ka = {vertex_key(v): v for v in a['vertices']}
        partner = None
        for j in range(i + 1, min(i + ADJACENT_WINDOW, len(faces))):
            if j in used or not same_texture(a, faces[j]):
                continue
            b = faces[j]
            kb = {vertex_key(v): v for v in b['vertices']}
            shared = [k for k in ka if k in kb]
            points = joined_points(a, b) if len(shared) == 2 else None
            if points is not None:
                partner = (j, b, points)
                break
        if partner is None:
            out.append(dict(kind=BAKE, repeat=(1, 1), tri=a,
                            points=list(a['vertices']),
                            texture=a['texture'], size=span(a['vertices']), source=[i]))
            used.add(i)
            continue

        j, b, points = partner
        kind, repeat = classify(points, a['texture'])
        out.append(dict(kind=kind, repeat=repeat, tri=a, pair=b, points=points,
                        texture=a['texture'], size=span(points), source=[i, j]))
        used.add(i)
        used.add(j)
    return out


def summarise(quads):
    kinds = collections.Counter(q['kind'] for q in quads)
    polygons = 0
    for q in quads:
        ru, rv = q['repeat']
        polygons += ru * rv if q['kind'] == SPLIT else 1
    shared = {(q['texture']['address'], q['texture']['width'],
               q['texture']['height'])
              for q in quads if q['kind'] in (DIRECT, SPLIT)}
    return dict(kinds=kinds, polygons=polygons, shared=shared,
                bakes=[q for q in quads if q['kind'] == BAKE])


def subdivide(quad):
    """A SPLIT quad as ru*rv sub-quads, each covering the texture exactly once.

    Corners are A,B,C,D around the quad; interpolating bilinearly keeps the
    sub-quads inside the original surface, so no new silhouette appears.
    """
    a, b, c, d = quad['points']
    ru, rv = quad['repeat']
    # Repeats are measured along S/T; the boundary may run T first.
    if abs(a[3] - b[3]) < .001:
        ru, rv = rv, ru

    def lerp(p, q, t):
        return tuple(p[k] + (q[k] - p[k]) * t for k in range(len(p)))

    def corner(u, v):
        # bilinear across the quad: A->B along u at v=0, D->C along u at v=1
        top = lerp(a, b, u)
        bottom = lerp(d, c, u)
        return lerp(top, bottom, v)

    pieces = []
    for iv in range(rv):
        for iu in range(ru):
            u0, u1 = iu / ru, (iu + 1) / ru
            v0, v1 = iv / rv, (iv + 1) / rv
            pieces.append([corner(u0, v0), corner(u1, v0),
                           corner(u1, v1), corner(u0, v1)])
    return pieces
