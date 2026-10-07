#!/usr/bin/env python3
"""Complete Player clip set of every cutscene, checked against a cache budget.

A cutscene is one CutsceneData array (scene assets or actor sources). Its
player cues map through sCueToCsActionMap to cutscene actions; each action's
clips are everything reachable from its D_80854B18/D_80854E50 entries (direct
clip or action function and its callees), i.e. all shots and branches. Common
Player clips reachable that way are counted too: under demand loading they are
only free if the common resident set really holds them.

Sizes come from the emitted strict bank (ids.json + ALL.PFB block lengths).
Output: cutscene_sets.json with per-cutscene clips/bytes/entries, bytes not
already in RESIDENT.PFB, and the largest set (minimum cache arena). Measurement.
"""
import argparse
import json
import os
import re
import struct
from pathlib import Path

import build_player_frame_bank as bank

GAME = Path(__file__).resolve().parent.parent
SLACK = 4


def block_sizes(pfb):
    data = pfb.read_bytes()
    count = struct.unpack_from('>I', data, 4)[0]
    offs = list(struct.unpack_from('>%dI' % count, data, 8)) + [len(data) - 4]
    ids = struct.unpack_from('>%dH' % count, data, 8 + 4 * count)
    return {ids[i]: offs[i + 1] - offs[i] for i in range(count)}


def action_clip_sets(oot, clip_names):
    text = (oot / 'src/overlays/actors/ovl_player_actor/z_player.c').read_text(encoding='utf-8')
    ents = bank.entities(text)
    ident = re.compile(r'\b\w+\b')
    refs = {n: set(ident.findall(b)) for n, b in ents.items()}
    def reach(starts, blocked):
        seen, todo = set(), list(starts)
        while todo:
            n = todo.pop()
            if n in seen or n in blocked or n not in refs:
                continue
            seen.add(n)
            todo += [r for r in refs[n] if r in refs]
        return seen
    # Ordinary Player code (reachable without the cutscene tables): its clips
    # belong to gameplay/common-set planning, not to one cutscene's set.
    ordinary = reach(bank.ROOTS, set(bank.CS_TABLES))
    blocked = set(bank.CS_TABLES) | ordinary
    actions, shared = {}, {}
    for table in bank.CS_TABLES:
        for line in ents.get(table, '').splitlines():
            m = re.search(r'\{\s*-?\d+\s*,\s*&?(\w+)\s*\},\s*// (PLAYER_CSACTION_\w+)', line)
            if not m:
                continue
            target, action = m.groups()
            if target in clip_names:
                own, common = {target}, set()
            else:
                mine = reach([target], blocked)
                own = {c for e in mine for c in refs[e] if c in clip_names}
                calls = {r for e in mine for r in refs[e] if r in ordinary}
                common = {c for e in reach(calls, set(bank.CS_TABLES)) for c in refs[e]
                          if c in clip_names} - own
            actions.setdefault(action, set()).update(own)
            shared.setdefault(action, set()).update(common)
    cue_map = re.search(r'sCueToCsActionMap\[PLAYER_CUEID_MAX\] = \{(.*?)\n\};', text, re.S).group(1)
    cue_to_action = {m.group(2): m.group(1) for m in re.finditer(
        r'-?(PLAYER_CSACTION_\w+),\s*// (PLAYER_CUEID_\w+)', cue_map)}
    return actions, shared, cue_to_action


