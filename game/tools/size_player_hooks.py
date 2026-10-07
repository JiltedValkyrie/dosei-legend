#!/usr/bin/env python3
"""Size Player's missing engine hooks and real Link skeleton objects (SH-2).

Hooks: each unresolved engine function/table from symbols.json is located in
the decomp, its file staged through the production fixups and compiled with
the target flags. `ld -r --gc-sections` rooted at the needed symbols gives the
real-source cost (same-file closure; deeper unresolved calls listed, not sized).
Each hook also gets an owner class from the migration rules (Saturn keeps
camera, audio, scene flow and UI; core owns gameplay state) and, for host
adapters, an estimate from the measured size of existing HOST bridges.

Skeletons: object_link_boy/object_link_child through the existing object blob
pipeline (real skeleton/limb data, one-word DL/texture keys), linked with
oot-core/object.ld exactly as the makefile does.

Measurement only: no live source list, carve, blob or disc changes.
"""
import argparse
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from oot_core_import import GAME, fixup, object_blob_sources, write_if_changed
from player_migration_symbols import nm, section_sizes

# Owner class per hook prefix (first match wins). host = Saturn adapter over
# the retained C owner; real = import source; saturn = resident replacement.
OWNERS = (
    (r'^(Audio_|func_800F4|func_800F6)', 'host_audio'),
    (r'^(Camera_|Play_CamIsNotFixed|OnePointCutscene_)', 'host_camera'),
    (r'^(Room_|Scene_SetTransition|Play_Trigger|Play_SetupRespawnPoint|Map_Save|Environment_)',
     'host_scene_flow'),
    (r'^Interface_', 'host_ui'),
    (r'^(Magic_|Inventory_|Item_CheckObtainability|func_800849EC|Health_IsCritical)', 'real_gameplay_state'),
    (r'^(guPerspective|guLookAt)', 'real_math'),
    # One entrance field for exits/voids: Saturn scene flow answers it.
    (r'^gEntranceTable$', 'host_scene_flow'),
    # Object DMA (get-item model, Link object): Saturn residency/sprites.
    (r'^(gObjectTable|osCreateMesgQueue|DmaMgr_|KaleidoManager_|KaleidoScopeCall_)',
     'saturn_resident_dispatch'),
)
LINK_OBJECTS = ('object_link_boy', 'object_link_child')


def plain_name(symbol):
    m = re.match(r'^__Z(\d+)(\w+)', symbol)
    if m:
        return m.group(2)[:int(m.group(1))]
    return symbol.lstrip('_')


def owner(name):
    return next((cls for pat, cls in OWNERS if re.match(pat, name)), 'unclassified')


def find_source(oot, name):
    pattern = re.compile(r'^[A-Za-z_][\w \*]*\b' + re.escape(name) + r'(\s*\(|\s*\[)', re.M)
    for path in sorted((oot / 'src').rglob('*.c')):
        if pattern.search(path.read_text(encoding='utf-8', errors='replace')):
            return path.relative_to(oot).as_posix()
    return None


def relocated(objdump, path):
    """Symbols referenced by relocations, i.e. by sections ld -r kept. nm -u
    on an ld -r output also lists names only dead sections used."""
    out = subprocess.run([objdump, '-r', str(path)], capture_output=True,
                         text=True, check=True).stdout
    return {re.sub(r'[+-]0x.*', '', l.split()[2]) for l in out.splitlines()
            if len(l.split()) == 3 and not l.startswith('OFFSET')}


def run(command, log=None):
    result = subprocess.run(command, capture_output=True, text=True)
    if log is not None:
        log.write_text(result.stdout + result.stderr, encoding='utf-8')
    return result


