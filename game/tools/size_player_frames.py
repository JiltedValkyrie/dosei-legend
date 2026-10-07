#!/usr/bin/env python3
"""Budget the real Player animation frame bank (measurement only).

Every LinkAnimationHeader (gameplay_keep player_anim_headers.c) names one
link_animetion data array; its frame count comes from link_animetion.h. One
source frame is PLAYER_LIMB_MAX * 3 + 1 s16 = 134 B (22 Vec3s incl. root
translation in joint 0, plus the face word). Root motion therefore costs no
extra bytes; morph/blend tables live in the Player struct (core size).

Reachable = animations referenced by relocations of kept Player code
(gc/source_profile.o). Age split, fail safe: an animation is age-only when it
appears only in that age's sAgeProperties block and nowhere else in kept
source, or (child) its name is a clink_ clip used nowhere outside age blocks.
Anything else is shared and counted for both ages. Aliased headers that share
one data array are counted once.

Compared with the current C Link bank (LINKANIM/ADULTANM, jo heap) and its
transactional era swap, which holds both banks at once: peak = 2 banks.
"""
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

GAME = Path(__file__).resolve().parent.parent
FRAME_BYTES = (22 * 3 + 1) * 2
SOURCE_SEGMENT_BYTES = 2513968   # extracted baserom link_animetion


def headers(oot):
    text = (oot / 'assets/objects/gameplay_keep/player_anim_headers.c').read_text(encoding='utf-8')
    extracted = oot / 'extracted/ntsc-1.2'
    out = {}
    for name, inc in re.findall(r'LinkAnimationHeader (\w+) = \{\n#include "([^"]+)"', text):
        body = (extracted / inc).read_text(encoding='utf-8')
        data = re.search(r'^\s*(\w+), // segment', body, re.M).group(1)
        out[name] = data
    return out


def frame_counts(oot):
    text = (oot / 'extracted/ntsc-1.2/assets/misc/link_animetion/link_animetion.h').read_text(
        encoding='utf-8')
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r'#define FRAMECOUNT_(\w+) (\d+)', text)}


def age_blocks(source):
    start = source.index('static PlayerAgeProperties sAgeProperties[] = {')
    end = source.index('\n};', start)
    body = source[start:end]
    # Two top-level initialisers: adult (LINK_AGE_ADULT 0), then child.
    depth, blocks, cur = 0, [], None
    for i, ch in enumerate(body):
        if ch == '{':
            depth += 1
            if depth == 2:
                cur = i
        elif ch == '}':
            if depth == 2:
                blocks.append(body[cur:i])
            depth -= 1
    if len(blocks) != 2:
        raise ValueError(f'expected 2 sAgeProperties blocks, found {len(blocks)}')
    return blocks, source[:start] + source[end:]


def relocated(objdump, path):
    out = subprocess.run([objdump, '-r', str(path)], capture_output=True, text=True,
                         check=True).stdout
    return {re.sub(r'[+-]0x.*', '', l.split()[2]).lstrip('_')
            for l in out.splitlines() if len(l.split()) == 3}


def budget(oot, refs, source, current):
    heads, counts = headers(oot), frame_counts(oot)
    (adult_block, child_block), rest = age_blocks(source)
    reach = sorted(h for h in heads if h in refs)
    def tag(name):
        word = re.compile(r'\b' + re.escape(name) + r'\b')
        a, c, o = word.search(adult_block), word.search(child_block), word.search(rest)
        if o:
            return 'shared'
        if a and not c:
            return 'adult'
        if c and not a:
            return 'child'
        return 'shared'
    sets = dict(adult=set(), child=set(), shared=set())
    for h in reach:
        sets[tag(h)].add(heads[h])
    def size(datas):
        return sum(counts[d] for d in datas) * FRAME_BYTES
    all_data = {heads[h] for h in heads}
    reach_data = {heads[h] for h in reach}
    child = sets['shared'] | sets['child']
    adult = sets['shared'] | sets['adult']
    peak = size(child) + size(adult)
    return dict(
        frame_bytes=FRAME_BYTES,
        headers=len(heads), reachable_headers=len(reach),
        unreferenced=sorted(set(heads) - set(reach)),
        all_bytes=size(all_data), reachable_bytes=size(reach_data),
        reachable_frames=sum(counts[d] for d in reach_data),
        shared_bytes=size(sets['shared']), child_only_bytes=size(sets['child'] - sets['shared']),
        adult_only_bytes=size(sets['adult'] - sets['shared']),
        child_bank_bytes=size(child), adult_bank_bytes=size(adult),
        swap_peak_bytes=peak,
        current_bank_bytes=current, current_swap_peak_bytes=2 * current,
        fits_current_allocation=max(size(child), size(adult)) <= current
                                 and peak <= 2 * current,
        note='Root motion is joint 0 of each frame (0 extra B). Blend/morph '
             'tables are Player struct fields (already in core size). Age split '
             'is name/table based and fail safe (unknown = shared).')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--oot', type=Path, default=os.environ.get('OOT'))
    parser.add_argument('--objdump', required=True)
    parser.add_argument('--player-gc', type=Path,
                        default=GAME / 'build/player-migration/gc/source_profile.o')
    parser.add_argument('--staged', type=Path, default=GAME /
                        'build/player-migration/decomp/src/overlays/actors/ovl_player_actor/z_player.cpp')
    parser.add_argument('--current', type=Path, default=GAME / 'build/cd/LINKANIM.BIN')
    parser.add_argument('--out', type=Path, default=GAME / 'build/player-migration/frames.json')
    args = parser.parse_args()
    if args.oot is None:
        raise SystemExit('set OOT or --oot')
    current = max(args.current.stat().st_size,
                  (args.current.parent / 'ADULTANM.BIN').stat().st_size
                  if (args.current.parent / 'ADULTANM.BIN').exists() else 0)
    report = budget(args.oot, relocated(args.objdump, args.player_gc),
                    args.staged.read_text(encoding='utf-8'), current)
    args.out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for key in ('reachable_headers', 'reachable_bytes', 'child_bank_bytes', 'adult_bank_bytes',
                'swap_peak_bytes', 'current_bank_bytes', 'current_swap_peak_bytes',
                'fits_current_allocation'):
        print(f'{key}: {report[key]}')
    print(f"unreferenced {len(report['unreferenced'])}; all headers {report['all_bytes']} B")


if __name__ == '__main__':
    main()
