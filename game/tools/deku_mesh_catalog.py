"""Expose all original Deku Tree rooms as Mesh Workshop editing sources.

These KFR1 previews are editing inputs, not replacements for runtime room banks.
"""
import argparse
from pathlib import Path
import build_hybrid_scene as hybrid
import build_link_model as link


def export(oot, rom_dir, out):
    out.mkdir(parents=True, exist_ok=True)
    for prefix in ('ydan', 'ydan_boss'):
        faces = hybrid.load_faces(oot, rom_dir, prefix=prefix)
        names = sorted({f['room'] for f in faces})
        for name in names:
            selected = []
            for original in faces:
                if original['room'] != name:
                    continue
                f = dict(original, limb=0, full_texture=True)
                # Preview transparency must preserve opaque-list alpha cutouts too.
                if f.get('texture') and any(c[3] < 64 for c in f['texture']['colors']):
                    f['transparent'] = True
                selected.append(f)
            dest = out / (name.upper() + '.BIN')
            link.write_model(selected, dest, character=False)
            print(dest.name, len(selected), 'source triangles')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=hybrid.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=Path(__file__).resolve().parents[1]/'build/generated/deku-edit')
    args = ap.parse_args()
    export(args.oot, args.rom_dir, args.out)
