#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/field-enemies/probe"
mkdir -p "$OUT"
python3 - "$GAME" "$D" "$OUT/actions.cpp" <<'PY'
from pathlib import Path
import re, sys
game, decomp, out = map(Path, sys.argv[1:])
parts = ['#include "oot_prelude.h"', '#include "play_state.h"', '#include "player.h"',
         '#include "save.h"', '#include "z_lib.h"', '#include "z_math.h"', '#include "rand.h"',
         '#include "item.h"', '#include "z_en_item00.h"', '#include "field_enemy_sprite.h"', '#define PRINTF(...) ((void)0)']
for actor, names in [('En_Encount1', ['EnEncount1_SpawnStalchildOrWolfos']),
                     ('En_Peehat', ['EnPeehat_Ground_StateGround']), ('En_Skb', ['EnSkb_Death'])]:
    stem = 'z_' + actor.lower()
    parts.append(f'#include "overlays/actors/ovl_{actor}/{stem}.h"')
    text = (decomp / f'src/overlays/actors/ovl_{actor}/{stem}.cpp').read_text()
    for name in names:
        match = re.search(r'^void ' + name + r'\([^;{}]*\) \{', text, re.M)
        parts.append(text[match.start():text.index('\n}', match.end())+2])
parts.insert(0, 'struct EnPeehat; struct PlayState; void EnPeehat_Ground_SetStateRise(EnPeehat*); void EnPeehat_HitWhenGrounded(EnPeehat*,PlayState*);')
text = (game / 'oot-core/src/field_enemy_sprite.cpp').read_text()
for name in ['FieldSprite_BreakStart', 'FieldSprite_BreakStep']:
    match = re.search(r'^(?:void|s32) ' + name + r'\([^;{}]*\) \{', text, re.M)
    parts.append(text[match.start():text.index('\n}', match.end())+2])
out.write_text('\n'.join(parts)+'\n')
PY
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -O1 -ffunction-sections -fdata-sections -no-pie \
    "$HERE/field_enemy_fixture.cpp" "$OUT/actions.cpp" -Wl,--gc-sections -o "$OUT/field_enemy_probe"
"$OUT/field_enemy_probe"
