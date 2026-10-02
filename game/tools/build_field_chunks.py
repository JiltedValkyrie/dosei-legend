"""Hyrule Field as distance-streamed pieces (KRM2), resident in the RAM cart.

The whole Field bank sits in the cart; only pieces near Link occupy the room
POINT/POLYGON/ATTR tables and VDP1 VRAM. A piece is one geometry set with an
XZ distance band [near, far) measured from Link to the piece bounds:

  cell full   plain Field faces of one 2048-unit cell      [0, FULL_RING)
  cell far    LOD2: 2x2 heightfield quads, top-down bake    [FULL_RING, inf)
  object lod1 original faces of a Workshop LOD object       [lod0, cull)
  object lod0 the imported close-up mesh                    [0, lod0)

A piece is resident while Link is within its band widened by HYSTERESIS, drawn
only inside the exact band. bake() sweeps a lattice over the Field and refuses
any position whose resident union breaks the table, vertex or VRAM budget.

Tiles share one deduplicated pool. VRAM holds them in fixed pixel pools, one
per power-of-two size bucket, sized to the worst resident count of that bucket,
so a slot address never changes and nothing fragments.
"""
import collections
import math
import struct

import build_hybrid_scene as hybrid
import build_quads as quads
from build_sgl_scene import face_normal, floor_uses_far_sort
from vdp1_budget import (tile_bytes, MAX_TABLE_POLYGONS, MAX_VERTICES,
                         MAX_SPRITE_SLOTS, RUNTIME_SPRITE_BYTES,
                         RUNTIME_SPRITE_SLOTS, VDP1_USER_AREA)

MAGIC = 0x4b524d32  # 'KRM2'
VERSION = 1
CELL_SHIFT = 11      # 2048-unit cells: cell = (x - origin) >> 11
FULL_RING = 1536     # full detail inside, LOD2 beyond (XZ distance to bounds)
HYSTERESIS = 384
LATTICE = 256
# Lattice points sit within LATTICE/sqrt(2) of any Link position, so widening
# by that much more makes every sampled union a superset of the real one.
SWEEP_WIDEN = HYSTERESIS + LATTICE * 3 // 4
FAR_INF = 0xFFFF
FIELD_FAR = 9000     # streamed Field draw distance (kokiri_sgl.c FIELD_FAR)
LOD2_GRID = 2        # quads per cell side
LOD2_TILE = 16
LOD0_TILE = 16
KIND_FULL, KIND_FAR, KIND_LOD1, KIND_LOD0 = 0, 1, 2, 3
LOD0_OBJECT_BASE = 0x10000
MAX_PIECES = 255     # one-byte object id per polygon; 0xFF is never used

HEADER = struct.Struct('>16I')
BUCKET = struct.Struct('>2I')
TILE = struct.Struct('>HHIIHH')
PIECE = struct.Struct('>6i8HII')  # bounds; near far points polys refs kind group pad; data, pad


def xz_distance(point, bounds):
    """Integer XZ distance from a point to an AABB (0 inside); runtime twin."""
    x, z = point
    dx = bounds[0] - x if x < bounds[0] else x - bounds[3] if x > bounds[3] else 0
    dz = bounds[2] - z if z < bounds[2] else z - bounds[5] if z > bounds[5] else 0
    return math.isqrt(dx * dx + dz * dz)


def bucket_of(length):
    size = 8
    while size < length:
        size *= 2
    return size


def _bounds(points):
    return (tuple(min(p[k] for p in points) for k in range(3)) +
            tuple(max(p[k] for p in points) for k in range(3)))


class Pool:
    """Global tile pool, deduplicated by exact (size, CLUT, pixels)."""

    def __init__(self, tiles=()):
        self.tiles, self.ids = [], {}
        for t in tiles:
            self.add(t['width'], t['height'], t['clut'], t['pixels'])

    def add(self, width, height, clut, pixels):
        key = (width, height, tuple(clut), bytes(pixels))
        if key not in self.ids:
            self.ids[key] = len(self.tiles)
            self.tiles.append(dict(width=width, height=height, clut=tuple(clut),
                                   pixels=bytes(pixels)))
        return self.ids[key]


def _face(points, tile, cull=False, mesh=False):
    return dict(points=[tuple(int(round(v)) for v in p[:3]) for p in points],
                tile=tile, cull=cull, mesh=mesh)


