"""Check source clock cadence and capture the gradient in visible Kronos.

Uses only the diagnostic command mailbox. The source clock and pause path run
normally; telemetry is read from symbols in this image's ELF.
"""
import argparse
import json
import subprocess
import time
from pathlib import Path

import control as c


def main():
    ap = argparse.ArgumentParser(__doc__)
    ap.add_argument('--folder', default='environment-v1')
    args = ap.parse_args()
    output = c.RUN / 'verification' / args.folder
    output.mkdir(parents=True, exist_ok=True)
    p = c.Process(json.loads((c.RUN / 'session.json').read_text(encoding='utf-8-sig'))['pid'])
    deadline = time.monotonic() + 60
    while True:
        try:
            p.words()
            break
        except RuntimeError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)
            p = c.Process(p.pid)
    rows = []

    def read(name):
        row = dict(name=name, **c.environment(p), state=c.status(p.words()))
        rows.append(row)
        print(json.dumps(row), flush=True)
        return row

    def step(ticks, buttons=0):
        return p.command(2, steps=ticks, buttons=buttons, axis_x=128, axis_y=128)

    def capture(name):
        subprocess.run(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                        '-File', str(c.ROOT / 'game/tools/capture-kronos.ps1'),
                        '-ViewerId', str(p.pid), '-OutputPath', str(output / (name + '.png'))], check=True)

    try:
        p.command(4, hud=1)
        p.command(1, pose=[0,181,6178,32768], camera=[0,310,6400,32768,-1820], legacy=0)
        step(60)  # Settle physics and initialize the core before measuring.
        if c.environment(p)['paused']:
            step(1, c.BUTTONS['start'])
            step(1)
        for name, start, advance in [('noon', 0x8000, 200), ('night', 0xE000, 400)]:
            p.command(5, pose=[start,start,0,0])
            before = read(name + '-before')
            step(30)
            after = read(name + '-after')
            assert (after['day_time']-before['day_time']) & 65535 == advance, (before, after)
            capture(name)
        p.command(5, pose=[0x7000,0x8000,0,0])
        step(30)
        held = read('sky-time-held-ahead')
        assert held['day_time'] == 0x7000+200 and held['skybox_time'] == 0x8000, held
        assert held['total_days'] == after['total_days']+1, (after,held)
        assert held['bgs_days'] == after['bgs_days']+1, (after,held)

        step(1, c.BUTTONS['start'])
        before = read('pause-before')
        assert before['paused'], before
        step(60)
        after = read('pause-after')
        assert after['paused'] and after['day_time'] == before['day_time'], (before, after)
        capture('pause-equipment')
        step(1, c.BUTTONS['start'])
        step(1)
        assert not read('pause-closed')['paused']

        for name, start in [('dawn',0x4000), ('dusk',0xB800)]:
            p.command(5, pose=[start,start,0,0])
            step(3)
            read(name)
            capture(name)
        p.command(5, pose=[0x8000,0x8000,0,0])
        step(3)
        read('restored-noon')
    finally:
        (output / 'clock.json').write_text(json.dumps(rows, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    main()
