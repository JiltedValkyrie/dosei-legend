#!/usr/bin/env python3
"""Split the real-Player frame bank into a resident set and demand groups.

Human directive 2026-10-06 (PLAYER_MIGRATION.md, "Demand-loaded Player
animation"): only clips current play can need stay loaded. Input is the
encoded bank (build_player_frame_bank.py: ALL.PFB, ids.json, scene_packs.json);
blocks are copied byte for byte, nothing is re-encoded.

Every clip id lands in exactly one file, so any set of these files registers
without duplicate ids:

  PLAYC.PFB      every clip the Saturn C cutscenes pose (build_link_model
                 CLIPS), resident from boot (the new-game opening needs only it)
  PLAYRES.PFB    the rest of the common set: loaded at the first scene load,
                 kept until the next file/level select (session reset)
  PG<name>.PFB   groups loaded at scene load (behind the loading screen):
                 HORSE (adult, horse scenes), SWIM (scenes with water boxes),
                 FISH (fishing pond); item groups BOTTLE, MAGIC, HAMMER, BOOM,
                 HOOK for items on C buttons, also loaded when the pause menu
                 closes. Player_UseItem refuses an item whose group is absent
                 (cold action waits; no mid-action CD read).
  PCS<id>.PFB    a scene's cutscene-only clips (every shot and branch of that
                 scene's cutscenes, pinned from scene load to scene unload)

Writes the files to --cd, build/generated/player_groups.h (host tables, in
cartridge HOST_COLD) and build/player-migration/player_groups.json (heap model).
"""
import argparse
import json
import re
import struct
import sys
from pathlib import Path

GAME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GAME / 'tools'))

# Group order is the bit order in the host/core mask (oot_core_api.h).
GROUPS = (
    ('HORSE', r'c?link_uma_'),
    ('SWIM', r'c?link_swimer_'),
    ('FISH', r'c?link_fishing_'),
    ('BOTTLE', r'c?link_bottle_'),
    ('MAGIC', r'c?link_magic_'),
    ('HAMMER', r'c?link_hammer_'),
    ('BOOM', r'c?link_boom_'),
    ('HOOK', r'c?link_hook_'),
)
# z_horse.c: scenes where Epona or a story horse can carry adult Link.
HORSE_SCENES = ('SCENE_HYRULE_FIELD', 'SCENE_LAKE_HYLIA', 'SCENE_GERUDO_VALLEY',
                'SCENE_GERUDOS_FORTRESS', 'SCENE_LON_LON_RANCH')
FISH_SCENES = ('SCENE_FISHING_POND',)
# Inventory items (include/item.h) -> item group, for the C buttons.
ITEM_GROUPS = {
    'ITEM_DINS_FIRE': 'MAGIC', 'ITEM_FARORES_WIND': 'MAGIC', 'ITEM_NAYRUS_LOVE': 'MAGIC',
    'ITEM_HAMMER': 'HAMMER', 'ITEM_BOOMERANG': 'BOOM',
    'ITEM_HOOKSHOT': 'HOOK', 'ITEM_LONGSHOT': 'HOOK',
}
BOTTLE_ITEMS = ('ITEM_BOTTLE_EMPTY', 'ITEM_BOTTLE_POE')    # inclusive range
CS_PACK = 0x100      # scene flag above every group bit


def read_bank(path):
    d = path.read_bytes()
    if d[:4] != b'PFB2':
        raise SystemExit('%s: not PFB2' % path)
    n = struct.unpack('>I', d[4:8])[0]
    offs = struct.unpack('>%dI' % n, d[8:8 + 4 * n])
    it = 8 + 4 * n
    ids = struct.unpack('>%dH' % n, d[it:it + 2 * n])
    blocks = {}
    for i, gid in enumerate(ids):
        end = offs[i + 1] if i + 1 < n else len(d) - 4
        blocks[gid] = d[offs[i]:end]
    return blocks


def pack_file(blocks, gids):
    """Same layout as build_player_frame_bank.pack_file."""
    gids = sorted(gids)
    head_len = 8 + 4 * len(gids) + ((2 * len(gids) + 3) & ~3)
    body, offsets = b'', []
    for g in gids:
        offsets.append(head_len + len(body))
        body += blocks[g]
    ids = struct.pack('>%dH' % len(gids), *gids)
    ids += bytes(-len(ids) % 4)
    return (b'PFB2' + struct.pack('>I', len(gids)) + struct.pack('>%dI' % len(gids), *offsets) +
            ids + body + bytes(4))


