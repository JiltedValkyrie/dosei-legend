# Full OoT recomp plan

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

Claude integration step 1 (2026-10-06): strict bank (uncertain clips strict) worst
scene 554,668 B; placed into real old allocations, worst pack fits. Two-pack
rollback does not fit (reload-from-disc rollback proposed). Frame-bank adapter,
region loader (both host-tested, isolated) and 5-region partition (2,514 B
main free) done; 110 collision call sites listed. Next: core collision API +
port non-Player callers, then resolved build. See PLAYER_MIGRATION.md.

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

Current state: C owns Link movement/actions; bridge_player.cpp supplies a proxy
to core actors. Link and core actors still use separate collision worlds. The
gallery prop and its geometry bridge are implemented with host/target evidence
recorded in OOT_CORE_PIPELINE_PLAN.md; human runtime acceptance is pending.
Migration staging has started on `oot-core` (Codex, 2026-10-06), fast-forwarded
to the current main baseline so existing fixes survive. The code/test-backed
[behavior inventory and dependency map](PLAYER_MIGRATION.md) records preservation
units, owners and gaps; individual inline-fix/test-case audit remains required
before each subsystem cutover. A separate importer stages the three real Player
sources through production fixups without changing the playable source list.
WSL host syntax passes all three after scoped enum/Fx and scaled rumble fixes.
Two focused tests pass, including 102,000 rumble ticks matching source pulse
timing with actual Fx32. Literal-range audit closed (Claude, 2026-10-06; five
tests pass). Pose-pass split preserves anchors; standalone GC Player is 143,437 B.
Combined retention now includes existing core dependencies, libgcc, temporary
duplicate-owner removal and 521 real animation headers: **659,244 B**. Baseline
501,840 B matches existing ELF size; combined wide audit passes. Core carve plus
two large Low RAM gaps totals 655,360 B, already 3,884 B short before remaining
hooks/frames/skeletons. Selected design adds retired music/fairy cart reservations
(24 KiB), yielding 679,936 B capacity and 20,692 B unallocated before those missing
costs/alignment. One ELF, separately loaded resident regions; no heap reduction
or speculative C-Link-retirement credit. Claude sized hooks + real skeletons:
8,884 B (estimates), about 11,808 B left before frame bank/alignment.
Frame bank does NOT fit: reachable raw frames 2.26 MB/age vs 423 KB current
bank; lossless compression too weak. Shared-bank prototype with trigger
residency and FK-checked reduction: 0.91-1.24 MB peak; still no fit.
Packed bank v1 at 0.5 units: 737,644 B peak, byte round trips pass; no fit. Needs a frame-reduction decision before
sections/loader.
Full placement/link/loader remain open.
Native Draw remains reachable from source actions; skeletons cannot be blank
placeholders. 9 duplicate owners and 713 unresolved symbols mapped in
PLAYER_MIGRATION.md. Isolated relocatable GC probes only; no resolved target game link/build, bake,
runtime ownership replacement or human acceptance is claimed.

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
   water and camera metadata. A collision-query adapter alone is not completion.
   The gallery bridge is temporary static-building support: source review found
   Y-only rotation, uniform scale from X, missing water/camera data and no rider
   feedback to core. It calls bg_dyna_set every core step, rebuilding transformed
   triangles/bounds even when unchanged. Avoid that repeated work while the
   bridge remains, without erasing previous transforms needed for rider motion.
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

Latest recorded Clean margin is 272 B (curtain/gallery checkpoints); this task
does not reverify the artifact. Older failures, margins and build holds below
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
The added Level Select option is **ALL ITEMS + MAX STATS**, default **NO**;
L toggles it; R selects Child/Adult, default Child. Confirmed entry grants the test loadout. The user clarified
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

The source inventories enumerate 110 scenes and 429 actor profiles. Only 75
scene assets are registered: 35 source scene destinations still lack assets.
The actor ledger includes 836 room layers, conditions, dialogue/reward/drop
sites and conservative dynamic dependencies; zero scenes pass its ready gate.
Forty-one horse clips are baked offline (910,945 B total sheet storage including
allocator terminators; largest cel plus aligned CLUT 1,472 B). They are neither
runtime-imported nor staged. Eight generic sprite slots, 16 actor views, missing
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

