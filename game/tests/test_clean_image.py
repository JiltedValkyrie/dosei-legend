"""Inspect the built SH-2 object, not just a source-side flag."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
OBJECT = ROOT/'build/obj-clean/main.o'


class CleanImage(unittest.TestCase):
    @unittest.skipUnless(OBJECT.exists(), 'build --clean first')
    def test_clean_hud_has_no_compiled_diagnostic_strings(self):
        data = OBJECT.read_bytes()
        for label in (b'heap %d', b'mv%u', b'msh p%d', b'Jo/SGL Kokiri viewer',
                      b'subm %d', b'cam %s', b'prep%u'):
            self.assertNotIn(label, data)
