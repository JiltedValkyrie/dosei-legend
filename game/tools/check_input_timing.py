"""Host timing checks, NOT controller-to-photon latency measurements.

Compile the current camera easing function unchanged and measure its step
response in callbacks. Separately model the current 30 Hz movement gate at
several callback cadences. Does not launch or send input to any window.
"""
import ctypes
import json
import os
import pathlib
import re
import subprocess
import tempfile


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    source = (root / 'src/demo.c').read_text()
    lag = re.search(r'^#define FOLLOW_LAG\s+(\d+)', source, re.M)[1]
    function = re.search(
        r'static int32_t follow_approach\([^}]+\n}', source)[0]
    code = '#include <stdint.h>\n#define FOLLOW_LAG ' + lag + '\n'
    code += function + '\n'
    code += 'int32_t sample(int32_t x,int32_t target) { return follow_approach(x,target); }'
    compiler = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')
    env = dict(os.environ)
    env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp:
        library = pathlib.Path(temp) / 'camera_response.dll'
        subprocess.run([str(compiler), '-shared', '-O2', '-x', 'c', '-',
                        '-o', str(library)], input=code, text=True, env=env,
                       check=True)
        lib = ctypes.CDLL(str(library))
        lib.sample.argtypes = [ctypes.c_int32, ctypes.c_int32]
        lib.sample.restype = ctypes.c_int32
        position = 0
        samples = []
        while position < 90:
            position = lib.sample(position, 100)
            samples.append(position)
        print(json.dumps({'camera_100_unit_step_positions': samples,
                          'callbacks_to_90_percent': len(samples)}))
        for rate in (60, 30, 20, 15):
            # Enumerate draw callbacks on a 60 Hz clock. At each callback the
            # real gate uses elapsed//2; a held button can move only if >0.
            previous = 0
            eligible = []
            interval = 60 // rate
            for tick in range(interval, 121, interval):
                steps = (tick - previous) // 2
                if steps:
                    eligible.append(tick / 60)
                previous += min(steps, 4) * 2
            gaps = [b - a for a, b in zip(eligible, eligible[1:])]
            print(json.dumps({
                'assumed_draw_callbacks_per_second': rate,
                'modeled_max_wait_to_eligible_update_ms': round(max(gaps) * 1000, 2),
                'camera_90_percent_settle_ms': round(len(samples) / rate * 1000, 2),
                'excludes': 'controller polling, SMPC phase, render time, GPU queue, display'
            }))


if __name__ == '__main__':
    main()
