"""Square-retopo fixtures in the real visible Kronos window (any run folder).

Same poses/cameras/inputs as compare_tr.py's mode-0 pass, so captures pair
with Astra's checkpoint (verification/m0-*, m2-*), plus walks along x=0 across
the whole patch in both directions (every 33/34 piece crossing). Each capture
stores status, SGL matrix, the walked VDP1 command list and a PNG. No TR face
records: the square floor has no P3 children to match.

    set CONTROL_RUN=game/build/square-retopo/s184
    python game/tools/control_probe/compare_square.py --folder s184-v1
"""
import json
import struct
import subprocess
import time
import control as c


def commands(p):
    raw = p.read(p.ptrs['Vdp1Ram'], 0x13300)
    out, at, ret = [], 0, 0
    for _ in range(2456):
        cmd = struct.unpack_from('>16H', raw, at)
        if cmd[0] & 0x8000:
            break
        jp = (cmd[0] >> 12) & 7
        if not jp & 4:
            out.append(dict(address=at, words=cmd))
        nxt = at + 32
        if jp & 3 == 1:
            nxt = cmd[1] * 8
        elif jp & 3 == 2:
            ret, nxt = at + 32, cmd[1] * 8
        elif jp & 3 == 3:
            nxt = ret
        if nxt >= len(raw) or nxt == at:
            break
        at = nxt
    return out


def snapshot(p, out, name, rows):
    data = c.trace(p)
    data['commands'] = commands(p)
    (out / (name + '.json')).write_text(json.dumps(data, indent=2))
    subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                    str(c.ROOT / 'game/tools/capture-kronos.ps1'), '-ViewerId', str(p.pid),
                    '-OutputPath', str(out / (name + '.png'))], check=True, capture_output=True)
    row = dict(name=name, link=data['status']['link'], camera=data['status']['camera'],
               commands=len(data['commands']), visible=data['visible'], total=data['total'])
    rows.append(row)
    print(json.dumps(row), flush=True)


def walk_across(p, out, rows, label, z0, yaw, back):
    """Land first, then traverse about 3600 units in six bounded input legs."""
    p.command(1, pose=[0, 450, z0, yaw], camera=[0, 520, z0 - back, yaw, -1820], legacy=0)
    p.command(2, steps=60, buttons=0, axis_x=128, axis_y=128)
    snapshot(p, out, f'{label}-0', rows)
    for leg in range(1, 7):
        p.command(2, steps=300, buttons=c.BUTTONS['b'], axis_x=128, axis_y=36)
        snapshot(p, out, f'{label}-{leg}', rows)


def main():
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--folder', required=True)
    args = ap.parse_args()
    p = c.Process(json.loads((c.RUN / 'session.json').read_text(encoding='utf-8-sig'))['pid'])
    end = time.monotonic() + 60
    while True:
        try:
            p.words()
            break
        except (RuntimeError, OSError):
            if time.monotonic() > end:
                raise
            time.sleep(.2)
            p = c.Process(p.pid)
    # Video RAM can be allocated after Work RAM during GUI startup.
    p = c.Process(p.pid)
    out = c.RUN / 'verification' / args.folder
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    p.command(4, hud=1)
    # Warm both local cells first, as compare_tr.py does: equal LOD history.
    p.command(1, pose=[736, 360, 4675, 13714], camera=[500, 440, 4675, 13714, -1820], legacy=0)
    time.sleep(1.5)
    for name, eye, legacy in [('oot', [-91, 262, 4320, 13714, -1820], 0),
                              ('far', [-214, 235, 4282, 13714, 0], 1)]:
        p.command(1, pose=[37, 185, 4353, 13714], camera=eye, legacy=legacy)
        snapshot(p, out, f'sq-{name}', rows)
    p.command(1, pose=[37, 185, 4353, 13714], camera=[-91, 262, 4320, 13714, -1820], legacy=0)
    for n in (10, 20, 30):
        p.command(2, steps=10, buttons=c.BUTTONS['b'], axis_x=128, axis_y=220)
        snapshot(p, out, f'sq-walk{n}', rows)
    for name, pose, eye, legacy in [
            ('corner', [23, 4, 3407, 44546], [-206, 54, 3226, 11317, 0], 1),
            ('center', [1192, 328, 4114, 14082], [1066, 415, 4078, 14082, -1820], 0)]:
        p.command(1, pose=pose, camera=eye, legacy=legacy)
        snapshot(p, out, f'sq-{name}', rows)
        p.command(2, steps=15, buttons=0, axis_x=128, axis_y=128)
        p.command(2, steps=8, buttons=c.BUTTONS['y'], axis_x=128, axis_y=128)
        snapshot(p, out, f'sq-{name}-jump', rows)
        p.command(2, steps=20, buttons=0, axis_x=200, axis_y=128)
        snapshot(p, out, f'sq-{name}-turn', rows)
    walk_across(p, out, rows, 'sq-north', 3500, 0, 130)
    walk_across(p, out, rows, 'sq-south', 6500, 32768, -130)
    p.command(1, pose=[37, 185, 4353, 13714], camera=[-91, 262, 4320, 13714, -1820], legacy=0)
    (out / 'summary.json').write_text(json.dumps(rows, indent=2))


if __name__ == '__main__':
    main()
