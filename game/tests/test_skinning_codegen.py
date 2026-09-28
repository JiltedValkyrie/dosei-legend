"""Guard the target-code regression that made posing cost ~100 ms."""
import pathlib
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
OBJDUMP = ROOT.parent.parent / 'sh2eb-elf/bin/sh2eb-elf-objdump.exe'


class SkinningCodegen(unittest.TestCase):
    def test_animated_mesh_does_not_cull_against_bind_pose_normals(self):
        scene = ROOT / 'build/generated/link_mesh.c'   # cart tables (BUG-039)
        if not scene.is_file():
            self.skipTest('build assets first')
        attrs = [line for line in scene.read_text().splitlines() if 'ATTRIBUTE(' in line]
        self.assertTrue(attrs)
        self.assertTrue(all('Dual_Plane' in line for line in attrs))

    def test_runtime_coordinates_do_not_use_float_macro(self):
        source = (ROOT / 'src/link_anim.c').read_text()
        for coordinate in ('offset[', 'local->', 'posed[', '-posed['):
            self.assertNotIn('toFIXED(' + coordinate, source)
        self.assertIn('#define INTEGER_FIXED', source)

    @unittest.skipUnless(OBJDUMP.is_file(), 'SH-2 objdump unavailable')
    def test_built_skinner_has_no_software_float_calls(self):
        found = False
        for directory in ('obj', 'obj-hires'):
            obj = ROOT / 'build' / directory / 'link_anim.o'
            if not obj.is_file():
                continue
            found = True
            text = subprocess.check_output([str(OBJDUMP), '-dr', str(obj)], text=True)
            for symbol in ('floatsidf', 'muldf3', 'fixdfsi', 'floatsisf', 'mulsf3'):
                self.assertNotIn(symbol, text, '%s needs rebuilding' % directory)
        if not found:
            self.skipTest('build both images before checking target objects')
