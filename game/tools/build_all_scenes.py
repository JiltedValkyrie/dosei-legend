"""Bake every OoT scene's rooms into VDP1 banks (all-scenes preflight).

Reads the decomp scene table (include/tables/scene_table.h) for every scene,
then runs the same converter as build_progression_rooms.py on each room.
Image-shaped rooms (prerendered backdrops) are reported as 'image', not baked
here: build_scene_backdrops.py owns them. A room that fails is 'blocked' with
its error; nothing is skipped silently. Output: build/all-scenes/ +
scene_preflight.json. Not registered in the runtime by this script.

Scenes are extracted and rooms baked in a process pool (--jobs, default
DOSEI_BAKE_JOBS or every CPU, capped at 24). Each room writes only its own
folder and the report keeps source scene and room order, so the output equals
a serial bake; only the progress lines arrive out of order.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import json
import os
import re
import traceback
from pathlib import Path

import build_hybrid_scene as hybrid
import build_room_scene as rooms
import build_sgl_scene as sgl

ROOT = Path(__file__).resolve().parents[1]
SCENE_LINE = re.compile(r'/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_SCENE\(\s*(\w+)_scene\s*,\s*\w+\s*,\s*(\w+)')
ROOM_SHAPE_IMAGE = 1


def converter_fingerprint():
    """Invalidate old room banks when a decoder, material or budget changes."""
    digest = hashlib.sha256()
    digest.update(('DOSEI_TEX_HALVE=%d' % hybrid.texture_halve_mode()).encode('ascii'))
    paths = [Path(__file__), ROOT.parent / 'shared/tools/build_kokiri_scene.py']
    paths += [ROOT / 'tools' / name for name in (
        'build_hybrid_scene.py', 'build_quads.py', 'build_room_scene.py',
        'build_sgl_scene.py', 'vdp1_budget.py', 'map_meshes.py')]
    paths += [ROOT / 'build/generated/LINK.BIN', ROOT / 'build/generated/ADULT.BIN']
    for path in paths:
        digest.update(path.name.encode('utf-8'))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def scene_fingerprint(converter, segments):
    digest = hashlib.sha256(converter.encode('ascii'))
    for name, data in sorted(segments.items()):
        digest.update(name.encode('utf-8'))
        digest.update(data)
    return digest.hexdigest()


def cache_current(rows, fingerprint, out):
    if not rows or any(row.get('fingerprint') != fingerprint for row in rows):
        return False
    for row in rows:
        if row['status'] == 'baked':
            folder = out / ('%s_room_%d' % (row['prefix'], row['room']))
            if any(not (folder / name).is_file() for name in
                   ('room.msh', 'room.tex', 'texture_manifest.json')):
                return False
    return True


def scene_list(oot, retail_only=False):
    out = []
    conditions = [True]
    for line in (oot / 'include/tables/scene_table.h').read_text(encoding='utf-8').splitlines():
        directive = line.strip()
        if directive.startswith('#if '):
            if directive != '#if DEBUG_ASSETS':
                raise ValueError('unhandled scene table condition: ' + directive)
            conditions.append(conditions[-1] and not retail_only)
            continue
        if directive == '#else':
            if len(conditions) < 2:
                raise ValueError('unmatched scene table #else')
            conditions[-1] = conditions[-2] and not conditions[-1]
            continue
        if directive == '#endif':
            if len(conditions) < 2:
                raise ValueError('unmatched scene table #endif')
            conditions.pop()
            continue
        if not conditions[-1]:
            continue
        m = SCENE_LINE.search(line)
        if m:
            out.append(dict(id=int(m.group(1), 16), prefix=m.group(2), scene=m.group(3)))
    if len(conditions) != 1:
        raise ValueError('unterminated scene table condition')
    if not out:
        raise SystemExit('scene table parsed as empty')
    return out


def room_shape(room_data):
    """Room header command 0x0A (SCENE_CMD_ROOM_SHAPE): segment pointer -> type byte."""
    for at in range(0, min(0x400, len(room_data)), 8):
        cmd = room_data[at]
        if cmd == 0x14:
            break
        if cmd == 0x0A:
            ptr = int.from_bytes(room_data[at + 4:at + 8], 'big') & 0xFFFFFF
            return room_data[ptr] if ptr < len(room_data) else None
    return None


def default_jobs():
    env = os.environ.get('DOSEI_BAKE_JOBS')
    return max(1, int(env)) if env else max(1, min(os.cpu_count() or 1, 24))


# Worker state: the generic-import flags, scene head and Link actor budget,
# set once per process (spawn on Windows hosts, fork in WSL).
_WORKER = {}


def _worker_init(head, actor):
    # Generic import mode (shared/tools/build_kokiri_scene.py): room G_MTX
    # kept at identity, G_BRANCH_Z near geometry walked. Both APPROXIMATE.
    hybrid.source.DisplayLists.generic_scene = True
    hybrid.source.DisplayLists.include_depth_branches = True
    _WORKER.update(head=head, actor=actor)


def _scan_scene(oot, rom_dir, converter, sc):
    """Extract one scene: its fingerprint and (name, room id, shape) rows."""
    prefix = sc['prefix']
    try:
        segments = hybrid.source.extract(oot, rom_dir, prefix=prefix)
    except Exception as error:  # noqa: BLE001 - report every failure
        return dict(error='extract: %s' % error)
    names = sorted((n for n in segments if n.startswith(prefix + '_room_')),
                   key=lambda n: int(n.rsplit('_', 1)[1]))
    return dict(fingerprint=scene_fingerprint(converter, segments),
                rooms=[(n, int(n.rsplit('_', 1)[1]), room_shape(segments[n])) for n in names])


def _bake_room(oot, rom_dir, out, entry, name):
    folder = out / name
    try:
        _, vertices, faces, rtiles = hybrid.convert(oot, _WORKER['head'], _WORKER['actor'], folder,
            rom_dir=rom_dir, prefix=entry['prefix'], room=name, layout={},
            room_pixel_limit=hybrid.GENERIC_ROOM_PIXEL_LIMIT,
            room_vertex_limit=hybrid.GENERIC_ROOM_VERTEX_LIMIT,
            room_face_limit=hybrid.GENERIC_ROOM_FACE_LIMIT)
        detail = json.loads((folder / 'texture_manifest.json').read_text())
        mesh, pixels, bounds = rooms.pack_room(vertices, faces, rtiles, detail['faces'],
                                              sgl.face_normal,
                                              source_empty=detail.get('source_empty', False))
        (folder / 'room.msh').write_bytes(mesh)
        (folder / 'room.tex').write_bytes(pixels)
        entry.update(status='baked', vertices=len(vertices), polygons=len(faces),
                     tiles=len(rtiles), mesh_bytes=len(mesh), pixel_bytes=len(pixels),
                     pixel_budget=detail['pixel_budget'],
                     source_empty=detail.get('source_empty', False))
    except Exception as error:  # noqa: BLE001
        entry.update(status='blocked', error='%s: %s' % (type(error).__name__, error),
                     where=traceback.format_exc().strip().splitlines()[-2].strip())
    return entry


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot', type=Path, default=Path(__import__('os').environ.get('DOSEI_OOT')
                    or 'D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--rom-dir', type=Path)
    ap.add_argument('--out', type=Path, default=ROOT / 'build/all-scenes')
    ap.add_argument('--only', action='append', help='scene prefix (repeatable)')
    ap.add_argument('--refresh-stale', action='store_true',
                    help='reuse only banks matching current source, converters and actor budget')
    ap.add_argument('--registered-only', action='store_true',
                    help='refresh currently registered scenes; retain unregistered report rows')
    ap.add_argument('--retail-only', action='store_true',
                    help='build all source retail scenes; exclude DEBUG_ASSETS-only entries')
    ap.add_argument('--jobs', type=int, default=default_jobs(),
                    help='worker processes (default DOSEI_BAKE_JOBS or CPU count, max 24)')
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    _, head, _, _ = sgl.read_scene(ROOT / 'levels/kokiri/assets/static/FOREST.BIN')
    actor = sgl.link_actor_budget(ROOT / 'build/generated/LINK.BIN')
    report = args.out / 'scene_preflight.json'
    old = json.loads(report.read_text()) if (args.only or args.refresh_stale or args.registered_only) and report.exists() else []
    source_scenes = scene_list(args.oot, retail_only=args.retail_only)
    if args.retail_only:
        retail = {row['prefix'] for row in source_scenes}
        old = [row for row in old if row['prefix'] in retail]
    selected = set(args.only) if args.only else None
    if args.registered_only:
        from build_scene_table import SCENES
        registered = {row['prefix'] for row in SCENES}
        selected = registered if selected is None else selected & registered
    kept = [r for r in old if r['prefix'] not in selected] if selected is not None else []
    converter = converter_fingerprint()
    scenes = [sc for sc in source_scenes if selected is None or sc['prefix'] in selected]
    # Per scene, in source order: finished report rows (None while pending).
    done = [None] * len(scenes)
    waiting = {}   # scene index -> [rows, rooms still baking]
    changed = False

    def checkpoint():
        # Keep unvisited cached rows during a long refresh. An interrupted
        # bake must not make every later scene disappear from registration.
        finished = [r for rows in done if rows is not None for r in rows]
        visited = {r['prefix'] for r in finished} | {r['prefix'] for r in kept}
        report.write_text(json.dumps(kept + finished + [r for r in old if r['prefix'] not in visited],
                                     indent=1) + '\n')

    with ProcessPoolExecutor(max_workers=args.jobs, initializer=_worker_init,
                             initargs=(head, actor)) as pool:
        scans = {pool.submit(_scan_scene, args.oot, args.rom_dir, converter, sc): i
                 for i, sc in enumerate(scenes)}
        bakes = {}
        for future in as_completed(scans):
            i = scans[future]
            sc, scan = scenes[i], future.result()
            prefix = sc['prefix']
            if 'error' in scan:
                done[i] = [dict(sc, room=None, status='blocked', error=scan['error'])]
                print('%s: extract blocked: %s' % (prefix, scan['error']), flush=True)
                changed = True
                continue
            cached = [r for r in old if r['prefix'] == prefix]
            if args.refresh_stale and cache_current(cached, scan['fingerprint'], args.out):
                done[i] = cached
                continue
            changed = True
            rows, queued = [], 0
            for name, room_id, shape in scan['rooms']:
                entry = dict(sc, room=room_id, fingerprint=scan['fingerprint'])
                if prefix == 'spot00' and room_id == 0:
                    # Hyrule Field already uses the spatial streaming bake/load
                    # route. A whole-field KRM1 bank is not its runtime payload.
                    entry.update(status='streamed', source_room_shape=shape,
                                 pipeline='build_field_chunks.py', owner='build_room_scene.py')
                elif shape == ROOM_SHAPE_IMAGE:
                    entry.update(status='image')
                else:
                    bakes[pool.submit(_bake_room, args.oot, args.rom_dir, args.out, entry, name)] = (i, len(rows))
                    queued += 1
                rows.append(entry)
            if queued:
                waiting[i] = [rows, queued]
            else:
                done[i] = rows
        print('scenes scanned: %d rooms to bake on %d workers' % (len(bakes), args.jobs), flush=True)
        for future in as_completed(bakes):
            i, at = bakes[future]
            entry = waiting[i][0][at] = future.result()
            print('%s room %d: %s%s' % (entry['prefix'], entry['room'], entry['status'],
                  ' (%s)' % entry['error'] if 'error' in entry else ''), flush=True)
            waiting[i][1] -= 1
            if not waiting[i][1]:
                done[i] = waiting.pop(i)[0]
                checkpoint()
    results = kept + [r for rows in done for r in rows]
    # Include extraction failures at the end too (no room loop writes them).
    if changed:
        report.write_text(json.dumps(results, indent=1) + '\n')
    counts = {}
    for r in results:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    print('rooms:', counts)
    if (args.only or args.retail_only) and any(
            (not args.only or r['prefix'] in args.only) and r['status'] == 'blocked'
            for r in results):
        raise SystemExit('requested scene bake failed; do not stage stale banks')


if __name__ == '__main__':
    main()
