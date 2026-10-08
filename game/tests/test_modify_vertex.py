"""Source display-list vertex edits must preserve prior faces and skin positions."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'shared/tools'))
from build_kokiri_scene import DisplayLists


class ModifyVertex(unittest.TestCase):
    def test_signed_uv_and_colour_modify_cached_vertex_without_retransform(self):
        commands = b''.join(struct.pack('>II', *pair) for pair in (
            (0x02140004, 0xffe00040), (0x02100004, 0x12345678), (0xdf000000, 0)))
        lists = DisplayLists(commands, b'')
        original = (100, 200, 300, 5, 6, 255, 255, 255, 255)
        lists.cache[2] = original
        prior_face = [lists.cache[2]]
        def forbid_reload(*args):
            self.fail('ModifyVertex must not apply the limb transform twice')
        lists.load_vertex = forbid_reload
        lists.walk(0x02000000)
        self.assertEqual(lists.cache[2], (100, 200, 300, -1, 2, 0x12, 0x34, 0x56, 0x78))
        self.assertEqual(prior_face, [original])

    def test_missing_vertex_and_screen_space_edits_fail_closed(self):
        for op, vertex, message in ((0x02140002, None, 'unloaded vertex'),
                                    (0x02180002, (0,)*9, 'Unsupported ModifyVertex field')):
            lists = DisplayLists(struct.pack('>IIII', op, 0, 0xdf000000, 0), b'')
            lists.cache[1] = vertex
            with self.assertRaisesRegex(ValueError, message):
                lists.walk(0x02000000)


if __name__ == '__main__': unittest.main()
