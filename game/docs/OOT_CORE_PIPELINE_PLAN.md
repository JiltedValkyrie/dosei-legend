# Plan: bulk decomp pipeline ("oot-core" on Saturn)

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


Current migration handoff (human, 2026-10-06): delta blocks, per-channel shifts
and spawn-proven scene packs are measured. Worst scene 688,068 B vs LINKANIM
423,472 B. No fit. Loader and Player cutover stay blocked. C decoder matched
509 clips / 16,837 frames. Details in ASTRA_HANDOFF_2026-10-05.md.

Curtain correction (human, 2026-10-06): restore the world-space behavior from
before vertical locking. Curtain anchors to Link, follows camera yaw, and stays
upright; camera pitch/height move it naturally on screen. Two-panel geometry
and map/time tint retained. Four focused host checks pass. Requested WSL Clean
quick build passes: usual ISO/CUE rebuilt, .bss 0x06083f10, 240 B below SGL.
Log: build/curtain-world-restore.log. Human visual acceptance remains open.
Removal and vertically locked restoration superseded.

## NEXT SESSION: mandatory Link migration (human, 2026-10-06)

2026-10-09 (Claude): real decomp Player is live in Clean (`PLAYER_SOURCE=1`,
API v28, phases 1/3/4/5 first cut). Next: human test batch, fix what it
finds, then phase 6 parity and phase 7 C Link deletion. See
PLAYER_MIGRATION.md "Real Player live in Clean".
Performance work: read the Debug overlay rows as documented in
[DEBUG_OVERLAY.md](DEBUG_OVERLAY.md) (human report: ~6 FPS Kokiri, CPU bound).
Goal (human 2026-10-09): 20 FPS minimum, no 64-bit maths. Latest (Claude):
decomp core update runs on the slave SH-2 during the scene/Link draw
(PLAYER_MIGRATION.md "Core update on the slave SH-2"); Navi is En_Elf. Second Debug build
(2026-10-09) adds catch-up cap 2, camera constraint once per frame, z_bgcheck
integer fast paths (host-identical) and sub-timer rows 10-12; awaiting human
Kokiri overlay screenshots before the next cut.

Cutover phase 2 done in code (Claude, 2026-10-09): one collision world, core
z_bgcheck behind `CORE_COLLISION=1` in the usual Clean image (API v27,
.bss 10,080 B spare, audits clean). Human Clean runtime batch + speed vs C
open. Next Claude work: phase 3 (frame bank as AnimTaskQueue_AddLoadPlayerFrame,
common set, cutscene preload/pin). See PLAYER_MIGRATION.md "Phase 2".

Latest human ordering (2026-10-08): Field enemies, then Water Temple enemies,
obstacles and puzzles. Mandatory Player migration remains required, especially
for horseback Big Poes, Like Like capture and Dark Link; neither a proxy nor an
actor pack closes that work. Field is now in the usual Clean test disc with
four actor/six effect profiles, API25 and source-era placement. Target memory
and SH-2 audits pass; all 1,461 ISO files match staging. ISO 84,131,840 bytes,
SHA256 `b62a08869df52cc08072962baa4bff6c0efeb3451e5903099d2461d6d8428eda`;
.bss 0x06083400, 3,072 bytes below fixed SGL. Human accepts the shown adult Poe
defeat/soul dialogue; other era, bottle and population checks remain pending.
Water Temple work: 23 rooms, runtime scene 79, source scene 5; all 36 source
units compile in isolation (140,644 bytes unlinked text). Borrowed source-water
ownership and original controller action probes pass; five non-boss enemies have
sprite conversions/bakes (Like Like, Dark Link pending Player). ABI26 is
code-only in the Clean raw target; no temple pack is staged. Keep the
mounted ABI25 image intact. See [Field handoff](FIELD_ENEMIES_2026-10-08.md) and
[Water Temple status](WATER_TEMPLE_2026-10-08.md) for current evidence.

The earlier texture-baseline Clean image (2026-10-08) uses accepted mode-2 room textures:
[measurements and acceptance](TEXTURE_HALVING_2026-10-08.md). Code, 34 focused
host checks, full WSL target build and final ISO comparison pass. Human accepted
the look and reported better performance; screenshot VRAM 49%, CPU~ 79% is
one observation, not a paired benchmark. Clean defaults to mode 2; explicit 0
restores full density, and standalone/other variants still default to 0.
That baseline's SGL margin was 1,792 B;
the ISO is 83,494,912 B after three obsolete image-scene mesh pairs were removed.
Inventory behavior below remains included; this asset experiment does not
complete or defer mandatory Player migration.

Current requested work (2026-10-08): all Link inventory through source paths,
crosshair retained, bounded source first-person sprites permitted; Biggoron/
Mirror equipment and shield art/fallback repair. See
[inventory source audit](INVENTORY_SOURCE_AUDIT_2026-10-08.md) and current RECOMP_PLAN.
The first projectile/gear repair wave is implemented, host-tested and target-built.
All 346 host cases plus the actual source actor probe pass. The usual Clean
image includes API24 and regenerated gear/aim art; all 1,458 files match staging.
Main .bss ends at 0x06083900 (1,792 B spare); resident core is 510,184 B.
Both integer audits and all 388 room records pass. See the
[inventory handoff](INVENTORY_HANDOFF_2026-10-08.md). Human acceptance remains
open; C/proxy Player remains live.
Complete remaining inventory via mandatory real Player migration, not a permanent
expanded proxy. Hammer/lens/spells/bottles/trades/masks/beans remain incomplete.

Previous requested follow-up: water shore step-up and region-based Debug Level
Select, exposed below save options after Start. Source implemented; 119 host
checks and matching Clean build pass. Main .bss 0x06083740, 2,240 B spare;
both math audits and all 1,457 disc file comparisons pass. See [water/menu handoff](WATER_MENU_HANDOFF_2026-10-08.md).
Preserve the shore fix in Player cutover; human runtime checks remain open.

Immediate map fix (human, 2026-10-08): Level Select omitted major dungeons.
All 101 retail maps now register; 75 old IDs stay fixed and 26 append.
All 388 room rows bake and the matching Clean target builds. Source faces and complete collision
remain; optional subdivisions and texture density obey existing room limits.
Exact C collision allocations and SCENETAB metadata/portal storage preserve
global heap/actor capacities. Nine debug-only entries have no retail inputs.
Old core resources and idle music caches release before new native asset loads;
this removes the measured Ranch-to-Gohma allocation overlap. Prior all-map target main
.bss ends at 0x06083110 (3,824 B spare); core remains 508,560 B. Runtime acceptance
and allocator-fragmentation checks remain open.
Final combined host run: 184 checks, no skips. All 101 OOCs and 1,457 ISO files
pass validation/byte comparison; core and main math audits pass.
See [ALL_MAPS_HANDOFF_2026-10-08.md](ALL_MAPS_HANDOFF_2026-10-08.md).
This map task adds no actors and does not complete Player/collision migration.

Parallel enemy work (human, 2026-10-08): Astra owns W0a in
[ENEMY_ROLLOUT_PLAN.md](ENEMY_ROLLOUT_PLAN.md). Five source/design reviews are
resolved; fixed code packs, full NPC SPR2 preload/cel cache, roster/audio tools,
combat boundary and effect views are shared groundwork only. No actors imported.
Matching W0a host/target evidence and open runtime/content gates are in
[ENEMY_W0A_HANDOFF_2026-10-08.md](ENEMY_W0A_HANDOFF_2026-10-08.md). Actual boss-category
profiles alone are exempt, hazards retain geometry, original 20 missing enemy
scenes stay in scope. Grab/capture/gear enemies wait for real Player cutover.
Player remains the required migration endpoint, not a permanent expanded proxy.

Claude integration step 1 (2026-10-06): strict bank (uncertain clips strict) worst
scene 554,668 B; placed into real old allocations, worst pack fits. Two-pack
rollback does not fit (reload-from-disc rollback proposed). Frame-bank adapter,
region loader (both host-tested, isolated) and 5-region partition (2,514 B
main free in that historical layout) done; 110 collision call sites listed.
Remeasure combined retention/placement against the current W0a core before
accepting the partition; no old margin carries forward. Next: core collision API +
port non-Player callers, then resolved build. See PLAYER_MIGRATION.md.

Claude (2026-10-06, Codex out): proxies use real transformFlags + core carry path;
one frame-step owner; scene reset restores water + clears proxies; replacement
memory ~19.4 KB measured. Host tests pass; 2 tracked Fx cases open. Next: port
callers onto bg_core_shim, then real link. Nothing live yet.

Claude (2026-10-06): fixed frame-bank precision search (blame per channel)
and action-specific anchors. Worst scene 552,756 B strict / 531,876 B with
action context, vs old same-stage 553,142 B (LINKANIM + C collision). Fit
needs C collision callers moved to core bgcheck. Next: sections + loader.


Astra combined memory follow-up: real core+Player dependencies, libgcc and 521
source animation headers retain 659,244 B after temporary duplicate-owner removal.
Baseline is exactly 501,840 B like existing ELF; combined wide audit passes.
Core + two large Low RAM gaps is 3,884 B short before missing dependencies.
Selected design adds retired music/fairy cart reservations (24 KiB): five resident
regions totaling 679,936 B, 20,692 B unallocated before remaining hooks, skeletons,
frame backing and alignment. No heap shrink or C-Link-retirement memory credit.
Claude sized hooks + real skeletons: 8,884 B, ~11,808 B left (estimates).
Frame bank measured: 2.26 MB raw/age vs 423 KB bank; no fit. Shared-bank
prototype (trigger residency, FK-checked reduction): peak 1.24/1.01/0.91 MB at
0.5/1/2 world-unit anchor tolerance; still no fit. Packed bank v1 (real
bytes, C round trip, source weapon/shield/foot anchors, 0.5 units): resident
688,548 B, transition peak 737,644 B vs 423,472 B; no fit yet. Decide frame
reduction (8-bit angles, per-scene cutscene clips, half rate + morph), then
partition sections and add versioned
multi-region loading; fit requires a resolved link. See PLAYER_MIGRATION.md.
No live build, allocation change or runtime acceptance.

