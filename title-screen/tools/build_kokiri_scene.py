#!/usr/bin/env python3
"""Convert US 1.2 Kokiri room display lists into textured VDP1 surfaces.

F3DEX2 vertices/triangles and RDP texture loads come directly from the ROM.
UVs are baked into per-surface tiles because VDP1 maps whole rectangular
textures onto distorted sprites. Triangles collapse the last two corners.
No collision geometry is used. Actor models and N64 combiner effects are
outside this first static-room renderer.
"""
import argparse
import collections
import csv
import hashlib
import json
import math
import re
import struct
from pathlib import Path

from PIL import Image
from extract_title_source import yaz0

ROOT = Path(__file__).resolve().parents[1]


def extract(root):
    config = root / 'baseroms/ntsc-1.2'
    roms = [p for p in config.glob('*.z64') if hashlib.md5(p.read_bytes()).hexdigest()
            == '57a9719ad547c516342e1a15d5c28c3d']
    assert len(roms) == 1, 'Verified US 1.2 ROM required'
    rom = roms[0].read_bytes()
    dma = int(re.search(r'dmadata_start: (\w+)', (config / 'config.yml').read_text())[1], 16)
    segments = {}
    with (config / 'segments.csv').open() as f:
        for index, row in enumerate(csv.DictReader(f)):
            name = row['Name']
            if name != 'spot04_scene' and not name.startswith('spot04_room_'):
                continue
            start, end, physical, packed_end = struct.unpack_from('>4I', rom, dma + index * 16)
            data = yaz0(rom[physical:packed_end]) if packed_end else rom[physical:physical + end - start]
            assert len(data) == end - start
            segments[name] = bytes(data)
    assert len(segments) == 4
    return segments


