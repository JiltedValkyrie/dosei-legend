#!/usr/bin/env python
"""Import the human-authored Kokiri OBJ as the resident SGL scene.

The authored mesh is one object exported from Blender with UVs into the preview
atlas its MTL names. This importer does NOT try to recover original OoT source
faces: it bakes each authored face's own atlas region into its own small 4bpp
VDP1 tile, so what ships is exactly what was authored, at the density the tile
size allows.

Output is the same set of files build_sgl_scene.py emits for the non-streaming
path (kokiri_scene.c/.h, kokiri_textures.c, kokiri_pixels.bin), so the existing
loader, fog, sorting and budget checks are unchanged. Build with STREAM_ROOMS=0.

Geometry rules kept deliberately conservative:
  * authored world coordinates are used as-is; nothing is recentred or scaled.
  * Y is negated by emit(), exactly once, as for the generated scene.
  * a triangle becomes an SGL degenerate quad (third corner repeated).
  * an n-gon is fan-split only when it is convex; a concave one is reported
    and split through its ear list instead of blindly fanned.
"""

import argparse
import collections
import math
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

import build_sgl_scene as sgl
from build_hybrid_scene import quantize
from PIL import Image

# VDP1 sprite width must be a multiple of 8; keep tiles inside what the budget
# and the loader's checks accept.
TILE_WIDTHS = (8, 16, 32, 64)
TILE_HEIGHTS = (8, 16, 32, 64)


def parse_mtl(path):
    """material name -> absolute texture path."""
    textures, current = {}, None
    for line in path.read_text(errors='replace').splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == 'newmtl':
            current = parts[1]
        elif parts[0] == 'map_Kd' and current:
            textures[current] = ' '.join(parts[1:])
    return textures


def parse_obj(path):
    positions, uvs, faces = [], [], []
    material, obj = None, None
    mtllib = None
    for number, line in enumerate(path.read_text(errors='replace').splitlines(), 1):
        parts = line.split()
        if not parts:
            continue
        tag = parts[0]
        if tag == 'v':
            positions.append(tuple(float(v) for v in parts[1:4]))
        elif tag == 'vt':
            uvs.append((float(parts[1]), float(parts[2])))
        elif tag == 'usemtl':
            material = parts[1]
        elif tag == 'o':
            obj = parts[1]
        elif tag == 'mtllib':
            mtllib = ' '.join(parts[1:])
        elif tag == 'f':
            corners = []
            for token in parts[1:]:
                bits = token.split('/')
                vertex = int(bits[0])
                texture = int(bits[1]) if len(bits) > 1 and bits[1] else None
                corners.append((vertex - 1 if vertex > 0 else len(positions) + vertex,
                                None if texture is None else
                                (texture - 1 if texture > 0 else len(uvs) + texture)))
            faces.append(dict(corners=corners, material=material, object=obj,
                              line=number))
    return positions, uvs, faces, mtllib


def convex(points):
    """True when a polygon's turns all have the same sign in its own plane."""
    if len(points) < 4:
        return True
    normal = [0.0, 0.0, 0.0]
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        normal[0] += (a[1] - b[1]) * (a[2] + b[2])
        normal[1] += (a[2] - b[2]) * (a[0] + b[0])
        normal[2] += (a[0] - b[0]) * (a[1] + b[1])
    sign = 0
    for i in range(len(points)):
        a, b, c = points[i], points[(i + 1) % len(points)], points[(i + 2) % len(points)]
        u = [b[k] - a[k] for k in range(3)]
        v = [c[k] - b[k] for k in range(3)]
        cross = (u[1] * v[2] - u[2] * v[1],
                 u[2] * v[0] - u[0] * v[2],
                 u[0] * v[1] - u[1] * v[0])
        dot = sum(cross[k] * normal[k] for k in range(3))
        if abs(dot) < 1e-6:
            continue
        if sign and (dot > 0) != (sign > 0):
            return False
        sign = 1 if dot > 0 else -1
    return True


