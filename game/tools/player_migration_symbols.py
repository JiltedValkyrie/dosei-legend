#!/usr/bin/env python3
"""Symbol/size audit of the staged SH-2 Player objects against the live core.

Reads `nm` of build/player-migration/sh2/*.o, the live core objects
(build/obj-clean/oot-core by default) and oot-core.elf. Writes symbols.json:
duplicate definitions (live owners to retire), unresolved references (missing
Saturn backend/dependency work) and size versus the cart carve headroom.
Audit only: nothing is linked, and the live blob is not changed.
"""
import argparse
import json
import re
import subprocess
import hashlib
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent
CARVE_BYTES = 0x90000          # makefile OOT_CORE_MAX_BYTES
LOAD_ADDR = 0x02770000         # makefile OOT_CORE_LOAD_ADDR
DEFINED = set('TDBRGSCWV')
WEAK = set('WV')  # inline copies merge at link: resolve, never duplicate
LIBGCC = re.compile(r'^_{2,3}(ashiftrt_r4_\d+|ashrsi3|ashlsi3|lshrsi3|movmem\w*|sdivsi3\w*|udivsi3\w*|mulsi3|clzsi2)$')
BUCKETS = (
    ('player_animations', re.compile(r'^_gPlayerAnim_')),
    ('link_draw_assets', re.compile(r'^_g(Link|EffIce|HoverBoots)')),
    ('tables', re.compile(r'^_g[A-Z]')),
)


def nm(tool, path):
    out = subprocess.run([tool, '-S', str(path)], capture_output=True,
                         text=True, check=True).stdout
    defined, undefined = {}, set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] == 'U':
            undefined.add(parts[1])
        elif len(parts) >= 3 and parts[-2] in DEFINED:
            size = int(parts[1], 16) if len(parts) == 4 else 0
            defined[parts[-1]] = parts[-2] in WEAK
    return defined, undefined


def section_sizes(tool, path):
    out = subprocess.run([tool, str(path)], capture_output=True, text=True,
                         check=True).stdout.splitlines()
    text, data, bss = (int(v) for v in out[1].split()[:3])
    return dict(text=text, data=data, bss=bss, total=text + data + bss)


def measure_gc(objdir, live_dir, ld, tools, output):
    """Relocatable section-GC probe, NOT a resolved or runnable link.

    Retain every Player service referenced by current core objects. The second
    case excludes the profile/call wrapper and roots gameplay entry points to
    estimate a future Saturn draw adapter; it is not permission to omit Draw's
    gameplay side effects. Unresolved dependencies remain unresolved.
    """
    objects = [objdir / (name + '.o') for name in
               ('z_player', 'z_player_lib', 'z_player_call')]
    definitions, required = set(), set()
    for path in objects:
        defined, _ = nm(tools['nm'], path)
        definitions.update(defined)
    live = sorted(live_dir.glob('*.o'))
    if not live:
        raise ValueError(f'no live objects: {live_dir}')
    for path in live:
        _, undefined = nm(tools['nm'], path)
        required.update(undefined & definitions)
    def entry(name):
        # Header-declared services have C linkage; overlay-local entry points
        # have C++ linkage. Match the complete Actor*/PlayState* signature.
        matches = definitions & {'_' + name, f'__Z{len(name)}{name}P5ActorP9PlayState'}
        if len(matches) != 1:
            raise ValueError(f'expected one {name} entry, found {sorted(matches)}')
        return next(iter(matches))
    gameplay = {entry('Player_Init'), entry('Player_Update'), entry('Player_Destroy')}
    draw = entry('Player_Draw')
    output.mkdir(parents=True, exist_ok=True)
    results = {}
    for name, inputs, roots in (
        ('source_profile', objects, required | {'_Player_Profile'}),
        ('gameplay_roots', objects[:2],
         (required - {'_Player_Profile'}) |
         gameplay),
    ):
        available = set()
        for path in inputs:
            available.update(nm(tools['nm'], path)[0])
        if not roots <= available:
            raise ValueError(f'{name}: missing roots {sorted(roots - available)}')
        target = output / (name + '.o')
        subprocess.run([ld, '-r', '--gc-sections',
                        *['--undefined=' + s for s in sorted(roots)],
                        '-Map=' + str(output / (name + '.map')),
                        '-o', str(target), *map(str, inputs)], check=True)
        kept, unresolved = nm(tools['nm'], target)
        if not roots <= set(kept):
            raise ValueError(f'{name}: linker dropped a required root')
        results[name] = dict(roots=sorted(roots), sizes=section_sizes(tools['size'], target),
                             unresolved_count=len(unresolved),
                             player_draw_retained=draw in kept,
                             sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    return dict(status='relocatable GC estimates only; unresolved dependencies excluded',
                inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in objects + live}, cases=results)


