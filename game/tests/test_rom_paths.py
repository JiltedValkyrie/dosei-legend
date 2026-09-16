"""Separate ROM storage must not change where decomp metadata is read."""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import build_link_model as link


class RomPathTests(unittest.TestCase):
    def test_scene_and_actor_use_external_rom_with_checkout_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            oot = root/'decomp'
            metadata = oot/'baseroms/ntsc-1.2'
            metadata.mkdir(parents=True)
            roms = root/'separate ROM directory'
            roms.mkdir()
            (metadata/'config.yml').write_text('dmadata_start: 0x0\n')
            (metadata/'segments.csv').write_text(
                'Name\nspot04_scene\nspot04_room_0\nspot04_room_1\nspot04_room_2\nobject_link_child\n')
            data = b''.join(struct.pack('>4I', 0, 1, 80+i, 0) for i in range(5))+b'ABCDE'
            (roms/'baserom.z64').write_bytes(data)
            # Synthetic fixture, not an actual game ROM. Production still checks MD5.
            with patch.object(hashlib, 'md5') as md5:
                md5.return_value.hexdigest.return_value = link.ROM_MD5
                segments = link.scene_tool.extract(oot, roms)
                self.assertEqual(segments['spot04_scene'], b'A')
                self.assertEqual(len(segments), 4)
                self.assertEqual(link.read_object(oot, 'object_link_child', roms), b'E')


if __name__ == '__main__':
    unittest.main()
