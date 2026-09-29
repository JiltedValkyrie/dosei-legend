import json
from pathlib import Path
import shutil
import unittest
from unittest.mock import Mock, patch

import test_music_install as fixtures

music = fixtures.music


class PublishTests(unittest.TestCase):
    def setUp(self):
        fixtures.InstallTests.setUp(self)
        folder = self.root / 'game/assets/audio'
        folder.mkdir(parents=True)
        for name in ('songs.json', 'cdda_tracks.json'):
            shutil.copyfile(fixtures.ROOT / 'game/assets/audio' / name, folder / name)
        self.songs = folder / 'songs.json'

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}

    def renderer(self, command, **kwargs):
        out = Path(command[command.index('--out') + 1])
        header = Path(command[command.index('--header') + 1])
        out.mkdir(parents=True, exist_ok=True)
        header.parent.mkdir(parents=True, exist_ok=True)
        cached = self.root / 'game/build/TRACK02.BIN'
        if cached.exists():
            self.assertEqual((out / cached.name).read_bytes(), cached.read_bytes())
        (out / 'TRACK05.BIN').write_bytes(bytes(2352))
        header.write_text('generated header')
        return Mock(returncode=0)

    def cd(self, song='NA_BGM_GAME_OVER'):
        return music.publish_song(self.root, song, music.CDDA_TARGET, 75,
                                  'New Death', soundfont=9, root=self.root)

    def test_cd_publish_adds_audio_and_named_route_preserving_other_songs(self):
        before = music.game_songs(self.root)
        cache = self.root / 'game/build/TRACK02.BIN'
        cache.parent.mkdir(parents=True)
        cache.write_bytes(bytes([7]) * 2352)
        with patch.object(music.subprocess, 'run', side_effect=self.renderer):
            self.cd()
        self.assertTrue((self.root / 'game/build/TRACK05.BIN').is_file())
        self.assertEqual(cache.read_bytes(), bytes([7]) * 2352)
        for old, new in zip(before, music.game_songs(self.root)):
            if old['song'] == 'NA_BGM_GAME_OVER':
                self.assertEqual(new['cd'], 'NEW_DEATH')
                self.assertEqual(new['id'], old['id'])
            else:
                self.assertEqual(old, new)
        self.assertEqual(music.cdda_tracks(self.root)[-1]['name'], 'NEW_DEATH')

    def test_bank_publish_updates_audio_and_changes_cd_route_to_bank(self):
        music.publish_song(self.root, 'NA_BGM_GAME_OVER', "Link's house", 75,
                           built=self.built, root=self.root)
        entry = next(s for s in music.game_songs(self.root) if s['song'] == 'NA_BGM_GAME_OVER')
        self.assertEqual(entry['src'], 'BANK')
        self.assertEqual(entry['bank'], 'house')
        self.assertNotIn('cd', entry)
        self.assertEqual((self.root / 'game/assets/audio/interiors/HOUSE_PCM.RAW').read_bytes(), self.built['pcm'])

    def test_render_failure_changes_nothing(self):
        before = self.snapshot()
        with patch.object(music.subprocess, 'run', return_value=Mock(returncode=1, stderr='render failed')):
            with self.assertRaisesRegex(ValueError, 'render failed'):
                self.cd()
        self.assertEqual(self.snapshot(), before)

    def test_mapping_write_failure_rolls_back_audio_and_track_manifest(self):
        before = self.snapshot()
        replace = music.os.replace
        def fail_mapping(src, dest):
            if dest == self.songs:
                raise OSError('mapping failed')
            return replace(src, dest)
        with patch.object(music.subprocess, 'run', side_effect=self.renderer), patch.object(music.os, 'replace', side_effect=fail_mapping):
            with self.assertRaisesRegex(OSError, 'mapping failed'):
                self.cd()
        self.assertEqual(self.snapshot(), before)

    def test_invalid_cd_route_rejected_before_render(self):
        before = self.snapshot()
        with patch.object(music.subprocess, 'run') as render:
            with self.assertRaisesRegex(ValueError, 'requires BANK'):
                self.cd('NA_BGM_KOKIRI')
            render.assert_not_called()
        self.assertEqual(self.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
