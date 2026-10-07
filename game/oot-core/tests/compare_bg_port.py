#!/usr/bin/env python3
"""Compare bg_port_probe rows: identical query inputs through the C library,
the Fx core (Saturn) and the same core source on host floats.

usage: compare_bg_port.py fx.txt hw.txt
Pairs: C vs hw (C library vs real source semantics), fx vs hw (Fx error only),
C vs fx (what porting changes). Categories per query kind: hit/miss, position,
owner+poly, surface. Exit 1 if inputs differ between the two runs.
"""
import sys
from collections import Counter, defaultdict

TOL = {'F': 1, 'W': 1, 'C': 1, 'L': 2}
# Line (2727,-156,-1406)->(3027,-156,-1256): float hits at x 3017, Fx misses.
KNOWN_FX = [('L', 2981)]


def load(path):
    rows = {}
    for line in open(path, encoding='utf-8'):
        parts = line.split('|')
        if len(parts) != 3 or not parts[0][:1] in 'FWCL':
            continue
        head = parts[0].split()
        key = (head[0], int(head[1]))
        def side(s):
            v = s.split()
            return dict(hit=int(v[0]), pos=tuple(int(x) for x in v[1:4]), bg=int(v[4]),
                        poly=int(v[5]), d0=v[6], d1=v[7])
        rows[key] = dict(inputs=tuple(head[2:]), c=side(parts[1]), k=side(parts[2]))
    return rows


def diff(kind, a, b):
    if a['hit'] != b['hit']:
        return 'hit/miss'
    if not a['hit']:
        return None
    if max(abs(x - y) for x, y in zip(a['pos'], b['pos'])) > TOL[kind]:
        return 'position'
    if a['bg'] != b['bg'] or a['poly'] != b['poly']:
        return 'owner/poly' if (a['d0'], a['d1']) != (b['d0'], b['d1']) else 'poly (same surface)'
    if (a['d0'], a['d1']) != (b['d0'], b['d1']):
        return 'surface'
    return None


def main():
    fx, hw = load(sys.argv[1]), load(sys.argv[2])
    if set(fx) != set(hw) or any(fx[k]['inputs'] != hw[k]['inputs'] for k in fx):
        print('INPUTS DIFFER between fx and hw runs')
        return 1
    totals = Counter(k for k, _ in fx)
    pairs = {'C vs hw': lambda k: (hw[k]['c'], hw[k]['k']),
             'fx vs hw': lambda k: (fx[k]['k'], hw[k]['k']),
             'C vs fx': lambda k: (fx[k]['c'], fx[k]['k'])}
    examples = defaultdict(list)
    for name, get in pairs.items():
        cats = defaultdict(Counter)
        for key in sorted(fx):
            a, b = get(key)
            d = diff(key[0], a, b)
            if d:
                cats[key[0]][d] += 1
                if len(examples[name]) < 5:
                    examples[name].append((key, fx[key]['inputs'], d, a, b))
        print(f'== {name}')
        for kind in 'FWCL':
            n = sum(cats[kind].values())
            print(f'  {kind} {n:4}/{totals[kind]:4}  ' + ', '.join(f'{c} {v}' for c, v in cats[kind].most_common()))
    # Tracked Fx regression cases (Astra 2026-10-06): small counts do not
    # prove harmless. Report each one's current state every run.
    for key in KNOWN_FX:
        if key in fx:
            d = diff(key[0], fx[key]['k'], hw[key]['k'])
            print(f"  known Fx case {key} in {fx[key]['inputs']}: {'STILL DIFFERS: ' + d if d else 'now matches float'}")
    for name in ('fx vs hw',):
        for key, inputs, d, a, b in examples[name]:
            print(f'  {name} {key} in {inputs}: {d}: fx {a} | hw {b}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
