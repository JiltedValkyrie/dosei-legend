import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_disc_directory import check


class DiscDirectoryTests(unittest.TestCase):
    def test_directory_records_include_dot_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(262):
                (root / str(i)).touch()
            with self.assertRaisesRegex(ValueError, '264 directory entries'):
                check(root, 256)
            check(root, 288)

    def test_rejects_names_mastering_accepts_but_saturn_cannot_find(self):
        for name in ('TREEMOUTH.BIN','BOSSHEART.BIN','BOSSCLEAR.PCM','BOSSCLEAR.LVL'):
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);(root/name).touch()
                with self.assertRaisesRegex(ValueError,'Saturn GFS 8.3'):
                    check(root,384)

    def test_short_asset_names_and_boot_binary_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name in ('TREEMTH.BIN','BOSSHRT.BIN','BOSSCLR.PCM','BOSSCLR.LVL','0.bin'):
                (root/name).touch()
            check(root,384)

    def test_subdirectory_also_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            sub = root / 'sub'
            sub.mkdir()
            for i in range(3):
                (sub / str(i)).touch()
            with self.assertRaisesRegex(ValueError, '5 directory entries'):
                check(root, 4)


if __name__ == '__main__':
    unittest.main()
