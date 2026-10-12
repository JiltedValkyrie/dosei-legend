# Mednafen performance handoff (2026-10-12)

Earlier stop/notes request is over: human resumed work the same day. RAM
boundary blocker solved by candidate 8. Candidate 10 (envelope v3 default)
is the current baseline; Clean rebuilt once with it (human-authorized).
Moving prepare is no longer the largest master item: next targets are the
gameplay step (mv), Link submit (lk) and actor draws, then core time.

## Gameplay repair candidate 12 (Claude, 2026-10-12; R0 carry review)

Reviewed API33 carry adapter against source. Cancel, death and room reset
already follow source detach rules: Player_Action_80846050 / carry upper
action handle a NULL actor; death throws/drops via source detach (state 3);
host scene/room reset fails `actor_resolve` and cancels. No change there.
Legacy C cancels (menu/text/knockdown/airborne) are only in the C branch.

Found and fixed: first-grab failure. Host prompt and offer used one rule
(xz 50, dy 40, +/-60 deg) for rock and pot. Source differs:
- EnIshi small offers xz 50 / dy 10; large 80 / 20 (Player gates strength).
- ObjTsubo offers xz 30 / dy 30 only within xz 100 and +/-60 deg of
  Player world (movement) yaw.
- Player admits only absYawDiff > 0x6000: +/-45 deg of shape yaw.
Host said "Grab" between 45 and 60 deg; A then did nothing.

Changes:
- `player_host_carry.h`: OotCore_CarryOffer runs the EnIshi/ObjTsubo offer
  branches. Host candidate: best-faced prop inside its source xz range.
- `Interface_SetDoAction` (was STUB) records Player_UpdateInterface's A
  label; API34 `OotCorePlayerView.do_action` carries it. Host Grab prompt,
  A reservation and carried Throw/Drop labels read it (before: Throw/Drop
  never shown under source; they came from inactive C link_lift).
- Test: carry test checks all three offer rules (negative check fails).

Not changed: pickup SFX (logged), stick visual, aim halving, tap-fire.
Candidate 11 image backed up in `build/mednafen-test/fix11-image/`.

Verification (no emulator run, per human):
- Host: carry test (negative variant fails as expected); 124 carry/lift/
  HUD/aim/control checks pass (34 skipped: local artwork); 269 gameplay/
  migration/core-view/actor checks pass, one existing skip.
- Temporary Debug `build/game-perf-kokiri.cue` via
  `build/gameplay-fix12-build.sh`: SHA256 `5dedadf95d2b6fba...618929`,
  no compiler errors, .bss ends 0x06083F10 (**240 B** spare). Host/core
  audits 567 / 1627 allowed multiplies, 0 failing; budget passes; 1,424
  ISO files match. Normal staging restored (1,434 files); Clean b54638cd
  unchanged. First two attempts failed the boundary by 16 B (BUILD.md 110).

Human checks on candidate 12: Grab prompt appears only where A grabs
(rock and pot, several angles); pickup, throw while moving, put-down when
still, Throw/Drop labels while carrying, damage while carrying, carry
through Kokiri room boundary, held stick/burn, aim feel, repeated shots.

## Gameplay repair candidate 11 (Astra, 2026-10-12; handed to Claude)

Human tested candidate-10 Clean and says it runs much better. Current task
is rock pickup, held C-item visuals and coarse low-FPS aiming, not another
performance batch. Candidate-10 moving 20 FPS remains unfinished.

Implemented:
- API33: host rock/pot identity adapter supplies a source Actor, with a live
  update sentinel for Player lifetime checks. Source Player owns admission,
  put-away/pickup/throw animation, hand position and release speed. Existing
  C prop flight, collisions and drops remain; no Player proxy rollback.
  OFFER runs before kick; READ runs after join. Handles cross the boundary,
  not C actor pointers. Explicit cancel clears all source references.
- Stick renderer reads source item/burn flags and hand/tip anchors. Idle
  source stick does not refresh the melee base, so export leftHandPos.
- First-person source stick axes halved before its nonlinear aim response.
  Walking, simulation cadence and shared shot/camera direction stay intact.
- Tap-ready/tap-fire remains intentional. First physical button release is
  deliberately held by the adapter; testing must include a second tap.

Verification so far:
- 319 focused checks run: 318 pass, one existing skip. New carry test executes
  the real Player pickup-frame attachment and detach code. Input test checks
  fine axes, repeated source ticks without cumulative scaling, and walking.
- Temporary Debug `f62f7752bfd73a5e1ab9763be7311e00534ae6939e8e44fc4440b438bae138f8`;
  `built:` present, no compiler errors. `.bss` ends `0x06083FB0`, only **80 B**
  spare. No memory/actor/geometry capacity cut.
