"""Retain a pack's engine dependencies in the one authoritative resident core.

Uses exact SH ABI names. No engine object copying/weakening or runtime tables.
"""
import argparse
from pathlib import Path
import subprocess


def symbols(nm, paths):
    defined, undefined = set(), set()
    for path in paths:
        for line in subprocess.check_output([nm, '-g', str(path)], text=True).splitlines():
            parts = line.split()
            if len(parts) >= 2:
                kind, name = parts[-2:]
                if kind == 'U':
                    undefined.add(name)
                elif kind.upper() not in ('U', 'W', 'V'):
                    defined.add(name)
    return defined, undefined


def build(nm, pack, resident, output):
    definitions, imports = symbols(nm, pack)
    engine, _ = symbols(nm, resident)
    keep = sorted((imports - definitions) & engine)
    text = '/* Exact scene-pack engine dependencies; generated before core link. */\n'
    text += ''.join(f'EXTERN({name})\n' for name in keep)
    if not output.exists() or output.read_text() != text:
        output.write_text(text)
    print(f'Pack engine exports: {len(keep)} exact symbols')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--nm', required=True)
    p.add_argument('--pack', nargs='+', required=True)
    p.add_argument('--resident', nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    build(a.nm, a.pack, a.resident, a.out)
