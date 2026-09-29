from pathlib import Path
import importlib.util
import json
import tempfile
import unittest

TOOL = Path(__file__).resolve().parents[1] / 'music-workshop/music_assets.py'
spec = importlib.util.spec_from_file_location('music_assets', TOOL)
music = importlib.util.module_from_spec(spec)
spec.loader.exec_module(music)

SOURCE, SOURCE_ERROR = music.find_source()
needs_extraction = unittest.skipIf(SOURCE is None,
                                   'No US 1.2 audio extraction: %s' % SOURCE_ERROR)


class ParsingTests(unittest.TestCase):
    """Header reads, which need no extraction."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'seq_99.seq'

    def test_reads_the_declared_soundfont_and_loop(self):
        self.path.write_text('#include "Soundfont_15.h"\n.sequence SEQ_0000\n'
                             'jump SEQ_0082\n')
        self.assertEqual(music.soundfont_of(self.path), 15)
        self.assertEqual(music.loop_label_of(self.path), 'SEQ_0082')

    def test_a_sequence_without_a_jump_has_no_loop_label(self):
        self.path.write_text('#include "Soundfont_3.h"\n.sequence SEQ_0000\nend\n')
        self.assertIsNone(music.loop_label_of(self.path))

    def test_a_sequence_without_a_soundfont_reports_none(self):
        self.path.write_text('.sequence SEQ_0000\nend\n')
        self.assertIsNone(music.soundfont_of(self.path))


@needs_extraction
class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.entries = {e['sequence']: e for e in music.catalog(SOURCE)}

    def test_finds_the_sequences_the_game_already_uses(self):
        for sequence in (30, 60, 31, 85, 35, 74, 75):
            self.assertIn(sequence, self.entries)

    def test_resolves_na_bgm_names_from_the_decomp_table(self):
        self.assertEqual(self.entries[60]['name'], 'NA_BGM_KOKIRI')
        self.assertEqual(self.entries[75]['name'], 'NA_BGM_DEKU_TREE_CS')

    def test_reports_the_soundfont_and_loop_each_sequence_declares(self):
        self.assertEqual(self.entries[60]['soundfont'], 15)
        self.assertEqual(self.entries[75]['soundfont'], 9)
        self.assertIsNotNone(self.entries[60]['loop'])

    def test_marks_music_the_game_already_ships(self):
        self.assertEqual(self.entries[60]['in_game'], 'kokiri forest')
        self.assertIsNone(self.entries[4]['in_game'])


@needs_extraction
class RenderTests(unittest.TestCase):
    def test_reports_a_score_against_the_player_limits(self):
        report = music.report(music.render(SOURCE, 75))
        self.assertEqual(report['soundfont'], 9)          # taken from the sequence
        self.assertTrue(report['frames_fit'])
        self.assertGreater(report['notes'], 0)
        self.assertLessEqual(report['peak_voices'], report['voices'])
        self.assertFalse(report['over_sample_budget'])

    def test_an_override_replaces_what_the_sequence_declares(self):
        built = music.render(SOURCE, 75, soundfont=3, loop=None,
                             stop_at_loop=False)
        self.assertEqual(built['soundfont'], 3)

    def test_a_budget_override_does_not_leak_into_the_next_render(self):
        before = music.audio.MUSIC_SAMPLE_BUDGET
        music.render(SOURCE, 75, budget=40000)
        self.assertEqual(music.audio.MUSIC_SAMPLE_BUDGET, before)

    def test_a_smaller_budget_produces_a_smaller_bank(self):
        small = len(music.render(SOURCE, 75, budget=40000)['pcm'])
        self.assertLess(small, len(music.render(SOURCE, 75)['pcm']))

    def test_the_budget_slack_only_covers_guard_samples(self):
        """A normal bank is in budget; a real overrun is still reported."""
        built = music.render(SOURCE, 75)
        self.assertFalse(music.report(built)['over_sample_budget'])
        built['budget'] = len(built['pcm']) // 4            # a real overrun
        self.assertTrue(music.report(built)['over_sample_budget'])

    def test_a_missing_sequence_is_refused(self):
        with self.assertRaises(ValueError):
            music.render(SOURCE, 9999)


class ExplainTests(unittest.TestCase):
    """Half the 105 sequences cannot be baked; say why, plainly."""

    def test_names_the_opcode_the_interpreter_lacks(self):
        reason = music.explain(ValueError('Unsupported sequence opcode: rldchan'))
        self.assertIn('rldchan', reason)
        self.assertIn('build_title_audio.py', reason)

    def test_explains_split_range_instruments(self):
        reason = music.explain(AssertionError("{'RangeLo': 'AF3'}"))
        self.assertIn('split-range', reason)

    def test_explains_an_infinite_release(self):
        self.assertIn('infinite',
                      music.explain(ValueError('Infinite release unsupported')))

    def test_never_returns_an_empty_reason(self):
        self.assertTrue(music.explain(AssertionError()).strip())


@needs_extraction
class ProbeTests(unittest.TestCase):
    def test_a_supported_sequence_probes_clean(self):
        built, reason = music.probe(SOURCE, 75)
        self.assertIsNone(reason)
        self.assertEqual(built['sequence'], 75)

    def test_an_unsupported_sequence_gives_a_reason_not_a_traceback(self):
        built, reason = music.probe(SOURCE, 3)      # uses rldchan
        self.assertIsNone(built)
        self.assertIn('rldchan', reason)

    def test_survey_reports_which_sequences_bake(self):
        entries = [e for e in music.catalog(SOURCE) if e['sequence'] in (3, 75)]
        rows = {r['sequence']: r for r in music.survey(SOURCE, entries)}
        self.assertTrue(rows[75]['bakes'])
        self.assertIsNotNone(rows[75]['seconds'])
        self.assertFalse(rows[3]['bakes'])
        self.assertIn('rldchan', rows[3]['reason'])


@needs_extraction
class BakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        self.folder = music.bake(SOURCE, 75, 'test bank', preview_seconds=4,
                                 workspace=self.workspace)

    def test_writes_the_five_bank_files(self):
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()),
                         ['TEST_BANK_LEVELS.RAW', 'TEST_BANK_PCM.RAW',
                          'preview.wav', 'test_bank_manifest.json',
                          'test_bank_score.h'])

    def test_the_header_matches_the_written_data(self):
        header = (self.folder / 'test_bank_score.h').read_text()
        pcm = (self.folder / 'TEST_BANK_PCM.RAW').stat().st_size
        levels = (self.folder / 'TEST_BANK_LEVELS.RAW').stat().st_size
        self.assertIn('#define TEST_BANK_PCM_BYTES %d' % pcm, header)
        self.assertIn('#define TEST_BANK_LEVEL_BYTES %d' % levels, header)
        self.assertIn('#define TEST_BANK_SAMPLE_BASE 4096', header)

    def test_the_manifest_records_the_source_and_its_limits(self):
        manifest = json.loads((self.folder / 'test_bank_manifest.json').read_text())
        self.assertEqual(manifest['sequence'], 75)
        self.assertEqual(len(manifest['sequence_sha256']), 64)
        self.assertTrue(any('not target playback' in line
                            for line in manifest['limitations']))

    def test_each_bake_gets_its_own_revision(self):
        again = music.bake(SOURCE, 75, 'test bank', preview_seconds=0,
                           workspace=self.workspace)
        self.assertNotEqual(again, self.folder)
        self.assertEqual(again.parent, self.folder.parent)

    def test_nothing_is_written_outside_the_workspace(self):
        self.assertEqual(self.folder.parent.parent, self.workspace)

    def test_a_bank_needs_a_name(self):
        with self.assertRaises(ValueError):
            music.bake(SOURCE, 75, '!!!', workspace=self.workspace)


if __name__ == '__main__':
    unittest.main()


class CddaManifestTests(unittest.TestCase):
    """The Red Book track list is data, so a new track needs no code change."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'game/assets/audio').mkdir(parents=True)
        self.manifest = self.root / music.CDDA_MANIFEST
        self.manifest.write_text(json.dumps({'tracks': [
            {'track': 2, 'name': 'CHEST', 'sequence': 43, 'soundfont': 3}]}))

    def install(self, sequence, name, **kwargs):
        """Install without rendering; build_cdda.py is exercised separately."""
        import unittest.mock as mock
        done = mock.Mock(returncode=0, stdout='', stderr='')
        with mock.patch.object(music.subprocess, 'run', return_value=done) as run:
            entry = music.install_cdda_track(sequence, name, root=self.root,
                                             **kwargs)
        return entry, run

    def test_a_new_track_takes_the_next_number(self):
        entry, _ = self.install(106, 'staff', soundfont=9)
        self.assertEqual(entry['track'], 3)
        self.assertEqual(entry['name'], 'STAFF')

    def test_reusing_a_name_replaces_that_track_instead_of_adding_one(self):
        self.install(106, 'STAFF', soundfont=9)
        entry, _ = self.install(107, 'STAFF', soundfont=3)
        self.assertEqual(entry['track'], 3)
        self.assertEqual(entry['sequence'], 107)
        self.assertEqual(len(music.cdda_tracks(self.root)), 2)

    def test_a_track_needs_a_name_for_its_c_define(self):
        with self.assertRaises(ValueError):
            self.install(106, '!!!', soundfont=9)

    def test_a_failed_render_leaves_the_manifest_untouched(self):
        import unittest.mock as mock
        before = self.manifest.read_bytes()
        done = mock.Mock(returncode=1, stdout='', stderr='bad sequence')
        with mock.patch.object(music.subprocess, 'run', return_value=done):
            with self.assertRaises(ValueError):
                music.install_cdda_track(106, 'STAFF', soundfont=9,
                                         root=self.root)
        self.assertEqual(self.manifest.read_bytes(), before)


