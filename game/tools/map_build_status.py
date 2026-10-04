"""Receipt for the layout included in a successfully verified Clean image."""
import argparse
import json
from pathlib import Path
from layout_variants import atomic_json


def signature(path):
    stat=Path(path).stat()
    return dict(size=stat.st_size,mtime_ns=stat.st_mtime_ns)


def record(game):
    game=Path(game)
    snapshot=json.loads((game/'build/generated/layout-build.json').read_text(encoding='utf-8'))
    atomic_json(game/'build/map-preview.json',dict(version=1,snapshot=snapshot,
                files={name:signature(game/'build'/name) for name in ('game-clean.iso','game-clean.cue')}))


def matches(game,name,document):
    game=Path(game)
    try:
        data=json.loads((game/'build/map-preview.json').read_text(encoding='utf-8'))
        return (data['version']==1 and data['snapshot']==dict(layout=name,document=document)
                and set(data['files'])=={'game-clean.iso','game-clean.cue'}
                and all(signature(game/'build'/name)==stamp for name,stamp in data['files'].items()))
    except (OSError,ValueError,KeyError,TypeError): return False


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--game',type=Path,required=True)
    record(parser.parse_args().game)