def closest_on_triangle(point, a, b, c):
    """Closest point on a triangle to `point`, with its barycentric weights."""
    ab = [b[k] - a[k] for k in range(3)]
    ac = [c[k] - a[k] for k in range(3)]
    ap = [point[k] - a[k] for k in range(3)]
    d1 = sum(ab[k] * ap[k] for k in range(3))
    d2 = sum(ac[k] * ap[k] for k in range(3))
    if d1 <= 0 and d2 <= 0:
        return a, (1.0, 0.0, 0.0)
    bp = [point[k] - b[k] for k in range(3)]
    d3 = sum(ab[k] * bp[k] for k in range(3))
    d4 = sum(ac[k] * bp[k] for k in range(3))
    if d3 >= 0 and d4 <= d3:
        return b, (0.0, 1.0, 0.0)
    vc = d1 * d4 - d3 * d2
    if vc <= 0 and d1 >= 0 and d3 <= 0:
        v = d1 / (d1 - d3) if d1 != d3 else 0.0
        return [a[k] + ab[k] * v for k in range(3)], (1 - v, v, 0.0)
    cp = [point[k] - c[k] for k in range(3)]
    d5 = sum(ab[k] * cp[k] for k in range(3))
    d6 = sum(ac[k] * cp[k] for k in range(3))
    if d6 >= 0 and d5 <= d6:
        return c, (0.0, 0.0, 1.0)
    vb = d5 * d2 - d1 * d6
    if vb <= 0 and d2 >= 0 and d6 <= 0:
        w = d2 / (d2 - d6) if d2 != d6 else 0.0
        return [a[k] + ac[k] * w for k in range(3)], (1 - w, 0.0, w)
    va = d3 * d6 - d5 * d4
    if va <= 0 and (d4 - d3) >= 0 and (d5 - d6) >= 0:
        w = (d4 - d3) / ((d4 - d3) + (d5 - d6))
        return [b[k] + (c[k] - b[k]) * w for k in range(3)], (0.0, 1 - w, w)
    denom = 1.0 / (va + vb + vc)
    v, w = vb * denom, vc * denom
    return ([a[k] + ab[k] * v + ac[k] * w for k in range(3)], (1 - v - w, v, w))


