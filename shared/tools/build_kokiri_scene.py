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


def extract(root, rom_dir=None, prefix='spot04', expect=None):
    """Every segment of one scene: `<prefix>_scene` plus its `<prefix>_room_N`.

    `prefix` used to be hardcoded to spot04. It is a parameter now because the
    slice needs Link's house, the Lost Woods, the Deku Tree and the shop as
    well, and each of those is an ordinary OoT scene read exactly the same way.
    `expect` is the segment count the caller believes the scene has; passing it
    turns a mis-typed prefix or a missing room into an immediate failure rather
    than a scene that silently loads short.
    """
    config = root / 'baseroms/ntsc-1.2'
    roms = [p for p in (Path(rom_dir) if rom_dir else config).glob('*.z64') if hashlib.md5(p.read_bytes()).hexdigest()
            == '57a9719ad547c516342e1a15d5c28c3d']
    assert len(roms) == 1, 'Verified US 1.2 ROM required'
    rom = roms[0].read_bytes()
    dma = int(re.search(r'dmadata_start: (\w+)', (config / 'config.yml').read_text())[1], 16)
    segments = {}
    with (config / 'segments.csv').open() as f:
        for index, row in enumerate(csv.DictReader(f)):
            name = row['Name']
            if name != prefix + '_scene' and not re.fullmatch(
                    re.escape(prefix) + r'_room_\d+', name):
                continue
            start, end, physical, packed_end = struct.unpack_from('>4I', rom, dma + index * 16)
            data = yaz0(rom[physical:packed_end]) if packed_end else rom[physical:physical + end - start]
            assert len(data) == end - start
            segments[name] = bytes(data)
    assert segments, 'no segments matched prefix %r' % prefix
    if expect is not None:
        assert len(segments) == expect, (
            'scene %s: expected %d segments, found %d'
            % (prefix, expect, len(segments)))
    return segments


def extract_object(root, rom_dir, name):
    """One object segment (gameplay_dangeon_keep, object_...) by exact name."""
    config = root / 'baseroms/ntsc-1.2'
    roms = [p for p in (Path(rom_dir) if rom_dir else config).glob('*.z64') if hashlib.md5(p.read_bytes()).hexdigest()
            == '57a9719ad547c516342e1a15d5c28c3d']
    assert len(roms) == 1, 'Verified US 1.2 ROM required'
    rom = roms[0].read_bytes()
    dma = int(re.search(r'dmadata_start: (\w+)', (config / 'config.yml').read_text())[1], 16)
    with (config / 'segments.csv').open() as f:
        for index, row in enumerate(csv.DictReader(f)):
            if row['Name'] != name:
                continue
            start, end, physical, packed_end = struct.unpack_from('>4I', rom, dma + index * 16)
            data = yaz0(rom[physical:packed_end]) if packed_end else rom[physical:physical + end - start]
            assert len(data) == end - start
            return bytes(data)
    raise ValueError('object %s not in segments.csv' % name)


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
        # Some actor lists use a large clamp rectangle over a smaller masked
        # texture (owl feathers). An explicit source XML binding describes
        # the resident image; the clamp rectangle is not its byte length.
        dimensions = getattr(self, 'texture_dimensions', {}).get(address)
        if dimensions is not None:
            width, height = dimensions
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

    def load_vertex(self, index, vertex):
        self.cache[index] = vertex

    def matrix(self, word, address):
        # Static rooms have none. Other importers must interpret, never ignore.
        raise ValueError(f'Matrix-aware importer required: {word:08x} {address:08x}')

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
        branch_address = None
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
            elif op == 0xE1 and getattr(self, 'include_depth_branches', False):
                branch_address = w1
            elif op == 0x04 and getattr(self, 'include_depth_branches', False):
                # Offline near geometry: Saturn performs its own per-frame cull.
                # F3DEX2 G_BRANCH_Z jumps, rather than pushing a return address.
                if branch_address is None: raise ValueError('BranchZ without RDPHALF_1')
                self.walk(branch_address, transparent, depth + 1)
                return
            elif op == 0x01:
                n = (w0 >> 12) & 255
                first = ((w0 >> 1) & 127) - n
                assert 0 <= first and first + n <= 32
                for i in range(n):
                    x, y, z, flag, u, v, r, g, b, a = struct.unpack('>hhhHhhBBBB', self.read(w1 + i * 16, 16))
                    # Skin importers retain source blend ownership through G_VTX.
                    self.vertex_address = w1 + i * 16
                    self.load_vertex(first + i, (x, y, z, u / 32, v / 32, r, g, b, a))
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
            elif op == 0xDA:
                self.matrix(w0, w1)
            elif op in (0x00, 0x03, 0xD8, 0xDB, 0xDC, 0xE2, 0xE3, 0xE6, 0xE7,
                        0xE8, 0xE9, 0xEE, 0xF7, 0xF8, 0xF9, 0xFB, 0xFC):
                # Culling bounds, RDP state, fog, lights and combiner.
                pass
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
                first_face = len(self.faces)
                raw = self.read(base + (0 if kind == 0 else 8), 8)
                opaque, translucent = struct.unpack('>II', raw)
                if opaque:
                    self.walk(opaque)
                if translucent:
                    self.walk(translucent, True)
                for face in self.faces[first_face:]:
                    face['object'] = i
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


