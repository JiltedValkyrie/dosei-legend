#!/usr/bin/env python3
"""Stage real Player with the production fixups, without selecting a runtime owner.

This is a compile/dependency work area, not a playable Player build. Never add
its sources to the live blob while bridge_player.cpp owns Player_Profile.
"""
import argparse
import hashlib
import json
from pathlib import Path

from oot_core_import import (GAME, HEADER_TREES, OOT_DEFAULT, fixup,
                             write_if_changed)

PLAYER_SOURCES = (
    'src/code/z_player_call.c',
    'src/code/z_player_lib.c',
    'src/overlays/actors/ovl_player_actor/z_player.c',
)


def stage(oot, out):
    # Validate the complete source set before writing anything.
    sources = {rel: (oot / rel).read_text(encoding='utf-8')
               for rel in PLAYER_SOURCES}
    stats = dict(macros=0, fxl=0, anon=0, mtxf=0, problems=[])
    headers = set()
    for tree in HEADER_TREES:
        headers.update((oot / tree).rglob('*.h'))
        headers.update((oot / tree).rglob('*.inc.c'))
    for path in sorted(headers):
        rel = path.relative_to(oot).as_posix()
        write_if_changed(out / 'decomp' / rel,
                         fixup(rel, path.read_text(encoding='utf-8'), stats))
    manifest = []
    for rel, source in sources.items():
        dest = Path('decomp') / Path(rel).with_suffix('.cpp')
        converted = fixup(rel, source, stats)
        write_if_changed(out / dest, converted)
        manifest.append(dict(source=rel, staged=dest.as_posix(),
                             source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                             staged_sha256=hashlib.sha256(converted.encode()).hexdigest()))
    report = dict(status='staged only; not compiled, linked or runtime-owned',
                  sources=manifest, fixups=stats,
                  ownership_blockers=[
                      'bridge_player.cpp defines Player_Profile and Player_UpdateWeaponInfo',
                      'bridge_play.cpp supplies Player library functions; resolve duplicate owners',
                      'z_player_call uses Kaleido overlay loading; Saturn needs resident dispatch',
                      'Player animation/root motion and gameplay limb anchors need Saturn backend',
                      'C movement, item dispatch and save copy-in must stop on core ownership',
                      'core collision must supply remaining C camera/actor queries before retirement',
                  ])
    write_if_changed(out / 'report.json', json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=OOT_DEFAULT)
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration')
    args = parser.parse_args()
    report = stage(args.oot, args.out)
    print(f"Staged {len(report['sources'])} real Player sources: {args.out}")
    print('Live source list, Player owner and disc unchanged. See report.json.')


if __name__ == '__main__':
    main()
