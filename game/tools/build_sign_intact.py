#!/usr/bin/env python3
"""Bake En_Kanban's intact sign; Saturn mesh mode handles its hit fade."""
import argparse
import pathlib
import struct

import build_link_model as link
from build_shop_props import PropLists


# gSignRectangularDL in the verified US 1.2 gameplay_keep segment. The source
# EnKanban_Draw selects it for partFlags==0xFFFF instead of drawing cut pieces.
SIGN_DISPLAY_LIST = 0x0403D560


def intact_faces(keep):
    lists = PropLists(b'', b'')
    lists.segments = {4: keep, 8: struct.pack('>II', 0xDF000000, 0)}
    lists.current_limb = 0
    lists.matrix_limbs = []
    lists.walk(SIGN_DISPLAY_LIST)
    faces = lists.faces
    positions = {tuple(v[:3]) for face in faces for v in face['vertices']}
    bounds = [(min(v[k] for v in positions), max(v[k] for v in positions))
              for k in range(3)] if positions else []
    # Reject a different segment/version or misplaced symbol, not a plausible
    # but unrelated display list. read_object also verifies the US 1.2 ROM MD5.
    if len(faces) != 19 or len(positions) != 14 or bounds != [(-2000, 2000), (0, 6000), (-300, 200)]:
        raise ValueError('gSignRectangularDL geometry does not match source sign')
    for face in faces:
        face['limb'] = 0
        face['full_texture'] = True
        # Keep source gameplay_keep textures through the shared prop baker.
        if face.get('texture_segment') == 4:
            face['texture_segment'] = 6
    link.apply_primitive_colour(faces)
    return link.scale_faces(faces, .01)


def build(oot, rom_dir, dest):
    faces = intact_faces(link.read_object(oot, 'gameplay_keep', rom_dir))
    positions, tiles, _owners, _locals = link.write_model(faces, dest, character=False)
    print('intact sign: %d points, %d faces, %d tiles, %d bytes' %
          (len(positions), len(faces), len(tiles), dest.stat().st_size))
    return len(positions), len(faces)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=pathlib.Path, default=link.OOT_DEFAULT)
    ap.add_argument('--rom-dir', type=pathlib.Path)
    ap.add_argument('--out', type=pathlib.Path,
                    default=pathlib.Path(__file__).resolve().parents[1] / 'build/cd/SIGNALL.BIN')
    args = ap.parse_args()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    build(args.oot, args.rom_dir, args.out)
