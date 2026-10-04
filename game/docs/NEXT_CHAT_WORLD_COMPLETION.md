# Next chat: cleanup blocker, connected world, complete NPC/dialogue coverage

2026-10-03, oot-core branch. Preserve the shared dirty tree. This handoff is a
plan, not an implementation or runtime acceptance claim. Read AGENTS.md,
CLAUDE.md, DOSEI-LEGEND-BIBLE.md, DEMO_PLAN.md, OOT_CORE_PIPELINE_PLAN.md and
ACTOR_SPRITE_ROLLOUT_PLAN.md first.

## Latest human evidence supersedes prior build success

- Startup/zone changes repeatedly show Jo Engine error:
  `In dosei_allocator_free(): Null pointer`. Screenshot: dynamic memory 22%,
  sprite memory 0%. Human presses Start about six times per zone to dismiss it.
  This is a null-free error, not evidence of RAM/VRAM exhaustion.
- One NPC now visible in Lon Lon Ranch. Full population, animals, dialogue and
  spawn conditions are not accepted. Do not assume every missing NPC should
  spawn in the currently selected age/time/story layer.
- Generic-zone doors remain unusable. User requires traversal through all
  zones/interiors, not level-select-only access, plus all NPCs and dialogue.
- Last target build passed: `build/ranch-sprite-build.log`, usual Clean image,
  .bss end 0x06081DC0 / 8,768 B spare. Its 36 host checks missed the null-free
  regression. Subsequent cleanup repair now built: `build/null-free-fix-build.log`,
  usual Clean image, .bss end 0x06081DE0 / 8,736 B spare. Runtime acceptance pending.

## P0: cleanup repaired; runtime acceptance pending

Confirmed source defect introduced by sprite conversion:
`story_route_free()` previously unconditionally called `jo_free()` on four Saria and two
owl pointers. `scene_flow.c` invokes it on scene changes; empty slots produce
six SDK errors. `actor_mesh_free()` previously checked NULL, direct `jo_free()`
does not (`joengine/jo_engine/malloc.c`; project heap_profile.c renames it).
The same defect in `emerald_story_free()` and `cutscene_actors_free()` is also
repaired. All three now guard optional pointers and clear them after release.

SDK error checks remain enabled; no heap enlargement or error suppression.
Host stubs now detect NULL frees. Eleven focused host checks pass, including
all 256 empty/partial/full story/emerald allocation combinations, repeated
teardown and cutscene cleanup before loading/after freeing. WSL Clean rebuild
passes. Human still verifies startup and repeated transitions without dismissals.
Next implementation priorities are P1 doors and P2 NPC/dialogue coverage.

## P1: wire the whole scene/room/entrance graph

Audit original scene/entrance tables, all alternate headers, transition actors,
collision exits, door parameter variants, spawn records and event gates.
`build_room_scene.py:transitions()` currently explicitly skips unsupported
generic transitions (including En_Door paths); `build_scene_table.py` passes
`strict=False` for generic scenes. Record every skipped edge and its reason.

Implement shared transition/door support for ordinary doors, interior returns,
shutters/locks, room crossings, grottos, warps and scripted entrances as required
by source conditions. Preserve keys, switches, story locks, age/time restrictions,
destination spawn/yaw/camera, save/respawn and music ownership. Do not unlock
everything or infer that a room mesh means its doorway works. Keep scene/save
IDs stable; handle missing destination assets explicitly rather than dropping
an edge. Validate bidirectional routes where source permits them, prevent
immediate bounce-back, and test repeated interior/exterior round trips.

Start with Ranch buildings and return doors, then all registered scenes; extend
registration/assets to remaining game destinations instead of declaring the
world complete while destinations are absent. Report total/reachable/blocked
edges by source condition. Host graph checks plus human traversal are required.

## P2: all NPCs, animals and source-driven dialogue

Execute ACTOR_SPRITE_ROLLOUT_PLAN.md with a versioned coverage ledger across
every map/room, child/adult era, day/night, alternate layer, actor parameter,
story flag, cue and transitive dynamic spawn. Ranch gameplay horses remain
unimported; cutscene horse sprites do not supply their actor logic. Diagnose
expected spawn -> actual actor -> loaded sheet/key -> slot -> draw separately.
Include later same-room spawns, not only the first room-initialization snapshot.

Bake every required NPC visual/clip variant offline with compact Saturn sheets
and timing metadata. Import original actor action/message selection and bridge
talk offers, choices, follow-ups, item/song checks, rewards and persistent flags.
Text assets alone do not implement dialogue. Test the correct presence/absence
and conversation for each relevant save/time/age state, including re-entry,
save/reload, cutscene completion/skip and dynamic replacements.

## Permanent constraints and acceptance

- NPCs, animals, fairies and non-boss enemies use baked sprites unless explicitly
  exempted. No runtime character meshes/materials/skeleton/pose-track loads,
  head/torso tracking or 3D fallback for converted actors. Source assets stay offline.
- Bosses explicitly exempt for now: retain models, complex damage/weak-point
  hitboxes and puzzle logic. Link remains separate. Preserve ordinary enemy
  combat, collision and original drops when converting them in the rollout.
- No new 64-bit runtime math. Prefer bounded 32-bit approximations and speed.
  Budget room + reachable actor/effect sets together; Ranch now reserves 64 KiB
  actors and 32 KiB spare. Do not hide missing actors behind capacity failures.
- Preserve decomp gameplay and 20 Hz/input/hit-volume bridge behavior. Avoid
  bespoke per-scene patches where a shared importer/runtime path can cover it.
- Batch host checks, target disassembly/resource audit and WSL Clean build to
  `game/build/game-clean.cue/.iso`. No emulator launch/input injection by agents.
  Human owns runtime testing. No commit/push without instruction.
- Track implemented, host-tested, target-built and human-accepted separately.
  Update plans and blockers honestly; no complete-world claim from a build.
