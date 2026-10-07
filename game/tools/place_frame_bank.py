#!/usr/bin/env python3
"""Place a frame bank into the allocations the old system frees (measurement).

The C system holds, during normal play: LINKANIM (jo heap, 423,472), the C
scene collision buffer (jo heap, 94,854), its index (jo heap, 16,384) and the
fixed dyna carve (cart, 18,432). The new system may reuse exactly those sizes
at the same lifecycle points. Same sizes do not prove fragmentation unchanged:
allocation order, lifetimes and temporary buffers must be measured in the real build.

Resident clips are split into PFB2 chunk files, each no larger than one
allocation (first-fit decreasing on clip block size, real header/pad cost).
Then the worst scene pack must fit contiguously in one allocation's free tail,
and a scene change with rollback (old pack kept until the new one validates)
must fit the two largest packs at once. Slot table and scratch are adapter
.bss in the core carve (already reserved there), not here.
"""
import argparse
import json
import struct
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent
ALLOCATIONS = [('linkanim_heap', 423472), ('collision_heap', 94854),
               ('collision_index_heap', 16384), ('dyna_carve', 18432)]


def blocks(path):
    data = path.read_bytes()
    count = struct.unpack_from('>I', data, 4)[0]
    offs = list(struct.unpack_from('>%dI' % count, data, 8)) + [len(data) - 4]
    ids = struct.unpack_from('>%dH' % count, data, 8 + 4 * count)
    return [(ids[i], offs[i + 1] - offs[i]) for i in range(count)]


def file_bytes(sizes):
    n = len(sizes)
    return 8 + 4 * n + ((2 * n + 3) & ~3) + sum(sizes) + 4


def place(resident, packs):
    """Try each allocation as the scene-pack home: fill the others first so
    that home keeps the largest contiguous tail. Best result wins."""
    best = None
    for home, _ in ALLOCATIONS:
        order = [a for a in ALLOCATIONS if a[0] != home] + [a for a in ALLOCATIONS if a[0] == home]
        result = place_order(resident, packs, order)
        if result and (best is None or (result['fits_worst_scene'], result['pack_home_tail'])
                       > (best['fits_worst_scene'], best['pack_home_tail'])):
            best = result
    return best


def place_order(resident, packs, order):
    chunks = {name: [] for name, _ in ALLOCATIONS}
    for clip_id, size in sorted(resident, key=lambda b: -b[1]):
        for name, cap in order:
            trial = [s for _, s in chunks[name]] + [size]
            if file_bytes(trial) <= cap:
                chunks[name].append((clip_id, size))
                break
        else:
            return None
    used = {n: file_bytes([s for _, s in c]) if c else 0 for n, c in chunks.items()}
    tails = sorted((cap - used[n], n) for n, cap in ALLOCATIONS)
    pack_sizes = sorted(packs.values(), reverse=True) + [0, 0]
    worst, second = pack_sizes[0], pack_sizes[1]
    # Worst pack: one contiguous tail. Rollback: two packs in two tails, or both in one.
    fits_scene = any(t >= worst for t, _ in tails)
    fits_transition = (any(t >= worst + second for t, _ in tails) or
                       (len(tails) >= 2 and tails[-1][0] >= worst and tails[-2][0] >= second))
    home = order[-1][0]
    return dict(pack_home=home, pack_home_tail=dict(ALLOCATIONS)[home] - used[home],
                chunks={n: dict(clips=len(c), file_bytes=used[n],
                                capacity=dict(ALLOCATIONS)[n],
                                free_tail=dict(ALLOCATIONS)[n] - used[n]) for n, c in chunks.items()},
                worst_pack=worst, second_pack=second,
                fits_worst_scene=fits_scene, fits_transition_with_rollback=fits_transition,
                heap_bytes_used=sum(used[n] for n in ('linkanim_heap', 'collision_heap',
                                                      'collision_index_heap')),
                fixed_bytes_used=used['dyna_carve'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bank', type=Path)
    args = parser.parse_args()
    resident = blocks(args.bank / 'RESIDENT.PFB')
    packs = {p.stem[2:]: p.stat().st_size for p in args.bank.glob('S_*.PFB')}
    report = place(resident, packs)
    if report is None:
        report = dict(fits=False, reason='resident clips do not fit the old allocations')
    else:
        report['fits'] = report['fits_worst_scene'] and report['fits_transition_with_rollback']
    (args.bank / 'placement.json').write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=1))


if __name__ == '__main__':
    main()
