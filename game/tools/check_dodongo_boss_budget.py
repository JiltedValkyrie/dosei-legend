"""Conservative whole-arena render budget, including source boss and rewards.

Counts every admitted/resident mesh, all 32 source sprite/effect view slots,
all four bomb flowers, both portal draws and every child tool sheet. No
visibility culling or mutually exclusive fight/reward phases are assumed.
"""
import argparse
import json
from pathlib import Path
import re
import struct

import build_sgl_scene as sgl
from check_forest_budget import mesh_cost
import oot_core_import as imp
import scene_pack_actors as packs
import vdp1_budget as budget


def check(game, oot, cd, core, room):
    scene = oot/'extracted/ntsc-1.2/assets/scenes/dungeons/ddan_boss/ddan_boss_scene.c'
    actors = {packs.enum(n) for n in packs.scene_pack(scene, packs.child_spawns(oot))}
    enums, _ = imp.object_ids(oot)
    built_ids = {int(p.stem[1:4], 16) for p in (core/'objects').glob('O*_ph.txt')}
    objects = set(imp.scene_objects(scene, built_ids, enums, oot))
    required = {'ACTOR_BOSS_DODONGO', 'ACTOR_EN_BDFIRE', 'ACTOR_DOOR_WARP1',
                'ACTOR_ITEM_B_HEART', 'ACTOR_EN_BOMBF', 'ACTOR_BG_BREAKWALL'}
    if not required <= actors:
        raise ValueError('Boss actor closure incomplete: ' + repr(required-actors))
    costs, draw = {}, {}
    pattern = r'\{\s*(\d+),\s*(0x[0-9A-F]+),\s*(\d+),\s*(ACTOR_\w+)\s*\}'
    for kind, obj, index, actor in re.findall(pattern, (core/'generic_meshes.h').read_text()):
        kind, obj, index = int(kind), int(obj, 16), int(index)
        if actor not in actors or (kind and obj not in objects):
            continue
        name = 'Q%03X%02X.MSH' % (obj, index) if kind else 'K%03X.MSH' % index
        data, header, _, _ = sgl.read_scene(cd/name)
        costs[name] = mesh_cost(cd/name)
        # All chest variants and the falling stair (room0) remain included.
        # Four bomb flowers, two portal layers; other mesh lists once each.
        copies = 4 if actor == 'ACTOR_EN_BOMBF' else 2 if actor == 'ACTOR_DOOR_WARP1' else 1
        draw[name] = header['ntris'] * copies
    expected_boss = json.loads((core/'kingdodongo_meshes.json').read_text())
    if len(expected_boss) != 20 or any(r['file'] not in costs for r in expected_boss):
        raise ValueError('Complete boss limb set is not resident')
    if len(costs) > 40:
        raise ValueError('Core mesh count exceeds resident 40 slots')
    magic, vertices, faces, tiles, pixels, *_ = struct.unpack_from('>8I', room.read_bytes())
    if magic != 0x4b524d31:
        raise ValueError('Boss room is not KRM1')
    hero = sgl.link_actor_budget(game/'build/generated/LINK.BIN')
    hero_bytes = sum(budget.tile_bytes(w, h) for w, h in hero['tiles'])
    # Bdfire uses the actual eight source fire textures at 32x32. No other
    # sprite actor object is listed by this scene; fail if that ever changes.
    _, symbols = imp.object_ids(oot)
    extra_sprites = {symbols[n] for n in imp.SPRITE_OBJECTS if n in symbols} & objects
    if extra_sprites:
        raise ValueError('Boss scene gains sprite objects needing budget: ' + repr(extra_sprites))
    source_sprites = 32 * budget.tile_bytes(32, 32)
    # Even a save importing boomerang/bombchus retains a complete child set.
    tool_costs = []
    for name in ('ITMBOM.SPR', 'ITMCHU.SPR', 'ITMBOO.SPR', 'ITMEXP.SPR'):
        sheet = (cd/name).read_bytes()
        if sheet[:4] != b'SPR1':
            raise ValueError('Invalid child tool sprite: ' + name)
        tool_costs.append(budget.tile_bytes(*struct.unpack_from('>HH', sheet, 4)))
    used = (budget.bank_bytes(pixels, tiles) + hero_bytes + budget.RUNTIME_SPRITE_BYTES +
            sum(c[0] for c in costs.values()) + source_sprites + sum(tool_costs))
    slots = (1 + tiles + len(hero['tiles']) + budget.RUNTIME_SPRITE_SLOTS +
             sum(c[1] for c in costs.values()) + 32 + len(tool_costs))
    # 32 view effects, 32 source sprites, four tool sprites; 64 extra commands
    # for HUD, held items, particles and targeting beyond the full hero model.
    polygons = faces + hero['polygons'] + sum(draw.values()) + 32 + 32 + 4 + 64
    report = dict(room=str(room), room_faces=faces, room_pixels=pixels,
                  meshes=len(costs), mesh_bytes=sum(c[0] for c in costs.values()),
                  vram_bytes=used, vram_limit=budget.VDP1_USER_AREA,
                  reserve_bytes=budget.FOREST_VRAM_MARGIN, sprite_slots=slots,
                  sprite_limit=budget.MAX_SPRITE_SLOTS, polygons=polygons,
                  polygon_limit=budget.MAX_POLYGONS, mesh_draw=draw)
    if (used + budget.FOREST_VRAM_MARGIN > budget.VDP1_USER_AREA or
            slots > budget.MAX_SPRITE_SLOTS or polygons > budget.MAX_POLYGONS):
        raise ValueError('Boss combined render budget failed: ' + json.dumps(report))
    print(json.dumps(report, indent=2))
    return report


if __name__ == '__main__':
    game = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, required=True)
    parser.add_argument('--cd', type=Path, default=game/'build/cd')
    parser.add_argument('--core', type=Path, default=game/'build/oot-core')
    parser.add_argument('--room', type=Path, default=game/'build/dodongo-route/room-probe/SGR1.MSH')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = check(game, args.oot, args.cd, args.core, args.room)
    if args.report:
        args.report.write_text(json.dumps(result, indent=2) + '\n')