Replace handwritten C Link with real core/decomp Player. Required next
implementation priority, not a benchmark-dependent choice. Preserve all Saturn
adaptations, added functionality and Link fixes on top of source Player behavior.
Start with a code/test-backed behavior inventory and dependency/ownership map;
then migrate in stages while keeping Saturn rendering/backend and gameplay timing.
One authoritative Player/shared collision world is the endpoint; a query bridge
or larger proxy is insufficient. Preserve actor contact/rider/switch feedback.
Retire replaced C paths only after replacement runtime/human acceptance.
Detailed rules and acceptance: [RECOMP_PLAN.md](RECOMP_PLAN.md#mandatory-link-migration-next-step).

Review found the gallery bridge calls bg_dyna_set every core step, rebuilding
unchanged static triangles; it passes only Y rotation/uniform X scale and omits
water/camera data and rider feedback. Keep it temporary and avoid redundant
transforms without breaking rider history. Profile total collision/update cost
and memory to guide core optimization; neither implementation is presumed faster.
Migration staging started by Codex on `oot-core`, preserving latest main through
fast-forward. See [PLAYER_MIGRATION.md](PLAYER_MIGRATION.md) for the initial
behavior/test inventory, owner map and exact blockers. Real z_player_call,
z_player_lib and z_player are staged through the production fixups in an isolated
build directory. WSL syntax passes all three after source-scoped enum/Fx and
scaled rumble repairs. Two focused tests pass, including 102,000 actual-Fx32
rumble ticks matching source pulse timing. Claude (2026-10-06): last three Fx
range literals fixed (exact turn ratio, world-space hookshot reticle reach);
5 tests pass. `TARGET=1 check_player_migration.sh` compiles all three as
isolated SH-2 objects: 0 wide/soft-float helpers, 151,049 B vs 87,984 B carve
headroom (NO FIT, upper bound), 9 duplicate owners, 713 unresolved (521 anims,
144 Link assets, 2 tables, 46 engine functions). Follow-up GC/layout evidence
above now guides the five-region resident design and remaining dependency sizing
before actual section partitioning, loader integration and live owner retirement.
C remains the live owner; no live link, disc change or runtime acceptance.
Earlier checkpoints below retain their evidence and gaps, not scheduling priority.

Camera defaults / fixed sky curtain (2026-10-06, source only): Hyrule Field
(SCENE_SPOT00) enters overhead; other scenes enter regular follow. Scene-entry
placement resets pending orbit turns and heading. L+R+B now toggles only regular
and the accepted first overhead view; the three farther survey views are removed.
Z/B+Z eased quarter-turns remain in overhead. First-person/interior framing stays
separate. 94 executing camera/control host checks pass.
The gradient's VDP2 rows were already fixed. Field's dither curtain now follows
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


## Raised-camera turns (2026-10-06)

Z/B+Z reversed; 16-step 32-bit cubic smoothstep replaces snapping, with bounded
pending turns and resident cursor/UI tick. 93 WSL camera/control checks pass.
Claude's full Clean build at 10:33 includes camera edits; 304 B spare. ISO program,
core and all five Adult Link files match staging; original 672-poly mesh restored.
Gossip Stone messages were nonfatal warnings, not a proven build blocker.
Human turn-feel/audio/Adult Link acceptance remains open. This image was later
removed by the failed Ocarina rebuild boundary guard; see current blocker above.
The earlier 2,704 B margin was from mixed objects, not usable headroom.

## Wave 0 Fx32 (2026-10-05, Claude; Astra GO, build allowed)

Human request: every NPC/animal/non-boss enemy -> real decomp actor + baked
sprite, then dialogue/trigger/save/era/time hooks. Astra review: no new wide
math, so shared Fx narrows to 32-bit FIRST; actor imports wait for it. Then
per-scene actor packs, demo route child-first, C mesh enemies replaced by
decomp actors (gohma.c larva path kept). Ledger: 151 sprite_required.

Implemented, host-tested, target-built (runtime NOT run; human owns it):
- oot-core/include/fx.h: Fx = one s32 Q16.16, saturating +/-FX_MAX. Mul from
  16-bit halves, div by 32/32 remainder steps; Fx*int, Fx/int, int/Fx exact
  integer paths. Runtime mul/div out of line (OotFx_* in oot_math.cpp).
  No long long, dmuls.l/MACH:MACL product or 64/32 divider in Fx.
  -DFX_SAT_AUDIT host hook reports each saturating caller.
- oot_math.cpp: 32-bit isqrt/sqrtf, sin/cos via 32-bit turn product.
- fx_sq.h (prelude): SQ/SQXZ/SQXYZ return pending squares (scaled hypot and
  comparisons); every decomp `f32 ...Sq` is retyped FxSq (stored square,
  scaled terms, explicit-only conversion to Fx); OotFx_Det2/DotRatio2/
  DotRatio3 for coordinate cross/dot products; OotFx_ScaleWrap16 for
  RAD/DEG_TO_BINANG and Math_SinF/CosF (wrap like N64 s16 store);
  OotFx_Q15Normal for COLPOLY_GET_NORMAL; IS_ZERO exact for squares.
- Importer rewrites: fix_rand_ranges (Rand*n, n >= 32768 -> 32-bit helpers,
  same single draw), fix_cross_products (sys_math3d, 12 sites),
  fix_stored_squares, cylinder side quadratics (Math3D_CylVsLineSeg,
  z_collision_check) -> bounded closest-approach/half-chord roots,
  subdivLengthInv lookups -> divide by subdivLength, plane sign test,
  sys_matrix 1/65536 literal, En_Md path yaw, arrow/attention squares.
  import_report.txt lists FX RANGE literals (29 now; reviewed: factorial
  table >7! unused by imports, 1e38 sentinels map to max, sys_matrix
  32768 range checks harmless).
- Tests updated: test_core_bgcheck (saturation values; Fx32 rewrites in the
  differential), test_ocarina (one-word Fx), math_probe cases.

Evidence:
- math_probe: 460 values, 0 over tolerance.
- bgcheck_probe Kokiri (S1): 4,997 rays, 0 floor mismatches, polyNodes
  5052 = 5052, height error median 0, p99 0.29, max 2.4 units.
- bgcheck_probe Hyrule Field (SA): 34,961 rays, 0 floor mismatches,
  polyNodes 5723 = 5723, p99 0.57, max 4.7 units (steep far slopes).
- test_core_bgcheck: 3 pass; 3,190 Ranch/Kakariko contacts identical,
  wall square roots 27,476 -> 895. test_sprite_clock, test_core_sprites,
  test_core_views, test_core_dialogue, ocarina Saria test pass.
- Blob: _oot_core_end 0x027DDE90 (450,192 B of 589,824; was 523,056 B),
  OOTCORE.BIN 388,808 B. SH-2 audit: no soft-float, no 64-bit libgcc
  helpers, no divider registers, no dmul in Fx code.
- Usual Clean image rebuilt (`./build.sh --clean --quick OOT_CORE=1`,
  build/fx32-clean.log): .bss 0x06083570, 2,704 B below work area.

Astra review fixes (2026-10-06):
- Integer squares (ATTENTION_RANGES SQ(350) = 122500) no longer pass through
  saturated Fx: FxSq(int) stores the 32-bit isqrt root (OotFx_SqFromInt).
- Math3D_Vec3f_Cross -> OotFx_Cross3: one shared shift for all six products,
  uniform 2^-k scale when a component exceeds Fx (every caller normalizes or
  passes unit normals). (300,0,300) x (300,0,600): y < 0, normalized -1.
- tools/audit_oot_core_wide.py matches 1-3 underscore helper spellings
  (___divdi3), excludes mangled _Z names, and has --self-test positive and
  negative controls. Real blob: only the 28 integer-division dmul sites.
- tests/test_fx32.py: every attention range boundary (r-1 inside, r+1
  outside, exact root), 2^31 integer square, cross/normal checks, audit
  controls. Re-run: math 0/460, Kokiri+Field 0 floor mismatches, 3,190
  contacts, 17 focused tests OK; Clean .bss 0x06083570 (2,704 B spare),
  OOTCORE.BIN 389,084 B.

Human test 2026-10-06 (image built from mixed objects, see BUILD.md 78):
- "oc load failed f 0", no Ranch NPCs/Cuccos, ocarina dead, rocks not
  liftable: stale non-core ram_cart.o/scene_flow.o reused by my OOT_CORE=1
  quick build. makefile OOT_CORE stamp now forces full recompiles; full
  `./build.sh --clean OOT_CORE=1` rebuild (build/fix-full-clean.log).
- Adult Link looked strange: disc still held Grok's cut ADLTMESH.BIN
  (11,456 B, ~358 polys, staged 10-05 19:39; quick builds never rebake).
  Current tool bakes the original 672-poly mesh; full build restages it.
- Kakariko shooting gallery exterior walls never drawn (pre-existing): the
  building is decomp Bg_Spot01_Objects2 (params 4 gallery, 3 adult matoyab
  that spawns carpenter Sabooro by day), not room geometry. Not imported;
  decomp DynaPoly_SetBgActor had no bridge to C bg_dyna. DONE 2026-10-06
  (Astra GO: visuals + collision only, NPC scope unchanged): imported as a
  GENERIC_DRAW prop with object_spot01_matoya/matoyab (O180/O181.OOB; meshes
  Q18007 gallery, Q1800A/D/11 posters, Q18107 construction site). Object
  blobs now keep CollisionHeader/CollisionPoly/SurfaceType/Vec3s/BgCamInfo/
  WaterBox. API v22 `dyna_view` lists live DynaPoly actors; oot_core_host
  core_dyna_* converts each source mesh once (normals n/2 Q14, surface/
  ignore/conveyor info) into the cart heap, bg_dyna_register/set/enable each
  decomp step, removes on actor death, resets on scene change. Daytime
  En_Daiku_Kakariko child spawn fails (not imported), as intended.
  tests/test_core_dyna.py; full Clean build passes, .bss 272 B spare; both
  ELF audits 0 failing. Human runtime check of walls/roof/posters pending.

Human ruling 2026-10-06 (supersedes the blanket dmuls ban): native
dmuls.l/dmulu.l ALLOWED (speed wins), stored values 32-bit; software 64-bit
helpers and soft-float BANNED; approximation fine. Done:
- Fx multiply back to inline dmuls.l + xtrct (MACH range check saturates);
  Det2/Cross3/DotRatio mul_shr use dmulu.l. Blob 499,216 B (90 KB spare).
- Game C: all 26 ___divdi3 calls removed via shared/lib/collision/div32.h
  (div64s_approx with one exact remainder correction, muldiv_s32,
  muldiv64_s32; SH-2 one out-of-line copy, host fixtures static inline):
  kokiri_collision (floor/plane height, line/edge params, wall push, dyna
  carry), collide.c cap_cap (32-bit, 13-bit normalized operands), cutscene
  cues, navi cap, dungeon_puzzles, recomp project_attention/crawl_camera.
  Power-of-two int64 divides stay (GCC inlines them, no helper).
- Jo jo_memory_usage_percent soft-float replaced by an integer version in
  heap_profile.c.
- Audit: dmuls/dmulu informational; fails on helpers/soft-float/divider.
  Game ELF 0 failing (605 allowed multiplies), blob 0 failing.
- Tests: 131 collision/bgcheck/push/climb/navi/cutscene/fx32 OK; full 58-file
  run 783 tests, remaining 7 errors + 2 failures are other agents' in-flight
  API changes (scene_flow.h/kokiri_camera.h attribute mismatch,
  link_anim_skin, POINT/SPdis, forest_scene), not div32/Fx.
- Clean: .bss 0x06083480, 2,944 B spare.

Open (Wave 0 not closed):
1. Preserve the main ELF/blob helper audit during Player migration. Native
   dmuls/dmulu, including compiler-generated constant-division products, are
   allowed by the narrowed 2026-10-06 ruling. Do not replace them with slow
   split multiplies. Software-wide/soft-float helpers remain banned.
2. Pre-existing stale fixtures fail (not Fx): test_core_save,
   test_ocarina song-pattern/Sun's Song (time API changes elsewhere).
3. Runtime: human Kronos check of collision, NPC talk ranges, attention,
   Mido path, item drops before actor imports start.

Current follow-up: exit-refusal zone latch, 90-degree Z/B+Z turns in the first
raised camera, and Link-anchored Field fade/two-panel curtain are implemented.
114 host checks pass (controls/camera/routes/haze, including three Clean-input
checks). Clean passes (`build/field-orbit-fix.log`), .bss0x06083DA0, 608 B spare.
Disc payloads match staging; frame setup is size-optimized. Heap and actor
budgets remain preserved.
Kronos is closed. First raised camera has positive human feedback; higher views
still expose large ground holes. Runtime acceptance of new fixes is pending.
See RECOMP_PLAN.md for current verification and remaining work.

Earlier task (2026-10-05): Astra owns the square-retopology runtime comparison
and environment/time integration. See [RECOMP_PLAN.md](RECOMP_PLAN.md) for current
scope, [FIELD_SQUARE_RETOPO_STATUS.md](FIELD_SQUARE_RETOPO_STATUS.md) for the
split-loader fix and runtime evidence, and
[ENVIRONMENT_TIME_STATUS.md](ENVIRONMENT_TIME_STATUS.md) for source clock,
landmark/fog/sky requirements and unresolved exact-parity work. 184 boundary
walk completed; the resumed 256 run also completed both boundary walks and its
90-step checks (5.657/5.703 s). The central patch has positive human visual
acceptance; north/castle reports are outside it. Human now requests Clean
promotion, broader ground quads, persistent castle/ranch walls and dark horizon
bands. Selection is `field-square-184`; outer visual panels use 1280-unit cells
on original planes, central panels stay 184. Capacity sweep passes including owl:
1249 Field polygons, 1732 vertices, 331776/445432 bytes. Clean rebuild passes:
Latest haze follow-up: `build/field-haze-final.log`, .bss0x06083FF0, 16 B below SGL. Cached sky
helpers use Os/shared mixing; heap and actor capacities remain intact. 47 Field/
sky host checks pass; ISO Field/COL/OOC/program bytes match staging.
Human accepts the dark sky and now requests a world-space dither band. This is
built as one upright camera-following mesh quad at3200 units, before Field's
4000 distance mesh/4500 full fog. Normal world depth/pitch applies; zero texture
slots. Two haze plus twelve sky checks pass. Human appearance/occlusion pending.
Human owns runtime checks. No GUI fixtures.
See [ASTRA_HANDOFF_2026-10-05.md](ASTRA_HANDOFF_2026-10-05.md).
Core API 20/OOC room-layer time metadata passed a coordinated isolated rebuild;
do not mix old OOC data with the new core. Clock/Sun's Song/destination-layer,
natural nine-state dawn sequence and v13 saved counter/hatch host tests pass.
Combined v2 passed visible-GUI clock cadence (+200 daytime/+400 nighttime per
30 steps), separate sky-time hold, pause freeze and a natural-sequence day-counter
increment. Adult Hylian front and Master Sword HUD look correct. Latest v3 builds
with 5,216 B below SGL but is unrun; initial equipment cursor and targeted landmark
trace are its pending checks. Far landmark SORT_CEN depth-sum overflow is identified,
now avoided with landmark SORT_MIN; visibility/occlusion still needs human checks.
Castle entrance walls and the entire ranch enclosure are retained. Counter reload/hatching target
checks, held/Mirror equipment, original BGM/nature handoff, weather,
song-effect timing and full audio/cutscene environment parity remain open.

The isolated candidate has a 160-command cap for the same ten P3 children,
guard projection and boundary refinement. It adds 76800 texture bytes, no slots;
target margin 1632 B. Eleven identical baseline/candidate poses/input sequences
were captured in the visible configured Kronos GUI, Adult/All Items. Mapping
error and major missing-floor cases improve. Remaining small raster gaps and
the measured ~54% longer 90-step walk prevent calling it a complete performance
or all-route solution. Current camera host checks: 18 camera + 25 follow pass;
main Clean ELF links with 6160 B spare, ISO preserved. Existing collision/follow
wide math remains migration debt. RECOMP_PLAN.md holds the current queue;
TOMB_RAIDER_POLY_NOTES.md retains the evidence and rejected variants.
BURNING_RANGERS_POLY_NOTES.md: BR static study (small tile faces, no clip/split).

Historical (2026-10-04, tools; firing defects found 2026-10-08): Link's C-button tools import the real decomp
actors En_Arrow, En_Bom, En_Bom_Chu, En_Boom and Arms_Hook (importer SOURCES;
API v19 `tool`/`tool_view`; oot-core/src/bridge_items.cpp plays z_player's
spawn/release/carry/hookshot side). Bow + fire/ice/light arrows, bombs (carry,
C/A throw), Bombchu, boomerang (child), hookshot/longshot (pulls Link via the
source velocity) are wired in C (gameplay.c dispatch, first-person aim for
bow/hook/boomerang, ammo + magic 4/4/8 spent on spawn). C enemies take the tools'
source dmgFlags through C AT mirrors. This baseline omitted R_UPDATE_RATE
initialization, projectile Draw-side collisions and MISC boomerang views; its
build did not prove working firing. Pause equips Biggoron (DMG_SLASH_GIANT,
no shield), Mirror Shield, Kokiri/Iron/Hover boots (save v12 adds `boots`;
iron sinks/walks underwater, hover holds ~19 source frames). Visuals: 13
ITM*.SPR sheets from tools/build_item_sprites.py (pitch bands as poses,
explosion 8 frames); Biggoron/Mirror/boots are sprites at Link's hand/foot
joints, replacing the hand mesh. Clean target built: .bss 112 B below SGL (Os
on cold/state files paid ~6 KB); blob end 0x027EEB40. Not runtime-tested.
Open: mirror light reflection, hammer, lens, spells, beans, bottles' new
contents, bow/hookshot held in hand (first-person hides Link), chain is one
repeated link, explosion is a billboard, boomerang spin not baked.

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


Song of Time shortcut (human request, 2026-10-04): completing the known song as
Child Link now changes him to Adult Link and reloads the current scene at its
saved entrance, refreshing actors, model, camera and music. The 2026-10-06
follow-up below now toggles adult back to child too. Failed loading restores
the prior age and source scene;
equipment changes only after successful loading. This requested shortcut is
separate from unfinished source Temple sword time travel. Level Select explicitly
shows **ADULT LINK: NO/YES**, default No; R toggles before confirmed entry.
Follow-up also adds shared dithered NPC/Link/fairy ground shadows; see
ACTOR_SPRITE_ROLLOUT_PLAN.md. Combined focused batches pass 41 tests.
Final WSL Clean rebuild passes (build/character-shadow-build.log);
.bss ends 0x06083FE0 (32 bytes below SGL). Human runtime checks pending.


## Prior implementation handoff (2026-10-04)

Active regression batch: complete source inventory/quest display, current-region
map, Ocarina/song bridge, real Adult Link asset/era path, interior views, door
materials, tomb alpha and populated Cucco CPU cost. Human screenshots supersede
the older cleanup report below. See RECOMP_PLAN.md for current test/build status;
the 400-check Clean evidence below describes the committed baseline only.
This regression batch now has 578 distinct passing host cases, full asset
generation and a passing WSL Clean relink. Final .bss end 0x06083E80 leaves
384 B below SGL. Matched target audit passes new bounded paths (max audited
frame 172 B); existing core wide math remains migration debt. All 889 staged
payloads match the mastered ISO. No emulator/human acceptance. Detailed changes,
logs/hash and remaining song/adult/item gaps: PLAYER_REGRESSIONS_2026-10-04.md.

Baseline sprite/CPU/save/cleanup work is committed as 9d384cd. This continuation
is recorded in cf9ba39 and merged into main, now the active development branch.
The former main is preserved as oot-vslice-demo (7c8cc93); retired dev's unique
tip is tagged archive/dev-2026-10-04 (5b560ab), with dirty worktree files intact.
Historical checkpoint sections
below retain their original evidence and do not describe the current image.

Committed baseline evidence: 400 distinct host checks passed. Full WSL asset regeneration and the final
C-only Clean relink pass (`world-completion-build.log`, `world-completion-link.log`).
Usual game-clean.cue/.iso rebuilt; .bss ends 0x06083D70, 656 B below SGL.
Save state, write/preview scratch and draw-cache ownership use checked low-RAM
carves; boot initializes persistent state/cache before use. Virtual story banks
use IDs 1024+ and C-prefixed files, with no real-room overwrite. Staging and
budget checks pass; retired aliases removed. Runtime acceptance remains open.

**Earlier runtime report:** repeated `dosei_allocator_free(): Null pointer` at
startup/zone changes, about six dismissals; one Ranch NPC visible; generic doors
still unwired. Confirmed source regression: story_route_free directly frees six
optional sprite pointers without guards. SDK rejects NULL; host stubs incorrectly
accepted it. The baseline repaired story_route_free, emerald_story_free and
cutscene_actors_free: guard optional pointers, then clear ownership. Eleven
focused host checks pass, including 256 allocation combinations and repeated
cleanup. WSL Clean rebuild passes (`build/null-free-fix-build.log`); usual image,
.bss end 0x06081DE0 / 8,736 B spare for that prior build. Runtime confirmation pending.
Current continuation additionally rolls actual failed story/emerald loads back;
NULL/double-free stubs test partial loads, repeated cleanup and retry. Generic
handle doors/shutters now retain source gates and layers, with shared scripted
entrance forwarding. Unsupported routes remain blocked and named in
[WORLD_ROUTE_AUDIT.json](WORLD_ROUTE_AUDIT.json). All-map registration now covers
101 retail scenes; nine debug-only entries lack
retail source payloads. Full connectivity remains unfinished.
Save v11 preserves v2-v10 and adds source-scene flags, keys/items, bottles,
era/time and stable source resume identifiers. The mirror seeds saved scene flags
before actor initialization and restores equipment/quest/ocarina predicates.
Automatic talk and milk reward/textbox handshakes are bridged; source minigame,
ocarina and full inventory behavior remain incomplete.

Later same-room NPC spawns now discover sheets without repeating failed reads.
Packets are validated, hidden sprites do not consume visible slots, and reused
native NPC views clear old generic sprite identities. Existing L+R overlay shows
generic actor/missing-sheet/fallback-pose/slot counts. Dynamic preloading and full
resource closure and eight-slot/16-view limits remain open.
[ACTOR_COVERAGE.json](ACTOR_COVERAGE.json) records 429 profiles/110 scenes and
836 room layers; no scene ready. Forty-one offline horse clips are baked,
but gameplay horses remain unimported because their Fx actions add wide runtime
math and their anchors/mount logic need work. Packages total 910,945 B including
allocator terminators; largest live cel plus CLUT is 1,472 B. They are not staged.
Current Clean target verification passes; horse gameplay remains unfinished.
Follow [NEXT_CHAT_WORLD_COMPLETION.md](NEXT_CHAT_WORLD_COMPLETION.md).
Prior build success does not supersede the human failures.

Level Select All Items? defaults Off; A toggles the highlighted items or
Link age option (default Child). Applies only on Begin Play Test. All source quest bits include
the three stones/Emerald, medallions and songs; source inventory/owned gear,
20 hearts, capped ammo/magic/upgrades, 500 rupees, tokens and dungeon test keys
are included. No new story completion flags. Mutually exclusive slots use
upgraded/final variants; tools are wired (see top); hammer, lens, spells, beans
remain unfinished. Save v12 now 2,434 bytes (boots); three-digit wallet cache/HUD repaired.

Current permanent rule: all NPCs, animals, fairies and non-boss enemies use baked
sprites. Bosses explicitly exempt for now: preserve their models and complex
damage/puzzle hitboxes. Link remains separate. See
[ACTOR_SPRITE_ROLLOUT_PLAN.md](ACTOR_SPRITE_ROLLOUT_PLAN.md) for all scenes,
child/adult eras, layers, triggers, spawn chains and verification gates.

Prior sprite checkpoint (now 9d384cd) was implemented and Clean target-built:

- Ranch sprite lookup used ROM offsets against relinked compact objects. New
  `generic_sprites.json` names clips; make resolves `generic_sprites.h` from the
  freshly linked `obj_syms.ld`. Missing names fail the build. Current clips load
  first; absent optional clips retain a compatible sprite. No 3D fallback.
- Sprite object data keeps AnimationHeader lengths only; pose/joint/skeleton
  arrays become unused identity placeholders. Ingo blob 1,720 B; child Malon
  680 B. No runtime skin registry or staged N????.BIN/.SKN for this cast.
- Ranch bake now reserves 64 KiB actors and 32 KiB spare. Pixels 341,568 ->
  272,448 B, saving 67.5 KiB; textures + palettes 295,776 B. Full builds rebake
  Ranch before scene registration, so old generic room caches cannot bypass it.
- Fairies use textured wing/glow cels, one sprite per fairy; FAIRY.BIN and wing
  geometry/travel-yaw work removed. Four resident 32x32 RGB slots, nine source
  cels in the former unused cart gap; no image generation or drawn replacement
  wing art. Shared 32-bit view test rejects hidden sprites before uploads.
- NPC visibility no longer resets all actor/prop textures. Slots survive until
  room generation/reload; current forest all-placement bound 55,424 B/253 slots.
- Nightmare riders/horses, Saria bridge, owl and story Ganon/horse use SPR;
  staged character BIN/ANM/TRK/SKN removed. Bridge/static props stay geometry.
  Original models still exist only as offline bake sources for these characters.
- 36 focused host checks pass. WSL Clean passes (`build/ranch-sprite-build.log`);
  usual image rebuilt, .bss end 0x06081DC0 / 8,768 B margin. New cull target
  disassembly uses 32-bit instructions/helpers. No emulator launched; appearance,
  save/reload, conversations and measured FPS remain human-unaccepted.

Next: finish combined target/staging checks, review the generated coverage
ledger and close source conditions/resources, then import Ranch gameplay horses
through bounded 32-bit actions/anchors and convert remaining non-boss actors.
Same-room discovery is implemented; preloading complete reachable trigger sets
and eliminating capacity-driven omissions remain open. Existing core wide math,
scene vertex work and prop matrix reconstruction remain CPU migration work.
The old N64-address bug and missing actor reservation are proven code defects;
the user-reported full performance problem is not claimed resolved.

## Prior Mednafen repair checkpoint (Astra, 2026-10-03)

Latest human: sprite NPCs must do no skeleton/head work, fairy flyby still used
models, and saving fails in Mednafen. Palette repair is human-accepted; overall
CPU/VDP1 performance and the new sprite/save fixes still need runtime acceptance.
Human requested commit/push before sprite/CPU changes: completed as **11312ec**
on origin/oot-core. The subsequent Ranch/CPU changes below are now in 9d384cd.
Keep batched work and no intermediate human-test asks. Decomp retains the Saturn backend.

### Sprite-only NPC and Mednafen save batch (2026-10-03)

Historical implementation, now included in 9d384cd:

- `npc_draw.c`: removed C NPC models/skins, joint matrices, head/torso tracking,
  Saria greeting model exception, and missing-sheet 3D fallback. Fairy flyby
  loads SPR sheets and uploads the authored Navi cast independently of Link's
  save scene. Shopkeeper also loads only a sprite. Saria cue motion/talk keeps
  running with the idle sheet (wave/run poses intentionally approximate).
- Importer + `sprite_actor.h`/`bridge_npc.cpp`: current generic NPCs initialize
  only clip metadata; no skeleton header read, joint/morph allocation or frame
  pose decoding. A 32-bit Q8 clock preserves clip completion/action transitions,
  reverse playback and loop modes through the existing Fx ABI fields. Generic
  NPC Actor_Draw remains bypassed. Tracking/fidget/stagger work is removed for
  Ingo, Malon, Talon and cow; action functions, movement, collision and talk stay.
  Morph delays and joint-driven root stagger are intentionally omitted under
  the human's approximation rule. Malon can use object/clip sheet lookup without
  reading a skeleton to obtain a limb count. Sprite mode also applies to Debug
  source; only Clean has been target-built. The later baseline converts nightmare riders/owl; Ranch gameplay horses
  remain unimported.
- Corrected sprite slot failure sentinel: the VDP1 allocator returns 32-bit
  UINT_MAX, but sprite instances store 16-bit slots. Compare the narrowed field
  against UINT16_MAX; otherwise a full bank falsely succeeds and can index slot
  65535. Flyby mask/bank generation retries keep each placement's own cel slot.
- Mednafen save evidence: configured default `%f.%M%x`, nine hash-named `.bkr`
  files for successive Clean discs; two oldest contain active DOSEI0, newer
  ones are empty. This explains save loss across rebuilds. Restored latest
  active candidate `game-clean.7f402babb95acd27ace60606f8dddfd6.bkr` to the
  unhashed `sav/game-clean.bkr`, plus matching `.smpc`; no originals overwritten.
  SHA256 of source and copy:
  `536A8E12E74D5F68BE0EC0BCDC49E72C644196428059657F5E7F97C779E481F3`.
  `tools/launcher/mednafen-saves.ps1` preserves this default-lookup behavior for
  future launches without changing global config. Existing stable backups win;
  deleted slot headers and custom filename formats are respected.
- BIOS backup robustness: project-local SDK wrapper reserves 16 KB executable
  area at low-RAM offset 0xF1600 and 8,312 work bytes at 0xF5600; no heap/cart
  placement or mount-time format attempt. Reads on a mounted failing device
  return DEVICE_ERROR, not EMPTY. File select/save panel show concrete format,
  full, protection, verify or damage errors. Unmounted devices still permit
  explicitly unsaved play. These defects were found during review; they are
  not established causes of the user's report.

Verified: 85 host tests covering real clock functions, poisoned skeleton/table
pointers, sprite matching/failed upload sentinel, Navi bank ownership/retry,
save-device failures, save serialization/file select/cutscene skip, and launcher
save migration. WSL Clean build passes (`build/sprite-save-build.log`), main
.bss end 0x06082220 / 7,648 B margin. Usual `game-clean.cue/.iso` rebuilt.
Sprite clock target disassembly (`build/sprite-clock-disassembly.txt`) uses
32-bit shift/divide helpers only; no new wide arithmetic. Existing Fx storage
and other wide code remain migration debt. No emulator run, FPS measurement or
human acceptance of this batch. Next: human save/reload and NPC dialogue/visual
check, continue 32-bit core conversion/direct prop matrices/compact scene culling.

Sources: [Mednafen filename lookup](https://mednafen.github.io/documentation/fname_format.txt),
[Sega STN-52 workspace correction](https://docs.exodusemulator.com/Archives/SSDDV25/segahtml/info/hon/stn52.htm).
Older checkpoint sections below describe their then-current builds; this batch
supersedes their Saria 3D, Debug 3D and sprite pose-work exceptions.

### Current performance review (2026-10-03)

**New human directive:** no 64-bit runtime math or wide fallbacks. Approximation
is allowed; performance takes priority over 1:1 OoT fidelity. Preserve playable
collision, combat and story. This supersedes the review's proposed wide DIVU
fast path and earlier preferences for exact Fx arithmetic. Existing wide core
and backend math remains migration debt; it has NOT all been converted.

**First implementation batch:** `src/recomp_camera.c` now converts headings with
32-bit integer multiplication. Large component pairs scale down together before
Q16 conversion; in-range inputs are unchanged. No float or wide arithmetic in
the new runtime path. The proposed wide-divide patch was removed before build;
`fx.h` retains its pre-task implementation pending a genuine 32-bit replacement.
New actual-function host regression passes 362,433 input pairs: all signed-16
values against axes/edges, extreme signed-32 pairs and 100,000 random vectors.
It checks old valid conversion exactly and large-vector direction within one
binang. All 11 existing player-camera tests also pass. WSL Clean build passes:
`build/cpu-heading-build.log`; usual `game-clean.cue/.iso` rebuilt. Main .bss ends
at 0x060838b0, leaving 1,872 B before SGL (previous Ranch build: 96 B).
The matching `build/game-clean.elf` heading routine at 0x0601dd2c uses 32-bit
range checks/shifts and one slAtan call. Its old six software-double calls are
gone; __floatsidf/__muldf3/__fixdfsi are absent from this entire Clean image.
Other legacy wide arithmetic remains, including main __divdi3 and core Fx.
No emulator run or measured FPS gain. This heading change is now in 9d384cd.

Requested scope: review oot-core and its Saturn CPU/VDP1 backends, then propose
refactors. The review below records the pre-implementation evidence; current
implementation status is above. Other proposals remain unimplemented. Existing
Ranch/CPU changes remain intact. No emulator was launched.

**Current architecture:** `Fx` still stores 64 bits, but `fx.h:35` defaults to
16 fractional bits; the Q39.24 header and early checkpoints describe the older
format. Narrow multiplication already uses `dmuls.l`. The core ELF has no
software-float, `__divdi3` or `__muldi3` symbols. The C backend DOES execute
software-double helpers in the reviewed baseline (finding 1, now changed).
Link is still the C player plus the small
`bridge_player.cpp` proxy, not a running imported z_player. Kokiri NPC ownership
is disabled; Clean generic NPCs skip their 3D draw. The historical 12.8 ms Ingo
draw and old Q24 benchmarks must not be presented as current Clean timings.

#### Recommended refactors, in implementation order

1. **Remove software-double conversions from common heading math (CPU).**
   `src/recomp_camera.c:17` calls `slAtan(toFIXED(dz), toFIXED(dx))`; this SDK's
   macro multiplies by `65536.0`. Pre-fix `collide_heading` disassembly showed
   two each of `__floatsidf`, `__muldf3`, `__fixdfsi`: six helper calls
   per heading. Digital movement inlines them into `player_input_motion`; analog
   movement, collision/gameplay headings and NPC sprite facing share this path
   (`src/player_input.c:422`, `src/npc_sprite.c:31`). These files were already
   unchanged before this review; this is not caused by the Ranch repair.
   Use integer conversion for proven [-32768,32767] components; normalize both
   components together for larger deltas. Preserve existing /256 truncation,
   zero handling and angle quadrants. Do not shift negative signed integers or
   independently clamp components. Check target disassembly and heading tests.

2. **Replace wide core arithmetic with bounded 32-bit math (CPU; next).**
   The original direct 64/32 DIVU proposal is superseded by the human's rule.
   Existing `fx.h` normalization uses CLZ and variable 64-bit shifts even for
   small values. Replace storage and operations with 32-bit units/scales;
   approximate distance/normalization where necessary, without wide fallback.
   Audit squared-distance comparisons, collision plane products, reciprocal
   grid indexing, angle wrapping, sqrt and trig together: simply narrowing the
   existing raw type would corrupt ranges and structure layouts. Rebuild every
   scene/object blob when Fx layout changes. Gameplay viability, bounded error
   and target instruction cost matter; exact float-reference parity is not a
   requirement. Keep tests for floor presence, sword reach, signs and zero.

3. **Pass prop matrices directly to SGL (CPU, generic scenes).**
   `oot-core/src/oot_core_draw.cpp:208-223` decomposes each ordinary nonzero-scale
   generic draw matrix using four square roots, seven fixed divides and three
   atan2 calls on the non-gimbal path. `src/cutscene_actor.c:564-575` then builds
   the transform again with translate/rotate/scale. Extend the draw-item ABI
   with a packed Q16 affine matrix and adapt coordinates once at the backend.
   Preserve the established mesh Y flip, multiplication order, sorting and
   mirrored/nonuniform transforms. Compare vertices against the original matrix
   and the current path's valid positive-scale cases; test every rotation axis,
   translation, negative scales and parent/view composition in the same view.
   NPC sprites already bypass this path; count generic draw items
   before estimating its importance in any particular scene.

4. **Separate sprite animation state from unconsumed pose work (CPU; implemented).**
   The new sprite-only batch above removes skeleton initialization, frame pose
   decode, tracking and fidget work for the current generic cast. Clocks and
   action/talk/collision remain. The later human instruction explicitly permits
   omitting morph delays, body auto-turn and joint-driven root stagger; these
   are no longer parity requirements. Runtime dialogue/visual acceptance remains
   pending. Future imported sprite NPCs must use the same importer/backend path.

5. **Cull compact scene chunks before vertex processing (CPU and VDP1).**
   `src/kokiri_sgl.c:1508-1529` uses radial XZ object bounds and still calculates
   depth for the entire room point table. The polygon pass begins at :1546;
   submission at :1784 reduces `nbPolygon` but keeps the full `nbPoint`. Rejected
   polygons therefore do not remove all vertex work. Bake spatial chunks with
   compact/remapped point tables and conservative 3D bounds; reject whole chunks
   against the actual pitched camera frustum before depth/transform/submission.
   Keep enough chunk size to avoid excessive submission overhead. CPU vertex
   work can shrink directly; measure VDP1 command/pixel savings separately since
   SGL already rejects some faces. Gains depend on the visible scene.
   Actual staged Kokiri room 0 has 1,756 vertices and 1,475 polygons; room 1 has
   1,558 and 1,464. These are asset counts, not measured visible submissions.
   Keep current near-plane handling, winding, room/portal behavior, fog and floor
   coverage. The failed warp/subdivision experiment is not revived by this plan.

6. **Batch dirty VRAM writes safely and keep sprite slots stable (both).**
   `src/npc_sprite.c:40-55` changes CLUTs on sheet switches and copies a full cel
   on pose/direction changes. Generic slots are assigned by visible traversal
   `used++` (`src/oot_core_host.c:388`), so one disappearing actor can rebind later
   actors' slots and trigger avoidable copies. Map slots to stable actor identity
   with lifecycle/generation invalidation. Cull definitely invisible sprites
   before facing/cel upload, using conservative billboard bounds. Gather dirty
   cel and fog-palette writes (`src/kokiri_sgl.c:1747-1772`) and perform a bounded
   batch at a verified previous-draw completion point, or use separately owned
   buffers if their full VRAM budget fits. Do not add a wait per sprite or remove
   existing draw-end guards. Callback uploads can overlap a previous draw; this
   is a contention/ownership concern, not a newly demonstrated corruption bug.
   Sega documents CPU/VDP1 VRAM contention and recommends short burst transfers
   outside drawing: [VDP1 manual, VRAM access](https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p02_10.htm).
   Track changed bytes/CLUTs as well as command count; fewer commands alone do
   not prove that large overlapping sprites finish sooner.

7. **Crop individual sprite cels offline (transfer size and possible VDP1 gain).**
   `tools/build_npc_sprites.py:153-163` gives every pose/view a common rectangle.
   Current Ingo `G0C004.SPR` has 30 cels of 48x56; only 10.1% of their pixels are
   opaque on average. Offline per-cel bounds, with widths rounded to eight, retain
   27.2% of the original average rectangle area. A cropped-cel format could save
   about 72.8% of this sheet's raw cel bytes before metadata/alignment, while
   retaining its artwork. Store crop dimensions and placement/flip anchors;
   update the baker, loader, VRAM budget and projection together. This is not a
   measured fill-rate/FPS gain and is not representative of every sheet.

#### Other confirmed repeated work and constraints

- `oot_core_api.cpp:470-476` calculates actor culling distance; generated
  `z_actor.cpp:2493-2500` then computes XZ sqrt, XYZ distance and yaw BEFORE its
  update-culling gate. The per-actor profiler starts later and misses that
  framework work. Share/cache spatial results when all inputs are unchanged;
  do not simply suppress fields used by attention or other actors. Background
  collision already has spatial lists; profile stationary floor rays before
  adding another broadphase. Dynamic floors/water invalidate naive caches.
- Catch-up runs up to four C steps (`src/recomp.c:1680`) and up to three decomp
  updates (`src/oot_core_host.c:485`) per displayed frame. Each update calls
  OotCore_DrawActors and Message_Draw (`oot_core_api.cpp:531-532`). Only the last
  prop draw list is displayed. Eventually separate pure render extraction from
  simulation, keeping message reveal and actor Draw side effects at their proper
  cadence; dropping arbitrary Draw calls would break decomp behavior. Preserve
  the existing sword sweep/input latch/player-push frame-skip contract.
- Profiling is always active: `oot_core_views.cpp:355-377` surrounds each actor
  with two timer calls, conversion and an ID scan even in Clean. Keep coarse
  phase counters; make detailed profiling switchable, aggregate ticks before
  converting. `OotCore_MessageView` also rebuilds/hashes active text whenever
  talk/UI callers query it (:178); cache per message-state revision and make
  activity queries cheap. These are secondary savings, not measured bottlenecks.
- Link's faces deliberately use Dual_Plane (`tools/build_sgl_scene.py:241-245`):
  vertices animate but normals remain in bind pose. Posed normals could restore
  the original single-sided materials and remove hidden-face VDP1 work, at extra
  CPU cost. Benchmark that tradeoff; changing the flag alone opens body holes.
  Current model has 385 vertices, 704 all-gear polygons and at most 520 selected
  polygons; the generated 591-polygon visible buffer is capacity, not live count.
- Existing core .text = 342,252 B, .data = 48,712 B, .bss = 69,312 B. Its linked
  Fx helpers have 109 local bodies totaling 18,590 B; consider shared cold
  fallbacks while keeping common fast operations inline. These are static size
  facts, not dynamic call counts or proof of cache misses. Broad -O2 or moving
  the whole blob to work RAM is not justified: the reviewed Ranch Clean build
  had only 96 B below SGL (heading batch now 1,872 B). Historical cart-vs-low-WRAM microbench results did
  not show a placement win; remeasure before changing memory architecture.

#### Measurement and acceptance needed for implementation

Use the same Clean build, scene, camera position/angle and actor state for each
comparison; include Kokiri and Ranch plus movement/turning, 15/30 FPS catch-up
and a prop-heavy room. No intermediate human run is requested by this review.
Existing `OC` is the LAST decomp step, not the frame's aggregate; add a step count
and sum per displayed frame, plus collision/framework/update/draw extraction
totals. Keep master CPU work, engine/sync time, uploaded bytes and submitted
vertices/commands distinct. `CPU~` measures callback share, not PC utilization.
SYNC includes VBlank/engine work; COPR sampled after sync is not a VDP1 busy
measurement (`src/frame_timer.h`). Measure draw completion for the matching
command list during the wait before calling the frame VDP1-bound. FRT samples
must stay less than its ~293 ms wrap interval apart; loading stalls need a
different measure. No FPS improvement or CPU/VDP1 dominance is established yet.

### Ranch visibility and CPU follow-up (after 11312ec)

- Two confirmed visibility blockers in oot_core_host.c: load_meshes ran before
  Actor_UpdateAll spawned the room list, and sprite matching compared the baked
  skeleton count directly to SkelAnime's count including root translation.
  Assets now load after the first actual decomp update and after room changes;
  Ingo's 19 baked limbs correctly match 20 SkelAnime joints.
- Sheet allocation now includes Jo's NUL byte (SPR1 lengths are four-byte aligned,
  so the old length-only allocation could overwrite the next heap header).
  Generic VRAM reserves only spawned instances, up to eight, instead of eight
  largest cels even for one Ingo. No forced spawns/story-flag bypasses; horses
  at that checkpoint still required actor import and a Skin baker. The current
  continuation has offline Skin packages; runtime horse import remains open.
- CPU: skipped unused C head/torso tracking for sprite NPCs; retained Saria's
  3D greeting. Moved room/Link PMOD normalization into mesh_load, removing the
  every-draw scan over those attribute tables. Native/transient callers keep
  their guard; fog mode switches preserve flat/texture transparency rules.
- L+R one-second overlay now includes MS (frame incl sync), M (movement), G
  (scene draw), L (Link draw), OC (last decomp step), all integer milliseconds.
  CPU~ is callback share, not PC utilization. Overall Mednafen performance has
  not been measured/declared fixed; absolute timings can separate CPU work from
  frame waiting in the next human batch. No intermediate test request.
- Two host lifecycle/render regressions plus four graphics tests pass. Deferred
  spawn, skipped steps, room/scene changes, root-joint match, rejection of wrong
  clips/skeletons, NUL capacity and instance slot count exercised. WSL Clean
  build passes: log build/mednafen-ranch-cpu-build.log, .bss 0x06083fa0 (96 B margin).
  First attempt exceeded the boundary by 256 B; Os on cold clip/scroll loading
  recovered space without reducing heap or SGL budgets. Usual image rebuilt.
  Ranch/CPU runtime acceptance remains pending. Later same-room discovery was
  absent at this checkpoint; the current continuation implements it, while
  trigger preloading and complete resource budgets remain unfinished.

### Accepted palette/CD checkpoint

Palette repair built in usual game-clean.cue/.iso; historical log
`build/mednafen-clut-build.log`, 96 bytes high-WRAM margin. Graphics human-accepted.
Confirmed backend defect: CLUT addresses require **32-byte boundaries**, not
eight-byte boundaries despite CMDCOLR's address/8 encoding. Sega VDP1 manual 6.4:
https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p06_40.htm
Link's current pixel blob is 8912 bytes (16 modulo 32). The old loader placed
all Link CLUTs halfway across a hardware boundary; that offset propagated into
room banks. Simulating the hardware boundary against the actual S4R0 data
reproduces the screenshot's noisy curtains/walls/floor. Correct source and
converted textures are clean. Offline comparison artifacts (ignored build dir):
`house-texture-comparison.png` and `house-clut-address.png` (correct, OR hypothesis,
hardware-boundary hypothesis from left to right; right matches reported defect).
This explains why validating bytes at the requested CPU pointer did not catch it.

`kokiri_sgl.c` now pads every CLUT allocation to an absolute 32-byte boundary:
mesh_load, actor/NPC tile upload and streamed Field palettes. All capacity checks
count padding; offline tile/bank/Field/panorama budgets follow the same rule.
Four graphics backend tests, six VRAM budget tests and eight Field streaming
tests pass. Actual upload functions tested at all eight-byte starting alignments,
all 16 palette colours via hardware address decoding, disk/cache and failure paths.
Negative control: both palette upload tests reject the old eight-byte alignment.
No asset replacement or decomp logic rewrite. Human confirms this repair checks out.

Earlier graphics batch (mednafen-graphics-build.log, then 160 bytes margin):
- Black fade previously subtracted alpha from RGB. Actual house bank at FADE 100:
  59.91% pixels clipped black. VDP2 alpha blend against black line-colour screen
  preserves dark detail (under 2% black even quantized back to 5 bits). Sky table
  scales proportionally. Gray/white flashes retain prior additive path.
  Reserves VDP2 word 0x7f400 (after 512 back-colour entries), CRAM entry 2047.
  Line-colour insertion: https://www.infochunk.com/saturn/segahtml_en/hard/intr/hon/p03_40.htm
- Initial 4bpp actor/NPC upload padded pixels to 8 bytes. This was insufficient;
  superseded by the 32-byte fix above (also covers odd-height SPR textures).
- Untextured faces normalize CMDPMOD colour mode to 0 with ECD/SPD set. Resident
  texture moves adjust only textured CL16Look colours, not flat RGB values.
  Command rules: https://www.infochunk.com/saturn/segahtml_en/hard/vdp1/hon/p09_10.htm
- Host regressions exercise actual upload/fade functions and baked house pixels.
  A host harness name clash caused test.exe's Windows assertion popup; fixed the
  harness, tests now fail via normal exit status without interactive CRT abort.
- Ruled out a tempting sprite-command lead: sprNoflip|FUNC_Sprite looks like
  reserved command 3, but SGL _sbMakeSprite masks/replaces the low nibble with 1.
  Do not change sprite direction flags based on that source expression alone.

Full decomp remains the goal. The current review and repair status above override
historical next-session queues below. Earlier reports covered VDP1 corruption,
startup delay, missing nightmare actors, Navi OOM/skipped shots and house exit.
Opening shots now complete and the palette repair has human graphics acceptance;
Navi room-load pauses, late music and house-exit verification remain open.
Historical SGL SP 0723 / PR 0604, END 1 (house) / 3 (nightmare/forest)
are plausible; they did not diagnose this palette-address bug. Fade now brighter.
Human explicitly confirms menu before music no longer crashes (earlier PAUSEFNT.BIN).
Earlier house exit reported CS4.BIN then S1.OOC CD failures; no explicit acceptance
for that path yet. Implemented CD ownership fix:
fs_low.c wraps Jo GFS open/load/read with music_yield_cd; cancel read-ahead using
NwStop, resume on next service with seek to consumed offset. Close cancels too.
Host mock-server regression passes interrupted load/resume and failure paths.
Sega manual: https://www.infochunk.com/saturn/segahtml_en/prgg/prg1/file/hon/p08_14.htm
NwCdRead remains active until consumption or NwStop; another request cannot
assume the drive is idle simply because music_service returned.
Baseline advanced externally to 8874db2 during investigation; its sprite work
is preserved. 11312ec contains Astra's accepted Mednafen repair batch; subsequent
Ranch/CPU implementation is described separately above.

- `heap_profile.c`: reproduced wasted free-block capacity; SDK reuse kept a whole
  large hole for a tiny allocation. Split unused tails, merge adjacent free holes
  before retrying a failed allocation. SDK reduction alone only retracts tails.
  Seven host allocator tests pass, including the two new pressure cases.
- `npc_draw.c`: Clean loads sprite first and skips BIN/ANM/TRK/SKN for those NPCs;
  That checkpoint retained Saria/3D fallbacks; the current sprite-only batch removes both.
- `kokiri_sgl.c`: Navi pool/maps stay resident, but ten room meshes no longer do
  (737,384 bytes saved in current assets). Bulk scratch load at shot boundary.
  This trades bounded room-change CD reads for lower peak heap use.
- `music.c/.h`, `main.c`: title PCM uses existing idle cart scratch for a whole
  file read. Generic boot fallback reads multi-sector chunks. Scratch is never
  retained or freed by music. Background swaps now yield read-ahead to Jo loads.
- Graphics correction: `cutscene_start` explicitly loads bank 4 for moving
  Link-house cameras; `kokiri_scene_draw` renders this as VDP1 panorama geometry.
  Earlier NBG1 diagnosis did not apply to the reported opening shot.
  Mesh upload now verifies CLUT words in actual VRAM;
  SPCTL/PRISA/EDSR readout now draws last on all screens, Clean included:
  hold L+R one second to toggle; release before toggling again; starts hidden.
  Human confirms toggle visible. Correction: SPCTL/PRISA hardware reads are invalid
  (write-only); their constant zeros did not diagnose corruption. New SGL SP/PR
  reads SDK shadow at GBR+416/+432; END reads EDSR. Intended settings only, not
  proof of hardware state. Verified offsets in LIBSGL slInitScroll/slSpriteColMode.
  Sega register rule: https://www.infochunk.com/saturn/segahtml_en/hard/vdp2/hon/p15_20.htm
  Register audit found two real write-only-read bugs: recomp_vblank's TVMD &= mask
  discarded display/mode bits, and pause saved invalid cycle-register reads.
  New sgl_registers.h reads this SDK's shadow. TVMD preserves shadow bits;
  pause uses slScrCycleSet for both shadow/hardware and restores saved cycles.
  Visual impact still needs Mednafen testing; do not call corruption fixed yet.
  Previous cutscene-only readout was not visible in human's Clean test. Palette files
  being correct offline did not establish that runtime VRAM or commands were.
- Historical WSL Clean target build passed with CD ownership and register fixes;
  high-WRAM margin 576 bytes. Log: build/mednafen-cd-build.log;
  superseded by latest build at top. Menu-before-music is now human-accepted;
  other remaining symptoms stay open. No intermediate human-test requests.
  Missing riders and house-exit crash are not independently root-caused yet.

The game plan was restored on this branch as a concise full-game status
document. Its current name is `RECOMP_PLAN.md` after the 2026-10-05 naming change.

## Context
Hand-port 1 system at time -> guess behavior, bugs pile up (BUG log long). zeldaret/oot at
D:\Workspace-Claude\game-decomps\n64\oot already extracted (ntsc-1.2) + built. 456 actor .c.
Want: compile REAL decomp game code for SH-2 in bulk, convert float in bulk, convert all music
in bulk. Our Saturn renderer/audio stay as backend. 4 MB cart required -> code room exist.

## Hard truths (must design around)
- f32 everywhere (`typedef float f32` ultratypes.h:24). SH-2 no FPU. Soft-float = ~10x slow. Not ship.
- Fixed 16.16 overflow: OoT pos up to ±~10000 units, distSq overflow fast. Blind swap break math.
- Actors draw via N64 Gfx display lists (gSPDisplayList, matrices). Need shim, not VDP1 native.
- RAM: OoT code ~1 MB + overlays. Fit cart if overlays load per scene like N64.

## Status — Phase 0 (2026-10-02)
Code in place (host-verified, target compile-verified; runtime numbers pending human run):
- `tools/oot_core_import.py` mirrors decomp `include/`+`src/` headers and listed sources into
  `build/oot-core/decomp/` (`.c` -> `.cpp`). Mechanical fixups only, counted in
  `build/oot-core/import_report.txt`: float literals -> `FXL()`, MtxF/`_words`/CamParamData
  anonymous aggregates named, MIN/MAX/ABS/CLAMP -> `OOT_SEL`, xstdio long double.
- `oot-core/include/oot_prelude.h` (force-included): `float`/`double` -> `Fx`, C++ keyword renames
  (`this` etc.), `OOT_SEL` mixed-type ternary. `oot-core/shim/`: assert.h, math.h.
- `oot-core/include/fx.h`: **Fx = int64, Q39.24** (not 32-bit Q16.16). Reasons found by probe:
  decomp builds floats past s16 (`Rand_ZeroOne()*0xFFFF`, distSq ~1e8) -> 32-bit saturates;
  16 frac bits lose 6% on reciprocals (Math3D_DefPlane normal). Mul fast path 1 dmuls when both
  fit 32 bits, 2 when one does. All ops constexpr. (Phase 1: GCC 9 still emits ctors for some
  file-scope tables, so the blob runs its own ctor table from `OotCoreEntry.init`.)
- Replaced (float bit tricks / libc): `oot-core/src/oot_math.cpp` (sqrtf isqrt64, sinf/cosf Q30
  poly, floor/round...), `oot_rand.cpp` (qrand same LCG, mantissa -> exact Fx).
  NOTE: N64 `sintable` samples i*pi/(2*1023); do not interpolate it as /1024.
- Compiles for SH-2 (sh2eb-elf-g++ 14.3, linked by Jo gcc 9.3), **zero soft-float calls**:
  z_lib, sys_math, sys_math_atan, sys_math3d, math64, sins/coss, **z_actor, z_collision_check,
  z_bgcheck, z_en_item00, En_Kusa** (~240 KB text). Also syntax-clean: z_player, z_camera.
- Host probe `oot-core/tests/run_host_probe.sh`: 458 values (sin/cos/sqrt/atan2/dist/plane/
  SmoothStep/Approach/StepTo/Rand) Fx vs real float, **0 over tolerance, worst 0.017%**.
- Target: `./build.sh OOT_CORE=1` builds `OOTCORE.BIN` (Phase 0: 10.6 KB), linked at the
  cached cart alias (now 0x027C0000, carve RAM_CART_OOTCORE), loaded + cache-purged at boot, called via
  its entry table. Debug panel rows 13-14 show ns/call (ma dv ss / ds sn at). Work RAM untouched
  by decomp code (standard image 6,832 B spare). Default/Clean builds unchanged (flag off).
  This blob is the Phase 1 pattern: decomp code lives in the cart, not work RAM.

## Status — Phase 1 (2026-10-02): steps 2-3 linked, not run
- Carve 256 KB at 0x027C0000 (`RAM_CART_OOTCORE_BYTES` 0x40000, `RAM_CART_FIXED_BYTES` 0xC2400,
  makefile `OOT_CORE_LOAD_ADDR`/`OOT_CORE_MAX_BYTES`). Blob compiled **-Os**: 203 KB in carve
  (OOTCORE.BIN 170 KB; -O2 was 425 KB). 0 soft-float symbols. Standard image 6,832 B spare.
- Decomp file list lives ONLY in `tools/oot_core_import.py` SOURCES; importer writes
  `build/oot-core/sources.mk`, makefile includes it. Linked now: z_actor, z_collision_check,
  z_bgcheck, z_en_item00, En_Kusa + batch 1/2 leaf systems: sys_matrix, z_skin_matrix,
  TwoHeadArena, z_lights, z_eff_ss_dead, z_bg_collect, z_bg_item, z_inventory, z_rcp,
  lookathil, mtxutil, z_effect, z_effect_soft_sprite(+old_init), z_eff_blure/spark/shield_particle,
  z_malloc, __osMalloc_n64.
- `oot_core_roots.cpp`: pointer table that keeps Actor_InitContext/UpdateAll/DrawAll/Spawn,
  BgCheck_Allocate, CollisionCheck_AT/OC, En_Kusa/En_Item00 profiles alive under gc. Step 4
  replaces it with the real API.
- Bridges (`oot-core/src/`): `bridge_tables.cpp` actor + effect-ss overlay tables built from
  the decomp table headers, all entries internal, **weak profiles** (import a file = registered;
  not imported = NULL profile, spawn must check). `bridge_play.cpp` REAL/HOST/STUB tagged:
  Play_GetCamera/ActiveCamId real; Item_Give, Health_ChangeBy, sfx -> `OotCoreHost`
  (`oot-core/include/oot_core_host.h`, global `gOotCoreHost`, not wired yet); Object_* = always
  loaded; Overlay_Load/Fault/os*/Player_* (InCsMode, ExplosiveHeld, ReleaseLockOn)/Magic_Reset/
  GetItem_Draw/Camera_RequestMode stubs. `bridge_assets.cpp`: 41 one-word placeholder asset
  symbols (gameplay_keep DLs/textures, object_kusa DLs) = draw-shim keys. `bridge_libc.cpp`.
- gSaveContext and gSegments are defined in bridge_play (zeroed). C side must fill what
  actors read (e.g. save inventory) before step 5.
- **Step 4/5 hazard:** Actor_UpdateAll and most actors read GET_PLAYER(play). Our Link is C,
  so step 4 needs a proxy Player actor in the PLAYER category, synced from C Link each frame.

## Status — Phase 1 step 4 (2026-10-02): built, runtime pending
- Kronos fix: Kronos fetched code only from 0x020xxxxx in CS0 -> blob hung after SEGA logo.
  `build/kronos-fix/kronos.exe` (BUILD.md 26). Boot now reaches title (human, 2026-10-02).
- API `oot-core/include/oot_core_api.h` (entry v3): init(host), play_bytes, play_init(block,
  scene, colHeader, player pos/yaw), set_player, update, draw (no-op until Phase 2), spawn
  (refuses non-imported ids), actor_count. `oot-core/src/oot_core_api.cpp` follows z_play
  Play_Init/Play_Update order for systems we have (lights, effects, effect-ss, colchk,
  bgcheck, actor ctx; AT/OC/Damage/Clear, Actor_UpdateAll, Effect/EffectSs_UpdateAll).
  gRegEditor now points at a real RegEditor (REG macros deref it).
- Player proxy `oot-core/src/bridge_player.cpp`: Player_Profile with real header, update copies
  C Link feet pos/yaw. Focus height 40 is APPROXIMATE. Yaw convention C vs OoT not verified.
- Play block (PlayState 78 KB + THA 192 KB + ZeldaArena 128 KB) in low work RAM carve
  RAM_LOW_OOTPLAY (0x71500, 0x64000; OOT_CORE builds only).
- Scene collision: importer SCENE_COLLISION cuts the CollisionHeader + arrays verbatim out of
  extracted `spot04_scene.c` -> `SPT04COL.BIN` (34 KB, 1692 polys) linked at 0x02780000
  (`oot-core/scenecol.ld`, carve RAM_CART_SCENECOL 256 KB before OOTCORE; OOTCORE address
  unchanged). Passed to BgCheck_Allocate.
- Host `src/oot_core_host.c`: boot loads both blobs, init, bench. `oot_core_frame()` after
  gameplay_step (30 Hz): in Kokiri Forest only, play_init on entry, set_player, update on 2 of
  every 3 steps (decomp = 20 Hz). Debug row 15: `oc p<playing> pl pr mi` actor counts.
  Expected in Kokiri: `oc p1 pl1 pr0 mi0`. Host callbacks still NULL.
- Next = step 5: spawn En_Kusa from Kokiri's room actor list, wire OotCoreHost (sfx,
  give_item, health) to action_audio/save, hide the matching world_props grass.

**Gate numbers (human, Kronos kronos-fix, Debug, -Os, blob in cart) 2026-10-02:** ns/call
ma 8582, dv 20901, ss 15864, ds 59799, sn 49818, at 28630. ~240 cycles for one Fx mul-add:
far too slow for bulk actors. Unknown split: cart (A-bus) code fetch / Kronos timing vs Fx
cost. Next: rerun the same bench from work RAM (low WRAM) to separate them before step 4.

Open / next:
- Human: run OOT_CORE=1 Debug build, read rows 13-14 (gate numbers). See NEXT SESSION below.
  Blob is -Os now: numbers from this build supersede any earlier -O2 reading.
- ROM data holding IEEE floats (CutsceneCameraPoint.viewAngle, some cutscene cmds) must be
  converted to Fx offline when that data is loaded.
- Asset headers come from `extracted/ntsc-1.2`; decomp `build/` only has ntsc-1.1 objects.
- SaturnMath++ (MIT, github robertoduarte/SaturnMathPP, clone ../../SaturnMathPP @8bdc355) is
  32-bit-only fixed point (16.16/24.8/8.24) -> cannot hold decomp floats; NOT the Fx type.
  Borrowed: its SH-2 divider register pattern -> `fx_div` hardware path when |quotient| < 2^30
  in Q24 (else libgcc __divdi3). Target-only; runtime unverified. Not interrupt-safe if an ISR
  uses the divider. Candidates later: its trig/atan2 LUTs if bench shows sinf/atan slow;
  Vector/Matrix/Frustum for Saturn-side renderer/draw shim (needs C++23).
- Work RAM: solved by the OOTCORE.BIN cart blob (carve 256 KB at 0x027C0000, 203 KB used).
  Grow it (src/ram_cart.h OOTCORE + FIXED bytes, makefile LOAD_ADDR/MAX_BYTES together; ram_cart.c
  checks the address) as actors are added. Each 64 KB taken shrinks bank-2 jo_malloc space.

## ALL SCENES (2026-10-02, human request "create every map and room, add to level select")
Build only, runtime NOT checked. Level select (title secret menu) now cycles 75 scenes
(11 slice + 64 generic, ids 11..74, names from SceneId). Pipeline: tools/build_all_scenes.py
(generic mode: segments 06-0D fallback = black texture/empty DL, room G_MTX ignored, G_BRANCH_Z
walked: all APPROXIMATE) -> build_scene_table.py _extra_scenes (caps filter) -> build_room_scene
copies banks. Generic scenes: save id SAVE_SCENE_COUNT+n (no persistent flags), doors between
registered scenes resolve from ROM exits, En_Door/other room transitions skipped (rooms only via
level select), image rooms use the shop RGB backdrop path (multi-bg: first picture only),
no actors, Kokiri music/sfx defaults. Not registered (26): see build/all-scenes/registered.json:
collision over 2321 tris (Forest/Fire/Spirit Temple, Ice Cavern, Ganon's Tower/Castle, GTG,
Ganon's Castle, hakasitarelay), small cap overflows (pixels/tiles/verts: Dodongo, Jabu, Water,
Shadow rooms, Barinade, Zora's/Lake/Gerudo/Desert/Lon Lon/Death Mountain/Kakariko field?,
etc.), moribossroom/hiral_demo converter errors.
Area music (2026-10-02): scene header seqId per scene (scene_entry_t.seq). Generic scenes play a
songs.json route or a disc bank M<seq>.HDR/.PCM/.LVL (tools/build_area_music.py, runtime
src/music_area.c, tables in jo heap). All 17 baked (converter now: channel io ports, delay1, notes before instr skipped). Effects omitted (build_title_audio OMITTED): combfilter, reverbidx, env, releaserate. Slice scenes keep their
hand music. Work RAM spare (Debug) 304 B. Next: raise caps (RAM cost) to admit the
near-misses; multi-bg camera selection; per-scene music; En_Door room switches.

## HANDOFF TO ASTRA (Claude, 2026-10-03, branch oot-core)
Committed+pushed 507dbc3: step A (grass back; cause = stale S1.OOC after carve move, makefile
addr.stamp + host blob guard), sword proxy fixes, FRAME-SKIP RULE, tests/run_bgcheck_probe.sh.
UNCOMMITTED (sprite NPCs, human loves them, Kronos PASS Kokiri; Lon Lon OOM fix built, untested):
- tools/build_npc_sprites.py (new): bakes NPC00-15.SPR (C NPCs) and --generic-only G*.SPR +
  build/oot-core/generic_sprites.h (decomp NPCs). tools/build_npc_models.py build(full=True).
- src/npc_sprite.c/.h (new, Clean only via makefile CLEAN_TEST): shared sprite draw.
- src/npc_draw.c: C NPC sprites, draw range 1500. The later 9d384cd baseline also converts Saria greeting and fairy flyby.
- src/oot_core_host.c: decomp NPC sprites (Clean): sheets for spawned NPC objects only,
  85% heap guard, 8 slots; set_flags(OOT_CORE_FLAG_NPC_SPRITES).
- Blob API v16 (oot_core_api.h/.cpp, oot_core_views.cpp, oot_core_draw.cpp): set_flags,
  NPC view object/limbs/anim; generic NPC Actor_Draw skipped when the flag is on.
- build.sh: sprite bake steps (C NPCs after build_npc_models; generic after build_core_skins).
- BUILD.md gotchas 42 (CRLF from Windows python into build.sh) and 43 (SGL sprHflip typo).
At this checkpoint Debug kept 3D NPCs; current source removes that fallback (Debug build unverified). Open: horses (import
En_Horse_Link_Child/En_Horse_Normal + Skin-limb baker), pitch row for above/below views,
Debug RAM (step E), roadmap step B now mostly replaced by sprites. Details: NPC SPRITES below.

## Historical checkpoint (2026-10-03, commit 736982c + docs; current handoff above)
Human goal: ALL NPCs in EVERY zone, ALL dialogue, spawn/talk/events checked against
save flags and triggers exactly like OoT. Must work in BULK for all actors (importer
and library level, no per-actor hand work) and stay fast, or the game is unplayable.
Human rules this chat: caveman talk; big batches, one Kronos test per batch; never leave
the playable game worse (the fast C slice is the baseline: targeting, talk, combat).
SATURN CUTS ALLOWED (human 2026-10-03). Must keep: the game functions, combat works,
story progresses (right NPCs/events/text by save state, flags, triggers). Everything
else may be cut or simplified for speed and memory:
- animation: lower rate, fewer frames, no head/torso turns, no limb callbacks, baked or
  simplified clips, LOD (far actors static or hidden);
- textures: flat colours, smaller tiles, shared palettes, faces only where it matters;
- assets streamed per scene/room from disc into the 4 MB cart (load at room change,
  never mid-play while CD-DA music plays);
- fewer simultaneous actors drawn, simpler effects, no 1:1 RDP features.
Rule: never hand a system to the decomp if it is slower or works worse than the C
version it replaces. Measure on the debug rows first.

Historical runtime snapshot (human Kronos, Debug, 2026-10-03; before the grass,
sprite and palette repairs below, not the current blocker list):
- Kokiri: C NPCs/Mido/signs/wonder spots again (oot_core_owns_kokiri_npcs() false),
  decomp = grass + drops only. C talk works. REGRESSION: decomp grass no longer exists
  after the FX_FRAC 24->16 change (suspect EnKusa_SnapToFloor -> BgCheck raycast fails
  -> Actor_Kill). The Kokiri boy never blocked the bridge exit in the C game (only Mido does):
  not a regression; the real En_Ko blocker comes back when Kokiri moves to the decomp (G).
- Lon Lon (generic scene): decomp runs (p1). Only Ingo spawned (others: real spawn
  flags). Ingo update 1.0 ms; decomp draw phase 12.8 ms; Ingo invisible (VRAM 99%:
  skin texture upload skipped). Buildings cannot be entered in ANY non-Kokiri map.
- Debug rows: 15 `oc p pl pr mi`, 16 `ou` total + talk/msg/npc/colliders/draw items,
  17 `op` phase times (0.1 ms: collision/actors/message/draw), top-3 actor ids x count =
  cost, `o<n>w<n>` talk-offer fail reason (1 player busy, 2 height, 3 talk dist, 4 range).
- Static RAM spare: Debug 640 B, Clean 4672 B. FREE RAM FIRST before any C addition
  (candidates: move C tables to cart; archive C systems the decomp replaced).

FRAME-SKIP RULE (human 2026-10-03, applies to EVERY C<->decomp hand-off, all steps):
Below 30 fps the C game runs up to 4 catch-up steps per drawn frame, but poses Link (and
other skinned C models) ONCE per drawn frame; the decomp runs 2 of every 3 C steps (20 Hz).
So C data handed to the decomp can repeat across steps, and a decomp step can be skipped.
- Hit volumes (AT/AC/OC) built from C poses stay live on steps where the source did not
  move; never drop them because "nothing changed" (real OoT does, at fixed 20 Hz).
- Sweeps go from the last pose the decomp SAW to now, same action only; never from an
  idle/sheath pose. First step of an action hits with the volume itself (with thickness).
- One-shot C events (presses, swing start, damage, item use) latch until a decomp step
  consumes them (input already does this). Decomp -> C results (damage to Link, knockback,
  player_push) apply once, on the C step after the decomp step, never twice.
- Check every new bridge at 15 fps AND 30 fps (human: inside 29 fps vs outdoors 15 fps).
Applies to step I (decomp enemies hurting C Link), G (talk), H (doors), all proxies.
First case: sword vs grass, bridge_player.cpp PlayerProxy_UpdateWeaponInfo.

NPC SPRITES (human 2026-10-03: "all NPC except Hero, incl. Lon Lon, horses as sprites").
Mido test PASSED. Rollout PASSED in Kronos ("better than 3D by far"); above/below view
looks a little odd (option: bake a 2nd pitch row). Sprite draw range 1500 (was 180-400
3D fade), built, waiting test. Rollout details (CLEAN IMAGE ONLY: Debug has
576 B static RAM at that checkpoint; current source uses sprites in Debug too, target verification pending).
- tools/build_npc_sprites.py: C NPCs NPC00-15.SPR (Mido, Saria idle, 13 Kokiri types,
  shopkeeper), <=8 poses/clip, cels <=64 px tall, full textures, 5 dirs + runtime mirror.
  --generic(-only): decomp NPC objects (GENERIC_NPC_SOURCES) -> G<oid3><nn>.SPR, one sheet
  per (skeleton, animation the actor source names), <=6 poses, <=56 px, one cel size per
  skeleton; build/oot-core/generic_sprites.h {object, limbs, anim offset, nn}. 34 sheets,
  1.57 MB total; host loads only the current scene's objects into the cart heap.
- src/npc_sprite.c: shared draw. One VDP1 slot per drawn instance; rewritten only on
  pose/direction change; a slot rebinds size+CLUT when its sheet changes.
- npc_draw.c: every placement + shopkeeper as sprite; the later 9d384cd baseline removes the
  former Saria greeting 3D exception. Focus = fixed height. No head/torso turns.
- Blob API v16: OOT_CORE_FLAG_NPC_SPRITES (set_flags): generic NPC Actor_Draw skipped
  (the 12.8 ms Lon Lon draw), NPC view carries object/limbs/anim/frame. Host: 8 slots
  sized for the scene's biggest cel, actor-list view order, 2000-unit box.
  Follow-up now allocates only spawned instance count, capped at eight.
- Lon Lon fix (human: out of memory G0C006.SPR): host loaded every object of every layer
  (1.5 MB). Now loads sheets only for objects of spawned generic NPCs, jo_malloc + 85% heap
  guard (skip, never error). Follow-up above fixes deferred-spawn loading and refreshes
  room changes; later same-room spawns of new objects remain a gap. Limit is cart sheet
  memory, not sprite count (VDP1
  draws hundreds: Dragon Force); slots (8) can grow.
- Horses NOT done: En_Horse_Link_Child (child Epona) and En_Horse_Normal not imported,
  and they use the Skin system (not SkelAnime): needs import + a Skin-limb baker. Next batch.
- Undo: revert npc_draw.c, oot_core_host.c, npc_sprite.*, blob views/draw/api v16,
  build.sh lines, build_npc_models.py full=, delete tools/build_npc_sprites.py.

FRAME-SKIP RULE (human 2026-10-03, applies to EVERY C<->decomp hand-off, all steps):
Below 30 fps the C game runs up to 4 catch-up steps per drawn frame, but poses Link (and
other skinned C models) ONCE per drawn frame; the decomp runs 2 of every 3 C steps (20 Hz).
So C data handed to the decomp can repeat across steps, and a decomp step can be skipped.
- Hit volumes (AT/AC/OC) built from C poses stay live on steps where the source did not
  move; never drop them because "nothing changed" (real OoT does, at fixed 20 Hz).
- Sweeps go from the last pose the decomp SAW to now, same action only; never from an
  idle/sheath pose. First step of an action hits with the volume itself (with thickness).
- One-shot C events (presses, swing start, damage, item use) latch until a decomp step
  consumes them (input already does this). Decomp -> C results (damage to Link, knockback,
  player_push) apply once, on the C step after the decomp step, never twice.
- Check every new bridge at 15 fps AND 30 fps (human: inside 29 fps vs outdoors 15 fps).
Applies to step I (decomp enemies hurting C Link), G (talk), H (doors), all proxies.
First case: sword vs grass, bridge_player.cpp PlayerProxy_UpdateWeaponInfo.

SPRITE IMPOSTOR TEST (human 2026-10-03, Mido only): PASS in Kronos ("perfect"), direction
sign fixed (phi = yaw - facing). Next: decide rollout (all NPC types; Debug needs RAM first).
tools/build_npc_sprites.py bakes NPC00.SPR from the real skeleton/anim with FULL textures
(build_npc_models build(full=True) -> SPR00.BIN/ANM, pure-python z-buffer raster, VDP1 A,B,C,C
tile mapping): 48x66 4bpp, 15 poses x 5 dirs (3 mirrored at runtime), 116 KB in cart heap.
src/npc_draw.c spr_draw: 1 VDP1 cel slot, rewritten only on pose/direction change, drawn
with slPutSprite (world pos, SGL scale/sort). CLEAN IMAGE ONLY (Debug has 608 B static RAM;
sprite code +864 B). No head turn, focus fixed at 85% height. If liked: bake all NPC types,
streaming cels as the NPC draw path (replaces most of step B). Undo: revert npc_draw.c,
build.sh, build_npc_models.py, delete tools/build_npc_sprites.py.

Historical roadmap (implementation below records its progress). The current
review orders performance proposals; the current Clean-only/batched-verification
directive supersedes this roadmap's earlier build-both-images/per-step test rule.

PHASE 1: make the decomp path cheap (nothing new until these pass)
 A. Grass back. DONE 2026-10-03: human Kronos PASS (grass back, cuts right at 15+30 fps).
    Cause was NOT Fx math: tests/run_bgcheck_probe.sh (real z_bgcheck + S1 blob, Fx16 vs
    float, 64-bit and MinGW 32-bit long) finds the floor at all 37 Kokiri En_Kusa spawns.
    Real cause: carve move left S1.OOC linked at old 0x0275xxxx; pointers garbage, floor
    snap failed, Actor_Kill. Fix: makefile addr.stamp relinks blobs; host rejects a blob
    outside the carve (BUILD.md gotcha 41). Logged, not blocking: Fx16 subdivLengthInv
    (1/524 -> 0.06% low) inserts 4962 vs 5052 poly nodes; slope floor error up to ~3 units
    on the grid (325/4997 over 0.1%). Fix later in C (32-bit Fx) if floors miss at edges.
    Human 2026-10-03: grass back and cuttable, but only point-blank. Cause guess: proxy
    sword's first live step only primed (real Player_UpdateWeaponInfo), with decomp on
    2 of 3 C steps and short C swing most of slash lost. Fix built: host sends blade points
    always, proxy swept from last idle pose -> WRONG: idle pose = sheath on back, cut grass
    behind Link (human). Now: first live step hits with the blade line itself, 8 units tall
    (like C capsule radius 4), then normal sweeps between decomp steps. Never sweep from idle.
    Human: still bad at 15 fps, fine at 29 fps. Real cause: Link posed once per drawn
    frame, catch-up steps see the same blade, real Player_UpdateWeaponInfo drops AT when
    the blade did not move. Fix built: keep last swept quad live (FRAME-SKIP RULE above).
    Gate: grass cuts at normal sword reach at 15 fps and 30 fps, never behind Link. Static RAM spare Debug 608 B, Clean 4640 B.
 B. Cheap NPC skeletons: no Actor_Draw/Gfx walker for NPCs. Limb matrices straight from
    SkelAnime.jointTable in 32-bit ints, no callbacks, every other step, nearest N only;
    far NPCs frozen pose or hidden. Gate: Ingo draw < 1 ms (row 17).
 C. True 32-bit Fx in bulk: FX_STORAGE32 switch; Debug traps overflow + logs caller PC;
    importer rules fix the patterns everywhere (squared distance -> distance compare or
    64-bit helper; Rand*0xFFFF -> s16 wrap). Gate: host probe 0, target 0 traps on a
    Kokiri + Lon Lon walk, actor update cost far below 64-bit (row 17).
 D. Update budget: cull actor updates outside a range / off-camera (real OoT culls too),
    lower update rate for far actors. Gate: decomp step < 5 ms in Kokiri with all NPCs.

PHASE 2: memory and streaming
 E. Free static RAM (Debug 640 B spare): move C tables/text to the cart, archive C systems
    the decomp replaced (Kokiri children, signs, wonder spots once G1 passes).
 F. Per-room streaming in the cart: object data blobs, skins and meshes load at room
    change into a cart pool (not just at scene load); texture budget per room with
    flat-colour fallback when VRAM is full (never invisible: draw flat). Debug row shows
    pool/VRAM use. Gate: Lon Lon NPCs visible, VRAM < 95%.

PHASE 3: the world works
 G. Talk for every decomp NPC (row 17 `w` reason -> fix proxy talk path). Navi/Z-target
    proxies generic for any decomp NPC (from the Kokiri registry code).
 H. Doors, grottos, exits in every registered scene (C scene flow: En_Door, Door_Shutter,
    Door_Ana, scene exit table). Gate: enter Lon Lon buildings, Kakariko houses, shops.
 I. Combat with decomp enemies: proxy player AC (damage to C Link), C sword vs decomp AC
    already works; knockback via player_push. Gate: fight Deku Babas/Skulltulas from decomp.

PHASE 4: content in bulk, zone by zone (story order)
 J. Kokiri (back to decomp: kids, Mido blocking, signs, Saria via C cutscene hand-off),
    Deku Tree, Lost Woods, Hyrule Field, Lon Lon, Market + Castle, Kakariko, Graveyard,
    Death Mountain, Goron City, Zora's River/Domain, Lake Hylia, Gerudo, ...
    Per zone: importer lists (actors + objects), skins/meshes build automatically, a
    checklist from the decomp (every actor in the room lists, spawn conditions by age /
    day-night / flags, text ids by flag state, events and item gives), save mirror both
    ways. Human checks a story sample per zone. Each zone's C counterpart moves to legacy/.
 K. Later systems as needed for story: z_demo cutscenes, get-item hold-up (sprite),
    ocarina songs, day/night clock, adult Link.

 Known gaps to keep logged: Navi targeting of decomp actors needs C proxies (done for
 Kokiri NPC registry, generalise in G); no Saria (z_demo cues); ocarina; get-item hold-up.

## Mednafen accuracy check (2026-10-03, Claude; human runtime test pending)
**Why:** Frogbull advised Mednafen (most accurate Saturn emu). Mednafen has accurate CD
(2x, ~150 sectors/s, real seeks), SH-2 and VDP timing. Kronos hid every problem below.
Treat Mednafen as the reference from now on; Kronos is only a fast smoke test.

**Launcher (done, smoke test passes):** Config > "Paths and emulator..." has tabs Paths +
Emulator. Emulator tab: Kronos/Mednafen, mednafen.exe, cart (must be `extram4`),
fullscreen, extra args, BIOS check. config.ini gains `mednafen` path + `[Emulator]`
section. Run = `mednafen -ss.cart extram4 -video.fs N <cue>`. BIOS in
`mednafen-1.32.1-win64/firmware/`: sega_101.bin (JP 1.01), mpr-17933.bin (EU 1.00).
Files: tools/launcher/{project-config,config-dialog,kronos-launcher}.ps1, SETUP.md.

**1. Slow loads: root cause found.** Jo `jo_fs_read_next_bytes` = one blocking GFS_Fread
per 2 KB sector. New `ram_cart_load_scratch(name,&len)` (ram_cart.c/.h) = one GFS_Load
into the pause page+backup carves (0x1D000, 325 KB, idle unless paused; never call while
paused). Converted: pause pages (pause_windows.c; human confirmed menu much faster),
room .MSH (kokiri_sgl.c room_load_bank, parsed via the opening-cache path), interior
backdrops .RGB, SFX/action PCM banks (action_audio.c upload), TITLE.RGB (recomp.c).
Still streamed (small): minimap/health HUD files. Pause `paint()` still copies 76,800
cart pixels per cursor move: next suspect if cursor lag remains.

**2. Game crawled while music loaded.** music.c swap read 32 KB/frame with blocking reads
(~8 fps for ~600 KB). Now `cd_stream_t`: GFS_NwCdRead read-ahead, each frame copies only
sectors already in the CD buffer (GFS_GetNumCdbuf, prototype declared locally, in LIBCD),
max 8 KB/frame; after STREAM_STALL empty frames re-issues NwCdRead, then one blocking
sector. UNTESTED: confirm no stall and music start delay; if GFS rejects Fread during
NwCdRead, fall back to bulk load during the black transition.

**3. HGANON.ANM "Out of memory"** (Jo error at 53% heap). actor_mesh_swap_clip
(cutscene_actor.c) held old clip while allocating 224 KB new one -> no contiguous block.
Now stages in cart scratch, validates, frees old, mallocs, copies. If malloc still fails
the mesh is marked unloaded (no motion) instead of a fatal error.

**4. Speckle "garbage" picture: NOT fixed.** Seen in opening (Link's house, Navi lines).
- Correction from source audit: the opening house uses bank-4 VDP1 panorama.
  The NBG1 RGB bitmap is the fixed-camera view, not this moving-camera shot.
- Ruled out: CLUT MSB (all set), backdrop pixel MSB (all set), CL32KRGB rewrite at
  kokiri_sgl.c fog code (also switches to untextured polygon).
- Added harmless `slDMAWait` between per-tile `jo_dma_copy` (mesh_load, field_upload).
  Did not fix it.
- Historical lead (not established for this VDP1 shot): VDP2 VRAM cycle patterns. Jo/SGL `slScrAutoDisp` picks them; Kronos ignores
  them, Mednafen/hardware obey. NBG1 bitmap sits in A0/A1 (needs 2 slots per bank);
  NBG0 text in B1, NBG2 minimap in B0. Pause path already sets them explicitly
  (recomp.c slScrCycleSet). Waiting on human: Mednafen Ctrl+1..7 layer toggles to name
  the bad layer. Then set explicit cycles for backdrop/cutscene. Other open lead:
  SGL MaxPolygons 3750 vs vdp1_budget.py 2200 command reserve (GAME_TEXTURE_BASE 0x13300).

**Build:** `./build.sh --clean --quick OOT_CORE=1` (WSL) passes; game-clean.cue rebuilt.
**Ownership:** Claude edited only the files named above + config.example.ini/README.md.
Other work that was uncommitted at this historical checkpoint (build.sh, makefile, oot-core/*, npc_draw.c,
oot_core_host.c, npc_sprite.*, build_npc_*.py, BUILD.md) is NOT Claude's this session:
leave it alone. Nothing committed.

## Historical NEXT SESSION: GAME CONTENT ROUTE (approved by human 2026-10-02)
The current performance review was explicitly requested on 2026-10-03 and
supersedes the historical tuning restriction in this checkpoint.
Goal: the actual game through the decomp: NPCs, dialogue paths, event triggers, actors
present/absent by progress flags, child/adult and day/night layers. No more perf tuning
unless a real frame-time problem blocks content (row 16 `ou` = decomp update us/step).
Rules: decomp HUD/pause/text stay on VDP2 (bridge their draw); held-up get-items are sprites,
not 3D GI models. Old C game code: when a decomp system works in game, move the C version to
legacy/ (archive, reference only) in the same batch; it still works slice start -> Field.
Steps (in order):
 0. DONE (build only): `./build.sh --quick ...` skips asset steps (C/C++/oot-core changes).
 1. DONE (build only): gSaveContext mirror both ways each step: eventChkInf/itemGetInf/
    infTable/scene flags (copy back after update), age (child), night (0), dayTime (noon).
 2. DONE: every registered scene gets a blob (<scene>.OOC, all room layers:
    main + AltHeaders); play_init in any scene, layer = Play_Init rule, per-room fallback =
    Scene_CommandAlternateHeaderList. Decomp grass/drops drawn in any scene. Scene-level alt
    headers (spawns, transition actors) not yet. Steps 0-2 runtime: human 2026-10-02, Kokiri
    grass test "no issue" (e57ec80). Second grass scene not reported separately.
 3+4+5a. BUILT, runtime NOT checked (API v9, Debug static RAM spare 432 B, Clean 4352 B,
    blob 392 KB of 448 KB carve). First decomp NPC = En_Ko (all Kokiri children):
    - Imported: z_skelanime, z_message, z_kanfont, z_construct (real Message_Init +
      Regs_InitData), z_face_reaction, z_path, gfxalloc, z_memory_utils, En_Ko.
    - Objects like N64: importer OBJECTS (os_anime, km1, kw1, fa) -> O<id hex>.OOB data
      blobs linked at segment 6 (oot-core/object.ld): skeletons/limbs/anims verbatim,
      DLs/textures one-word placeholders. obj_syms.ld gives OOTCORE their 0x06 addresses.
      Each OOC lists the built objects its room ObjectLists name; host loads them after the
      OOC in the scene carve; set_objects fills objectCtx slots. Object_GetSlot real search;
      unbuilt object ids = resident slot 0 (gameplay_keep etc.), built-but-unloaded = -1.
      SEGMENTED_TO_VIRTUAL/OS_K0_TO_PHYSICAL without K0BASE, gSegments[2]=0x02000000.
    - Scene paths: OOC carries Path lists per scene layer (Scene_CommandPathList).
    - Text from ROM: NESMSG.BIN = baserom nes_message_data_static in cart carve
      RAM_CART_MSGDATA; entry table offsets from the ROM's own table in `code`
      (importer msg_syms.ld). Japanese table emptied (English only, language set ENG).
    - z_message runs for real: Message_Update + Message_Draw each decomp step, Gfx to a
      scratch buffer (bridge_message.cpp). oot_core_views.cpp lays the decoded page into
      38x4 cells + colours; C oot_core_message_box() prints it on the VDP2 rows 20-25 with
      the VDP1 panel and prompt mark (decomp box replaces the C box while up).
    - Player proxy talk: copy of Player_ActionHandler_Talk / StartTalking / SetupTalk /
      Action_Talk close; real player body cylinder (OC) -> push sent to C Link.
    - C: Kokiri children absent from C logic while decomp plays (gameplay_npc_present);
      npc_draw draws each En_Ko with its type's baked model at decomp curFrame + decomp
      head/torso turn. A goes to the decomp while it offers talk or talks, B while it talks; Link frozen
      (gameplay_blocks_world) while the decomp text box is up.
    - APPROXIMATE / missing (log, not blockers): one baked clip per type (decomp anim
      changes not shown), glyph widths = 1 cell, item icons not drawn, no Z-target/C-Up
      talk to decomp NPCs, no talk anims for Link, Navi hints about children may still be
      C, no ocarina in messages, player name fixed "Link". Mido/Saria stay C (next batch).
    Human check (Debug, one pass): Kokiri Forest - kids visible where OoT has them, look at
    Link; walk up, A opens real ROM text, A pages/closes, choices (if any) by D-pad; kid
    blocking the exit pushes Link; row 15 `oc p1 ...` no freeze; one Kokiri house; heap row
    no failed allocations (bank-2 heap is now 598 KB, was ~1 MB).
    Human 2026-10-02 on 82c0ac4: C Mido talks and blocks; decomp grass NOT cut by sword.
    Cause found: Actor_UpdateAll only updates actors with INSIDE_CULLING_VOLUME (set by
    Actor_DrawAll's culling, which never runs) or UPDATE_CULLING_DISABLED; En_Kusa clears
    the latter once ready, so it stopped updating. Fix: OotCore_CullActors (sphere of the
    actor's culling distance around the player) before Actor_UpdateAll. APPROXIMATE.
 5a. BUILT, runtime NOT checked (API v10; Debug spare 6320 B, Clean 10272 B after the Jo
    work-RAM malloc arena 51200 -> 45056, overflow goes to cart zones):
    - En_Md (Mido, object_md blob, drawn as model 0 by npc_draw), En_Wonder_Item,
      En_Wonder_Talk2, Obj_Mure2, En_Kanban (object_kanban blob).
    - C Mido, C wonder spots, C sign read/cut off while the decomp plays; C still draws
      signs, parts from decomp partFlags (prop_query). Flying sign pieces not drawn.
    - Null-profile guards (importer): spawning a not-imported actor/effect returns
      nothing (Obj_Mure2 rock circles -> En_Ishi not imported yet).
    - Debug row 16 adds `t<talk> m<msgMode> x<textId> n<npcs> c<AT>/<AC>/<OC>`.
    Human check: grass cuts again; kids/Mido visible; Mido blocks the Deku path (push)
    until sword+shield, talks ROM text; signs read with A (ROM text), sword cuts pieces off;
    hidden wonder spots drop items; row 16 numbers if anything is wrong.
 5b. Phase 2 generic draw, BUILT, runtime NOT checked (API v11; Debug spare 5104 B,
    Clean 9072 B; blob 395 KB of 448 KB):
    - oot_core_draw.cpp: per generic-draw actor, real Actor_Draw into scratch Gfx
      (now in the low-WRAM play block, RAM_LOW_OOTPLAY 0x70000), then a Gfx walker
      (G_MTX/POPMTX/DL/ENDDL/segment) turns each call of a placeholder DL into a draw
      item: mesh key + transform as translate*Ry*Rx*Rz*scale (no raw SGL matrix).
    - Placeholders are indexed: keep ones in section .keep_ph (importer KEEP_PLACEHOLDERS,
      append only, keep_ph.txt); object ones after an 'OOB1' header in each .OOB
      (O<id>_ph.txt). tools/build_core_meshes.py builds K<idx>.MSH / Q<obj><idx>.MSH
      with build_shop_props.static_mesh at scale 1 for every DL the generic actors name.
    - C (oot_core_host.c): loads the scene's meshes after set_objects, uploads them last
      in npc_draw upload_visible (a full bank skips them, never errors), draws items in
      world_props_draw via actor_mesh_draw_euler (Y flip negates pitch/roll).
    - Generic-draw actors (importer GENERIC_DRAW_SOURCES): Obj_Tsubo, En_Gs, Obj_Hana,
      En_Wood02 (trees/bushes), Obj_Syokudai (torches), Obj_Kibako (crates). Meshes load
      only for generic actors the scene's room lists contain (mesh_list, C cap 40).
      set_camera passes the C camera yaw (Camera_GetCamDirYaw for torch flames). API v12.
      They spawn ONLY in generic scenes (save scene >= SAVE_SCENE_COUNT); slice scenes keep
      the C copies, so Kokiri is unchanged by this step. En_Ishi left out (38 KB, needs
      carry). Gossip stone material/squished DLs fail the converter (only base DL drawn).
    Human check: level select into a generic scene with pots/gossip stones/flowers (e.g.
    Kakariko, Death Mountain trail, a dungeon room with pots): props appear at the right
    place/size/orientation; sword breaks a pot (drop appears). If props are mirrored or
    tipped: report it (pitch/roll sign in actor_mesh_draw_euler is the first suspect).
 5c. Real NPC animation by runtime skinning, BUILT, runtime NOT checked (API v13):
    - Matrix_Init now runs in play_init (was missing: any Matrix_* call wrote through
      NULL; affected En_Kanban updates and every draw).
    - En_Ko/En_Md are drawn for real each step (Actor_Draw -> SkelAnime_DrawFlex); the
      blob copies the flex matrix array (gSPSegment 0x0D, dListCount entries) per actor
      and exposes it in OotCoreNpcView.mats.
    - build_npc_models.py writes NPCnn.SKN (per vertex: matrix slot = depth-first index
      of limbs with a DL, limb-local position). C actor_mesh_draw_skinned transforms the
      baked model's vertices with the live matrices: every animation, blink-free pose and
      head/torso turn comes from the decomp. Falls back to the baked idle clip when the
      table or matrices are missing.
    - Scratch opaque display list 64 KB (RAM_LOW_OOTPLAY 0x78000).
    Human check: kids/Mido animate like OoT (sitting, standing, digging...), turn heads,
    no exploded limbs. Exploded or inside-out limbs = slot order mismatch (report which
    kid type).
 5. Next: more generic actors, En_Sa (needs z_demo cues), other areas.
    Archive the C Kokiri child/Mido/sign code to legacy/ once confirmed.
 6. Later: z_demo cutscenes, z_player, z_camera. Then archive C counterparts.

## SPEED (2026-10-02, human Kronos kronos-fix, Debug, ns per call, cart)
Low-WRAM copy (OOTBENCH.BIN, rows 16-17) is NOT faster than cart: cost is the math, not the bus.
Fixes: fx.h dmuls.l inline 32x32 path + 32-bit shift helpers + always_inline (61769fc);
oot_math sqrtf = divider Newton, sinf/cosf = Q30 table + interpolation, after SaturnMath++
(bec381b, e810ba3). Host probe 0 over tolerance each time.
  ma 9015 -> 7549, dv 20901 -> 19922, ss 15864 -> 14362, ds 59799 -> 39371, sn 49818 -> 10553,
  at 28630 -> 26350 (decomp code, unchanged). Kronos SH-2 timing is approximate: a ~60-instruction
  loop shows ~200 cycles. Next: real per-frame cost row (Actor_UpdateAll time), real hardware
  run if possible. 32-bit Fx would halve again but needs an overflow audit (not started).
  dv still slow: check fx_div hardware path is taken (FX_RUNTIME / range test) before more work.

## Historical NEXT SESSION: Phase 1 step 5 (first live decomp actor)
Rule: game logic comes from decomp source via `tools/oot_core_import.py`. Do not rewrite a
system by hand that the decomp already has. Our C code stays only as the Saturn backend
(render, audio, VDP2 UI, file IO). Read game/docs/BUILD.md first (Linux/WSL build only;
gotchas 20-29 are oot-core). Run git from Windows. Human runs Kronos (`build/kronos-fix`).

State at handoff (commit 8bfdb92, branch oot-core, not pushed): steps 2-4 done (see status
sections above). Step 4 runtime CONFIRMED by human 2026-10-02 (Kronos kronos-fix, Debug):
row 15 `oc p1 pl1 pr0 mi0` in Kokiri Forest, no freeze. Gate speed numbers are slow
(ma 8582 ns); human said fix later, do not block on them.

Step 5 progress (2026-10-02, Debug build OK; tasks 1-3 runtime CONFIRMED by human):
- DONE 1: importer cuts each room's main-header ActorEntryList into the scene blob (SPT04COL.BIN
  now starts with OotSceneBlob, oot-core/include/oot_scene_blob.h; section .scene_header).
  load_room_actors (oot_core_api.cpp) copies only ids in sRoomActorIds (= ACTOR_EN_KUSA) into
  play->actorEntryList; Actor_UpdateAll spawns them. API version 4.
- DONE 2: play_init takes room; entry set_room(room) = Room_RequestNewRoom + FinishRoomChange
  (func_80031B14 kills old-room actors). Host calls it each frame with kokiri_scene_room().
  NOTE: KOKIRI_STREAM_ROOMS is not defined, so room is always 0 -> room 2 grass (4) never spawns
  (same as C grass, which also filters room 0).
- DONE 3 (partial): OotCoreHost wired. play_sfx -> action_audio_decomp_sfx (PLANT_BROKEN, GET_RUPY,
  GET_ITEM, HP_RECOVER; others silent); Audio_PlaySfxGeneral (SFX_PLAY_CENTERED) now routes too.
  give_item maps decomp ItemId -> save_item_give; health_change -> save_heal/save_damage.
  En_Item00 seeds/nuts/stick use GetItem offer (Actor_OfferGetItem), not Item_Give: task 5.
- Human confirmed 2026-10-02: Debug, Kokiri, L+R row 15 `oc p1 pl1 pr12 mi0`, no freeze.
- DONE 6 (build only, runtime NOT checked): entry set_sword (API v5). Host sends
  gameplay_sword_active() + gameplay_blade_points() each step; player proxy (bridge_player.cpp)
  owns meleeWeaponQuads[0] (z_player D_80854650), sweeps prev->cur line with a copy of
  Player_UpdateWeaponInfo, dmgFlags DMG_SLASH_KOKIRI. APPROXIMATE: one blade line, one quad
  (real: two lines/quads); jump/spin dmg flags not passed. Human check: cut Kokiri grass,
  row 15 `mi` should rise above 0 when a drop spawns (drops are invisible, not collectable yet).
- Human confirmed 2026-10-02: sword cuts decomp grass.
- DONE 4+5 batch (build only, runtime NOT checked; API v7, work RAM spare 3,760 B):
  - Room lists now also spawn ACTOR_EN_ITEM00 (9 floor rupees in room 0).
  - oot_core_owns_kokiri_props() (src/oot_core_host.h): while decomp plays Kokiri, C grass
    (gameplay.c tufts) and C floor rupees stop cutting/collecting; kokiri_sgl.c draws decomp
    En_Kusa (uncut, object ready) with the grass billboard and decomp En_Item00 with
    kokiri_drop_draw (params = ITEM00 type) via entry actor_view. Wonder-item drops stay C.
  - Rupees/hearts: En_Item00 collects by distance (real code) -> Item_Give -> C save.
  - Seeds/nuts/stick: player proxy handles Actor_OfferGetItemNearby (PlayerProxy_GetItem):
    APPROXIMATE, given at once (no hold-up, no first-get text).
  - Entry set_save mirrors C save into gSaveContext each step (health, capacity, rupees,
    stick/nut/slingshot + ammo; child; no magic/bombs/bow) so the real drop table and
    Item00 filters see the real state. Floor rupees use temp collectible flags (0x24-0x27):
    they respawn on scene re-entry, as in OoT (C used to keep them taken in the save).
  - Missing (logged): Kusa lift/throw with A (Actor_OfferCarry), Item00 collect rise anim,
    two-quad sword, room 2 (no room streaming).
- Human check (one pass): Debug, Kokiri, L+R. Cut grass -> grass sprite vanishes, drop
  visible, walk over -> rupee/heart counted with sound; grass regrows later; floor rupees
  visible and collectable; seeds only drop with slingshot owned; no double cut sound.

Step 5 tasks, in order:
1. Room actor lists: importer cuts each Kokiri room's ActorEntryList verbatim out of
   extracted `spot04_room_<n>.c` (main header lists `spot04_room_0_03000094`,
   `spot04_room_1_03000088`, `spot04_room_2_03000084`; AltHeaders = other scene setups, later),
   same way as SCENE_COLLISION. Put them in the SPT04COL blob (data, fixed address) or the
   oot-core blob. Spawn via `play->actorEntryList`/`numActorEntries` (Actor_UpdateAll spawns
   them, real behaviour) or entry `spawn`. Start with ACTOR_EN_KUSA entries only; leave all
   other ids to the C game until imported (step 6).
2. Rooms: actors carry `room`; set `play->roomCtx.curRoom.num` from `kokiri_scene_room()` so
   room-bound actors behave (check z_actor Actor_Spawn/room kill logic).
3. Wire `OotCoreHost` (`oot-core/include/oot_core_host.h`) in `src/oot_core_host.c`:
   play_sfx -> action_audio (map decomp NA_SE_* ids used by En_Kusa/En_Item00), give_item and
   health_change -> save_state / existing item_drop pickup code. En_Item00 calls Item_Give.
4. Hide the C grass that the decomp now owns: world_props grass in Kokiri Forest only
   (world_props.c / world_props_draw.c). Grass is invisible until Phase 2 draw shim, so for
   testing either keep C grass drawn but non-interactive, or add a debug marker. Pick the
   option that keeps the slice playable; record it in RECOMP/plan.
5. Collectibles: En_Item00 spawned by Item_DropCollectibleRandom must be picked up by the
   player proxy (needs player cylinder / Actor_HasParent etc. — check what En_Item00 tests;
   bridge only what is missing). Drops must match the real table (CLAUDE.md drop rule).
6. Debug row 15 shows prop/misc counts; human cuts grass with sword: grass needs the C sword
   to hit decomp colliders -> C sword AT must enter `play->colChkCtx` (CollisionCheck_SetAT)
   via a host->blob call (add entry `set_sword(...)`). This is the first C->decomp combat link.

After step 5:
6. Bulk: import every Kokiri actor overlay the scene spawns, one per commit, each with a drop
   check. Stand-in player and stub list (bridge_play.cpp STUB tags) shrink as files import.
7. Phase 2 draw shim: real GraphicsContext + Actor_DrawAll; gSPDisplayList(seg addr) ->
   prebuilt Saturn mesh (build_actor_model.py, keyed by bridge_assets.cpp symbols). Faces
   textured only (VRAM rule).
8. Music bulk (independent): shared/tools/build_title_audio.py over all sequences.

Known hazards: ROM IEEE-float data must be converted to Fx at load. Keep Fx ops constexpr.
Blob code runs from the cart only on build/kronos-fix Kronos (BUILD.md 26). Blob 200 KB of
256 KB carve: grow carve (ram_cart.h + makefile together) before it overflows. Work RAM spare
5,696 B: new C host code must stay small. Boot markers on row 20 (oot_core_host.c).

## Approach (phased, each phase gate)
### Phase 0 — spike, prove or kill (do first)
1. New dir `game/oot-core/` (or `shared/oot-core/`). Build decomp C files as **C++** for SH-2 with
   `f32` = `Fx` class (32-bit store, int64 mul/div, saturate/assert on overflow in debug).
   Mechanical: no hand edit of logic. Script `tools/oot_core_import.py` copies listed decomp files,
   applies regex fixups for C-vs-C++ (void* casts, designated init) only.
2. Math lib: sinf/cosf/sqrtf/atan2 -> tables + SH-2 DIVU. `Math_*`, `Math3D_*` dist functions
   get int64 internal path (fix distSq overflow at source, once).
3. Port tiny slice: z_actor.c core + z_lib.c + 1 simple actor (En_Kusa grass, has drop table) +
   z_collision_check minimal. Stub libultra/gfx (`Gfx` writes -> recorder).
4. Measure on target: cycles per actor update (SH-2 disasm check no `__adds f`/soft-float).
   Gate: if update cost too high or overflow everywhere -> stop, report.

### Phase 1 — core systems bulk
z_bgcheck (collision), z_collision_check, z_actor, z_camera, z_player, z_play loop, z_message,
save. Replace our hand ports gradually behind flag; keep our renderer.

### Phase 2 — draw shim
Offline: convert actor/object display lists -> our VDP1 mesh format (extend
`game/tools/build_actor_model.py`). Runtime: `gSPDisplayList(seg addr)` -> lookup prebuilt mesh +
current matrix -> existing kokiri_sgl draw. No runtime F3DEX parse of triangles.

### Phase 3 — actors in bulk
Import actor overlays scene by scene (Kokiri first). Each actor: compile, link draw shim. Drops
come free (real code).

### Music bulk (parallel, independent)
`shared/tools/build_title_audio.py` already convert OoT seq -> SCSP score, fail on unknown opcode.
Run over ALL sequences, collect unsupported-opcode list, implement missing opcodes once in
`shared/lib/music/music.c`. Output full bank. SFX same path later.

## Critical files
- new: `game/oot-core/**`, `game/tools/oot_core_import.py`, fixed `Fx` header
- `game/makefile` (add C++ objects, SH-2 g++ from sh2eb-elf)
- `shared/tools/build_title_audio.py`, `shared/lib/music/music.c`
- `game/docs/RECOMP_PLAN.md` (record strategy + phase status, required rule)

## Verification
- Host: compile oot-core natively, run actor update vs real float build, compare outputs (diff tolerance).
- Target: build clean image, disasm check no soft-float helpers, cycle count report.
- Human runs Kronos/Saroo test (no emulator launch by agent).
- Music: build all seqs, report coverage %.

## Risk
Phase 0 may fail perf. Then fallback: keep hand-port but drive it from decomp source per system
(current way) + bulk music still win.


2026-10-06 map curtain follow-up (source only; no target build): shared 3D
curtain uses per-map base fog palette and clock tint, matching the fixed dark
horizon band. Kokiri daytime source fog is warm RGB 200/200/150. All 75 map
palettes parse; 17 sky/curtain host cases pass. Static rooms retain static tint;
weather/story palette selection and target appearance/fit remain unverified.
Next authorized build regenerates environment_sky_data.h (+600 palette bytes).
See RECOMP_PLAN.md for current coverage and bitmap-interior limitation.

Human authorized follow-up quick build: Clean OOT_CORE=1 passes; regenerated
sky tables included, .bss 0x06083ef0 leaves 272 B below SGL. Missing curtain
scene-flow declaration fixed. All CUE files present. No emulator verification.
Log: build/curtain-quick-build.log.