- Host/core audits: 567 / 1627 allowed hardware multiplies, zero failures.
  Forest budget passes; 1,424 ISO files match candidate staging.
- First build attempt interrupted by WSL hangup; retry protects HUP. Next
  attempt caught missing SIGNALL in preserved old Debug staging; final build
  generates merged sign and retires exact old SIGN0..10 payloads.
- Normal staging restored by EXIT trap. Candidate files retained in
  `build/mednafen-test/fix11-result-cd`. Clean `b54638cd` unchanged.
- Before human stopped automation: second C-left tap showed a released seed
  (`a0DR`) alongside the rearmed held seed; held stick is visibly rendered;
  second rock pickup attempt shows rock lifted and item gate `g0800`
  (carrying). Captures `fix11-fire.png`, `fix11-stick.png`, `fix11-grab2.png`
  in build/mednafen-test. First grab attempt failed; facing tolerance may
  differ between the host Grab prompt and source admission. Throw/drop,
  pots, room transitions, burning sticks and aim feel remain unverified.
- Human explicitly stopped automated testing: Claude fixes, human tests.
  Private Mednafen closed normally and original config restored. No further
  emulator automation unless human requests it. Clean remains b54638cd;
  gameplay changes are only in the temporary Debug image and source tree.

Claude next:
1. Review existing API33 carry adapter rather than reimplementing it. Check
   cancelled pickup, death/room reset, throw/drop and host/source Grab facing
   agreement (host cone +/-0x2AAA, source offer default +/-0x2000).
2. Keep source-owned stick visual and reduced first-person sensitivity;
   preserve camera/projectile alignment and fixed simulation cadence.
3. Slingshot is tap-ready/tap-fire; physical first release intentionally holds.
   Do not change that mapping based on the earlier hold/release test alone.
4. Finish remaining gameplay fixes and produce checked human-test artifact.
   Debug high-RAM spare is only 80 B: respect boundary, no capacity cuts.
   Human performs runtime checks. No automated emulator tests/focus changes.

## Candidate 9/10: moving scene prepare (Claude, 2026-10-12)

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
Clean rebuilt once (human-authorized) with candidate 10 code:
`b54638cdcbf1189bc922f316f217ea382c5970b1f994126835c812b7bd356f51`, .bss
0x060828B0 (5,968 B spare), audits 488/1,625 clean, budget passes, 1,424 ISO
files match. Previous Clean c3f29128 backed up in
`build/mednafen-test/clean-c3f29128/`. Clean not runtime-tested yet.

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

## Resumed 2026-10-12: RAM fixed, eighth candidate tested

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

## Current result (before resume)

- **20 FPS moving/aiming is not achieved or accepted.**
- Last successfully tested temporary candidate: `6f806172`, with full evidence
  in [the review](PERFORMANCE_REVIEW_2026-10-12.md).
- Heart pulse composition improved from about 11.4 ms to 0.4–0.8 ms by reading
  its 640-byte atlas from CPU Low RAM instead of VDP2.
- Candidate 6: M idle 14.1 FPS; valid M first-person aim 9.4 FPS, whole frame
  93.5 ms, slave core 74.2 ms/frame, master join 36.6 ms. P aim 9.4 and C aim
  9.0 were short samples at slightly different angles, not a controlled ranking.
- Earlier forward-input route samples caught Link on a ledge. They do not
  prove sustained running FPS. STATE1_13 also explains the failed early aim
  attempts; normal A releases the ledge. Grounded aim works.
- Row-1 `lk` retains an old sample when Link drawing is skipped. It does not
  prove Link is visible in first person. The figure ahead in aim captures is
  a Kokiri NPC. Dialogue profiler freeze remains deliberately unchanged.

## Seventh source batch (runtime-tested as part of candidate 8)

The seventh source batch combines:

1. Exact bounded Player affine transforms and zero-vector origins. Keeps
   source rounding/saturation, with fallback for matrices outside the proven
   bounds. `oot_core_draw.cpp`, `player_anchor_matrix.h`, importer and make
   dependencies changed. The missing private `Matrix_GetCurrent` declaration
   was fixed; the host fixture now detects that integration mistake.
2. A Player-only draw wrapper removes discarded N64 lighting, color-filter
   commands, floor matrices and shadow drawing. Retains actor transform,
   object dependency, all limb callbacks, floor rays, feet contact flags and
   unknown-shadow fallback. Boss/other actor drawing is unchanged.
