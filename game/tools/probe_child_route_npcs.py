#!/usr/bin/env python3
"""Compile the route NPC sources in isolation, without staging a game image."""
import argparse
import json
import re
from pathlib import Path
import subprocess

import child_route_npcs as route
import oot_core_import as imp
from build_pack_exports import symbols


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--cxx', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=Path('build/child-route-npcs'))
    parser.add_argument('--sprites', action='store_true', help='also bake route sprites into the isolated output')
    parser.add_argument('--sprite-object', action='append', help='limit the isolated bake to one object (repeatable)')
    parser.add_argument('--shops', action='store_true', help='compile source keeper, stock and shelf actors')
    parser.add_argument('--ranch', action='store_true', help='compile source child Epona and normal horses')
    parser.add_argument('--common', action='store_true', help='compile common child Market/Kakariko NPCs')
    parser.add_argument('--rewards', action='store_true', help='compile child reward NPCs')
    parser.add_argument('--masks', action='store_true', help='compile child mask customers')
    parser.add_argument('--minigames', action='store_true', help='compile child minigame actors and managers')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    flags = ('-x c++ -std=gnu++17 -fno-exceptions -fno-rtti -fpermissive -funsigned-char -w '
             '-fno-threadsafe-statics -fno-use-cxa-atexit -Os -m2 -ffunction-sections -fdata-sections '
             '-include oot_prelude.h -DPLATFORM_N64=1 -DPLATFORM_GC=0 -DPLATFORM_IQUE=0 '
             '-DOOT_VERSION=NTSC_1_2 -DOOT_REVISION=2 -DOOT_REGION=REGION_US '
             '-DLIBULTRA_VERSION=LIBULTRA_VERSION_I -DLIBULTRA_PATCH=1 -DDEBUG_FEATURES=0 '
             '-DNDEBUG -DF3DEX_GBI_2 -DNON_MATCHING -DAVOID_UB -D_LANGUAGE_C '
             '-D_MIPS_SZLONG=32 -D_MIPS_SZINT=32 -D_MIPS_SZPTR=32 -nostdinc').split()
    generated = Path('build/oot-core/decomp')
    flags += ['-I' + str(p) for p in (args.out / 'decomp/src', Path('oot-core/shim'),
              Path('oot-core/include'), generated / 'include', generated / 'include/libc',
              generated / 'src', generated, args.oot / 'extracted/ntsc-1.2', args.oot)]
    stats = dict(macros=0, fxl=0, anon=0, mtxf=0, files=0, written=0, problems=[])
    imported = 'child_route_npcs.adapt' in Path(imp.__file__).read_text()
    actors, sources = route.ACTORS + route.GATE_ACTORS, route.SOURCES + route.GATE_SOURCES
    adapter = route
    if args.shops:
        import child_route_shops as adapter
        actors, sources = adapter.ACTORS, adapter.SOURCES
        imported = 'child_route_shops.adapt' in Path(imp.__file__).read_text()
    if args.ranch:
        import ranch_sources as adapter
        actors, sources = adapter.ACTORS + adapter.EXISTING_NPCS, adapter.SOURCES + adapter.EXISTING_SOURCES
        imported = 'ranch_sources.adapt' in Path(imp.__file__).read_text()
    if args.common:
        import child_common_npcs as adapter
        actors, sources = adapter.ACTORS, adapter.SOURCES
        imported = 'child_common_npcs.adapt' in Path(imp.__file__).read_text()
    if args.rewards:
        import child_reward_npcs as adapter
        actors, sources = adapter.ACTORS, adapter.SOURCES
        imported = 'child_reward_npcs.adapt' in Path(imp.__file__).read_text()
    if args.masks:
        import child_mask_sources as adapter
        actors, sources = adapter.ACTORS, adapter.SOURCES
        imported = 'child_mask_sources.adapt' in Path(imp.__file__).read_text()
    if args.minigames:
        import child_minigame_sources as adapter
        actors, sources = adapter.ACTORS, adapter.SOURCES
        imported = 'child_minigame_sources.adapt' in Path(imp.__file__).read_text()
    results = []
    for name, rel in zip(actors, sources):
        original = args.oot / rel
        cpp = args.out / 'decomp' / Path(rel).with_suffix('.cpp')
        cpp.parent.mkdir(parents=True, exist_ok=True)
        for path, dest in ((original, cpp), (original.with_suffix('.h'), cpp.with_suffix('.h'))):
            relative = path.relative_to(args.oot).as_posix()
            text = path.read_text(encoding='utf-8')
            if not imported:
                text = adapter.adapt(relative, text)
            dest.write_text(imp.fixup(relative, text, stats))
        # Source cross-actor layouts must use current importer adapters too,
        # even before a concurrent complete core import has regenerated them.
        pending = re.findall(r'#include "(overlays/actors/[^"\n]+\.h)"', original.read_text(encoding='utf-8'))
        seen = set()
        while pending:
            header = pending.pop()
            if header in seen: continue
            seen.add(header)
            original_header = args.oot / 'src' / header
            header_text = original_header.read_text(encoding='utf-8')
            pending += re.findall(r'#include "(overlays/actors/[^"\n]+\.h)"', header_text)
            dest_header = args.out / 'decomp/src' / header
            dest_header.parent.mkdir(parents=True, exist_ok=True)
            dest_header.write_text(imp.fixup('src/' + header, header_text, stats))
        obj = cpp.with_suffix('.o')
        run = subprocess.run([str(args.cxx), *flags, '-c', str(cpp), '-o', str(obj)],
                             text=True, capture_output=True)
        cpp.with_suffix('.log').write_text(run.stdout + run.stderr)
        results.append(dict(actor=name, compiled=run.returncode == 0, object=str(obj),
                            error=run.stderr if run.returncode else ''))
        print(name, 'compiled' if run.returncode == 0 else run.stderr[:1000], flush=True)
    if args.ranch:
        for name in ('bridge_ranch', 'ranch_horse_sprite'):
            obj = args.out / (name + '.o')
            run = subprocess.run([str(args.cxx), *flags, '-c', 'oot-core/src/' + name + '.cpp', '-o', str(obj)],
                                 text=True, capture_output=True)
            obj.with_suffix('.log').write_text(run.stdout + run.stderr)
            results.append(dict(actor=name, compiled=run.returncode == 0, object=str(obj),
                                error=run.stderr if run.returncode else ''))
            print(name, 'compiled' if run.returncode == 0 else run.stderr[:1000], flush=True)
    nm = args.cxx.with_name(args.cxx.name.replace('g++', 'nm'))
    definitions, imports = symbols(str(nm), [r['object'] for r in results if r['compiled']])
    resident_elf = Path('build/oot-core/oot-core.elf')
    resident, _ = symbols(str(nm), [resident_elf] if resident_elf.exists() else [])
    engine, _ = symbols(str(nm), list(Path('build/obj-clean/oot-core').glob('*.o')))
    report = dict(actors=results, importer_problems=stats['problems'],
                  additional_engine_exports=sorted((imports - definitions - resident) & engine),
                  dependencies_not_in_current_core=sorted(imports - definitions - resident - engine))
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    if args.sprites:
        import build_npc_sprites as sprites
        work, sheets = args.out / 'sprite-work', args.out / 'sprites'
        work.mkdir(exist_ok=True)
        sheets.mkdir(exist_ok=True)
        sprites.bake_generic(args.oot, args.oot / 'baseroms/ntsc-1.2', work, sheets,
                             args.out, only_objects=args.sprite_object or route.OBJECTS)
    raise SystemExit(any(not r['compiled'] for r in results) or bool(stats['problems']))


if __name__ == '__main__':
    main()
