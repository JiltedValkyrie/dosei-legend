#!/usr/bin/env python3
"""Source-backed enemy inventory and fail-closed content admission.

Generation inventories unimplemented content; --require-ready is the build
admission gate. Candidate closures do not prove branch reachability or peaks.
No actor is imported, compiled or enabled by this tool.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re

import build_actor_coverage as coverage
import oot_core_import as imp

GAME = Path(__file__).resolve().parents[1]
HAZARDS = {'En_Trap', 'Bg_Haka_Sgami', 'En_Honotrap', 'En_Arow_Trap',
           'En_Tubo_Trap', 'Door_Killer', 'En_Ice_Hono', 'En_Yukabyun', 'En_Fire_Rock'}
SPAWNERS = {'En_Encount1', 'En_Encount2', 'Obj_Roomtimer', 'En_Anubice_Tag'}
PROPS = {'Bg_Po_Event', 'Bg_Po_Syokudai', 'Bg_Bdan_Objects', 'En_Wood02',
         'Obj_Kibako2', 'Obj_Makekinsuta'}
CHILDREN = {'En_Nutsball', 'En_Skjneedle', 'En_Anubice_Fire', 'En_Fd_Fire',
            'En_Si', 'En_Part'}
GATED = {'En_Wallmas', 'En_Floormas', 'En_Rd', 'En_Rr', 'En_Dh', 'En_Dha',
         'En_GeldB', 'En_Skj', 'En_Mb'}
BODYBREAK = {'En_Bb', 'En_Sb', 'En_Skb', 'En_Test', 'En_Tite'}
EXTRA = HAZARDS | SPAWNERS | PROPS | CHILDREN | GATED | {'En_Sw'}
# Human-approved registration scope, distinct from broader source candidates.
REGISTER_SCENES = {'ddan', 'bdan', 'Bmori1', 'HIDAN', 'MIZUsin', 'jyasinzou',
                   'HAKAdan', 'ice_doukutu', 'ganon', 'men', 'ganontika',
                   'ganon_final', 'kakusiana', 'hakasitarelay', 'spot07',
                   'spot08', 'spot09', 'spot11', 'spot13', 'spot16'}
HOOKS = re.compile(r'\b(?:Play_TriggerRespawn|Player_SetCsAction\w*|'
                   r'Inventory_DeleteEquipment|PLAYER_STATE2_7)\b')
SFX_CALL = re.compile(r'\b(?:Actor_PlaySfx\w*|Audio_PlayActorSfx\w*|'
                      r'Audio_PlaySfx\w*|EffectSsDeadSound_\w+)\s*\(')
EFFECT_CALL = re.compile(r'\b(EffectSs\w+)\s*\(')
SFX_TABLE = re.compile(r'/\*\s*(0x[0-9A-Fa-f]+)\s*\*/\s*DEFINE_SFX\('
                       r'(\w+),\s*(NA_SE_\w+),\s*([^,]+),')


def classify(actor):
    symbol = actor['symbol']
    if actor['category'] == 'ACTORCAT_BOSS':
        return 'boss_exempt'
    if symbol in HAZARDS:
        return 'hazard_geometry'
    if symbol in SPAWNERS:
        return 'logic_spawner'
    if symbol in PROPS:
        return 'spawner_prop_geometry'
    if symbol in CHILDREN:
        return 'sprite_child'
    if actor['category'] == 'ACTORCAT_ENEMY' or symbol in EXTRA:
        return 'sprite_enemy'
    return 'dependency_review'


def sfx_table(oot):
    result = {}
    for path in sorted((oot / 'include/tables/sfx').glob('*_table.h')):
        for match in SFX_TABLE.finditer(path.read_text(encoding='utf-8')):
            ident, channel, symbol, priority = match.groups()
            result[symbol] = {'id': int(ident, 16), 'channel': channel,
                              'priority': priority.strip()}
    return result


def sites(text, pattern):
    result = []
    for match in pattern.finditer(text):
        args = coverage.call_args(text, match.end())
        result.append({'line': text.count('\n', 0, match.start()) + 1,
                       'call': match[0].split('(')[0].strip(),
                       'arguments': args})
    return result


def params(entry):
    fields = coverage.call_args(entry.strip()[1:-1] + ')', 0)
    expression = [field for field in fields if field][-1]
    try:
        value = int(expression, 0) & 0xFFFF
    except ValueError:
        value = None
    return expression, value


def player_gate(symbol, value=None):
    if symbol in GATED:
        return 'real_player_cutover'
    if symbol == 'En_Am':
        # z_en_am.h ARMOS_STATUE == 0; other params are the enemy.
        return 'real_player_cutover' if value == 0 else (
            'params_review' if value is None else None)
    return None


def effect_types(oot):
    """Associate public spawn wrappers with their explicit EffectSs type.

    Wrapper-to-wrapper calls and actor-private helpers remain named candidates;
    only explicit source types are claimed as resolved.
    """
    result = {}
    path = oot / 'src/code/z_effect_soft_sprite_old_init.c'
    text = coverage.uncomment(path.read_text(encoding='utf-8'))
    starts = list(re.finditer(r'\bvoid\s+(EffectSs\w+)\s*\([^;]*?\)\s*\{', text))
    for i, match in enumerate(starts):
        body = text[match.end(): starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        result[match[1]] = sorted(set(re.findall(r'\bEFFECT_SS_[A-Z0-9_]+\b', body)))
    return result


def actor_record(key, actor, oot, sounds, effects):
    text = (oot / actor['source']).read_text(encoding='utf-8') if actor['source'] else ''
    clean = coverage.uncomment(text)
    sound_sites = sites(clean, SFX_CALL)
    symbols = sorted(set(re.findall(r'\bNA_SE_[A-Z0-9_]+\b', clean)))
    fx = sites(clean, EFFECT_CALL)
    hooks = [{'line': clean.count('\n', 0, m.start()) + 1, 'symbol': m[0]}
             for m in HOOKS.finditer(clean)]
    result = {name: actor.get(name) for name in
              ('id', 'symbol', 'category', 'profile_declared_id', 'source',
               'source_sha256', 'profile_instance_size', 'object', 'object_id',
               'spawn_calls', 'spawn_dependencies', 'drop_sites', 'boss_dependency_of')}
    result.update(actor=key, classification=classify(actor),
                  classification_reason=('decomp ACTORCAT_BOSS' if actor['category'] == 'ACTORCAT_BOSS'
                                         else 'human enemy/hazard scope and decomp category'),
                  player_gate=player_gate(actor['symbol']), player_hook_sites=hooks,
                  bodybreak_wait=actor['symbol'] in BODYBREAK,
                  bodybreak_contract=('revival_counter_and_delay' if actor['symbol'] == 'En_Test'
                                      else 'head_break_and_death' if actor['symbol'] == 'En_Skb'
                                      else 'death_completion' if actor['symbol'] in BODYBREAK else None),
                  object_candidates=sorted(set(re.findall(r'\bOBJECT_[A-Z0-9_]+\b', clean))),
                  effect_calls=fx,
                  effect_types=sorted({typ for site in fx for typ in effects.get(site['call'], [])}),
                  unresolved_effect_calls=sorted({site['call'] for site in fx
                                                 if not effects.get(site['call'])}),
                  sfx=[dict(symbol=s, **sounds.get(s, {'id': None})) for s in symbols],
                  sfx_calls=sound_sites,
                  instance_bytes=None,
                  wave='W3' if player_gate(actor['symbol']) else 'scene_wave',
                  verification={'inventory_generated': True, 'implemented': False,
                                'target_built': False, 'human_accepted': False})
    return result


def effective_layer(layers, index):
    """Match Scene_CommandAlternateHeaderList, including adult-night fallback."""
    if index < len(layers) and layers[index]['present']:
        return index, layers[index]
    if index == 3 and len(layers) > 2 and layers[2]['present']:
        return 2, layers[2]
    return 0, layers[0]


def room_record(scene, room, index, layer, rows, actors):
    all_roots = [p['actor'] for p in layer['placements']]
    reached = coverage.closure(all_roots, actors)
    scoped = sorted(a for a in reached if a in rows)
    placements = []
    for placement in layer['placements']:
        key = placement['actor']
        if key not in rows:
            continue
        expression, value = params(placement['entry'])
        placements.append(dict(placement, params_expression=expression, params_u16=value,
                               player_gate=player_gate(rows[key]['symbol'], value)))
    counts = dict(sorted(Counter(p['actor'] for p in placements).items()))
    unknown = [dict(actor=a, **edge) for a in reached for edge in actors.get(a, {}).get('spawn_calls', [])
               if edge['resolution'] == 'review_indirect']
    # Ordinary NPCs can summon enemies; preserve the complete root-to-enemy
    # graph rather than starting closure at enemy-category placements only.
    spawners = sorted(a for a in reached if a not in rows and
                      any(d in scoped for d in coverage.closure([a], actors)))
    return {'scene': scene['prefix'], 'room': room['room'], 'layer': index,
            'era_time': coverage.LAYERS[index] if index < 4 else 'cutscene_setup',
            'source_layer': layer['layer'], 'all_placement_count': len(all_roots),
            'placements': placements, 'reachable_actor_candidates': scoped,
            'non_enemy_spawner_candidates': spawners,
            'objects': sorted({rows[a]['object_id'] for a in scoped if rows[a]['object_id'] is not None}),
            'sfx_ids': sorted({s['id'] for a in scoped for s in rows[a]['sfx'] if s['id'] is not None}),
            'effect_types': sorted({e for a in scoped for e in rows[a]['effect_types']}),
            'unknown_spawn_calls': unknown,
            'budget': {'placed_instances_by_actor': counts, 'placed_kind_count': len(counts),
                       'candidate_kind_count': len(scoped), 'peak_instances': None,
                       'zelda_arena_bytes': None, 'tha_bytes': None,
                       'reason': 'compiled sizes, dynamic multiplicity, resident/adjacent-room overlap unresolved'},
            'ready': False}


def validate(roster, require_ready=()):
    failures = []
    rows = roster['actors']
    actual = sorted(k for k, a in rows.items() if a['classification'] == 'boss_exempt')
    if actual != sorted(roster['source_boss_set']):
        failures.append('boss set differs from source ACTORCAT_BOSS profiles')
    for key, actor in rows.items():
        if actor['category'] == 'ACTORCAT_ENEMY' and actor['classification'] == 'dependency_review':
            failures.append('unclassified enemy: ' + key)
        for edge in actor['spawn_calls']:
            for target in edge['targets']:
                if target not in roster['known_actor_ids']:
                    failures.append('unknown spawn target: ' + target)
    scenes = {s['prefix']: s for s in roster['scenes']}
    for prefix in require_ready:
        scene = scenes.get(prefix)
        if scene is None:
            failures.append('unknown enemy scene: ' + prefix)
            continue
        for room in scene['rooms']:
            name = f"{prefix}/{room['room']}/layer{room['layer']}"
            if room['unknown_spawn_calls']:
                failures.append(name + ': unresolved spawn target expression')
            if room['budget']['peak_instances'] is None or room['budget']['zelda_arena_bytes'] is None:
                failures.append(name + ': unmeasured actor peak/size')
            elif room['budget']['zelda_arena_bytes'] > 0x20000:
                failures.append(name + ': ZeldaArena exceeds 131072 bytes')
            if room['budget']['tha_bytes'] is None or room['budget']['tha_bytes'] > 0x30000:
                failures.append(name + ': THA unmeasured or exceeds 196608 bytes')
        if not scene['ready']:
            failures.append(prefix + ': content/runtime acceptance incomplete')
    return failures


def build(ledger, oot):
    actors = ledger['actors']
    sounds, effects = sfx_table(oot), effect_types(oot)
    wanted = {key for key, actor in actors.items()
              if actor['category'] in ('ACTORCAT_ENEMY', 'ACTORCAT_BOSS') or actor['symbol'] in EXTRA}
    rows = {key: actor_record(key, actors[key], oot, sounds, effects) for key in sorted(wanted)}
    scenes = []
    for scene in ledger['scenes']:
        rooms = []
        for room in scene['rooms']:
            for index in range(max(4, len(room['layers']))):
                _, layer = effective_layer(room['layers'], index)
                record = room_record(scene, room, index, layer, rows, actors)
                if record['reachable_actor_candidates']:
                    rooms.append(record)
        if rooms:
            scenes.append({'id': scene['id'], 'prefix': scene['prefix'], 'scene': scene['scene'],
                           'runtime_index': scene['runtime_index'], 'rooms': rooms, 'ready': False})
    result = {'format_version': 1, 'source_version': imp.VERSION,
              'source_revision': ledger.get('source_revision', 'unknown'),
              'semantics': 'conservative source candidates; no runtime admission or simultaneous-peak claim',
              'known_actor_ids': sorted(actors),
              'source_boss_set': sorted(k for k, a in actors.items() if a['category'] == 'ACTORCAT_BOSS'),
              'actors': rows, 'scenes': scenes,
              'approved_registration_scenes': sorted(REGISTER_SCENES),
              'additional_unregistered_candidates': [
                  {'prefix': s['prefix'], 'scene': s['scene'],
                   'status': 'inventory only; outside the approved 20 registrations'}
                  for s in scenes if s['runtime_index'] is None and s['prefix'] not in REGISTER_SCENES],
              'limits': {'zelda_arena_bytes': 0x20000, 'tha_bytes': 0x30000,
                         'dyna_polygons': 512, 'dyna_vertices': 512, 'dyna_nodes': 1000},
              'summary': {'actors': len(rows), 'bosses': sum(a['classification'] == 'boss_exempt' for a in rows.values()),
                          'scenes': len(scenes), 'unregistered_scenes': sum(s['runtime_index'] is None for s in scenes),
                          'room_layers': sum(len(s['rooms']) for s in scenes), 'ready_scenes': 0}}
    errors = validate(result)
    if errors:
        raise ValueError('; '.join(errors))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--coverage', type=Path, default=GAME / 'docs/ACTOR_COVERAGE.json')
    parser.add_argument('--out', type=Path, default=GAME / 'docs/ENEMY_ROSTER.json')
    parser.add_argument('--require-ready', action='append', default=[])
    args = parser.parse_args()
    ledger_bytes = args.coverage.read_bytes()
    result = build(json.loads(ledger_bytes), args.oot)
    result['coverage_sha256'] = hashlib.sha256(ledger_bytes).hexdigest()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary']))
    failures = validate(result, args.require_ready)
    if failures:
        raise SystemExit('enemy admission blocked:\n' + '\n'.join(failures))


if __name__ == '__main__':
    main()