3. Hidden Link skips vertex skinning while bones remain current. Existing jobs
   join before buffers/age change. `link_anim_draw_sync()` skins a bones-only
   pose if first person exits during the same frame. Kokiri Link draw calls
   this new consumer; no new BSS for the skin change.
4. Skip the 20 unused sign snapshot queries while C owns Kokiri signs. The
   original snapshot path remains available if ownership changes. NPC view
   extraction rejects non-view actors before clearing a reusable output row.
5. Cold profiler averages/sums moved to Low RAM at `0x002FF280`, reservation
   `0x300` bytes. Explicit boot initialization, capacity guard, unchanged
   displayed averages. Hot counters remain high RAM. Write-only
   `perf_sub_last` removed; the three profiler routines use `Os`.
6. Debug row 15 adds `cvN@line` for unsafe core ENTRY calls; row 22 adds joined
   host aim mode/item button/first-person state. No race is established merely
   from an ambiguous old screenshot; use the actual recorded source line.
7. Only `--perf-kokiri` boots at source Kokiri spawn 9, outside Mido's house:
   `(-445, 0, -486)`, yaw 0. The first 400 units forward were checked against
   static collision. Ordinary Debug/Clean entries stay unchanged. This avoids
   spawn 0's immediate wooden ledge; do not extrapolate the clear route beyond
   the checked corridor.

## Verification

`game/build/kokiri-speed7-tests.log`: 217 tests passed for the seventh batch;
candidate 8 adds the snap_npc carve test (219, `kokiri-speed8-tests.log`).
Includes 250,000 affine cases, 440,000 chained limb matrices, 100,000 origins,
100,000 feet states and 24,000 wrapper states against source
ActorShadow_DrawFeet/Actor_Draw, same-frame hidden-to-visible skin refresh,
snapshot ownership, cold RAM initialization and guard bytes.

RAM history: the seventh link ended BSS at 0x06084070, 112 B over SGL; guard
removed that image. Solved in candidate 8 by moving `snap_npc` to Low RAM;
.bss now ends 0x06083970, 1,680 B spare. No capacities reduced.

## Preserved artifacts and shutdown state

- Ordinary Debug ISO unchanged:
  `6117a58cd8181717610bcb071383d273dc796f890ee40decba20f1df70505941`.
- Clean ISO rebuilt 2026-10-12 with candidate 10:
  `b54638cdcbf1189bc922f316f217ea382c5970b1f994126835c812b7bd356f51`;
  previous c3f29128 backed up in `build/mednafen-test/clean-c3f29128/`.
- Failed seventh staging archived to
  `game/build/mednafen-test/speed7-failed-cd` for inspection only.
- Candidate 8 staging: `mednafen-test/speed8-cd`; image
  `build/game-perf-kokiri.iso` (6cdeb96e) until the next candidate overwrites it.
- Normal `game/build/cd` restored from `mednafen-test/debug-cd` and verified:
  all **1,434** files exactly match ordinary Debug. Log:
  `game/build/kokiri-speed8-debug-preserved.log`.
- Earlier candidate staging remains in `speed2-cd` through `speed6-cd`.
- No test Mednafen process remains. Normal config SHA256 restored:
  `e85e7a76a5a8c9648aac5cf63baad56e439895f4b134e1f60eb2c28523caa5da`.
- No commits or resets. Shared tree already contained extensive work; preserve it.

## Resume steps

1. RAM: solved (candidate 8). Check .bss headroom on every further change.
2. Build script `game/build/kokiri-speed8-build.sh` (copy per candidate). It
   expects normal Debug staging and no existing `speedN-cd`; an ERR trap
   archives failed staging and restores normal Debug staging.
3. Test the new temporary image on a **private background desktop only**.
   Human is playing; **never activate a window, switch desktops or send global
   keys**. Ignored helper `game/build/mednafen-test-control.ps1` forcibly uses
   Background/Post and validates owned process identity. It isolates keyboard
   bindings and restores config on close. Do not launch if another Mednafen
   process exists. Loading can take roughly two minutes.
4. Measure M idle, short forward route, grounded aim/fire and same-frame aim
   exit. Inspect row 15 call provenance and row 22 aim state. Then compare job
   modes if useful; judge whole frames. Keep normal emulator timing/cache.
5. Further options are hypotheses: hot core code relocation requires proper
   linked addresses/load copy/cache handoff, and collision fast-copy allocation
   requires an actual budget. Do not shrink N64 graphics scratch blindly;
   bosses still use the shared draw buffers.

No Clean build until Debug is ready for a 20 FPS test. Real Player, source
collision, slave work and simulation cadence remain required. Rock grab and
invisible held stick remain explicitly deferred; simplify cut signs to fading
as already authorized. Do not spend this performance task on dialogue counters.
