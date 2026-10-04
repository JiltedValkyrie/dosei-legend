# All-scene NPC and enemy sprite rollout

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
heap and actor limits unchanged. Final ISO refresh is blocked by running Kronos
holding game-clean.iso; do not overwrite a mounted image. Logs:
build/round-shadow-link.log and build/round-shadow-boundary.log.
Human visual/FPS acceptance remains pending; no emulator launched.


Updated 2026-10-04. Active branch: main (oot-core pipeline). Owner: current implementing agent;
human owns emulator/hardware acceptance. This plan covers the entire game,
including scenes and actors not yet imported. It is not a completion claim.

## Permanent contract

Every NPC, animal, fairy and non-boss enemy uses baked sprites unless the human
explicitly authorizes an exception. **Bosses are explicitly exempt for now**
(human, 2026-10-03): retain their models, pose-driven complex hitboxes,
damage/weak-point logic and puzzle interactions. Do not sprite-convert bosses
or simplify their collision under this rollout. Track the exemption in the
coverage ledger; only a later human directive changes it. Link retains its
separate renderer. Rooms and static gameplay props
remain geometry; categorizing a character as a prop does not exempt it.

N64 assets are offline source. Runtime character packages contain sprite cels,
palettes, clip timing/events and small collision/attachment descriptors only.
No character mesh/material/skin/per-vertex tracks, skeleton pose evaluation,
joint or morph allocation, head/torso tracking, or 3D fallback. Shader/material
appearance is baked into pixels. Keep original game logic, conversations,
movement, cue timing, damage, weak points, hit reactions, rewards and drops.
Any pose-derived gameplay position becomes a bounded 32-bit anchor or simple
collision shape, independent of sprite facing. Do not remove gameplay to save
render time. Approximation is explicitly allowed; no new 64-bit runtime math.

## Current evidence and gaps

New populated-room regression (2026-10-04): Ranch Cuccos and Kakariko cause
severe slowdown; title scenery without actors runs smoothly. Imported Cucco
still performed eight unused wing/head pose interpolations. Those calls are
removed while clip clocks, gameplay timers and RNG advancement stay intact.
Conservative 32-bit bounds now reject distant source static collision triangles
before expensive Fx narrow phase; actual imported collision tests preserve all
3,190 probe contacts and reduce square-root calls 27,214 -> 701. Dynamic actor
collision and boss hitboxes are unchanged. Full assets and the final Clean
relink now pass, with 578 distinct host cases across the affected batch and
384 B high-RAM margin. The matched SH-2 bounds wrappers use the actual Fx ABI
without wide/float helpers; Saria proximity also reads 32-bit words directly.
Actor-view scratch retains 24 rows in a checked, fill-before-read low-RAM carve.
Human populated-room FPS acceptance remains pending. Full Fx-wide migration
and actors missing from the coverage ledger remain required.

The sprite/CPU/save/cleanup baseline is now commit 9d384cd; the continuation
below is recorded in this checkpoint, with commit/push and main integration
authorized on 2026-10-04. 400 distinct host checks pass. Full assets and the final
C-only WSL Clean relink pass; usual image rebuilt, .bss end 0x06083D70 / 656 B
spare. Save/write/preview/draw-cache low-RAM carves fix the integration overflow.
Story banks use IDs 1024+ and C-prefixed files; real room banks no longer collide.
Staging/budget checks pass; prior build figures below are historical. Human
runtime acceptance and complete actor coverage remain open.

Earlier human test reports six repeated null-free errors at startup/zone changes,
one Ranch NPC visible and generic doors unusable. Cleanup guards are now fixed
in all three sprite teardown paths; stubs detect NULL frees. Eleven focused
host checks pass, including 256 allocation combinations and repeated cleanup.
Baseline Clean rebuild passed (`build/null-free-fix-build.log`), .bss margin 8,736 B.
Runtime acceptance pending. Full doors and NPC/dialogue execution order is in
[NEXT_CHAT_WORLD_COMPLETION.md](NEXT_CHAT_WORLD_COMPLETION.md).

Current continuation also tests actual failed loads/retries and double frees.
A versioned [source coverage ledger](ACTOR_COVERAGE.json) enumerates 429 profiles,
110 source scenes, 836 room layers/parameters and transitive static spawn candidates.
Indirect spawns and boss dependencies remain explicit. No scene is marked ready:
static extraction is not proof of story-branch or runtime coverage. Ranch source
conditions explain why a fresh child daytime exterior can contain only Ingo;
normal gameplay horses are missing. Adult daytime Malon uses En_Ma3, not the
imported En_Ma2. Offline horse Skin sprites do not implement runtime actors;
importing their current Fx action code would add forbidden wide arithmetic.
There are 41 offline gameplay-horse clips, including young/normal/Epona/Ingo and
Gerudo-saddle variants: 910,945 B total sheet storage including allocator
terminators and a largest live cel plus CLUT of 1,472 B. These packages are not
staged; no horse gameplay or per-scene simultaneous population budget is complete.
Thirty-five source destinations also still lack registered scene assets.

