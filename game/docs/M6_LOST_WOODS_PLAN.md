# M6 draft: post-Emerald Kokiri and Lost Woods

Astra side draft, 2026-09-25. Expands DEMO_PLAN M6 after reviewed M5.

## Playable result and scope

Kokiri responds to the Emerald/death story state, Mido's post-story behavior and
forest exit change correctly, and all ten Lost Woods rooms exist with source-exact
child access. Saria's bridge scene grants Fairy Ocarina and hands off toward Hyrule
Field. Lost Woods actors, wrong-way exits, target game and owls follow the reachable
story state. M7 owns Hyrule Field exploration; M6b owns grotto interiors/token and
scrub-shop completion. Do not duplicate those implementations.

## Open scope decision: Sacred Forest Meadow

The reviewed child-day Lost Woods layer has no Mido meadow block. The source route
is reachable. Human must choose either an explicitly acknowledged demo boundary or
additional Meadow content; that decision remains open. Do not invent a child Mido
or claim an absent source gate. Preparation of other rooms can proceed, but final
reachability acceptance and release boundary documentation depend on this decision.
If content expands, estimate scene/actor/save/audio costs and obtain scope direction
before implementing it. Do not silently adopt the umbrella risk list's conflicting
claim that Meadow is simply unreachable/out of scope.

## Dependencies and contracts

| Previous milestone | M6 use |
|---|---|
| M3 NPC/message/choice and population pipeline | Post-story dialogue, paths and exits |
| M4 Slingshot, inventory/quest and C input | Target game, Fairy Ocarina grant/assignment |
| M5 Emerald/death completion and final spawn | Story-state entry, not a second Emerald grant |
| M1/M2 actors, combat, traversal and targeting | Source encounters, safe locks, gates and world collision |
| Existing cutscene/scene flow | Bridge shots, mandatory effects and destination handoff |

Bridge completion must resolve to a valid destination. While M7 gameplay import
is absent, use explicit integration fixtures and record the live transition pending;
never ship a silent fallback to title or loop as if it were source behavior.
M6 may export Field transition data in agreement with its future owner, but that
is not completion of M7. M6b depends on M6 room/entrance IDs; freeze those contracts.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Source | Required evidence |
|---|---|
| spot10 child headers/actor lists and exit table | Ten-room graph, correct-way/wrong-way destinations, child layer and entry spawns |
| En_Ko, En_Md, En_Sa | Emerald-dependent text/paths, actual bridge-exit guard and removal timing |
| z_demo.c conditional triggers, Demo_Sa, bridge cutscene | LOST_WOODS_9 condition, C1 behavior, GI/quest effects and Field destination |
| En_Owl and placed params | Lost Woods owl dialogue, repeat choices, flight and story flags |
| En_Skj, En_Dnt_Nomal, En_Okuta, En_Shopnuts | Reachable talk/minigame/combat/shop states, rewards and params |
| Obj_Bombiwa, Door_Ana and scene collision | Actual blockers, capability requirements and grotto entry identities |
| z_en_item00.c and actor-specific grant paths | Drops, minigame rewards/capacity and persistence |

The bridge is room 5 in the reviewed source plan; validate all graph edges from
extracted headers, not geometric proximity. Alternate adult actor lists must not
be merged into child populations. Recheck EVENTCHKINF_09/1C/C1 branch semantics
and which actor owns each write instead of treating flags as generic quest stages.

## Delivery checkpoints

### M6a: story/room graph and scope ledger

Build a matrix for pre-Emerald, post-Emerald/pre-bridge, post-ocarina and reload:
NPC populations/text, path changes, gates, scene layers and conditional cutscenes.
Enumerate every Lost Woods doorway with destination room/scene/spawn and source
condition, including wrong-way returns. Identify the Meadow decision edge.

List all actors by room, object/audio dependencies, rewards and source availability.
Budget overlapping room banks, not all ten resident at once. Preserve 8.3 IDs.

Review: graph/source evidence, persistent flag ownership, M6b/M7 interfaces and
explicit pending Meadow decision. No invented guard as a convenience workaround.

### M6b checkpoint: forest aftermath (not milestone M6b)

Port post-Emerald Kokiri dialogue, Mido behavior and actual exit guard transition.
Reuse M3 NPC models and message rules. Update only source-defined flags on completed
interactions; entering the forest alone must not simulate conversations.

Review: return from M5 naturally, repeat talk, exit/re-enter, save/reload, and earlier
save fixtures. Mido at the forest and an adult Lost Woods Mido are different cases.

### M6c: Lost Woods routes and encounters

Import all rooms with their source actor/layer lists. Wire right/wrong passages and
room banks. Add reachable En_Okuta and other source-present combat actors with full
damage/drop audit. Port Skull Kid talk without fabricating unavailable song branches.
Implement the target game using actual Slingshot impacts, source scoring/rewards,
cancel/retry and capacity checks; confirm which rewards are reachable in this demo.

Lost Woods owls own their dialogue/choice/flight/camera behavior here. Scrub shop
identities/placements feed M6b; do not build a second purchase system. Source bomb
rocks remain closed while required equipment is absent. Check manual jump/climb
cannot bypass source blockers due to an incorrect collision import.

Review: traverse graph forward/back, take every wrong exit, target game success/
failure/retry, owl repeat, actor unload/reload and source rewards.

### M6d: Saria bridge and destination contract

Port Saria bridge staging, baked shots, Fairy Ocarina get-item and progression
writes. Double-Start skips only current shot; grants/flags/destination still happen
exactly once. Reuse M5 cutscene transition discipline for bank and control restoration.

Review: ordinary playback, consecutive shot skips, already-owned item/flag fixtures,
re-entry and save/reload after completion. M7 closes actual Field intro/destination
runtime acceptance; leave that named check pending until its scene exists.

## Acceptance and later obligations

- Ten-room source graph exists; correct/wrong exits, room IDs and source blocks
  behave correctly. No child Mido gate, no merged adult population.
- Post-story forest flags/text and exit access survive reload without duplicate
  grants or forced replay of story cutscenes.
- Required source rewards and target-game outcomes use shared capacity/persistence.
- Meadow policy is decided and truthfully implemented/documented before final
  scope acceptance; its unresolved edge is a blocker, not an optional TODO.
- M6b closes named grotto/shop/token integrations. M7 closes bridge-to-Field live
  handoff. Host fixtures alone do not establish either runtime outcome.

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