def cutscenes(oot):
    """(name, [cue ids]) per CutsceneData array; files without a visible array
    declaration count as one cutscene each."""
    out = []
    roots = [oot / 'extracted/ntsc-1.2/assets/scenes', oot / 'src/overlays/actors',
             oot / 'assets/scenes']
    seen = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob('*.c')):
            body = path.read_text(encoding='utf-8', errors='replace')
            if 'CS_PLAYER_CUE(' not in body or path in seen:
                continue
            seen.add(path)
            arrays = list(re.finditer(r'CutsceneData (\w+)\[\]\s*=\s*\{(.*?)\n\};', body, re.S))
            if arrays:
                for m in arrays:
                    cues = re.findall(r'CS_PLAYER_CUE\((PLAYER_CUEID_\w+)', m.group(2))
                    if cues:
                        out.append((f'{path.parent.name}/{m.group(1)}', cues))
            else:
                out.append((f'{path.parent.name}/{path.stem}',
                            re.findall(r'CS_PLAYER_CUE\((PLAYER_CUEID_\w+)', body)))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=os.environ.get('OOT'))
    parser.add_argument('--bank', type=Path, default=GAME / 'build/player-migration/bank_strict')
    parser.add_argument('--arena', type=int, default=0, help='cache arena to check sets against')
    args = parser.parse_args()
    ids = json.loads((args.bank / 'ids.json').read_text(encoding='utf-8'))
    sizes = block_sizes(args.bank / 'ALL.PFB')
    resident = set(block_sizes(args.bank / 'RESIDENT.PFB'))
    actions, shared, cue_to_action = action_clip_sets(args.oot, set(ids))
    rows, missing = [], set()
    for name, cues in cutscenes(args.oot):
        clips, common = set(), set()
        for cue in cues:
            action = cue_to_action.get(cue)
            if action is None:
                missing.add(cue)
                continue
            clips |= actions.get(action, set())
            common |= shared.get(action, set())
        clip_ids = sorted({ids[c] for c in clips if c in ids})
        total = sum(sizes[i] + SLACK for i in clip_ids)
        extra = [i for i in clip_ids if i not in resident]
        common_ids = sorted({ids[c] for c in common if c in ids} - set(clip_ids))
        rows.append(dict(cutscene=name, cues=len(cues), clips=len(clip_ids), bytes=total,
                         ordinary_clips_reached=len(common_ids),
                         ordinary_bytes_reached=sum(sizes[i] + SLACK for i in common_ids),
                         non_resident_clips=len(extra),
                         non_resident_bytes=sum(sizes[i] + SLACK for i in extra)))
    rows.sort(key=lambda r: -r['bytes'])
    worst = rows[0] if rows else {}
    worst_nr = max(rows, key=lambda r: r['non_resident_bytes']) if rows else {}
    report = dict(status='measurement: per-cutscene clips (all branches). own = clips only cutscene code '
                         'reaches; ordinary = gameplay clips reachable through the shared Player '
                         'update (common-set planning, not this set)',
                  cutscenes=len(rows), cues_without_action=sorted(missing),
                  largest_set=worst, largest_non_resident_set=worst_nr,
                  max_entries=max((r['clips'] for r in rows), default=0),
                  sets=rows)
    if args.arena:
        report['arena'] = args.arena
        report['sets_exceeding_arena'] = [r['cutscene'] for r in rows if r['bytes'] > args.arena]
        report['sets_exceeding_64_entries'] = [r['cutscene'] for r in rows if r['clips'] > 64]
    out = args.bank.parent / 'cutscene_sets.json'
    out.write_text(json.dumps(report, indent=1) + '\n', encoding='utf-8')
    print(f"{len(rows)} cutscenes; largest set {worst.get('cutscene')}: {worst.get('clips')} clips "
          f"{worst.get('bytes')} B; largest non-resident {worst_nr.get('cutscene')}: "
          f"{worst_nr.get('non_resident_clips')} clips {worst_nr.get('non_resident_bytes')} B; "
          f"max entries {report['max_entries']}")
    for r in rows[:12]:
        print(f"  {r['bytes']:7} B {r['clips']:3} own clips; ordinary reached {r['ordinary_clips_reached']:3} "
              f"({r['ordinary_bytes_reached']:6} B) {r['cutscene']}")
    if args.arena:
        print('exceeding arena:', report['sets_exceeding_arena'], '>64 entries:',
              report['sets_exceeding_64_entries'])


if __name__ == '__main__':
    main()
