"""Bake the real En_Owl's two skeletons, five clips and source head flip."""
import argparse
import json
from pathlib import Path
import build_npc_sprites as sprites
import owl_sources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/child-route-owl'))
    args = parser.parse_args()
    work, out = args.out / 'sprite-work', args.out / 'sprites'
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    sprites.bake_generic(args.oot, args.oot / 'baseroms/ntsc-1.2', work, out, args.out,
                         only_objects=owl_sources.OBJECTS, extra_sources=owl_sources.SOURCES,
                         extra_objects=owl_sources.OBJECTS)
    rows = json.loads((args.out / 'generic_sprites.json').read_text())
    files = {out / ('G%03X%02X.SPR' % (row[0], row[3])) for row in rows}
    print('owl sprites:', len(rows), 'keys,', len(files), 'sheets,',
          sum(path.stat().st_size for path in files), 'bytes; runtime acceptance pending')


if __name__ == '__main__':
    main()
