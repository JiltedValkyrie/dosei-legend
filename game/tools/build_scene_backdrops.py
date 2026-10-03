#!/usr/bin/env python
"""Stage the prerendered backdrops OoT uses for its interiors.

A room whose shape is ROOM_SHAPE_TYPE_IMAGE (decomp include/room.h) has no
display-list geometry worth speaking of. Instead the room header points at a
320x240 background image plus a tiny display list, and the camera is fixed so
the picture lines up. Link's house, the shop and the other Kokiri houses are
all built this way.

Two things make this a gift on the Saturn rather than a problem:

  * The image is 320x240 -- exactly the display's resolution -- so it needs no
    scaling and lands one pixel per pixel.
  * It goes to VDP2 as a scroll-screen bitmap, like the title artwork already
    does, so an interior costs NOTHING from the VDP1 texture budget. That
    matters: the tightest Kokiri Forest room bank leaves under 5 KB of VDP1
    VRAM spare, and an interior converted as geometry would never have fit.

The source is stored as ordinary JFIF JPEG inside the room segment, which is
why a raw read of it looks like noise. Pillow decodes it directly. Output is
the same big-endian RGB555 blob TITLE.RGB uses, so the runtime can stage it
through the path that already exists.
"""

import argparse
from vdp1_budget import bank_bytes
import io
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / 'shared/tools'))
import build_kokiri_scene as source
from build_scene_table import SCENES

from PIL import Image
import asset_names

WIDTH = 320
HEIGHT = 240


def rgb555(rgb):
    """Big-endian Saturn RGB555, matching build_demo_assets.py.

    Bit 15 marks a visible pixel; pure black is left fully clear so it reads as
    transparent, which is the convention the title artwork already uses.
    """
    r, g, b = rgb
    if not (r or g or b):
        return 0
    return 0x8000 | (b >> 3) << 10 | (g >> 3) << 5 | (r >> 3)


def room_backdrop(room, multi_first=False):
    """The JFIF image and its declared size from a ROOM_SHAPE_TYPE_IMAGE room.

    Header walk: room command 0x0A points at a RoomShapeImageSingle --
    type, amountType, entry, source, unk, tlut, width, height, fmt, siz, ...
    Only the SINGLE form is handled; a MULTI room (several backdrops selected
    by camera) raises rather than silently taking the first.
    """
    for offset in range(0, 0x400, 8):
        if room[offset] == 0x14:
            break
        if room[offset] != 0x0A:
            continue
        shape = int.from_bytes(room[offset + 4:offset + 8], 'big') & 0xFFFFFF
        kind, amount = room[shape], room[shape + 1]
        if kind != 1:
            raise ValueError('room shape %d is not ROOM_SHAPE_TYPE_IMAGE' % kind)
        if amount == 2 and multi_first:
            # RoomShapeImageMulti: numBackgrounds @8, backgrounds* @0xC;
            # RoomShapeImageMultiBgEntry (0x1C): bgCamIndex @2, source @4,
            # width/height @0x10. APPROXIMATE: first entry only; the real
            # room picks the entry whose bgCamIndex is the active bg camera.
            entries = int.from_bytes(room[shape + 12:shape + 16], 'big') & 0xFFFFFF
            start = int.from_bytes(room[entries + 4:entries + 8], 'big') & 0xFFFFFF
            width, height = struct.unpack_from('>2H', room, entries + 0x10)
            return room[start:], width, height
        if amount != 1:
            raise ValueError('multi-background rooms are not handled yet '
                             '(amountType %d)' % amount)
        start = int.from_bytes(room[shape + 8:shape + 12], 'big') & 0xFFFFFF
        width, height = struct.unpack_from('>2H', room, shape + 20)
        return room[start:], width, height
    raise ValueError('room has no mesh header')


def convert(data, width, height):
    """Decode the JPEG and pack it as big-endian RGB555."""
    image = Image.open(io.BytesIO(bytes(data)))
    image.load()
    if image.size != (width, height):
        raise ValueError('backdrop is %dx%d, header says %dx%d'
                         % (image.size[0], image.size[1], width, height))
    pixels = image.convert('RGB').getdata()
    return b''.join(struct.pack('>H', rgb555(p)) for p in pixels)


