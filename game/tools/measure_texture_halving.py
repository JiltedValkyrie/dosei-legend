"""Snapshot staged texture bytes and compare an opt-in density build."""
import argparse
import csv
import hashlib
import json
import re
import statistics
import struct
from pathlib import Path

from vdp1_budget import (VDP1_USER_AREA, bank_bytes, tile_bytes,
                         RUNTIME_SPRITE_BYTES, FOREST_ACTOR_BYTES)
from build_sgl_scene import link_actor_budget

ROOT = Path(__file__).resolve().parents[1]


def snapshot():
    files = {}
    for folder in ('generated', 'cd'):
        for path in sorted((ROOT / 'build' / folder).iterdir()):
            if path.suffix not in ('.TEX', '.MSH', '.STM') and path.name not in (
                    'LINK.BIN', 'ADULT.BIN', 'ADLTTEX.BIN', 'LGEARTEX.BIN'):
                continue
            data = path.read_bytes()
            row = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
            if data[:4] == b'KRM1':
                _, vertices, faces, tiles, pixels, *_ = struct.unpack_from('>8I', data)
                row.update(tiles=tiles, pixels=pixels, bank_bytes=bank_bytes(pixels, tiles))
            elif data[:4] == b'KRM2':
                header = struct.unpack_from('>16I', data)
                row.update(tiles=header[3], pixels=header[4])
            files[folder + '/' + path.name] = row
    return files


def compare(before, after):
    rooms = []
    retired_path = ROOT / 'build/generated/obsolete_image_banks.json'
    retired = {row['file'] for row in json.loads(retired_path.read_text())} if retired_path.exists() else set()
    link = link_actor_budget(ROOT / 'build/generated/LINK.BIN')
    link_reserve = sum(tile_bytes(w, h) for w, h in link['tiles'])
    residents = link_reserve + RUNTIME_SPRITE_BYTES + FOREST_ACTOR_BYTES
    for name, row in before.items():
        if not re.fullmatch(r'cd/[SZC][0-9A-Z]+R[0-9A-Z]+\.TEX', name):
            continue
        mesh = name[:-3] + 'MSH'
        filename = name.split('/')[-1]
        removed = name not in after
        if (removed and filename not in retired) or (not removed and mesh not in after):
            raise ValueError('Missing rebuilt room: ' + name)
        old = before[mesh]['bank_bytes']
        new = 0 if removed else after[mesh]['bank_bytes']
        rooms.append(dict(file=filename, status='obsolete_image_bank_removed' if removed else 'active',
                          before=row['bytes'], after=0 if removed else after[name]['bytes'],
                          bank_before=old, bank_after=new, area_free=VDP1_USER_AREA-new,
                          free_after_residents=VDP1_USER_AREA-new-residents))
    active = [r for r in rooms if r['status'] == 'active']
    return dict(texture_area=VDP1_USER_AREA, room_count=len(rooms), rooms=rooms,
                active_room_count=len(active), retired_room_count=len(rooms)-len(active),
                link_reserve=link_reserve, runtime_sprites=RUNTIME_SPRITE_BYTES,
                actor_reserve=FOREST_ACTOR_BYTES,
                minimum_free_after_residents=min(r['free_after_residents'] for r in rooms),
                room_tex_before=sum(r['before'] for r in rooms),
                room_tex_after=sum(r['after'] for r in rooms),
                worst_tex_before=max(r['before'] for r in active),
                worst_tex_after=max(r['after'] for r in active),
                median_tex_before=statistics.median(r['before'] for r in active),
                median_tex_after=statistics.median(r['after'] for r in active),
                worst_bank_before=max(r['bank_before'] for r in active),
                worst_bank_after=max(r['bank_after'] for r in active),
                median_bank_before=statistics.median(r['bank_before'] for r in active),
                median_bank_after=statistics.median(r['bank_after'] for r in active),
                navipool_before=before['generated/NAVIPOOL.TEX']['bytes'],
                navipool_after=after['generated/NAVIPOOL.TEX']['bytes'],
                staged_tex_before=sum(r['bytes'] for n, r in before.items() if n.startswith('cd/') and n.endswith('.TEX')),
                staged_tex_after=sum(r['bytes'] for n, r in after.items() if n.startswith('cd/') and n.endswith('.TEX')))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--before', type=Path)
    args = ap.parse_args()
    result = snapshot()
    if args.before:
        result = compare(json.loads(args.before.read_text()), result)
        field_before = args.before.parent / 'field-before.json'
        field_after = ROOT / 'build/generated/field_stream_report.json'
        if field_before.exists() and field_after.exists():
            a, b = json.loads(field_before.read_text()), json.loads(field_after.read_text())
            result['field_vram_before'] = a['vram_total']
            result['field_vram_after'] = b['vram_total']
            result['field_free_after'] = VDP1_USER_AREA - b['vram_total']
            if b.get('texture_halving'):
                result['field_pixels_before'] = b['texture_halving']['before']
                result['field_pixels_after'] = b['texture_halving']['after']
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    if args.before:
        with args.out.with_suffix('.csv').open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(result['rooms'][0]))
            writer.writeheader()
            writer.writerows(result['rooms'])
        print(json.dumps({k: v for k, v in result.items() if k != 'rooms'}, indent=2))
