#!/usr/bin/env python3
"""Diff bg_shim_scenario rows: C library reference vs bg_core_shim over the
real core. usage: compare_bg_shim.py c.txt shim.txt [tolerance]
Proxy ids are compared after mapping through each run's 'I ids' row.
Exit status 0 only means both runs produced the same row sequence; the
printed per-row differences are the result.
"""
import sys


def rows(path):
    out = []
    for line in open(path, encoding='utf-8'):
        if '|' in line:
            head, tail = line.split('|')
            out.append((head.split(), tail.split()))
    return out


def main():
    c, s = rows(sys.argv[1]), rows(sys.argv[2])
    tol = int(sys.argv[3]) if len(sys.argv) > 3 else 2
    def same_head(x, y):
        if len(x) != len(y) or x[:2] != y[:2]:
            return False
        if x[0] == 'I':
            return True
        return all(a == b or (a.lstrip('-').isdigit() and b.lstrip('-').isdigit() and abs(int(a) - int(b)) <= tol)
                   for a, b in zip(x[2:], y[2:]))
    if len(c) != len(s) or not all(same_head(x, y) for (x, _), (y, _) in zip(c, s)):
        print('ROW SEQUENCE DIFFERS')
        return 1
    cid = {v: str(i) for i, v in enumerate(c[0][0][2:5])}
    sid = {v: str(i) for i, v in enumerate(s[0][0][2:5])}
    diffs = 0
    for (head, a), (_, b) in zip(c, s):
        if head[0] == 'I':
            continue
        def norm(vals, ids):
            # F rows: fy bg poly d0 d1 -> map bg through the id table (scene 50 kept)
            vals = list(vals)
            if head[0] == 'F' and vals[1] in ids:
                vals[1] = 'p' + ids[vals[1]]
            return vals
        na, nb = norm(a, cid), norm(b, sid)
        bad = []
        for i, (x, y) in enumerate(zip(na, nb)):
            if x == y:
                continue
            try:
                if abs(int(x) - int(y)) <= tol:
                    continue
            except ValueError:
                pass
            bad.append(i)
        if bad:
            diffs += 1
            print(f"DIFF {' '.join(head)}: C {' '.join(na)} | shim {' '.join(nb)}")
    # Tracked Fx case: platform corner (local 20,20) at y 2500; core on
    # floats and the C library hit the platform, Fx core falls through.
    for (head, a), (_, b) in zip(c, s):
        if head[:5] == ['F', 'plat', '520', '2700', '520']:
            same = a[0] == b[0]
            print(f"known Fx case plat 520,520: {'now matches' if same else 'STILL DIFFERS'} (C {a[0]} | shim {b[0]})")
    print(f'{len(c)} rows, {diffs} differ beyond +-{tol}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
