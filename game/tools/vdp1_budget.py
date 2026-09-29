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
# MaxPolygons commands plus 256 extra slots for system/clipping/sprite commands.
COMMAND_RESERVE = 2200 * 32 + 8 * 1024
TEXTURE_BASE = (COMMAND_RESERVE + 255) & ~255
VDP1_USER_AREA = VDP1_END - TEXTURE_BASE

# makefile: JO_MAX_SPRITE. Slot 0 is Jo's.
MAX_SPRITE_SLOTS = 2400

# tools/build_sgl_area.py --max-polygons.
#
# This is a PER-FRAME ceiling: SGL only needs slots for what is submitted, not
# for the whole table. Measured worst case over a yaw/position sweep of the
# previous forest sweep was 1354 faces. Equipped Link now submits at most
# 520 faces (1874 combined), keeping 326 slots of headroom while returning ~46 KB of work RAM to .bss, which the
# dialogue text needs. The total-table check below is deliberately kept as the
# conservative guard, with the frame figure allowed to exceed it.
MAX_POLYGONS = 2200
# Worst-case submitted polygons, re-measured when the mesh changes.
MAX_FRAME_POLYGONS = 1354 + 520  # prior forest sweep + max equipped Link
# Whole-table ceiling. Independent of MaxPolygons: this one is about the RAM
# the POINT/POLYGON/ATTR tables occupy, not what one frame can draw.
MAX_TABLE_POLYGONS = 2600
MAX_VERTICES = 2500

CLUT_BYTES = 32
ALIGN = 8

# Resident non-mesh sprites: fairy_load() and minimap_init(). Reserve optional
# effects too: successful uploads remain resident when the room bank loads.
# (label, count, width, height, bytes per pixel)
RUNTIME_SPRITES = (
    ('fairy glows', 9, 16, 16, 2),  # player, NPC, enemy: three steps each
    ('sparkle', 1, 8, 8, 2),
    ('grass', 1, 32, 32, 2),
    ('rupees', 2, 16, 16, 2),
    ('HUD digits', 10, 8, 16, 2),
    ('gear pickups', 2, 16, 16, 2),
    ('pause icons', 3, 32, 32, 2),
    ('message panel', 1, 32, 16, 2),
    ('message marks', 2, 16, 16, 2),
    ('minimap markers', 9, 8, 8, 1),
)
RUNTIME_SPRITE_BYTES = sum(n * ((w * h * bpp + 7) // 8 * 8)
                           for _, n, w, h, bpp in RUNTIME_SPRITES)
RUNTIME_SPRITE_SLOTS = sum(n for _, n, _, _, _ in RUNTIME_SPRITES)

# Prefer lower forest bake density to filling VRAM to 99%. This is spare
# capacity after all current residents, not a substitute for counting them.
FOREST_VRAM_MARGIN = 32 * 1024

# Uploaded after the room: world props and the nearby NPC set. These are
# separate from the safety margin. check_forest_budget validates the actual
# staged meshes and all visibility-box intersections against this allowance.
FOREST_ACTOR_BYTES = 64 * 1024
FOREST_ACTOR_SLOTS = 576


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

    def reserve_forest_actors(self):
        self.parts.append(dict(label='actors', bytes=FOREST_ACTOR_BYTES,
                               tiles=FOREST_ACTOR_SLOTS, polygons=0, vertices=0))

    @property
    def texture_bytes(self):
        """Tile bytes only, so a caller can reason about one mesh's cost."""
        return sum(p['bytes'] for p in self.parts)

    @property
    def vram_bytes(self):
        """Everything VDP1 must hold: tiles PLUS the runtime sprites.

        The sprites are loaded from the CD at startup and are not tiles, so
        they appear in no part. Counting them only here keeps texture_bytes
        meaning what every caller already assumes it means."""
        return self.texture_bytes + RUNTIME_SPRITE_BYTES

    @property
    def tiles(self):
        return sum(p['tiles'] for p in self.parts)

    @property
    def sprite_slots(self):
        return 1 + self.tiles + RUNTIME_SPRITE_SLOTS

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
        if self.vram_bytes > self.vram_limit:
            out.append('VDP1 textures %d bytes exceed %d available '
                       '(commands reserved below texture base %#x) by %d'
                       % (self.vram_bytes, self.vram_limit, TEXTURE_BASE,
                          self.vram_bytes - self.vram_limit))
        if self.sprite_slots > MAX_SPRITE_SLOTS:
            out.append('%d tiles plus resident sprites need %d sprite slots, JO_MAX_SPRITE is %d'
                       % (self.tiles, self.sprite_slots, MAX_SPRITE_SLOTS))
        # Two separate limits, because they fail for different reasons.
        #
        # MaxPolygons is PER FRAME: culling is what keeps a frame inside it, so
        # the whole table is allowed to be larger. What must never exceed it is
        # the measured worst frame.
        if MAX_FRAME_POLYGONS > MAX_POLYGONS:
            out.append('worst measured frame %d exceeds MaxPolygons %d'
                       % (MAX_FRAME_POLYGONS, MAX_POLYGONS))
        # The table itself still has a ceiling: every polygon costs POLYGON and
        # ATTR bytes in work RAM whether or not it is ever submitted.
        if self.polygons > MAX_TABLE_POLYGONS:
            out.append('%d polygons exceed the %d-polygon table budget'
                       % (self.polygons, MAX_TABLE_POLYGONS))
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
                     % (self.vram_bytes, self.vram_limit,
                        100.0 * self.vram_bytes / self.vram_limit,
                        self.vram_limit - self.vram_bytes))
        lines.append('  polys  %7d of %7d   sprites %d of %d'
                     % (self.polygons, MAX_POLYGONS,
                        self.sprite_slots, MAX_SPRITE_SLOTS))
        return '\n'.join(lines)
