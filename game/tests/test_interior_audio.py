"""Area scores must fit sound RAM, retain loop points and bind every trigger."""
import json
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_cart_tables as tables


class InteriorAudio(unittest.TestCase):
    def test_house_and_shop_score_bounds(self):
        for name, sequence in (('HOUSE', 31), ('SHOP', 85), ('DUNGEON', 24), ('WOODS', 62), ('FAIRY', 40), ('BOSS',27), ('BOSSCLEAR',33)):
            with self.subTest(bank=name):
                gen = ROOT / 'build/generated'
                header = (gen / (name.lower() + '_score.h')).read_text()
                manifest = json.loads((gen / (name.lower() + '_manifest.json')).read_text())
                value = lambda suffix: tables.define(header, name + '_' + suffix)
                override = ROOT / 'assets/audio/interiors' / (name.lower() + '_manifest.json')
                expected = json.loads(override.read_text())['sequence'] if override.exists() else sequence
                self.assertEqual(manifest['sequence'], expected)
                self.assertEqual(value('LOOP_FRAME'), manifest['loop_frame'])
                self.assertLess(value('LOOP_FRAME'), value('FRAMES'))
                self.assertEqual((gen / (name + '_LEVELS.RAW')).stat().st_size,
                                 value('FRAMES') * value('VOICES'))
                self.assertEqual((gen / (name + '_PCM.RAW')).stat().st_size, value('PCM_BYTES'))
                self.assertLessEqual(value('SAMPLE_BASE') + value('PCM_BYTES'), 0x50000)
                for offset, start, end in tables.rows(header, name.lower() + '_pcm'):
                    self.assertTrue(0 <= start < end < 65535)
                    self.assertLessEqual(offset + 2 * end, value('PCM_BYTES'))
                for frame, slot, sample, pitch, pan in tables.rows(header, name.lower() + '_triggers'):
                    self.assertLess(frame, value('FRAMES'))
                    self.assertLess(slot, value('VOICES'))
                    self.assertLess(sample, len(tables.rows(header, name.lower() + '_pcm')))

    def test_disc_trigger_bank_order_and_payload(self):
        blob = (ROOT / 'build/cd/MUSICTRG.BIN').read_bytes()
        self.assertEqual(blob[:4], b'KTRG')
        self.assertEqual(struct.unpack_from('>H', blob, 4)[0], len(tables.BANKS))
        at = 6 + 2 * len(tables.BANKS)
        for i, (name, prefix, path) in enumerate(tables.BANKS):
            rows = tables.rows(path.read_text(), name)
            self.assertEqual(struct.unpack_from('>H', blob, 6 + 2 * i)[0], len(rows))
            for row in rows:
                self.assertEqual(struct.unpack_from('>HBBHBx', blob, at), row)
                at += 8
        self.assertEqual(at, len(blob))
        self.assertLessEqual(at, tables.MUSICTRG_LIMIT)


if __name__ == '__main__':
    unittest.main()
