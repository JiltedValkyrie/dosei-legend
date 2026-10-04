# Next chat: populated-room regressions, connected world and full actor coverage

Latest follow-up (2026-10-04): shadows are now twelve-sided circular disks,
not diamonds. Adult Link uses ADULTACT.PCM with original adult attack, jump,
climb, hurt, fall, landing and death recordings (13 replacements). Scene-age
changes and return from opening audio select the correct bank; a failed load
stays silent and is retryable. Non-voice bytes, resident offsets, playback rates
and sound-RAM/area budgets are unchanged. Adult tails are bounded to the shared
event slots with a short fade; exact original sequencing remains approximate.
The adult PCM was regenerated/staged through WSL. Final ELF boundary passes at
0x06083FF0 (16 B spare); final usual Clean image is blocked by Kronos's open ISO.
Host checks this follow-up: 22 action audio, 1 age-bank lifecycle, 1 shadow,
6 sprite, 3 collision-index and 28 collision cases pass (61 total).

NPC complaint remains active, not resolved: only six generic actor types are
imported. Fixed a separate residency defect: eagerly loading unused animation
sheets for one object could crowd out later characters. Keep one compatible
sheet per object/skeleton; later poses use the existing approximate fallback.
Regression covers extra same-object clips and later different-object spawns.
Most town actor profiles, complete dialogue/rewards and the reported inability
to talk still require work. No universal talk fix or full population claim.
Asked human which maps/NPCs and era; no answer yet. Preserve source conditions.


2026-10-04 follow-up: Song of Time now makes Child Link adult via a scene reload
at the saved entrance (not a toggle back); failed loading restores Child age.
Level Select explicitly labels its existing R toggle ADULT LINK: NO/YES.
Shared ground-shadow helper covers sprite NPCs/animals/cutscene cast, Link and
native fairies with one untextured dithered quad. No-floor/offscreen/high-flight
cases skip submission. Legacy mesh enemy/boss shadows remain outside this pass.
41 focused host checks pass; final image evidence is in DEMO_PLAN.md.
Human runtime appearance/FPS checks pending; no emulator launch or new commit.


2026-10-04, main carries the oot-core checkpoint. Preserve shared work. This handoff records
partial implementation and remaining work, not world/runtime acceptance. Read AGENTS.md,
CLAUDE.md, DOSEI-LEGEND-BIBLE.md, DEMO_PLAN.md, OOT_CORE_PIPELINE_PLAN.md and
ACTOR_SPRITE_ROLLOUT_PLAN.md first.

New active human report: capped inventory owns all source slots but pause art
shows four items/Emerald; map stuck at Kokiri; Ocarina cannot equip/play; Adult
Link missing; generic interiors have only top view; doors have magenta normals;
hearts flicker; Ranch/Kakariko with Cuccos run slowly; graveyard tomb texture
has holes. Fixes are implemented, host-tested and Clean target-built. See
[PLAYER_REGRESSIONS_2026-10-04.md](PLAYER_REGRESSIONS_2026-10-04.md)
for controls, resource layout, verification and remaining song/item/adult gaps.
The prior build evidence below is historical.
Source collision differential: 3,190 probes match, sqrt calls 27,214 -> 701.
578 distinct host cases pass. Final .bss end 0x06083E80 leaves 384 B below SGL;
Link pose/matrix/skin and actor-view carves preserve heap/actor capacities.
Matching SH-2 audit passes new bounded paths, max audited frame 172 B; existing
wide math remains debt. The ISO matches all 889 staged payloads. No emulator
launched; human visual/performance acceptance remains pending. Logs:
build/regression-clean-final-link.log, build/regression-target-audit.log,
build/regression-iso-audit.log. Keep the old 656 B margin below historical.

Baseline 9d384cd contains the prior sprite/CPU/save/cleanup checkpoint. Current
continuation is recorded in cf9ba39 and merged into main. The prior main is
preserved as oot-vslice-demo (7c8cc93). Retired dev history remains at tag
archive/dev-2026-10-04 (5b560ab), with its dirty worktree detached and intact. Full asset
regeneration and the final C-only WSL
Clean relink pass. Usual game-clean.cue/.iso rebuilt; .bss ends 0x06083D70,
656 B below SGL. 400 distinct host checks pass. Runtime acceptance remains open.

Integration evidence: the initial link overflowed by 784 B. Save state moved
to low RAM; write/summary buffers each exceeded the 1 KiB master stack and now
use separate 4 KiB scratch carves. Another full asset build linked 80 B over;
moving draw-cache ownership into low RAM fixed the remaining overflow. Carves
0x27800/0x28800/0x29800/0x2A800 hold live save/write/preview/draw cache, with
size/order gates and explicit boot initialization of save/cache. Host tests
poison surrounding bytes and cover nested summary during write and repeated
cache cleanup. Heap sizes, actor capacities and SDK error handling are unchanged.

Logs: `build/world-completion-build.log` records full asset generation and the
80 B failed link; `build/world-completion-link.log` records the successful
C-only relink. An intervening WSL build stopped during asset generation and
was restarted fully (`world-completion-interrupted.log`); it is not verification.
`world-logic-tests.log`: 369 checks; `world-assets-tests.log`: 30 checks; the
additional low-RAM draw-cache lifecycle check passes with the five existing
core-sprite checks and two save-carve checks (400 distinct checks total).
`world-target-audit.log`: changed save/door/sprite/host objects have no wide or
float helper references; matching Clean disassembly agrees with __bend.
Final save-summary frame is 12 B and save-write frame 72 B; these are individual
frames, not proof of whole call-chain stack bounds. Existing core wide math remains.

