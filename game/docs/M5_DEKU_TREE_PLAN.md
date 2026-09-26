# M5 draft: Great Deku Tree, Gohma and Emerald

Astra side draft, 2026-09-25. Expands DEMO_PLAN M5 after reviewed M4.

## Playable result and scope

From a normal fresh-file progression, enter the Great Deku Tree, complete the
source dungeon puzzles, defeat Gohma through her intended vulnerabilities, collect
the heart container if desired, use blue warp, receive Kokiri Emerald and see the
Deku Tree death/story chain. No debug grants, skipped puzzle prerequisites or
substitute boss health bar. Save/Game Over inside returns through correct dungeon
resume policy. Post-Emerald forest/Lost Woods behavior belongs to M6.

The plan names 12 ydan rooms and two boss rooms. Confirm headers, transitions and
actor lists from the extraction before allocating; a room count is not a memory
residency budget. Actor types listed below require actual spawn evidence.

## Dependencies and closure obligations

| Foundation | M5 closes |
|---|---|
| M1 traversal/dynamic collision/water | Real vines, ledges, block, rotating platforms and basement water checks |
| M2 combat/health/continue | Dungeon enemies, boss, reflected scrub encounter and live dungeon/boss respawn |
| M3 chests/grants/choices/doors | Dungeon treasures, Tree mouth choices and story flag transactions |
| M4 items/map/compass | Actual ignition/web/switch/seed puzzles and dungeon map display |
| Existing baked cutscenes/audio banks | Multi-scene death/flashback chain, fanfares and area bank restoration |

M6b owns final gold-token collection audit. Implement the shared gold actor/token
contract early here if reachable dungeon content needs it; do not permanently omit
reachable tokens and call a complete dungeon verified. Track any remaining M6b
case explicitly. No duplicate push-block, torch, drop or enemy engine.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Source group | Research output |
|---|---|
| ydan/ydan_boss headers, collision, room lists, entrances | Layer-aware room graph, exits, water, camera, switch/chest/clear flags |
| Bg_Treemouth and associated text/cutscenes | Initial choice, refusal/retry, mouth collision and persistent meeting flags |
| Door_Shutter, En_Holl, Obj_Switch, Obj_Syokudai | Door/clear rules, transitions, accepted attacks, torch timing |
| Bg_Ydan_Sp/Maruta/Hasi, Obj_Lift, Obj_Oshihiki/Makeoshihiki | Burn/jump-break conditions, motion, dynamic ownership and persistence |
| Bg_Breakwall | Whether spawned and actual destruction trigger; never assume Deku Nut breaks it |
| En_Dekubaba, En_Karebaba, En_St, En_Sw, En_Goma, En_Hintnuts/En_Nutsball | Params, collision, damage/effects, state machine, source drops and puzzle sequencing |
| Boss_Goma, Item_B_Heart, Door_Warp1 | Vulnerability/egg phases, death, optional heart, warp/quest grant and repeat entry |
| Scene cutscenes and z_demo.c destinations | Full Emerald/death chain, flashback scene/object dependencies, flags and final spawn |

Keese and any other actor are included if relevant room/layer data places them;
not because a generic dungeon list says so. Build an actor/drop manifest per room.
Use source music identifiers rather than assuming umbrella-plan numeric sequences
are correct across the project's bank mapping.

## Delivery checkpoints

### M5a: dungeon manifest and streaming shell

Export the complete room graph with triggers, entrance mapping, persistent flags,
required objects/actors and source camera/water data. Budget worst overlapping
rooms, boss/minions, actor pool, SGL commands, textures, collision and bank staging.
Follow 0-9/A-Z 8.3 naming for rooms above nine; validate every generated reference.

Import geometry and transitions, then test each room/door route in a diagnostic
fixture without claiming normal progression. Dynamic collision registers/removes
with actor lifetime; room unload cannot leave a ghost platform/web. Integrate map
and compass metadata. These scaffolding routes never become release shortcuts.

Review: room completeness, flag isolation, unload/reload, bank failure behavior,
actual memory peaks and first dungeon resume check.

### M5b: entrance and puzzle mechanisms

Port Tree mouth meeting/choice/refusal/retry/opening and ydan introduction. Apply
story flags at source-defined completion boundaries, not on text draw. Mouth
collision and entrance availability track the same state.

