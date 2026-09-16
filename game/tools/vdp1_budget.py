#!/usr/bin/env python
"""Enforced VDP1 and SGL capacity budget for the Kokiri scene.

Every mesh shares one VDP1 texture area, one SGL sprite table and one per-frame
polygon list. Counting texture pixels alone has already bitten this project
twice -- once when Link's tile count overran JO_MAX_SPRITE and aborted into Jo's
error handler at load, once when a per-face bake plan overran VRAM by 13 KB. So
this counts everything that competes:

  * pixel data, per tile, at its real 4bpp size
  * the 32-byte CLUT every tile carries, whether or not it is unique
  * 8-byte alignment, because SGL addresses sprite character data in 8-byte
    units and a tile that is not aligned wastes the remainder
  * a reservation for the VDP1 command table below our texture base
  * Link's resident tiles, which are loaded alongside the scene

Raising a limit is a deliberate act: change the constant here, and the check in
build_sgl_scene.py and the runtime guard in kokiri_sgl.c will agree or the build
fails.
"""

# Jo's nominal JO_VDP1_USER_AREA_SIZE disagrees with its physical start/end.
# Derive capacity from addresses. SGL's Work RAM SpriteBuf does not eliminate
# hardware commands in VDP1 VRAM (slInitSprite writes to 0x25C00000).
VDP1_END = 0x7FEF8  # Jo's reserved end, below the physical 512 KiB VRAM end.

# Reserve from VRAM offset zero, NOT from the already-offset texture area.
# 2600 commands plus 256 extra slots for system/clipping/sprite commands.
COMMAND_RESERVE = 2600 * 32 + 8 * 1024
TEXTURE_BASE = (COMMAND_RESERVE + 255) & ~255
VDP1_USER_AREA = VDP1_END - TEXTURE_BASE

# makefile: JO_MAX_SPRITE. Slot 0 is Jo's.
MAX_SPRITE_SLOTS = 2400

# tools/build_sgl_area.py --max-polygons.
MAX_POLYGONS = 2600
MAX_VERTICES = 2500

CLUT_BYTES = 32
ALIGN = 8


def tile_bytes(width, height):
    """Bytes one 4bpp tile costs, CLUT and alignment included."""
    pixels = width * height // 2
    total = pixels + CLUT_BYTES
    return (total + ALIGN - 1) // ALIGN * ALIGN


class Budget(object):
    """Accumulates one build's cost and refuses to exceed the hardware."""

    def __init__(self):
        self.parts = []

    def add(self, label, tiles, polygons, vertices):
        """tiles: iterable of (width, height)."""
        tiles = list(tiles)
        byte_total = sum(tile_bytes(w, h) for w, h in tiles)
        self.parts.append(dict(label=label, bytes=byte_total,
                               tiles=len(tiles),
                               polygons=polygons, vertices=vertices))

    @property
    def texture_bytes(self):
        return sum(p['bytes'] for p in self.parts)

    @property
    def tiles(self):
        return sum(p['tiles'] for p in self.parts)

    @property
    def polygons(self):
        return sum(p['polygons'] for p in self.parts)

    @property
    def vertices(self):
        return sum(p['vertices'] for p in self.parts)

    @property
    def vram_limit(self):
        return VDP1_USER_AREA

    def failures(self):
        out = []
        if self.texture_bytes > self.vram_limit:
            out.append('VDP1 textures %d bytes exceed %d available '
                       '(commands reserved below texture base %#x) by %d'
                       % (self.texture_bytes, self.vram_limit, TEXTURE_BASE,
                          self.texture_bytes - self.vram_limit))
        if self.tiles + 1 > MAX_SPRITE_SLOTS:
            out.append('%d tiles need %d sprite slots, JO_MAX_SPRITE is %d'
                       % (self.tiles, self.tiles + 1, MAX_SPRITE_SLOTS))
        if self.polygons > MAX_POLYGONS:
            out.append('%d polygons exceed MaxPolygons %d'
                       % (self.polygons, MAX_POLYGONS))
        if self.vertices > MAX_VERTICES:
            out.append('%d vertices exceed MaxVertices %d'
                       % (self.vertices, MAX_VERTICES))
        return out

    def report(self):
        lines = ['budget:']
        for p in self.parts:
            lines.append('  %-10s %6d tiles %7d B  %5d polys %5d verts'
                         % (p['label'], p['tiles'], p['bytes'],
                            p['polygons'], p['vertices']))
        lines.append('  %-10s %6d tiles %7d B  %5d polys %5d verts'
                     % ('TOTAL', self.tiles, self.texture_bytes,
                        self.polygons, self.vertices))
        lines.append('  VRAM   %7d of %7d B (%.1f%%), %d B spare'
                     % (self.texture_bytes, self.vram_limit,
                        100.0 * self.texture_bytes / self.vram_limit,
                        self.vram_limit - self.texture_bytes))
        lines.append('  polys  %7d of %7d   sprites %d of %d'
                     % (self.polygons, MAX_POLYGONS,
                        self.tiles + 1, MAX_SPRITE_SLOTS))
        return '\n'.join(lines)
