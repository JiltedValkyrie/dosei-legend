#!/usr/bin/env python
"""Occlusion masks for prerendered interiors, from the room's own depth mesh.

An OoT ROOM_SHAPE_TYPE_IMAGE room draws its JPEG backdrop and then the room
entry's opa display list (z_room.c Room_DrawImageSingle): untextured
geometry that only fills the Z-buffer, so the counter and walls hide actors
standing behind them while the picture stays the backdrop. VDP1 has no
Z-buffer. The Saturn equivalent here:

  * project that depth mesh through the exact runtime camera (main.c view:
    flip X, RotX(-pitch), RotY(-yaw), translate; SGL screen distance from the
    scene table), z-buffer it offline, and record per pixel which source
    surface is nearest and at what depth;
  * keep a pixel only where an actor could stand BEHIND that surface (walkable
    collision floor and the placed actors, extruded to head height), so floor
    pixels and walls nothing can pass behind never become masks;
  * cut the kept pixels into 16x16 screen tiles PER SOURCE SURFACE (coplanar,
    connected triangles), each with its own sort depth, so one big mask can
    never hide an actor standing in front of another part;
  * copy the backdrop's own pixels into the tile. Transparency is coverage:
    a pixel the mesh does not cover (door openings, gaps) is 0x0000 whatever
    colour the backdrop has there; a covered black pixel stays opaque.

Runtime draws each tile as a VDP1 sprite sorted at its depth with the actor
polygons. Per-polygon Z sort is still an approximation of the N64's
per-pixel test; crossings need a runtime check before other rooms use it.
Fixed-camera rooms only: a pivot (panorama) room has no single view.
"""
import argparse
import math
import pathlib
import struct
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'shared/tools'))
sys.path.insert(0, str(HERE))
import build_kokiri_scene as source                          # noqa: E402
from build_scene_table import SCENES, fixed_camera          # noqa: E402
import asset_names                                           # noqa: E402

W, H, TILE = 320, 240, 16
ACTOR_HEIGHT = 60          # tallest actor top above its floor (child cast)
DEPTH_EPSILON = 3          # a surface must be this much nearer than the actor
LOWEST_SAMPLE = 10         # nothing stands under a floor: skip foot-level samples
TILE_DEPTH_BIAS = 16       # sort key past the farthest pixel: covers an actor polygon's own depth span (Link head, Kronos 2026-09-28); shopkeeper sits ~50 behind
SURFACE_FOLD = 0.5         # cos 60 deg: sharper folds start a new surface