def rgba16(value):
    return ((value >> 11 & 31) * 255 // 31, (value >> 6 & 31) * 255 // 31,
            (value >> 1 & 31) * 255 // 31, 255 if value & 1 else 0)


class DisplayLists:
    def __init__(self, scene, room):
        self.segments = {2: scene, 3: room}
        self.cache = [None] * 32
        self.tiles = [{} for _ in range(8)]
        self.images = {}
        self.palette = [(255, 255, 255, 255)] * 256
        self.image = None
        self.texture_on = False
        self.texture_tile = 0
        self.scale = (1.0, 1.0)
        self.geom = 0
        self.prim = (255, 255, 255, 255)
        self.faces = []
        self.textures = {}
        self.opcodes = collections.Counter()
        self.external_lists = set()

    def read(self, address, size):
        segment, offset = address >> 24, address & 0xFFFFFF
        assert segment in self.segments, f'Unknown segment {segment:02x}'
        data = self.segments[segment]
        assert offset + size <= len(data), (hex(address), size, len(data))
        return data[offset:offset + size]

    def texture(self):
        if not self.texture_on:
            return None
        tile = self.tiles[self.texture_tile]
        if tile.get('tmem') not in self.images:
            raise ValueError(f'No texture loaded at {tile}')
        image = self.images[tile['tmem']]
        key = (tuple(sorted(tile.items())), image, tuple(self.palette), self.scale)
        if key in self.textures:
            return self.textures[key]
        address, image_width, image_fmt, image_size = image
        width = (tile['lrs'] - tile['uls']) // 4 + 1
        height = (tile['lrt'] - tile['ult']) // 4 + 1
        fmt, size = tile['fmt'], tile['size']
        count = width * height
        raw = self.read(address, (count * (4 << size) + 7) // 8)
        colors = []
        for i in range(count):
            if size == 0:
                value = (raw[i // 2] >> (4 if i % 2 == 0 else 0)) & 15
            elif size == 1:
                value = raw[i]
            elif size == 2:
                value = int.from_bytes(raw[2*i:2*i+2], 'big')
            else:
                value = int.from_bytes(raw[4*i:4*i+4], 'big')
            if fmt == 0 and size == 2:
                color = rgba16(value)
            elif fmt == 0 and size == 3:
                color = tuple(raw[4*i:4*i+4])
            elif fmt == 2:
                color = self.palette[value + (tile['palette'] * 16 if size == 0 else 0)]
            elif fmt == 3 and size == 0:
                v = (value >> 1) * 255 // 7
                color = (v, v, v, (value & 1) * 255)
            elif fmt == 3 and size == 1:
                v = (value >> 4) * 17
                color = (v, v, v, (value & 15) * 17)
            elif fmt == 3 and size == 2:
                v = value >> 8
                color = (v, v, v, value & 255)
            elif fmt == 4:
                v = value * (17 if size == 0 else 1)
                color = (v, v, v, v)
            else:
                raise ValueError(f'Unsupported texture format {fmt}/{size}')
            colors.append(color)
        texture = dict(tile, width=width, height=height, colors=colors,
                       address=address, scale=self.scale)
        self.textures[key] = texture
        return texture

    def triangle(self, word, transparent):
        indices = [(word >> shift & 255) // 2 for shift in (16, 8, 0)]
        vertices = [self.cache[i] for i in indices]
        assert all(v is not None for v in vertices)
        if len({v[:3] for v in vertices}) < 3:
            return
        self.faces.append(dict(vertices=vertices, texture=self.texture(),
                               lighting=bool(self.geom & 0x20000), prim=self.prim,
                               transparent=transparent, cull=bool(self.geom & 0x400)))

    def walk(self, address, transparent=False, depth=0):
        assert depth < 32
        # Dynamic segments 8+ supply texture-scroll command lists. Static
        # geometry remains valid at scroll offset zero.
        if address >> 24 not in self.segments:
            self.external_lists.add(hex(address))
            assert address >> 24 >= 8, hex(address)
            return
        for _ in range(100000):
            w0, w1 = struct.unpack('>II', self.read(address, 8))
            address += 8
            op = w0 >> 24
            self.opcodes[op] += 1
            if op == 0xDF:
                return
            if op == 0xDE:
                self.walk(w1, transparent, depth + 1)
                if (w0 >> 16) & 1:
                    return
            elif op == 0x01:
                n = (w0 >> 12) & 255
                first = ((w0 >> 1) & 127) - n
                assert 0 <= first and first + n <= 32
                for i in range(n):
                    x, y, z, flag, u, v, r, g, b, a = struct.unpack('>hhhHhhBBBB', self.read(w1 + i * 16, 16))
                    self.cache[first + i] = (x, y, z, u / 32, v / 32, r, g, b, a)
            elif op == 0x05:
                self.triangle(w0, transparent)
            elif op == 0x06:
                self.triangle(w0, transparent)
                self.triangle(w1, transparent)
            elif op == 0xD9:
                self.geom = (self.geom & (w0 & 0xFFFFFF)) | w1
            elif op == 0xD7:
                self.texture_on = bool(w0 & 255)
                self.texture_tile = (w0 >> 8) & 7
                self.scale = ((w1 >> 16) / 65536, (w1 & 65535) / 65536)
            elif op == 0xFA:
                self.prim = tuple((w1 >> shift) & 255 for shift in (24, 16, 8, 0))
            elif op == 0xFD:
                self.image = (w1, (w0 & 4095) + 1, (w0 >> 21) & 7, (w0 >> 19) & 3)
            elif op == 0xF5:
                tile = self.tiles[(w1 >> 24) & 7]
                tile.update(fmt=(w0 >> 21) & 7, size=(w0 >> 19) & 3,
                            line=(w0 >> 9) & 511, tmem=w0 & 511,
                            palette=(w1 >> 20) & 15, cmt=(w1 >> 18) & 3,
                            maskt=(w1 >> 14) & 15, shiftt=(w1 >> 10) & 15,
                            cms=(w1 >> 8) & 3, masks=(w1 >> 4) & 15, shifts=w1 & 15)
            elif op == 0xF2:
                self.tiles[(w1 >> 24) & 7].update(uls=(w0 >> 12) & 4095, ult=w0 & 4095,
                                                lrs=(w1 >> 12) & 4095, lrt=w1 & 4095)
            elif op in (0xF3, 0xF4):
                assert self.image
                tile = self.tiles[(w1 >> 24) & 7]
                self.images[tile['tmem']] = self.image
            elif op == 0xF0:
                count = ((w1 >> 14) & 1023) + 1
                base = (self.tiles[(w1 >> 24) & 7]['tmem'] - 256) * 4
                raw = self.read(self.image[0], count * 2)
                assert 0 <= base and base + count <= 256
                self.palette[base:base+count] = [rgba16(v[0]) for v in struct.iter_unpack('>H', raw)]
            elif op in (0x00, 0x03, 0xD8, 0xDB, 0xDC, 0xE2, 0xE3, 0xE6, 0xE7, 0xE8,
                        0xE9, 0xEE, 0xF7, 0xF8, 0xF9, 0xFB, 0xFC):
                pass  # culling bounds, RDP state, fog, lights and combiner
            else:
                raise ValueError(f'Unsupported display opcode {op:02x} at {address-8:08x}')
        raise ValueError('Unterminated display list')

    def room(self):
        for offset in range(0, 0x400, 8):
            cmd = self.read(0x03000000 + offset, 8)
            if cmd[0] == 0x14:
                break
            if cmd[0] != 0x0A:
                continue
            pointer = int.from_bytes(cmd[4:], 'big')
            header = self.read(pointer, 12)
            kind, count = header[:2]
            entries = int.from_bytes(header[4:8], 'big')
            assert kind in (0, 2), kind
            for i in range(count):
                base = entries + i * (8 if kind == 0 else 16)
                raw = self.read(base + (0 if kind == 0 else 8), 8)
                opaque, translucent = struct.unpack('>II', raw)
                if opaque:
                    self.walk(opaque)
                if translucent:
                    self.walk(translucent, True)
            return
        raise ValueError('Room has no mesh header')


def coordinate(value, scale, shift, origin, mode, mask, extent):
    value *= scale * (2 ** (-shift if shift <= 10 else 16 - shift))
    value = math.floor(value - origin / 4)
    if mode & 2:
        return max(0, min(extent - 1, value))
    period = (1 << mask) if mask else extent
    if mode & 1 and (value // period) & 1:
        value = period - 1 - value % period
    return value % period % extent


def bake(face, size=16):
    pixels = []
    tex = face['texture']
    vertices = face['vertices']
    for y in range(size):
        v = y / (size - 1)
        for x in range(size):
            u = x / (size - 1)
            weights = ((1-u)*(1-v), u*(1-v), v)
            if tex:
                uv = [sum(w * p[3+i] for w, p in zip(weights, vertices)) for i in range(2)]
                s = coordinate(uv[0], tex['scale'][0], tex['shifts'], tex['uls'], tex['cms'], tex['masks'], tex['width'])
                t = coordinate(uv[1], tex['scale'][1], tex['shiftt'], tex['ult'], tex['cmt'], tex['maskt'], tex['height'])
                color = tex['colors'][t * tex['width'] + s]
            else:
                color = (255, 255, 255, 255)
            if face['lighting']:
                normal = [sum(w * (p[5+i] if p[5+i] < 128 else p[5+i]-256) / 127
                              for w, p in zip(weights, vertices)) for i in range(3)]
                light = .65 + .35 * max(0, sum(a*b for a,b in zip(normal, (.3,.9,.3))))
                shade = [light] * 3
            else:
                shade = [sum(w * p[5+i] / 255 for w,p in zip(weights, vertices)) for i in range(3)]
            pixels.append(tuple(min(255, round(color[i] * shade[i])) for i in range(3)) + (color[3],))
    rgb = Image.new('RGB', (size, size))
    rgb.putdata([p[:3] for p in pixels])
    quantized = rgb.quantize(colors=15, method=Image.Quantize.MEDIANCUT)
    palette = quantized.getpalette()
    palette += [0] * (45 - len(palette))
    clut = [0] + [0x8000 | (palette[i*3] >> 3) | ((palette[i*3+1] >> 3) << 5) |
                  ((palette[i*3+2] >> 3) << 10) for i in range(15)]
    indices = [i+1 if p[3] >= 64 else 0 for i,p in zip(quantized.tobytes(), pixels)]
    raw = bytes((indices[i] << 4) | indices[i+1] for i in range(0, len(indices), 2))
    return struct.pack('>16H', *clut) + raw


def collision_triangles(scene):
    """Read the scene collision command and its native US 1.2 CollisionHeader."""
    def offset(pointer):
        assert pointer >> 24 == 2
        return pointer & 0xFFFFFF
    for pos in range(0, 0x400, 8):
        if scene[pos] == 0x14:
            break
        if scene[pos] != 3:
            continue
        header = offset(struct.unpack_from('>I', scene, pos+4)[0])
        nv = struct.unpack_from('>H', scene, header+12)[0]
        vp = offset(struct.unpack_from('>I', scene, header+16)[0])
        np = struct.unpack_from('>H', scene, header+20)[0]
        pp = offset(struct.unpack_from('>I', scene, header+24)[0])
        vertices = [struct.unpack_from('>3h', scene, vp+6*i) for i in range(nv)]
        triangles = []
        for i in range(np):
            poly = struct.unpack_from('>4H4h', scene, pp+16*i)
            abc = [vertices[v & 0x1FFF] for v in poly[1:4]]
            normal = [round(n/2) for n in poly[4:7]]
            bounds = [min(v[k] for v in abc) for k in range(3)] + [max(v[k] for v in abc) for k in range(3)]
            triangles.append(tuple(n for v in abc for n in v) + tuple(normal) + tuple(bounds))
        assert triangles
        return triangles
    raise ValueError('No collision header in US 1.2 scene')


def write_scene(faces, segments):
    positions = list(dict.fromkeys(v[:3] for f in faces for v in f['vertices']))
    lookup = {p:i for i,p in enumerate(positions)}
    center = tuple((min(p[i] for p in positions) + max(p[i] for p in positions)) // 2 for i in range(3))
    radius = math.ceil(max(math.dist(p, center) for p in positions))
    texture = bytearray()
    records = bytearray()
    tiles = {}
    def area(face):
        a,b,c = [v[:3] for v in face['vertices']]
        u,v = ([b[i]-a[i] for i in range(3)], [c[i]-a[i] for i in range(3)])
        return sum((u[(i+1)%3]*v[(i+2)%3]-u[(i+2)%3]*v[(i+1)%3])**2 for i in range(3))
    large = {id(f) for f in sorted(faces, key=area, reverse=True)[:300]}
    for face in faces:
        size = 32 if id(face) in large else 16
        tile = bake(face, size)
        if tile not in tiles:
            tiles[tile] = len(texture)
            texture.extend(tile)
        offset = tiles[tile]
        ids = [lookup[v[:3]] for v in face['vertices']]
        records.extend(struct.pack('>4HIIHH', *ids, ids[2], offset+32, offset, (size//8)<<8 | size,
                                   int(face['transparent']) | (int(face['cull']) << 1)))
    vertex_data = b''.join(struct.pack('>3h', *p) for p in positions)
    vertex_data += bytes((-len(vertex_data)) % 4)
    vo, fo = 64, 64 + len(vertex_data)
    collision = collision_triangles(segments['spot04_scene'])
    collision_data = b''.join(struct.pack('>18h', *t) for t in collision)
    co = fo + len(records)
    to = (co + len(collision_data) + 7) & ~7
    total = to + len(texture)
    commands = len(faces) + 3
    assert total < 1024*1024 - 2048
    assert commands*32 + len(texture) + 32 < 512*1024
    header = struct.pack('>9I3i4I', 0x4B465231, 2, len(positions), len(faces), vo, fo,
                         to, len(texture), total, *center, radius, commands, co, len(collision))
    output = ROOT / 'cd/FOREST.BIN'
    output.parent.mkdir(exist_ok=True)
    output.write_bytes(header + vertex_data + records + collision_data + bytes(to-co-len(collision_data)) + texture)
    manifest = dict(source='ntsc-1.2', segments={n:hashlib.sha256(d).hexdigest() for n,d in segments.items()},
                    vertices=len(positions), triangles=len(faces), unique_tiles=len(tiles),
                    texture_bytes=len(texture), command_bytes=commands*32, file_bytes=total,
                    center=center, radius=radius, collision_triangles=len(collision))
    (ROOT / 'assets/generated').mkdir(parents=True, exist_ok=True)
    (ROOT / 'assets/generated/kokiri_scene_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps(manifest, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--oot-root', type=Path, default=Path('D:/Workspace-Claude/game-decomps/n64/oot'))
    args = parser.parse_args()
    segments = extract(args.oot_root)
    faces = []
    for name, data in segments.items():
        if 'room' not in name:
            continue
        dl = DisplayLists(segments['spot04_scene'], data)
        dl.room()
        faces.extend(dl.faces)
        print(name, len(dl.faces), 'triangles;', len(dl.textures), 'texture states;',
              'opcodes', {hex(k):v for k,v in dl.opcodes.items()}, 'dynamic', dl.external_lists)
    print('total triangles', len(faces))
    write_scene(faces, segments)


if __name__ == '__main__':
    main()
