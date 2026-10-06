import sys
import unittest
import wave
from io import BytesIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'audio-workshop'))
import audio_assets as audio


class AudioWorkshopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.oot = audio.decomp_root()
        cls.source = audio.audio_source()
        cls.seq = (cls.oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
        cls.rows = audio.catalog(cls.oot)

    def test_catalog_sorted_with_sfx_and_music(self):
        ground = next(r for r in self.rows if r['name'] == 'NA_SE_PL_WALK_GROUND')
        self.assertEqual(ground['kind'], 'Player')
        self.assertEqual(ground['channel'], 'CHAN_02A1')
        kinds = [r['kind'] for r in self.rows]
        self.assertLess(kinds.index('Player'), kinds.index('Music'))
        self.assertGreater(sum(r['kind'] != 'Music' for r in self.rows), 400)
        self.assertGreater(sum(r['kind'] == 'Music' for r in self.rows), 50)

    def test_footstep_preview_has_sound(self):
        data = audio.render_sfx('CHAN_02A1', self.source, self.seq)
        with wave.open(BytesIO(data)) as wav:
            self.assertEqual(wav.getnchannels(), 1)
            pcm = wav.readframes(wav.getnframes())
        self.assertTrue(any(pcm))


if __name__ == '__main__':
    unittest.main()
