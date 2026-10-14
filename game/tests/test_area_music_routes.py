"""Every sequence the source can request has a bank: ocarina song fanfares too."""
import json
import os
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
OOT = Path(os.environ.get('DOSEI_OOT', ROOT.parents[2] / 'game-decomps/n64/oot'))


@unittest.skipUnless((OOT / 'include/tables/sequence_table.h').exists(), 'decomp required')
class AreaMusicRoutes(unittest.TestCase):
    def test_message_ocarina_fanfares_are_required(self):
        import build_area_music as music
        table = (OOT / 'include/tables/sequence_table.h').read_text(encoding='utf-8')
        ids = {n: int(i) for i, n in re.findall(r'DEFINE_SEQUENCE\s*\(Sequence_(\d+),\s*(NA_BGM_\w+)', table)}
        text = (OOT / 'src/code/z_message.c').read_text(encoding='utf-8')
        body = re.search(r'sOcarinaSongFanfares\[\] = \{(.*?)\};', text, re.S).group(1)
        fanfares = {ids[n] for n in re.findall(r'NA_BGM_\w+', body)}
        self.assertEqual(len(fanfares), 12)
        routed = {s['id'] for s in json.loads((ROOT / 'assets/audio/songs.json').read_text())['songs']}
        # Song of Time (0x48) crashed Field -> Kakariko: AUDF fatal, no bank.
        self.assertIn(0x48, fanfares)
        self.assertLessEqual(fanfares - routed, music.route_sequences(OOT))


if __name__ == '__main__':
    unittest.main()
