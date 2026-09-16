"""Kokiri score checks; no emulator or active build changes required."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent / 'shared/tools'))
import build_title_audio as audio


class KokiriAudioTests(unittest.TestCase):
    def test_sequence_timing_and_transpose(self):
        source = audio.ROOT / 'build/audio-source/extracted/assets/audio/sequences/seq_60.seq'
        notes, tempo, volumes, gain, intro, end, omitted = audio.interpret(source, 'SEQ_0050')
        self.assertEqual((len(notes), gain, intro, end), (597, 70, 960, 5952))
        self.assertEqual({t for _, t in tempo}, {145})
        times = audio.timeline(tempo, end)
        self.assertAlmostEqual(times[intro], 8.27586206897)
        self.assertAlmostEqual(times[end], 51.3103448276)
        self.assertEqual(sorted({n['program'] for n in notes}), [0, 1, 2, 3, 4, 8, 10, 11, 12, 13, 14, 15])
        self.assertTrue(all(n['end_tick'] > n['tick'] for n in notes))
        self.assertNotIn('transpose', omitted)
        # Replay with transpose removed in-memory to ensure it changes notes,
        # rather than merely being accepted by the parser.
        original = audio.parse
        def untransposed(path):
            code, labels = original(path)
            return [(op, [0] if op == 'transpose' else args) for op, args in code], labels
        try:
            audio.parse = untransposed
            plain = audio.interpret(source, 'SEQ_0050')[0]
        finally:
            audio.parse = original
        deltas = [n['key'] - p['key'] for n, p in zip(notes, plain)]
        self.assertEqual(set(deltas), {0, 12})

    def test_generated_budget_guards_and_triggers(self):
        folder = ROOT / 'levels/kokiri/assets/audio'
        manifest = json.loads((folder / 'manifest.json').read_text())
        pcm = (folder / 'KOKIRI_PCM.RAW').read_bytes()
        levels = (folder / 'KOKIRI_LEVELS.RAW').read_bytes()
        self.assertEqual(len(pcm), manifest['pcm_bytes'])
        self.assertLess(len(pcm) + audio.SAMPLE_BASE, 512 * 1024)
        self.assertEqual(len(levels), manifest['frames'] * audio.VOICES)
        for sample in manifest['samples']:
            self.assertEqual(sample['offset'] % 2, 0)
            self.assertLess(sample['loop_start'], sample['loop_end'])
            self.assertLess(sample['loop_end'], 65535)
            begin = sample['offset'] + 2 * sample['loop_start']
            end = sample['offset'] + 2 * sample['loop_end']
            self.assertEqual(pcm[begin:begin + 8], pcm[end:end + 8])
        header = (folder / 'kokiri_score.h').read_text()
        triggers = re.findall(r'\{ (\d+), (\d+), (\d+), (\d+), (\d+) \}', header)
        self.assertEqual(len(triggers), 597)
        previous = -1
        for item in triggers:
            frame, slot, sample, pitch, pan = map(int, item)
            self.assertGreaterEqual(frame, previous)
            self.assertLess(frame, manifest['frames'])
            self.assertLess(slot, audio.VOICES)
            self.assertLess(sample, len(manifest['samples']))
            self.assertLess(pitch, 65536)
            self.assertLess(pan, 32)
            previous = frame

    def test_title_assets_unchanged_by_generalized_builder(self):
        source = audio.ROOT / 'build/audio-source/extracted/assets/audio'
        envelopes, instruments, samples, pcm, hashes = audio.load_font(source)
        notes, tempo, volumes, gain, intro, end, _ = audio.interpret(source / 'sequences/seq_30.seq')
        _, levels, triggers, _ = audio.bake(notes, audio.timeline(tempo, end), volumes, gain,
                                           envelopes, instruments, samples, end)
        self.assertEqual(bytes(pcm), (audio.ROOT / 'assets/audio/title/TITLE_PCM.RAW').read_bytes())
        self.assertEqual(bytes(levels), (audio.ROOT / 'assets/audio/title/TITLE_LEVELS.RAW').read_bytes())
        expected = re.findall(r'\{ (\d+), (\d+), (\d+), (\d+), (\d+) \}',
                              (audio.ROOT / 'assets/audio/title/title_score.h').read_text())
        self.assertEqual(triggers, [tuple(map(int, t)) for t in expected])
