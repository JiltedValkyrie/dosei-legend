"""Title metadata must follow regenerated PCM, or all sound init is skipped."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]


class TitleAudioSize(unittest.TestCase):
    def test_title_size_is_generated_and_matches_sample_bank(self):
        assets = ROOT / 'shared/assets/audio/title'
        header = (assets / 'title_score.h').read_text()
        size = re.search(r'#define TITLE_PCM_BYTES (\d+)', header)
        self.assertIsNotNone(size, 'title generator must export its PCM byte count')
        self.assertEqual(int(size[1]), (assets / 'TITLE_PCM.RAW').stat().st_size)
        base = int(re.search(r'#define TITLE_SAMPLE_BASE (\d+)', header)[1])
        limit = int(re.search(r'#define MUSIC_SAMPLE_LIMIT (0x[0-9A-Fa-f]+)',
                    (ROOT / 'shared/lib/music/music.h').read_text())[1], 16)
        self.assertLessEqual(base + int(size[1]), limit)
        source = (ROOT / 'game/src/music_banks.c').read_text()
        self.assertNotRegex(source, r'#define\s+TITLE_PCM_BYTES')
        self.assertIn('TITLE_SAMPLE_BASE, TITLE_PCM_BYTES', source)


if __name__ == '__main__': unittest.main()
