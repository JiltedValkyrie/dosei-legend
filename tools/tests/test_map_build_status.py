import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'game/tools'))
import map_build_status as status


class BuildStatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.game=Path(self.tmp.name)
        generated=self.game/'build/generated'; generated.mkdir(parents=True)
        self.document={'version':1,'base':'ntsc-1.2','rooms':{}}
        (generated/'layout-build.json').write_text(json.dumps(dict(layout='water',document=self.document)))
        for name in ('game-clean.iso','game-clean.cue'): (self.game/'build'/name).write_bytes(b'fixture')

    def test_no_receipt_means_unverified(self):
        self.assertFalse(status.matches(self.game,'water',self.document))

    def test_success_identifies_exact_layout_and_document(self):
        status.record(self.game)
        self.assertTrue(status.matches(self.game,'water',self.document))
        self.assertFalse(status.matches(self.game,'other',self.document))
        self.assertFalse(status.matches(self.game,'water',dict(self.document,labels={'x':'changed'})))

    def test_replaced_or_missing_image_invalidates_receipt(self):
        status.record(self.game)
        (self.game/'build/game-clean.iso').write_bytes(b'other image')
        self.assertFalse(status.matches(self.game,'water',self.document))
        (self.game/'build/game-clean.cue').unlink()
        self.assertFalse(status.matches(self.game,'water',self.document))


if __name__=='__main__': unittest.main()