Host sprite discovery includes later same-room spawns without reloading existing
sheets or retrying absent files every step. Packets are validated before upload;
L+R diagnostics show imported views, missing sheets, fallback poses and allocated
slots. Dynamic preloading, eight-slot/16-view limits and full scene actor/effect
budget closure remain open. Save v11 and its mirror retain source scene flags,
keys, equipment, quest items, bottles and era/time. The player bridge honors
automatic talk offers and milk reward/textbox parent handshakes. Talon's timer/
carry minigame, ocarina/song interactions and other unsupported rewards remain
open. Combined target/human verification is tracked in the game plan.

Prior checkpoint implementation, Clean target-built then (runtime pending):
C Kokiri NPCs, shopkeeper and Saria greeting use SPR; generic Ingo, child
and adult Malon, Talon, Cucco and cow use sprite clocks and compact object
metadata. That checkpoint also converts nightmare riders/horses, Saria bridge clips,
owl and creation-story Ganon/horse. Fairy wings/glow are baked together into
32x32 textured cels. Generic animation lookup now resolves linked object symbols
instead of original ROM offsets. Room-generation slots replace visibility-driven
whole-bank uploads. 36 focused host checks and the Clean target build pass;
.bss margin 8,768 B.
Human visual/dialogue/performance checks remain pending.

Human reports Ranch NPCs/animals invisible and about 96% VRAM, and forest slow
with NPCs. Ranch's old room lacked actor reservation. New bake reserves 64 KiB
for actors plus 32 KiB spare; actual room textures including palettes now
295,776 B. Timing shares and resulting runtime VRAM/FPS are not yet measured.

Ranch gameplay horses (`En_Horse`, `En_Horse_Normal`, `En_Horse_Link_Child`) are
not imported. Neither nightmare horses nor the 41 new offline gameplay clips
implement those actors. Most
NPC/enemy types and their alternate states are not covered. Existing non-boss C enemies
and any remaining non-boss character-shaped story models are migration debt.
Existing boss mesh/hitbox pipelines remain intentionally exempt.
Do not label the whole game sprite-only based on this batch.

## Coverage ledger: generated inventory, review still required

Extend the generated manifest keyed by actor ID, object, visual variant, semantic
clip, and source revision. Record gameplay owner, bake recipe, sprite package,
timing/events, collider/attachment recipe, resource costs, dependencies and
status. Keep code-implemented, host-tested, target-built and human-accepted as
separate fields. Missing data or unsupported animation must fail the coverage
gate for a scene declared ready; never silently leave an actor invisible.

Enumerate all actor profiles and categories, not only `ACTORCAT_NPC` and
`ACTORCAT_ENEMY`: bosses, fairies, livestock, companions, cutscene duplicates,
NPC spawners, enemies disguised as props, and actor category changes need review.
Identify boss encounters and gameplay-critical subactors explicitly: preserve
their collision/puzzle dependencies rather than converting by category alone.
Start with the decomp actor/object/scene/entrance tables, every room header and
alternate header, all actor parameter variants, and original actor source.
Unclassified profiles remain explicit ledger blockers.

Each scene's coverage matrix must include:

| Dimension | Required cases |
| --- | --- |
| Place | Every scene/room, interior, grotto, dungeon, boss room, shop and minigame |
| Era | Child/adult (past/future), both transitions and revisits |
| Time/setup | Day/night, alternate scene headers, entrance spawn and room layers |
| Story | Before/after story flags, quest rewards, local switches, clears and resets |
| Triggers | Proximity, talk, songs, items, timers, switches, waves and scripted cues |
| Spawn chain | Scene list, runtime spawn calls, spawners, children, summons and replacements |
| Actor state | Params, costumes, equipment, transformation, damage, death and disappearance |
| Persistence | Save/reload, room re-entry, scene return, cutscene skip and respawn |

Walk dynamic spawn dependencies transitively, including actors absent from room
lists. Record source conditions and representative reachable test scenarios.
Static text scanning alone cannot prove arbitrary code branches covered: review
indirect spawn tables/callbacks and reconcile runtime actor traces during human
tests. Impossible combinations need a source-backed reason; unknown is not absent.

## Bake and package pipeline

1. Decode original skeleton/skin, display lists, textures and animation OFFLINE.
   Support standard/flex skeletons, horse Skin, segmented limbs, multi-part
   actors and morph variants. Bosses keep their renderer. Preserve source UV/alpha and
   attachments in the baked image; never send those structures to Saturn.
2. Define semantic clips and timing separately from visual samples. Bake idle,
   walk/run/fly, turn, talk/gesture, attack, damage, death and scripted states
   where used. A small visual sample set must retain action completion/events.
   Start from the existing 5 directions with mirroring and 4bpp SPR format.
   Asymmetric actors may need distinct views instead of mirroring.