def main():
    here = pathlib.Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser()
    ap.add_argument('--cd', type=pathlib.Path, default=here / 'build/cd')
    ap.add_argument('--out', type=pathlib.Path, default=here / 'build/generated')
    ap.add_argument('--oot', type=pathlib.Path,
                    default=pathlib.Path((__import__('os').environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot')))
    ap.add_argument('--rom-dir', default=None)
    ap.add_argument('--png', action='store_true',
                    help='also write a PNG of each backdrop, to look at')
    args = ap.parse_args()

    args.cd.mkdir(parents=True, exist_ok=True)
    args.out.mkdir(parents=True, exist_ok=True)
    # z_vr_box.c: the five toggle-view houses. Bank 4 is the existing
    # panorama renderer; room identifies the gameplay interior, not collision.
    from build_opening_banks import house_panorama
    from build_room_scene import pack_room
    from build_sgl_scene import face_normal as normal
    # 2: SKYBOX_KOKIRI_SHOP (KSVR): two faces (Skybox_Calculate256 shop
    # range) turned by skyboxCtx->rot.y 0.8: the shop's browsing view
    # (Play_SetShopBrowsingViewpoint), never the player toggle.
    panoramas = {0: ('LHVR', 4), 2: ('KSVR', 2, 0.8), 3: ('KHVR', 4), 4: ('K3VR', 3),
                 5: ('K4VR', 3), 6: ('K5VR', 3)}
    for index, spec in panoramas.items():
        vertices, faces, tiles = house_panorama(args.oot, *spec)
        records = [dict(object=0, indices=list(f['idx'])) for f in faces]
        mesh, pixels, _ = pack_room(vertices, faces, tiles, records, normal)
        if bank_bytes(len(pixels), len(tiles)) > 140000:
            raise ValueError('Interior panorama exceeds reserved texture budget')
        for ext, blob in [('MSH', mesh), ('TEX', pixels)]:
            (args.cd / asset_names.room_asset(4, index, ext)).write_bytes(blob)
    staged = 0
    for index, entry in enumerate(SCENES):
        if entry['shape'] != 'image':
            continue
        segments = source.extract(args.oot, args.rom_dir, prefix=entry['prefix'],
                                  expect=entry['rooms'] + 1)
        for room_id in range(entry['rooms']):
            room = segments['%s_room_%d' % (entry['prefix'], room_id)]
            try:
                data, width, height = room_backdrop(room, multi_first=bool(entry.get("generic")))
            except ValueError as error:
                if not entry.get('generic'):
                    raise
                print('backdrop: %s room %d not staged: %s' % (entry['prefix'], room_id, error))
                continue
            if (width, height) != (WIDTH, HEIGHT) and entry.get('generic'):
                print('backdrop: %s room %d is %dx%d, not staged (runtime stages %dx%d)'
                      % (entry['prefix'], room_id, width, height, WIDTH, HEIGHT))
                continue
            if (width, height) != (WIDTH, HEIGHT):
                raise ValueError('%s room %d backdrop is %dx%d; the runtime '
                                 'stages %dx%d' % (entry['prefix'], room_id,
                                                   width, height, WIDTH, HEIGHT))
            blob = convert(data, width, height)
            assert len(blob) == WIDTH * HEIGHT * 2
            name = asset_names.room_asset(index, room_id, 'RGB')
            (args.cd / name).write_bytes(blob)
            staged += 1
            print('backdrop: %-10s room %d -> %s  %dx%d  %d bytes  '
                  '(JPEG source %d bytes)'
                  % (entry['prefix'], room_id, name, width, height, len(blob),
                     data.find(b'\xff\xd9') + 2))
            if args.png:
                image = Image.open(io.BytesIO(bytes(data)))
                image.convert('RGB').save(
                    args.out / ('S%dR%d_backdrop.png' % (index, room_id)))
    if not staged:
        print('backdrop: no image-shaped rooms in the scene table')


if __name__ == '__main__':
    main()
