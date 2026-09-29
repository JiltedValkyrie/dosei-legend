"""Check the post-room upload peak, including every loaded forest prop."""
from pathlib import Path
import re
import struct

import vdp1_budget as budget

ROOT = Path(__file__).resolve().parents[1]


def mesh_cost(path):
    data = path.read_bytes()
    magic, _, _, faces, _, records, _, _ = struct.unpack_from('>8I', data)
    if magic != 0x4b465231:
        raise ValueError('Not KFR1: %s' % path)
    # Same identity as upload_actor: offsets AND dimensions, per mesh.
    tiles = {struct.unpack_from('>IIH', data, records + i * 20 + 8)
             for i in range(faces)}
    return (sum(budget.tile_bytes((size >> 8) * 8, size & 255)
                for _, _, size in tiles), len(tiles))


def actor_peak(cd, placements):
    rows = placements.split('const kokiri_npc_t kokiri_npcs')[1].split('};')[0]
    children = []
    for row in re.findall(r'\{([^{}]+)\}', rows):
        values = [v.strip() for v in row.split(',')]
        x, _, z, _, param = (int(v, 0) for v in values[:5])
        kind, _, scene = values[5:]
        if int(scene) != 0 or kind != 'KOKIRI_NPC_CHILD':
            continue
        model = 2 + (param & 255)
        radius = 240 if (param & 255) == 5 else 180
        children.append((x, z, radius, model))
    # Mido can move; Saria is forced visible in her greeting. Count both at
    # every location, regardless of room/presence flags, for a safe upper bound.
    props = ['ROCK', 'POT', 'CHEST', 'BUSH', 'GOSSIP']
    props += ['SIGN%d' % i for i in range(11)]
    fixed = [mesh_cost(cd / (name + '.BIN')) for name in props + ['NPC00', 'NPC01']]
    costs = {m: mesh_cost(cd / ('NPC%02d.BIN' % m)) for _, _, _, m in children}
    # A visibility circle lies inside its box. Every maximal overlapping box
    # set includes a pair of box boundaries; no sampling gaps between points.
    xs = {x + side * r for x, _, r, _ in children for side in (-1, 1)}
    zs = {z + side * r for _, z, r, _ in children for side in (-1, 1)}
    peaks = [sum(c[k] for c in fixed) for k in (0, 1)]
    for x in xs:
        for z in zs:
            visible = {m for nx, nz, r, m in children
                       if abs(nx - x) <= r and abs(nz - z) <= r}
            for k in (0, 1):
                peaks[k] = max(peaks[k], sum(c[k] for c in fixed) +
                               sum(costs[m][k] for m in visible))
    return tuple(peaks)


def check(root=ROOT):
    cd = root / 'build/cd'
    peak = actor_peak(cd, (root / 'build/generated/kokiri_actors.c').read_text())
    if peak[0] > budget.FOREST_ACTOR_BYTES or peak[1] > budget.FOREST_ACTOR_SLOTS:
        raise ValueError('Forest actors exceed reservation: %s' % (peak,))
    header = (root / 'build/generated/link_scene.h').read_text()
    value = lambda name: int(re.search(r'#\s*define\s+' + name + r'\s+(\d+)', header)[1])
    link_slots = value('LINK_TILE_COUNT')
    resident = value('LINK_PIXEL_BYTES') + link_slots * 32 + budget.RUNTIME_SPRITE_BYTES
    for path in sorted(cd.glob('S1R*.MSH')):
        _, _, _, tiles, pixels, _, _, _ = struct.unpack_from('>8I', path.read_bytes())
        used = resident + pixels + tiles * 32 + budget.FOREST_ACTOR_BYTES
        slots = 1 + link_slots + budget.RUNTIME_SPRITE_SLOTS + tiles + budget.FOREST_ACTOR_SLOTS
        if used + budget.FOREST_VRAM_MARGIN > budget.VDP1_USER_AREA or slots > budget.MAX_SPRITE_SLOTS:
            raise ValueError('%s: actors included, VRAM %d + %d margin / %d; slots %d / %d' %
                             (path.name, used, budget.FOREST_VRAM_MARGIN,
                              budget.VDP1_USER_AREA, slots, budget.MAX_SPRITE_SLOTS))
        print('%s: actors included, %d B spare; %d sprite slots' %
              (path.name, budget.VDP1_USER_AREA - used, slots))
    print('Forest actor upper bound: %d B, %d slots' % peak)


if __name__ == '__main__':
    check()
