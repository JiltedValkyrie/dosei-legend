# Real N64 rooms. Texture warp work. Future-session handoff.

Latest user override: stop active renderer experiments, restore floor/water
textures, hand exact overlap problem to Claude Opus. Read
[current occlusion handoff](CLAUDE_OPUS_FLOOR_OCCLUSION.md) before this checkpoint.

Checkpoint: 2026-09-18. User-approved direction. Work not finished. No commit.

## What user want

Use real N64 level data. Keep original rooms, tunnel transitions, object groups,
textures, UVs, and material rules. Do not invent room cuts from screenshot.
Keep huts and bridge in separate authored groups where source supports this.
Hide unseen/far groups. Load next room through real tunnel transition.
Do not keep whole forest mesh and every room texture resident together.
Use saved polygon/texture budget to reduce bad ground stretching.
Use same source-first approach for future areas too.

User quad export may help topology. Not permission to replace original textures
with workshop preview atlas. Quads alone not cure affine texture warp.

User follow-up: going forward, inspect user's actual running Kronos session for
texture warp and overlap. That session is acceptance reference, not substitute
test scene. Capture its window in background; preserve focus, input, and loaded
disc. Ask user to walk/turn/jump when movement evidence needed. Separate texture
stretch from draw-order overlap; a still alone cannot prove temporal overlap.

## Real source to read first

Local verified NTSC 1.2 decomp:
`D:/Workspace-Claude/game-decomps/n64/oot`.

- `src/code/z_room.c`, `Room_DrawCullable`: original room draw/culling rules.
- `include/room.h`, `RoomShapeCullableEntry`: original bounds sphere and
  opaque/translucent display-list entries.
- `src/overlays/actors/ovl_En_Holl/z_en_holl.c` and `.h`: real tunnel actor,
  transition volume, room choice, current/previous room behavior.
- Extracted `spot04_scene`, `spot04_room_0`, `_1`, `_2`: real Kokiri data.

Original renderer culls room entries using projected bounds spheres and depth.
Not simply draw entire forest. Do not claim N64 used prototype distance cutoff.

| Authored room | Source triangles | Cullable entries |
| --- | ---: | ---: |
| 0 | 1220 | 18 |
| 1 | 598 | 3 |
| 2 | 242 | 7 |

Total 2060 source triangles. Entries not all neatly named huts: some hold terrain,
decals, or background. Preserve source identity before adding semantic labels.

Scene command `0x0e` holds two transitions. Actor 35 (`En_Holl`), params `0x13f`,
type 4 (horizontal invisible), yaw 0 for both:

| Front room | Back room | N64 position x,y,z |
| --- | --- | --- |
| 0 | 2 | -785,120,1219 |
| 1 | 0 | 2160,-1,-148 |

Original test uses feet relative to actor: -50 < y < 200, abs(local x) < 200,
50 < abs(local z) < 100. Negative z picks front; positive z picks back.
Middle band gives hysteresis. Read original code before changing these rules.

## What broke. What not count as proof.

Prim-color multiplication fixes lost tint, not stretched ground mapping.
Earlier spawn-only split missed user's bad spot. See
[failed-fix record](FOREGROUND_WARP_FAILURE_2026-09-18.md).

Matched bad view: camera (651,71,234), yaw 17174, pitch -1820;
Link collision eye (773,90,224), facing 50873.
Foreground source faces 462,463,497,498 still triangles in user's quad export.
Large triangles plus collapsed VDP1 quad corner stretch texture toward near apex.
No more "fixed" from different camera or one still image.

## Work present, still prototype

- `shared/tools/build_kokiri_scene.py`: preserve room-entry object index per face.
- `game/tools/workshop_quads.py`: validate export provenance, positions, original
  UV/material compatibility; reuse compatible joins, not preview atlas.
- `game/tools/build_quads.py`: respect object boundaries and preferred joins.
- `game/tools/build_hybrid_scene.py`: room filtering, triangle-to-three-quad
  conversion, budget-limited ground refinement, existing prim tint kept.
- `game/tools/build_room_scene.py`: emit per-room `R0.MSH/R0.TEX` through
  `R2.MSH/R2.TEX`, real transition records, max-room-sized resident buffers.
