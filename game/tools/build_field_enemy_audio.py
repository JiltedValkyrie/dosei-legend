#!/usr/bin/env python3
"""Render the complete Field actor SFX set into the existing area reservation."""
import argparse
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

import build_enemy_audio as enemy
import build_enemy_roster as roster
import field_enemy_sources as field


def build(oot, source, generated, cd):
    table = roster.sfx_table(oot)
    groups = []
    for sources in (field.SOURCES[:3], field.SOURCES[3:]):
        text = '\n'.join((oot / p).read_text() for p in sources + field.EFFECT_SOURCES)
        symbols = set(re.findall(r'\bNA_SE_[A-Z0-9_]+\b', text))
        groups.append(symbols)
    records = [dict(symbol=s, **table[s]) for s in sorted(set.union(*groups))]
    seq = (oot / 'assets/audio/sequences/seq_0.prg.seq').read_text()
    fonts = {i: ET.parse(source / f'soundfonts/Soundfont_{i}.xml') for i in (0, 1)}
    # Held sounds retain one complete loop pass, repeated by the host while
    # source requests continue. One-shots keep their complete rendered tails.
    samples = {r['id']: enemy.audio.render_channel(seq, r['channel'], fonts, source,
                                                  enemy.RATE, once=True) for r in records}
    limit = json.loads((generated / 'action_audio.json').read_text())['area_limit']
    reports, rows = [], []
    for age, symbols in enumerate(groups):
        for stride, octave in ((1, 13), (2, 12), (4, 11)):
            bank, entries = bytearray(), []
            for symbol in sorted(symbols, key=lambda s: table[s]['id']):
                sid = table[symbol]['id']
                offset, length = enemy.append_sample(bank, samples[sid][::stride])
                entries.append((sid, offset, length, octave))
            if len(bank) <= limit:
                break
        else:
            raise ValueError(f'Field age {age}: {len(bank)} exceeds area limit {limit}')
        name = ('FLDCHILD.PCM', 'FLDADULT.PCM')[age]
        (cd / name).write_bytes(bank)
        rows.append(entries)
        reports.append(dict(file=name, bytes=len(bank), rate=enemy.RATE / stride,
                            area_limit=limit, symbols=sorted(symbols)))
    lines = ['/* Generated complete Field SFX banks; existing area RAM only. */',
             'typedef struct { unsigned short id, offset, length, octave; } field_sfx_t;']
    for age, entries in enumerate(rows):
        lines.append(f'static const field_sfx_t field_sfx_{age}[] = {{')
        lines.extend('    {0x%04x, %d, %d, %d},' % row for row in entries)
        lines.append('};')
    lines += ['static const field_sfx_t *const field_sfx_rows[] = {field_sfx_0, field_sfx_1};',
              'static const unsigned field_sfx_count[] = {%d, %d};' % tuple(map(len, rows)),
              'static const unsigned field_sfx_bytes[] = {%d, %d};' % tuple(r['bytes'] for r in reports),
              'static const char *const field_sfx_file[] = {"FLDCHILD.PCM", "FLDADULT.PCM"};']
    (generated / 'field_audio_data.h').write_text('\n'.join(lines) + '\n')
    (generated / 'field_audio.json').write_text(json.dumps(reports, indent=2) + '\n')
    print(json.dumps(reports, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('../shared/build/audio-source/extracted/assets/audio'))
    parser.add_argument('--generated', type=Path, default=Path('build/generated'))
    parser.add_argument('--cd', type=Path, default=Path('build/cd'))
    args = parser.parse_args()
    build(args.oot, args.source, args.generated, args.cd)
