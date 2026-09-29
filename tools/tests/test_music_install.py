"""Game exports replace coherent banks and survive the interior asset builder."""
from pathlib import Path
import importlib.util
import json
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/music-workshop'))
sys.path.insert(0, str(ROOT / 'game/tools'))
import music_assets as music
import build_interior_audio as interiors


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        seq = self.root / 'seq_75.seq'
        seq.write_text('fixture sequence')
        self.built = dict(sequence=75, soundfont=9, loop=None, seconds=1,
            frames=60, voices=24, notes=[], triggers=[(0, 0, 0, 0, 64)],
            pcm=b'\x00\x01' * 4, levels=b'\xff' * (60 * 24), budget=159600,
            samples=[dict(offset=0, loop_start=0, loop_end=4)], omitted=[],
            sample_base=0x1000, times={0: 0, 1: .5}, intro=1, seq_path=seq)

    def install(self, target):
        return music.install_game_bank(self.root, self.built, target,
                                       preserve_intro=True, root=self.root)

    def test_every_target_uses_runtime_names_and_overwrites(self):
        for target, (folder, prefix, raw) in music.GAME_TARGETS.items():
            with self.subTest(target=target):
                destination = self.root / folder
                destination.mkdir(parents=True, exist_ok=True)
                (destination / (raw + '_PCM.RAW')).write_bytes(b'old')
                self.assertEqual(self.install(target), destination)
                self.assertEqual((destination / (raw + '_PCM.RAW')).read_bytes(), self.built['pcm'])
                self.assertEqual((destination / (raw + '_LEVELS.RAW')).read_bytes(), self.built['levels'])
                header = (destination / (prefix.lower() + '_score.h')).read_text()
                self.assertIn('#define %s_LOOP_FRAME 30' % prefix, header)
                self.assertIn(prefix.lower() + '_triggers[]', header)
                manifest = json.loads((destination / (prefix.lower() + '_manifest.json')).read_text())
                self.assertEqual(manifest['game_target'], target)
                self.assertFalse(any('workspace only' in s for s in manifest['limitations']))
                self.assertFalse(list(destination.glob('.music-bank-*')))

    def test_invalid_bank_does_not_replace_existing_files(self):
        destination = self.install('Kokiri Forest')
        before = {p.name: p.read_bytes() for p in destination.iterdir()}
        for key, value in [('voices', 25), ('frames', 65536),
                           ('sample_base', 0x50000), ('levels', b'')]:
            original = self.built[key]
            self.built[key] = value
            with self.assertRaises(ValueError):
                self.install('Kokiri Forest')
            self.built[key] = original
        self.assertEqual(before, {p.name: p.read_bytes() for p in destination.iterdir()})

    def test_failed_second_replace_restores_first(self):
        destination = self.install('Title')
        before = {p.name: p.read_bytes() for p in destination.iterdir()}
        self.built['pcm'] = b'\x01\x02' * 4
        replace = music.os.replace
        calls = 0

        def fail_once(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError('simulated locked file')
            return replace(source, target)

        with patch.object(music.os, 'replace', side_effect=fail_once):
            with self.assertRaises(OSError):
                self.install('Title')
        self.assertEqual(before, {p.name: p.read_bytes() for p in destination.iterdir()})

    def test_house_override_survives_rebuild_and_clears_stock_stamp(self):
        folder = self.install("Link's house")
        generated = self.root / 'game/build/generated'
        generated.mkdir(parents=True)
        (generated / 'HOUSE.stamp').write_text('old stock digest')
        self.assertTrue(interiors.copy_workshop_bank('HOUSE', generated, folder))
        self.assertFalse((generated / 'HOUSE.stamp').exists())
        self.assertEqual((generated / 'HOUSE_PCM.RAW').read_bytes(), self.built['pcm'])
        (generated / 'HOUSE_PCM.RAW').write_bytes(b'stale')
        self.assertTrue(interiors.copy_workshop_bank('HOUSE', generated, folder))
        self.assertEqual((generated / 'HOUSE_PCM.RAW').read_bytes(), self.built['pcm'])
        for path in folder.iterdir():
            path.unlink()
        self.assertFalse(interiors.copy_workshop_bank('HOUSE', generated, folder))

    def test_incomplete_override_fails_without_copying(self):
        folder = self.root / 'overrides'
        folder.mkdir()
        (folder / 'SHOP_PCM.RAW').write_bytes(b'incomplete')
        generated = self.root / 'generated'
        with self.assertRaisesRegex(ValueError, 'Incomplete workshop bank'):
            interiors.copy_workshop_bank('SHOP', generated, folder)
        self.assertFalse(generated.exists())


if __name__ == '__main__':
    unittest.main()
