"""Compare math probe outputs: real-float reference vs Fx. Exit 1 on failures."""
import sys


def load(path):
    rows = []
    for line in open(path):
        name, val = line.rsplit(' ', 1)
        rows.append((name, float(val)))
    return rows


def main(ref_path, fx_path):
    ref, fx = load(ref_path), load(fx_path)
    if [n for n, _ in ref] != [n for n, _ in fx]:
        print('probe name lists differ')
        return 1
    bad = 0
    worst = (0.0, '')
    for (name, r), (_, f) in zip(ref, fx):
        err = abs(r - f)
        # Q16 step is 1.5e-5; allow a few steps plus 0.1% relative drift.
        # Integer outputs (angles) allow +/-2 binang units.
        tol = max(2.0 if r == int(r) and abs(r) > 1 else 0.0, 1e-4 + abs(r) * 1e-3)
        rel = err / max(abs(r), 1.0)
        if rel > worst[0]:
            worst = (rel, f'{name}: ref {r} fx {f}')
        if err > tol:
            bad += 1
            print(f'FAIL {name}: ref {r} fx {f} err {err:.6g}')
    print(f'{len(ref)} values, {bad} over tolerance; worst rel {worst[0]:.3g} ({worst[1]})')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(*sys.argv[1:3]))