Virtual story banks now use IDs 1024+ / C-prefixed files, separate from real
scene IDs. Post-emitter uniqueness/header checks prevent the original room
overwrites. Removed 76 exact retired generated/staged S2/S3/S4 MSH/TEX/MAP
files, preserving real RGB backdrops. Staged scenery/budget checks pass.

## Earlier human evidence and cleanup history

- Startup/zone changes repeatedly show Jo Engine error:
  `In dosei_allocator_free(): Null pointer`. Screenshot: dynamic memory 22%,
  sprite memory 0%. Human presses Start about six times per zone to dismiss it.
  This is a null-free error, not evidence of RAM/VRAM exhaustion.
- One NPC now visible in Lon Lon Ranch. Full population, animals, dialogue and
  spawn conditions are not accepted. Do not assume every missing NPC should
  spawn in the currently selected age/time/story layer.
- Generic-zone doors remain unusable. User requires traversal through all
  zones/interiors, not level-select-only access, plus all NPCs and dialogue.
- Historical target build passed: `build/ranch-sprite-build.log`, usual Clean image,
  .bss end 0x06081DC0 / 8,768 B spare. Its 36 host checks missed the null-free
  regression. Subsequent cleanup repair now built: `build/null-free-fix-build.log`,
  usual Clean image, .bss end 0x06081DE0 / 8,736 B spare. Runtime acceptance pending.

## P0: cleanup repaired; runtime acceptance pending

Continuation: story/emerald loaders now release old ownership and roll failed
loads back. Test stubs reject NULL/double frees; tests execute failed allocations,
all 17 cutscene acquisition failures, retries and 256 ownership combinations.
Do not replace these with manually injected-pointer tests alone.

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
teardown and cutscene cleanup before loading/after freeing. That baseline Clean
rebuild passed; continuation target verification now passes too. Human still
verifies startup and repeated transitions without dismissals.
The newer player regressions above take priority; full P1/P2 coverage remains required.

## P1: wire the whole scene/room/entrance graph

Implemented this continuation: shared En_Door/ordinary Door_Shutter policy,
source layer masks, exact handle-door collision seal opening, static door leaf,
source key/switch/room-clear/time/event gates, scripted entrance request bridge
and explicit missing-destination refusal. Save v11 retains old versions and adds
124 source-scene flag slots, dungeon items/keys, age/time/cutscene, bottle slots
and source scene/entrance identity. Scene flags seed before actor initialization.
Review [WORLD_ROUTE_AUDIT.json](WORLD_ROUTE_AUDIT.json) for each blocked edge,
missing reverse edge, source condition and extraction error. Structural reach
is not human traversal acceptance. Only 75 scene assets are registered; 35
source destinations remain absent. Virtual story banks must not alias these
gameplay scene IDs or overwrite their staged files. Combined target and
namespace/staging checks now pass. Audit: 1,551 layer exits (634 blocked),
1,738 transition actors (1,124 blocked), 379 missing reverse scene edges,
94 scripted entrance assignments and nine extraction errors. Sixty-seven scenes
are structurally reachable in the union of all layers; this is not a playable
route count for one age/time/story state.

Audit original scene/entrance tables, all alternate headers, transition actors,
collision exits, door parameter variants, spawn records and event gates.
`build_room_scene.py:transitions()` now keeps En_Door and gated shutter records;
unsupported records remain closed. `strict=False` does not silently drop those
edges. Missing assets/rooms and special transitions stay explicit audit blockers.

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

Implemented this continuation: [ACTOR_COVERAGE.json](ACTOR_COVERAGE.json) contains
429 profiles, 110 scenes and 836 room layers, plus static dynamic-spawn closure,
conditions, dialogue/reward/drop sites, hashes, boss dependencies and unresolved
classifications. No scene ready. Forty-one horse clips are baked offline under
build/generated/horse-sprites; no horse runtime import or disc staging. Sheet
storage totals 910,945 B including allocator terminators; the largest live cel
with aligned CLUT costs 1,472 B, not a completed scene population budget. Importing
existing horse Fx actions would add forbidden wide arithmetic; 32-bit action
lowering, bounds/anchors, cloned horses and mount/save behavior remain required.

Ranch source examples: child day before Talon's return has Ingo and normal
horses; after return, Malon and young Epona become eligible. Night exterior has
enemy replacements. Adult day Malon is missing En_Ma3, not imported En_Ma2.
Do not force every Ranch character into the same room/layer.

Host now discovers later same-room sheets, validates packets, avoids repeated
failed reads, culls before spending visible slots and clears reused native view
keys. L+R overlay separates actor/missing-sheet/fallback-pose/slot counts.
Dynamic sets still need preloading and budgeting before triggers; eight-slot/
16-view caps remain debt. NPC save predicates now include equipment, quest
items, ocarina, bottles and era/time. Automatic talk and milk reward parent/
textbox handshakes are implemented. Source inventory ownership now includes the
full test loadout, but usable item actions, minigame timers/carrying, songs and
many source dialogue branches remain open.

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

Latest user addition is implemented: Level Select **ALL ITEMS + MAX STATS**,
default No every open; L toggles items, R selects Child/Adult, A enters. Era defaults
Child. Yes grants source inventory slots
(Time Ocarina/Longshot and final trade variants), all gear owned, quest mask
0x00ffffff (all stones/medallions/songs), 20 hearts, capped ammo/magic/upgrades,
500 rupees, 100 source tokens, dungeon items and eight source-debug keys. No
extra eventChkInf/story completion bits. The source has mutually exclusive
bottle/trade/upgrade slots; they are not simultaneous independent item actions.
Unimplemented C item controls remain open. Toggle/navigation never grants;
confirmed entry retains the existing fresh test file/no backup slot behavior.
Save v11 is 2,433 bytes and still migrates v2-v10. Wallet cache/HUD support 500
without uint8 truncation or out-of-bounds digit access.

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
