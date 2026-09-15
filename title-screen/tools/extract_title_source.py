#!/usr/bin/env python3
"""Prepare US 1.2 ROM segments for ZeldaRET's audio extractor.

Run this on Windows, then run the decomp's extract_audio.py under WSL.
Only the output directory is written; the decomp checkout remains read-only.
"""
import argparse
import csv
import hashlib
import re
import struct
from pathlib import Path


def yaz0(data):
    assert data[:4] == b"Yaz0"
    size = int.from_bytes(data[4:8], "big")
    out = bytearray()
    pos = 16
    while len(out) < size:
        flags = data[pos]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if flags & (1 << bit):
                out.append(data[pos])
                pos += 1
            else:
                a, b = data[pos:pos + 2]
                pos += 2
                count = a >> 4
                distance = ((a & 15) << 8 | b) + 1
                if count == 0:
                    count = data[pos] + 18
                    pos += 1
                else:
                    count += 2
                for _ in range(count):
                    out.append(out[-distance])
    assert len(out) == size
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--oot-root', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    config_dir = args.oot_root / 'baseroms/ntsc-1.2'
    candidates = [p for p in config_dir.glob('*.z64')
                  if hashlib.md5(p.read_bytes()).hexdigest() ==
                  '57a9719ad547c516342e1a15d5c28c3d']
    assert len(candidates) == 1, 'Expected exactly one verified compressed US 1.2 ROM'
    rom = candidates[0].read_bytes()
    config = (config_dir / 'config.yml').read_text()
    dma = int(re.search(r'dmadata_start: (\w+)', config)[1], 16)
    args.out.mkdir(parents=True, exist_ok=True)
    with (config_dir / 'segments.csv').open() as source:
        for i, row in enumerate(csv.DictReader(source)):
            name = row['Name']
            if name not in ('code', 'Audiobank', 'Audioseq', 'Audiotable'):
                continue
            start, end, physical, compressed_end = struct.unpack_from('>4I', rom, dma + i * 16)
            data = (yaz0(rom[physical:compressed_end]) if compressed_end
                    else rom[physical:physical + end - start])
            assert len(data) == end - start
            (args.out / name).write_bytes(data)
            print(name, len(data), hashlib.sha256(data).hexdigest())


if __name__ == '__main__':
    main()
