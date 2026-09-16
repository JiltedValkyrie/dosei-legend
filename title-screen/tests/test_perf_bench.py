"""Run the production profiler against controlled FRT reads and report capture."""
from pathlib import Path
import os
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PerfBenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['PATH'] = 'C:/msys64/mingw64/bin;' + os.environ['PATH']
        cls.exe = ROOT / 'build/perf_bench_test.exe'
        cls.exe.parent.mkdir(exist_ok=True)
        subprocess.run([
            'C:/msys64/mingw64/bin/gcc.exe', '-std=c99', '-O2',
            '-Wall', '-Wextra', '-Werror',
            '-I' + str(ROOT / 'tests/native/perf_stubs'),
            str(ROOT / 'tests/native/perf_bench_harness.c'),
            '-o', str(cls.exe),
        ], check=True)

    def test_clock_accounting_and_report(self):
        for scenario in ('byte_carry', 'full_carry', 'pending', 'status_carry',
                         'multiple_wraps', 'wide_report', 'nested', 'invalid_span',
                         'negative', 'attempt_cap', 'overflow', 'warmup',
                         'field_boundary_pending', 'field_arm_and_close',
                         'field_partial_and_wrap', 'field_bad_periods',
                         'field_absent', 'field_rejected_population'):
            with self.subTest(scenario=scenario):
                result = subprocess.run([str(self.exe), scenario], capture_output=True,
                                        text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
