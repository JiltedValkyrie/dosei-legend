#!/usr/bin/env bash
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
GAME=$(cd "$HERE/../.." && pwd)
OOT=${OOT:-${DOSEI_OOT:-$(cd "$GAME/../../../game-decomps/n64/oot" && pwd)}}
source "$GAME/oot-core/oot-core-flags.sh"
OUT="$GAME/build/oot-core/tool-actor-probe"
mkdir -p "$OUT"
python3 - "$D/src/code/z_actor.cpp" "$GAME/oot-core/src/bridge_player.cpp" "$OUT/movement.cpp" <<'PY'
import pathlib, sys
text=pathlib.Path(sys.argv[1]).read_text()
parts=['#include "oot_prelude.h"\n#include "actor.h"\n#include "regs.h"\n#include "z_math.h"\n#include "z_lib.h"\n#include "player.h"\n#include "play_state.h"']
for name in ('Actor_UpdatePos','Actor_UpdateVelocityXZGravity','Actor_MoveXZGravity','Actor_SetProjectileSpeed'):
    start=text.index('void '+name+'(')
    end=text.index('\n}',start)+2
    parts.append(text[start:end])
start=text.index('Actor* Actor_SpawnAsChild(')
parts.append(text[start:text.index('\n}',start)+2])
text=pathlib.Path(sys.argv[2]).read_text()
start=text.index('u8 Player_UpdateWeaponInfo(')
parts.append(text[start:text.index('\n}',start)+2])
pathlib.Path(sys.argv[3]).write_text('\n'.join(parts))
PY
${HOST_CXX:-g++} $OOT_CORE_CXXFLAGS -O1 -g -ffunction-sections -fdata-sections -no-pie \
    "$HERE/tool_actor_fixture.cpp" "$GAME/oot-core/src/bridge_items.cpp" "$OUT/movement.cpp" \
    "$D/src/overlays/actors/ovl_En_Arrow/z_en_arrow.cpp" \
    "$D/src/overlays/actors/ovl_Arms_Hook/z_arms_hook.cpp" \
    "$D/src/overlays/actors/ovl_En_Bom/z_en_bom.cpp" \
    "$D/src/overlays/actors/ovl_En_Boom/z_en_boom.cpp" \
    "$D/src/code/z_lib.cpp" "$D/src/code/sys_math.cpp" "$D/src/code/sys_math_atan.cpp" \
    "$D/src/libultra/gu/sins.cpp" "$D/src/libultra/gu/coss.cpp" \
    "$GAME/oot-core/src/oot_math.cpp" "$GAME/oot-core/src/oot_rand.cpp" \
    -Wl,--gc-sections -o "$OUT/tool_actor_probe"
"$OUT/tool_actor_probe"
