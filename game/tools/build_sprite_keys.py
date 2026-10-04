"""Resolve sprite animation keys from the same linked objects as oot-core."""
import argparse
import json
from pathlib import Path
import re


def resolve(rows, symbols):
    addresses = dict((name.lstrip('_'), int(address, 16)) for name, address in
                     re.findall(r'(\w+)\s*=\s*0x([\da-fA-F]+);', symbols))
    lines = ['/* Generated from linked object symbols; never use ROM offsets. */']
    for oid, limbs, name, file in rows:
        address = addresses[name]  # Missing animation is a build error.
        if address >> 24 != 6:
            raise ValueError('sprite animation outside object segment: ' + name)
        lines.append('    { 0x%03X, %d, 0x%06X, 0x%02X }, /* %s */' %
                     (oid, limbs, address & 0xFFFFFF, file, name))
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('rows', type=Path)
    ap.add_argument('symbols', type=Path)
    ap.add_argument('out', type=Path)
    args = ap.parse_args()
    args.out.write_text(resolve(json.loads(args.rows.read_text()), args.symbols.read_text()))