def host_bridge_sizes(live, nm_tool):
    """Measured size of existing HOST-tagged bridge functions."""
    sizes = []
    for src in sorted((GAME / 'oot-core/src').glob('bridge_*.cpp')):
        obj = live / (src.stem + '.o')
        if not obj.exists():
            continue
        names = re.findall(r'^[A-Za-z_][\w \*]*\b(\w+)\([^;{]*\)\s*\{\s*/\* HOST', src.read_text(
            encoding='utf-8'), re.M)
        out = subprocess.run([nm_tool, '-S', str(obj)], capture_output=True, text=True).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) == 4 and parts[2] in 'Tt' and plain_name(parts[3]) in names:
                sizes.append(int(parts[1], 16))
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cxx', required=True)
    parser.add_argument('--cxxflags', required=True)
    parser.add_argument('--ld', required=True)
    parser.add_argument('--nm', required=True)
    parser.add_argument('--size', required=True)
    parser.add_argument('--objdump', required=True)
    parser.add_argument('--player-gc', type=Path,
                        default=GAME / 'build/player-migration/gc/source_profile.o')
    parser.add_argument('--oot', type=Path, default=os.environ.get('OOT'))
    parser.add_argument('--symbols', type=Path, default=GAME / 'build/player-migration/symbols.json')
    parser.add_argument('--live', type=Path, default=GAME / 'build/obj-clean/oot-core')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/hooks')
    args = parser.parse_args()
    if args.oot is None:
        raise SystemExit('set OOT or --oot')
    flags = shlex.split(args.cxxflags)
    args.out.mkdir(parents=True, exist_ok=True)
    unresolved = json.loads(args.symbols.read_text(encoding='utf-8'))['unresolved']
    player_refs = relocated(args.objdump, args.player_gc)
    listed = unresolved['engine_functions'] + unresolved['tables']
    hooks = [s for s in listed if s in player_refs]
    dead_hooks = sorted(plain_name(s) for s in listed if s not in player_refs)
    live_defs = set()
    for obj in sorted(args.live.glob('*.o')):
        live_defs.update(nm(args.nm, obj)[0])

    by_file, rows = {}, {}
    for symbol in hooks:
        name = plain_name(symbol)
        rel = find_source(args.oot, name)
        rows[symbol] = dict(name=name, source=rel, owner=owner(name))
        if rel:
            by_file.setdefault(rel, []).append(symbol)
        else:
            rows[symbol]['status'] = 'no decomp definition found'

    files = {}
    for rel, roots in sorted(by_file.items()):
        stem = Path(rel).stem
        stats = dict(macros=0, fxl=0, anon=0, mtxf=0, problems=[])
        source = args.out / 'decomp' / Path(rel).with_suffix('.cpp')
        write_if_changed(source, fixup(rel, (args.oot / rel).read_text(encoding='utf-8'), stats))
        obj = args.out / (stem + '.o')
        result = run([args.cxx, *flags, '-c', str(source), '-o', str(obj)],
                     args.out / (stem + '.log'))
        entry = dict(roots=[rows[s]['name'] for s in roots])
        if result.returncode:
            errors = [l for l in result.stderr.splitlines() if 'error' in l]
            entry.update(status='compile FAIL', first_errors=errors[:3])
            for s in roots:
                rows[s]['status'] = 'source compile failed'
            files[rel] = entry
            continue
        defined = nm(args.nm, obj)[0]
        present = [s for s in roots if s in defined]
        for s in roots:
            if s not in defined:
                rows[s]['status'] = 'signature differs from Player reference'
        if not present:
            entry['status'] = 'no matching root'
            files[rel] = entry
            continue
        kept = args.out / (stem + '.gc.o')
        result = run([args.ld, '-r', '--gc-sections', *['--undefined=' + s for s in present],
                      '-Map=' + str(args.out / (stem + '.gc.map')), '-o', str(kept), str(obj)])
        if result.returncode:
            entry.update(status='gc link FAIL', first_errors=result.stderr.splitlines()[:3])
            files[rel] = entry
            continue
        size = section_sizes(args.size, kept)
        deeper = sorted(s for s in relocated(args.objdump, kept) & nm(args.nm, kept)[1]
                        if s not in live_defs)
        entry.update(status='sized', bytes=size['total'], sizes=size,
                     deeper_unresolved=len(deeper))
        for s in present:
            rows[s]['status'] = 'sized with file closure'
        files[rel] = entry

    bridge = host_bridge_sizes(args.live, args.nm)
    mean = round(sum(bridge) / len(bridge)) if bridge else None
    classes = {}
    for row in rows.values():
        classes.setdefault(row['owner'], []).append(row['name'])
    host_count = sum(len(v) for k, v in classes.items() if k.startswith('host_'))
    real_files = {rel: e for rel, e in files.items()
                  if any(owner(n).startswith('real_') for n in e['roots'])}

    skeletons = {}
    for name in LINK_OBJECTS:
        data, ph, dropped = object_blob_sources(name, args.oot / 'extracted/ntsc-1.2')
        base = args.out / name
        Path(str(base) + '.cpp').write_text(data, encoding='utf-8')
        Path(str(base) + '_ph.cpp').write_text(ph, encoding='utf-8')
        ok = True
        for unit in (str(base) + '.cpp', str(base) + '_ph.cpp'):
            result = run([args.cxx, *flags, '-c', unit, '-o', unit[:-4] + '.o'],
                         Path(unit[:-4] + '.log'))
            ok = ok and result.returncode == 0
        entry = dict(placeholders=len(dropped))
        if ok:
            result = run([args.cxx, '-m2', '-nostdlib', '-nostartfiles',
                          '-T', str(GAME / 'oot-core/object.ld'),
                          '-Wl,--defsym,OOT_OBJECT_MAX_BYTES=0x30000',
                          str(base) + '.o', str(base) + '_ph.o', '-o', str(base) + '.elf'],
                         Path(str(base) + '.link.log'))
            ok = result.returncode == 0
        if ok:
            entry.update(status='linked', sizes=section_sizes(args.size, Path(str(base) + '.elf')))
        else:
            entry['status'] = 'FAIL (see logs)'
        skeletons[name] = entry

    report = dict(
        status='measurement only; hooks not linked, skeleton blobs not installed',
        hooks=rows, dead_only_hooks=dead_hooks,
        live_refs=dict(player_animations=sum(s.startswith('_gPlayerAnim_') for s in player_refs),
                       link_assets=sum(s.startswith('_gLink') for s in player_refs)),
        files=files, owner_classes=classes,
        host_bridge_samples=len(bridge), host_bridge_mean_bytes=mean,
        host_adapter_count=host_count,
        host_adapter_estimate_bytes=(mean * host_count) if mean else None,
        real_source_bytes=sum(e.get('bytes', 0) for e in real_files.values()),
        real_source_files_failed=sorted(rel for rel, e in real_files.items()
                                        if e['status'] != 'sized'),
        skeletons=skeletons)
    (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'hooks referenced by kept Player code {len(hooks)}; dead-only {dead_hooks}')
    print(f"live refs: {report['live_refs']}")
    for cls, names in sorted(classes.items()):
        print(f'{cls}: {len(names)}')
    for rel, e in sorted(files.items()):
        print(f"{rel}: {e['status']} {e.get('bytes', '')} deeper={e.get('deeper_unresolved', '-')}")
    print(f'host bridge mean {mean} B x {host_count} = {report["host_adapter_estimate_bytes"]} B')
    print(f'real source (same-file closure) {report["real_source_bytes"]} B; '
          f'failed {report["real_source_files_failed"]}')
    for name, e in skeletons.items():
        print(f"{name}: {e['status']} {e.get('sizes', {}).get('total', '')} B, "
              f"{e['placeholders']} placeholders")


if __name__ == '__main__':
    main()
