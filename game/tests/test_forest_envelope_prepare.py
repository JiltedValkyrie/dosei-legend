"""Actual scene_prepare stays exact while reusing bounded camera candidates."""
import ctypes
import math
import random
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_core_bgcheck import compiler_env
from test_graphics_backend import ROOT, function
from test_forest_envelope_draft import linked_trig


class ForestEnvelopePrepare(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        sine, cosine = linked_trig()
        (folder / 'trig.h').write_text(
            'static const int linked_sin[65536]={' + ','.join(map(str, sine)) + '};\n' +
            'static const int linked_cos[65536]={' + ','.join(map(str, cosine)) + '};\n')
        text = (ROOT / 'src/kokiri_sgl.c').read_text()
        fixture = (ROOT / 'tests/fixtures/forest_envelope_host.c').read_text()
        candidate = text[text.index('volatile unsigned forest_envelope_enabled'):]
        candidate = candidate[:candidate.index('/* Small views')]
        work = re.search(r'static union \{.*?\} forest_work;.*?forest_prep_fits\[.*?;', text, re.S).group()
        prep = text[text.index('static int side_cull_dist,'):text.index('/* Master: add the last prepare')]
        prep = re.sub(r'^#define PREP_PHASE\(v\).*$', '#define PREP_PHASE(v) (v)', prep, flags=re.M)
        fixture = fixture.replace('/* ACTUAL_CANDIDATE_STATE */', candidate)
        fixture = fixture.replace('/* ACTUAL_FOREST_WORK */', work)
        fixture = fixture.replace('/* ACTUAL_LOD */', function(ROOT / 'src/kokiri_sgl.c', 'static bool forest_lod_changed('))
        fixture = fixture.replace('/* ACTUAL_PREP */', prep)
        source = folder / 'scene.c'
        source.write_text(fixture)
        compiler, cls.env = compiler_env()
        exact = folder / 'exact.so'
        result = subprocess.run(
            [compiler, '-x', 'c', '-std=c99', '-O2', '-shared', '-fPIC', '-Wno-pointer-to-int-cast',
             '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-I', str(ROOT / 'src'),
             str(source), '-o', str(exact)], env=cls.env, capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        cached = folder / 'cached.so'
        shutil.copyfile(exact, cached)
        cls.exact, cls.cached = ctypes.CDLL(str(exact)), ctypes.CDLL(str(cached))
        cls.exact.set_full_scan(1)
        cls.exact.run_frame.restype = cls.cached.run_frame.restype = ctypes.c_uint32
        cls.buffer_type = ctypes.c_uint32 * (510 * 18 + 64 * 17)
        cls.a, cls.b = cls.buffer_type(), cls.buffer_type()

    def compare_frame(self, view, mode=1, pack=2):
        for lib, enabled in ((self.exact, 0), (self.cached, mode)):
            lib.set_mode(enabled, pack)
            lib.set_view(*view)
            self.assertNotEqual(lib.run_frame(), 0xFFFFFFFF, 'fog pass must leave tiles reset')
            self.assertEqual(lib.verify_geometry(), 0, (view, mode, pack))
        self.exact.snapshot(self.a)
        self.cached.snapshot(self.b)
        if bytes(self.a) != bytes(self.b):
            first = next(i for i, (a, b) in enumerate(zip(self.a, self.b)) if a != b)
            self.fail(f'view={view}, mode={mode}, pack={pack}, word={first}: '
                      f'exact={self.a[first]}, cached={self.b[first]}')

    def test_random_camera_walks_and_reload_preserve_visible_geometry_and_fog(self):
        rng = random.Random(21341)
        reuses = spill = high = 0
        for bank in range(6):
            for lib in (self.exact, self.cached):
                lib.load_bank(7381 + bank, bank & 1)
            x, y, z, yaw, pitch, linkz = 0, 50, 0, 0, 0, 0
            for frame in range(160):
                if frame and frame % 37 == 0:
                    yaw += rng.randrange(-30000, 30000)
                    x, z = rng.randrange(-1000, 1000), rng.randrange(-1000, 1000)
                else:
                    x += rng.randrange(-5, 6)
                    y += rng.randrange(-4, 5)
                    z += rng.randrange(-5, 6)
                    yaw += rng.randrange(-30, 31)
                pitch += rng.randrange(-20, 21)
                linkz = (0, 500, 4000)[(frame // 23) % 3]  # near/far/culled LOD
                view = (x, y, z, yaw, pitch, 280, 0, linkz)
                self.compare_frame(view)
                reuses += self.cached.state(0)
                spill += bool(self.cached.state(4) and self.cached.state(3))
                high += bool(not self.cached.state(4) and self.cached.state(3))
                if self.cached.state(0):
                    self.assertEqual(self.cached.state(2), 0, 'refit must request slave bank purge')
        self.assertGreater(reuses, 100)
        self.assertGreater(spill, 50)
        self.assertGreater(high, 50)
        print(f'actual prepare: 960 moving frames, {reuses} candidate refits; {high} high/{spill} spill draws exact')

    def test_running_variants_lead_widen_and_spill_stay_exact(self):
        """Running-speed walks (12-30 units/frame, steady turns) per variant."""
        builds = {}
        for mode in (1, 2, 3, 4, 5):
            rng = random.Random(9100 + mode)
            builds[mode] = refits = spill = 0
            for bank in range(3):
                for lib in (self.exact, self.cached):
                    lib.load_bank(4410 + bank, bank & 1)
                x, y, z, yaw, pitch = -400, 60, -500, 0, -600
                speed, turn = 12 + 6 * bank, (0, 24, -60)[bank]
                for frame in range(150):
                    if frame % 50 == 49:
                        yaw += 16384      # sharp turn, then run on
                    yaw = (yaw + turn + rng.randrange(-6, 7)) & 0xFFFF
                    sine, cosine = math.sin(yaw * math.tau / 65536), math.cos(yaw * math.tau / 65536)
                    x += round(speed * sine) + rng.randrange(-1, 2)
                    z += round(speed * cosine) + rng.randrange(-1, 2)
                    y += rng.randrange(-2, 3)
                    self.compare_frame((x, y, z, yaw, pitch, 280, 0, 0), mode=mode)
                    builds[mode] += self.cached.state(6)
                    refits += self.cached.state(0)
                    spill += bool(self.cached.state(4) and self.cached.state(3))
            self.assertGreater(refits, 150, mode)
            if mode == 5:
                self.assertGreater(spill, 300, 'variant 5 must draw from the Low RAM spill')
        self.assertLess(builds[2], builds[1])
        self.assertLess(builds[3], builds[2])
        print('running variants: builds per 450 frames ' +
              ', '.join(f'v{m}={builds[m]}' for m in sorted(builds)))

    def test_mode_fov_roll_pitch_bank_and_lod_boundaries(self):
        for lib in (self.exact, self.cached):
            lib.load_bank(1949, 1)
        view = (0, 50, 0, 0, 0, 280, 0, 0)
        self.compare_frame(view)
        self.compare_frame(view)
        self.assertTrue(self.cached.state(2))
        self.compare_frame(view, mode=0)
        self.assertFalse(self.cached.state(2), 'mode change must invalidate still-camera shortcut')
        self.compare_frame(view, mode=1)
        self.assertFalse(self.cached.state(2))
        for pack in (0, 1, 2, 2, 0, 2):
            self.compare_frame(view, pack=pack)
        for pitch in (7935, 7936, 8191, 8192, 8193, -7936, -8192, 32767, -32768, 0):
            for roll in (0, 1):
                for distance in (280, 1024, 1025):
                    view = (0, 50, 0, 65535, pitch, distance, roll, 500)
                    self.compare_frame(view)
        for scene in (3, 85, 81, 85):
            for lib in (self.exact, self.cached):
                lib.set_scene(scene)
            self.compare_frame((0, 50, 0, 0, 0, 280, 0, 0))
        for lib in (self.exact, self.cached):
            lib.load_bank(551, 0)
        self.compare_frame((0, 50, 0, 0, 0, 280, 0, 0))

    def test_empty_candidates_reuse_then_invalidate_without_stale_maps(self):
        for lib in (self.exact, self.cached):
            lib.load_bank(981, 1)  # All geometry lies at positive Z.
        self.compare_frame((0, 50, 0, 32768, 0, 280, 0, 0))
        self.assertTrue(self.cached.state(5))
        self.assertEqual(self.cached.state(1), 0)
        self.assertEqual(self.cached.state(3), 0)
        self.compare_frame((1, 50, 0, 32780, 0, 280, 0, 0))
        self.assertTrue(self.cached.state(0), 'empty candidate list should reuse safely')
        self.assertEqual(self.cached.state(1), 0)
        for mode, pack in ((0, 2), (1, 2), (1, 0), (1, 2)):
            self.compare_frame((1, 50, 0, 32780, 0, 280, 0, 0), mode, pack)
        self.compare_frame((1, 50, 0, 0, 0, 280, 0, 0))
        self.assertGreater(self.cached.state(1), 0)
        self.assertGreater(self.cached.state(3), 0)
        for lib in (self.exact, self.cached):
            lib.load_bank(1239, 1)
        self.compare_frame((1, 50, 0, 32780, 0, 280, 0, 0))
        self.assertEqual(self.cached.state(1), 0)
        self.compare_frame((2, 50, 0, 32790, 0, 280, 0, 0))
        self.assertTrue(self.cached.state(0))
