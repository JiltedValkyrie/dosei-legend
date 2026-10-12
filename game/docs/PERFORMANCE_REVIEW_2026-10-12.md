# Performance and Player regression review, 2026-10-12

## Active Mednafen measurements and Saturn-focused batch

**Stopped at human request.** Latest source batch passes 217 host tests, but
final target link still exceeds SGL by 112 B. Guard removed the unsafe image;
normal Debug staging restored and all 1,434 files verified. No seventh-candidate
runtime test or post-build audit/ISO acceptance. Exact resume state:
[PERFORMANCE_HANDOFF_2026-10-12.md](PERFORMANCE_HANDOFF_2026-10-12.md).

Astra is authorized to launch/control Mednafen and make a temporary image
booting directly into child Kokiri. Ordinary Debug 6117a58c and Clean c3f29128
are preserved. Human now forbids foreground focus changes while playing.
Use background-scoped test input only. Slow loading is expected; loading
screens and frozen dialogue overlays are not frame measurements.

First isolated image 8d88deb1 has the preserved Debug code plus direct boot.
Short moving captures: M about 8 FPS, P 7.5, C 6.3. M aim capture 7 FPS;
C aim attempt entered dialogue and is invalid. These are route samples, not
a sustained benchmark. Images: build/mednafen-test/{M,P,C}-*.png.

Second isolated image 4ea3f91942f4ae27568b3cc3f6906fe2d286e63e67222b7e86c6e878a0632d4c:
original 14-point/19-face intact sign replaces merged 66-point/87-face geometry;
four recent quantized Player poses cache exact decoder prefixes. No animation
cadence changes. 170 tests pass, host/core audits 0 failures, 1,435 ISO payloads
match staging. Host .bss 0x06083640 (2,496 B spare), core .lowbss 0x9130.
Normal Debug staging restored byte-for-byte; Clean hash unchanged. Logs:
build/kokiri-speed2-{tests,build,host-audit,core-audit,disc,debug-preserved}.log.
The old verifier's final "intact sign 66/87" line describes legacy piece files
still present in that image, not the new SIGNALL geometry.

Runtime: speed2-boot-check.png shows 12.6 FPS, sign 1.2 ms versus first image's
about 15 ms at the initial view (561 gathered vertices). speed2-M-idle-2.png
shows 13.3 FPS from a changed position; speed2-M-run-2.png shows 9.4 FPS,
91.6 ms fr, 50.4 ms master prep, 53.7 ms core. Initial speed2-M-idle-1/run-1
were still loading and are invalid. speed2-M-aim-1 did not establish first
person and is also invalid for aim performance. No sustained 20 FPS claim.

Third candidate f2f19b8268560b0666ea7844e9cf1f2c26e24c3fbcdcb1fdfa88d6b170336be6
implements hit/fade/gone signs without fragment simulation/assets, 16-byte SP2
payload/allocation alignment for SH-2 burst DMA, existing 6 KiB high-WRAM draw
storage reused for depth/side scratch, and existing angle-table use for Player
IK/matrix extraction. 189 tests pass; both math audits and forest budget pass;
all 1,424 payloads match. Host .bss 0x060831C0 (3,648 B spare). First private
desktop runtime works without focus changes or user-controller bindings:
speed3-M-idle-1/2 show 14.1/16 FPS; speed3-M-run-1 shows 9.4 FPS, fr98.8 ms,
mp65.8 ms (pd16.7, pp31.7, pf10.6, pk9.5), core25.7 ms. Moving prep remains
the large cost. C-item attempts have not established a valid aim measurement.

Fourth candidate e9d4ba8e74bae55a2e09d2910456f822fbbf12545545c35c3c77a9b68aa14b9d
adds exact dirty HUD uploads: pulse footprint at most 9 cells/288 bytes instead
of full heart+magic banks/2,880 bytes. Tracks both destination banks independently;
magic uploads only when its state changes. No new VRAM or pulse cadence change.
190 tests pass, both audits clean (540 host/1,607 core allowed multiplies), forest
budget passes and all 1,424 payloads match. Host .bss 0x060833E0 (3,104 B spare).
Ordinary Debug/Clean and matching Debug staging remain preserved. Runtime:
speed4-M-idle-1 14.1 FPS, fr63.5 ms; speed4-M-run-1 9.4 FPS, fr99.6 ms,
mp69.2 ms; r1 remains 11.2 ms. No large HUD timing gain established.
speed4-M-aim still third person: invalid for aim performance. Evidence:
build/kokiri-speed{3,4}-*.log and mednafen-test/speed{3,4}-*.png.

Fifth candidate 7444b92dd50023bf1ac1641539a3f575254dec47dabf48e5868ffd9b742ee728:
Kokiri candidates reuse a conservative bounded camera region, retaining exact
actual-camera culling, sorting and fog. All mapped candidates restore on bank,
LOD, roll, FOV or mode invalidation. Refit scratch respects the high-RAM point
union and Low-RAM inverse map. Empty lists are valid; capacity failure falls
back without losing geometry. Host differential: 960 moving frames, 893 refits,
492 high/172 spill draws; visible geometry and fog match the uncached path.
The visibility bound passes 1,919,873 views; SGL LUT checks all 33,619,968 angle
pairs. No stored wide arithmetic or software multiply/divide helpers added.
Also rejects far signs and impossible attention candidates before angle math,
with unchanged prompt/target results and occlusion ordering. Row 22 splits HUD
queries/health/visibility; row 21 reads live Player item gates after core join.
201 tests pass, host/core audits 561/1,607 allowed multiplies and zero failures,
forest budget passes, all 1,424 ISO payloads match. Host .bss 0x06083EB0 leaves
only 336 B below SGL; check every further change. Normal Debug 6117a58c and Clean
c3f29128 remain unchanged and normal staging is restored/verified.
Runtime: initial idle 15 FPS, `hud q1 hp114 vis0` (0.1 ms): HUD health draw,
not prompt scans, accounts for the remaining roughly 11 ms. Forward input
capture gives 8 FPS with mp31.2 ms. That route catches Link on a wooden ledge;
these short forward-input captures do not establish sustained running FPS.
Live flags identify STATE1_13 (ledge hang), which never runs item admission;
this explains the earlier failed aim attempts despite g0000. Normal A releases
the ledge. Then speed5-M-aim-ground.png confirms first person: 9.4 FPS, fr91.9,
core70.8, join47.6 ms. No item-input fix or benchmark bypass required.

Sixth candidate 6f806172a021191493ce1411958b99c6c59fa2caf3764f5d67539043d40b0a15
copies the five heart atlas fills (640 B) to unused Low RAM at 0x002FF000 during
normal HEARTS.BIN loading. Pulse composition previously read VDP2 for every
pixel despite composing its output in CPU RAM. Pixel output is unchanged;
runtime VDP2 source reads are removed. Last slave-stack byte is below the new
carve; compile-time bounds enforce separation. No new high-RAM storage.
202 tests pass, both audits clean (561/1607), budget passes, 1,424 files match;
.bss remains 0x06083EB0, 336 B spare. Both normal images/staging preserved.
Private-desktop measurements: heart pulse `hp4` through `hp8` (0.4-0.8 ms),
down from about 11.4 ms. Initial idle 14.1 FPS; valid M first-person aim
9.4 FPS, fr93.5 ms, slave core74.2 ms, join36.6 ms. P aim 9.4 FPS and C aim
9.0 FPS at slightly different camera angles are short samples, not a controlled
ranking. Core aim work remains large. `speed6-M-idle-1` is still loading and
invalid. Row-1 Link draw cost can retain an earlier sample when that phase is
skipped: it does not prove Link is drawn in first person. The character seen
ahead in these aim pictures is an NPC. No first-person visibility regression
was established.