- `game/src/kokiri_sgl.c`: experimental room-bank replacement and object culling;
  Link/fairy stay resident. Main loop calls `kokiri_scene_update()`.
- `game/build.sh` / `build_sgl_scene.py`: explicit `STREAM_ROOMS=1` and `QUAD_OBJ`.
  Default still legacy path. New room mode not promoted to normal player images.

User export:
`workspace/meshes/3fd66b9e8dab/exports/20260915-192723-504f315e/mesh-kokiriforest-quads.obj`.
332 compatible quad joins accepted; one otherwise valid join rejected by source
compatibility. Bent/concave export quads not blindly trusted.
Workshop `prefer_quads` setting not automatically wired into this build path.

Important gaps:

- Prototype saves object index, not original sphere data yet. Culling currently
  derived AABB + XZ distance 1310. Replace/justify against real N64 rules.
- One replaceable room bank. No proven original-style current/previous-room
  overlap or prefetch. Check tunnel visibility before calling architecture done.
- Blocking room reads and VDP1-safe upload window need live verification.
- Title camera touring other rooms needs review.
- Build summary can report Link-only 517 polygons for streaming mode. Wrong
  summary, not true scene count. Use room manifests; fix summary next.

## Evidence and budget checkpoint

Experiments isolated under ignored `workspace/warp-audit/`.
Root player ISOs not replaced with room prototype. Do not overwrite them yet.
Isolated probe has fixed-camera `PERF_PROBE=4` edits. Never promote probe edits.

First room capture: `workspace/warp-audit/exact-room-quads.png`.
Ground improved at matched camera, but water draw-order regression visible.
Latest refinement tries to restore translucent-ground subdivision.
Latest refinement builds, but capture failed because target process gone.
Cause unknown. Latest water fix NOT visually verified. No walk/jump proof yet.

Follow-up live user-session inspection: window title `Kronos v2.7.0 ISO:
game-clean.cue`. Background captures saved as
`workspace/warp-audit/user-session-20260918-a.png` and
`user-session-20260918-motion-1.png` through `-4.png`.
Large diagonal stretched ground patches visible around Link between fence posts.
First/last sampled view stayed at same place; idle pose/fairy changed.
These captures prove visible stretch, not walk/jump overlap behavior. Window title
alone not proof of full disc path/build identity. No input, restart, or disc swap.

Latest successful isolated build: `workspace/warp-audit/rooms-refine-build.log`.
Counts include Link geometry:

| Resident room | Polygons / 2600 | Vertices / 2500 | Texture bytes / 432632 |
| --- | ---: | ---: | ---: |
| 0 | 2369 | 2484 | 427512 |
| 1 | 2050 | 1945 | 427960 |
| 2 | 937 | 897 | 258072 |

Latest `.bss` ends `0x060a66d0`; work area starts `0x060a7200`.
Only **2864 bytes** gap. Earlier 36560-byte room-build gap now stale.
Ground refinement spent that space. Need leave safer margin, not blindly add mesh.

Targeted host tests passed: workshop 4, room format/quad geometry 2,
forest partition 8. Root generated-room integration test skipped without banks.
Current full suite not rerun. Old 186/187-pass reports not proof for this prototype.

## Next session order

1. Read this and failure record. Preserve dirty user edits and baseline images.
2. Preserve original N64 sphere metadata. Match room/object visibility behavior
   to source, including tunnel overlap; no arbitrary room guesses.
3. Reduce refinement pressure on RAM/vertex limit. Fix streaming build summary.
4. Add host tests for both tunnels in both directions, hysteresis, deferred load,
   object partition integrity, bank bounds, and no missing source faces.
5. Build isolated probe. Capture exact bad camera before/after, then walk, turn,
   jump, approach huts/bridge, cross both tunnels and return. Check water ordering,
   disappearing geometry, texture-bank corruption, audio stalls, and frame cost.
6. Run full host suite and generated-room validation. Record actual results.
7. Only after visual/movement/budget gates pass, build normal and clean images
   without probe flags. Report remaining affine limits honestly. Do not auto-commit.

Background capture only. No focus steal, desktop capture, global input, or closing
user emulator. Identify owned process each time; old process IDs not safe handles.
No unrelated renderer/control rewrite. Control handoff still applies unchanged.
