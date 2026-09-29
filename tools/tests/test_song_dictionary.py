import ctypes
import hashlib
import json
import os
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'game/tools'))
sys.path.insert(0, str(ROOT / 'tools/music-workshop'))
import build_cdda
import song_dictionary as songs
import music_assets

GCC = Path('C:/msys64/mingw64/bin/gcc.exe')


class SongDictionaryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game = self.root / 'game'
        audio = self.game / 'assets/audio'
        audio.mkdir(parents=True)
        for name in ('songs.json', 'cdda_tracks.json'):
            shutil.copyfile(ROOT / 'game/assets/audio' / name, audio / name)
        self.path = audio / 'songs.json'
        self.tracks_path = audio / 'cdda_tracks.json'

    def test_assignment_keeps_id_and_other_routes(self):
        before = songs.load(self.game)
        music_assets.assign_song('NA_BGM_GAME_OVER', 'CD', 'CHEST', root=self.root)
        after = songs.load(self.game)
        for old, new in zip(before['songs'], after['songs']):
            if old['song'] == 'NA_BGM_GAME_OVER':
                self.assertEqual(new['id'], old['id'])
                self.assertEqual(new['cd'], 'CHEST')
            else:
                self.assertEqual(new, old)
        music_assets.assign_song('NA_BGM_GAME_OVER', 'BANK', 'house', root=self.root)
        entry = next(s for s in songs.load(self.game)['songs'] if s['song'] == 'NA_BGM_GAME_OVER')
        self.assertNotIn('cd', entry)
        self.assertEqual(entry['bank'], 'house')

    def test_bad_mapping_and_streaming_cd_leave_dictionary_unchanged(self):
        before = self.path.read_bytes()
        for name, source, target in [('NA_BGM_GAME_OVER', 'CD', 'MISSING'),
                                      ('NA_BGM_GAME_OVER', 'BANK', 'missing'),
                                      ('NA_BGM_KOKIRI', 'CD', 'CHEST')]:
            with self.assertRaises(ValueError):
                music_assets.assign_song(name, source, target, root=self.root)
            self.assertEqual(self.path.read_bytes(), before)

    @unittest.skipUnless(GCC.is_file(), 'host GCC required')
    def test_actual_dispatch_survives_track_reorder_and_bank_assignment(self):
        def compile_and_check(folder, expected_track):
            songs.generate(self.game, folder)
            build_cdda.write_header(build_cdda.load_tracks(self.tracks_path), folder / 'cdda_tracks.h')
            harness = '''
#include "music_songs.c"
music_bank_t music_bank_title, music_bank_house, music_bank_nightmare,
 music_bank_kokiri, music_bank_navi, music_bank_deku_tree, music_bank_shop;
static int track, bank, fade;
void cdda_play(int n) { track=n; }
bool music_fade_to(const music_bank_t *p, unsigned int frames) {
 bank=(p==&music_bank_house) ? 1 : 2;fade=frames;return true;
}
int run(void) { track=bank=0;music_play(NA_BGM_GAME_OVER);return track ? track : -bank; }
int bank_fade(void) { music_play_fade(NA_BGM_LINK_HOUSE, 17);return bank==1 && fade==17; }
int bank_lookup(void) { return music_song_bank(NA_BGM_LINK_HOUSE)==&music_bank_house && music_song_bank((oot_song_t)65535)==0; }
int unknown(void) { return music_play((oot_song_t)65535); }
'''
            dll = folder / 'dispatch.dll'
            subprocess.run([str(GCC), '-shared', '-O2', '-I', str(ROOT / 'game/src'),
                            '-I', str(ROOT / 'shared/lib/music'), '-I', str(folder),
                            '-x', 'c', '-', '-o', str(dll)], input=harness, text=True, check=True,
                           env=dict(os.environ, PATH=str(GCC.parent) + os.pathsep + os.environ.get('PATH', '')))
            lib = ctypes.CDLL(str(dll))
            self.assertEqual(lib.run(), expected_track)
            self.assertEqual(lib.bank_fade(), 1)
            self.assertEqual(lib.bank_lookup(), 1)
            self.assertEqual(lib.unknown(), 0)
        doc = json.loads(self.tracks_path.read_text())
        original = next(t['track'] for t in doc['tracks'] if t['name'] == 'GAME_OVER')
        compile_and_check(self.root / 'original', original)
        a = next(t for t in doc['tracks'] if t['name'] == 'CHEST')
        b = next(t for t in doc['tracks'] if t['name'] == 'GAME_OVER')
        a['track'], b['track'] = b['track'], a['track']
        self.tracks_path.write_text(json.dumps(doc))
        compile_and_check(self.root / 'reordered', b['track'])
        music_assets.assign_song('NA_BGM_GAME_OVER', 'BANK', 'house', root=self.root)
        compile_and_check(self.root / 'bank', -1)

    def test_track_cache_follows_content_not_timestamps(self):
        source = self.root / 'source'
        for folder in ('sequences', 'soundfonts'):
            (source / folder).mkdir(parents=True)
        (source / 'soundfonts/Soundfont_3.xml').write_text('<Soundfont><Samples/></Soundfont>')
        seq = source / 'sequences/seq_43.seq'
        seq.write_text('original')
        entry = dict(track=2, name='CHEST', sequence=43, soundfont=3)
        fingerprint = build_cdda.track_fingerprint(entry, source)
        target = self.root / 'TRACK02.BIN'
        data = bytes(2352)
        target.write_bytes(data)
        target.with_suffix('.json').write_text(json.dumps(dict(fingerprint=fingerprint,
                                  sha256=hashlib.sha256(data).hexdigest())))
        self.assertTrue(build_cdda.cached_track(target, fingerprint))
        self.assertFalse(build_cdda.cached_track(target, build_cdda.track_fingerprint(dict(entry, track=3), source)))
        stamp = seq.stat()
        seq.write_text('modified')
        os.utime(seq, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertFalse(build_cdda.cached_track(target, build_cdda.track_fingerprint(entry, source)))
        target.write_bytes(bytes([1]) * 2352)
        self.assertFalse(build_cdda.cached_track(target, fingerprint))

    def test_generated_constants_and_routes_are_not_numeric_track_calls(self):
        songs.generate(self.game)
        routes = (self.game / 'build/generated/song_routes.inc').read_text()
        self.assertIn('SONG_CD(NA_BGM_GAME_OVER, CDDA_TRACK_GAME_OVER)', routes)
        for filename in ('demo.c', 'cutscene.c'):
            self.assertNotIn('cdda_play(', (ROOT / 'game/src' / filename).read_text())

    def test_cue_uses_dictionary_tracks_and_rejects_missing_audio(self):
        image, cue = self.root / 'game.iso', self.root / 'game.cue'
        image.write_bytes(bytes(2048))
        for n in (2, 3):
            (self.root / ('TRACK%02d.BIN' % n)).write_bytes(bytes(2352))
        args = ['write_cue.py', str(image), str(cue)]
        with patch.object(sys, 'argv', args), patch.object(build_cdda, 'load_tracks', return_value=[dict(track=2, name='CHEST')]):
            runpy.run_path(str(ROOT / 'game/tools/write_cue.py'))
            self.assertIn('TRACK02.BIN', cue.read_text())
            self.assertNotIn('TRACK03.BIN', cue.read_text())
            (self.root / 'TRACK02.BIN').unlink()
            with self.assertRaisesRegex(SystemExit, 'Missing declared CD song'):
                runpy.run_path(str(ROOT / 'game/tools/write_cue.py'))

    def test_duplicate_song_ids_rejected(self):
        doc = songs.load(self.game)
        doc['songs'][1]['id'] = doc['songs'][0]['id']
        with self.assertRaisesRegex(ValueError, 'Duplicate song'):
            songs.validate(doc, build_cdda.load_tracks(self.tracks_path))


if __name__ == '__main__':
    unittest.main()
