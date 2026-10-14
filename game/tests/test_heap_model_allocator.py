"""heap_peak_model.Heap must replay the game's real allocator exactly.

Compiles src/heap_profile.c (which wraps joengine malloc.c) on the host with
tests/fixtures/jo_shim, replays random traces of fast / reuse / same-size
allocations and frees through both, and compares the result zone and the
whole block layout (offsets, sizes, free flags) after every operation,
including out-of-memory merges and retries.
"""
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JO = ROOT.parents[1] / 'joengine' / 'jo_engine'
sys.path.insert(0, str(ROOT / 'tools'))
import heap_peak_model as hp  # noqa: E402

BEH = (hp.FAST, hp.REUSE, hp.SAME)


class HeapModelAllocator(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cc = shutil.which('gcc') or shutil.which('cc')
        if not cc or not (JO / 'malloc.c').exists():
            raise unittest.SkipTest('host C compiler or joengine malloc.c unavailable')
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        shutil.copytree(ROOT / 'tests/fixtures/jo_shim/jo', t / 'jo')
        for src in (JO / 'malloc.c', ROOT / 'src/heap_profile.c', ROOT / 'src/heap_profile.h',
                    ROOT / 'tests/fixtures/heap_model_driver.c'):
            shutil.copy(src, t / src.name)
        cls.exe = t / 'driver'
        subprocess.run([cc, '-O1', '-fgnu89-inline', '-w', '-I', str(t), '-o', str(cls.exe),
                        str(t / 'heap_model_driver.c')], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def replay(self, seed, zones, ops=1500):
        rng = random.Random(seed)
        heap = hp.Heap([('z%d' % i, n) for i, n in enumerate(zones)])
        script, expect, live, sizes = [], [], [], []
        script += ['z %d' % n for n in zones]
        for k in range(ops):
            if live and rng.random() < 0.42:
                key = live.pop(rng.randrange(len(live)))
                heap.free('k%d' % key)
                script.append('f %d' % key)
                expect.append((0, self.layout(heap)))
                continue
            if sizes and rng.random() < 0.3:
                n = rng.choice(sizes)            # exact repeats exercise SAME / reuse
            else:
                n = rng.choice((rng.randint(1, 64), rng.randint(1, 900), rng.randint(500, 4000)))
                sizes.append(n)
            beh = rng.randrange(3)
            script.append('m %d %d %d' % (k, n, beh))
            try:
                zone = heap.malloc('k%d' % k, n, BEH[beh])
                live.append(k)
            except hp.OutOfMemory:
                zone = -1
            expect.append((zone, self.layout(heap)))
        out = subprocess.run([str(self.exe)], input='\n'.join(script) + '\n', capture_output=True,
                             text=True, check=True).stdout.split('\n')
        got, i = [], 0
        while i < len(out) and out[i].startswith('R '):
            zone = int(out[i][2:])
            rows = []
            for z in range(len(zones)):
                parts = out[i + 1 + z].split()[2:]
                rows.append([tuple(map(int, p.split(':'))) for p in parts])
            got.append((zone, rows))
            i += 1 + len(zones)
        self.assertEqual(len(got), len(expect))
        for step, (g, e) in enumerate(zip(got, expect)):
            if g[1] == e[1] and (g[0] == e[0] or script[len(zones) + step][0] == 'f'):
                continue
            self.fail('seed %d step %d (%s): C %r != model %r' % (
                seed, step, script[len(zones) + step], g, e))
        return sum(1 for zone, _ in expect if zone < 0)

    @staticmethod
    def layout(heap):
        return [[(b[0], b[1], int(b[2])) for b in heap.blocks[z]] for z in range(len(heap.caps))]

    def test_random_traces_match(self):
        for seed in range(6):
            self.replay(seed, (2048, 16384, 6144, 1024))

    def test_tight_zones_force_merges(self):
        failures = sum(self.replay(seed, (512, 4096, 2048), ops=2500) for seed in range(6, 10))
        self.assertGreater(failures, 0)  # traces reach out-of-memory merge + retry


if __name__ == '__main__':
    unittest.main()