def enum_values(path, pattern):
    """/* 0xNN */ NAME rows of an include/*.h enum."""
    return {n: int(v, 16) for v, n in re.findall(r'/\*\s*0x([0-9A-Fa-f]+)\s*\*/\s*' + pattern, path.read_text())}


def split(oot, bank, cd, header, manifest):
    import build_link_model as blm
    bits = dict(re.findall(r'#define OOT_CORE_PLAYER_GROUP_(\w+) (\d+)',
                           (GAME / 'oot-core/include/oot_core_api.h').read_text()))
    if bits != {k: str(i) for i, (k, _) in enumerate(GROUPS)}:
        raise SystemExit('GROUPS order differs from oot_core_api.h OOT_CORE_PLAYER_GROUP_*')
    blocks = read_bank(bank / 'ALL.PFB')
    ids = json.loads((bank / 'ids.json').read_text())
    packs = json.loads((bank / 'scene_packs.json').read_text())
    forced = {sym for _, sym, *_ in blm.CLIPS}
    missing = forced - set(ids)
    if missing:
        raise SystemExit('C cutscene clips missing from the bank: %s' % sorted(missing))
    by_gid = {}
    for h, g in ids.items():
        by_gid.setdefault(g, []).append(h)
    if set(by_gid) != set(blocks):
        raise SystemExit('ids.json and ALL.PFB disagree')
    group_of = {}
    for g, heads in by_gid.items():
        tags = set()
        for h in heads:
            name = h[len('gPlayerAnim_'):]
            hit = [k for k, p in GROUPS if re.match(p, name)]
            tags.add('RES' if h in forced else hit[0] if hit else None)
        if len(tags) == 1 and None not in tags and 'RES' not in tags:
            group_of[g] = tags.pop()
    names = [k for k, _ in GROUPS]
    group_gids = {k: sorted(g for g, t in group_of.items() if t == k) for k in names}
    forced_gids = {g for g, heads in by_gid.items() if any(h in forced for h in heads)}

    scenes = re.findall(r'/\*\s*0x([0-9A-Fa-f]+)\s*\*/\s*DEFINE_SCENE\((\w+)_scene,\s*\w+,\s*(SCENE_\w+)',
                        (oot / 'include/tables/scene_table.h').read_text())
    scene_id = {folder: int(v, 16) for v, folder, _ in scenes}
    enum_id = {e: int(v, 16) for v, _, e in scenes}
    cs = {}
    needs = {}
    for folder, gids in packs.items():
        if folder not in scene_id:
            raise SystemExit('scene pack %s has no scene_table entry' % folder)
        own = sorted(set(gids) - forced_gids - set(group_of))
        need = {group_of[g] for g in gids if g in group_of}
        if own:
            cs[scene_id[folder]] = own
        if need:
            needs[scene_id[folder]] = need
    cs_gids = {g for v in cs.values() for g in v}
    resident = sorted(set(blocks) - set(group_of) - cs_gids)
    # Partition: every id in exactly one file family; CS packs only overlap
    # each other (one is loaded at a time).
    assert not (set(resident) & set(group_of)) and not (set(resident) & cs_gids)
    assert not (cs_gids & set(group_of)) and forced_gids <= set(resident)

    sroot = oot / 'extracted/ntsc-1.2/assets/scenes'
    water = set()
    for folder, sid in scene_id.items():
        hits = list(sroot.glob('*/%s/%s_scene.c' % (folder, folder)))
        if hits and re.search(r'^WaterBox \w+\[\]', hits[0].read_text(encoding='utf-8'), re.M):
            water.add(sid)
    count = max(scene_id.values()) + 1
    flags = [0] * count
    for sid in range(count):
        mask = 0
        if sid in water:
            mask |= 1 << names.index('SWIM')
        if sid in cs:
            mask |= CS_PACK                   # PCS<id>.PFB exists
        for g in needs.get(sid, ()):
            mask |= 1 << names.index(g)
        flags[sid] = mask
    horse = [enum_id[e] for e in HORSE_SCENES]
    fish = [enum_id[e] for e in FISH_SCENES]
    items = enum_values(oot / 'include/item.h', r'(ITEM_\w+)')
    item_rows = sorted((items[i], names.index(g)) for i, g in ITEM_GROUPS.items())
    bottles = (items[BOTTLE_ITEMS[0]], items[BOTTLE_ITEMS[1]])

    cd.mkdir(parents=True, exist_ok=True)
    sizes = {}
    c_clips = sorted(forced_gids)
    data = pack_file(blocks, c_clips)
    (cd / 'PLAYC.PFB').write_bytes(data)
    sizes['PLAYC.PFB'] = len(data)
    data = pack_file(blocks, sorted(set(resident) - forced_gids))
    (cd / 'PLAYRES.PFB').write_bytes(data)
    sizes['PLAYRES.PFB'] = len(data)
    for k in names:
        data = pack_file(blocks, group_gids[k])
        (cd / ('PG%s.PFB' % k)).write_bytes(data)
        sizes['PG%s.PFB' % k] = len(data)
    for old in cd.glob('PCS??.PFB'):
        old.unlink()
    for sid, gids in sorted(cs.items()):
        data = pack_file(blocks, gids)
        (cd / ('PCS%02X.PFB' % sid)).write_bytes(data)
        sizes['PCS%02X.PFB' % sid] = len(data)

    h = ['/* Generated by tools/split_player_bank.py: Player clip groups. */',
         '#ifndef PLAYER_GROUPS_H', '#define PLAYER_GROUPS_H',
         '#define PLAYER_GROUP_COUNT %d' % len(names)]
    h += ['#define PLAYER_GROUP_%s %d' % (k, i) for i, k in enumerate(names)]
    h += ['#define PLAYER_GROUP_CS_PACK 0x%Xu' % CS_PACK,
          '#define PLAYER_GROUP_SCENES %d' % count,
          '#define PLAYER_GROUP_BOTTLE_FIRST 0x%02Xu' % bottles[0],
          '#define PLAYER_GROUP_BOTTLE_LAST 0x%02Xu' % bottles[1],
          '#ifdef PLAYER_GROUPS_TABLES',
          '/* PG<name>.PFB in group-bit order. */',
          'static const char player_group_files[PLAYER_GROUP_COUNT][12] HOST_COLD = { %s };' %
          ', '.join('"PG%s.PFB"' % k for k in names),
          '/* Per OoT scene: bit g = group g required (water, cutscene clips), CS_PACK = PCS<id>.PFB. */',
          'static const unsigned short player_group_scene[PLAYER_GROUP_SCENES] HOST_COLD = {']
    for i in range(0, count, 16):
        h.append('    ' + ', '.join('0x%03X' % f for f in flags[i:i + 16]) + ',')
    h += ['};',
          'static const unsigned char player_group_horse_scenes[] HOST_COLD = { %s };' %
          ', '.join('0x%02X' % s for s in horse),
          'static const unsigned char player_group_fish_scenes[] HOST_COLD = { %s };' %
          ', '.join('0x%02X' % s for s in fish),
          '/* Inventory item id -> group (C buttons). */',
          'static const unsigned char player_group_items[][2] HOST_COLD = { %s };' %
          ', '.join('{ 0x%02X, %d }' % r for r in item_rows),
          '#endif', '#endif', '']
    header.parent.mkdir(parents=True, exist_ok=True)
    header.write_text('\n'.join(h))   # after the .PFB files: make orders on it
    report = {'groups': names, 'sizes': sizes, 'scene_flags': flags, 'horse_scenes': horse,
              'fish_scenes': fish, 'item_groups': {str(a): names[b] for a, b in item_rows},
              'bottle_items': list(bottles), 'scene_ids': scene_id,
              'resident_clips': len(resident), 'group_clips': {k: len(v) for k, v in group_gids.items()},
              'cs_packs': {('%02X' % k): len(v) for k, v in cs.items()},
              'all_bytes': (bank / 'ALL.PFB').stat().st_size}
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(report, indent=1) + '\n')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--oot', type=Path, required=True)
    ap.add_argument('--bank', type=Path, default=GAME / 'build/player-migration/bank_full')
    ap.add_argument('--cd', type=Path, default=GAME / 'build/cd')
    ap.add_argument('--header', type=Path, default=GAME / 'build/generated/player_groups.h')
    ap.add_argument('--manifest', type=Path, default=GAME / 'build/player-migration/player_groups.json')
    args = ap.parse_args()
    r = split(args.oot, args.bank, args.cd, args.header, args.manifest)
    s = r['sizes']
    print('Player bank split: C clips %d B + common %d B (%d clips) of %d; groups %s; %d scene cutscene packs, max %d B' % (
        s['PLAYC.PFB'], s['PLAYRES.PFB'], r['resident_clips'], r['all_bytes'],
        ', '.join('%s %d' % (k, s['PG%s.PFB' % k]) for k in r['groups']),
        len(r['cs_packs']), max([v for k, v in s.items() if k.startswith('PCS')] or [0])))


if __name__ == '__main__':
    main()
