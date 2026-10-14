"""The opening cue retains every source note and its release tail."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import build_cdda as cdda


class ChestAudio(unittest.TestCase):
    def test_complete_source_sequence_is_not_capped(self):
        chest = next(e for e in cdda.load_tracks() if e['name'] == 'CHEST')
        self.assertNotIn('max_seconds', chest)
        source = cdda.audio.ROOT / 'build/audio-source/extracted/assets/audio'
        sequence = source / f"sequences/seq_{chest['sequence']}.seq"
        if not sequence.exists():
            self.skipTest('extracted audio source required')
        notes, tempo, _, _, _, end, _ = cdda.audio.interpret(sequence, 'SEQ_0000')
        seconds = cdda.audio.timeline(tempo, end)[end] + 1.0
        self.assertEqual(len(notes), 276)
        self.assertGreater(seconds, 8.5)
        self.assertLess(seconds, 8.6)
        target = ROOT / 'build/TRACK02.BIN'
        if cdda.cached_track(target, cdda.track_fingerprint(chest, source)):
            duration = target.stat().st_size / (4 * cdda.HZ)
            self.assertGreaterEqual(duration, seconds)
            self.assertLess(duration, seconds + 1 / 75)


if __name__ == '__main__':
    unittest.main()
