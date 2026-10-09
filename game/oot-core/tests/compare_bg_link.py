#!/usr/bin/env python3
"""Classify bg_link_scenario rows: C Link wrappers over the C library vs
bg_core_link.c over the real core. usage: compare_bg_link.py c.txt core.txt
Exit 1 only for a broken contract: the core run's no-scene guard row, a
missing spawn, or a different row sequence. Value differences are printed:
the core answers with source z_bgcheck, so a few edge/plane cases differ.
"""
import sys


def rows(path):
    return [line.split() for line in open(path, encoding='utf-8') if line.strip()]


def main():
    c, k = rows(sys.argv[1]), rows(sys.argv[2])
    guard = [r for r in k if r[0] == 'G']
    k = [r for r in k if r[0] != 'G']
    if guard != [['G', '0', '0', '1']]:
        print('NO-SCENE GUARD FAILED', guard)
        return 1
    if [r[0] for r in c] != [r[0] for r in k]:
        print('ROW SEQUENCE DIFFERS', len(c), len(k))
        return 1
    if c[0][1] != '1' or k[0][1] != '1':
        print('SPAWN FAILED', c[0], k[0])
        return 1
    stats = {}
    worst = []
    for a, b in zip(c, k):
        t = a[0]
        n = stats.setdefault(t, [0, 0, 0])   # rows, exact, hit/miss differs
        n[0] += 1
        if a == b:
            n[1] += 1
            continue
        if t == 'F':
            if a[4] != b[4]:
                n[2] += 1
            else:
                worst.append((abs(int(a[5]) - int(b[5])), ' '.join(a), ' '.join(b)))
        elif t == 'C' or t == 'J':
            n[2] += 1
        elif t == 'W':
            d = max(abs(int(a[i]) - int(b[i])) for i in (3, 4, 5))
            if d > 4:
                worst.append((d, ' '.join(a), ' '.join(b)))
            if a[6] != b[6]:
                n[2] += 1
        else:
            worst.append((0, ' '.join(a), ' '.join(b)))
    print('spawn C', c[0][2:], 'core', k[0][2:])
    for t, (total, exact, flip) in sorted(stats.items()):
        print(f'{t}: {total} rows, {exact} exact, {flip} hit/miss or ground differs')
    worst.sort(reverse=True)
    for d, a, b in worst[:12]:
        print(f'  d={d}: C [{a}] core [{b}]')
    return 0


if __name__ == '__main__':
    sys.exit(main())