Add webs, torches, switches, blocks/platforms/logs and locked/clear doors in small
source-based groups. Test stick burn transfer, drop-height floor-web break, water
interaction, timed mechanisms and moving-platform traversal against real geometry.
Bind treasure chests and map/compass/Slingshot grants to persistent room flags.

Review: independently solve every puzzle without debug inventory; no standing,
manual-jump or save/reload bypass of mandatory conditions.

### M5c: enemies and scrub sequence

Port actors one at a time: model/face budget -> state machine -> collision/effects
-> rewards -> host tests -> visible encounter. Reuse Karebaba and Nutsball from M2.
Cover Skulltula vulnerable/back-side logic, wall variants, larvae/eggs, and other
source-present enemies. Each actor includes no-drop/immunity/respawn cases.

Implement the En_Hintnuts ordering puzzle from source, including wrong-order reset,
reflection, retreat/talk and clear-door result. No hardcoded room-clear shortcut
that ignores actor state or grants completion after leaving/re-entering.

Review: room-by-room combat/drop checklist and persistent versus temporary clears.

### M5d: Gohma and reward transition

Implement boss phases, ceiling behavior, eggs/larvae, eye vulnerability, stun,
damage windows and death. Fixed-step hit/animation timing remains coherent at low
render rates. Limit/clean up minions without silently changing the required fight.
The eye counts as face texture; body stays flat-shaded.

Spawn heart container and blue warp with source conditions. Optional heart pickup
must not gate warp incorrectly or duplicate on reload. Keep boss-clear, heart
collection and quest grant as distinct persistent facts. Verify death/continue
before and after boss defeat, reload/re-entry, and exhausted-ammo recovery paths.

Review: full boss fight, source weakness, rewards once, camera legibility and peak
resource budget with boss plus larvae/effects present.

### M5e: Emerald/death cutscene chain and milestone closure

Bake all required story shots and flashback banks, including scenes beyond current
playable geography only as needed for those cutscenes. Reuse the opening pipeline;
restore gameplay actor, texture, audio and collision banks at the destination.

Permanent double-Start skips the current shot, not the entire chain. Every skip
must execute mandatory grants/flags/destination effects once while allowing
presentation cues to be omitted/coalesced appropriately. Test consecutive skips,
no skip and final-shot transitions; no extra Emerald or stranded loading state.

Review: fresh title -> legitimate dungeon clear -> Emerald/death -> post-story
forest spawn, plus save/continue and reload on both sides of every grant boundary.

## Acceptance and later obligations

- All required rooms/actors/puzzles in source layer accounted for; flag index and
  room IDs above nine round-trip without filename or persistence collisions.
- M1 deferred traversal and M2 dungeon resume checks close with runtime evidence.
- M4 item fixtures close against actual dungeon surfaces/enemies and map data.
- Whole dungeon playable without debug; both controllers, slow rendering, room
  churn, empty ammo and defeat/retry do not strand progression.
- Story skip and ordinary playback yield identical mandatory progression state.
- M6 owns post-Emerald NPC/exit behavior; M6b closes remaining named token audits.
  Neither obligation is silently marked complete by this milestone.

## Review and verification rules

Planning only; no implementation owner assigned here. Start code after preceding
milestone review and human owner assignment. Recheck current source and working
diff before taking files; M1/other active work stays with its owner. Dependencies
below describe required behavior, not permission for a parallel rewrite.

At each implementation checkpoint: focused host tests in separate processes,
**clean image only** per current human instruction, SGL map boundary, worst-room
VDP1 budget, cart bounds/heap high-water and audio bank bytes. Inspect changed
runtime hot paths for software float. Do not cut the malloc arena by guesswork.
Runtime checks use the project's non-focus-stealing workflow or human play;
report observed versus pending checks separately. No build/runtime checks were
performed for this draft. Source references are implementation research targets
unless explicitly marked verified; umbrella-plan actor lists are not spawn proof.

Record changed files, source parity, approximations, save compatibility, measured
budgets and deferred acceptance in OPUS_HANDOFF and VSLICEPROGRESS when code lands.
Code stays uncommitted for review unless human requests commit. Planning does not
complete a milestone or authorize the next one. All new actors include source
spawn/drop audits in the same task; characters use flat materials except faces.

All menus must use VDP2 for text, panels, icons, maps and cursors. Budget VDP2
storage/layers and restoration explicitly; no VDP1 menu textures or commands.
