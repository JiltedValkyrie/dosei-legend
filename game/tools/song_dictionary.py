"""One song routing dictionary shared by the Workshop and game generator."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
BANKS = ('title', 'house', 'nightmare', 'kokiri', 'navi', 'deku_tree', 'shop', 'dungeon', 'woods')
# These callers need data streaming, startup initialization or timed bank stops.
# CD fanfares run only at the existing frozen-world playback sites.
BANK_ONLY = {'NA_BGM_TITLE', 'NA_BGM_LINK_HOUSE', 'NA_BGM_OPENING_GANON',
             'NA_BGM_KOKIRI', 'NA_BGM_NAVI_OPENING', 'NA_BGM_DEKU_TREE_CS', 'NA_BGM_SHOP', 'NA_BGM_DUNGEON', 'NA_BGM_SARIA_THEME'}
REQUIRED = BANK_ONLY | {'NA_BGM_GAME_OVER', 'NA_BGM_OPEN_TRE_BOX', 'NA_BGM_SMALL_ITEM_GET'}


def validate(document, tracks):
    songs = document['songs']
    names, ids = set(), set()
    cd_names = {t['name'].upper() for t in tracks}
    for entry in songs:
        name, number = entry['song'], entry['id']
        if not re.fullmatch(r'NA_BGM_[A-Z0-9_]+', name):
            raise ValueError('Invalid song constant: ' + name)
        if type(number) is not int or not 0 <= number <= 65535:
            raise ValueError('Song IDs must be integers in 0..65535')
        if name in names or number in ids:
            raise ValueError('Duplicate song name or ID: ' + name)
        names.add(name)
        ids.add(number)
        if entry['src'] == 'BANK':
            if entry.get('bank') not in BANKS:
                raise ValueError('Unknown bank for ' + name)
        elif entry['src'] == 'CD':
            if entry.get('cd') not in cd_names:
                raise ValueError('Unknown named CD track for ' + name)
            if name in BANK_ONLY:
                raise ValueError(name + ' requires BANK: its current game caller streams data or uses timed bank cues')
        else:
            raise ValueError('Song source must be BANK or CD: ' + name)
    if REQUIRED - names:
        raise ValueError('Missing required songs: ' + ', '.join(sorted(REQUIRED - names)))
    return songs


def load(root=ROOT):
    from build_cdda import load_tracks
    document = json.loads((root / 'assets/audio/songs.json').read_text(encoding='utf-8'))
    try:
        tracks = load_tracks(root / 'assets/audio/cdda_tracks.json')
    except SystemExit as exc:
        raise ValueError(str(exc)) from exc
    validate(document, tracks)
    return document


def generate(root=ROOT, out=None):
    out = out or root / 'build/generated'
    songs = load(root)['songs']
    header = ['/* Generated from assets/audio/songs.json. Do not edit. */',
              '#ifndef DOSEI_SONG_IDS_H', '#define DOSEI_SONG_IDS_H',
              'typedef enum {']
    routes = ['/* Generated song routes. Define SONG_BANK and SONG_CD before including. */']
    for s in songs:
        header.append('    %s = %d,' % (s['song'], s['id']))
        routes.append('SONG_BANK(%s, %s)' % (s['song'], s['bank']) if s['src'] == 'BANK'
                      else 'SONG_CD(%s, CDDA_TRACK_%s)' % (s['song'], s['cd']))
    header += ['} oot_song_t;', '#endif', '']
    out.mkdir(parents=True, exist_ok=True)
    for name, text in [('song_ids.h', '\n'.join(header)), ('song_routes.inc', '\n'.join(routes) + '\n')]:
        path = out / name
        if not path.exists() or path.read_text() != text:
            path.write_text(text)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    generate(out=args.out)