class UvSource(object):
    """Nearest-surface UV lookup against an already-textured mesh.

    A remesh throws the UVs away, so they are taken back from the mesh that
    still has them: for each corner of the new mesh, the closest point on the
    old surface decides the UV. Corners are transferred individually rather
    than per shared vertex, so a UV seam in the source stays a seam here
    instead of being averaged across it.
    """

    CELL = 128.0

    def __init__(self, path):
        positions, uvs, faces, _ = parse_obj(path)
        if not uvs:
            sys.exit('%s has no UVs to transfer' % path)
        self.triangles = []
        for face in faces:
            corners = [c for c in face['corners'] if c[1] is not None]
            for i in range(1, len(corners) - 1):
                trio = (corners[0], corners[i], corners[i + 1])
                self.triangles.append(tuple(positions[c[0]] for c in trio) +
                                      tuple(uvs[c[1]] for c in trio))
        self.grid = collections.defaultdict(list)
        for index, tri in enumerate(self.triangles):
            points = tri[:3]
            low = [min(p[k] for p in points) for k in (0, 2)]
            high = [max(p[k] for p in points) for k in (0, 2)]
            for x in range(int(low[0] // self.CELL), int(high[0] // self.CELL) + 1):
                for z in range(int(low[1] // self.CELL), int(high[1] // self.CELL) + 1):
                    self.grid[(x, z)].append(index)
        print('uv src  : %s, %d triangles' % (path.name, len(self.triangles)))

    def lookup(self, point):
        cell = (int(point[0] // self.CELL), int(point[2] // self.CELL))
        best, best_distance = None, None
        for radius in range(0, 40):
            candidates = []
            for x in range(cell[0] - radius, cell[0] + radius + 1):
                for z in range(cell[1] - radius, cell[1] + radius + 1):
                    if radius and max(abs(x - cell[0]), abs(z - cell[1])) != radius:
                        continue
                    candidates.extend(self.grid.get((x, z), ()))
            for index in candidates:
                tri = self.triangles[index]
                near, weights = closest_on_triangle(point, *tri[:3])
                distance = sum((near[k] - point[k]) ** 2 for k in range(3)) ** .5
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best = tuple(sum(weights[i] * tri[3 + i][axis] for i in range(3))
                                 for axis in (0, 1))
            # Anything closer than the ring we have already searched cannot be
            # beaten by a further ring, so stop as soon as that is true.
            if best_distance is not None and best_distance <= radius * self.CELL:
                break
        return best, (best_distance if best_distance is not None else float('inf'))


def plane_axes(points):
    """Two axis indices that keep the polygon's area when it is flattened."""
    normal = [0.0, 0.0, 0.0]
    for i, a in enumerate(points):
        b = points[(i + 1) % len(points)]
        normal[0] += (a[1] - b[1]) * (a[2] + b[2])
        normal[1] += (a[2] - b[2]) * (a[0] + b[0])
        normal[2] += (a[0] - b[0]) * (a[1] + b[1])
    dominant = max(range(3), key=lambda k: abs(normal[k]))
    return [k for k in range(3) if k != dominant], normal[dominant] >= 0


def signed_area(flat):
    return sum(flat[i][0] * flat[(i + 1) % len(flat)][1] -
               flat[(i + 1) % len(flat)][0] * flat[i][1]
               for i in range(len(flat))) / 2


def inside(a, b, c, p):
    def side(u, v, w):
        return (v[0] - u[0]) * (w[1] - u[1]) - (v[1] - u[1]) * (w[0] - u[0])
    d1, d2, d3 = side(a, b, p), side(b, c, p), side(c, a, p)
    return not ((d1 < 0 or d2 < 0 or d3 < 0) and (d1 > 0 or d2 > 0 or d3 > 0))


def ear_clip(corners, positions):
    """Triangulate any simple polygon, concave included.

    A fan from corner 0 is only correct for a convex polygon: on a concave one
    it emits triangles that leave the surface, which on this hardware shows up
    as a face folded through the geometry. Ear clipping only ever cuts a
    triangle that is inside the polygon and contains no other corner.
    """
    points = [positions[c[0]] for c in corners]
    axes, _ = plane_axes(points)
    flat = [(p[axes[0]], p[axes[1]]) for p in points]
    order = list(range(len(corners)))
    if signed_area(flat) < 0:
        order.reverse()
    pieces = []
    guard = 0
    while len(order) > 3 and guard < len(order) * len(order) + 16:
        guard += 1
        for position in range(len(order)):
            prev = order[position - 1]
            current = order[position]
            following = order[(position + 1) % len(order)]
            a, b, c = flat[prev], flat[current], flat[following]
            cross = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
            if cross <= 0:
                continue        # reflex corner, not an ear
            if any(inside(a, b, c, flat[other]) for other in order
                   if other not in (prev, current, following)):
                continue        # another corner is inside this ear
            pieces.append([corners[prev], corners[current], corners[following]])
            order.pop(position)
            break
        else:
            break               # no ear found; fall through with what is left
    if len(order) >= 3:
        pieces.append([corners[i] for i in order[:3]])
        for extra in range(3, len(order)):
            pieces.append([corners[order[0]], corners[order[extra - 1]],
                           corners[order[extra]]])
    return pieces


def merge_quads(pieces, positions):
    """Pair triangles sharing an edge back into convex quads.

    SGL spends one polygon slot on a triangle and one on a quad, so every pair
    merged here is a slot saved and one less affine seam across the surface.
    """
    merged, used = [], set()
    for i, first in enumerate(pieces):
        if i in used or len(first) != 3:
            continue
        for j in range(i + 1, len(pieces)):
            if j in used or len(pieces[j]) != 3:
                continue
            second = pieces[j]
            shared = [c for c in first if c in second]
            if len(shared) != 2:
                continue
            odd_first = [c for c in first if c not in shared][0]
            odd_second = [c for c in second if c not in shared][0]
            # Keep the shared edge's own order so the quad stays wound the
            # same way as the two triangles that made it.
            index = [first.index(c) for c in shared]
            if (index[0] + 1) % 3 == index[1]:
                quad = [odd_first, shared[0], odd_second, shared[1]]
            else:
                quad = [odd_first, shared[1], odd_second, shared[0]]
            if not convex([positions[c[0]] for c in quad]):
                continue
            merged.append(quad)
            used.add(i)
            used.add(j)
            break
        else:
            merged.append(first)
            used.add(i)
    for i, piece in enumerate(pieces):
        if i not in used:
            merged.append(piece)
    return merged


def triangulate(face, positions):
    """Split an n-gon, preserving each corner's own UV.

    Convex faces fan straight into quads; concave ones are ear clipped and the
    result merged back into quads where that is safe.
    """
    corners = face['corners']
    if len(corners) <= 4:
        return [corners]
    if convex([positions[c[0]] for c in corners]):
        pieces, i = [], 1
        while i < len(corners) - 1:
            if i + 2 < len(corners):
                pieces.append([corners[0], corners[i], corners[i + 1], corners[i + 2]])
                i += 2
            else:
                pieces.append([corners[0], corners[i], corners[i + 1]])
                i += 1
        return pieces
    return merge_quads(ear_clip(corners, positions), positions)


def midpoint(a, b, positions, uvs):
    """New corner halfway along an edge, in world AND uv, keyed by the edge.

    Both faces sharing an edge compute the same midpoint from the same two
    endpoints, so a split edge stays conforming as long as the neighbour splits
    too. Where the neighbour does NOT split, the new vertex still lies on its
    straight edge, so the worst case is a T-junction at the rounding of one
    world unit, not an open crack.
    """
    key = (min(a[0], b[0]), max(a[0], b[0]), min(a[1], b[1]), max(a[1], b[1]))
    cached = midpoint.cache.get(key)
    if cached is not None:
        return cached
    pa, pb = positions[a[0]], positions[b[0]]
    positions.append(tuple((pa[k] + pb[k]) / 2 for k in range(3)))
    ua, ub = uvs[a[1]], uvs[b[1]]
    uvs.append(((ua[0] + ub[0]) / 2, (ua[1] + ub[1]) / 2))
    corner = (len(positions) - 1, len(uvs) - 1)
    midpoint.cache[key] = corner
    return corner


midpoint.cache = {}


def centre_corner(corners, positions, uvs):
    positions.append(tuple(sum(positions[c[0]][k] for c in corners) / len(corners)
                           for k in range(3)))
    uvs.append((sum(uvs[c[1]][0] for c in corners) / len(corners),
                sum(uvs[c[1]][1] for c in corners) / len(corners)))
    return (len(positions) - 1, len(uvs) - 1)


def subdivide(corners, positions, uvs):
    """One level: 4 children, splitting every edge at its midpoint."""
    if len(corners) == 3:
        a, b, c = corners
        ab = midpoint(a, b, positions, uvs)
        bc = midpoint(b, c, positions, uvs)
        ca = midpoint(c, a, positions, uvs)
        return [[a, ab, ca], [ab, b, bc], [ca, bc, c], [ab, bc, ca]]
    a, b, c, d = corners
    ab = midpoint(a, b, positions, uvs)
    bc = midpoint(b, c, positions, uvs)
    cd = midpoint(c, d, positions, uvs)
    da = midpoint(d, a, positions, uvs)
    centre = centre_corner(corners, positions, uvs)
    return [[a, ab, centre, da], [ab, b, bc, centre],
            [centre, bc, c, cd], [da, centre, cd, d]]


def face_span(corners, positions):
    points = [positions[c[0]] for c in corners]
    return max(max(p[k] for p in points) - min(p[k] for p in points)
               for k in range(3))


def refine(faces, positions, uvs, span_limit, max_depth, polygon_cap):
    """Split the widest faces first until they fit the span limit or the cap.

    Widest-first matters: the budget is finite, and a 900-unit ground slab is
    what stretches its texture across the near view, not a 60-unit hut panel.
    """
    depth = {id(f): 0 for f in faces}
    work = list(faces)
    while True:
        candidates = [f for f in work
                      if depth[id(f)] < max_depth
                      and face_span(f, positions) > span_limit]
        if not candidates:
            break
        candidates.sort(key=lambda f: face_span(f, positions), reverse=True)
        target = candidates[0]
        children = subdivide(target, positions, uvs)
        if len(work) - 1 + len(children) > polygon_cap:
            print('  note  : split stopped at the %d-polygon cap; %d faces '
                  'still exceed %d units' % (polygon_cap, len(candidates), span_limit))
            break
        level = depth[id(target)] + 1
        index = work.index(target)
        work[index:index + 1] = children
        for child in children:
            depth[id(child)] = level
    return work


def tile_size(uv_corners, atlas_size, world_corners, units_per_texel, cap):
    """Tile just big enough for the face.

    Two limits apply and the smaller wins. The atlas footprint is the most
    detail that actually exists in the source pixels, so a bigger tile than
    that only resamples the same texels. The world span is what the player
    sees, expressed as world units per texel; a face covering little ground
    does not earn a large tile however big its atlas region happens to be.
    """
    width_px = (max(u for u, _ in uv_corners) - min(u for u, _ in uv_corners)) * atlas_size[0]
    height_px = (max(v for _, v in uv_corners) - min(v for _, v in uv_corners)) * atlas_size[1]
    span = max(max(c[k] for c in world_corners) - min(c[k] for c in world_corners)
               for k in range(3))
    world_texels = span / units_per_texel if units_per_texel > 0 else cap

    def pick(value, choices):
        for size in choices:
            if size >= value:
                return min(size, cap)
        return min(choices[-1], cap)

    return (pick(min(width_px, world_texels), TILE_WIDTHS),
            pick(min(height_px, world_texels), TILE_HEIGHTS))


def sample(atlas, uv):
    """Nearest texel, with the OBJ's bottom-left origin flipped to image rows."""
    width, height = atlas.size
    x = min(width - 1, max(0, int(uv[0] * width)))
    y = min(height - 1, max(0, int((1.0 - uv[1]) * height)))
    return atlas.getpixel((x, y))


def bake(atlas, uv_corners, width, height):
    """Bilinear corner interpolation, the same mapping VDP1 will apply."""
    pixels = []
    if len(uv_corners) == 3:
        uv_corners = list(uv_corners) + [uv_corners[2]]
    a, b, c, d = uv_corners
    for y in range(height):
        v = (y + .5) / height
        for x in range(width):
            u = (x + .5) / width
            top = ((1 - u) * a[0] + u * b[0], (1 - u) * a[1] + u * b[1])
            bottom = ((1 - u) * d[0] + u * c[0], (1 - u) * d[1] + u * c[1])
            pixels.append(sample(atlas, ((1 - v) * top[0] + v * bottom[0],
                                         (1 - v) * top[1] + v * bottom[1])))
    return pixels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--obj', required=True, type=pathlib.Path)
    parser.add_argument('--out', type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parents[1]
                        / 'build' / 'generated')
    parser.add_argument('--atlas', type=pathlib.Path,
                        help='override the texture the MTL names')
    parser.add_argument('--max-tile', type=int, default=32,
                        help='largest tile edge in texels (8, 16, 32 or 64)')
    parser.add_argument('--units-per-texel', type=float, default=6.0,
                        help='world units each texel should cover')
    parser.add_argument('--uv-from', type=pathlib.Path,
                        help='textured OBJ to take UVs from when the mesh has '
                             'none (a remesh drops them)')
    parser.add_argument('--uv-tolerance', type=float, default=24.0,
                        help='world units a corner may sit from the source '
                             'surface before it is reported')
    parser.add_argument('--split-span', type=float, default=0,
                        help='split any face wider than this many world units '
                             '(0 disables subdivision)')
    parser.add_argument('--max-depth', type=int, default=2,
                        help='most subdivision levels applied to one face')
    parser.add_argument('--polygon-cap', type=int, default=1800,
                        help='most forest polygons after subdivision')
    parser.add_argument('--cull', action='store_true',
                        help='emit Single_Plane (backface culling) faces')
    args = parser.parse_args()

    positions, uvs, raw_faces, mtllib = parse_obj(args.obj)
    if not positions or not raw_faces:
        sys.exit('%s: no geometry' % args.obj)
    source_uv = UvSource(args.uv_from) if args.uv_from else None
    if not uvs and source_uv is None:
        sys.exit('%s: no UVs and no --uv-from to take them from' % args.obj)
    if source_uv is not None:
        # A remeshed export has no vt records at all, so every corner gets its
        # UV from the nearest point on the textured mesh. Distances are
        # reported: a corner that is far from the old surface has no honest
        # answer and the build says so rather than inventing one.
        far, worst = 0, 0.0
        for face in raw_faces:
            transferred = []
            for vertex, _ in face['corners']:
                uv, distance = source_uv.lookup(positions[vertex])
                worst = max(worst, distance)
                if distance > args.uv_tolerance:
                    far += 1
                uvs.append(uv)
                transferred.append((vertex, len(uvs) - 1))
            face['corners'] = transferred
        print('uv xfer : %d corners, worst distance %.1f units, %d beyond %.0f'
              % (sum(len(f['corners']) for f in raw_faces), worst, far,
                 args.uv_tolerance))
        if far:
            print('  warn  : %d corners had no source surface within tolerance; '
                  'their texture is the nearest one found' % far)

    atlas_path = args.atlas
    if atlas_path is None:
        if not mtllib:
            sys.exit('%s: no mtllib and no --atlas' % args.obj)
        textures = parse_mtl(args.obj.parent / mtllib)
        names = sorted(set(textures.values()))
        if len(names) != 1:
            sys.exit('expected exactly one map_Kd, found %d: %s' % (len(names), names))
        atlas_path = pathlib.Path(names[0])
    if not atlas_path.exists():
        sys.exit('atlas not found: %s' % atlas_path)
    atlas = Image.open(atlas_path).convert('RGBA')
    print('atlas   : %s %dx%d' % (atlas_path.name, atlas.size[0], atlas.size[1]))

    # --- geometry -------------------------------------------------------
    pieces, arities = [], collections.Counter()
    missing_uv = 0
    for face in raw_faces:
        arities[len(face['corners'])] += 1
        for corners in triangulate(face, positions):
            if any(c[1] is None for c in corners):
                missing_uv += 1
                continue
            pieces.append(list(corners))
    if missing_uv:
        print('  warn  : %d faces dropped for missing UVs' % missing_uv)
    print('source  : %d vertices, %d faces %s -> %d pieces'
          % (len(positions), len(raw_faces), dict(sorted(arities.items())), len(pieces)))

    # A face's texture is mapped affinely across the whole face, so the wider
    # the face the harder the near-camera stretch, and a face that crosses the
    # near plane is clipped as one piece. Splitting the widest faces attacks
    # both. Children are cut at edge midpoints, so a neighbour that splits too
    # stays conforming and one that does not keeps its straight edge.
    if args.split_span > 0 and args.max_depth > 0:
        before = len(pieces)
        pieces = refine(pieces, positions, uvs, args.split_span,
                        args.max_depth, args.polygon_cap)
        widest = max(face_span(f, positions) for f in pieces)
        print('split   : %d -> %d polygons (limit %d units, depth %d), '
              'widest face now %d units'
              % (before, len(pieces), args.split_span, args.max_depth, widest))

    faces = []
    for corners in pieces:
        index = [c[0] for c in corners]
        if len(index) == 3:
            index.append(index[2])
        faces.append(dict(idx=tuple(index), uv=[uvs[c[1]] for c in corners],
                          cull=args.cull, mesh=False))

    # --- textures -------------------------------------------------------
    tiles, tile_ids = collections.OrderedDict(), {}
    for face in faces:
        width, height = tile_size(face['uv'], atlas.size,
                                  [positions[i] for i in face['idx']],
                                  args.units_per_texel, args.max_tile)
        clut, pixels = quantize(bake(atlas, face['uv'], width, height), width, height)
        key = (width, height, clut, pixels)
        if key not in tile_ids:
            offset = len(tiles) * 4096   # synthetic tex_off; only identity matters
            tile_ids[key] = offset
            tiles[offset] = dict(index=len(tiles), width=width, height=height,
                                 clut=clut, pixels=pixels)
        face['tex_off'] = tile_ids[key]
    sizes = collections.Counter('%dx%d' % (t['width'], t['height']) for t in tiles.values())
    print('tiles   : %d unique of %d faces  %s'
          % (len(tiles), len(faces), dict(sizes)))

    # --- bounding sphere, native world scale ----------------------------
    low = [min(p[k] for p in positions) for k in range(3)]
    high = [max(p[k] for p in positions) for k in range(3)]
    centre = [(low[k] + high[k]) / 2 for k in range(3)]
    radius = max(math.dist(p, centre) for p in positions)
    head = dict(cx=int(round(centre[0])), cy=int(round(centre[1])),
                cz=int(round(centre[2])), radius=int(math.ceil(radius)))
    print('bounds  : %s .. %s  centre %s radius %d'
          % ([int(v) for v in low], [int(v) for v in high],
             (head['cx'], head['cy'], head['cz']), head['radius']))

    verts = [tuple(int(round(v)) for v in p) for p in positions]
    pixel_bytes = sgl.emit(head, verts, faces, tiles, args.out)
    clut_bytes = len(tiles) * 32
    print('vram    : %d pixel + %d CLUT = %d bytes'
          % (pixel_bytes, clut_bytes, pixel_bytes + clut_bytes))
    print('out     : %s' % (args.out / 'kokiri_scene.c'))


if __name__ == '__main__':
    main()
