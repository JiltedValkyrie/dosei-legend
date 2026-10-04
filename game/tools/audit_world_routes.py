"""Source scene/entrance/door audit. Readiness is structural, never gameplay acceptance."""
import argparse
import collections
import json
import os
from pathlib import Path
import re
import struct

import build_all_scenes
import build_room_scene as rooms
import build_scene_table as scenes

ROOT = Path(__file__).resolve().parents[1]
GATES = {
    0: 'tunnel', 2: 'vertical tunnel', 4: 'horizontal tunnel', 6: 'narrow tunnel',
    8: 'openable shutter', 9: 'back room clear', 10: 'back switch',
    11: 'back unopenable', 13: 'boss key; opposite side unopenable',
    15: 'front clear/back switch', 19: 'small key; persistent unlock switch',
    24: 'room handle', 25: 'small key; persistent unlock switch',
    26: 'room handle', 27: 'scene exit handle', 28: 'ajar handle',
    29: 'checkable text; Talon returned event exception',
    30: '18:00 < time < 21:00; closed text otherwise', 31: 'room handle',
}


def audit(oot):
    registry = {entry['scene']: entry for entry in scenes.SCENES}
    entrance = scenes.entrance_metadata(oot)
    registration = scenes.ALL_SCENES_DIR / 'registered.json'
    failures = {e['scene']: e['status'] for e in json.loads(registration.read_text())['scenes']
                if e['status'] != 'ok'} if registration.exists() else {}
    scene_rows, edges, portals, errors = [], [], [], []
    for entry in build_all_scenes.scene_list(oot):
        prefix, name = entry['prefix'], entry['scene']
        scene_rows.append(dict(entry, registered=name in registry,
                               blocker=failures.get(name, '' if name in registry else 'not registered')))
        try:
            data = scenes.source.extract(oot, None, prefix=prefix)[prefix + '_scene']
            surfaces = scenes.source.collision_surfaces(data)
            highest = max((p['exit'] for p in surfaces), default=0)
            for layer, commands in rooms.transition_layers(data):
                pointer = next((addr & 0xffffff for cmd, _, addr in commands if cmd == 0x13), None)
                if pointer is None or not highest:
                    continue
                exits = struct.unpack_from('>%dH' % highest, data, pointer)
                for slot in sorted({p['exit'] for p in surfaces if p['exit']}):
                    number = exits[slot-1]
                    target = entrance.get(number+layer)
                    reason = []
                    if name not in registry:
                        reason.append('source not registered')
                    if target is None:
                        reason.append('special or unresolved entrance')
                    elif target['scene'] not in registry:
                        reason.append('destination not registered: ' + failures.get(target['scene'], 'no assets'))
                    edges.append(dict(source=name, prefix=prefix, layer=layer, exit=slot,
                                      entrance=number, variant_entrance=number+layer, destination=target['scene'] if target else None,
                                      spawn=target['spawn'] if target else None,
                                      keep_music=target['keep_music'] if target else None,
                                      status='blocked' if reason else 'structural', blockers=reason))
            for row in rooms.transition_rows(data):
                kind = rooms.transition_kind(row['actor'], row['params'])
                reason = []
                if name not in registry:
                    reason.append('scene not registered')
                if kind not in GATES:
                    reason.append('source actor/gate requires implementation')
                if name in registry and any(r < -1 or r >= registry[name]['rooms'] for r in (row['front'], row['back'])):
                    reason.append('room bank missing')
                portals.append(dict(row, scene=name, prefix=prefix, kind=kind,
                                    condition=GATES.get(kind, 'unsupported: closed'),
                                    status='blocked' if reason else 'implemented', blockers=reason))
        except Exception as error:
            errors.append(dict(scene=name, error=str(error)))
    pairs = {(e['source'], e['destination']) for e in edges if e['destination']}
    for edge in edges:
        edge['reverse_scene_edge'] = (edge['destination'], edge['source']) in pairs
    reachable = {'SCENE_KOKIRI_FOREST'}
    while True:
        more = {e['destination'] for e in edges if e['source'] in reachable and e['status']=='structural'}
        if more <= reachable:
            break
        reachable |= more
    # Actor/script requests are recorded by their actual source assignment.
    # Conditional reachability cannot be inferred from a text scan.
    scripted = []
    imported = (ROOT/'tools/oot_core_import.py').read_text(encoding='utf-8')
    for path in sorted((oot/'src/overlays/actors').glob('*/*.c')):
        source = path.read_text(encoding='utf-8')
        for match in re.finditer(r'(?:nextEntranceIndex|save\.entranceIndex)\s*=\s*([^;]+);', source):
            scripted.append(dict(file=str(path.relative_to(oot)).replace('\\','/'),
                                 line=source[:match.start()].count('\n')+1,
                                 expression=match[1].strip(), imported=path.name in imported,
                                 status='source condition/trigger verification pending'))
    return dict(version=1, source='OoT ntsc-1.2 extracted scene segments + decomp source',
                semantics='structural means assets/edge present, NOT gates/traversal/actor trigger accepted',
                summary=dict(source_scenes=len(scene_rows),registered_scenes=len(registry),
                             layer_exit_edges=len(edges),blocked_exit_edges=sum(e['status']=='blocked' for e in edges),
                             layer_transition_actors=len(portals),blocked_transition_actors=sum(p['status']=='blocked' for p in portals),
                             structurally_reachable_scenes=len(reachable),
                             missing_reverse_scene_edges=sum(not e['reverse_scene_edge'] for e in edges),
                             scripted_assignments=len(scripted),extract_errors=len(errors)),
                structurally_reachable=sorted(reachable), scenes=scene_rows, exits=edges,
                transitions=portals, scripts=scripted, errors=errors,
                remaining=['Unregistered scenes require resource/asset work.',
                           'Special grotto return entrances need respawn ownership.',
                           'Transition camera choreography and fade types remain pending; source metadata retained.',
                           'Alternate spawn/collision headers require complete runtime selection.',
                           'Unimported warp/script actors cannot trigger the shared request bridge.',
                           'All routes require source-conditioned human traversal; level select is not evidence.'])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--oot',type=Path,default=Path(os.environ.get('DOSEI_OOT') or 'D:/Workspace-Claude/game-decomps/n64/oot'))
    ap.add_argument('--out',type=Path,default=ROOT/'docs/WORLD_ROUTE_AUDIT.json')
    args=ap.parse_args()
    result=audit(args.oot)
    args.out.write_text(json.dumps(result,indent=1)+'\n',encoding='utf-8')
    print(json.dumps(result['summary'],sort_keys=True))


if __name__=='__main__':
    main()