3. Share layouts/pivots, palettes and unchanged cels across compatible clips.
   Choose per-family size/pose/view budgets; ordinary actors start around
   32-56 texels tall and 4-8 poses. These are tunable ceilings, not a demand for
   expensive sampling everywhere. Large non-boss actors may need a few bounded
   sprite parts, with a measured total cost. No skeletal hierarchy for converted actors.
4. Introduce stable clip/variant IDs. Until then, generate sprite keys from the
   final linked object symbol table every build; ROM offsets are not valid
   runtime keys after compaction. Cache by source + recipe + format version.
5. Store one copy of shared artwork per package; allocate one cel per live
   visible instance when mutable. Include palette/alignment bytes and maximum
   simultaneous clip/variant working set. Stage reachable packages before a
   trigger/cutscene needs them; no unplanned per-frame CD reads.
6. Strip character meshes, materials, frame arrays, joint indices and skeletons
   from staged runtime data. Temporary offline models belong only in bake cache.
   Audit both .OOB content and disc files, not merely skipped draw calls.

## Saturn resource gates

Use the existing shared allocator and renderer. Do not add a parallel renderer
or globally increase SGL tables to hide overflow. Count actual allocations:

| Resource | Gate |
| --- | --- |
| Gameplay VDP1 textures | Current area 445,432 B; Link, UI, room, actor cels, effects, CLUTs and alignment included |
| Room allowance | Reserve actor working set before density upgrades; current default actor reserve 65,536 B and spare 32,768 B |
| Command/table capacity | Use generated SGL/Jo limits for the selected scene; count commands, sprite slots, submitted vertices and polygons |
| Work RAM | Target .bss stays below generated SGL area; report byte margin for the actual build |
| Cart RAM | Count fixed carves, object metadata, shared sheets, spawn/cutscene peaks and transition overlap; preserve allocator margin |
| Uploads | Measure changed cel bytes per frame and peak simultaneous changes; keep slots stable across camera/visibility changes |
| CPU/VDP1 time | Measure each at worst populated views and triggers; 30 Hz rendering gives 33.3 ms total frame cadence, not a claimed achieved result |

Use smaller room textures first when a room takes actor space. Then share/crop
cels, reduce redundant poses/view directions/resolution, and cap resident visual
working sets using the reachable spawn ledger. Cull before facing, cel copies
and draw submission. Never reset the whole bank because one NPC becomes visible.
If the set still cannot fit, fail the ready-scene budget check with the named
costs; do not silently drop actors, disable drops or pretend a 3D fallback solves it.
Do not claim FPS from bytes saved or a successful compiler run.

## Implementation waves and exit checks

| Wave | Work | Required exit evidence |
| --- | --- | --- |
| 0, active | Retain implemented Ranch keys/reservation, compact NPC data and fairy/cutscene mesh removal; review generated coverage ledger and complete scene resource reports/integration repairs | Current host tests + usual Clean target; human Ranch/forest/opening checks remain separate |
| 1 | Import Ranch gameplay horses and all current scene NPC variants; audit child/adult Malon/Ingo/Talon, Cuccos/cows, interiors and night layers | Every reachable Ranch actor/state renders, talks/interacts and survives save/re-entry; populated VRAM/CPU/VDP1 measurements |
| 2 | Convert currently playable forest/Tree/Field non-boss enemies; retain attacks, projectiles, stun, death/rewards/drops; leave bosses and complex gameplay hitboxes intact | Combat/drop regressions and human encounters; no non-exempt character mesh or pose payload in ready scenes |
| 3 | Remaining child-era overworld/towns/interiors and child dungeons, shops/minigames, companions and cutscene duplicates | Per-scene coverage matrix, spawn-chain closure, resource gates and runtime acceptance |
| 4 | Adult-era maps/dungeons and all past/future changes, revisits, story replacements and transformations; preserve boss exemption | Both eras + transition/save/reload scenarios; no default-layer-only acceptance |
| 5 | Ending/special cutscenes, late scripted waves and every remaining non-exempt ledger entry | Entire ledger classified and verified; bosses recorded as exempt, not converted; no unexplained missing bake or unapproved 3D exception |

Waves organize work, not permission to omit other game content. Add newly found
actors/triggers to the same ledger immediately. Human requests can reprioritize
waves without weakening the permanent rule.

## Verification and handoff

Host tests exercise production key lookup, capacity failure/retry, clipping,
stable bank ownership, clip completion/events, dialogue ownership, hit/damage
and original drop conditions. Bake tests validate alpha, pivots, every reachable
clip reference and all packet bounds. Include negative controls for the old
ROM-address mismatch and missing actor reservation.

Target checks inspect SH-2 hot-path disassembly for new wide/float helpers, audit
runtime disc payloads, report room + actor costs, and rebuild the usual
`game-clean.cue/.iso`. Human tests own Mednafen/hardware execution; agents do not
launch emulators. Capture actor counts, missing-key/upload failures, heap/VRAM
peaks and CPU/VDP1 time at named scenarios. A screenshot or build alone does not
complete a wave. Update this plan, DEMO_PLAN and the pipeline handoff together.