def scene_header(scene):
    """Every scene header command, keyed by opcode, in file order."""
    out = {}
    for pos in range(0, 0x400, 8):
        if scene[pos] == 0x14:
            break
        out.setdefault(scene[pos], []).append(scene[pos:pos + 8])
    return out


def _segment_offset(command):
    return int.from_bytes(command[4:8], 'big') & 0xFFFFFF


def spawn_points(scene):
    """Link's start poses: header command 0x00, 16-byte ActorEntry each.

    These are where the original puts the player for each entrance, so a new
    game beginning in Link's bed is a spawn index, not an authored coordinate.
    """
    header = scene_header(scene)
    if 0x00 not in header:
        return []
    command = header[0x00][0]
    base = _segment_offset(command)
    out = []
    for i in range(command[1]):
        _, x, y, z, _, yaw, _, params = struct.unpack_from('>H6hH', scene,
                                                           base + 16 * i)
        out.append(dict(x=x, y=y, z=z, yaw=yaw & 0xFFFF, params=params))
    return out


def entrance_spawns(scene, count):
    """Header command 0x06: (spawn, room) per entrance offset into this scene.

    There is no count in the header, so the caller says how many entries it
    expects to read. Reading past the real list returns neighbouring data, so
    a wrong count is the caller's error to avoid, not something detectable here.
    """
    header = scene_header(scene)
    if 0x06 not in header:
        return []
    base = _segment_offset(header[0x06][0])
    return [(scene[base + 2 * i], scene[base + 2 * i + 1]) for i in range(count)]


def exit_list(scene, count):
    """Header command 0x13: entrance id per exit slot.

    SurfaceType.exitIndex is ONE-BASED into this list, so a polygon carrying
    exitIndex 2 leaves through exit_list()[1]. Verified against the original:
    spot04's exitIndex 4 resolves to 0x272 (ENTR_LINKS_HOUSE_1) and
    link_home's exitIndex 2 resolves to 0x211 (ENTR_KOKIRI_FOREST_3), which is
    the two-way door between them.

    Like the entrance list this has no stored count.
    """
    header = scene_header(scene)
    if 0x13 not in header:
        return []
    base = _segment_offset(header[0x13][0])
    return [struct.unpack_from('>H', scene, base + 2 * i)[0]
            for i in range(count)]


def collision_surfaces(scene):
    """Per-polygon surface fields alongside the geometry.

    collision_triangles() returns geometry only and stays that way, so
    FOREST.COL is unchanged and its consumers are untouched. This is the
    richer read, needed because the dungeon and the scene transitions live in
    fields that were being discarded.

    Bit layout is SURFACETYPE0/1 from the decomp's include/bgcheck.h:219 --
    data[0]: bgCamIndex 0..7, exitIndex 8..12, floorType 13..17,
             wallType 21..25, floorProperty 26..29
    data[1]: material 0..3, floorEffect 4..5, lightSetting 6..10, echo 11..16
    Only the fields the slice uses are decoded; the rest stay in the source.
    """
    for pos in range(0, 0x400, 8):
        if scene[pos] == 0x14:
            break
        if scene[pos] != 3:
            continue
        header = _segment_offset(scene[pos:pos + 8])
        nv = struct.unpack_from('>H', scene, header + 12)[0]
        vp = struct.unpack_from('>I', scene, header + 16)[0] & 0xFFFFFF
        count = struct.unpack_from('>H', scene, header + 20)[0]
        pp = struct.unpack_from('>I', scene, header + 24)[0] & 0xFFFFFF
        types = struct.unpack_from('>I', scene, header + 28)[0] & 0xFFFFFF
        vertices = [struct.unpack_from('>3h', scene, vp + 6 * i)
                    for i in range(nv)]
        out = []
        for i in range(count):
            poly = struct.unpack_from('>4H4h', scene, pp + 16 * i)
            data0, data1 = struct.unpack_from('>2I', scene, types + 8 * poly[0])
            out.append(dict(
                vertices=[vertices[v & 0x1FFF] for v in poly[1:4]],
                normal=[round(n / 2) for n in poly[4:7]],
                exit=(data0 >> 8) & 0x1F,
                floor_type=(data0 >> 13) & 0x1F,
                wall_type=(data0 >> 21) & 0x1F,
                material=data1 & 0x0F))
        assert out
        return out
    raise ValueError('No collision header in US 1.2 scene')


