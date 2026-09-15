"""Regression checks for the US 1.2 score and timing/pitch conversion."""
import math
import struct
import unittest
from pathlib import Path

import build_title_audio as audio


class AudioTests(unittest.TestCase):
    def test_pitch_round_trip(self):
        # Exercise both sides of octave boundaries, including pitches above
        # the old u16 playback-rate ceiling and negative SCSP octaves.
        for rate in (4000, 11025, 22050, 32000, 44099, 44100, 44101, 65535, 88000, 96000):
            word = audio.scsp_pitch(rate)
            octave = (word >> 11) & 15
            if octave >= 8:
                octave -= 16
            actual = 44100 * 2 ** octave * (1 + (word & 1023) / 1024)
            self.assertLess(abs(1200 * math.log2(actual / rate)), 1.0)

    def test_gate_crossing_tempo_change(self):
        times = audio.timeline([(0, 120), (48, 60)], 96)
        # A half-quarter before the change and half-quarter after it.
        self.assertAlmostEqual(times[72] - times[24], .75)

    def test_envelope_time_is_audio_ticks(self):
        env = {'points': [(2, 32700), (229, 0), (1, 0)]}
        self.assertGreater(audio.envelope_level(env, .01), .9)
        self.assertEqual(audio.envelope_level(env, 1.0), 0)
        self.assertAlmostEqual(audio.release_seconds(186), 65 / 60)
        self.assertAlmostEqual(audio.release_seconds(93), 200 / 60)

    def test_full_us12_sequence(self):
        source = audio.ROOT / 'build/audio-source/extracted/assets/audio'
        self.assertTrue(source.is_dir(), 'Run the US 1.2 extraction before tests')
        notes, tempo, volumes, gain, intro, end, _ = audio.interpret(source / 'sequences/seq_30.seq')
        self.assertEqual(len(notes), 221)
        self.assertEqual(len(tempo), 17)
        self.assertEqual(intro, 624)
        self.assertEqual(gain, 70)
        times = audio.timeline(tempo, end)
        self.assertAlmostEqual(times[end], 77.9023775786, places=7)
        self.assertEqual(sorted({n['program'] for n in notes}), [1, 10, 11, 13, 14])
        self.assertGreater(len(volumes[11]), 20)
        self.assertTrue(all(n['end_tick'] > n['tick'] for n in notes))

    def test_sample_memory_and_loop_guards(self):
        import json
        manifest = json.loads((audio.ROOT / 'audio_manifest.json').read_text())
        blob = (audio.ROOT / 'assets/TITLE_PCM.RAW').read_bytes()
        self.assertLess(len(blob) + audio.SAMPLE_BASE, 512 * 1024)
        for s in manifest['samples']:
            self.assertEqual(s['offset'] % 2, 0)
            self.assertLess(s['loop_start'], s['loop_end'])
            self.assertLess(s['loop_end'], 65535)
            start = s['offset'] + 2 * s['loop_start']
            end = s['offset'] + 2 * s['loop_end']
            self.assertEqual(blob[start:start + 8], blob[end:end + 8])

    def test_linked_assets_match_generated_files(self):
        # Catch stale builtin assets or an incorrect sample copy size.
        symbols = {}
        for line in (audio.ROOT / 'build/title-screen.sym').read_text().splitlines():
            fields = line.split()
            if len(fields) == 3:
                symbols[fields[2]] = int(fields[0], 16)
        image = (audio.ROOT / 'build/title-screen.bin').read_bytes()
        for symbol, file in (('_asset_title_pcm', 'TITLE_PCM.RAW'),
                             ('_asset_title_levels', 'TITLE_LEVELS.RAW')):
            begin, end = symbols[symbol] - 0x06004000, symbols[symbol + '_end'] - 0x06004000
            self.assertEqual(image[begin:end], (audio.ROOT / 'assets' / file).read_bytes())
        self.assertLess(symbols['___bss_end'], 0x06100000)


if __name__ == '__main__':
    unittest.main()
