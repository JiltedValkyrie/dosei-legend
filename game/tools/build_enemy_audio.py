#!/usr/bin/env python3
"""Build scene enemy SFX libraries and room copy maps, with explicit admission.

PCM8 is rendered offline at 5512.5 Hz using the existing reduced OoT renderer.
Unsupported source sequencing is a named failure, never a silent omission.
Generated libraries are groundwork: no runtime enemy bank loader is enabled.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import build_action_audio as audio
import build_enemy_roster as roster_tool
import oot_core_import as imp

GAME = Path(__file__).resolve().parents[1]
RATE = 5512.5


def append_sample(bank, pcm):
    if not pcm or len(pcm) > 65535:
        raise ValueError('empty or over-65535-byte SFX sample')
    bank.extend(bytes(-len(bank) % 2))
    offset = len(bank)
    bank.extend(pcm)
    bank.extend(bytes(4 + (-len(bank) % 2)))
    return offset, len(pcm)


def library(scene, samples, area_limit, cart_limit, retained_area_bytes):
    """Budget every room including the existing area bank and quiet guards.

    samples maps source sfx id to half-rate PCM8. Deduplicate sample bytes in
    the scene library; room slots stay sorted by id for generated lookup.
    """
    if not (0 <= retained_area_bytes <= area_limit and cart_limit > 0):
        raise ValueError('invalid area/cart reservation')
    wanted = sorted({sid for room in scene['rooms'] for sid in room['sfx_ids']})
    missing = [sid for sid in wanted if sid not in samples]
    if missing:
        raise ValueError('missing SFX: ' + ', '.join('0x%04X' % sid for sid in missing))
    payload, dedup, records = bytearray(), {}, []
    for sid in wanted:
        pcm = samples[sid]
        if pcm not in dedup:
            dedup[pcm] = append_sample(payload, pcm)
        offset, length = dedup[pcm]
        records.append({'id': sid, 'offset': offset, 'length': length, 'rate': RATE})
    header_bytes = 16 + len(records) * 12
    blob = bytearray(struct.pack('>4sHHII', b'ESF1', 1, len(records), header_bytes, header_bytes + len(payload)))
    for row in records:
        row['offset'] += header_bytes
        blob.extend(struct.pack('>HHII', row['id'], 13, row['offset'], row['length']))
    blob.extend(payload)
    if len(blob) > cart_limit:
        raise ValueError('%s scene SFX %d exceeds cart reservation %d' % (scene['prefix'], len(blob), cart_limit))
    by_id = {row['id']: row for row in records}
    rooms = []
    for room in scene['rooms']:
        # Existing sounds retain their exact region at the beginning.
        bank = bytearray(retained_area_bytes)
        rows = []
        for sid in sorted(set(room['sfx_ids'])):
            offset, length = append_sample(bank, samples[sid])
            rows.append({'id': sid, 'slot': len(rows), 'library_offset': by_id[sid]['offset'],
                         'sound_offset': offset, 'length': length, 'octave': 13})
        if len(bank) > area_limit:
            names = ', '.join('0x%04X=%d' % (r['id'], r['length']) for r in rows)
            raise ValueError('%s/%s/layer%d sound RAM %d > %d; retained=%d; %s' %
                             (scene['prefix'], room['room'], room['layer'], len(bank), area_limit,
                              retained_area_bytes, names))
        rooms.append({'room': room['room'], 'layer': room['layer'], 'sound_bytes': len(bank), 'slots': rows})
    report = {'scene': scene['prefix'], 'file': 'E%03X.ESF' % scene['id'],
              'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest(),
              'cart_limit': cart_limit, 'area_limit': area_limit, 'retained_area_bytes': retained_area_bytes,
              'samples': records, 'rooms': rooms,
              'runtime_loader_implemented': False,
              'limitations': 'reduced source sequencing; no vibrato/reverb; no runtime admission implied'}
    return bytes(blob), report


def room_header(report):
    lines = ['/* Generated room source-id -> library/sound RAM slot mapping. */',
             'typedef struct { unsigned short id, length; unsigned int source, destination; } enemy_sfx_copy_t;']
    for index, room in enumerate(report['rooms']):
        lines.append('static const enemy_sfx_copy_t enemy_sfx_room_%d[] = {' % index)
        for row in room['slots']:
            lines.append('    {0x%04X, %d, %d, %d},' %
                         (row['id'], row['length'], row['library_offset'], row['sound_offset']))
        lines.append('    {0, 0, 0, 0} };')
    return '\n'.join(lines) + '\n'


def render(oot, source, records):
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text(encoding='utf-8')
    fonts = {i: ET.parse(source / ('soundfonts/Soundfont_%d.xml' % i)) for i in (0, 1)}
    samples, failures = {}, []
    for record in records:
        try:
            samples[record['id']] = audio.render_channel(seq, record['channel'], fonts, source, RATE)
        except (audio.Unsupported, ValueError, IndexError, KeyError, AttributeError, FileNotFoundError) as exc:
            failures.append({'symbol': record['symbol'], 'id': record['id'],
                             'channel': record['channel'], 'reason': str(exc)})
    return samples, failures


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--source', type=Path, default=GAME.parent / 'shared/build/audio-source/extracted/assets/audio')
    parser.add_argument('--roster', type=Path, default=GAME / 'docs/ENEMY_ROSTER.json')
    parser.add_argument('--action-audio', type=Path, default=GAME / 'build/generated/action_audio.json')
    parser.add_argument('--out', type=Path, default=GAME / 'build/generated/enemy-audio')
    parser.add_argument('--scene', action='append', required=True)
    parser.add_argument('--cart-budget', type=int, required=True)
    parser.add_argument('--retained-area-bytes', type=int,
                        help='Existing area reservation; defaults to largest built area bank, never zero by assumption')
    args = parser.parse_args()
    roster = json.loads(args.roster.read_text(encoding='utf-8'))
    base = json.loads(args.action_audio.read_text(encoding='utf-8'))
    by_scene = {s['prefix']: s for s in roster['scenes']}
    missing = set(args.scene) - by_scene.keys()
    if missing:
        raise SystemExit('unknown scene: ' + ', '.join(sorted(missing)))
    selected = [by_scene[s] for s in args.scene]
    wanted = {sid for scene in selected for room in scene['rooms'] for sid in room['sfx_ids']}
    table = roster_tool.sfx_table(args.oot)
    records = sorted((dict(symbol=symbol, **record) for symbol, record in table.items()
                      if record['id'] in wanted), key=lambda row: row['id'])
    samples, failures = render(args.oot, args.source, records)
    args.out.mkdir(parents=True, exist_ok=True)
    if failures:
        (args.out / 'unsupported.json').write_text(json.dumps(failures, indent=2) + '\n', encoding='utf-8')
        raise SystemExit('unsupported SFX; no library published: ' + ', '.join(row['symbol'] for row in failures))
    reserve = (args.retained_area_bytes if args.retained_area_bytes is not None
               else max(bank['bytes'] for bank in base['area_banks']))
    # Complete all validations before publishing any requested library.
    outputs, admission_failures = [], []
    for scene in selected:
        try:
            outputs.append(library(scene, samples, base['area_limit'], args.cart_budget, reserve))
        except ValueError as exc:
            admission_failures.append({'scene': scene['prefix'], 'reason': str(exc)})
    if admission_failures:
        (args.out / 'admission_failures.json').write_text(json.dumps(admission_failures, indent=2) + '\n', encoding='utf-8')
        raise SystemExit('enemy SFX admission blocked; no library published:\n' +
                         '\n'.join(row['reason'] for row in admission_failures))
    for blob, report in outputs:
        path = args.out / report['file']
        path.write_bytes(blob)
        path.with_suffix('.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        path.with_suffix('.h').write_text(room_header(report), encoding='utf-8')
        print('%s: %d bytes, %d SFX' % (report['file'], len(blob), len(report['samples'])))


if __name__ == '__main__':
    main()