def _group_tile(pool, group, size):
    clut, pixels = hybrid.render_tile(group, size, size, False)
    return pool.add(size, size, clut, pixels)


def lod0_faces(faces, pool):
    """Close-up meshes: every group its own fixed 16x16 bake (no VRAM pass)."""
    out = collections.defaultdict(list)
    for group in quads.build(faces):
        group['kind'] = quads.BAKE
        tile = _group_tile(pool, group, LOD0_TILE)
        out[group['tri']['lod0_of']].append(_face(
            group['points'], tile, group['tri']['cull'], group['tri']['transparent']))
    return out


class Surface:
    """Top-down lookup over source triangles for the LOD2 bake."""

    def __init__(self, faces, bucket=512):
        self.bucket, self.cells = bucket, collections.defaultdict(list)
        for face in faces:
            v = face['vertices']
            xs, zs = [p[0] for p in v], [p[2] for p in v]
            for bx in range(int(min(xs)) // bucket, int(max(xs)) // bucket + 1):
                for bz in range(int(min(zs)) // bucket, int(max(zs)) // bucket + 1):
                    self.cells[(bx, bz)].append(face)

    def top(self, x, z):
        """(face, interpolated 9-tuple) of the highest surface at x,z, or None."""
        best = None
        for face in self.cells.get((int(x) // self.bucket, int(z) // self.bucket), ()):
            w = hybrid.barycentric((x, 0, z), face['vertices'], axes=(0, 2))
            if w is None or min(w) < -1e-4:
                continue
            p = tuple(sum(wi * q[k] for wi, q in zip(w, face['vertices'])) for k in range(9))
            if best is None or p[1] > best[1][1]:
                best = (face, p)
        return best

    def colour(self, x, z):
        return self.shade(self.top(x, z))

    @staticmethod
    def shade(hit):
        if hit is None:
            return (0, 0, 0, 0)
        face, p = hit
        tex = face['texture']
        if tex:
            s = hybrid.source.coordinate(p[3], tex['scale'][0], tex['shifts'], tex['uls'],
                                         tex['cms'], tex['masks'], tex['width'])
            t = hybrid.source.coordinate(p[4], tex['scale'][1], tex['shiftt'], tex['ult'],
                                         tex['cmt'], tex['maskt'], tex['height'])
            c = tex['colors'][t * tex['width'] + s]
        else:
            c = (255, 255, 255, 255)
        light = hybrid.shade(p, face['lighting'])
        prim = [v / 255 for v in face['prim'][:3]]
        return tuple(max(0, min(255, round(c[k] * light[k] * prim[k]))) for k in range(3)) + (c[3],)


def lod2_faces(surface, origin, cell, pool, heights):
    """2x2 heightfield quads over one cell; corners shared across cells."""
    step = (1 << CELL_SHIFT) // LOD2_GRID
    cx, cz = cell
    out = []

    def corner(i, j):
        key = (cx * LOD2_GRID + i, cz * LOD2_GRID + j)
        if key not in heights:
            x, z = origin[0] + key[0] * step, origin[1] + key[1] * step
            hit = surface.top(x, z)
            heights[key] = None if hit is None else hit[1][1]
        return heights[key]

    for i in range(LOD2_GRID):
        for j in range(LOD2_GRID):
            x0 = origin[0] + (cx * LOD2_GRID + i) * step
            z0 = origin[1] + (cz * LOD2_GRID + j) * step
            pixels, under = [], []
            for py in range(LOD2_TILE):
                for px in range(LOD2_TILE):
                    u, v = px / (LOD2_TILE - 1), py / (LOD2_TILE - 1)
                    hit = surface.top(x0 + u * step, z0 + v * step)
                    if hit is not None:
                        under.append(hit[1][1])
                    pixels.append(surface.shade(hit))
            if not any(p[3] >= 64 for p in pixels):
                continue  # no surface under this quad: nothing to draw far away
            ys = [corner(i, j), corner(i + 1, j), corner(i + 1, j + 1), corner(i, j + 1)]
            known = [y for y in ys if y is not None]
            if not known:  # no corner on a surface: use the heights under the quad
                known = under
            ys = [y if y is not None else sum(known) / len(known) for y in ys]
            clut, packed = hybrid.quantize(pixels, LOD2_TILE, LOD2_TILE)
            tile = pool.add(LOD2_TILE, LOD2_TILE, clut, packed)
            out.append(_face([(x0, ys[0], z0), (x0 + step, ys[1], z0),
                              (x0 + step, ys[2], z0 + step), (x0, ys[3], z0 + step)], tile))
    return out


def build_pieces(positions, records, tiles, source_faces, lod_settings, lod0_source):
    """Return (pieces, pool, origin)."""
    pool = Pool(tiles.values())  # original ids are preserved: pool id == tile index
    lod_objects = {int(k): v for k, v in lod_settings.items()}
    xs = [p[0] for p in positions]
    zs = [p[2] for p in positions]
    origin = (min(xs), min(zs))
    cells = collections.defaultdict(list)
    objects = collections.defaultdict(list)
    for r in records:
        face = _face([positions[i] for i in r['indices'][:3 if r['indices'][2] == r['indices'][3] else 4]],
                     r['tile'], r['cull'], r['mesh'])
        if r['object'] in lod_objects:
            objects[r['object']].append(face)
            continue
        p = face['points']
        cell = ((sum(q[0] for q in p) // len(p) - origin[0]) >> CELL_SHIFT,
                (sum(q[2] for q in p) // len(p) - origin[1]) >> CELL_SHIFT)
        cells[cell].append(face)
    pieces = []
    for cell in sorted(cells):
        pieces.append(dict(kind=KIND_FULL, cell=cell, group=('cell', cell), near=0, far=FULL_RING, faces=cells[cell]))
    surface = Surface([f for f in source_faces if f.get('object') not in lod_objects])
    heights = {}
    for cell in sorted(cells):
        faces = lod2_faces(surface, origin, cell, pool, heights)
        if faces:
            x0 = origin[0] + (cell[0] << CELL_SHIFT)
            z0 = origin[1] + (cell[1] << CELL_SHIFT)
            pieces.append(dict(kind=KIND_FAR, cell=cell, group=('cell', cell), near=FULL_RING, far=FAR_INF, faces=faces,
                               cell_bounds=(x0, 0, z0, x0 + (1 << CELL_SHIFT), 0, z0 + (1 << CELL_SHIFT))))
    near_faces = lod0_faces(lod0_source, pool) if lod0_source else {}
    for obj in sorted(lod_objects):
        setting = lod_objects[obj]
        if obj not in objects:
            raise ValueError('LOD object %d has no faces in the Field' % obj)
        near = setting['lod0_distance'] if near_faces.get(obj) else 0
        cull = min(setting['cull_distance'], FAR_INF - 1)
        if not 0 <= near <= cull:
            raise ValueError('LOD distances out of range for object %d' % obj)
        pieces.append(dict(kind=KIND_LOD1, object=obj, group=('object', obj), near=near, far=cull, faces=objects[obj]))
        if near_faces.get(obj):
            pieces.append(dict(kind=KIND_LOD0, object=obj, group=('object', obj), near=0, far=near, faces=near_faces[obj]))
    for piece in pieces:
        points = [p for f in piece['faces'] for p in f['points']]
        b = _bounds(points)
        # A LOD2 piece's band is measured to its whole cell, so it can never be
        # hidden while the full piece of the same cell is also hidden.
        if 'cell_bounds' in piece:
            c = piece['cell_bounds']
            b = (c[0], b[1], c[2], c[3], b[4], c[5])
        if piece['kind'] == KIND_FULL:
            x0 = origin[0] + (piece['cell'][0] << CELL_SHIFT)
            z0 = origin[1] + (piece['cell'][1] << CELL_SHIFT)
            b = (min(b[0], x0), b[1], min(b[2], z0),
                 max(b[3], x0 + (1 << CELL_SHIFT)), b[4], max(b[5], z0 + (1 << CELL_SHIFT)))
        piece['bounds'] = b
        verts = []
        ids = {}
        for f in piece['faces']:
            f['local'] = []
            for p in f['points']:
                if p not in ids:
                    ids[p] = len(verts)
                    verts.append(p)
                f['local'].append(ids[p])
            if len(f['local']) == 3:
                f['local'].append(f['local'][-1])
        piece['points'] = verts
        piece['tiles'] = sorted({f['tile'] for f in piece['faces'] if f['tile'] is not None})
    if len(pieces) > MAX_PIECES:
        raise ValueError('%d Field pieces exceed the one-byte object id' % len(pieces))
    return pieces, pool, origin


def resident(pieces, point, widen, owl=False):
    """Pieces that may be resident; owl mode keeps every LOD object at LOD1."""
    out = []
    for i, piece in enumerate(pieces):
        if owl and piece['kind'] == KIND_LOD0:
            continue
        if owl and piece['kind'] == KIND_LOD1:
            if xz_distance(point, piece['bounds']) < piece['far'] + widen:
                out.append(i)
            continue
        d = xz_distance(point, piece['bounds'])
        lo = max(0, piece['near'] - widen)
        hi = piece['far'] + widen if piece['far'] != FAR_INF else None
        if d >= lo and (hi is None or d < hi):
            out.append(i)
    return out


def sweep_mode(pieces, pool, owl):
    """Worst resident union over the lattice for one mode."""
    b = [p['bounds'] for p in pieces]
    x0, x1 = min(v[0] for v in b), max(v[3] for v in b)
    z0, z1 = min(v[2] for v in b), max(v[5] for v in b)
    worst = dict(points=0, polys=0, pieces=0)
    bucket_worst = collections.Counter()
    worst_at = {}
    cells = []
    group_of = {}
    for i, piece in enumerate(pieces):
        group_of.setdefault(piece['group'], []).append(i)
    for x in range(x0, x1 + LATTICE, LATTICE):
        for z in range(z0, z1 + LATTICE, LATTICE):
            ids = resident(pieces, (x, z), SWEEP_WIDEN, owl)
            # Members of one group are exclusive: the streamer swaps them in
            # one VDP1-idle step, so only the costlier member counts.
            chosen = collections.defaultdict(list)
            for i in ids:
                chosen[pieces[i]['group']].append(i)
            points = polys = count = 0
            buckets = collections.Counter()
            used_total = 0
            for members in chosen.values():
                points += max(len(pieces[i]['points']) for i in members)
                polys += max(len(pieces[i]['faces']) for i in members)
                count += 1
                per = [collections.Counter(bucket_of(len(pool.tiles[t]['pixels']))
                                           for t in pieces[i]['tiles']) for i in members]
                for size in set().union(*per):
                    buckets[size] += max(c[size] for c in per)
                used_total += max(len(pieces[i]['tiles']) for i in members)
            cells.append(dict(x=x, z=z, pieces=count, points=points, polys=polys,
                              tiles=used_total))
            for key, value in (('points', points), ('polys', polys), ('pieces', count)):
                if value > worst[key]:
                    worst[key], worst_at[key] = value, (x, z)
            for size, n in buckets.items():
                bucket_worst[size] = max(bucket_worst[size], n)
    return worst, worst_at, bucket_worst, cells


def sweep(pieces, pool, actor, owl_actor=None):
    """Capacity plan over both modes: normal, and owl (LOD0 off, owl counted)."""
    owl_actor = owl_actor or dict(tiles=[], polygons=0, vertices=0)
    worst, worst_at, bucket_worst, cells = sweep_mode(pieces, pool, False)
    owl_worst, owl_at, owl_buckets, _ = sweep_mode(pieces, pool, True)
    for size, n in owl_buckets.items():
        bucket_worst[size] = max(bucket_worst[size], n)
    buckets = sorted(bucket_worst.items())
    slots = sum(n for _, n in buckets)
    pool_bytes = sum(size * n for size, n in buckets)
    vram = pool_bytes + slots * 32
    actor_bytes = sum(tile_bytes(w, h) for w, h in actor['tiles'] + owl_actor['tiles'])
    plan = dict(worst=worst, worst_at=worst_at, buckets=buckets, slots=slots,
                pool_bytes=pool_bytes, vram=vram, actor_bytes=actor_bytes,
                vram_total=vram + actor_bytes + RUNTIME_SPRITE_BYTES,
                vram_limit=VDP1_USER_AREA, cells=cells)
    failures = []
    if worst['polys'] + actor['polygons'] > MAX_TABLE_POLYGONS:
        failures.append('Field resident %d polygons + %d actor exceed the %d-polygon table budget at %s'
                        % (worst['polys'], actor['polygons'], MAX_TABLE_POLYGONS, worst_at['polys']))
    if owl_worst['polys'] + actor['polygons'] + owl_actor['polygons'] > MAX_TABLE_POLYGONS:
        failures.append('Owl mode: Field %d + actor %d + owl %d polygons exceed %d at %s'
                        % (owl_worst['polys'], actor['polygons'], owl_actor['polygons'],
                           MAX_TABLE_POLYGONS, owl_at['polys']))
    if owl_worst['points'] + actor['vertices'] + owl_actor['vertices'] > MAX_VERTICES:
        failures.append('Owl mode: Field %d + actor %d + owl %d vertices exceed MaxVertices %d at %s'
                        % (owl_worst['points'], actor['vertices'], owl_actor['vertices'],
                           MAX_VERTICES, owl_at['points']))
    if worst['points'] + actor['vertices'] > MAX_VERTICES:
        failures.append('Field resident %d vertices + %d actor exceed MaxVertices %d at %s'
                        % (worst['points'], actor['vertices'], MAX_VERTICES, worst_at['points']))
    if plan['vram_total'] > VDP1_USER_AREA:
        failures.append('Field VRAM %d B (pools %d + CLUTs %d + actors %d + sprites %d) exceeds %d'
                        % (plan['vram_total'], pool_bytes, slots * 32, actor_bytes,
                           RUNTIME_SPRITE_BYTES, VDP1_USER_AREA))
    if 1 + slots + len(actor['tiles']) + len(owl_actor['tiles']) + RUNTIME_SPRITE_SLOTS > MAX_SPRITE_SLOTS:
        failures.append('Field %d tile slots exceed sprite slots' % slots)
    if worst['pieces'] > MAX_PIECES:
        failures.append('%d resident pieces exceed the one-byte object id' % worst['pieces'])
    plan['owl_worst'], plan['owl_at'] = owl_worst, owl_at
    plan['failures'] = failures
    return plan


def pack(pieces, pool, plan, normal=face_normal):
    """Big-endian KRM2 file: header, buckets, tiles, CLUTs, pieces, data, pool."""
    bucket_index = {size: i for i, (size, _) in enumerate(plan['buckets'])}
    pixels = bytearray()
    tile_rows = []
    for t in pool.tiles:
        size = bucket_of(len(t['pixels']))
        tile_rows.append(TILE.pack(t['width'], t['height'], len(pixels), len(t['pixels']),
                                   bucket_index.get(size, 0xFFFF), 0))
        pixels.extend(t['pixels'] + bytes((-len(t['pixels'])) % 8))
    head_bytes = (HEADER.size + BUCKET.size * len(plan['buckets']) + TILE.size * len(pool.tiles) +
                  32 * len(pool.tiles) + PIECE.size * len(pieces))
    data = bytearray()
    rows = []
    groups = {}
    for piece in pieces:
        groups.setdefault(piece['group'], len(groups))
    for piece in pieces:
        baked = [(x, -y, z) for x, y, z in piece['points']]
        offset = head_bytes + len(data)
        for p in baked:
            data.extend(struct.pack('>3i', *(v * 65536 for v in p)))
        for f in piece['faces']:
            data.extend(struct.pack('>3i4H', *normal(baked, f['local']), *f['local']))
        for f in piece['faces']:
            n = normal(baked, f['local'])
            sort = 0x66 if floor_uses_far_sort(baked, f['local'], n) else 0x67
            data.extend(struct.pack('>BB5H', 0 if f['cull'] else 1, sort, f['tile'],
                                    0x88 | (0x100 if f['mesh'] else 0), 0, 0, 2))
        data.extend(struct.pack('>%dH' % len(piece['tiles']), *piece['tiles']))
        data.extend(bytes((-len(data)) % 4))
        b = piece['bounds']
        rows.append(PIECE.pack(*b, piece['near'], piece['far'], len(piece['points']),
                               len(piece['faces']), len(piece['tiles']), piece['kind'],
                               groups[piece['group']], 0, offset, 0))
    pool_offset = head_bytes + len(data)
    total = pool_offset + len(pixels)
    header = HEADER.pack(MAGIC, VERSION, len(pieces), len(pool.tiles), len(pixels),
                         len(plan['buckets']), plan['slots'], total,
                         max(plan['worst']['points'], plan['owl_worst']['points']),
                         max(plan['worst']['polys'], plan['owl_worst']['polys']),
                         max(plan['worst']['pieces'], plan['owl_worst']['pieces']),
                         HYSTERESIS, pool_offset, len(groups), FIELD_FAR, 0)
    out = bytearray(header)
    for size, count in plan['buckets']:
        out.extend(BUCKET.pack(size, count))
    for row in tile_rows:
        out.extend(row)
    for t in pool.tiles:
        out.extend(struct.pack('>16H', *t['clut']))
    for row in rows:
        out.extend(row)
    assert len(out) == head_bytes
    out.extend(data)
    out.extend(pixels)
    assert len(out) == total
    return bytes(out)


def unpack(blob):
    """Host parser for tests: returns (header tuple, buckets, tiles, pieces)."""
    h = HEADER.unpack_from(blob, 0)
    if h[0] != MAGIC or h[1] != VERSION or h[7] != len(blob):
        raise ValueError('bad KRM2 header')
    at = HEADER.size
    buckets = [BUCKET.unpack_from(blob, at + i * BUCKET.size) for i in range(h[5])]
    at += BUCKET.size * h[5]
    tiles = [TILE.unpack_from(blob, at + i * TILE.size) for i in range(h[3])]
    at += TILE.size * h[3] + 32 * h[3]
    pieces = []
    for i in range(h[2]):
        row = PIECE.unpack_from(blob, at + i * PIECE.size)
        pieces.append(dict(bounds=row[:6], near=row[6], far=row[7], points=row[8], polys=row[9],
                           refs=row[10], kind=row[11], group=row[12], offset=row[14]))
    return h, buckets, tiles, pieces


def bake(oot, rom_dir, head, actor, owl_actor, document, out_path, report_path=None,
         room='spot00_room_0'):
    """Full Field bake; raises on any budget failure. Returns a sizing summary."""
    import copy
    import json
    import tempfile
    import pathlib
    from map_meshes import apply_lods
    layout = copy.deepcopy(document) if document else {}
    lods = layout.get('lods', {})
    # LOD1 conversion runs on the original faces: the close-up meshes are baked
    # separately at a fixed density, so they never starve the Field's tiles.
    for entry in lods.values():
        entry['bundle'] = None
    merged = dict(tiles=list(actor['tiles']) + list(owl_actor['tiles']),
                  polygons=actor['polygons'] + owl_actor['polygons'],
                  vertices=actor['vertices'] + owl_actor['vertices'])
    with tempfile.TemporaryDirectory() as temp:
        folder = pathlib.Path(temp)
        _, positions, faces, tiles = hybrid.convert(
            oot, head, merged, folder, rom_dir=rom_dir, room=room, prefix='spot00',
            layout=layout, base_tile_limit=32, source_tessellation=True, wall_split_limit=3)
        manifest = json.loads((folder / 'texture_manifest.json').read_text())
    records = manifest['faces']
    source_faces = [f for f in hybrid.load_faces(oot, rom_dir, prefix='spot00') if f['room'] == room]
    lod0_source = []
    lod_settings = {}
    if document and document.get('lods'):
        segments = hybrid.source.extract(oot, rom_dir, prefix='spot00')
        extended, settings = apply_lods(source_faces, segments, document)
        lod0_source = [f for f in extended if f.get('lod0_of') is not None and f['room'] == room]
        lod_settings = settings.get(room, {})
    pieces, pool, origin = build_pieces(positions, records, tiles, source_faces,
                                        lod_settings, lod0_source)
    plan = sweep(pieces, pool, actor, owl_actor)
    summary = dict(origin=origin, pieces=len(pieces), tiles=len(pool.tiles),
                   kinds=dict(collections.Counter(p['kind'] for p in pieces)),
                   worst=plan['worst'], worst_at=plan['worst_at'], owl_worst=plan['owl_worst'], buckets=plan['buckets'],
                   slots=plan['slots'], vram_total=plan['vram_total'], vram_limit=plan['vram_limit'],
                   actor_polygons=actor['polygons'], failures=plan['failures'])
    if report_path is not None:
        pathlib.Path(report_path).write_text(json.dumps(dict(summary, cells=plan['cells']), indent=1) + '\n')
    print('field stream: %d pieces (%s), %d pool tiles; worst resident %d polys / %d verts / '
          '%d pieces (owl mode %d / %d); VRAM %d of %d B (%d slots)'
          % (len(pieces), summary['kinds'], len(pool.tiles), plan['worst']['polys'],
             plan['worst']['points'], plan['worst']['pieces'], plan['owl_worst']['polys'],
             plan['owl_worst']['points'], plan['vram_total'], plan['vram_limit'], plan['slots']),
          flush=True)
    if plan['failures']:
        raise ValueError('; '.join(plan['failures']))
    blob = pack(pieces, pool, plan)
    pathlib.Path(out_path).write_bytes(blob)
    return dict(summary, file_bytes=len(blob))
