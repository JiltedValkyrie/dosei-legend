#!/usr/bin/env python3
"""Source-backed whole-game actor coverage inventory; unknown never means absent.

Static candidates are deliberately not a reachability proof. Indirect spawn IDs,
category changes, story predicates and native C implementations require review.
No scene becomes ready from successful extraction or the presence of text files.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess

import oot_core_import as imp

GAME = Path(__file__).resolve().parents[1]
PROFILE = re.compile(r'ActorProfile\s+(\w+)\s*=\s*\{(.*?)\};', re.S)
TABLE = re.compile(r'/\*\s*(0x[\dA-Fa-f]+)\s*\*/\s*DEFINE_ACTOR(?:_INTERNAL)?\((\w+),\s*(ACTOR_\w+)')
SCENES = re.compile(r'/\*\s*(0x[\dA-Fa-f]+)\s*\*/\s*DEFINE_SCENE\((\w+)_scene,\s*\w+,\s*(SCENE_\w+)')
SPAWN = re.compile(r'\b(Actor_Spawn(?:AsChild|AsChildAndCutscene|Entry)?|Actor_SpawnTransitionActors)\s*\(')
CHARACTERS = {'ACTOR_EN_HORSE', 'ACTOR_EN_HORSE_NORMAL', 'ACTOR_EN_HORSE_LINK_CHILD',
              'ACTOR_EN_HORSE_GANON', 'ACTOR_EN_HORSE_ZELDA', 'ACTOR_EN_ELF',
              'ACTOR_EN_NIW', 'ACTOR_EN_COW', 'ACTOR_EN_BUTTE', 'ACTOR_EN_FISH',
              'ACTOR_EN_INSECT', 'ACTOR_EN_DOG', 'ACTOR_EN_FU', 'ACTOR_EN_TK',
              'ACTOR_BG_DY_YOSEIZO', 'ACTOR_EN_KAKASI', 'ACTOR_EN_KAKASI2', 'ACTOR_EN_KAKASI3'}
LAYERS = ['child_day', 'child_night', 'adult_day', 'adult_night']


def uncomment(text):
    # Preserve source locations for every generated call-site reference.
    return re.sub(r'/\*.*?\*/|//[^\n]*',
                  lambda match: re.sub(r'[^\n]', ' ', match[0]), text, flags=re.S)


def call_args(text, start):
    """Balanced call arguments, retaining expressions for unresolved actor IDs."""
    level, out, first = 1, [], start
    for pos in range(start, len(text)):
        c = text[pos]
        if c in '([{':
            level += 1
        elif c in ')]}':
            level -= 1
            if not level:
                out.append(text[first:pos].strip())
                return out
        elif c == ',' and level == 1:
            out.append(text[first:pos].strip())
            first = pos + 1
    raise ValueError('unterminated source call')


def spawn_edges(text, path):
    edges = []
    for match in SPAWN.finditer(text):
        args = call_args(text, match.end())
        index = 3 if 'AsChild' in match[1] else 2
        expr = args[index] if index < len(args) else '<transition table>'
        targets = sorted(set(re.findall(r'\bACTOR_[A-Z0-9_]+\b', expr)))
        direct = len(targets) == 1 and expr == targets[0]
        resolution = 'direct' if direct else 'review_indirect'
        if re.fullmatch(r'[A-Za-z_]\w*', expr) and not direct:
            # Source-backed finite local id assignments (En_Encount1's
            # spawnId, for example). Unknown writes keep the gate unresolved.
            assignments = re.findall(r'\b' + re.escape(expr) + r'\s*=\s*([^;]+);', text)
            if assignments and all(re.fullmatch(r'ACTOR_[A-Z0-9_]+', a.strip()) for a in assignments):
                targets = sorted({a.strip() for a in assignments})
                resolution = 'finite_source_assignments'
        edges.append({'line': text.count('\n', 0, match.start()) + 1,
                      'call': match[1], 'actor_expression': expr,
                      'targets': targets, 'resolution': resolution,
                      'source': path})
    return edges


def actor_placements(text):
    """Read complete ActorEntry initializers, including multiline params/rotations."""
    rows, depth, start = [], 0, 0
    clean = uncomment(text)
    for pos, char in enumerate(clean):
        # Walk the comment-free copy, whose indices are used below.
        if char == '{':
            if depth == 0:
                start = pos
            depth += 1
        elif char == '}':
            depth -= 1
            if depth == 0:
                rows.append((start, pos + 1))
    result = []
    for start, end in rows:
        row = clean[start:end]
        actor = re.search(r'\bACTOR_[A-Z0-9_]+\b', row)
        if actor:
            result.append({'actor': actor[0], 'entry': ' '.join(row.split())})
    return result


def condition_sites(text):
    """Keep complete source gate expressions; do not try to execute C in Python."""
    result = []
    for match in re.finditer(r'\bif\s*\(', text):
        args = call_args(text, match.end())
        expression = ', '.join(args)
        if re.search(r'Flags_|GET_|CHECK_|IS_|LINK_|params|sceneId|sceneLayer|msgCtx|inventory|stateFlags', expression):
            result.append({'line': text.count('\n', 0, match.start()) + 1,
                           'expression': ' '.join(expression.split())})
    return result


def closure(roots, actors):
    found, pending = set(roots), list(roots)
    while pending:
        actor = actors.get(pending.pop(), {})
        for target in actor.get('spawn_dependencies', []):
            if target not in found:
                found.add(target)
                pending.append(target)
    return sorted(found)


def sheets(rows, folder):
    result = {}
    if rows and len(rows[0]) >= 5:
        from build_sprite_keys import groups
        symbols = (GAME / 'build/oot-core/obj_syms.ld').read_text(encoding='utf-8')
        for index, ((oid, skeleton), clips) in enumerate(groups(rows, symbols).items()):
            name = 'G%03X%02X.SP2' % (oid, index)
            path = folder / name
            record = {'object_id': oid, 'skeleton_key': skeleton, 'package': name,
                      'clips': [clip[2] for clip in clips],
                      'status': 'baked' if path.is_file() else 'missing'}
            if path.is_file():
                blob = path.read_bytes()
                if len(blob) < 16:
                    raise ValueError('invalid sprite archive: ' + name)
                magic, version, count, key, size = struct.unpack_from('>4sHHII', blob)
                if (magic != b'SPR2' or version != 2 or count != len(clips) or key != skeleton or
                        size != len(blob) or count > (len(blob) - 16) // 12):
                    raise ValueError('invalid sprite archive: ' + name)
                max_cel = 0
                for slot, (animation, _, _) in enumerate(clips):
                    anim, offset, length = struct.unpack_from('>III', blob, 16 + slot * 12)
                    if anim != animation or offset < 16 + count * 12 or length < 52 or offset + length > len(blob):
                        raise ValueError('invalid sprite archive clip: ' + name)
                    sheet = blob[offset:offset + length]
                    if sheet[:4] != b'SPR1':
                        raise ValueError('invalid sprite archive clip: ' + name)
                    width, height = struct.unpack_from('>2H', sheet, 4)
                    max_cel = max(max_cel, ((width * height // 2 + 31) & ~31) + 32)
                record.update(cart_bytes=len(blob) + 1, vdp1_instance_bytes=max_cel,
                              sha256=hashlib.sha256(blob).hexdigest())
            result.setdefault(oid, []).append(record)
        return result
    for row in rows:
        oid, limbs, clip, key = row[:4]
        name = f'G{oid:03X}{key:02X}.SPR'
        path = folder / name
        record = {'object_id': oid, 'limbs': limbs, 'clip': clip, 'package': name,
                  'status': 'baked' if path.is_file() else 'missing'}
        if path.is_file():
            blob = path.read_bytes()
            if blob[:4] != b'SPR1' or len(blob) < 52:
                raise ValueError(f'invalid sprite package: {name}')
            width, height, dirs, poses, ticks = struct.unpack_from('>5H', blob, 4)
            record.update(width=width, height=height, directions=dirs, poses=poses,
                          ticks=ticks, cart_bytes=len(blob) + 1,
                          vdp1_instance_bytes=((width * height // 2 + 31) & ~31) + 32,
                          sha256=hashlib.sha256(blob).hexdigest())
        result.setdefault(oid, []).append(record)
    return result


def build(oot, asset_root, sprite_rows=(), sprite_dir=None, registrations=(), horse_rows=()):
    enums, _ = imp.object_ids(oot)
    packages = sheets(sprite_rows, sprite_dir or GAME / 'build/cd')
    profiles = {}
    sources = {}
    for path in sorted((oot / 'src').rglob('*.c')):
        text = path.read_text(encoding='utf-8')
        if 'ActorProfile ' not in text:
            continue
        rel = path.relative_to(oot).as_posix()
        for match in PROFILE.finditer(text):
            fields = [v.strip() for v in uncomment(match[2]).split(',')]
            if len(fields) >= 9:
                # Some source profiles deliberately contain a different actor
                # id (En_Goma says BOSS_GOMA). The overlay table's symbol is
                # authoritative; indexing by that field overwrites real bosses.
                profiles[match[1].removesuffix('_Profile')] = (fields, rel, text)
        sources[rel] = text
    field_sources = set(imp.field_enemy_sources.SOURCES)
    # Scene-pack actors (scene_pack_actors): PACK_ACTORS load wherever their
    # scene lists them; SOURCE_ACTORS only in source-owned scenes.
    spa = imp.scene_pack_actors
    route_sources = {spa.source(n) for n in spa.SOURCE_ACTORS}
    route_scope = sorted(int(m[1], 16) for m in SCENES.finditer(
        (oot / 'include/tables/scene_table.h').read_text(encoding='utf-8')) if m[2] in spa.SOURCE_SCENES)
    imported = set(imp.SOURCES) | field_sources | set(spa.SOURCES)
    generic = {actor for actor, _ in imp.GENERIC_NPC_SOURCES}
    generic.update('ACTOR_' + name.upper() for name in imp.field_enemy_sources.ACTORS[1:])
    actors = {}
    table = (oot / 'include/tables/actor_table.h').read_text(encoding='utf-8')
    actor_enums = {m[3] for m in TABLE.finditer(table)}
    for match in TABLE.finditer(table):
        aid, symbol, enum = match.groups()
        fields, rel, text = profiles.get(symbol, ([], None, ''))
        category = fields[1] if fields else None
        obj = fields[3] if fields else None
        oid = enums.get(obj)
        edges = spawn_edges(text, rel) if rel else []
        # Direct spawn edges plus all actor constants conservatively cover table
        # candidates. References are labelled as candidates, not proven spawns.
        candidates = sorted((set(re.findall(r'\bACTOR_[A-Z0-9_]+\b', text)) & actor_enums) - {enum})
        deps = sorted({t for edge in edges for t in edge['targets']})
        if any(e['resolution'] == 'review_indirect' for e in edges):
            deps = sorted(set(deps + candidates))
        if enum == 'ACTOR_PLAYER':
            policy = 'link_separate'
        elif category == 'ACTORCAT_BOSS':
            policy = 'boss_exempt_preserve_complex_hitboxes'
        elif category in ('ACTORCAT_NPC', 'ACTORCAT_ENEMY') or enum in CHARACTERS:
            policy = 'sprite_required'
        else:
            policy = 'classification_review_required'
        own_packages = packages.get(oid, []) if enum in generic else []
        anims = sorted(set(re.findall(r'\b\w+(?:Anim|Animation)\b', text)))
        predicates = sorted(set(re.findall(r'\b(?:EVENTCHKINF_\w+|INFTABLE_\w+|EVENTINF_\w+|SCENE_\w+|LINK_IS_\w+|IS_DAY|IS_NIGHT|IS_CUTSCENE_LAYER)\b', text)))
        status = 'decomp_imported' if rel in imported else 'not_imported_native_owner_requires_review'
        blockers = []
        if policy == 'classification_review_required':
            blockers.append('visual classification unresolved; category is not an exemption')
        if status != 'decomp_imported':
            blockers.append('gameplay owner / native parity not verified')
        if policy == 'sprite_required' and not own_packages:
            blockers.append('sprite recipe/package mapping unverified or missing')
        if any(e['resolution'] == 'review_indirect' for e in edges):
            blockers.append('indirect spawn expression requires source/runtime review')
        blockers.append('era/time/params/story/dialogue/reward/persistence scenarios not accepted')
        actors[enum] = {'id': int(aid, 16), 'symbol': symbol, 'category': category,
                       'profile_declared_id': fields[0] if fields else None,
                       'profile_instance_size': fields[4] if fields else None,
                       'object': obj, 'object_id': oid, 'source': rel,
                       'source_sha256': hashlib.sha256(text.encode()).hexdigest(),
                       'visual_policy': policy, 'gameplay_owner': status,
                       'scene_pack_scope': [81] if rel in field_sources else
                                           route_scope if rel in route_sources else None,
                       'clip_candidates': anims, 'source_predicates': predicates,
                       'source_condition_sites': condition_sites(text),
                       'dialogue_reward_sites': [
                           {'line': line, 'expression': value.strip()}
                           for line, value in enumerate(text.splitlines(), 1)
                           if re.search(r'\b(?:Actor_Offer(?:Talk|GetItem)\w*|Message_(?:Start|Continue)Textbox|'
                                        r'SET_EVENTCHKINF|SET_INFTABLE|SET_ITEMGETINF|Flags_Set\w+)\s*\(', value)],
                       'drop_sites': [
                           {'line': line, 'expression': value.strip()}
                           for line, value in enumerate(text.splitlines(), 1)
                           if re.search(r'\b(?:Item_DropCollectible\w*|Actor_OfferGetItem\w*)\s*\(', value)],
                       'spawn_calls': edges, 'spawn_dependencies': deps,
                       'actor_reference_candidates': candidates,
                       'sprite_packages': own_packages,
                       'offline_horse_packages': [r for r in horse_rows if r['actor'] == enum],
                       'category_changes': sorted(set(re.findall(r'Actor_ChangeCategory\([^;]*?\b(ACTORCAT_\w+)\b', text))),
                       'timing_events': 'original action clock; clip events need per-actor review',
                       'collider_attachment_recipe': 'review_required',
                       'verification': {'implemented': rel in imported, 'host_tested': False,
                                        'target_built': False, 'human_accepted': False},
                       'blockers': blockers}
    for enum, extra in {
        'ACTOR_EN_HORSE_NORMAL': [
            'original action math needs bounded 32-bit lowering before import',
            'Skin init/free must become allocation-free clip clock',
            'head sphere registration moves from draw into gameplay update',
            'HORSE_WAIT_CLONE needs two source Ranch clones and stable clones, collision and sound'],
        'ACTOR_EN_HORSE_LINK_CHILD': [
            'original action math / Horse_RotateToPoint need bounded 32-bit lowering before import',
            'Skin init/free and head sphere need clock/anchor bridge',
            'Talon-return and Epona-song events plus song response/re-entry remain unverified'],
        'ACTOR_EN_HORSE': [
            'original action math needs bounded 32-bit lowering before import',
            'jointTable root-y jump reads need small offline timing/height descriptors',
            'rider/head/hoof Skin_GetLimbPos needs bounded gameplay anchors',
            'mount/dismount, race, archery, Ingo rider, gates, saves and scripted spawn chain unimplemented'],
    }.items():
        if enum in actors:
            actors[enum]['blockers'].extend(extra)
    # Boss gameplay dependencies stay explicit even when a subactor changes
    # category. This is a preservation review, never sprite-conversion approval.
    for enum, record in actors.items():
        record['boss_dependency_of'] = []
    for boss, record in actors.items():
        if record['visual_policy'] == 'boss_exempt_preserve_complex_hitboxes':
            for dep in closure(record['spawn_dependencies'], actors):
                if dep in actors and dep != boss:
                    actors[dep]['boss_dependency_of'].append(boss)
    scenes = []
    scene_text = (oot / 'include/tables/scene_table.h').read_text(encoding='utf-8')
    registered = {s['prefix']: s['index'] for s in registrations}
    for match in SCENES.finditer(scene_text):
        sid, prefix, enum = match.groups()
        paths = list((asset_root / 'assets/scenes').glob(f'*/{prefix}/{prefix}_scene.c'))
        record = {'id': int(sid, 16), 'scene': enum, 'prefix': prefix,
                  'runtime_index': registered.get(prefix), 'rooms': [], 'ready': False}
        roots = set()
        if paths:
            for room in imp.room_files(paths[0]):
                text = room.read_text(encoding='utf-8')
                variants = []
                for layer, (name, present) in enumerate(imp.room_layers(room, text, asset_root)):
                    placements = []
                    if name:
                        inc = room.parent / (name + '.inc.c')
                        body = uncomment(inc.read_text(encoding='utf-8'))
                        placements = actor_placements(body)
                        roots.update(p['actor'] for p in placements)
                    variants.append({'layer': layer,
                                     'era_time': LAYERS[layer] if layer < 4 else 'cutscene_setup',
                                     'present': present, 'fallback': None if present else 'previous_available_header',
                                     'source_list': name, 'placements': placements})
                record['rooms'].append({'room': room.name, 'layers': variants})
        reached = closure(roots, actors)
        record['reachable_actor_candidates'] = reached
        record['missing_gameplay_candidates'] = [a for a in reached
            if actors.get(a, {}).get('gameplay_owner') != 'decomp_imported' or
            (actors.get(a, {}).get('scene_pack_scope') is not None and
             record['id'] not in actors[a]['scene_pack_scope'])]
        record['budget'] = {'room_plus_actor_effect_peak': None,
                            'reason': 'simultaneous dynamic spawn and native actor sets require review'}
        record['blockers'] = ['source predicates need scenario review', 'dynamic multiplicity/indirect calls unresolved',
                              'scene resource/coverage gate not passed', 'human verification pending']
        if not paths:
            record['blockers'].append('extracted scene absent')
        if prefix not in registered:
            record['blockers'].append('runtime destination not registered')
        scenes.append(record)
    # Spawn sites in engine and other shared systems are roots too (horses,
    # fairies, effects). They are not assigned to every scene without proof.
    shared = []
    for path in sorted((oot / 'src/code').glob('*.c')):
        shared.extend(spawn_edges(path.read_text(encoding='utf-8'), path.relative_to(oot).as_posix()))
    return {'format_version': 1, 'source_version': imp.VERSION,
            'coverage_semantics': 'conservative static inventory, not branch/reachability acceptance',
            'required_dimensions': ['scene', 'room', 'age', 'time', 'header_layer', 'params', 'story_flags',
                                    'dynamic_trigger', 'dialogue_choices', 'rewards', 'save_reload', 'cutscene_skip'],
            'actors': actors, 'scenes': scenes, 'shared_spawn_calls': shared,
            'summary': {'profiles': len(actors), 'scenes': len(scenes),
                        'imported_profiles': sum(a['verification']['implemented'] for a in actors.values()),
                        'ready_scenes': 0}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=imp.OOT_DEFAULT)
    parser.add_argument('--out', type=Path, default=GAME / 'docs/ACTOR_COVERAGE.json')
    parser.add_argument('--require-ready', action='append', default=[])
    args = parser.parse_args()
    sprite_path = GAME / 'build/oot-core/generic_sprites.json'
    scene_path = GAME / 'build/generated/scene_table.json'
    horse_path = GAME / 'build/generated/horse-sprites/manifest.json'
    rows = json.loads(sprite_path.read_text()) if sprite_path.exists() else []
    registrations = json.loads(scene_path.read_text())['scenes'] if scene_path.exists() else []
    horse_rows = json.loads(horse_path.read_text())['recipes'] if horse_path.exists() else []
    result = build(args.oot, args.oot / 'extracted' / imp.VERSION, rows,
                   registrations=registrations, horse_rows=horse_rows)
    rev = subprocess.run(['git', '-C', str(args.oot), 'rev-parse', 'HEAD'], capture_output=True, text=True)
    result['source_revision'] = rev.stdout.strip() if rev.returncode == 0 else os.environ.get('OOT_SOURCE_REV', 'unknown')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary']))
    by_name = {s['prefix']: s for s in result['scenes']}
    failed = [s for s in args.require_ready if not by_name.get(s, {}).get('ready')]
    if failed:
        raise SystemExit('coverage gate blocked: ' + ', '.join(failed))


if __name__ == '__main__':
    main()
