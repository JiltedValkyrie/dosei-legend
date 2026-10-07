#!/usr/bin/env python3
"""Sized list of every C collision caller that must move to core z_bgcheck
before the C collision storage (scene buffer, index, dyna carve) is reclaimed.

Counts call sites of the shared/lib/collision API per game source file, maps
each API call to the core bgcheck function that replaces it, and measures the
C library code that retires with it (Clean ELF symbol spans). Reports only;
changes nothing.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent
REPO = GAME.parent
LIB = REPO / 'shared/lib/collision'

# C API -> core replacement (decomp function names) and the new oot_core_api
# entry the C side would call. One entry can serve several C calls.
CORE = {
    'kokiri_collision_floor': ('BgCheck_EntityRaycastDown4', 'bg_floor'),
    'bg_floor': ('BgCheck_EntityRaycastDown4', 'bg_floor'),
    'kokiri_collision_spawn': ('BgCheck_EntityRaycastDown4', 'bg_floor'),
    'kokiri_collision_clear': ('BgCheck_EntityCheckCeiling + SphVsWall', 'bg_clear'),
    'kokiri_collision_move': ('BgCheck_EntitySphVsWall3 + RaycastDown4', 'bg_move'),
    'kokiri_collision_move_actor': ('Actor_UpdateBgCheckInfo path (SphVsWall3, CheckCeiling, RaycastDown4)', 'bg_move'),
    'kokiri_collision_jump': ('Actor_UpdateBgCheckInfo path', 'bg_move'),
    'kokiri_collision_fall': ('Actor_UpdateBgCheckInfo path', 'bg_move'),
    'kokiri_collision_actor_begin_step': ('BgCheckInfo prior-contact state', 'bg_move'),
    'kokiri_collision_actor_wall': ('BgCheck_EntitySphVsWall3 (wallPoly, wallBgId)', 'bg_wall'),
    'kokiri_collision_actor_set_crawl': ('Player crawl wall height (source Player)', 'bg_move'),
    'kokiri_collision_actor_probe_still': ('BgCheck_EntityRaycastDown4', 'bg_floor'),
    'bg_wall_flags': ('SurfaceType_GetWallFlags', 'bg_surface'),
    'bg_poly_plane_distance': ('CollisionPoly plane (normal, dist)', 'bg_surface'),
    'bg_poly_vertices': ('CollisionPoly_GetVertices', 'bg_surface'),
    'bg_scene_set': ('BgCheck_Allocate/Init from scene blob (already core)', 'scene load'),
    'bg_scene_mesh': ('play->colCtx.colHeader', 'scene load'),
    'bg_mesh_bytes': ('scene blob size (already core)', 'scene load'),
    'kokiri_collision_init': ('BgCheck_Init (already core)', 'scene load'),
    'kokiri_collision_index': ('BgCheck lookup (already core, THA)', 'scene load'),
    'bg_water_set_surface': ('WaterBox ySurface write', 'bg_water'),
    'bg_water_reset_surface': ('WaterBox ySurface restore', 'bg_water'),
    'bg_dyna_init': ('DynaPoly_Init (already core)', 'dyna'),
    'bg_dyna_register': ('DynaPoly_SetBgActor', 'dyna'),
    'bg_dyna_set': ('DynaPoly actor transform (actor world/shape)', 'dyna'),
    'bg_dyna_enable': ('DynaPoly_EnableCollision / DisableCollision', 'dyna'),
    'bg_dyna_remove': ('DynaPoly_DeleteBgActor', 'dyna'),
    'bg_dyna_clear': ('DynaPoly reset on scene load', 'dyna'),
    'bg_dyna_step': ('DynaPoly_UpdateContext/UpdateBgActorTransforms', 'dyna'),
    'bg_dyna_carry': ('DynaPolyActor rider (BgCheck_UpdateBgActor/ floorBgId)', 'dyna'),
    'bg_dyna_triangles_used': ('debug count', 'dyna'),
}
CALL = re.compile(r'\b(' + '|'.join(sorted(CORE, key=len, reverse=True)) + r')\s*\(')


def symbol_sizes(nm, elf):
    """COFF has no symbol sizes: use address gaps between text symbols."""
    out = subprocess.run([nm, '--target=coff-sh', str(elf)], capture_output=True,
                         text=True, check=True).stdout
    rows = sorted((int(p[0], 16), p[2]) for p in (l.split() for l in out.splitlines())
                  if len(p) == 3 and p[1] in 'Tt' and not p[2].startswith('.'))
    sizes = {}
    for (a, n), (b, _) in zip(rows, rows[1:]):
        if b - a < 0x4000:
            sizes[n.lstrip('_')] = b - a
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--nm', default=str(REPO.parent / 'sh2eb-elf/bin/sh2eb-elf-nm.exe'))
    parser.add_argument('--elf', type=Path, default=GAME / 'build/game-clean.elf')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/collision_ports.json')
    args = parser.parse_args()
    files = {}
    for path in sorted((GAME / 'src').glob('*.c')):
        calls = {}
        for m in CALL.finditer(path.read_text(encoding='utf-8', errors='replace')):
            calls[m.group(1)] = calls.get(m.group(1), 0) + 1
        if calls:
            files[path.name] = calls
    lib_text = (LIB / 'kokiri_collision.c').read_text(encoding='utf-8')
    lib_funcs = set(re.findall(r'^(?:static\s+)?[\w\s\*]+?\b(\w+)\s*\([^;]*\)\s*\{', lib_text, re.M))
    sizes = symbol_sizes(args.nm, args.elf) if args.elf.exists() else {}
    lib_code = sum(sizes.get(f, 0) for f in lib_funcs)
    entries = sorted({CORE[c][1] for calls in files.values() for c in calls})
    report = dict(
        status='port list only; nothing moved',
        storage_reclaimed=dict(scene_buffer_heap=94854, index_heap=16384, dyna_carve=18432),
        c_library_code_bytes=lib_code, c_library_functions_sized=sum(1 for f in lib_funcs if f in sizes),
        new_core_api_entries=entries,
        files={f: dict(calls=c, sites=sum(c.values()),
                       core=sorted({CORE[k][0] for k in c})) for f, c in files.items()},
        total_sites=sum(sum(c.values()) for c in files.values()))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    print(f"{len(files)} files, {report['total_sites']} call sites; C library code "
          f"{lib_code} B; new core API entries: {', '.join(entries)}")
    for f, e in sorted(report['files'].items(), key=lambda x: -x[1]['sites']):
        print(f"{e['sites']:4} {f:24} {', '.join(sorted(e['calls']))}")


if __name__ == '__main__':
    main()