def collision_data(scene):
    """The whole CollisionHeader, with nothing the runtime might need dropped.

    decomp include/bgcheck.h CollisionHeader: minBounds +0, maxBounds +6,
    numVertices +12, vtxList +16, numPolygons +20, polyList +24,
    surfaceTypeList +28, bgCamList +32, numWaterBoxes +36, waterBoxes +40.
    CollisionPoly (16 bytes): u16 type, u16 flags_vIA (bits 13-15 ignore
    camera/entity/projectiles), u16 flags_vIB (bit 13 floor conveyor), u16 vIC,
    Vec3s normal (Q15), s16 dist. SurfaceType is two raw u32 words, kept whole.
    WaterBox (16 bytes): s16 xMin, ySurface, zMin, xLength, zLength, pad,
    u32 properties. BgCamInfo: u16 setting, s16 count, Vec3s* data.

    Neither surface types nor bgCams store a count: the highest index any
    polygon (or water box, for bgCams) refers to bounds what is safe to read.
    """
    for pos in range(0, 0x400, 8):
        if scene[pos] == 0x14:
            break
        if scene[pos] != 3:
            continue
        return collision_header_data(scene, _segment_offset(scene[pos:pos + 8]))
    raise ValueError('No collision header in US 1.2 scene')


def collision_header_data(scene, header):
    """collision_data() for a CollisionHeader at a known offset in `scene`.

    Objects carry their own headers (a push block's gPushBlockCol in
    gameplay_dangeon_keep, say); every pointer is taken as an offset into the
    same segment, as it is for a scene.
    """
    nv = struct.unpack_from('>H', scene, header + 12)[0]
    vp = struct.unpack_from('>I', scene, header + 16)[0] & 0xFFFFFF
    count = struct.unpack_from('>H', scene, header + 20)[0]
    pp = struct.unpack_from('>I', scene, header + 24)[0] & 0xFFFFFF
    types = struct.unpack_from('>I', scene, header + 28)[0] & 0xFFFFFF
    cams = struct.unpack_from('>I', scene, header + 32)[0]
    nwater = struct.unpack_from('>H', scene, header + 36)[0]
    wp = struct.unpack_from('>I', scene, header + 40)[0] & 0xFFFFFF
    vertices = [struct.unpack_from('>3h', scene, vp + 6 * i)
                for i in range(nv)]
    polys = []
    for i in range(count):
        kind, via, vib, vic, nx, ny, nz, _dist = struct.unpack_from(
            '>4H4h', scene, pp + 16 * i)
        polys.append(dict(
            vertices=[vertices[v & 0x1FFF] for v in (via, vib, vic)],
            normal=[round(n / 2) for n in (nx, ny, nz)],
            surface=kind, ignore=via >> 13, conveyor=(vib >> 13) & 1))
    surface_count = max(p['surface'] for p in polys) + 1
    surfaces = [struct.unpack_from('>2I', scene, types + 8 * i)
                for i in range(surface_count)]
    water = [struct.unpack_from('>5h2xI', scene, wp + 16 * i)
             for i in range(nwater)] if nwater else []
    bgcams = []
    if cams:
        highest = max([s[0] & 0xFF for s in surfaces] +
                      [w[5] & 0xFF for w in water])
        base = cams & 0xFFFFFF
        for i in range(highest + 1):
            setting, n, data = struct.unpack_from('>HhI', scene, base + 8 * i)
            vectors = []
            if data and n > 0:
                at = data & 0xFFFFFF
                vectors = [struct.unpack_from('>3h', scene, at + 6 * k)
                           for k in range(n)]
            bgcams.append(dict(setting=setting, vectors=vectors))
    assert polys
    return dict(polys=polys, surfaces=surfaces, water=water, bgcams=bgcams)


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
    output = ROOT.parent / 'game/levels/kokiri/assets/static/FOREST.BIN'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(header + vertex_data + records + collision_data + bytes(to-co-len(collision_data)) + texture)
    manifest = dict(source='ntsc-1.2', segments={n:hashlib.sha256(d).hexdigest() for n,d in segments.items()},
                    vertices=len(positions), triangles=len(faces), unique_tiles=len(tiles),
                    texture_bytes=len(texture), command_bytes=commands*32, file_bytes=total,
                    center=center, radius=radius, collision_triangles=len(collision))
    (output.parent / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
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
