#!/usr/bin/env python3
"""Compile original Water Temple prop actions using the existing Fx importer.

This isolated probe cannot stage an actor or overwrite the playable disc.
Unresolved engine/Player/scene interfaces remain explicit link prerequisites.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess

import oot_core_import as imp
import water_temple_sources as water
from build_actor_packs import Elf32
from build_pack_exports import symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--out', type=Path, default=Path('build/water-temple'))
    parser.add_argument('--all', action='store_true', help='also compile enemy/support inventory, not runtime admission')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
    flags = shlex.split(os.environ['OOT_CORE_CXXFLAGS'])
    results = []
    names = water.PROPS + water.ENEMIES + water.SUPPORT if args.all else water.PROPS
    sources = water.PROP_SOURCES + water.ENEMY_SOURCES + water.SUPPORT_SOURCES if args.all else water.PROP_SOURCES
    for name, rel in zip(names, sources):
        source = args.oot / rel
        target = args.out / source.stem
        target.mkdir(exist_ok=True)
        cpp = target / source.with_suffix('.cpp').name
        cpp.write_text(imp.fixup(rel, source.read_text(), stats))
        header = source.with_suffix('.h')
        (target / header.name).write_text(imp.fixup(str(Path(rel).with_suffix('.h')), header.read_text(), stats))
        obj = target / source.with_suffix('.o').name
        own_headers = Path('build/oot-core/decomp') / Path(rel).parent
        run = subprocess.run([args.cxx, *flags, '-I' + str(own_headers), '-m2', '-Os', '-ffunction-sections',
                              '-fdata-sections', '-fno-threadsafe-statics', '-fno-use-cxa-atexit',
                              '-c', str(cpp), '-o', str(obj)], text=True, capture_output=True)
        (target / 'compile.log').write_text(run.stdout + run.stderr)
        results.append(dict(actor=name, source=rel, compiled=run.returncode == 0,
                            object=str(obj), error=run.stderr if run.returncode else ''))
        print(name, 'compiled' if run.returncode == 0 else run.stderr[:500], flush=True)
    objects = [r['object'] for r in results if r['compiled']]
    nm = str(Path(args.cxx).with_name('sh-elf-nm'))
    definitions, imports = symbols(nm, objects)
    resident, _ = symbols(nm, [Path('build/oot-core/oot-core.elf')])
    engine, _ = symbols(nm, list(Path('build/obj-clean/oot-core').glob('*.o')))
    dependencies = sorted(imports - definitions)
    text_bytes = sum(s[5] for path in objects for s in Elf32(path).sections if s[2] & 4)
    report = dict(source_scene=5, runtime_scene=79, staged=False, actors=results,
                  unlinked_text_bytes=text_bytes,
                  resident_exports=[s for s in dependencies if s in resident],
                  additional_engine_exports=[s for s in dependencies if s not in resident and s in engine],
                  unresolved=[s for s in dependencies if s not in resident and s not in engine],
                  importer_problems=stats['problems'])
    (args.out / ('all.json' if args.all else 'props.json')).write_text(json.dumps(report, indent=2) + '\n')
    raise SystemExit(any(not r['compiled'] for r in results) or bool(stats['problems']))


if __name__ == '__main__':
    main()