def low_ram_gaps(header):
    """Static unassigned spans only, never runtime heap-free measurements."""
    source = header.read_text(encoding='utf-8')
    values = {name: int(value, 0) for name, value in re.findall(
        r'^#define\s+(RAM_LOW_\w+)\s+(0x[0-9A-Fa-f]+|[0-9]+)u?\b', source, re.M)}
    spans = []
    for name, offset in values.items():
        if name.endswith('_OFFSET'):
            size_name = name[:-7] + '_BYTES'
            if size_name not in values:
                raise ValueError(f'nonliteral/missing size: {size_name}')
            spans.append((offset, offset + values[size_name], name[:-7]))
    gaps, end = [], 0
    for start, stop, name in sorted(spans):
        if start < end or stop > values['RAM_LOW_BYTES']:
            raise ValueError(f'overlap/out-of-range low RAM carve: {name}')
        if start > end:
            gaps.append(dict(address=hex(values['RAM_LOW_ADDRESS'] + end), bytes=start - end))
        end = stop
    if end < values['RAM_LOW_BYTES']:
        gaps.append(dict(address=hex(values['RAM_LOW_ADDRESS'] + end),
                         bytes=values['RAM_LOW_BYTES'] - end))
    return dict(status='header-unassigned spans, not allocated or runtime-validated',
                gaps=gaps, total_bytes=sum(g['bytes'] for g in gaps),
                header_sha256=hashlib.sha256(header.read_bytes()).hexdigest())


def audit(objdir, live_dir, elf, tools):
    player = sorted(objdir.glob('*.o'))
    if not player:
        raise SystemExit(f'no staged SH-2 Player objects in {objdir}')
    live = sorted(live_dir.glob('*.o'))
    live_defs, live_strong, player_strong = {}, set(), set()
    for path in live:
        defined, _ = nm(tools['nm'], path)
        for sym, weak in defined.items():
            live_defs.setdefault(sym, []).append(path.name)
            if not weak:
                live_strong.add(sym)
    player_defs, player_undef, sizes = {}, set(), {}
    for path in player:
        defined, undefined = nm(tools['nm'], path)
        for sym, weak in defined.items():
            player_defs.setdefault(sym, []).append(path.name)
            if not weak:
                player_strong.add(sym)
        player_undef |= undefined
        sizes[path.name] = section_sizes(tools['size'], path)
    duplicates = {sym: dict(player=player_defs[sym], live=live_defs[sym])
                  for sym in sorted(player_strong & live_strong)}
    unresolved = sorted(s for s in player_undef - set(player_defs) - set(live_defs)
                        if not LIBGCC.match(s))
    buckets = {name: [] for name, _ in BUCKETS}
    buckets['engine_functions'] = []
    for sym in unresolved:
        name = next((n for n, pat in BUCKETS if pat.match(sym)), 'engine_functions')
        buckets[name].append(sym)
    end = None
    out = subprocess.run([tools['nm'], str(elf)], capture_output=True,
                         text=True, check=True).stdout
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in ('_oot_core_end', 'oot_core_end'):
            end = int(parts[0], 16)
    used = end - LOAD_ADDR if end is not None else None
    player_total = sum(s['total'] for s in sizes.values())
    headroom = CARVE_BYTES - used if used is not None else None
    return dict(
        status='audit only; Player objects not linked into the live blob',
        live_objects=str(live_dir), live_object_count=len(live),
        player_sizes=sizes, player_total_bytes=player_total,
        carve_bytes=CARVE_BYTES, live_blob_bytes=used, carve_headroom_bytes=headroom,
        fits_upper_bound=(headroom is not None and player_total <= headroom),
        duplicates=duplicates,
        unresolved_counts={k: len(v) for k, v in buckets.items()},
        unresolved=buckets,
        note='Sizes are pre --gc-sections upper bounds; duplicates must be '
             'retired from the live owner, never suppressed.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--objdir', type=Path, default=GAME / 'build/player-migration/sh2')
    parser.add_argument('--live', type=Path, default=GAME / 'build/obj-clean/oot-core')
    parser.add_argument('--elf', type=Path, default=GAME / 'build/oot-core/oot-core.elf')
    parser.add_argument('--nm', default='sh-elf-nm')
    parser.add_argument('--size', default='sh-elf-size')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/symbols.json')
    parser.add_argument('--gc-ld', help='optional SH-2 ld for isolated relocatable GC estimates')
    args = parser.parse_args()
    report = audit(args.objdir, args.live, args.elf, dict(nm=args.nm, size=args.size))
    if args.gc_ld:
        report['section_gc'] = measure_gc(args.objdir, args.live, args.gc_ld,
                                         dict(nm=args.nm, size=args.size),
                                         args.out.parent / 'gc')
        report['low_ram'] = low_ram_gaps(GAME / 'src/ram_low.h')
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f"Player SH-2 total {report['player_total_bytes']} B; carve headroom "
          f"{report['carve_headroom_bytes']} B; fits={report['fits_upper_bound']}")
    for name, case in report.get('section_gc', {}).get('cases', {}).items():
        print(f"GC {name}: {case['sizes']['total']} B, Player_Draw kept={case['player_draw_retained']}")
    print(f"duplicates {len(report['duplicates'])}; unresolved {report['unresolved_counts']}: {args.out}")


if __name__ == '__main__':
    main()