class CddaBuilderTests(unittest.TestCase):
    """build_cdda.py validates the manifest and names every track for the runtime."""

    def setUp(self):
        builder = (Path(__file__).resolve().parents[2]
                   / 'game/tools/build_cdda.py')
        spec = importlib.util.spec_from_file_location('build_cdda', builder)
        self.cdda = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cdda)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'cdda_tracks.json'

    def write(self, tracks):
        self.path.write_text(json.dumps({'tracks': tracks}))
        return self.path

    def test_rejects_a_gap_that_would_silently_drop_later_tracks(self):
        """write_cue.py stops at the first missing TRACKnn.BIN."""
        with self.assertRaises(SystemExit):
            self.cdda.load_tracks(self.write([
                {'track': 2, 'name': 'A', 'sequence': 43, 'soundfont': 3},
                {'track': 4, 'name': 'B', 'sequence': 32, 'soundfont': 35}]))

    def test_rejects_duplicate_names(self):
        with self.assertRaises(SystemExit):
            self.cdda.load_tracks(self.write([
                {'track': 2, 'name': 'A', 'sequence': 43, 'soundfont': 3},
                {'track': 3, 'name': 'A', 'sequence': 32, 'soundfont': 35}]))

    def test_the_generated_header_names_every_track_and_its_range(self):
        entries = self.cdda.load_tracks(self.write([
            {'track': 2, 'name': 'CHEST', 'sequence': 43, 'soundfont': 3},
            {'track': 3, 'name': 'STAFF', 'sequence': 106, 'soundfont': 9}]))
        header = Path(self.temp.name) / 'cdda_tracks.h'
        self.cdda.write_header(entries, header)
        text = header.read_text()
        self.assertIn('#define CDDA_TRACK_CHEST', text)
        self.assertIn('#define CDDA_TRACK_STAFF', text)
        self.assertIn('#define CDDA_TRACK_FIRST 2', text)
        self.assertIn('#define CDDA_TRACK_LAST  3', text)
        self.assertIn('#define CDDA_TRACK_COUNT 2', text)

    def test_the_shipped_manifest_matches_the_tracks_the_game_plays(self):
        """Game routes name these songs; physical track numbers may change."""
        entries = {e['name']: e['track']
                   for e in self.cdda.load_tracks(self.cdda.MANIFEST)}
        self.assertTrue({'CHEST', 'GAME_OVER', 'SMALL_ITEM'} <= entries.keys())
