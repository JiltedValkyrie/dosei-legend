#!/usr/bin/env python3
"""Isolated combined-core retention probe; not a runnable or dependency-complete link.

Recompile copies of the three bridges with the nine replaced definitions removed.
Link all existing core objects plus real Player with relocatable section GC, so
previously discarded engine sections pulled in by Player contribute to the size.
No unresolved symbol is stubbed, and no live build output is modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess

from player_migration_symbols import GAME, nm, section_sizes, low_ram_gaps

REPLACED = {
    'bridge_player': ['Player_UpdateWeaponInfo'],
    'bridge_play': ['Player_InCsMode', 'Player_GetExplosiveHeld',
                    'Player_ReleaseLockOn', 'Player_GetMask'],
    'bridge_items': ['Player_HoldsHookshot', 'Player_IsBurningStickInRange',
                     'Player_InBlockingCsMode'],
}


def remove_definition(text, name):
    # Current bridge functions end on their own line. Refuse ambiguous or
    # changed layouts; leave a declaration so earlier callers retain linkage.
    pattern = re.compile(r'^[\w* ]+\b' + re.escape(name) +
                         r'\([^;{}]*\)\s*\{[^\n]*\n.*?^\}', re.M | re.S)
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f'expected one bridge definition: {name}')
    match = matches[0]
    declaration = match.group().split('{', 1)[0].rstrip() + ';'
    return text[:match.start()] + declaration + text[match.end():]


def run(command, log=None):
    result = subprocess.run(command, capture_output=True, text=True)
    if log:
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise RuntimeError(f'{command[0]} failed: {result.stderr[:3000]}')
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--cxxflags', required=True)
    parser.add_argument('--ld', required=True)
    parser.add_argument('--nm', required=True)
    parser.add_argument('--size', required=True)
    parser.add_argument('--oot', type=Path, default=os.environ.get('OOT'))
    parser.add_argument('--live', type=Path, default=GAME / 'build/obj-clean/oot-core')
    parser.add_argument('--player', type=Path, default=GAME / 'build/player-migration/sh2')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/placement')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    # Objects actually linked into the resident core (its link map). The same
    # directory also holds scene actor-pack objects (Field enemies), which are
    # linked into OAP packs, not the core.
    core_map = GAME / 'build/oot-core/oot-core.map'
    linked = {Path(line.split()[1]).name for line in core_map.read_text(errors='ignore').splitlines()
              if line.startswith('LOAD ') and line.endswith('.o')} if core_map.exists() else None
    live = sorted(p for p in args.live.glob('*.o') if linked is None or p.name in linked)
    if not live:
        raise ValueError('no core objects')
    replacements = {}
    for name, functions in REPLACED.items():
        text = (GAME / 'oot-core/src' / (name + '.cpp')).read_text(encoding='utf-8')
        for function in functions:
            text = remove_definition(text, function)
        if name == 'bridge_player':
            text, count = re.subn(r'^ActorProfile Player_Profile = \{.*?^\};',
                                  'extern ActorProfile Player_Profile;', text, flags=re.M | re.S)
            if count != 1:
                raise ValueError('expected one proxy Player_Profile')
        source = args.out / (name + '.cpp')
        target = source.with_suffix('.o')
        source.write_text(text, encoding='utf-8')
        run([args.cxx, *shlex.split(args.cxxflags), '-I' + str(GAME / 'oot-core/src'),
             '-c', str(source), '-o', str(target)], source.with_suffix('.log'))
        replacements[name + '.o'] = target

    # Preserve the same ctor/placeholder/entry roots as oot-core.ld. Undefined
    # backend and asset symbols remain visible; this is intentionally ld -r.
    script = args.out / 'retention.ld'
    script.write_text('''SECTIONS {
 .oot_entry : { KEEP(*(.oot_entry)) }
 .text : { *(.text .text.*) }
 .rodata : { *(.rodata .rodata.*) }
 .data : { *(.data .data.*) . = ALIGN(4);
   KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array)) KEEP(*(.ctors)) }
 .keep_ph : { KEEP(*(.keep_ph)) }
 .bss : { *(.bss .bss.*) *(COMMON) }
 /DISCARD/ : { *(.comment) *(.dtors) *(.fini_array) *(.eh_frame) }
}
''', encoding='utf-8')
    player = [args.player / (name + '.o') for name in
              ('z_player', 'z_player_call', 'z_player_lib')]
    if args.oot is None:
        raise ValueError('set OOT or --oot for real animation-header dependency sizing')
    animation_source = args.oot / 'assets/objects/gameplay_keep/player_anim_headers.c'
    animation_object = args.out / 'player_anim_headers.o'
    run([args.cxx, *shlex.split(args.cxxflags), '-c', str(animation_source),
         '-o', str(animation_object)], args.out / 'player_anim_headers.log')
    combined = [replacements.get(p.name, p) for p in live] + player
    # Check that replacements eliminated duplicate strong owners, not merely
    # hidden linker diagnostics or rebound calls to renamed proxy definitions.
    owners = {}
    for path in combined:
        for symbol, weak in nm(args.nm, path)[0].items():
            if not weak:
                if symbol in owners:
                    raise ValueError(f'duplicate {symbol}: {owners[symbol]}, {path}')
                owners[symbol] = str(path)
    report = dict(status='combined retention lower bound; missing implementations/assets not sized',
                  inputs={str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in live + player}, cases={},
                  low_ram=low_ram_gaps(GAME / 'src/ram_low.h'))
    libgcc = Path(run([args.cxx, '-m2', '-print-libgcc-file-name']).strip())
    report['libgcc'] = dict(path=str(libgcc), sha256=hashlib.sha256(libgcc.read_bytes()).hexdigest())
    for name, objects in [('baseline', live), ('with_player', combined),
                          ('with_animation_headers', combined + [animation_object])]:
        target = args.out / (name + '.o')
        run([args.ld, '-r', '--gc-sections', '--undefined=_oot_core_entry',
             '-T', str(script), '-Map=' + str(target.with_suffix('.map')),
             '-o', str(target), *map(str, objects), str(libgcc)], target.with_suffix('.log'))
        defined, undefined = nm(args.nm, target)
        for root in ('_oot_core_entry', '_Player_Profile'):
            if root not in defined:
                raise ValueError(f'{name}: missing retained root {root}')
        report['cases'][name] = dict(sizes=section_sizes(args.size, target),
                                    unresolved=sorted(undefined), unresolved_count=len(undefined),
                                    sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    old = report['cases']['baseline']
    new = report['cases']['with_player']
    headers = report['cases']['with_animation_headers']
    report['animation_header_bytes_retained'] = headers['sizes']['total'] - new['sizes']['total']
    report['animation_source_sha256'] = hashlib.sha256(animation_source.read_bytes()).hexdigest()
    report['new_unresolved'] = sorted(set(new['unresolved']) - set(old['unresolved']))
    report['retained_growth_bytes'] = new['sizes']['total'] - old['sizes']['total']
    # Read capacity from current makefile, not a stale duplicated constant.
    makefile = (GAME / 'makefile').read_text(encoding='utf-8')
    capacity = int(re.search(r'^OOT_CORE_MAX_BYTES\s*=\s*(0x[0-9a-fA-F]+)', makefile, re.M)[1], 16)
    large_gaps = [gap for gap in report['low_ram']['gaps'] if gap['bytes'] >= 0x6000]
    report['candidate_capacity_bytes'] = capacity + sum(gap['bytes'] for gap in large_gaps)
    report['candidate_unallocated_bytes_before_missing_dependencies'] = (
        report['candidate_capacity_bytes'] - headers['sizes']['total'])
    # Already-retired fixed reservations, not heap or active actor capacity.
    cart_header = (GAME / 'src/ram_cart.h').read_text(encoding='utf-8')
    constants = {name: int(value, 0) for name, value in re.findall(
        r'^#define\s+(RAM_CART_\w+)\s+(0x[0-9A-Fa-f]+|[0-9]+)u?\b', cart_header, re.M)}
    fixed_base = (constants['RAM_CART_BANK2_ADDRESS'] + constants['RAM_CART_BANK2_BYTES']
                  - constants['RAM_CART_OOTCORE_OFFSET'] - constants['RAM_CART_OOTCORE_BYTES'])
    retired = []
    for name in ('RAM_CART_MUSICTRG', 'RAM_CART_FAIRY'):
        consumers = [str(p) for p in (GAME / 'src').rglob('*')
                     if p.suffix in ('.c', '.h') and p.name not in ('ram_cart.c', 'ram_cart.h')
                     and name in p.read_text(encoding='utf-8')]
        if consumers:
            raise ValueError(f'{name} no longer unused: {consumers}')
        retired.append(dict(name=name,
            cached_address=hex((fixed_base + constants[name + '_OFFSET']) & ~0x20000000),
            bytes=constants[name + '_BYTES']))
    report['retired_cart_candidates'] = retired
    report['extended_candidate_capacity_bytes'] = (report['candidate_capacity_bytes']
                                                   + sum(r['bytes'] for r in retired))
    report['extended_unallocated_bytes_before_missing_dependencies'] = (
        report['extended_candidate_capacity_bytes'] - headers['sizes']['total'])
    elf = GAME / 'build/oot-core/oot-core.elf'
    load = int(re.search(r'^OOT_CORE_LOAD_ADDR\s*=\s*(0x[0-9a-fA-F]+)', makefile, re.M)[1], 16)
    end = re.search(r'^([0-9a-fA-F]+)\s+\w\s+_oot_core_end$', run([args.nm, str(elf)]), re.M)
    if not end:
        raise ValueError('missing baseline ELF end symbol')
    elf_bytes = int(end[1], 16) - load
    # ld -r keeps C++ inline (comdat) sections and skips the production
    # script's alignment, so the probe and the real link differ by a little.
    # Record the gap; a large one means the object set is wrong.
    gap = elf_bytes - old['sizes']['total']
    report['baseline_elf'] = dict(sha256=hashlib.sha256(elf.read_bytes()).hexdigest(), bytes=elf_bytes,
                                 same_size=gap == 0, link_minus_probe_bytes=gap)
    if abs(gap) > 4096:
        raise ValueError('retention baseline differs from current ELF by %d B; reconcile artifacts first' % gap)
    report['placement_accepted'] = False
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: report[key] for key in ('retained_growth_bytes',
          'candidate_capacity_bytes', 'candidate_unallocated_bytes_before_missing_dependencies',
          'extended_unallocated_bytes_before_missing_dependencies',
          'placement_accepted')}, indent=2))


if __name__ == '__main__':
    main()
