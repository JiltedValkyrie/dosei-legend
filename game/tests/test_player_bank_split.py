"""split_player_bank.py: resident + demand groups + scene cutscene packs.

Every clip id of ALL.PFB lands in exactly one family (resident, one group,
scene packs), blocks are byte-identical, the Saturn C cutscene clips stay
resident, and resident + all groups + any one scene pack register together
(no duplicate ids, PlayerFrameBank_Register's rule).
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import split_player_bank as sp  # noqa: E402

BANK = ROOT / 'build/player-migration/bank_full'
OOT = Path(os.environ.get('DOSEI_OOT', str(ROOT.parents[2] / 'game-decomps/n64/oot')))


@unittest.skipUnless((BANK / 'ALL.PFB').exists() and (OOT / 'include/item.h').exists(),
                     'encoded bank and decomp required')
class PlayerBankSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        t = Path(cls.tmp.name)
        cls.report = sp.split(OOT, BANK, t / 'cd', t / 'player_groups.h', t / 'groups.json')
        cls.cd = t / 'cd'
        cls.header = (t / 'player_groups.h').read_text()

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def files(self, pattern):
        return {p.name: sp.read_bank(p) for p in sorted(self.cd.glob(pattern))}

    def test_partition_and_bytes(self):
        everything = sp.read_bank(BANK / 'ALL.PFB')
        c_clips = self.files('PLAYC.PFB')['PLAYC.PFB']
        res = self.files('PLAYRES.PFB')['PLAYRES.PFB']
        self.assertFalse(set(c_clips) & set(res))
        res = {**res, **c_clips}
        groups = self.files('PG*.PFB')
        packs = self.files('PCS??.PFB')
        self.assertEqual(len(groups), len(sp.GROUPS))
        seen = set(res)
        for blocks in groups.values():
            self.assertFalse(seen & set(blocks))
            seen |= set(blocks)
        for blocks in packs.values():
            self.assertFalse(seen & set(blocks))      # loadable with every group
        self.assertEqual(seen | {g for b in packs.values() for g in b}, set(everything))
        for family in [res] + list(groups.values()) + list(packs.values()):
            for gid, block in family.items():
                self.assertEqual(block, everything[gid])
        self.assertLess(len(sp.pack_file(res, res)), (BANK / 'ALL.PFB').stat().st_size)

    def test_c_cutscene_clips_resident(self):
        import json
        import build_link_model as blm
        ids = json.loads((BANK / 'ids.json').read_text())
        res = self.files('PLAYC.PFB')['PLAYC.PFB']
        for _, sym, *_ in blm.CLIPS:
            self.assertIn(ids[sym], res, sym)

    def test_header_tables(self):
        self.assertIn('PLAYER_GROUP_COUNT %d' % len(sp.GROUPS), self.header)
        self.assertEqual(len(re.findall(r'"PG\w+\.PFB"', self.header)), len(sp.GROUPS))
        flags = self.report['scene_flags']
        ids = self.report['scene_ids']
        self.assertTrue(flags[ids['spot04']] & 2)                 # Kokiri Forest water -> SWIM
        self.assertLess(max(flags), 1 << 9)                       # cutscene flag clear of group bits
        self.assertEqual(sp.CS_PACK, 1 << len(sp.GROUPS))
        self.assertTrue(flags[ids['tokinoma']] & sp.CS_PACK)            # Temple of Time cutscene pack
        for name, size in self.report['sizes'].items():
            self.assertTrue((self.cd / name).stat().st_size == size)


if __name__ == '__main__':
    unittest.main()
