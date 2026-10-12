# Full OoT recomp plan

## Current task and verification (2026-10-12)

**Current request: plan completion of handwritten C gameplay retirement and
full core ownership.** The executable work order is
[Full core ownership and C retirement](#full-core-ownership-and-c-retirement).
This is a planning/source-review update only: no runtime changes, new test
results, target builds or emulator runs. Existing repair work remains with
Claude; human owns runtime testing. Subsequent implementation needs an explicit
file owner at handoff because the shared working tree contains active repairs.

**Gameplay repair handed to Claude; human tests.** Human tested candidate-10 Clean
`b54638cd` and reports much better performance. Rock grab, invisible held
Deku Stick and coarse first-person aim are now the priority; they are no
longer deferred. Preserve candidate-10 speed work and one source Player.

Candidate 10 remains the accepted performance baseline: envelope v3,
conditional attributes and touched-tile fog reduce prepare from 23-30 to
12-15 ms. Moving whole frame remains 64-79 ms (10-15 FPS); aim 50-53 ms
(16-20 FPS). Moving 20 FPS is unfinished. Its 222 host tests, math audits,
budget and 1,424-file ISO checks passed. Debug had 496 B of high-RAM spare;
Clean had 5,968 B. Historical candidates and measurements belong in
[the handoff](PERFORMANCE_HANDOFF_2026-10-12.md).

Repair implementation in progress, not runtime-accepted:
- API33 host prop adapter gives source Player a live rock/pot Actor identity.
  Source owns pickup/put-away/throw and hand attachment; existing host prop
  physics, collisions and drops remain. Host handles cross the boundary,
  never host Actor pointers; offer before kick, read after join.
- Stick rendering reads source item/burn state and hand/tip anchors; no
  legacy item/ammo state is revived to make it visible.
- First-person input magnitude is halved before source aim math. Walking,
  simulation cadence and source camera/projectile alignment remain intact.
- Saturn tap-ready/tap-fire remains intentional. A physical release after
  the first tap is not a valid firing test; test a distinct second press.

R0 carry review (Claude, candidate 12: code, host tests and temporary
Debug `game-perf-kokiri` 5dedadf9 built, 240 B spare; human test pending): cancel/death/room-reset already follow source detach. Grab
failure fixed: core now applies EnIshi/ObjTsubo offer ranges and Player's
+/-45 deg admission; HUD Grab/Throw/Drop come from source
`Interface_SetDoAction` via API34 `do_action` (was a reachable stub).
[Handoff](PERFORMANCE_HANDOFF_2026-10-12.md#gameplay-repair-candidate-12-claude-2026-10-12-r0-carry-review).

Candidate-11 temporary Debug built: 318 host checks pass, one existing skip;
math audits zero failures, budget passes, all 1,424 ISO files match staging.
High-RAM spare is 80 B. Short private-desktop observations showed released
seed on second tap, visible held stick and rock pickup after facing adjustment;
these do not establish full parity. Human now explicitly says no automated
emulator testing: Claude fixes, human tests. Emulator closed/config restored.
Normal Debug/staging and accepted Clean b54638cd preserved. Review carry
cancellation/throw/drop/room reset and prompt-facing agreement; human checks
these plus aiming feel, burning sticks and repeated shots. No actor/geometry
limit cuts, slave rollback or gameplay tick reduction.

## Full core ownership and C retirement

This is the current implementation sequence, superseding older isolated-import
orders below. "C retirement" means retiring handwritten gameplay authority;
the source decomp itself is C, and the Saturn backend may remain C. The finished
game uses source Player, actors, collision, inventory/progression, camera and
story rules, with explicit Saturn adaptations. All retail scenes, eras,
day/night/story layers, dungeons, bosses and ending remain in scope.

### Starting point and boundaries

- **Implemented and previously target-built:** real Player and core z_bgcheck
  are live with `PLAYER_SOURCE=1` / `CORE_COLLISION=1`; source actors, tools,
  messages and scene packs are partially integrated. Host camera, props,
  contacts, save/item services and story paths still own gameplay. API33 carry
  is a temporary host-prop adapter, not source prop replacement.
- **Host-tested prototype only:** demand animation request/cache code exists;
  the live makefile uses the whole resident `PLAYANIM.PFB` bank. Production
  action-start gates, complete cutscene sets and CD servicing remain open.
- **Runtime acceptance:** candidate-10 speed improvement and particular earlier
  features have human evidence; complete Player parity, moving 20 FPS and
  whole-game traversal do not. Candidate-11 temporary Debug repair evidence
  above must not be applied to the preserved candidate-10 Clean image.
- **Keep:** Saturn SGL/VDP rendering, Link meshes/gear/skinning, sprite drawing,
  input mapping and labels, HUD/pause/minimap presentation, audio/CD, backup
  device/file format adapters, asset conversion, loaders and SH-2 scheduling.
  Move gameplay decisions out of these modules where still present. Do not
  delete `player_*.c` by wildcard: `player_input.c` contains required adaptation.
- **Retire:** duplicate action machines, world/contact solvers, item/reward
  writers, actor/story scripts and proxy Player. Thin queries over the single
  core world and presentation snapshots may remain; permanent duplicate
  gameplay worlds or state machines may not.

### Ownership ledger to close

These are source-inspected migration units, not completed replacement claims.
Before changing each unit, expand its row into exact symbols/callers, preserved
behaviors, source counterpart, field writer, tests and human acceptance evidence.
Use [PLAYER_MIGRATION.md](PLAYER_MIGRATION.md) for the Link preservation detail,
and existing actor/route ledgers for content rather than inventing parallel lists.

| Unit / current files | Required final owner | Retire or retain after acceptance |
| --- | --- | --- |
| `recomp.c`, `player_air/bg/climb/crawl/lift/push/slope/water/items.c`, `link_anim_state.c`, proxy `bridge_player.cpp` | Source Player and source action/animation timing | Delete old movement/action/item branches and proxy; keep pad conversion, renderer, frame decoder and render interpolation |
| `oot_core_host.c`, `save_state.c`, `health_hud.c`, `bridge_items.cpp`, `bridge_player_source.cpp` | Source inventory/health/magic/equipment and progression state, with one authoritative writer per field | Replace per-tick bidirectional mirrors and host mutation callbacks with commands/snapshots; retain serialization, device I/O and HUD drawing |
| `attention.c`, `recomp_camera.c`, `recomp_follow.c`, `player_camera.c`, camera hooks in bridges | Source Attention and camera modes, plus explicit Saturn camera additions | Remove duplicate target selection and camera gameplay rules; retain view/projection adapter, overhead/house controls and accepted easing |
| `world_props.c`, `gameplay.c`, `item_drop.c`, `dungeon_doors/puzzles/torches/webs.c` | Source prop/puzzle/drop actors and source flags/contact responses | Replace carry proxies, host pushes/warps and reward rules per actor; retain prop geometry drawing and loading |
| `actor_sys.c`, `collide.c`, legacy enemy modules and host combat in `gameplay.c` | Source Actor lifecycle and AT/AC/OC collision checks | Remove C actor pool/contact dispatch only after its last live consumer is migrated; retain snapshot-to-render dispatch |
| `story_route.c`, `emerald_story.c`, `cutscene.c`, `cutscene_actor.c`, `scene_flow.c`, remaining NPC logic in `gameplay.c` | Source scene/entrance, actor, message and cutscene rules | Retain transactional loading, fades, camera/render/audio adapters; remove copied quest/cue/reward decisions |
| `bg_core_link.c`, `bg_core_shim.c`, `recomp_collision.c`, `shared/lib/collision` runtime selection | Core z_bgcheck storage, queries and dynamic actors | Remove C Player wrappers/legacy solver once unused; keep needed read-only core-query adapters; retire C dyna proxies with their owning props |
| `minimap.c`, HUD/pause/file-select and music/environment hooks | Core supplies map/progression/time/item/music intent; Saturn presents it | Keep backend code; audit map discovery, menu mutations, clock/song rules and music triggers for hidden gameplay ownership |

For every bridge `STUB`, `HOST` or copied `REAL` body, record its source function
and classify it as a required gameplay replacement, retained platform service,
or proven unreachable N64-only operation. Reachable camera, room, reward,
cutscene and item no-ops are open requirements, even when the link succeeds.
Importer patches belong in `tools/oot_core_import.py` or its source modules;
generated `build/oot-core` edits cannot be the sole implementation.

### Ordered implementation waves

| Wave | Concrete deliverable | Completion gate |
| --- | --- | --- |
| R0 — preserve the live baseline | Close rock pickup/throw/cancel/room-reset, held/burning stick, low-FPS aim and repeated-shot parity. Inventory remaining Player fixes and every cross-boundary writer; capture matching source/build identities. | Focused executing checks plus human repair acceptance; preserve candidate-10 speed work, both CPUs, actor/heap capacities and ordinary images |
| R1 — core state and item transactions | Make core save/inventory/progression state authoritative for live play. Load once from the versioned Saturn save, apply menu/equipment/reward commands once, publish read-only snapshots after join, serialize a coherent core snapshot. Migrate health, ammo, magic, bottles/fairies, rupees, equipment, keys and flags by field group. | No field has two writers; save/reload, death/revive, era/equip change and reward consumption round trips pass; old saves/preferences and session-only cheats preserved |
| R2 — production demand animation | Wire the existing cache into real Player action gates and scene/cutscene entry. Inventory common/age/equipment sets and complete cutscene dependencies; implement prefetch, owned reservations/pins, cancellation and error recovery through CD/audio services. | Common movement stays ready; no action/cue/reward advances on a cold clip; full cutscene preloaded/pinned without per-shot I/O; measured working set and load/recovery peaks fit |
| R3 — retire C Player and proxy | Complete remaining movement/combat/water/climb/talk/gear preservation rows. Move targeting authority to source Attention. Split mixed files, remove accepted C Player branches, `link_anim_state.c` action logic, C projectiles/item timers and proxy `bridge_player.cpp`. | Both-era human parity batches pass; production link has only source Player; removed symbols have no remaining callers; pad/UI/render adapters remain functional |
| R4 — core camera, scene and story services | Replace reachable camera/one-point/room/transition stubs with source behavior adapted to fixed point. Preserve overhead turns, first-person/house modes and Saturn prompts. Transfer entrance/respawn, dialogue-close, song, time travel, cutscene cue and progression decisions into core. | Route round trips, failed-load restoration, doors/warps/death, whole-cutscene entry/exit and source quest predicates pass; no duplicate cue/reward/camera controller |
| R5 — retire host actors, props and contacts | Replace each remaining host prop/NPC/enemy/puzzle with its source actor in scene packs; move combat and dynamic-platform ownership with it. Keep API33 carry/contact adapters only until their individual consumers are accepted. | Each actor retains spawn conditions, damage/stun/tool/hold interactions, talk/reward/drop rules and flags; scene budget covers all reachable actors/effects; delete host owner immediately after that unit's acceptance |
| R6 — complete the full game | Finish remaining scene/era/layer rosters, source entrance graph, horses and minigames, bottles/trades/songs, adult dungeons, bosses and ending. Field/Water Temple work and the opening route seed the order, not a scope limit. | Coverage ledger tracks every retail scene/layer and required dynamic dependency with separate host/target/human evidence; complete child/adult progression and save round trips accepted |
| R7 — remove remaining production fallbacks | Delete obsolete C gameplay build branches, `PLAYER_SOURCE=0` / `CORE_COLLISION=0` production selections and remaining no-core gameplay mode; remove dead ABI, loaders, generated payloads and reserved storage only after consumer audit. | Matching Debug/Clean links and disc contents have no retired owner or fallback; measured reclaimed memory; all remaining bridges are documented backend services; no unresolved required gameplay stub |

R0 is the current implementation task, assigned to Claude; carry review
is candidate 12 (above), remaining R0 items await human checks/inventory. R1 and R2
then close the state/animation prerequisites for R3. R4/R5 may be staged by a
bounded subsystem once its R1/R3 dependencies are ready; source actor work that
does not touch active repairs can continue under its existing plan. R6 proceeds
per accepted scene pack, without waiting to collect every actor into one giant
cutover. R7 cleanup happens incrementally after each acceptance, with a final
whole-tree pass. Do not postpone all deletions until the full game is playable.
The moving-20-FPS target remains required; optimize the chosen core ownership
and fix severe regressions within each wave rather than gate migration on an
open-ended benchmark project.

R5 content order: finish current Kokiri/interior/Deku Tree legacy overlap;
close already-open Field and Water Temple dependencies under their plans;
continue Lost Woods/Field/Ranch/Market/Castle/Kakariko and the remaining game
in source progression/dependency order. Boss exemption preserves models,
pose-driven hitboxes and puzzles while source boss logic replaces handwritten
logic. Non-boss NPCs/animals/fairies/enemies use baked sprites, semantic gameplay
anchors and clip clocks, never runtime skeletons or model fallback. Update
[ACTOR_SPRITE_ROLLOUT_PLAN.md](ACTOR_SPRITE_ROLLOUT_PLAN.md) and its coverage
ledger in every actor implementation task; map admission alone is not readiness.

### Acceptance and deletion protocol

For each row, record **implemented / host-tested / target-built /
human-accepted / retired** separately, with exact artifact identity and remaining
gaps. A prototype, successful import, passing build or narrow runtime observation
does not advance the other columns. No new result is claimed by this plan.

1. Trace actual callers and writers in the current shared tree; preserve every
   Saturn addition and its verification before changing the owner. Keep only one
   live owner during transition. Each rollback path needs a named replacement
   and acceptance gate; it must not become the default development target.
2. Test the affected ownership boundary with executing checks: input edges across
   skipped ticks, exactly-once damage/items/rewards, stale handle rejection,
   dynamic carry/contact history, save round trips, cancellation and failed scene
   restore as applicable. Adapt legacy fixtures to the new public contract before
   removing their implementation dependencies; do not delete coverage to go green.
3. Preserve the 20 Hz/input/contact contract and master/slave ownership. Offer
   commands before core kick, read coherent snapshots after join; no renderer or
   UI access to mutating core state. Core owns movement; remaining host displacement
   or warp requests need explicit ownership and eventual source replacement.
4. Build in WSL per [BUILD.md](BUILD.md), using matching host/core/scene packs,
   ABI and asset formats. Run relevant math audits, region/heap/VRAM/load-peak
   guards and ISO/staging checks. 32-bit stored values and native SH-2 products
   stay allowed; software-wide/soft-float helpers remain banned. Reserve no
   speculative deletion savings and reduce no actor, geometry or heap capacities.
5. Human runs relevant movement/combat/items/water/climb/dialogue/cutscene/
   era/save/route checks on the matching image. **No automated emulator testing.**
   Preserve accepted images while preparing the next authorized candidate; do
   not overwrite mounted discs. Runtime failure keeps that unit unaccepted.
6. After acceptance, remove only the obsolete owner's code, callers, build
   inputs, adapters and assets. Recheck the resolved link and stage, measure
   actual savings, and reconcile this plan plus the unit's handoff. Retain needed
   backend code even if its old filename contains `player` or `gameplay`.

Full-core completion requires all required gameplay owned by source-backed core
systems, preserved Saturn functionality, accepted full-game coverage and retired
duplicate owners. A Player proxy, shared query bridge, source-only build or 101
registered maps alone does not satisfy that result.

## Prior review checkpoints (historical evidence, 2026-10-12)

Latest (Claude, 2026-10-12): Mednafen `slave scene prepare stalled (N)` root
cause found and fixed in code: the FRT counter was read as a 16-bit word;
Mednafen returns only FRC >> 8, so the extended timer jumped 293 ms per byte
wrap and fired the watchdog falsely (human N values 19-52 prove the slave was
running). Byte FRCH->FRCL reads now; usual Clean image rebuilt; audit now
fails on FRT word loads. Human now reports no crash, but Mednafen about 5 FPS
versus Kronos 20. Exact test duration/routes unspecified. Earlier Mednafen timer/profiler numbers are
invalid. [Fix record](PERFORMANCE_REVIEW_2026-10-12.md#root-cause-and-fix--frt-word-read-claude-2026-10-12).
Exit/aim acceptance remains unspecified.

Human reports Claude's slave/speed work raised FPS from 10 to 20; the new slave
jobs must be preserved. Current task is Astra's authorized combined Debug
performance batch (handoff after sign profiling); no Clean builds until Debug
is ready for the human's 20 FPS test. Six focused timer/job
tests and 11 audit self-tests independently passed at the earlier checkpoint.
Claude 2026-10-12 follow-up: the slave wrap limitation is fixed (slave FRT
/128 per job) and Debug `build/game.cue` adds VBlank pacing, master-waits and
slave-job rows 16-17 plus slave core profiling (Clean rebuilt to match). Next:
human Mednafen Debug reading with Shift+F1 in Kokiri; assign the 5 vs 20 FPS
gap only from that. Guide: DEBUG_OVERLAY.md "Mednafen reading".
Since then: prep-first scheduling and Low RAM geometry are built and human
measurements show gains: title 20 FPS, Kokiri idle 8, moving about 6.6. Music
check passes. Coverage is now complete and averaged; latest human Debug shot
shows signs 29.7 ms out of 30.4 ms world-props remainder, whole frame 114 ms.
Astra batch implements conservative sign culling, one intact-sign geometry
batch with piece fallback, high-WRAM C actor pool, validated handle hints and
single-read NPC pose access. Sign partFlags are snapshotted before slave work
to avoid drawing through live actor lists. 66 focused host tests pass.
Final Debug target build passes, .bss 0x06080C50 (13,232 bytes spare), both
math audits zero failures and all 1,434 ISO payloads match staging. Clean
hash c3f29128 remains unchanged. Full evidence is in the performance review;
Human retest: up to 13 FPS idle; screenshots show 12 FPS at fr80.2 ms and
8.1 FPS at fr116.8 ms. Gains observed; sustained 20 FPS not demonstrated.
Dialogue rows freeze (except bottom VRAM/M/S), so chat FPS is stale evidence.
Human says leave that overlay behavior alone. Current follow-up implements
joined DMA cel uploads, protected/rotating cel-cache replacement, exact
visible-vertex packing, and concurrent master scene prep/slave core updates
(M default, old P/C orders selectable). No gameplay ticks/contacts/story cut.
Follow-up Debug built: 81 host tests pass, .bss 0x060813A0 (11,360 B spare),
host/core math audits clean and all 1,434 ISO payloads match staging. Debug
hash 5f3eec29; Clean unchanged at c3f29128. Human retest confirms idle
12-18.7 FPS, moving about 8 FPS; aiming also slows substantially. Human clarified
rock grab fails and held C-button stick is invisible: separate issues. NPC talk
was working; general talk failure/phantom stick diagnosis withdrawn. Human
explicitly defers both bugs and requests performance work. No full gameplay acceptance.
Interaction follow-up adds retained source-input diagnostics on Debug row 21;
80 control/aim host tests pass, including A surviving a skipped tick without
generating an item press. Diagnostic Debug 7f39dee3 built; both math audits
pass, all 1,434 ISO files match staging, Clean unchanged. Root cause remains
open. Human trace confirms A delivered to grounded, empty-handed Player, no
talk offer/message; no gameplay fix claimed. Current performance batch preserves
vertex prefix order across cull changes and computes side masks once per vertex,
with no changed visibility criteria. 16 focused tests pass; Debug 4568aa9c built,
both math audits clean, 1,434 ISO files match staging, Clean unchanged. Runtime
moving-frame gain not measured yet; compare whole frame and mp/pk, not pp alone.
Aim pose optimization remains open; both deferred bugs stay in BUG_FEATURE_LOG.
New larger rendering batch replaces in-place packing by a bounded high-WRAM
draw-point gather (512 vertices). Only visible indices change and are restored
before rebuilding; source points/hidden faces stay untouched. Overflow uses
the complete bank, not dropped geometry. Modes 0/full and 1/in-place remain.
Player anchor-only hierarchy walk retains source overrides/post callbacks and
matrix operations but omits discarded per-limb N64 matrix/display output.
30 focused tests pass, one existing migration test skips; additional control/
aim/anchor suite 81 pass. Debug c9cc6dc8 built, .bss ends 0x06082DB0 (4,688 B
spare), both math audits clean, 1,434 ISO payloads match staging. Clean unchanged.
Runtime moving/aim gain and full-turn/reload/weapon parity remain unaccepted.
Artifact details and combined human test gates in the performance review.
Latest small shadow cost does not support thrashing as the large cost.
jw0 does not rule out core contention gains.
Slave /128 extends the wrap period to about 293 ms; it is not an unlimited
duration counter. See the latest performance review for screenshot units and
test limits. Clean movement/aim/exits/reloads remain pending acceptance.
Real Player and core collision are live in Clean (`PLAYER_SOURCE=1`,
`CORE_COLLISION=1`); slave jobs remain enabled. Migration parity and human
acceptance are incomplete. The whole resident animation bank does not satisfy
the demand-loading requirement.

Current fixes, scope, tests and acceptance queue:
[performance review](PERFORMANCE_REVIEW_2026-10-12.md). Repairs cover slot order,
source aim/input adapters, uncached slave ownership, shared pose caching,
collision stamp initialization and duplicate proxy tool timers. WSL Clean rebuild
passes; 102 focused tests pass, one legacy probe wrapper skips (separate collision
probe executed). Host/core SH-2 audits pass; all 1,434 ISO files match staging.
Human says the first repairs seem okay, then reports an oversized aiming arrow,
wrong exits into Lost Woods, and repeated Mednafen scene-preparation timeouts on
the title screen and in Kokiri Forest (Link's house works). Crash now reported
absent after Claude's timer repair; route/aim acceptance and moving-FPS signoff remain open.
Follow-up code removes the aiming overlay and hides the nocked arrow only in
first person, imports and binds original per-layer exit lists, bounds source
exit indices, and passes entrance spawn/respawn identity before Player init.
Slave scene preparation keeps its job but now receives explicit timer ownership
and publishes progress for the watchdog. This addresses false completion
deadlines and adds a stalled-progress diagnostic; this earlier attempt did not
fix the FRT read defect. Expanded host batch: 118 pass, one legacy probe wrapper skips.
API32/format-3 Clean rebuild passes; .bss ends 0x0607D250 (28,080 B spare),
host/core math audits pass, and all 1,434 ISO files match staging. Human
route/aim runtime acceptance remains unspecified. That Mednafen retest failed;
the false-timeout cause (16-bit FRT read) is fixed above; latest human reports no crash.
The dated artifact sizes and open-next-step claims below describe their own
checkpoints; current ownership and next actions are this section and the final
queue, not the older isolated-migration state.

## Earlier implementation checkpoints

Prior task (human, 2026-10-08): implement Hyrule Field decomp enemies next,
superseding the earlier enemy scene order. Field scene-pack/source sprite work
is in progress. Focused source spawn/drop probes and isolated WSL SH-2 actor
compilation pass. The 59-case focused host batch passes; actor/effect pack links
with a clean math audit and fits alongside scene data. Raw Clean target passes
the fixed SGL boundary after redistributing existing heap bytes to low WRAM.
The usual Clean test disc is rebuilt: 84,131,840 bytes, 1,461 files matching
staging, core/host/pack math audits clean and .bss 0x06083400 (3,072 B spare).
Human accepts the shown adult Poe defeat/soul dialogue (screenshot VRAM 51%,
CPU~82%); child cases, bottles, Big Poes and population checks remain open.
Final focused batch: 72 host cases pass. Field sound scene-selection correction
is code-only pending the next build; current Kronos image is left intact.
Broad legacy host
discovery is not green. Scope and remaining
requirements: [Field enemies](FIELD_ENEMIES_2026-10-08.md). Preserve all original
spawn/combat/drop paths; adult Poe bottles remain a Player integration dependency.
Mandatory real Player migration is still required.
Human follow-up in progress: implement Water Temple enemies, obstacles
and puzzle actors as a dungeon integration test. Preserve source age/item,
water-level, key/door and room-clear requirements. Full dungeon integration is
unfinished; inventory identifies 23 rooms and runtime scene 79/source
scene 5. All 36 original prop/enemy/support actors, including En_Holl passages,
compile in an isolated SH-2 probe; no temple pack is staged. Source-owned water borrowing is implemented
with host/lifetime tests passing, including boxes beyond the legacy 16-entry
override limit. Original water-controller action probes pass level changes,
switch replacement during movement and local rise/fall; six water/lifetime/rate
host cases pass. Source transition tables and room-side spawning have three
passing host cases; old OOC layouts now fail closed. Sprite conversion code and
bakes cover Shell Blade, Stinger, Tektite (red/blue), Keese (normal/fire body,
lens-only hidden variants) and Spikes (rock/metal/spiked): 25 isolated sheets.
Sprite views and host tests pass; the sprite archives link in the Clean raw
target (Z27 sheets 394,097 heap bytes, below Field's 479,243 peak). No temple
pack, runtime admission or gameplay acceptance yet. Like Like and Dark Link
remain unconverted pending real Player work. Clean raw target: .bss ends
0x060837f0, 2,064 bytes below SGL; core and converted-enemy math audits clean.
The accepted ABI25 Field ISO is unchanged; all OOCs must regenerate before
mastering another image.
Boss exemption and Player-dependent interactions remain. Current scope and
dependencies: [Water Temple](WATER_TEMPLE_2026-10-08.md).

Human-accepted texture reduction (2026-10-08): reduce the usual
Clean image's room TEX tiles to save budget for remaining content. Code:
`DOSEI_TEX_HALVE=0/1/2` uses the existing indexed sampler before the room cap;
mode 2 covers rooms, panorama banks, Navi's shared pool and the complete Field
pool. Mode 1 also covers Link/ADULT/LGEAR mesh TEX; SPR/HUD/get-item dimensions
stay unchanged per the human's scope clarification. Clean now defaults to mode 2;
explicit 0 restores full density. Standalone tools and other variants default to
0. Existing caps and the command region are unchanged.
Host: 34 focused cases pass, plus actual retained-bank/Field/Navi validation;
mode 0 matches the saved pre-edit converter on 100 budget fixtures and real
Deku room 0 MSH/TEX/manifest. Mode-1 Link builders pass isolated offline smoke.
Clean default follow-up: WSL Bash syntax and 15 variant/default/export cases
pass, including explicit 0/1/2 overrides and unchanged non-Clean defaults.
Target: full WSL `OOT_CORE=1` Clean mode-2 build and final repack pass; usual
`game-clean.cue` is the accepted reduced-room image. SGL margin remains 1,792 B;
all 1,452 ISO files match staging and both SH-2 math audits pass. Three obsolete image-scene MSH/TEX pairs
were removed from density staging, with originals backed up. Worst active room
TEX is 87,296 B; worst bank including CLUTs/alignment is 124,640 B, leaving
204,312 B after Link/runtime sprites/64 KiB actors in the unchanged 445,432 B
area. NAVIPOOL is 141,536 B; ISO is 83,494,912 B. Full measurements, per-room
CSV and limits: [texture experiment](TEXTURE_HALVING_2026-10-08.md).
Human acceptance: user says it looks almost the same and reports improved
performance. Screenshot shows VRAM 49%, CPU~ 79%; no paired FPS/load-time
measurement or separate Kokiri/Field route-completion claim. Clean's default
now preserves the accepted mode; the current target image already uses mode 2.
This asset task does not close or defer the required Player migration below.

Current inventory work (human, 2026-10-08): wire every Link inventory action
through the decomp paths, retaining the digital-controller crosshair. Source
first-person tool sprites are approved when meshes cannot fit. Also repair
Biggoron/Mirror equipment and shield presentation; Hylian fallback is blue,
Mirror fallback red with a silver center. The complete starting coverage and
source ownership map is [INVENTORY_SOURCE_AUDIT_2026-10-08.md](INVENTORY_SOURCE_AUDIT_2026-10-08.md).

First repair wave is implemented: the missing source R_UPDATE_RATE initialization
explains stationary projectile motion; source movement, arrow/hook/boomerang
Draw-side gameplay work, bomb blast radius, source-to-C swept contact views,
magic-arrow fallback and source-owned equipment admission are repaired in code.
First-person sprites and textured/flat shield fallback are integrated.
All 346 host cases and the actual source actor probe pass. Full assets and the
usual Clean image are rebuilt: main .bss ends at 0x06083900 (1,792 B spare),
resident core is 510,184 B, and all 1,458 disc files match staging. Both SH-2
math audits pass. All 388 room records pass (359 mesh, 28 image, one streamed).
Evidence and remaining checks: [inventory handoff](INVENTORY_HANDOFF_2026-10-08.md).
Human runtime acceptance remains open. This repairs the temporary tool bridge,
not real Player ownership.
Hammer, lens, spells, beans, bottles, trades, masks and source Player item actions
remain required; do not declare all inventory functional from this wave.

Water ledge and debug-menu follow-up (2026-10-08): surface swimmers now perform
source-derived wall/ledge admission and the original swim step-up clip, with
child/adult water heights and landing clearance. Level Select remains compiled
and appears below save options after Start. Ten regions contain all 101 maps;
A opens maps/options and toggles Link age or All Items. Only Begin Play Test
starts an unsaved session; Go Back returns to maps. The legacy title cheat stays.
Source and 119 host checks pass (104 focused, 15 map/session regressions).
Previous matching water/menu Clean target was rebuilt;
main .bss ends at 0x06083740 (2,240 B spare), core remains 508,560 B. Both math
audits pass; all 1,457 disc files match staging. Current verification: [water/menu handoff](WATER_MENU_HANDOFF_2026-10-08.md).
Human acceptance of the reported ledge and rendered menu remains open.
Carry this shore-exit behavior into the mandatory real Player migration.

All-map fix (human, 2026-10-08): all 101 retail maps now register for Level
Select, including every temple and retail cutscene stage. The missing maps were
registration/budget exclusions. The existing 75 IDs remain fixed; 26 append.
All 388 room rows bake with no blockers. Optional subdivisions and texture
density obey existing limits; complete source collision uses exact per-scene
allocation. Scene entries and portals share SCENETAB.BIN. Old core resources
unload before new native assets; inactive music tables are released when idle.
Heap zones and actor capacities stay unchanged. Previous all-map Clean target built:
main .bss ends at 0x06083110 (3,824 B spare), resident core remains 508,560 B.
All 184 host checks pass without skips; 101 OOCs validate, both ELF math audits
pass, and all 1,457 ISO files match staging (79 filesystem slots remain).
Verification and limits: [all-map handoff](ALL_MAPS_HANDOFF_2026-10-08.md).
Nine additional `DEBUG_ASSETS` entries have no retail source payload. This task
imports no actors and does not complete their gameplay or route connectivity.
Runtime/human acceptance and heap-fragmentation telemetry remain open; mandatory
real Player/collision cutover and enemy admission gates remain required.

Human playtest fixes (Claude, 2026-10-08): proxy Player now keeps source
room -1, so a room change no longer deletes it and disables every C tool.
Iron Boots in water leave the swim clip (stale SWIM self-heals). Arrow sheet
thickened at bake plus a three-cel flight trail. Code + focused host tests;
Clean target built (game-clean.cue, 18:18); human runtime check open.
Tool SFX added: 16 resident source sounds, held loops, flagged actor audio;
Deku Tree area tails trimmed for room (human choice). Door/zone water-fall
lock still lacks a repro.
Magic meter (source Magic_DrawMeter on the VDP2 heart cells) implemented and
host-tested. Arrow_Fire/Ice/Light imported (source gameplay/SFX, host ITMMAG
sprites, hit tint), source magic meter states, charge SFX; forest/boss
tails trimmed for sound RAM. Room bakes now parallel. Human check open.
Text (human 2026-10-08): only coloured emphasis is bold (bold glyph copies in
free B1 text cells); Debug Play Test shows the source room on row 29. Main
.bss ends 0x06083FB0 (80 B spare); magic state code is -Os to fit.
Player cutover plan approved 2026-10-08 (PLAYER_MIGRATION.md "Cutover plan"):
phase 0 remeasure done - Player is ~20-25 KB short in the five-region design;
phase 1 (Astra) moves scene NPC/prop actors into OAP packs (~87 KB of NPCs),
phase 2 (Claude) unifies collision. Overhead camera turn is C-Up/B+C-Up, Z
targets; slingshot fires source ARROW_SEED. Main .bss margin 208 B.
Phase 2 (Claude, 2026-10-09): core z_bgcheck is now the only collision world
in Clean (`CORE_COLLISION=1`; `=0` = C library rollback). C bg_* and C Link
wrappers run over the core (bg_core_shim.c / bg_core_link.c); core scene loads
inside scene_flow_load; C props are core DynaPoly proxies; C scene buffer,
index and core->C dyna mirror gone. Core API v27. Host probe/focused tests pass
(6 pre-existing fixture errors); Clean rebuilt, audits clean, main .bss
0x060818A0 (10,080 B spare). Speed vs C and runtime acceptance open (human
Clean play). The subsequent real-Player cutover supersedes that phase ordering.
Real Player first cut (Claude, 2026-10-09, human "replace all of the player
C with decomp"): `PLAYER_SOURCE=1` in Clean. Scene NPC/prop actors moved to
63 per-scene packs (phase 1, Claude by human choice), real z_player linked
in the core with 46 host hooks (API v28), whole frame bank resident
(PLAYANIM.PFB 626 KB, no LINKANIM), host feeds the pad and draws Link from
the jointTable. C Link kept only as `PLAYER_SOURCE=0` rollback. Human Kronos
runs (2026-10-09): animations good, talk closes, Navi is now the decomp
En_Elf (C-up prompt live). Speed work toward the 20 FPS goal (Debug readings,
Kokiri): 6 FPS -> 15 FPS via z_bgcheck integer fast paths, catch-up cap,
camera constraint once per frame, Link skin inline, shadow/HUD caches, and the
second SH-2 running the decomp core update, Link's skin and the scene prepare
(PLAYER_MIGRATION.md speed sections, DEBUG_OVERLAY.md). Human now reports
10→20 FPS, with moving-frame and item regressions under the current review.
Broader runtime acceptance and migration parity remain open.

Enemy groundwork (Astra, 2026-10-08): [ENEMY_ROLLOUT_PLAN.md](ENEMY_ROLLOUT_PLAN.md)
and [source design review](ENEMY_DESIGN_REVIEW.md). All five review choices are
settled. W0a implements shared infrastructure without importing any actor:
generated source roster, fixed-address packs/teardown, SPR2 NPC libraries and
scene preload/shared cels, temporary two-way combat, effect snapshots and audio
generation. Host/target verification and open runtime/content gates are recorded
in the [W0a handoff](ENEMY_W0A_HANDOFF_2026-10-08.md) and enemy plan.
Historical final W0a: 91 host checks passed without skips; Clean image rebuilt,
main .bss 0x06083ee0 (288 B spare), core 508,560 B. Disc bytes and math audits
passed. The all-map build superseded that main-RAM margin; recompute Player fit
from the matching current ELF/BIN, including the new scene allocation lifetimes.
Boss exemption follows the 20 actual ACTORCAT_BOSS profiles; En_Bdfire is not
exempt. Hazards retain geometry; the original 20 missing enemy scenes remain
in scope. Enemy work runs alongside mandatory Player migration; grab/capture/
gear actors wait for real Player. The old W0b gate remains for its pilot scenes;
the human explicitly advanced Field and Water Temple before that sequence.

The following dated reviews/checkpoints retain historical evidence. Current
enemy status is above and in its plan; current Player ownership is the real
core Player, with remaining parity work in PLAYER_MIGRATION.md. Older priority,
slot-count, scene-discovery and plan-only claims do not supersede those states.

Astra shim review (2026-10-06; source inspection, tests not rerun):
The isolated shim/proxy implementation and integer bounding-center importer fix
are present. Reported 177-row host comparison is not live integration acceptance.
Before Player cutover, initialize the proxy DynaPolyActor.transformFlags using
the proper core flags/initializer: registration currently stores only the private
Proxy.transform byte. api_dyna_carry reads that byte and calls carry helpers
straight away, but the real DynaPolyActor_TransformCarriedActor path reads
actor.transformFlags, currently zero. Test carry through the normal core actor
path as well as the C shim. Choose one frame-boundary owner and test actual order.

Budget the full replacement storage, not only the retired C allocations:
sProxies[BG_ACTOR_MAX] contains full DynaPolyActor and CollisionHeader objects,
plus source vertices/polys/surfaces, the core transformed pool, shim conversion
scratch/surface scratch, camera views, code and stack. The 192-triangle cap alone
is not a memory-fit proof. Scene teardown/reload must reset both shim ownership
and core proxy/water bookkeeping before core IDs can be reused; SetPlay currently
only changes the pointer. Cover a scene round trip, not just remove/re-register.
The remaining Fx corner fall-through and line miss remain explicit regressions.
Continue isolated caller ports/resolved linking; no Clean or runtime claim here.


Astra follow-up collision review (2026-10-06, source inspection only):
The probe now feeds identical coordinates to C and core and checks input identity
between Fx and float runs. The owner-local dynamic polygon index now subtracts
polyStartIndex; the real-matrix dyna probe covers two owners, removal and slot
reuse. These earlier source-review gaps are closed. Reported Fx/float residuals:
floor 0, wall 7, ceiling 0, line 3; no numerical/runtime equivalence claimed.
Normal-first plane arithmetic and direct dyna-normal division are importer fixes
that affect the next live core rebuild. No new Clean build or runtime acceptance.

Remaining focused checks: preserve the one Fx line miss as a regression case
and classify its gameplay significance; validate transformed slopes and moving
platform contact during proxy integration. The flat-normal test currently allows
normal.y >= 32700 and distance +/-2, rather than asserting exact flat normals.
compare_bg_port.py is a diagnostic report: exit zero checks identical inputs,
not absence of collision differences. Host reports are not target timing evidence.
Continue C shim, dynamic proxies and caller ports toward the real resolved link;
retain current Saturn behavior inventory and include adapter/storage peaks.

Cache handle/manifest/reservation fixes are reported implemented and host-tested;
the earlier Ready-loop gap review is historical, not the current implementation.
The 64 KB cutscene result covers cutscene-exclusive Link clips only. Common
Player call-graph reach (~400 clips) does not prove simultaneous need. Determine
state/cue/branch-specific animation requirements and account for every actual
participant before claiming a full cutscene set fits. Preserve whole-cutscene
preloading/pinning and zero per-shot loads. Common set/CD servicing/start gates
and actual runtime peaks remain open.


Historical Astra demand-cache review (2026-10-06; superseded by handle fixes):
Cache/rollback are isolated prototypes, not completed production demand loading.
Common-set selection, actual cutscene dependency manifests, CD/audio servicing
and real Player start gates remain open. Continue independent collision API/ports
and resolved-link work, but close these cache issues before playback integration:
- Ready requests members individually and pins only after all report ready.
  Completed members of a pending set remain evictable. Reserve/admit the entire
  deduplicated set and protect it during loading; use an owned request handle
  with one acquire/release lifecycle, cancellation and no repeat-pin leaks.
- NO_SPACE must distinguish temporary contention from impossible admission.
  A clip/set larger than the arena, or more than 64 cache entries, cannot become
  ready by waiting; the current loop can evict/reload members indefinitely.
  Preflight actual bytes/slack/entry limits, existing pins and fragmentation.
  Return explicit cannot-fit for intrinsically oversized sets; solve the whole
  cutscene budget before playback. Never stream per shot to escape this failure.
- Init lacks a manifest-length argument and does not validate clip offsets,
  monotonic ranges or archive bounds before Request sizes/starts a read. Add
  length-aware, overflow-safe archive-index validation before mutating cache state.
Required focused regressions: impossible whole set, pending-set members surviving
unrelated pressure, repeated polling/cancel/release and malformed manifest ranges.
Streaming 510 clips serially through 48 KB proves eviction/decoding, not that any
complete real cutscene fits; test real whole-cutscene manifests before acceptance.


Human cutscene-loading clarification (2026-10-06): preload and validate ALL
animations for the entire cutscene before playback, across every shot, participant,
reachable branch and uninterrupted chained segment. Pin the complete set until
playback/return transition finishes. No per-shot animation loads or mid-playback
loading stalls. Budget the full cutscene set; solve capacity before starting,
never by interrupting shots. Runtime implementation remains pending.


Current animation directive (human, 2026-10-06): demand-load only clips needed
for current play or an upcoming requested action/cutscene. Keep common responsive
moves ready; prefetch rare clips before action/cutscene start, pin all consumers,
and evict unreferenced clips within a bounded cache. A cold clip is a load request,
not a missing-asset error. Never skip gameplay or start cue clocks without data.
This supersedes all-clips-resident and scene-load-only animation restrictions.
Detailed contract: PLAYER_MIGRATION.md, "Demand-loaded Player animation".
Request/cache/readiness implementation and memory/latency verification remain
pending; existing whole-bank measurements are historical comparison baselines.
Continue isolated Player/collision integration with this revised frame-bank plan.


Astra integration review (2026-10-06): GO for isolated collision API/ports and
resolved linking. Scene-pack rollback by reloading the old pack from CD during
the same loading screen is approved. Stop Player/animation consumers, unregister
old pack slots before overwriting, retain old scene/pack identity and state, and
publish new state only after complete load/validation. On new-pack failure,
restore/revalidate the old pack and matching state before resuming. If restoration
also fails, stay out of gameplay and report a recoverable loading error or safe
error screen; never resume with missing/stale animation pointers. The newer
demand-loading directive governs animation I/O and action-start gating.
Use the strict bank as reference; cutscene-only relaxation remains unproven.

Source-review blockers before adapter acceptance: PlayerFrameBank_Register
currently validates shallow offsets/counts, not full decoder input. Validate
stride/block size, kept-frame counts, widths/shifts, all block/stream extents and
padding with overflow-safe range checks; reject duplicate IDs and unintended
resident/scene collisions before publishing slots. Add malformed-block checks
that prove slots unchanged and decoding cannot divide by zero/read out of bounds.
The claim "validates a whole bank" is not yet supported by this implementation.
Same-sized chunks alone do not prove equal fragmentation: match lifetime/order,
headers/alignment, load scratch and largest-free-block needs. Partition report is
not a resolved-link fit; account for frame decoder, loader and all new adapters
in their actual regions. Low-RAM versus cart speed is unmeasured here, not an
established slower/faster result. No production cutover or new runtime acceptance.


Claude (2026-10-06, Codex out): proxies use real transformFlags + core carry path;
one frame-step owner; scene reset restores water + clears proxies; replacement
memory ~19.4 KB measured. Host tests pass; 2 tracked Fx cases open. Next: port
callers onto bg_core_shim, then real link. Nothing live yet.

Third core Fx fix + shim (Claude, 2026-10-06): DynaPoly bounding-sphere centre
saturated (larger/higher dyna meshes vanished); now integer sum. C bg_* shim +
DynaPoly proxies over the core: 177-row scenario matches C on float core; Fx core
1 tracked corner case. Isolated; callers not ported yet.

Second core Fx fix (Claude, 2026-10-06): DynaPoly normals lost ~10% on large
polys (reciprocal normalise); now divide. Collision parity redone with identical
inputs: Fx vs float 0/7/0/3 (floor/wall/ceil/line) differences. Runtime check of
dyna platforms pending.

Severe core bug fixed (Claude, 2026-10-06): Fx z_bgcheck line tests and
point-plane distances saturated (raw s16 normal x position before scaling).
Line tests barely hit. Importer fix in MACRO_REWRITES; host mismatch totals improve; direct Fx/float parity remains unverified. Live core behaviour changes at the next Clean build: needs runtime check.

Historical Claude integration step 1 (2026-10-06): strict bank (uncertain clips strict) worst
scene 554,668 B; placed into real old allocations, worst pack fits. Two-pack
rollback does not fit (reload-from-disc rollback proposed). Frame-bank adapter,
region loader (both host-tested, isolated) and 5-region partition (2,514 B
main free in that old partition) done; 110 collision call sites listed. W0a
changes the baseline: that margin is not current. Remeasure combined Player
placement against the current inventory ELF/BIN before partition or cutover acceptance.
See PLAYER_MIGRATION.md for historical evidence and current integration work.

Claude follow-up (2026-10-06): blame-based per-channel precision + action-specific
anchors cut worst scene to 552,756 B (0.5 everywhere) / 531,876 B (0.5 gameplay,
2.0 visual). Same-stage old total incl. C collision 553,142 B. Fit depends on
retiring C collision callers; see PLAYER_MIGRATION.md. Next: sections + loader.

Current migration handoff (human, 2026-10-06): Grok emitted real 8-pose delta
blocks, per-channel shifts and spawn-proven scene packs at the 0.5 world-unit
anchor limit. Python mismatches: none. C decoder matched 509 clips / 16,837
frames. Resident file 653,616 B (439 clips). Worst scene 688,068 B. Transition
peak 710,632 B. Existing LINKANIM block 423,472 B. Still no fit (about 265 KB
short on the worst scene). Loader and Player cutover stay blocked. SH-2
decoder text 928 B; not timed on hardware. See ASTRA_HANDOFF_2026-10-05.md.

Curtain correction (human, 2026-10-06): restore the world-space behavior from
before vertical locking. Curtain anchors to Link, follows camera yaw, and stays
upright; camera pitch/height move it naturally on screen. Two-panel geometry
and map/time tint retained. Four focused host checks pass. Requested WSL Clean
quick build passes: usual ISO/CUE rebuilt, .bss 0x06083f10, 240 B below SGL.
Log: build/curtain-world-restore.log. Human visual acceptance remains open.
Removal and vertically locked restoration superseded.

Camera HUD (2026-10-06): human approved mockup and requested implementation plus
commit. Native CAMERA / Z / B+Z strip uses 88x24 pixels at (216,64), beneath
existing item buttons. Shows only with normal gameplay HUD in overhead camera;
clears in regular view, first-person/crawl camera, interiors and hidden HUD.
Existing button cell allocation holds 33 contiguous camera tiles and its palette;
no extra HUD name-map reservation, heap or VDP1 slots. Palette bank 11 follows
the composed item banks; main RAM does not retain an extra palette/map table.
Camera turns now play requested NA_SE_SY_CAMERA_ZOOM_DOWN_2 (0x4829), baked
from CHAN_5C1E / LAYER_5C22 with the existing offline linear falling-glide
approximation. Both age banks include it at half rate; worst sound bank leaves
952 bytes. Host verification: executing HUD visibility/item regression 1/1;
audio bank and SCSP routing checks 23/23. Full Clean OOT_CORE build passes
(`build/camera-hud-clean.log`), .bss ends 0x06083f30 (208 bytes below work area).
Updated `build/game-clean.cue` / ISO ready; runtime appearance and sound
acceptance remain open. Preview: `build/mockups/camera-controls-v1.png`.

## Mandatory Link migration: next step

Human directive (2026-10-06): replace handwritten C Link gameplay with the real
core/decomp Player, including z_player_call.c and ovl_player_actor. This is a
required implementation wave, not an optional experiment or a decision awaiting
benchmark results. All existing Saturn adaptations, added features and Link fixes
must survive on top of the decomp implementation. It supersedes the older
actor-first continuation below. Full-game scope and existing unfinished work stay.

Current state: real Player owns movement/actions; core z_bgcheck is the shared
collision world in Clean. Saturn input, camera, renderer, save/UI and remaining
C actors use adapters. Legacy Player/proxy paths remain behind rollback until
acceptance. Current review repairs item/aim and slave handoff regressions;
migration parity, demand loading and runtime acceptance remain open. The
[behavior inventory and dependency map](PLAYER_MIGRATION.md) records preservation
units, owners and gaps; individual inline-fix/test-case audit remains required
before accepting each subsystem cutover. Historical staging evidence follows:
WSL host syntax passes all three after scoped enum/Fx and scaled rumble fixes.
Two focused tests pass, including 102,000 rumble ticks matching source pulse
timing with actual Fx32. Literal-range audit closed (Claude, 2026-10-06; five
tests pass). Pose-pass split preserves anchors; that checkpoint measured
standalone GC Player at 143,437 B.
The 2026-10-06 combined-retention checkpoint measured **659,244 B**, including
core dependencies, libgcc, temporary duplicate-owner removal and 521 animation
headers, against a 501,840 B core baseline. Its proposed five-region capacity
was 679,936 B; historical margins and later adapter estimates remain recorded
in PLAYER_MIGRATION.md. W0a changes the resident core, so those retention totals
and the 20,692 B / 11,808 B / 2,514 B margins are not current fit evidence.
Use current resolved Clean/core artifacts for further placement work, including
dependencies/adapters, collision proxies, alignment and load peaks. Do not count
speculative C-Link retirement or reduce heap capacity to admit new work.
Older whole-frame-bank deficits are historical comparison data. The current
human contract is a bounded demand-loaded common/action cache with complete
cutscene preloading/pinning. Measure its metadata, decoder, loading/recovery
scratch and full live working sets alongside W0a scene resources. Current
whole-bank runtime does not close demand-cache working-set admission.
Native Draw remains reachable from source actions; skeletons cannot be blank
placeholders. 9 duplicate owners and 713 unresolved symbols mapped in
PLAYER_MIGRATION.md as historical isolated-probe evidence. Real Player is now
target-linked and running; those old unresolved counts are not current blockers.

Rules and sequence:
1. Before replacement, inventory existing Link behavior from actual code, tests
   and human directives. Record current source, intended core/adapter owner and
   verification for every fix/addition; distinguish accepted, implemented-only
   and still-missing behavior. Include digital/analog/custom controls and labels,
   B-held walking, Y jump, A interaction, X attack, R shield, C-item access,
   targeting, first-person/house views and the added overhead camera/turns;
   child/adult animation and gear, movement/ledge/roll/climb/crawl/lift/swim,
   combat/tools/damage, dialogue/rewards, Ocarina/era changes, cutscene control,
   inventory/save/death/respawn and scene transitions. This is an audit list,
   not a claim all of those systems are already complete.
2. Import and adapt real Player source. Core owns player action state, movement,
   collision response and gameplay interactions. Keep Saturn input, rendering,
   audio, UI and save adapters where needed. Preserve the current Link renderer,
   meshes, gear fixes and presentation; importing Player does not require an N64
   graphics backend or change the NPC sprite/boss rules. Put Saturn additions
   into explicit source patches/adapters with a clear behavior owner.
3. Migrate in bounded stages with one gameplay owner per migrated subsystem.
   Preserve simulation/input-edge timing and the existing 20 Hz core contract;
   adapt render/input cadence without running two Player action machines or
   applying movement, hits, item use or rewards twice. Keep working legacy paths
   until their replacements pass acceptance, then archive the replaced code.
   Remaining C actor/camera collision callers must be accounted for before
   removing their collision storage. End state: one authoritative Player and
   shared core collision world; no permanent proxy or second gameplay solver.
4. Preserve dynamic collision semantics: contact/bg IDs, standing/riding and
   switch feedback, required transforms, enable/delete lifecycle, surfaces,
   water and camera metadata. Core z_bgcheck already owns the world; remaining
   C prop proxies must retire with their source actor replacements. Recheck
   actual transform/contact ownership and unchanged-transform costs before
   each retirement; do not treat the older gallery mirror's limitations as
   current evidence or erase previous transforms needed for rider motion.
5. Measure whole collision/update cost, memory and dynamic rebuilds on the target
   as migration proceeds, alongside representative query costs. Neither core nor
   C is presumed faster. Results guide bounded optimization of the chosen core
   implementation, never permission to abandon Player migration. Native SH-2
   multiply is allowed; stored runtime values stay 32-bit. No software-wide or
   soft-float helpers, reduced actor/heap budgets, or disabled boundary guards.
6. Verify preserved behavior with focused executing checks, a matching host/core
   target build and human runtime checks in both eras. Include static walls,
   moving/rotating platforms and switches when their source actors are integrated.
   Track gaps explicitly; original-source availability, proxy success or a build
   alone does not finish migration. Completion requires real Player ownership,
   preserved Saturn functionality, retired duplicate paths and runtime acceptance.

Candidate-10 Clean margin is 5,968 B; Debug margin is 496 B. The gameplay
repair temporary Debug link has 80 B spare; host/audit/budget/ISO checks pass,
while human runtime acceptance remains pending.
Earlier 28,176 B, inventory 1,792 B and water/menu 2,240 B margins are historical.
Older failures, margins and build holds below
describe their named checkpoints, not current headroom or a new hold.

## Historical checkpoints and retained verification gaps

The migration rules and final next-action list set current priority. Checkpoints
below retain evidence and unfinished requirements; their older ordering, blanket
hardware-multiply ban and build-state claims are superseded by current directives.

Map curtain / environment tint (2026-10-06, source, host and target verified):
- Shared fixed-height dither curtain now submits in every 3D scene, including
  the panorama geometry path. Near room walls naturally occlude it; flat bitmap
  interiors keep their existing background renderer, with no foreground veil.
- Curtain and dark horizon band use the same map/time colour. Base source scene
  fog colours tint the ground gradient and normal outdoor sky; Kokiri's unset
  sky uses a darkened fog tint. Kokiri daytime fog is RGB 200/200/150 (warm yellow
  grey), not evidence that its original skybox is goldenrod.
- Four six-hour colour anchors approximate time changes; static-light rooms keep
  their first light colour. Alternate weather/story fog palettes remain pending.
  All 75 current map palettes parse. Two polygons/six vertices reserved in boss
  and story geometry budgets; no curtain textures or sprite slots added.
- 13 sky and 4 curtain host tests pass, including Kokiri source colours, map
  differences, darker night and fixed camera alignment. Human authorized Clean quick build with OOT_CORE=1; colour tables regenerated
  (600 additional palette bytes for 75 maps). Build passes with .bss ending
  0x06083ef0, 272 bytes below SGL work area. Log: build/curtain-quick-build.log.
  No emulator run; human scene/night appearance checks remain pending.

Camera defaults / fixed sky curtain (2026-10-06, source only): Hyrule Field
(SCENE_SPOT00) enters overhead; other scenes enter regular follow. Scene-entry
placement resets pending orbit turns and heading. L+R+B now toggles only regular
and the accepted first overhead view; the three farther survey views are removed.
Z/B+Z eased quarter-turns remain in overhead. First-person/interior framing stays
separate. 94 executing camera/control host checks pass.
The gradient's VDP2 rows were already fixed. The shared dither curtain follows
camera position and cancels yaw/pitch, keeping its vertical screen position fixed
on slopes and in first-person. Distance sorting and two-panel mesh remain; terrain
fog still uses Link-relative depth. Four haze host checks pass. No build/bake or
runtime test, per human hold. Human visual checks remain after a later build.


Dialogue readability and Kokiri text handoff (2026-10-06, source only):
- A or B fills the current core text page; a later press advances it. Source
  control codes, choices, page waits and Ocarina timing stay in z_message.
  Revealing text receives two draw/reveal ticks per core step; other message
  modes run once. The separate cutscene typewriter increases from 2 to 4 chars.
- Regular Kokiri conversations (children, Mido, Saria) open/continue/close through
  the core ROM-message engine. C retains placement, text-id selection and existing
  quest/gate/close callbacks; this is a text-engine migration, not a full actor
  import. Source choices return to the existing branch callbacks. Core mode no
  longer uses the C page renderer for these conversations. Non-core fallback,
  shop/item/system messages and scripted greeting cutscenes remain separate.
- Shared dialogue font ASCII is bolded once at boot; pause restores those cells.
  Core blue/light-blue text maps to yellow, black to white; cutscene blue emphasis
  also maps to yellow. Core rows overwrite padded colour runs without blanking
  the visible page first. Old per-name kana glyph generation is removed.
- Host verification: 15 focused cases pass (5 new page/choice/reveal/font checks,
  5 Ocarina, 3 core dialogue, 2 core views); 1 source-table Ocarina comparison
  skipped in WSL. gameplay.c syntax passes both core/non-core configurations.
- Human explicitly says DO NOT BUILD. No target build, bake, disc change or
  emulator run in this task. Core ABI increments to 21; matching rebuilt host
  and blob are required later. Earlier RAM overflow remains a build blocker;
  these source changes do not prove target fit or runtime acceptance.


Song of Time repeat fix (2026-10-06): the requested shortcut now toggles both
child/adult directions. Load failure restores the original age; equipment changes
only after a successful load. Free-play start resets stale audio state; completion
stops listening/playback; B cancels free play during recognition or result playback
and releases the player flags. The retained Ocarina instruction row is written
only on open and cleared on close instead of being rewritten each display frame.
Host: five Ocarina tests pass (one local-source comparison skipped in WSL),
including four successive toggles, both recovery directions, repeated recognition,
completion consumption and playback cancellation. Clean link failed the SGL
boundary check: .bss ends 0x06085600, 5,632 B over 0x06084000. Log:
`build/ocarina-repeat-clean.log`. Build guard removed game-clean ISO/CUE/ELF/raw;
no runnable updated disc is available. Shared-tree size recovery is required
before human retest. Heap/actor capacities were not reduced; no runtime check.


Human scope/wording directive (2026-10-05): full OoT recomp for Saturn. Every
scene, era, day/night/story layer, actor and game system remains in scope.
Use "full recomp", "game", "implementation wave" and "opening route" in
current plans and handoffs. The opening route orders work; it does not limit
the finished game. Project files and symbols now use recomp naming. Original
decomp symbols, archived Git refs and historical screenshot paths retain their names.

Naming change (2026-10-05): renamed this plan, the recomp runtime sources and
header, asset tool/test and control-probe include. Updated source symbols,
build inputs, callers, tests, tooling and documentation together. Static rename
and reference checks only; no compilation, bake or runtime check. Existing
binaries retain their previous symbols until an authorized rebuild; updated
probe tooling requires a matching rebuilt binary before use.

Current Wave 0 status (2026-10-06): OOT_CORE_PIPELINE_PLAN.md records Fx32
implementation, host checks and Clean builds, superseding the earlier build hold.
Runtime acceptance and later actor waves remain open. Other wide paths remain debt.

Human ruling (2026-10-06, narrowed): native SH-2 dmuls.l/dmulu.l and the
casts that generate them are allowed. Stored values remain 32-bit; software
64-bit helpers and soft-float are banned. Approximation is authorized. Claude's
gallery import and both ELF audits are recorded in the pipeline handoff;
gallery runtime acceptance remains pending. Link migration is the next priority.

Latest camera follow-up (2026-10-06): reversed both first-raised-view Z/B+Z
quarter-turn directions. Each turn uses a 16-step cubic Hermite smoothstep
(~0.53 s at 30 Hz), zero endpoint slopes, and only 32-bit integer math.
Bounded pending turns preserve cardinal stops; opposite pending taps cancel,
and view changes clear pending turns. The initial cursor tick is superseded by
resident NA_SE_SY_CAMERA_ZOOM_DOWN_2, played once per Z edge (see HUD update above).
Verification: 93 executing camera/control host checks pass in WSL, including
reversed endpoints, wrap, easing, radius, queued reversal and reset. Claude's full Clean build at 10:33 includes both changed camera sources
(`build/fix-full-clean.log`); 304 B spare. Disc program, core and all five Adult
Link payloads match staging. Adult mesh restored from 358 to original 672 polygons.
That image is historical: the later Ocarina build failed and removed it.
Earlier Gossip Stone messages were nonfatal
warnings, not the cause of the interrupted camera build.
Human turn-feel/audio acceptance remains pending.

Latest implemented follow-up: stop repeated unavailable-exit text, add 90-degree Z/B+Z
turns to the first raised camera, and anchor Field fog/dither to Link.
Implemented: failed destinations warn once within a 600-unit XZ neighbourhood;
walking away or changing scenes rearms the notice. Repeated scripted requests
are consumed, movement remains possible, and valid transitions still work.
First raised view: Z/B+Z turn opposite directions, now reversed and eased
by the camera follow-up above.
Targeting/recenter and B cancellation are consumed only for that outdoor view.
The later camera-default change replaces the five-view cycle with two views.
Field fog and distance mesh use Link-relative forward depth; visibility keeps
camera depth. The later fixed-curtain change replaces the Link-position/yaw
anchor with camera position/yaw/pitch cancellation. Source fade caching also tracks Link movement. This does not fix
large ground triangles disappearing or establish a clipping root cause.

Verification: 71 controls, 20 camera, 16 route and 4 haze/fade host checks pass.
Three controls checks also pass with DOSEI_CLEAN_TEST enabled (114 checks total).
The route harness was updated for existing source time/layer APIs. Clean rebuild
passes (`build/field-orbit-fix.log`): .bss0x06083DA0, 608 B below SGL. Disc
Field/COL/OOC/program bytes match staging and all CUE tracks exist. Frame setup
uses size optimization; heap/actor capacities stay unchanged. Human runtime acceptance
of these fixes remains pending. The human likes the first raised view; higher
views still expose ground defects. Dark sky is accepted and retained. Combined
Field/Link/owl/haze is 2475/2600 polygons, 2424/2500 vertices. Existing wide
crawl-camera math remains migration debt.

Earlier human feedback: dark sky gradient is accepted; retain it. Add a
camera-following world-space dither curtain before full Field fog. Implemented
as one upright VDP1 mesh quad at3200 units, with ordinary depth sorting and
camera pitch projection; no texture/sprite slot. Clean build passes
(`build/field-haze-final.log`), .bss0x06083FF0, 16 B below SGL. Two executing
haze host tests and twelve sky tests pass. Combined Field/Link/owl/haze uses
2474/2600 polygons and 2422/2500 vertices. ISO bytes/track references verified;
new target helper uses integer shifts and existing SGL calls. Human owns runtime
appearance/occlusion checks. Sky callback and cold background-priority setup
use size optimization; no heap/actor capacity was reduced.

Human now requests the accepted quad ground in usual Clean, broader Field ground
coverage, persistent castle/ranch walls and a dark horizon veil (2026-10-05).
This supersedes the isolated/build-only scope in the paused handoff. Human owns
runtime checks; do not run GUI fixtures. Selection now uses `field-square-184`.
Implementation adds offline outer-ground subdivisions without altering source
planes or outer collision, retains the complete ranch enclosure/castle walls,
uses SORT_MIN for landmarks and adds four dark Field background bands.
Whole-map capacity checks pass: 1249 Field polygons, 1732 vertices and
331776/445432 bytes, including Link/owl/effect reserves. Outer cells are 1280
units; uniform fine 184 cells across the map exceed current limits. Usual Clean
build passes (`build/field-haze-final.log`), .bss 0x06083FF0: 16 B below
SGL. Heap and actor capacities are preserved; cached sky helpers use size
optimization. 47 focused Field/sky host checks pass. Disc Field/COL/OOC/program
bytes match staging and all CUE tracks exist. Human runtime checks remain;
changes are uncommitted. Static RAM margin is tight.

Earlier isolated verification (2026-10-05): the split-block Field loader fixes the initial contiguous
SAR0.STM allocation failure in both isolated builds. 184 now runs in the visible
configured Kronos; its full boundary walk completed, and two 90-step walks took
5.781 s each. The resumed 256 run completed both boundary walks and measured
5.657/5.703 s for 90 steps. The earlier interruption was the human closing the
GUI, not an emulator crash. The human accepts the central patch's appearance
("VERY nice"). Good ground at (0,181,6178) is inside the patch; the bad north
ground at (6,67,7067), source1029, and castle approach (0,0,2940), sources602/612,
are outside it. Preserve that accepted patch. Wider visual-only ground panels
and Clean promotion are implemented and target-built, awaiting human checks.

New authorized environment work: [ENVIRONMENT_TIME_STATUS.md](ENVIRONMENT_TIME_STATUS.md).
Keep distant low-detail volcano/ranch/castle landmarks visible without distance
dither, bring terrain fog closer, blend lower sky toward each map's ground
colour, and implement source time-of-day behavior. Clock, Sun's Song, destination
time/layer rules and layered room/sky settings are imported. Natural dawn's
nine-state sequence and saved day counters are implemented; 10 clock, 7 natural
sequence, 3 dialogue/hatch and 38 save/migration host tests pass. Source sky
colours, per-map lower gradient, closer Field fog and retained
far landmarks are implemented. Canonical landmark bake fits 340512/445432 B,
with zero unrelated full-detail changes. Combined v2 passed visible-GUI +200
daytime/+400 nighttime advancement per 30 steps, separate sky-time hold, pause
freeze and one natural-sequence day-counter increment. Its 90-step walks took
5.766/5.781 s. Hylian front and Master Sword HUD look correct; pause dims owned
age-ineligible gear. The wood was Hylian's own back face, not a second shield.
Latest v3 builds with 5,216 B below SGL; initial equipment cursor and targeted
landmark trace changes are not runtime-tested. Held/Mirror gear and v13 reload/
hatching need target checks. Far landmarks remain unresolved: SGL SORT_CEN's
32-bit depth sum overflows above mean z8192; central castle needs separate
trace. New SORT_MIN avoids that sum; runtime visibility/occlusion still needs
human checks. Original BGM/nature handoff, audio/weather
ownership, source song-effect timing and full cutscene environment lifecycle
remain open. Do not claim exact whole-environment parity.

Retopology geometry/budget history and images:
[FIELD_SQUARE_RETOPO_STATUS.md](FIELD_SQUARE_RETOPO_STATUS.md),
[FIELD_SQUARE_RETOPO_PLAN.md](FIELD_SQUARE_RETOPO_PLAN.md).
Existing textures and common STM/COL/OOC geometry stay required. Human's good
visual feedback is local acceptance, not proof of all-route holes/seams or
performance acceptance. Outer expansion now uses coarser visual-only panels on
original planes, preserving collision and the fine central patch.

Collision audit (2026-10-05): baseline COL agrees with all 1,579 extracted
polygons, source-derived Q14 normals and info words. Decoded staged OOC agrees
on geometry, flags and surfaces; 786 faces have a one-unit Q14 normal difference
after conversion. Preserve that baseline distinction when checking new outputs.
Grok's corrections are confirmed: Field uses the `0xF000` spot allocation,
recorded feet `(60,3367)` lie only on poly 436, and curb 598–613 extends to
Z 6800. Plan now requires real node capacity checks before writes and boundary
cuts on each curb's own plane. No implementation or build changed in this audit.

Current TR candidate is frozen at
`build/astra-control/checkpoint-2026-10-05/game.cue`, with all audio tracks,
sources and evidence. Same ten P3 children from four source faces only. It uses
SGL's sort/DMA queue, guard projection and at most 16 visible leaves per child
(160 total). Near/guard boundary cells may refine two extra levels; ordinary
cells keep 1/4/16. This exceeds the earlier two-level proposal in depth, not
the command cap. Immutable parent-index tiles add 76800 B, no sprite slots;
total budget 350112/445432 B. WSL target passes with 1632 B below SGL.
Eleven matched baseline/candidate poses cover both cameras, normal walking,
jumping and turning in the human-visible configured Kronos. Peak captured
commands: 628. Mapping error is substantially lower; small raster gaps remain
possible. A 90-step walk takes 7.265–7.312 s versus 4.735 s baseline, about 54%
longer. Visual feedback does not approve this cost or establish all-route seams.
No Clean/Debug image promotion and no production renderer change.

Camera correction is implemented in main source and the isolated build:
ordinary follow now collides in both modes, preserves age/profile height plus
pitch rise above sampled ground, and shortens against walls/ceilings. A raised
eye turns down toward Link. Previously only traversal transitions used the
collision ray; shortening alone also left the eye almost touching a slope.
Host tests pass 18 camera and 25 follow cases. Main Clean ELF links with 6160 B
spare; its ISO is intentionally preserved. Recorded Field turn no longer places
the camera under the slope. Existing wide math in collision/follow is migration
debt; the new paths introduce no wide/float helper references.

The isolated control harness boots Field through the existing Level Select path,
feeds bounded normal pad/physics steps through a 4164-byte low-RAM mailbox,
and captures SGL's real matrix and command list. Initial repeated walk/jump
and both-camera matrix checks passed; final matched fixture evidence is under
`build/astra-control/verification/tr-v10/`. Whole-world determinism is not claimed.
The source STM remains Opus's four-face P3 patch, with the renderer operating on
its ten children; standalone P3 had severe swim before the current experiment.
The old universal near-rejection explanation is not supported by actual SGL
traces. Backface checks, projected XY limits and camera clearance also matter.

Details/history: [TOMB_RAIDER_POLY_NOTES.md](TOMB_RAIDER_POLY_NOTES.md).
Burning Rangers static study (2026-10-05, research only, no code change):
[BURNING_RANGERS_POLY_NOTES.md](BURNING_RANGERS_POLY_NOTES.md). The supplied static study reports mostly 20-unit tile faces, whole-face near
rejection, and no clip/runtime split. Visual behavior and an all-face depth-ratio
bound were not established by that study.
Baseline preserved at `build/baseline-2026-10-05/`, source checkpoint 807d1e0;
source/image provenance remains distinct from preserved hashes. The preexisting
`src/player_input.c` analog chord edit is preserved and included in the local
source checkpoint requested by the human. Runnable build artifacts remain in
ignored build directories; this checkpoint does not publish or push anything.
Other unfinished game requirements below remain open.

Latest follow-up (2026-10-04): shadows are now twelve-sided circular disks,
not diamonds. Adult Link uses ADULTACT.PCM with original adult attack, jump,
climb, hurt, fall, landing and death recordings (13 replacements). Scene-age
changes and return from opening audio select the correct bank; a failed load
stays silent and is retryable. Non-voice bytes, resident offsets, playback rates
and sound-RAM/area budgets are unchanged. Adult tails are bounded to the shared
event slots with a short fade; exact original sequencing remains approximate.
The adult PCM was regenerated/staged through WSL. That ELF boundary passed at
0x06083FF0 (16 B spare); the handoff recorded the Clean image refresh blocked
by Kronos's open ISO. P0 preserved the existing image and its hash; that alone
does not certify which of these source changes the preserved disc contains.
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


Character ground shadows (2026-10-04): shared sprite draw adds one black VDP1
mesh-dither circular disk for visible NPCs, animals and sprite cutscene characters.
Link and native fairies use the same helper. Static geometry persists through
SGL submission; matrices place each instance on the indexed collision floor.
Offscreen/missing-floor/over-512-unit-high shadows are skipped; radius is capped
at 64 and shrinks with height. No heap, texture tiles, skeletons or new wide math.
Budget addition is twelve transformed vertices and five polygon/commands per visible
character, plus one indexed floor query; scenery and actors still share existing
SGL rejection accounting and limits. Flat circular disks approximate slopes;
legacy mesh enemies/boss shadows are not converted by this NPC/character pass.
The prior diamond-shadow Clean image passed before this correction. Current
round-shadow/adult-audio ELF links with .bss end 0x06083FF0 (16 B spare).
Cold collision loading/index construction and fog setup use size optimization;
heap and actor limits unchanged. That handoff recorded ISO refresh blocked by
Kronos holding game-clean.iso; the current diagnostic preserves that image/hash
without certifying its source provenance.
Do not overwrite a mounted image. Logs:
build/round-shadow-link.log and build/round-shadow-boundary.log.
Human visual/FPS acceptance remains pending; no emulator launched.


Song of Time shortcut (human request, 2026-10-04): completing the known song as
Child Link now changes him to Adult Link and reloads the current scene at its
saved entrance, refreshing actors, model, camera and music. The 2026-10-06
follow-up below now toggles adult back to child too. Failed loading restores
the prior age and source scene;
equipment changes only after successful loading. This requested shortcut is
separate from unfinished source Temple sword time travel. Level Select explicitly
shows **ADULT LINK: NO/YES**, default No; R toggles before confirmed entry.
Host Ocarina/Level Select batches pass 15 tests. WSL Clean rebuild passes;
.bss ends 0x06083FE0 (32 bytes below SGL). Human runtime checks pending.


Updated 2026-10-05. Active branch: main (oot-core decomp pipeline). Goal: the full OoT decomp on Saturn,
using imported original game logic with Saturn graphics/audio/file backends.
The full recomp preserves source gameplay with the required Saturn adaptations.

## Prior regression priority and evidence

Current warp task is wrapped at the saved local TR candidate and camera fix.
Wave 0 implementation and build evidence are in the current pipeline handoff;
runtime acceptance and later waves remain pending. Existing square-retopology
work and its unresolved geometry, collision and budget checks remain recorded
above. The preceding
human regression report (2026-10-04, after main integration):
the capped test save
still displays only four inventory items and Emerald; world map remains Kokiri,
Ocarina cannot equip/play, generic interiors lack view switching, doors show
normal-vector colours, hearts flicker, and populated Ranch/Kakariko Cucco scenes
slow severely. Graveyard tomb textures also lose dark detail. These are the
remaining regression priorities, superseding the earlier null-free report below.
Implemented work replaces slice-only pause art with all source slot/quest icons and
scene-area map markers, double-buffers heart tiles, connects source Ocarina
recognition, repairs scene camera/material extraction, and bounds source actor
collision work. Real child/adult source meshes share a transactional renderer;
Level Select chooses the era before source actor initialization. Full assets and
the final WSL Clean relink pass; human acceptance remains pending. Detailed changes, controls,
resource layout and limits: [player regression checkpoint](PLAYER_REGRESSIONS_2026-10-04.md).
Prior Clean evidence below belongs to the committed baseline.

Verification: 578 distinct host cases pass across the final affected batches.
The usual game-clean.cue/.iso is rebuilt; .bss ends 0x06083E80, 384 B below SGL.
Link points/matrices/skin and draw-view scratch use checked low-RAM carves;
heap size, SGL limits and actor counts are unchanged. Matching SH-2 audit finds
no wide/soft-float helpers in the new bounded paths; audited frames peak at 172 B.
The mastered ISO matches all 889 staged payloads. This proves build/staging,
not human visual/FPS acceptance. Full logs and image hash are in the checkpoint.
3,190 real Ranch/Kakariko collision probes match original
contacts while source square-root calls fall from 27,214 to 701. Cucco unused
wing/head pose interpolation is removed; timers/RNG/gameplay remain. Existing
wide Fx narrow-phase math remains migration debt. Pause renderer checks cover
all 24 inventory slots and quest bits, upgraded Ocarina, region changes, page
lifecycle and VRAM restoration. Runtime checks remain pending.

The prior sprite/CPU/save/cleanup checkpoint is now 9d384cd. The current
world-completion continuation is recorded in this checkpoint. The user authorized
commit/push and integration into main on 2026-10-04. This merge preserves the
prior main at oot-vslice-demo (7c8cc93), with dev, dev-gameplay and
feature/kokiri-slice-actions retired. Tag archive/dev-2026-10-04 preserves the
dev-only tip 5b560ab; its dirty worktree remains detached with files intact.
Earlier build evidence below describes those prior checkpoints.

Earlier human test: startup/each zone shows `dosei_allocator_free(): Null pointer`
about six times (22% dynamic memory, 0% sprite memory); one Ranch NPC visible;
generic-zone doors still unusable. Prior build/host success is not runtime
acceptance. Confirmed cleanup defect: story_route_free unconditionally frees
four Saria + two owl slots; SDK rejects NULL and test stubs missed this.
Cleanup guards were already present at the start of this continuation. Current
work additionally rolls failed story/emerald loads back and tests real failed
loads/retries with NULL/double-free rejecting stubs. Shared source-gated handle
doors/shutters, layer filtering, scripted entrance forwarding and whole-world
route auditing are implemented. Save v11 preserves old file versions and
adds generic source-scene flags, dungeon keys/items, bottles and era/time.
Same-room NPC spawns discover sheets; diagnostics separate actor, missing-sheet,
fallback-pose and allocated-slot counts. Automatic talk offers and Ranch milk
reward/textbox handshakes now use the original source identifiers.
At the committed baseline, 400 distinct host checks passed. Full WSL asset regeneration and the final C-only
Clean relink pass (`world-completion-build.log`, `world-completion-link.log`).
That game-clean.cue/.iso had .bss end 0x06083D70, 656 B below SGL.
Save state, separate write/preview scratch and draw-cache ownership now use
bounded, initialized low-RAM carves. Virtual story banks use IDs 1024+ and
C-prefixed files; real room banks no longer get overwritten. Staging/budget
checks pass and retired story aliases are removed. Previous margins below
are historical. Preserve heap sizes, actor capacities and boundary checks.
Full world traversal and NPC coverage remain incomplete. Continue missing
destinations, special transitions, runtime horse logic, missing actors, dialogue,
rewards and resource gates. No complete-world or runtime acceptance claim.
Level Select offers **All Items? Off/On**, default **Off**, and
**Link: Child/Adult**, default Child. A toggles the highlighted option.
Begin Play Test grants the selected test loadout. The user clarified
that quest items are required too: all stones (including Kokiri Emerald), songs,
medallions and other quest bits are granted, plus source inventory/equipment,
20 hearts, capped ammunition/magic, 500 rupees and eight source-debug small keys.
Upgraded items/final trade variants occupy the source's mutually exclusive slots.
Adult entry now defaults C to bow/bombs/hookshot when owned. Tools act through the
decomp actors with ITM*.SPR sprites; equipment page equips Biggoron, Mirror and
Iron/Hover boots (code + host tests + Clean target build; human runtime test pending).
Still denied: hammer, lens, magic spells, beans.
No extra story completion flags are set. C actions for unimplemented weapons
remain unfinished despite their source inventory ownership. The existing fresh
test-run/no-backup-slot behavior remains; toggling alone never changes the save.
Detailed actionable handoff: [NEXT_CHAT_WORLD_COMPLETION.md](NEXT_CHAT_WORLD_COMPLETION.md).

Human confirms the 32-byte palette repair checks out in Mednafen. That graphics
repair is runtime-accepted. Checkpoint 9d384cd contains Ranch lookup/reservation
repairs, converted-cast model removal and baked fairy wings; the later report of
one Ranch NPC means full population/visibility is still unaccepted.
Permanent rule: NPCs/animals/fairies/non-boss enemies
use sprites; bosses are explicitly exempt to preserve complex damage/puzzle
hitboxes. Full era/layer/trigger coverage is planned in
[ACTOR_SPRITE_ROLLOUT_PLAN.md](ACTOR_SPRITE_ROLLOUT_PLAN.md). High CPU/slow
gameplay versus Kronos remains open. The accepted palette repair was pushed as
11312ec; subsequent Ranch/CPU/save/cleanup work is preserved in 9d384cd.
This checkpoint records the world-completion continuation after that baseline.
Keep batched verification and one Clean image;
do not request intermediate emulator checks. Decomp retains the Saturn backend.

Requested CPU/VDP1 review is complete; findings and ordered refactors are in
[the current performance review](OOT_CORE_PIPELINE_PLAN.md#current-performance-review-2026-10-03).
First implementation is the heading conversion: 32-bit integer math replaces
software-double conversion, with bounded scaling for large deltas. Host regression
passes 362,433 angle-input pairs and 11 existing player-camera tests pass.
WSL Clean build and matching target disassembly pass; usual image rebuilt.
Human now forbids 64-bit runtime math and allows approximation over exact OoT
fidelity. The tentative wide-divide patch was removed; converting existing Fx
and other wide math remains explicitly unfinished. Prior inspection confirmed
software-double heading conversions in the C backend, costly fixed-divide setup,
prop matrix decomposition/reconstruction, unconsumed sprite pose work and full
room vertex processing after polygon rejection. Their current frame-time shares
are unmeasured. No emulator run or performance acceptance.

Earlier Mednafen/hardware evidence, retained as context for the priorities above:
VDP1 3D models and 2D sprites corrupt; slow title music/scenery startup; missing
nightmare riders; Navi opening memory error followed by skipped shots; house
exit failure. Latest human test: all opening sequences/shots now complete, but
Navi room reads pause the cutscene and music starts late. The later palette repair
now has explicit human graphics acceptance.
Earlier house exit showed CD read failures for CS4.BIN, then S1.OOC (not a
confirmed OOM). Latest human explicitly confirms opening the menu before music
now works. House-exit CD failure has no explicit acceptance yet. Latest forest
and nightmare screenshots still show severe VDP1 corruption before the CLUT fix.

## Prior world-content continuation: implementation and verification

The committed baseline includes cleanup rollback/retry, common door policies, source save predicates, same-room
sprite discovery, automatic talk/milk handshakes and the opt-in full test loadout
with passing host, target and staging checks after the RAM and virtual-bank repairs above.
The current regression batch extends this with full pause/HUD item pictures,
quest display, source map regions, real era assets, Ocarina and populated-room
render/CPU fixes. Source song recognition does not finish the missing song puzzle
actors, Temple sword time travel, dungeon Sun stun, or every inventory action.
No emulator was launched; human acceptance of these changes remains pending.

The source inventories enumerate 110 scene-table entries and 429 actor profiles.
The all-map task above registers all 101 maps with retail source payloads,
preserving 75 existing IDs and adding 26 maps; host and target evidence is in
the linked handoff, while runtime acceptance remains open.
Nine DEBUG_ASSETS entries have no source payload in the retail inputs.
The actor ledger includes 836 room layers, conditions, dialogue/reward/drop
sites and conservative dynamic dependencies; zero scenes pass its ready gate.
Forty-one horse clips are baked offline (910,945 B total sheet storage including
allocator terminators; largest cel plus aligned CLUT 1,472 B). They are neither
runtime-imported nor staged. Sixteen generic sprite slots, 16 actor views, missing
actors such as En_Ma3 and unimplemented actions/branches remain coverage limits.

## Prior checkpoint implementation and verification

Evidence below belongs to checkpoints through 9d384cd. Build margins, test
counts and image contents describe those builds, not the current continuation.

- Ranch/sprite checkpoint: linked-symbol sprite keys fix the
  ROM-offset mismatch (Malon previously expected 0x820, linked at 0xBD8).
  Compact object blobs now retain clip lengths but no skeleton/frame/joint data;
  Ingo OOB is 1,720 B, child Malon 680 B. Current clips load before optional clips;
  an unavailable pose keeps a compatible loaded sprite instead of vanishing.
- Ranch pixels shrink from 341,568 to 272,448 B (67.5 KiB saved); room + CLUTs
  are 295,776 B. Bake reserves 64 KiB actor bank plus 32 KiB spare. Human's
  prior 96% runtime VRAM/invisible-NPC report is not yet runtime-accepted fixed.
- Fairies now draw original textured wings and glow in one 32x32 billboard;
  no runtime FAIRY.BIN, four wing polygons, travel-facing math or skeletal work.
  NPC slots stay resident across visibility changes; shared 32-bit frustum
  rejection happens before sprite facing/uploads and fairy orbit work.
- Nightmare riders/horses, Saria bridge, owl and story Ganon/horse load SPR only.
  Their BIN/ANM and legacy NPC/skin payloads are removed from the staged disc;
  original models remain offline bake inputs. Static scene/bridge props and
  Link stay geometry. Boss models and complex hitboxes remain exempt.
- Verification: 36 focused host checks pass (sprite keys/clock/wing texture/assets,
  bank lifecycle, culling, story/cutscene and resource checks). WSL Clean target
  passes, log `build/ranch-sprite-build.log`; usual image rebuilt. Main .bss ends
  0x06081DC0, 8,768 B margin. Sprite culling disassembly uses 32-bit operations;
  legacy wide math elsewhere remains. Human runtime/FPS/dialogue checks pending.
  Ranch gameplay horses are still unimported; cutscene horses do not cover them.

- Sprite/save checkpoint: fairy flyby, Saria greeting and shopkeeper
  use only NPC SPR sheets, with no runtime model fallback or head/torso tracking.
  Flyby uploads use the authored cast instead of Link's house scene. Imported
  Ranch NPCs retain a 32-bit frame clock for action transitions, but no skeleton
  reads, joint allocation, pose decoding or morphing. Ingo/Malon/Talon/cow
  tracking and Ingo fidget/root stagger are bypassed; talk/action/collision stay.
  Malon's zero-limb metadata matches sheets by object/clip. Fixed 16-bit sprite
  slot sentinel handling so a full bank cannot report a successful upload.
- Mednafen evidence: nine hash-named internal backups, only two older ones with
  DOSEI0. Current config uses default `%f.%M%x`; rebuilds changed disc identity.
  Copied the newest active save (`7f402babb95acd27ace60606f8dddfd6`) to stable
  `sav/game-clean.bkr`, plus its RTC file; originals retained, backup hashes equal.
  Launcher now performs this non-overwriting migration before running Mednafen.
  No global emulator settings changed. Host mock tests cover preservation across
  hash changes, existing stable saves, deleted entries and custom naming.
- Backup driver also gets reserved low RAM (16 KB code + Sega STN-52's 8,312-byte
  workspace), no automatic formatting, and specific save failure text. Mounted
  device read failures no longer masquerade as NEW FILE. These are code repairs,
  not proof they caused the reported Mednafen failure.
- Verification for this batch: 85 focused host tests pass. WSL Clean target build
  passes (`build/sprite-save-build.log`); usual `game-clean.cue/.iso` rebuilt.
  Main .bss ends 0x06082220, 7,648-byte margin. Sprite clock target disassembly
  uses only 32-bit arithmetic; the existing wider Fx ABI storage is unchanged.
  Runtime save/reload, sprite appearance, dialogue and performance still need
  human acceptance; no emulator launched. The later batch above also converts
  the separate nightmare riders/owl renderers.
- CPU checkpoint: heading conversion uses 32-bit range checks, shifts and
  slAtan on SH-2. Six software-double calls per heading are gone; matching
  game-clean.elf no longer links __floatsidf/__muldf3/__fixdfsi. Build log:
  build/cpu-heading-build.log. Main .bss 0x060838b0, margin 1,872 B (was 96 B).
  Host checks above pass; no emulator run or measured FPS gain. Other existing
  64-bit math remains migration debt. No wide-divide optimization was retained.
- Existing decomp integration and NPC sprites: see OOT_CORE_PIPELINE_PLAN.md.
  Sprite baseline is commit 8874db2; Kokiri was human-accepted in Kronos only.
- Allocator/CD checkpoint: allocator splits reused holes and merges adjacent free blocks
  on allocation pressure; Clean sprite NPCs no longer retain unused 3D copies
  (Saria's former greeting mesh exception is now removed); Navi retains pixel pool/maps but loads each
  room mesh through bulk-read scratch, saving 737,384 resident mesh bytes.
- Boot music accepts caller-owned scratch for one whole PCM read. Other callers
  use multi-sector GFS reads, not Jo's per-sector reader.
  New CD ownership fix: project-local Jo GFS open/load/read hooks stop music
  read-ahead before file access; music resumes from consumed sector on service.
  Stop/start errors propagate, stream close stops read-ahead. Mock CD regression
  passes for interrupted/resumed loads, final partial sector and error paths.
- Graphics investigation: opening house uses VDP1 panorama bank 4, not the
  fixed NBG1 JPEG. This shot alone does not implicate NBG1 cycle patterns.
  Added actual VRAM CLUT readback validation. SP/PR/END now uses an independent
  overlay, drawn last even on Clean/title/menus/cutscenes: hold L+R one second
  to toggle, release before another toggle. Hidden initially. No direction needed.
  Correction: hardware SPCTL/PRISA are write-only; original zero readouts were
  invalid. New `SGL SP / PR` shows SGL's RAM shadow (intended settings only).
  END still reads hardware EDSR. Human confirms toggle shows the readout.
  Register audit also found TVMD read/modify/write in every VBlank and pause
  saving write-only cycle registers. TVMD now preserves SGL's shadow bits;
  pause saves shadow cycles and uses slScrCycleSet to update shadow and hardware.
  Latest human readouts: SGL SP 0723, PR 0604; END 1 in house, 3 in nightmare
  and forest. These plausible values do not establish texture correctness.
  Latest graphics batch additionally replaces black cutscene fades' negative
  colour offset with VDP2 alpha blending against a black line-colour screen.
  Host analysis of actual house pixels at screenshot FADE 100: old subtraction
  clips 59.91% to black; blending leaves under 2% black even with 5-bit output.
  This explains a major artifact in that shot, not all reported VDP1 corruption.
  Background sky fades proportionally; white flashes/gray transition path retained.
  The initial eight-byte CLUT padding was insufficient and is superseded below.
  Flat polygons/lines use
  required texture-mode bits 0; texture relocation no longer adds addresses to
  Link's flat RGB colours. The fade made the house brighter, but corruption persisted.
- Graphics root cause found: VDP1 CLUTs require 32-byte alignment, even though
  CMDCOLR encodes addresses in eight-byte units. Link's current 8912-byte pixel
  payload placed its palettes 16 bytes off that boundary and propagated the
  offset into later room palettes. Applying the hardware boundary to actual
  house assets reproduces the speckled curtains/walls and wrong floor colours
  offline. Source and correctly addressed converted house textures are clean.
  All three CLUT allocation paths now align actual VRAM addresses to 32 bytes:
  mesh banks (Link/rooms/panorama), streamed Field pools and per-tile actor/NPC
  uploads. Capacity checks and offline budgets include the padding. Existing
  texture data and imported decomp logic are preserved.
- Host: four graphics backend tests and six VRAM budget tests pass; eight Field
  stream tests pass. Actual upload functions are tested across all eight-byte
  start alignments, disk/cache paths, all 16 palette entries and capacity failure.
  Negative control: both upload regressions reject the former eight-byte rule.
  Earlier seven allocator tests and CD ownership regression also passed.
  Target: WSL Clean build passes, 96 bytes below SGL work area;
  log build/mednafen-clut-build.log. Runtime: no emulator launched. Human confirms
  earlier opening shots complete, toggle visible, and menu before music works.
  Human subsequently confirms the 32-byte palette fix checks out in Mednafen.
- Ranch sprite checkpoint (runtime pending): host loaded sheets before
  Actor_UpdateAll spawned the room's NPCs, so the NPC list was empty. Asset load
  now follows the first actual decomp update, including after room changes;
  skipped 20 Hz steps never trigger premature loads. Sprite matching now accounts
  for SkelAnime's extra root-translation joint (Ingo: 20 joints vs 19 baked limbs).
  Sheet allocation includes Jo's trailing NUL, avoiding a one-byte heap overrun.
  Generic sprite VRAM slots now follow actual spawned instance count, capped at
  eight, instead of always reserving eight largest cels for even one NPC.
- CPU work removed: sprite-only C NPCs no longer compute unused head/torso
  tracking each catch-up step (now also Saria and fairy flyby). Scene and Link
  flat-face mode normalization happens at upload instead of scanning their
  attributes every draw; dynamic fog transitions and native callers retain correct
  modes. Decomp still steps at 20 Hz with the existing input/hit-volume contract.
  L+R's existing one-second toggle now also shows millisecond timings: MS total
  frame including sync, M movement/gameplay, G scene draw, L Link draw, OC last
  decomp update. CPU~ remains callback share, not Windows CPU utilization.
  Overall Mednafen slowdown has not been quantitatively attributed or accepted
  as fixed; target timing evidence is still required. No emulator launched.
- Checkpoint verification: two host regressions execute actual host lifecycle/load/upload/
  draw functions with deferred actors; four graphics regressions also pass.
  WSL Clean build passes, 96-byte high-WRAM margin, log
  build/mednafen-ranch-cpu-build.log. Cold clip/scroll loading code uses Os to fit;
  heap and SGL capacities preserved. That Clean image contained these changes.

## Next actions / remaining work

Implementation order is R0-R7 in
[Full core ownership and C retirement](#full-core-ownership-and-c-retirement).
The queue below preserves earlier acceptance/content requirements within those
waves; it does not authorize a separate performance-first task or emulator use.

Human accepted the current mode-2 Clean texture look; Clean now defaults to
that mode. See the measurement handoff above. Broader Kokiri/Field route checks
and the other visual/gameplay acceptance items below remain open.

Human verification queue includes the rebuilt inventory wave: digital aim and
crosshair, repeated arrow/hook shots, contacts/return, bombs and adult gear
selection plus texture/fallback restoration. Global source movement now runs
at the intended rate; also check existing source NPC behavior in real rooms.

Next implementation: close real Player preservation gaps under PLAYER_MIGRATION.md.
First human validates the active rock/stick/aim repair against candidate-10 Clean;
then close core state/items and production demand animation toward C Player
retirement. Carry measured moving-frame optimization through those waves.
Retain exit checks for Ranch, Zora's
Domain and the Saria bridge. Also check repaired C mapping,
repeated shots, cancel and idle/moving FPS with the slave enabled. Continue
source inventory/camera parity and demand animation loading; measure new memory
requirements against the current resolved artifacts. Do not restart the already
live Player/collision cutover or treat rollback C paths as authoritative.
Retire each legacy path only after acceptance. Heap/actor capacities stay intact.
The older actor/Fx32 order does not defer this directive. Wave 0 host/target
evidence remains in the pipeline handoff. The following are retained verification
gaps and full-game requirements, not competing permission to postpone migration.

0. Permanent camera easter egg Clean rebuild and host checks pass.
   Exit/orbit/Link-fade Clean rebuild and static RAM checks pass.
   Reversed/eased turns and UI tick passed host checks and were included in the
   historical 10:33 full Clean image. Human checks restored Adult Link, turn feel/audio,
   text dismissal, quarter-turns,
   nearby-ground fade. Higher-camera ground holes remain.
   Human checks Field overhead default, regular defaults elsewhere, two-view
   L+R+B cycling and movement during first-person/hills.
   Earlier whole-Field capacity checks pass; ground defects remain reported.
   Human checks ground transitions, seams, movement, castle/ranch visibility,
   at different times/camera angles, including curtain visibility.
   Dark sky gradient is human-accepted and retained. TR remains isolated;
   production uses SGL. Builds do not prove warp or performance acceptance.
1. Preserve passing combined regression verification and the usual Clean image,
   heap sizes, actor capacities and SDK error handler. Human still checks all
   inventory/quest pages, Ocarina input, both eras, house views, door/tomb art,
   steady hearts and populated Ranch/Kakariko frame timings. Human owns all
   runtime checks; earlier emulator-control exceptions are superseded. Capped items remains
   opt-in on Begin Play Test; A toggles the highlighted
   All Items or Link age option. Complete the missing source song actors and adult story path.
2. Finish the source entrance graph. Current route audit separates structural
   reach from traversal acceptance and records every known missing destination,
   reverse edge, source gate and extraction error. The all-map task above admits
   all retail maps; nine debug-only entries need unavailable source inputs.
   Special grotto returns, alternate collision/spawn headers, transition cameras/fades and
   unimported scripted/warp actors remain blockers. Kakariko cutscene layers also
   share collision exit indices beyond their shorter exit arrays; real Player
   now bounds those indices against the selected imported list. The older host
   route audit can still overread following light data as entrances. Bound that
   extraction before trusting those edges; do not guess a destination. Preserve keys and boss logic.
3. Review and extend the generated actor ledger across eras/time/story/dynamic
   triggers. Enemy W0a groundwork is implemented and target-built; human runtime
   acceptance remains open. Enemy work runs alongside mandatory Link migration; follow
   ENEMY_ROLLOUT_PLAN for enemy order and Player-gated capture/gear behavior.
   The remaining NPC order retains required Fx32 verification and scene packs:
   Kokiri, Deku Tree, Lost Woods, Field, Ranch, Market, Castle and Kakariko,
   then the remaining game. Ranch horse runtime and En_Ma3 remain required.
   Offline horse sheets and text on disc do not implement gameplay. Sprite banks
   must preload reachable trigger sets and budget scenery/actors/effects together.
   Sixteen generic cel slots and 16 views remain explicit limits, not full coverage.
   Debug target verification, sprite pitch views, non-boss enemy migration,
   player/camera/cutscene and combat bridge parity remain required. Preserve the
   20 Hz/input/hit-volume contract and boss exemption. Do not archive a replaced
   C system before human acceptance of its replacement.
4. Performance implementation remains open: establish per-displayed-frame CPU
   totals and draw-completion timing. Current gate is sustained Mednafen 20 FPS
   moving/aiming using M and unchanged emulator settings; latest batch/status
   is at the top. Human now prioritizes grab/stick/aim repairs before further
   performance work; these are no longer deferred.
   Heading target verification is complete;
   preserve the recorded Fx32/helper removal and audit new Player paths. Pass
   prop matrices directly where supported; profile the full collision workload.
   Sprite pose separation is implemented for the current sprite NPC cast.
   Follow with compact scene culling and per-cel upload reduction (stable banks now implemented);
   assess per-cel cropping from the review's offline evidence. Preserve gameplay
   and the 20 Hz/input/hit-volume contract. Approximation and native SH-2 products
   are allowed; software-wide/soft-float fallback is not. A storage-width change needs matching collision/units and
   scene/object blob changes. Broad -O2 and relocating the whole blob are not
   validated solutions. Verify the matching artifact before budgeting Player.
   Candidate-10 Debug leaves 496 B before SGL; accepted Clean leaves 5,968 B.
   Gameplay-repair temporary Debug link leaves 80 B; host/audit/budget/ISO checks
   pass, human acceptance pending. The historical
   272-byte curtain and 2,240-byte water/menu margins are superseded. Older 304/2,704/8,736-byte
   reports are not available headroom; the 2,704-byte report was a mixed build.
   Human reports prior idle gains to 12-18.7 FPS but moving about 8; target
   20 while moving remains open. Human tests; no automated emulator runs.
5. CD house-exit fix still needs verification; Navi room-read
   pauses and late music cues remain open. No CD test is requested now; the
   separate polygon plan proposes a human movement gate after an authorized P1.
   Existing generic NPC libraries now preload by the scene object union; no
   same-room sprite CD discovery remains in that path. New enemy/effect dynamic
   sets still need full roster/budget admission. Missing clips/capacity remain
   explicit failures; host evidence does not establish runtime readiness.
   Graphics/CD checkpoint 11312ec remains pushed and graphics accepted. Broader
   save/reload, dialogue and performance acceptance remain pending; host tests or
   a build do not prove that the overall slowdown is resolved.

Detailed handoff and historical evidence: OOT_CORE_PIPELINE_PLAN.md.