def room_depth_mesh(room):
    """Triangles of the image room's opa DL, world coordinates."""
    for off in range(0, 0x400, 8):
        if room[off] == 0x14:
            break
        if room[off] != 0x0A:
            continue
        shape = int.from_bytes(room[off + 4:off + 8], 'big') & 0xFFFFFF
        if room[shape] != 1 or room[shape + 1] != 1:
            raise ValueError('not a single-image room')
        entry = int.from_bytes(room[shape + 4:shape + 8], 'big') & 0xFFFFFF
        opa, _xlu = struct.unpack_from('>II', room, entry)
        break
    else:
        raise ValueError('room has no mesh header')
    tris, cache = [], [None] * 64

    def walk(address, batch):
        a = address & 0xFFFFFF
        while True:
            w0, w1 = struct.unpack_from('>II', room, a)
            op = w0 >> 24
            if op == 0x01:                           # G_VTX (F3DEX2)
                n = (w0 >> 12) & 0xFF
                end = (w0 & 0xFF) >> 1
                base = w1 & 0xFFFFFF
                for k in range(n):
                    cache[end - n + k] = struct.unpack_from('>3h', room, base + 16 * k)
                batch[0] += 1
            elif op in (0x05, 0x06):                 # G_TRI1 / G_TRI2
                words = [w0] if op == 0x05 else [w0, w1]
                for w in words:
                    i = [((w >> s) & 0xFF) // 2 for s in (16, 8, 0)]
                    tris.append(([cache[j] for j in i], batch[0]))
            elif op == 0xDE:
                if (w1 >> 24) == 3:
                    walk(w1, batch)
                if (w0 >> 16) & 0xFF:
                    return
            elif op == 0xDF:
                return
            a += 8
    walk(opa, [0])
    return tris


class Camera:
    """main.c: slScale(-1,1,1) slRotX(-pitch) slRotY(-yaw) T(-x,+y,-z) on
    SGL coordinates (x, -y, z); screen = centre + v * dist / v.z."""
    def __init__(self, cam, dist):
        self.x, self.y, self.z = cam['x'], cam['y'], cam['z']
        pitch = -(cam['pitch'] if cam['pitch'] < 0x8000 else cam['pitch'] - 0x10000)
        self.p = -pitch * math.pi / 32768       # RotX(-demo_pitch)
        yaw = cam['yaw'] & 0xFFFF
        self.yw = -yaw * math.pi / 32768        # RotY(-demo_yaw)
        self.dist = dist

    def view(self, v):
        x, y, z = v[0] - self.x, -(v[1] - self.y), v[2] - self.z
        c, s = math.cos(self.yw), math.sin(self.yw)
        x, z = c * x + s * z, -s * x + c * z                # RotY
        c, s = math.cos(self.p), math.sin(self.p)
        y, z = c * y - s * z, s * y + c * z                 # RotX
        return (-x, y, z)                                   # flip X

    def screen(self, v):
        x, y, z = self.view(v)
        if z <= 1:
            return None
        return (W / 2 + x * self.dist / z, H / 2 + y * self.dist / z, z)


def raster(tri, fn):
    """Scanline fill of a screen triangle (x, y, z); fn(px, py, z)."""
    (x0, y0, z0), (x1, y1, z1), (x2, y2, z2) = tri
    area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
    if abs(area) < 1e-6:
        return
    lo_x, hi_x = max(0, int(math.floor(min(x0, x1, x2)))), min(W - 1, int(math.ceil(max(x0, x1, x2))))
    lo_y, hi_y = max(0, int(math.floor(min(y0, y1, y2)))), min(H - 1, int(math.ceil(max(y0, y1, y2))))
    for py in range(lo_y, hi_y + 1):
        cy = py + 0.5
        for px in range(lo_x, hi_x + 1):
            cx = px + 0.5
            a = ((x1 - cx) * (y2 - cy) - (x2 - cx) * (y1 - cy)) / area
            b = ((x2 - cx) * (y0 - cy) - (x0 - cx) * (y2 - cy)) / area
            c = 1 - a - b
            if a < -1e-4 or b < -1e-4 or c < -1e-4:
                continue
            # perspective-correct depth: interpolate 1/z
            inv = a / z0 + b / z1 + c / z2
            fn(px, py, 1 / inv)


def plane_key(tri):
    (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
    ux, uy, uz = bx - ax, by - ay, bz - az
    vx, vy, vz = cx - ax, cy - ay, cz - az
    nx, ny, nz = uy * vz - uz * vy, uz * vx - ux * vz, ux * vy - uy * vx
    length = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
    nx, ny, nz = nx / length, ny / length, nz / length
    d = nx * ax + ny * ay + nz * az
    return (round(nx * 20), round(ny * 20), round(nz * 20), round(d / 4))


def surfaces(tris):
    """Group coplanar triangles that share vertices: one source surface each."""
    parent = list(range(len(tris)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    # Connected pieces (shared vertices) whose faces do not fold more than
    # SURFACE_FOLD against each other: a counter's front and top stay apart,
    # a round stump stays one piece.
    normals = [plane_key(verts)[:3] for verts, _ in tris]
    seen = {}
    for i, (verts, _batch) in enumerate(tris):
        for v in verts:
            for j in seen.setdefault(v, []):
                a, b = normals[i], normals[j]
                dot = (a[0]*b[0] + a[1]*b[1] + a[2]*b[2]) / 400.0
                if dot >= SURFACE_FOLD:
                    parent[find(i)] = find(j)
            seen[v].append(i)
    ids, out = {}, []
    for i in range(len(tris)):
        out.append(ids.setdefault(find(i), len(ids)))
    return out, len(ids)


def actor_far_depth(camera, floors, actors):
    """Per pixel: the farthest depth at which any actor could be seen."""
    far = [[0.0] * W for _ in range(H)]

    def mark(point):
        s = camera.screen(point)
        if not s:
            return
        px, py = int(s[0]), int(s[1])
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                x, y = px + dx, py + dy
                if 0 <= x < W and 0 <= y < H and s[2] > far[y][x]:
                    far[y][x] = s[2]
    for tri in floors:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = tri
        steps = max(1, int(max(abs(bx - ax), abs(bz - az), abs(cx - ax), abs(cz - az)) / 4))
        for i in range(steps + 1):
            for j in range(steps + 1 - i):
                u, v = i / steps, j / steps
                x = ax + (bx - ax) * u + (cx - ax) * v
                y = ay + (by - ay) * u + (cy - ay) * v
                z = az + (bz - az) * u + (cz - az) * v
                for h in range(LOWEST_SAMPLE, ACTOR_HEIGHT + 1, 5):
                    mark((x, y + h, z))
    for (x, y, z, radius) in actors:
        for h in range(LOWEST_SAMPLE, ACTOR_HEIGHT + 1, 4):
            for k in range(16):
                a = k * math.pi / 8
                mark((x + radius * math.cos(a), y + h, z + radius * math.sin(a)))
    return far


def build_scene(oot, rom_dir, index, backdrop, actors, preview=None):
    entry = SCENES[index]
    segments = source.extract(oot, rom_dir, prefix=entry['prefix'], expect=entry['rooms'] + 1)
    scene = segments[entry['prefix'] + '_scene']
    cam = fixed_camera(scene)
    dist = round(120.0 / math.tan(math.radians(cam['fov'] / 200.0)))
    camera = Camera(cam, dist)
    tris = room_depth_mesh(segments[entry['prefix'] + '_room_0'])
    owner, count = surfaces(tris)

    depth = [[math.inf] * W for _ in range(H)]
    surf = [[-1] * W for _ in range(H)]
    for (verts, _batch), sid in zip(tris, owner):
        projected = [camera.screen(v) for v in verts]
        if None in projected:
            continue

        def put(px, py, z, sid=sid):
            if z < depth[py][px]:
                depth[py][px] = z
                surf[py][px] = sid
        raster(projected, put)

    collision = source.collision_data(scene)
    floors = [p['vertices'] for p in collision['polys'] if p['normal'][1] > 8000]
    far = actor_far_depth(camera, floors, actors)
    keep = [[surf[y][x] >= 0 and depth[y][x] + DEPTH_EPSILON < far[y][x]
             for x in range(W)] for y in range(H)]

    tiles = []
    for sid in range(count):
        for ty in range(0, H, TILE):
            for tx in range(0, W, TILE):
                zs = [depth[y][x] for y in range(ty, ty + TILE) for x in range(tx, tx + TILE)
                      if keep[y][x] and surf[y][x] == sid]
                if not zs:
                    continue
                zs.sort()
                pixels = bytearray()
                for y in range(ty, ty + TILE):
                    for x in range(tx, tx + TILE):
                        if keep[y][x] and surf[y][x] == sid:
                            c = struct.unpack_from('>H', backdrop, 2 * (y * W + x))[0]
                            pixels += struct.pack('>H', c | 0x8000)
                        else:
                            pixels += b'\0\0'
                # Sort at the tile's FARTHEST covered pixel (+bias): an actor in
                # front of any part of it must win (Kronos 2026-09-28: the
                # median hid Link's head in front of the counter top). Actors
                # behind stand far past a surface, never inside it.
                tiles.append((tx, ty, int(math.ceil(zs[-1])) + TILE_DEPTH_BIAS, sid,
                              bytes(pixels)))
    if preview:
        write_preview(preview, backdrop, tris, camera, keep, surf)
    return dict(camera=cam, dist=dist, triangles=len(tris), surfaces=count, tiles=tiles)


def write_preview(path, backdrop, tris, camera, keep, surf):
    from PIL import Image, ImageDraw
    img = Image.new('RGB', (W, H))
    px = img.load()
    for y in range(H):
        for x in range(W):
            c = struct.unpack_from('>H', backdrop, 2 * (y * W + x))[0]
            r, g, b = (c & 31) << 3, ((c >> 5) & 31) << 3, ((c >> 10) & 31) << 3
            if keep[y][x]:
                h = (surf[y][x] * 97) % 360
                r, g, b = (r + (255 if h < 120 else 0)) // 2, (g + (255 if 120 <= h < 240 else 0)) // 2, (b + (255 if h >= 240 else 0)) // 2
            px[x, y] = (r, g, b)
    draw = ImageDraw.Draw(img)
    for verts, _ in tris:
        s = [camera.screen(v) for v in verts]
        if None not in s:
            draw.polygon([(p[0], p[1]) for p in s], outline=(255, 255, 0))
    img = img.resize((W * 3, H * 3), Image.NEAREST)
    img.save(path)


def pack(result):
    """'KMSK' u16 count u16 tile; per tile: x y w h depth(int16) surface, then
    w*h big-endian RGB555 (MSB set = opaque, 0x0000 = transparent)."""
    out = bytearray(b'KMSK' + struct.pack('>HH', len(result['tiles']), TILE))
    for tx, ty, z, sid, pixels in result['tiles']:
        out += struct.pack('>6h', tx, ty, TILE, TILE, z, sid) + pixels
    return bytes(out)


def build_shop_counter(oot, rom_dir, backdrop, dest):
    """Reuse the authored counter surface in the moving browsing view.

    Its material comes from the original fixed-camera picture, projected back
    onto the depth mesh. Unlike screen masks this geometry follows camera yaw.
    """
    import build_link_model as link
    segments = source.extract(oot, rom_dir, prefix='kokiri_shop', expect=2)
    cam = fixed_camera(segments['kokiri_shop_scene'])
    camera = Camera(cam, round(120 / math.tan(math.radians(cam['fov']/200))))
    colours = [((c & 31)*255//31, ((c>>5)&31)*255//31,
                ((c>>10)&31)*255//31, 255)
               for (c,) in struct.iter_unpack('>H', backdrop)]
    texture = dict(width=W, height=H, colors=colours, scale=(1.,1.),
                   shifts=0, shiftt=0, uls=0, ult=0, cms=2, cmt=2, masks=0, maskt=0)
    faces=[]
    for verts, _ in room_depth_mesh(segments['kokiri_shop_room_0']):
        # Source counter rail/front: x +/-109, z -7..15, y 0..40.
        if not all(abs(x)<=109 and 0<=y<=40 and -7<=z<=15 for x,y,z in verts):
            continue
        # Split long counter triangles to keep sorting and picture sampling local.
        pending=[verts]
        while pending:
            tri=pending.pop()
            edges=[math.dist(tri[i],tri[(i+1)%3]) for i in range(3)]
            i=max(range(3), key=edges.__getitem__)
            if edges[i]>32:
                a,b,c=tri[i],tri[(i+1)%3],tri[(i+2)%3]
                mid=tuple((a[k]+b[k])/2 for k in range(3))
                pending.extend(((a,mid,c),(mid,b,c)))
                continue
            screen=[camera.screen(v) for v in tri]
            if None in screen: continue
            vertices=[tuple(round(c) for c in v)+(uv[0],uv[1],255,255,255,255)
                      for v,uv in zip(tri,screen)]
            faces.append(dict(vertices=vertices, texture=texture, lighting=False,
                              transparent=False, cull=False, limb=0, full_texture=True))
    if not faces: raise ValueError('source shop counter missing')
    link.write_model(faces,dest,character=False)
    print('counter : %d source-derived faces' % len(faces))


def main():
    here = HERE.parent
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', default=None)
    ap.add_argument('--cd', type=pathlib.Path, default=here / 'build/cd')
    ap.add_argument('--generated', type=pathlib.Path, default=here / 'build/generated')
    ap.add_argument('--preview', type=pathlib.Path)
    args = ap.parse_args()
    sys.path.insert(0, str(args.generated))
    # Shop only until its crossings are proven in Kronos (Astra 2026-09-28).
    index = next(i for i, e in enumerate(SCENES) if e['prefix'] == 'kokiri_shop')
    backdrop = (args.cd / asset_names.room_asset(index, 0, 'RGB')).read_bytes()
    if len(backdrop) != W * H * 2:
        sys.exit('masks: backdrop is %d bytes' % len(backdrop))
    # EnOssan (0,0,-59) and the shop's child Kokiri stand where Link cannot.
    build_shop_counter(args.oot, args.rom_dir, backdrop, args.cd / "COUNTER.BIN")
    actors = [(0, 0, -59, 16)]
    result = build_scene(args.oot, args.rom_dir, index, backdrop, actors, args.preview)
    name = asset_names.room_asset(index, 0, 'MSK')
    (args.cd / name).write_bytes(pack(result))
    print('masks  : %s  %d depth triangles, %d surfaces, %d tiles, %d VRAM bytes'
          % (name, result['triangles'], result['surfaces'], len(result['tiles']),
             len(result['tiles']) * TILE * TILE * 2))


if __name__ == '__main__':
    main()
