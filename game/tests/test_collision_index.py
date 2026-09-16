"""The collision XZ index must change speed, not answers.

Builds the real collision set from FOREST.BIN, then compares every
kokiri_collision_floor/clear result with and without the index over a dense
sweep of the scene. Compiles the shared baseline source natively, so it does
not exercise SH-2 behaviour -- only that indexing is answer-preserving.
"""

import ctypes
import pathlib
import struct
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCENE = ROOT / 'levels/kokiri/assets/static/FOREST.BIN'
SOURCE = ROOT.parent / 'shared/lib/collision/kokiri_collision.c'
GCC = pathlib.Path('C:/msys64/mingw64/bin/gcc.exe')

INDEX_BYTES = 16 * 1024


def collision_triangles(path):
    data = path.read_bytes()
    names = ('magic', 'version', 'nverts', 'ntris', 'vo', 'fo', 'to', 'texbytes',
             'total', 'cx', 'cy', 'cz', 'radius', 'commands', 'co', 'ncol')
    head = dict(zip(names, struct.unpack_from('>9I3i4I', data, 0)))
    return data[head['co']:head['co'] + head['ncol'] * 36], head['ncol']


@unittest.skipUnless(SCENE.is_file() and SOURCE.is_file() and GCC.is_file(),
                     'scene, collision source and mingw gcc required')
class IndexEquivalenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # ignore_cleanup_errors: Windows keeps the loaded DLL locked.
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        library = pathlib.Path(cls.tmp.name) / 'collision.dll'
        # gcc.exe needs its own bin directory on PATH to load its DLLs when
        # it is launched outside an MSYS2 shell; without it the process exits
        # non-zero with no diagnostics at all.
        env = dict(os.environ)
        env['PATH'] = str(GCC.parent) + os.pathsep + env.get('PATH', '')
        subprocess.run([str(GCC), '-shared', '-O2', '-o', str(library),
                        str(SOURCE)], check=True, env=env)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.kokiri_collision_clear.restype = ctypes.c_bool
        cls.lib.kokiri_collision_floor.restype = ctypes.c_bool
        cls.lib.kokiri_collision_index.restype = ctypes.c_bool

        raw, count = collision_triangles(SCENE)
        # The file stores big-endian int16; the host build reads native order.
        swapped = bytearray(len(raw))
        for i in range(0, len(raw), 2):
            swapped[i], swapped[i + 1] = raw[i + 1], raw[i]
        cls.data = (ctypes.c_char * len(swapped)).from_buffer(swapped)
        cls.count = count

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _reinit(self, indexed):
        self.lib.kokiri_collision_init(self.data, ctypes.c_uint32(self.count))
        if not indexed:
            return False
        # Held on the instance: the C side keeps pointers into this buffer, so
        # letting it fall out of scope crashes the queries. That lifetime rule
        # is the contract kokiri_collision_index() documents.
        self._index_buffer = ctypes.create_string_buffer(INDEX_BYTES)
        return bool(self.lib.kokiri_collision_index(self._index_buffer,
                                                    ctypes.c_uint32(INDEX_BYTES)))

    def _sweep(self):
        for x in range(-2300, 6000, 311):
            for z in range(-3000, 2400, 289):
                yield x, z

    def test_index_builds_within_the_viewer_buffer(self):
        self.assertTrue(self._reinit(True),
                        '16 KB is not enough to index this collision set')

    def test_floor_matches_the_full_scan(self):
        plain = {}
        self._reinit(False)
        height = ctypes.c_int32()
        for x, z in self._sweep():
            hit = self.lib.kokiri_collision_floor(x, z, 200,
                                                  ctypes.byref(height))
            plain[(x, z)] = (bool(hit), height.value if hit else None)

        self.assertTrue(self._reinit(True))
        for x, z in self._sweep():
            hit = self.lib.kokiri_collision_floor(x, z, 200,
                                                  ctypes.byref(height))
            got = (bool(hit), height.value if hit else None)
            self.assertEqual(got, plain[(x, z)], 'floor differs at %d,%d' % (x, z))

    def test_clear_matches_the_full_scan(self):
        class Position(ctypes.Structure):
            _fields_ = [('x', ctypes.c_int32), ('y', ctypes.c_int32),
                        ('z', ctypes.c_int32)]
        self.lib.kokiri_collision_clear.argtypes = [Position]

        plain = {}
        self._reinit(False)
        for x, z in self._sweep():
            for y in (40, 91, 200):
                plain[(x, y, z)] = bool(
                    self.lib.kokiri_collision_clear(Position(x, y, z)))

        self.assertTrue(self._reinit(True))
        for x, z in self._sweep():
            for y in (40, 91, 200):
                got = bool(self.lib.kokiri_collision_clear(Position(x, y, z)))
                self.assertEqual(got, plain[(x, y, z)],
                                 'clear differs at %d,%d,%d' % (x, y, z))


if __name__ == '__main__':
    unittest.main()