Next implementation: continue mandatory Link migration under the rules at the
top of this plan and PLAYER_MIGRATION.md. Initial inventory and isolated real
source staging, tested fixed-point patches and the isolated SH-2 object audit
exist. Combined retention with actual animation headers is 659,244 B; selected
five-region resident design offers 679,936 B before missing dependency costs.
Next implement/size remaining engine hooks, skeletons and animation backing,
partition sections with linker guards and add a versioned multi-region loader.
Require a resolved link before accepting fit. Temporary-copy duplicate removal
is measured; live owners and C Link remain until their cutover. Heap stays intact.
Complete each subsystem's detailed fix audit before its staged cutover.
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
   steady hearts and populated Ranch/Kakariko frame timings. Astra's authorized
   emulator control is scoped to the warp diagnostic. Capped items remains
   opt-in on confirmed Level Select entry; L toggles
   it, R selects era. Complete the missing source song actors and adult story path.
2. Finish the source entrance graph. Current route audit separates structural
   reach from traversal acceptance and records every known missing destination,
   reverse edge, source gate and extraction error. Thirty-five absent scene
   assets, special grotto returns, alternate collision/spawn headers, transition cameras/fades and
   unimported scripted/warp actors remain blockers. Kakariko cutscene layers also
   share collision exit indices beyond their shorter exit arrays; the old audit
   overreads following light data as entrances. Bound extraction by referenced
   data before trusting those edges; do not guess a destination. Preserve keys and boss logic.
3. Review and extend the generated actor ledger across eras/time/story/dynamic
   triggers. After the immediate Link migration, retain the proposed actor order
   with the required Fx32 verification and scene packs:
   Kokiri, Deku Tree, Lost Woods, Field, Ranch, Market, Castle and Kakariko,
   then the remaining game. Ranch horse runtime and En_Ma3 remain required.
   Offline horse sheets and text on disc do not implement gameplay. Sprite banks
   must preload reachable trigger sets and budget scenery/actors/effects together.
   Eight generic slots and 16 views remain explicit limits, not full coverage.
   Debug target verification, sprite pitch views, non-boss enemy migration,
   player/camera/cutscene and combat bridge parity remain required. Preserve the
   20 Hz/input/hit-volume contract and boss exemption. Do not archive a replaced
   C system before human acceptance of its replacement.
4. Performance implementation remains open: establish per-displayed-frame CPU
   totals and draw-completion timing. Heading target verification is complete;
   preserve the recorded Fx32/helper removal and audit new Player paths. Pass
   prop matrices directly where supported; profile the full collision workload.
   Sprite pose separation is implemented for the current sprite NPC cast.
   Follow with compact scene culling and per-cel upload reduction (stable banks now implemented);
   assess per-cel cropping from the review's offline evidence. Preserve gameplay
   and the 20 Hz/input/hit-volume contract. Approximation and native SH-2 products
   are allowed; software-wide/soft-float fallback is not. A storage-width change needs matching collision/units and
   scene/object blob changes. Broad -O2 and relocating the whole blob are not
   validated solutions. Latest recorded Clean margin is 272 bytes; verify the
   actual matching artifact before budgeting Player. Older 304/2,704/8,736-byte
   reports are not available headroom; the 2,704-byte report was a mixed build.
   No new FPS or CPU-versus-VDP1 conclusion is established.
5. CD house-exit fix still needs verification; Navi room-read
   pauses and late music cues remain open. No CD test is requested now; the
   separate polygon plan proposes a human movement gate after an authorized P1.
   Same-room NPC sheet discovery is implemented and host-tested. Reachable
   dynamic sets still need preloading and budgeting before triggers; discovery
   may read the CD at spawn. Missing clips/capacity have explicit diagnostics.
   Graphics/CD checkpoint 11312ec remains pushed and graphics accepted. Broader
   save/reload, dialogue and performance acceptance remain pending; host tests or
   a build do not prove that the overall slowdown is resolved.

Detailed handoff and historical evidence: OOT_CORE_PIPELINE_PLAN.md.