Seventh candidate source, now paused: exact bounded affine Player anchor transforms,
hidden Link vertex-skin suppression with same-frame aim-exit refresh, Debug
async-call line provenance and host aim-state fields. Temporary entry moves
to source Kokiri spawn 9 (outside Mido's house) so the short forward test does
not immediately catch the old spawn-0 ledge. Ordinary entries are unchanged.
Sustained moving/aim 20 FPS remains open.

### Candidate 9/10: moving scene prepare (Claude, 2026-10-12)

Baseline candidate 8. Changes (kokiri_sgl.c, forest_envelope.h, forest_vertex_pack.h):
- Candidate envelope variants, Debug L+R+Right cycles v1..v5 (row 23 shows
  `env vN b% bt xp xa xo`: build % of frames, mean build-pass time, exit
  reasons position/angle/other). v1 original 64 units/256 binang centred;
  v2 led along last-frame camera motion (3/4 radius) and yaw (4 frames, cap
  3/4 angle); v3 led + 128 units; v4 led + 128 + 512 binang; v5 = v3 with
  draw points forced to the Low RAM spill (depth/side scratch in high RAM).
  Every variant stays conservative: fe_begin_sized bound proof covers led
  centres up to 256 units/1024 binang (1.92 M views, zero lost faces); refit
  still needs the camera inside. Default now **v3**.
- Exact pass: sort/MESHon written only when changed (ATTR rows are Low RAM,
  write-through); forest_mesh read once per face.
- Fog: touched-tile list in the tile_depth carve tail; the fog pass visits and
  resets only touched tiles (full scan on overflow/bank load); VDP1 CLUT writes
  in 32-bit pairs. Host reference (full scan each frame) matches exactly.
- RAM: code growth pushed .bss 1,520 B over SGL. Fixed without capacity cuts:
  cold envelope helpers Os/noinline, gather/pack noinline, and master-only
  snap_view + snap_tools moved to new Low RAM carve 0x00209000 (0x800; mesh
  flags carve trimmed to 0x800 >= 1,916 polygons). .bss 0x06083E10, 496 B spare.
- 222 tests pass (new: running variants, sized/led bound proof, tile-list
  reference, snapshot carve). Host sim builds per 450 running frames:
  v1 137, v2 91, v3 51, v4 52, v5 51. Audits 552/1,625, 0 failures; budget
  passes; 1,424 ISO files match. Candidate 10 test ISO 3f305c9d.

Mednafen, mode M, spawn 9, forward/back 1.7 s run samples (rows 0/15-23):
- Candidate 9 A/B, 4 samples each. Builds: v1 25-33% of frames in 3/4
  samples (mean build pass 12-19 ms/frame, about 50 ms per build); v2 builds
  in 2/4; v3 **0/4** (mp 11.5-12.3 ms vs 23-30 with builds); v4 no gain,
  more vertices (523, spill); v5 spill same as v3 (no placement gain).
  Whole frame v1 70.6-74.8 ms, v3 64.7-72.8 ms.
- Candidate 10 (v3 default), 6 samples: frame 68.2-79.1 ms, 10.0-13.3 FPS
  shown; one build in six (79.1 ms); others mp 13.4-14.9 (pd 4.1, pp 7.3,
  pf 2). Join wait now 0.6-2.5 ms: faster prepare exposes core waiting.
  Idle 47.9 ms / 20.0 FPS (first), 58.1 later.
- Master while running (v3): work 54-65 ms = gameplay step mv 14-18, Link
  submit lk 10-11, refit prepare 12-15, actor draw da 9, scene submit 4-5,
  UI 2. Core on slave 25-45 ms. Prepare is no longer the largest item.
- Aim (grounded slingshot, four samples 1.5 s apart): 20.0/16.0/20.0/16.0 FPS,
  frame 50.2-53.2 ms, master waits 16-17 ms at join (core bound).
- Projectile firing still unproven: in 4 attempts row 7 shows the seed
  En_Arrow live but `H` (held by Link), never released, with background-posted
  C+Left release. Source fires on C release after the nock. Human fire worked
  2026-10-08; this may be test-input specific. Logged in BUG_FEATURE_LOG.

Eighth candidate (Claude, 2026-10-12): `snap_npc` (1,792 B, master-only NPC
draw snapshot) moved to Low RAM carve 0x002FF580..0x002FFC7F after profiler
history; `snap_npc_n` bounds reads, filled before each kick, no cache handoff
needed. 219 tests pass; .bss ends 0x06083970 (1,680 B below SGL); host/core
audits 562/1,625 allowed multiplies, 0 failures; budget passes; 1,424 ISO files
match staging. Test ISO 6cdeb96e. Debug 6117a58c, Clean c3f29128, normal
staging (1,434 files) and Mednafen config e85e7a76 restored/verified.
Private-desktop runtime, mode M, spawn 9 (captures build/mednafen-test/speed8-*):
idle 17.6 FPS fr50.5 core23.5; forward run 10.0 FPS fr79.0 mp32.8 core41.0;
grounded slingshot first-person (v1 a2 b1) 16.0 FPS fr53.2 core31.6 join11.9;
after second C-left press 20.0 FPS vb3.0 fr53.3 (shot not visually confirmed);
X/B exit: Link visible and skinned next capture, exit frame 10.0, then 16.0.
cv0 on every row-15 sample. Aim near target; moving run still ~10 FPS
(master prep pd/pp + core ~41 ms). 20 FPS moving not achieved.

## Preserved Debug candidate 6117a58c

Target: 20 displayed FPS on Mednafen while moving/aiming, 50 ms whole frame.
Latest human shot before this batch: 8 FPS, core 62.1 ms, forest submit
22.9 ms, 1,756/1,756 vertices. The prior overlay lacked gather mode, so the
shot does not prove whether that view overflowed the 512-point cache or simply
referenced every vertex. M remains the human's fastest observed scheduling
mode and the default. Mednafen settings are unchanged. Its near-59-Hz output
counter is not the game's displayed FPS. Dialogue rows remain deliberately
unchanged. No Clean build; grab and held-stick repairs stay deferred.

Implemented together:

- Forest gather retains the 512-point high-WRAM path and adds a full-bank
  Low RAM spill. Larger views still transform only referenced points; no
  512-point fallback to the entire source bank. Count before copying, then
  copy each referenced point once and remap only visible indices. Restore
  before the next cull; source points/hidden indices stay unchanged. Empty
  views skip the forest submission. Modes 0/full and 1/in-place retained.
- Reclaim only unused CD-directory reservation tail: actual .lowfs is
  0x9DB0; reservation becomes 0xA000. Spill occupies 0x253500..0x259500,
  24 KiB, enough for every legal bank's 2,047 points. File/directory
  capacities and table addresses are unchanged. Compiler/linker checks
  enforce point capacity and nonoverlap; directory initialization stops
  before the spill. Existing CPU cache handoffs remain in place.
- Fx division replaces repeated general divide/CLZ/variable-shift chunks
  with one initial divide and exact shift/subtract remainder steps. Zero
  numerator also avoids the old potential shift-by-32. No float or software
  wide arithmetic. Target routine shrinks 208 to 136 bytes; own stack saves
  shrink 40 to 16 bytes. Disassembly confirms no helper calls in the loop.
  This is an instruction-path improvement, not a measured frame-time claim.
- Master actor scans stop at the last occupied slot, retaining holes and
  first-free allocation. With no live update callbacks, skip twelve empty
  category passes; when callbacks exist, preserve their original live order
  and mutation behavior. actor_update_slow retains the category-pass fallback.
  NPC mirror sync fetches the core view once per pass, with unchanged matching.

Verification: 151 focused tests pass, no skips. Includes >1.2 million exact
division oracle comparisons under UBSan, high/spill/overflow geometry restore,
full-size spill canaries, actor callback spawn/kill/profile mutation ordering,
4,000 randomized actor-pool operations, controls/aim/anchor and existing
render/job/music checks. Debug build has no error entries and a built line.
.bss ends 0x06082FC0 (4,160 B below SGL); .lowfs size 0x9DB0. Host/core math
audits report 539/1,607 allowed hardware multiplies and zero failures outside
libgcc. All 1,434 ISO payloads match staging exactly. SHA256:
6117a58cd8181717610bcb071383d273dc796f890ee40decba20f1df70505941.
Clean unchanged: c3f29128f85ad90110b7f05061e2c19b0b228eca59a58f9d8dbba9d6460090f2.
Evidence: build/fps20-{tests,build,host-audit,core-audit,disc}.log;
build/fps20-{host,core}.dis and build/game.map.

Runtime acceptance pending: Astra uses the temporary direct-Kokiri image,
same Mednafen settings. One combined run: idle, moving, aim/fire/shield,
full camera turn, house round trip. Compare whole-frame FPS/fr and rows
16-20. Row 20 g2 = high gather, g3 = Low RAM spill; g4 is an unexpected
capacity fallback. A full vertex count alone is now unambiguous with g.
Do not add overlapping phase times or claim 20 FPS from host tests/builds.

## Rendering/overlap follow-up (prior Debug candidate)

Larger batch after human "go big": latest moving screenshot reports mp57.1 ms,
pk18.4 ms, core64.8 ms; idle shot reused prep. Views/timer windows differ, so
this does not establish a controlled regression, but prep remains expensive.
Implemented a 512-point high-WRAM draw cache: gather visible points, rewrite
only visible face indices, restore them before the next rebuild. Source point
order never changes in this mode. Hidden polygons are never remapped. Overflow
leaves source indices intact and submits the full vertex bank. Cache hits reuse
the draw cache; bank reloads reset the pending-restore count after replacement.
Mode 2 default; old mode 1 and unpacked mode 0 retained. Uses 6 KiB extra high
RAM; depth/side scratch holds maps between prepares as before. Restore time is
included in depth/mp, so pk alone is not the total cost.

Player pose: dedicated hierarchy walker executes the same root/child/sibling
matrix stack, override and post callbacks as SkelAnime_DrawFlexLod. It omits
only the RSP matrix allocation/serialization and per-limb display lists that
were discarded. All gameplay anchors still run at the existing cadence;
active aiming still updates each source tick. Post-callback effects stay intact;
no boss walker changes. Host equivalence fixture compares callback events and
matrix state for both LODs, null callbacks, override suppression and post matrix
edits. Gather fixtures check restored geometry, hidden faces and overflow.
30 focused tests pass, one pre-existing migration skip; additional controls/
aim/anchor suite 81 pass. Debug built (built line, no error entries); .bss ends
0x06082DB0, 4,688 bytes below SGL. Host/core audits zero failures; all 1,434
ISO payloads match staging; Clean unchanged. SHA256:
c9cc6dc88eb842f06573624bf2e34301340a4f0bb2a202f0707fad5454eff6a5.
Evidence: build/big-render-{tests,controls,build,host-audit,core-audit,disc}.log.
Two extra-test WSL launches failed transiently; retry after build passed.
No FPS claim; held stick/grab bugs remain deferred by human. Human test moving,
aim/fire/shield, full camera turn and house round trip; capture rows 2, 18-20.

Human clarification after interaction trace: rock grab fails; held C-button
stick is invisible, unrelated. NPC talk was working. Withdraw general talk
failure/phantom stick interpretation. Screenshot p8000 h8000 iFF/00 tFFFF g1
m00 confirms A-only at source, empty hand, grounded, no talk offer/message.
Human says log these two bugs and continue performance; repairs deferred.

Moving-prep batch: replace first-occurrence vertex reordering with marked-set
prefix hole filling. The same visible vertex set now leaves all points/indices
untouched even when polygon order changes. Changed sets move only prefix holes
and remap all faces as before. Side-plane masks are computed once per vertex
using the same signed-short inputs/rounding, then combined by four ANDs per
polygon. No new scratch allocation or visibility rule. Depth timing now includes
side-mask arithmetic previously charged to partition; judge mp/whole frame.
16 focused tests pass, including 400 varying packed views/rooms, unchanged-set
no-write checks, and 60,000 conservative cull cases. Debug built with no errors;
host/core math audits zero failures, all 1,434 files match staging, Clean unchanged.
SHA256 4568aa9c8132d9e4741f29ee3d1ad0773f67ace1da9ec3e3353a85ae9e777861.
Evidence: build/moving-prep-{tests,build,host-audit,core-audit,disc}.log.
Runtime moving/aiming gain remains unmeasured.
Player anchor/aim cost remains open.

Latest human retest: idle 12-18.7 FPS, moving about 8 FPS; aiming also has a
large slowdown. Separate idle/run shots show master prep 0/32.7 ms, including
packing 0/11.1 ms and partition 0/16.7 ms; slave core 39.7/58.5 ms, forest
submit 3.1/2.5 ms. Running Player draw reads 24.8 ms. These overlapping and
differently averaged counters are not additive savings estimates.

Initial report (superseded by clarification above): cannot interact with signs, rocks or NPCs; apparent
stick-use action occurs, ownership uncertain. Exact physical trigger pending.
Source review confirms Saturn A maps to N64 A and X to B in player_source_pad;
this alone does not validate live inputs or identify the fault. Active aiming
requires the full source anchor pose every update; keep projectile/shield
anchors correct while optimizing. No gameplay fix established for these reports.

Interaction follow-up: row 21 retains the last source press/held masks, held
item/action, talk-offer actor and grounded state through release ticks, plus
live message mode. This distinguishes a wrong button from missing offers or
Player state admission. 80 control/aim tests pass, including actual input
consumer A-only delivery across skipped ticks. Diagnostic Debug built with no
error entries; host/core math audits zero failures; 1,434 files match staging.
SHA256 7f39dee3d5b5ddffb3815340ca2f46af54c59e250b1cef3933c7014ced921dbc.
Clean unchanged. Logs: build/interaction-tests.log and interaction-trace-*.log.
Human supplied row 21; interpretation and revised performance priority above.

Human tested the prior batch: up to 13 FPS idle; supplied non-dialogue shots
show 12.0 FPS/fr80.2 ms and 8.1 FPS/fr116.8 ms. Signs fall to 0.2 ms in those
views, while cel copies remain about 11-13 ms and forest submit 22-23 ms.
Human clarified that upper diagnostic rows freeze during dialogue; those chat
values do not establish stable live FPS or phase costs. Human explicitly says
leave dialogue refresh alone. It is unchanged. Prior fr is a smoothed FRT
metric; FPS uses a VBlank window, so their reciprocals need not match.

Implemented together, preserving the prior gains:

- Cel pixels use slDMACopy through jo_dma_copy, with slDMAWait before and
  after each transfer. The slot is marked current only after completion.
  Unchanged cels retain the no-copy path; palettes/dimensions still update on
  clip changes. npc_sprite_cpu_copy=1 restores the old CPU copy for diagnosis.
- Core sprite drawing resolves visible samples first and reserves all already
  resident hits before replacing anything. Misses rotate through unpinned
  entries instead of repeatedly replacing slot zero. This retains recent
  animation cels and prevents an early miss evicting a later actor's hit.
  Near-plane depth is refreshed before each submit. No animation tick cuts.
- Forest points are partitioned into a visible prefix, with every polygon's
  indices remapped, including hidden faces. SGL transforms only that prefix.
  All world geometry survives camera turns and room reloads. Packing reuses
  depth/side scratch after its last use, allocating no additional vertex bank.
  Unchanged camera views reuse the result; forest_pack_enabled=0 restores full
  transforms and invalidates the preparation cache on a mode change.
- New default M mode starts the core on the slave and prepares geometry on
  the master at the same time. Inputs are the same master-owned camera/LOD/
  bank state used by the previous slave prep, separate from core PlayState.
  Changed geometry queues a slave cache purge after the core job, before any
  later SGL forest transform; a busy SGL queue keeps transforms on the master.
  No early join or gameplay-rate change. L+R+Left cycles M/P/C, retaining both
  previous queue orders. Master preparation counts in whole-frame work and
  new mp, outside the old sc interval; smaller sc alone proves no gain.

Row 20: geo vUSED/TOTAL pk mp (per-refresh means; times in 0.1 ms). Use this
with rows 13-19 and whole-frame FPS to judge the combined candidate.

Verification: 81 focused tests pass without skips (rendering, sprite libraries,
actor lifecycle/collision, signs, slave jobs, source input and scene exits).
New tests check 400 changing synthetic views/rooms, all hidden-face coordinates,
empty/all-visible sets and scratch boundaries, DMA completion/no-copy behavior,
cache reservation/rotation, and master-prepare/purge admission. Existing sprite
scene fixture was updated to the already-current API32 room/spawn signature,
save entrance and fixed-camera flag contract; assertions retained.

Debug build has the built line and no error: entries. .bss ends 0x060813A0,
11,360 bytes below SGL. Host/core math audits: 539/1,607 allowed hardware
multiplies, zero failures. All 1,434 ISO payloads match staging. Debug SHA256:
5f3eec2936d4746208d5732831134ecdca905a789d52c82db63df4c8f7234854.
Clean unchanged at c3f29128f85ad90110b7f05061e2c19b0b228eca59a58f9d8dbba9d6460090f2.
Logs: build/render-batch-tests.log, render-batch-build.log,
render-batch-{host,core}-audit.log, render-batch-disc.log. Existing Gossip
Stone asset omissions remain; no new runtime asset file introduced.

No emulator run by Astra. Human test one candidate: same idle/moving camera,
turn fully around (hidden geometry returns), NPC animation/aim/fire, and house
round trip. Capture rows 16-20 outside dialogue. FPS gain, DMA display integrity
and overlap behavior remain target-runtime acceptance gates; 20 FPS not claimed.

## Earlier Astra combined Debug batch

Human authorized a combined pass after the sign sample (fr114.0, sg29.7 ms).
No Clean rebuild until Debug is ready for the human's 20 FPS test. No emulator
launched or controlled. Runtime gain is not established by the changes below.

- Signs: a conservative origin-centred radius derived from all piece vertices
  rejects off-screen whole signs before submissions. Intact 0x7FF masks use
  one geometry-only merged mesh (66 points, 87 polygons); cut/fallen pieces
  retain original transforms and geometry. Attributes refresh after every
  original texture upload, without allocating duplicate textures. Allocation
  failure falls back to original pieces. Scene teardown frees the batch.
- C actor pool: default storage moves from uncached cart to high WRAM; reserved
  cart carve remains available via CART_ACTOR_POOL=1, with a mode-stamp rebuild.
  Pool is master-owned, never DMA/slave-written; no mixed cached alias/purge
  scheme introduced. Capacity, category order, spawn/kill semantics unchanged.
- Handle resolution: a 128-byte direct-mapped slot hint validates full live
  identity, profile and kill state on every hit; collisions fall back to the
  original scan. Pool reset clears hints. This reduces repeated NPC focus and
  C actor/contact lookups without removing simulation work.
- NPC draw fetches position/yaw from one npc_at evaluation, preserving live
  cutscene positions and turned facing. Core NPC ownership remains unchanged.
- Additional correctness issue found: sign partFlags used ENTRY->prop_query
  while the slave could mutate actor lists. The existing pre-kick snapshot
  now also captures authored forest sign masks. Busy queries read only those
  masks; idle queries retain live behavior. This carries the same previous-
  update visual latency as the other draw snapshots. Snapshot query cost is
  outside sg, so judge whole frame, not sg alone.

Diagnostic fallbacks: dosei_sign_slow bits 0/1 disable cull/merge respectively;
actor_resolve_slow=1 restores scanning; CART_ACTOR_POOL=1 restores pool
placement at build time. Existing prep-first toggle remains. No gameplay
ticks, story, contacts or C-only actors removed: ownership review does not
justify deleting their remaining step work. Scheduling/core hot-code changes
remain measurement-dependent after this combined candidate.

Host verification: 66 tests pass, no skips (sign batching/allocation failures,
cut/fallen fallback, NPC pose equivalence, sign snapshot busy ownership, actor
identity/collision lifecycle, slave jobs, scene decoding, source input/exits).
Log: build/batch-speed-tests.log. Debug build/audits and ISO verification logs:
build/batch-speed-build.log, batch-speed-{host,core}-audit.log,
batch-speed-disc.log. Final Debug build has the required built line and
no error: entries; .bss ends 0x06080C50, 13,232 bytes below SGL work area.
Host/core math audits: 537/1,607 allowed hardware multiply sites, zero failures;
audit self-tests pass. All 1,434 ISO payloads match staging (ISO names normalized
to uppercase for the staging inventory comparison). Debug ISO SHA256:
2650ba8a8a3f9a2f161a756710a82328e6a44c315844f22f84c3e675e933525d.
Clean was neither built nor overwritten; SHA256 remains
c3f29128f85ad90110b7f05061e2c19b0b228eca59a58f9d8dbba9d6460090f2.
The two pre-existing Gossip Stone converter omissions remain in the wrapper
log; no new asset conversion omissions introduced by this code-only batch.

Human combined test: same Kokiri camera idle/moving and facing signs; sign
reading/cutting, aim/fire, room/scene round trips, NPC talk/target/contact.
Capture rows 9 and 13-19. Target is sustained 50 ms / 20 FPS; no prediction
of reaching it without runtime evidence. Real hardware remains untested.

## Astra step-3 review: latest screenshots and current code

Keep Low RAM geometry: reported whole-frame gains and successful music check
support the move in tested scenes. No runtime edits or image rebuild here.
Independent WSL run: 14 timer/job and scene-decoder tests pass, recorded in
build/step3-review-tests.log. Scene tests stub bank_allocate; target-only
allocation is not host-exercised. Production has forest size and carve bounds
checks and retains normal bank-load/prepare purge points. Other scenes and
Clean aim/fire/exit/reload acceptance remain open.

Main finding: world_props_draw.c:205 ends PS_DWP halfway through the function.
Drops, signs, enemy/boss paths, doors and chest loops remain inside PS_DNPC.
Therefore np minus wc/wp is NOT isolated NPC work. Time the complete props
call, split its untimed remainder, then profile NPC visibility/sample/upload
work if still expensive. No shadow/actor cuts justified by that residual.

Latest Kokiri screenshot: fr1212/wk1093/sy119 = 121.2/109.3/11.9 ms;
np496/wp70 = 49.6/7.0 ms; spr n3/sh7/put0/rs0 = three instrumented styled
sprite calls, 0.7 ms shadow time, under 0.1 ms submission and deferred resolve
each. These counters do not cover every shadow caller, but they do not support
shadow thrashing as this sample's major cost. Zero is rounded, not no calls.
cel137 = 13.7 ms cel copies, unlike earlier low-cel samples; this is a global
nested timer, not an additional disjoint phase. Measure repeated samples.

jw0 means negligible final join wait, not that faster core code cannot help:
shared-memory contention and slave queue occupancy may affect master cost
and forest transform ownership. Master profiling remains next priority.
Latest slave cu566 is 56.6 ms, not the earlier 71 ms. Title fr470/fps20.0/vb3.0
and Kokiri fr1212/fps8.0/vb7.5 use instantaneous FRT versus windowed VBlank
metrics; their reciprocals need not match. Human owns further runtime tests.

## Follow-up review: no crash; Mednafen about 5 FPS versus Kronos 20

Human now reports no crash after Claude's FRT repair. This supersedes the
pending crash retest below, but does not establish route/aim acceptance or
a timed endurance run. Review only: no runtime code, emulator settings or
disc changed by Codex in this follow-up.
Human clarifies 5 FPS is an estimate of motion, not a measured counter;
slowdown persists with Link off-screen. Hiding Link does not stop Player
update, collision or scene work, so this does not isolate a rendering cost.

The byte-read repair addresses the demonstrated false watchdog time jump.
Independent WSL rerun: all 6 `test_speed_jobs` cases pass; audit self-tests
11/11 pass (`build/frt-review-tests.log`, `frt-review-audit-tests.log`).
No new crash defect found in that change. This is not a fresh target build
or an independent emulator reproduction.

Remaining review finding: slave timing can still undercount long work.
`oot_core_host.c:1552` and `kokiri_sgl.c:2170` subtract two 16-bit counter
samples. An update/preparation lasting a whole counter period loses that
period; at the code's /8 calibration this is only about 18 ms. Actual slave
prescaler must be recorded before interpreting S %. Master callback share
also includes waiting, and slave source subphase callbacks return zero.
These counters cannot yet identify the 5 FPS bottleneck. Preserve slave jobs;
first obtain wrap-safe job durations and separate work from join waits.

Observed configuration evidence:

- Configured custom Kronos: `build/kronos-fix/kronos.ini` has
  `General\\SH2Cache=false`. This is configuration evidence, not a captured
  effective runtime setting.
- Mednafen 1.32.1 startup log records the usual Clean cue, 4 MiB expansion
  RAM and `CPU Cache Emulation Mode: Data only`. Launcher has no extra args.
- Core executes at cart address `0x02760000`; Player state/slave stack use
  low work RAM. Cache and memory timing differences are plausible costs,
  not measured attribution of the fourfold gap.

Distinguish host emulation speed from the game's own draw rate first.
Mednafen Shift+F1 shows virtual, rendered and blitted FPS, top to bottom
([manual](https://mednafen.github.io/documentation/)). Record all three plus
game VDP1/VDP2 counters, same scene/camera/image, idle and moving, and whether
audio slows. A virtual rate far below the expected console refresh points
to host emulation speed; full virtual refresh with about 5 game frames points
to work/waits inside the emulated game. Mixed limitations remain possible.
Mednafen documents heavy host CPU requirements and explicitly warns that
even its Saturn slowdown is not an authoritative real-hardware measurement
([Saturn manual](https://mednafen.github.io/documentation/ss.html)). Neither
emulator result alone proves Saturn will sustain 20 FPS. Exact cause of this
gap remains unmeasured; no blanket cache rollback or timing workaround justified.

## Root cause and fix — FRT word read (Claude, 2026-10-12)

**Status: fixed in code, Clean image rebuilt; human now reports no crash.**
Detailed route/endurance coverage unspecified; FPS follow-up above remains open.

Evidence. Human error values `stalled (31, 52, 30, 19, 35, 47, 49...)`. Progress
starts at 1 and steps every 64 vertices (about 33 after the depth pass), then in
partition/fog. Varying N = the slave was running and advancing; the watchdog
fired at random points. Kronos was the only emulator used for the 10->20 FPS
baseline.

Cause. `frame_timer.c` read FRC with `*(volatile uint16_t *)0xFFFFFE12`
(`_read_ticks`: `mov.w @r1`). The SH7604 FRT is an 8-bit module: read FRCH
(latches FRCL into TEMP), then FRCL. Mednafen (`ss/sh7095.inc`) answers a word
read at 0x12 with `FRC >> 8` only; Kronos returns the full count. So the timer
saw a 0..255 counter, `read_ticks` counted each 255->0 as a 16-bit wrap
(+65536 ticks = 293 ms), and any wrap inside `prep_wait` produced ~292 ms of
false elapsed time, over the 250 ms limit. Wraps occur every ~293 ms real time,
hence "error returns almost immediately". House skips scene prepare; the core
join rarely spins. The earlier 250 ms total version failed the same way.
SGL's slave queue (slSlaveFunc -> SINIT, SlaveControl, sbMakeDMATable, slSynch
reset command 44) was checked in disassembly and is not involved.

Fix.
- `frame_timer.h` `frame_timer_frc()`: byte reads FRCH, FRCL, FRCH again (+FRCL
  to clear the latch), retry if the high byte moved (an ISR FRCH read between
  our bytes re-latches TEMP). Per-CPU on-chip register, slave-safe.
- `frame_timer.c` `read_ticks`/init, `kokiri_sgl.c` `frame_slave_job`,
  `oot_core_host.c` `slave_job_body` use it. No other FRT word reads remain.
- Watchdog, timeouts, slave jobs and `SLAVE_JOBS` default unchanged.
- `tools/audit_oot_core_wide.py` now FAILS on word/long loads from the FRT
  block (0xFFFFFE10-1F); it flags exactly the three old sites in
  `exit-host.dis` and none in SGL or the core. Self-test 11/11.
- Tests (`test_speed_jobs.py`): monotonic `read_ticks` under Mednafen latch
  semantics with injected ISR re-latches (control without the retry fails);
  source guard against 16/32-bit FRT pointers.

Verification. WSL `./build.sh --clean --quick OOT_CORE=1` (core unchanged):
`built:` line, no errors, .bss ends 0x0607D370 (27,792 B below the work area).
New disassembly: `frame_timer_frc` is `mov.b` fe12, fe13, fe12, fe13 in order.
Audits (`build/frt-{host,core}-audit.log`): host 461 / core 1,604 allowed
multiplies, 0 failing. 1,434 ISO files match staging, API32, core 549,980 B;
ISO SHA256 `52159b25e279f63432c691fec4fbf2d2128d1eaccb1ae2618c93c70eb2517a20`
(`build/frt-disc-check.log`). Focused host tests 107 pass / 1 skip
(`build/frt-tests.log`; WSL needs `DOSEI_OOT=/mnt/d/...`). No emulator run.

Consequences. All earlier Mednafen frame-timer/profiler readings (phase rows,
master/slave %) were wrong; re-measure. Kronos numbers were unaffected.

Human check (usual Clean image, Mednafen, slave jobs on): title idle 1+ min,
Kokiri walk/turn, house round trips, then exits and aim/fire. Note real FPS.
If any watchdog error remains, report its exact text and number; the next
step would be cache-through slave job/phase breadcrumbs.

### Follow-up: Mednafen speed diagnosis build (Claude, 2026-10-12)

Human: crash gone. Codex review: Kronos runs with SH-2 cache emulation off;
slave timer loses counts; separate emulator speed from game speed. Debug image
`build/game.cue` (and matching Clean) rebuilt: slave FRT /128 per job, slave
core profiling clock, rows 16-17 (VBlank pacing, master waits on the slave,
slave job times). Guide: DEBUG_OVERLAY.md "Mednafen reading". Debug .bss ends
0x0607E360 (23,712 B spare), Clean 0x0607D5A0 (27,232 B); audits 0 failing;
1,434 ISO files match staging for both (Debug SHA256 `1c6ca04f...`, Clean
`4da0e608...`); focused WSL tests pass, 1 skip. No emulator run; no reading yet.

First readings (human, 2026-10-12, ms). Mednafen title: fps 10 (vb 6.0),
fr 94 = wk 46 + sy 48, master waits 42 for slave scene prepare (slave pr 43).
Mednafen Kokiri: fps 5 (vb 12), fr 187 = wk 151 + sy 35; master: prepare
wait 41, npc_draw 50, step 31, Link submit 12; slave: prepare 38, core 55
(actor updates 23 per update), skin 3. Kronos same build: 20 FPS (vb 3.0)
both places; title prepare 17, Kokiri core 6.8, npc_draw 10.8, Link 7.6.
Mednafen costs are 2.5-8x Kronos. Shift+F1 virtual FPS not yet reported.

Findings and changes (built, not run):
- Forest bank (points/polygons/attributes/tiles/CLUTs) came from Jo's cart
  heap, which hands out cache-THROUGH addresses (0x224xxxxx): every scene
  prepare and SGL transform read went uncached over the A-bus. Kronos does
  not charge for that. `kokiri_sgl.c bank_allocate()` now uses the cached
  alias; master purges after bank loads; slave purges per prepare job and
  SGL purges it every frame (sbMakeDMATable CCR write). Hyrule Field pieces
  are written into the same bank by the CPU (covered).
- Child Link floated: the bridge exported the raw jointTable root. Source
  Player_OverrideLimbDrawGameplayCommon scales the child root by 0.64 (16/25)
  and subtracts unk_6C4. Applied in `bridge_player_source.cpp` (unk_6C2 tilt
  case not applied). Full Clean rebuild (core + packs).
- Builds: Debug .bss 0x0607E360, Clean 0x0607D5C0 (27,200 B); core 550,132 B;
  audits 0 failing (core 1,607 allowed multiplies); Clean 1,434 ISO files match
  staging (SHA256 `00373050...`); Debug matches except `0.BIN`, rebuilt by the
  later Clean build (Debug SHA256 `a996c8bf...`). 124 focused tests, 2 skip.
Next: Mednafen Debug reading at the same spots (expect `S pr` well below 38)
plus Shift+F1.

Second reading (Mednafen, cached bank + child root): child Link grounded.
Title fps 12 (vb 5.0), fr 78, slave prepare 39.5 (was 43): the cached bank
helped little, so uncached bank reads were not the main prepare cost.
Kokiri fps 7 (vb 8.5), fr 154 = wk 137 + sy 17; master waits 29 at prepare
although the slave's prepare was reused (0): it waits behind the core job
(76 ms, actor updates 30 per update, Player alone 20.8 per update vs 3.3 on
Kronos). npc_draw 46 (world props 7). Vb counts emulated VBlanks, so these
are Saturn-time costs independent of PC speed.
Third Debug build (row 18): prepare depth/partition/fog split on either CPU,
fog tiles rewritten, NPC cel copy time/KB into VDP1 VRAM. Suspects: fog
palette and cel writes into VDP1 VRAM (slow while VDP1 draws), cel source
read uncached from the cart heap. Debug .bss 0x0607E5B0, Clean 0x0607D750
(26,800 B); audits 0 failing; both ISOs matched staging after their builds
(Debug `d09062ac...`, Clean `b53e963f...`); 124 tests, 2 skip.
Player update cost (core code in cart RAM; Low RAM is full) is the other
large item and needs its own plan.

Third reading (Mednafen, row 18). Title: prepare depth 10.7, partition 25.5,
fog 3.2 (28 tiles), cel 0. Kokiri walking: fps 6 (vb 10), prepare 39
(10.8/26.0/2.3, 13 fog tiles), cel copies 1.6 ms / 2 KB, npc_draw 46.6 (world
props 5.7), core 47 (Player 10.9 per update), host collision queries 10 per
refresh. Conclusions: VDP1 palette/cel writes are NOT the cost (earlier
suspicion wrong). Depth ~150 cycles/vertex and partition ~450 cycles/polygon
match streaming the bank from cart RAM: the cache cannot help single-pass
reads, so the cached alias gained little. The core also runs code and much
data from the cart. npc_draw's own work is small (cels, 10 queries); its
4x inflation fits master bus stalls while the slave streams the cart.
Cart (A-bus) traffic is the common cause. Options recorded in the decision
below; nothing implemented beyond diagnostics.

Human plan (2026-10-12), separate experiments; report whole-frame change, not
smaller waits; no gameplay cuts, no permanent slave rollback; keep slave gains:
1. Baseline: slave timer wrap fixed (/128); record whole frame, core, prepare,
   transforms (`sb`, `sy`) and waits, same Kokiri camera idle and moving, plus
   Mednafen Shift+F1 virtual FPS. 2. Job order alone (prepare before core
   where dependencies allow; keep only if the whole frame improves).
   3. Forest geometry into Low RAM alone (move cold tables to the cart; check
   space, cache visibility and other scenes). 4. Combine proven gains; verify
   movement, aim/fire, exits, scene reloads. 5. Hot core code into fast RAM
   after profiling; keep stack/heap headroom. Real Saturn needed for a final
   hardware claim.
Steps 1-2 built (Debug `build/game.cue`, not run): row 18 `sb`, live job-order
toggle L+R+Left (row 16 `C`/`P`). Dependency check: scene prepare reads only
camera/LOD/bank state the master sets before either kick; the core does not
write them during its update, so order is free. Clean keeps the core-first
order. Audit false positive (literal pool after rts) fixed with a self-test.
Debug .bss 0x0607E6A0; Clean rebuilt to match (staging matched after each
build; Clean `789f4fc3...`); audits 0 failing; 170 focused tests, 11 skip.

Step 2 result (Mednafen, Kokiri, same spot; ms). Core-first C vs prepare-
first P: moving fr 173.6 -> 154.8 (fps 5.2 -> 6.3, vb 11.5 -> 9.5); idle
133.2 -> 125.9 (fps 7.0 -> 7.5). Whole frame improves in both, so P is now
the default (Debug L+R+Left still flips to C). In P the master transforms the
forest itself (`sb` 24.5-30.6) while the core holds the slave; `sy` fell
(19.5 -> 10.1 moving).

Step 3 built (not run): forest POINT/POLYGON/ATTR tables (24.6 + 38.3 +
23.0 KB) moved from the cart heap to Low RAM 0x259500-0x26E480
(`RAM_LOW_FOREST_BANK`, the former MUSICTRG slot); MUSICTRG.BIN (~90 KB,
read a few rows per tick) now loads once into a cart heap block; tile
records and CLUTs stay in the cart (cached alias). Coherence unchanged:
CPU writes only, slave purge per prepare job, SGL slave purge per frame,
master purges after the prepare and after each bank load. Hyrule Field
pieces are copied into the same tables. Compare against step 2's P numbers
(and C via the toggle). Debug .bss 0x0607E690; Clean 0x0607D760 (26,784 B),
`69318f89...`; staging matched after each build; audits 0 failing; 170
focused tests, 11 skip.

Step 3 result (Mednafen, ms; vs step 2 P). Title fr 78 -> 47 (fps 12 -> 20,
vb 3.0), prepare 39.5 -> 25.4 (depth 5.9, partition 16.7, fog 2.6). Kokiri
moving fr 154.8 -> 136.6 (fps 6.6, vb 9.0), slave prepare 46 -> 36; idle
125.9 -> 120.4 (fps 8.0, vb 7.5). Whole frame improves: keep. Human: music
loads fine. Critical path is now the MASTER: in Kokiri idle the core (~71
ms on the slave, Player 14-16 per update) finishes before the join (jw 0);
master work wk 109-128 = npc_draw ~39 own (+ world props 5-7), step loop 31
(C gameplay 11, puzzles/actor_sys 10), forest submit with the master's own
transform 24, Link 6-14. These prioritize master profiling; they do not rule
out gains from reduced core contention. NPC residual includes unmeasured
world-prop work, as the Astra review above explains.
Fourth Debug build (row 19 `spr n sh put rs`): sprite count, shadow lookup+
submit, slPutSprite time, and the shadow floor queries resolved after the
join. The shadow floor cache has 16 cells; ~20 shadowed actors may thrash it.
Debug .bss 0x0607E7C0; Clean 0x0607D810 (26,608 B, `e401ad76...`); audits 0
failing; 170 tests, 11 skip. Remaining step-4 checks for the human: movement,
aim/fire, exits and scene reloads on the combined build. Remaining suspects: core 55 ms (code and data in cart RAM),
npc_draw 50 ms, other cart-heap data read every frame.

## Claude handoff — latest Mednafen retest failed

*Superseded by the root cause above; kept as history.*

**Blocking and unresolved.** After API32 follow-up, human says: "Not fix.
Write report for Claude fix." Codex stops implementation at human request.
The progress-watchdog change did not resolve the reported failure. No new
screenshot or stalled-progress number was supplied. The latest message does
not separately confirm or reject the exit/aim changes. Do not call this merely
awaiting its first runtime test, or claim the Mednafen crash is fixed.

### Reproduction and constraints

- Original Mednafen error: `In prep_wait(): slave scene prepare did not finish`.
- Happens on title screen and repeatedly in Kokiri Forest. Press Start to
  continue; error returns almost immediately. Link's house was okay.
- Screenshot: dynamic memory 58%, sprite memory 0%, VRAM 55%, master 97%, slave
  33%. These readings do not establish cause or precise frame timing.
- Preserve real Player/core collision and useful slave jobs. Human reports
  Claude's work raised idle FPS from 10 to 20; game jobs previously did not use
  the slave. A permanent all-slave rollback does not meet the request.

### Code path and failed attempt

`game/src/main.c:419` queues core update then scene prep. Actor drawing follows;
`kokiri_scene_draw` waits for prep before scene submission. Core join occurs
later at `main.c:565`. A prep timeout could mean prep is stuck, still queued
behind another job, or completion/timing is wrong. Its label does not identify
the failing worker. House success is consistent with skipping scene prep, not
proof the core or queue is sound.

- `game/src/kokiri_sgl.c:1828`: `scene_prepare(bool on_slave)`, including LOD,
  depth, culling/partition, sort keys and fog. Fog writes VDP1 palettes directly.
- Same file: callback 2161, kick 2183, SGL queue drain 2203, `prep_wait` 2214.
- `game/src/oot_core_host.c:1542`: core worker; dedicated low-RAM stack wrapper
  follows; kick/join 1608/1622. Core join still has a separate 250 ms watchdog.
- `game/src/link_anim.c`: skin job/join. `frame_timer.c`: master FRT extension
  and conversion. `ram_low.h`: dedicated slave stack carve.

Codex removed shared `prep_on_slave` and redundant `job_prep` flags. Timer
ownership is now an argument, and callback always prepares then publishes
completion. Cache-through progress starts at 1, incrementing periodically in
depth, partition and fog. Wait allows 2 seconds before first progress and
250 ms without further progress. Start resets the diagnostic deadline without
resubmitting work. New error is `slave scene prepare stalled (%u)`.
**This improved detection, not a proven root-cause repair.** Host watchdog
tests simulate progress/stalls; they cannot establish SH-2 cache coherence,
SGL queue dispatch, bus behavior or Mednafen execution. No emulator was launched
or controlled by Codex. No cause was established before handing back the build.

### Next checks — hypotheses, not findings

1. Capture new stalled-progress value and verify loaded image. Zero means no
   heartbeat observed; positive means callback entered. Count does not uniquely
   identify a phase. Add cache-through markers for core start/end and prep
   LOD/depth/partition/fog/end if needed.
2. Establish whether title repro actually queues a core job. Check SGL queue
   pointers, callback order and outstanding skin/core work. Inspect stack
   bounds, shared-data lifetime, publication and cached aliases. Current target
   disassembly is `build/exit-host.dis`; `perf-review-host.dis` is older, with
   different addresses.
3. If prep starts, find last advancing phase. Check geometry bounds, palette
   writes and concurrent master access. Verify watchdog elapsed time against
   master FRT settings/wraps. Do not just increase timeouts again and call it fixed.
4. `SLAVE_JOBS=0` exists as a diagnostic control, not the final solution.
   Isolate individual jobs as needed. Never rerun prep on master while its
   slave callback can still mutate the same bank.
5. Require live title/Kokiri stability, then house round trips, movement,
   Ranch/Domain/bridge exits and aim/fire, with slave-enabled FPS recorded.
   Passing builds/tests already failed to predict playability here.

### Artifact and preservation

Usual `game/build/game-clean.cue/.iso`: API32, OOC `0x4f4f4303`, slave enabled.
ISO SHA256 `c4c3dfd4fb5f37dcad31fa614f90d00de436211087608ca6ac4c5b5407a76896`.
118 host tests pass, one legacy collision wrapper skips; host/core math audits
pass; 1,434 ISO files match staging. Core 549,980 B; main .bss 0x0607D250,
28,080 B below SGL. Logs: `build/exit-regression-tests.log`,
`build/exit-disc-check.log`, `build/exit-{core,host}-audit.log`,
`build/perf-review-build.log`. These are host/build evidence, not runtime proof.

Shared tree is dirty/uncommitted, based on `45e668f`; do not reset it.
Preserve C-slot/aim repairs, uncached core busy readers, shared pose key,
collision-stamp initialization and removal of duplicate proxy tool timers.
Follow-up also imports/binds/bounds exit lists, passes entrance spawn/respawn
identity, and removes aim overlay/held first-person arrow while retaining fired
projectiles. Implementation details follow below.

Build through WSL Linux; see BUILD.md. Human owns ordinary emulator tests.
Do not close/control their emulator or overwrite a mounted Clean image.
This handoff changes documentation only; no new runtime repair or rebuild.

Human baseline: Claude's work doubled observed frame rate from 10 to 20 FPS;
the second SH-2 was not previously used by the game jobs. The initial report
distinguishes idle 20 FPS from movement and reports mixed C items and missing
first-person aim. Preserve the dual-CPU schedule and gains. No emulator launched
in this review; no new measured FPS claim.

## Scope and disposition

Reviewed `1311746..45e668f`, including the real Player/collision cutover bundled
in speed pass 1, all three speed passes, and the slave rollback switch. Checked
the local original Player/camera/projectile sources against the adapters.

| Area | Finding / disposition |
| --- | --- |
| Source Player C items | **Fixed:** host slots are down/left/right; source `sItemButtons` is B/left/down/right. Swap the first two only at the save boundary; apply the inverse for bottle writeback. Physical pad mapping and HUD remain unchanged. |
| First-person admission | **Fixed:** `Camera_RequestMode` returned NORMAL for every request, so `Player_ActionHandler_13` rejected aim. Acknowledge source mode and present source focus/rotation through API31. |
| Saturn aim controls | **Fixed in adapters:** translate tap-to-ready/tap-to-fire into source button holds/releases at 20 Hz. Source owns animation, ammo, projectile creation and release. Wait for hook return before synthesizing rearm; a C press during flight retracts it. Digital/analog look reaches Player, camera and crosshair use its focus. Cancel/blocked state clears the latch. |
| Input cadence | **Fixed:** retain short presses until a source update, include them in held state for that update, derive releases from the last consumed pad, and preserve host C/attack edges across no-step frames. R now has a press edge. Reset input on scene teardown. C item forwarding happens after legacy `gameplay_step`, preventing duplicate tool use. |
| Slave ownership | **Fixed:** busy was written through an uncached alias but three guards read the cached byte. Kick, entry audit and join now all read the uncached flag. Keep snapshots, private stack, purges, queued SFX, bounded waits, Link skin and scene prepare jobs. |
| Source/proxy tool overlap | **Fixed:** proxy `OotCore_ToolStep` still changed source `unk_A73`, duplicating Player's release timer. Proxy carry/return bookkeeping is now compiled only for the proxy. Sprite contact/attachment and audio work remains. |
| Link pose cache | **Fixed and reduced storage:** synchronous and slave entry points shared output buffers but had separate last-pose keys. One shared 132-byte key prevents A/B/A stale-pose reuse and removes the second key. |
| Sparse Player anchor pass | **Retained:** do not add a full skeleton pass to every moving frame. Translate cached focus with world movement on skipped idle passes, force the initial and first-person passes, retain full passes for active weapons/carry/shield. Idle pose detail still refreshes every eighth source update. Clear stale draw timing when skipped. |
| Collision stamp table | **Fixed:** new polygon-check tables were uninitialized while the new stamp path skipped clearing. Initialize once on allocation; retain cheap query stamps and wrap clear. Guard large `chkDist` ceiling conversion against signed overflow. |
| Integer collision fast paths / Q15 / constant division | Retained. Bounded integer rejection, source fallback near edges, native SH-2 constant multiply/divide lowering remain. Collision probe differences are recorded separately; this is not full float parity. |
| SGL scheduling and side cull | Retained. Scene prepare precedes forest submission; bounded queue drain gives SGL its slave transform opportunity. Existing conservative side-plane test retained; no renderer/warp rewrite. |
| Scene-local portal/door lists / prop scan | Retained. List overflow falls back to full scan; authored order/filtering preserved. No actor-cap reduction. |
| HUD/sky caching | Retained. Hearts composed in WRAM and copied to inactive VDP2 bank; existing visible/magic/pulse keys remain. |
| Shadow floor cells | Retained; follow-up: cache lacks dynamic-floor and same-scene room invalidation. Visual approximation only, not authoritative collision. Link uses source floor height directly. |
| Frame catch-up | Retained. Host remains 30 Hz, source 20 Hz, maximum three host steps/two source updates per displayed frame. Below the catch-up budget, simulation slows; 20 FPS idle is not moving-scene acceptance. |
| Memory relocation / frame bank | Retained existing 0xA0000 core and 0x30000 scene carve and normal guards. Whole-bank residency is still demand-loading migration debt. No new heap or actor cap cuts. |

## Verification

Host: 103 focused cases, **102 pass / 1 skip**. The skipped legacy migration
wrapper requires `build/cd/S1.COL`, now retired by core collision; the separate
`run_bg_port_probe.sh` was executed against `build/disc-retired/S1.COL`.
New executing regressions cover cached/uncached disagreement, shared skin-key
alternation, stamp initialization/600 queries/wrap, source input cadence,
hook return, camera admission and C-slot/aim-axis mapping.

Collision: Fx versus source-float remains 0 floor / 7 wall / 0 ceiling / 3 line
differences; the known line hit/miss remains. Dyna owner-local ID/removal/reuse
contract passes; the 185-row shim scenario retains one known elevated-platform
discrepancy beyond ±2. Wrapper comparisons retain existing differences. These
are recorded limitations, not a claim of full collision parity.

Target: usual WSL Clean build succeeds with slave jobs enabled, API31 host/core
and rebuilt scene packs. Main BSS ends `0x0607D1F0`, 28,176 B below SGL. Core
binary 549,804 B; this excludes BSS and is not a full memory retention measure.
Both matching ELF audits have zero forbidden sites: core 1,604 allowed native
multiply sites, host 461. All **1,434 ISO files match staging** byte-for-byte.
ISO 81,928,192 B, SHA256
`a01a6989330723809976034cd6556efc08f7801e518e046f49b26da14f978eff`.

Logs: `build/perf-review-tests.log`, `build/perf-review-collision.log`,
`build/perf-review-build.log`, `build/perf-review-{core,host}-audit.log`,
`build/perf-review-disc.log`. Existing Linux fixtures needed `gcc` discovery,
`-fPIC`, current source save fields and updated region addresses; fixes preserve
assertions rather than turning failed checks into skips.
Two pre-existing Gossip Stone display-list extraction omissions are still
reported by the asset wrapper. They are not new item/aim regression findings.

## Remaining acceptance and next useful performance work

### Follow-up: exits, aim obstruction and Mednafen

Human says the initial changes seem okay, but reports a large aiming arrow,
multiple exits returning to Lost Woods, and repeated `prep_wait` timeout errors
in Mednafen's title/Kokiri scenes. Link's house works. No broad acceptance.

- Removed the first-person hand/tool overlay and stopped loading its atlas.
  Suppress the held arrow sprite only while in first person; the source actor,
  ammunition, release, flight, trails and collision remain active.
- `play->exitList` was never initialized after the real Player cutover. Player
  dereferenced a null scene list when touching exit polygons. OOC format 3 now
  carries exact source exit lists for all scene layers, validates their ranges,
  binds using source alternate-header fallback, and bounds Player exit indices.
  API32 also passes `play->spawn` for special return entrances. Destination
  entrance identity now precedes Player initialization, with recovery restoring
  the old identity before reloading the old scene.
- Scene preparation now receives timer ownership as an argument, removing the
  shared cached mode flag. Its callback always publishes completion. Heartbeats
  during vertex/cull/fog passes let the watchdog distinguish progress from a
  stall: 250 ms without progress after start, 2 s while queued. A stalled job
  reports its progress value; Start resets the diagnostic deadline without
  resubmitting work or letting both CPUs mutate the bank. Slave jobs stay on.
  This is a robustness fix and diagnostic improvement, **not proof the reported
  Mednafen failure is solved**. No emulator was launched or controlled.

Host: 19 exit/import/actor-pack/job checks pass, including retail Ranch, Zora's
Domain and bridge-entrance lists, empty/absent layers, index bounds, malformed
OOC rejection and a progressing preparation exceeding the old total deadline.
Expanded host batch: 118 pass, one old collision wrapper skips (the prior
standalone collision evidence remains unchanged). `build/exit-regression-tests.log`.
Target: usual Clean API32/format-3 image rebuilt, slave enabled. .bss ends
0x0607D250 (28,080 B below SGL), core is 549,980 B. Math audits: core 1,604 and
host 461 allowed hardware multiply sites, zero forbidden sites. All 1,434 ISO
files match staging; image is 81,944,576 B, SHA256
`c4c3dfd4fb5f37dcad31fa614f90d00de436211087608ca6ac4c5b5407a76896`.
Logs: `build/exit-disc-check.log`, `build/exit-{core,host}-audit.log` and
`build/perf-review-build.log`. Subsequent Mednafen retest failed; see handoff
above. Live route/aim acceptance remains unspecified.

Human check the usual Clean image: each C direction against its HUD assignment;
bow, elemental arrows, slingshot and hook/longshot tap/aim/fire/repeat/cancel;
digital and analog look; Z-target use; shield; bottles; pause/room transitions.
Compare idle and moving FPS from the same camera/scene as the 10→20 baseline.
Host checks cannot establish projectile/crosshair alignment or target performance.

The next performance work should measure movement, held tools and populated rooms
with the slave enabled. Reuse safe unchanged work and reduce the source anchor
pass cost before changing clocks or throttling gameplay further. Core subphase
timers return zero while on the slave (`host_ticks`); total slave job timing is
separate and its 16-bit FRT measurement can wrap. Fix measurement before attributing
moving-frame cost to a particular source phase. Snapshots intentionally add one
frame of visual latency; batched source updates share the most recent host state.

Remaining migration hooks, source inventory parity, demand animation loading,
moving-world collision discrepancies and C rollback retirement remain explicit
requirements. None is closed by the FPS gain or this build.

### Profiling coverage fix (Claude, 2026-10-12, after Astra review)

Astra: `wp` stopped halfway through world_props_draw, so drops, signs,
bosses, Gohma, babas and chests counted as `np`; the "39 ms NPC own work"
claim was unproven. Shadows 0.7 ms and deferred lookups <0.1 ms in that
frame (cache thrash weak); cel copies 13.7 ms in one frame need repeats;
jw 0 does not prove a faster core cannot help (less bus contention could
still shorten master work). All accepted; the earlier claims are withdrawn.
Debug build changes (no gameplay change): row 13 adds `wr` (rest of
world_props_draw, end of function, no early returns) and `pl` (npc_draw's
own shopkeeper/NPC sprite loop); `np` - `wc` - `wp` - `wr` - `pl` is the
small remainder (bank check, interior mask, shop). Rows 10-19 now show the
per-frame MEAN over each overlay refresh (~0.25 s) instead of the last frame.
Debug .bss 0x0607E9B0 (`213c81b1...`); Clean 0x0607D970 (26,256 B,
`2d543dc1...`); staging matched after each build; audits 0 failing; 170
tests, 11 skip. Clean gameplay checks (movement, aim/fire, exits, reloads)
remain open.

Coverage reading (Mednafen, Kokiri, refresh means, 3 shots; ms):
fr 114.5 / 118.7 / 134.1, wk 100.5-124.7. np 47.0 / 48.1 / 35.7 =
wc 0 + wp 6.9-4.7 + wr 36.2 / 36.5 / 25.4 + pl 13.5 / 14.2 / 15.1.
So the rest of world_props_draw (`wr`) is the largest master item, not NPC
sprites. Sprites drawn n 3; shadow 0.4-0.7; cel 2.1-3.0; slPutSprite ~0;
deferred shadow queries 0: ~11 ms of `pl` unexplained by its parts.
Signs: up to 11 meshes each, drawn within +-1000 units of Link with NO view
cull (props got one 2026-10-09). Next Debug build (built, not run) row 19
adds `nd` (time inside npc_sprite_draw calls), `sg` (signs block), `ch`
(chest loop). Debug .bss 0x0607EAA0 (`b3fada74...`). Human 2026-10-12: no
Clean rebuilds until Debug is ready for the 20 FPS test (Clean `c3f29128...`
was built just before that instruction).
