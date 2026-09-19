# Vertical slice progress

## Lock camera, rupee melody and pause controls (2026-09-18)

- Target camera now eases behind Link on acquire and tracks target-facing yaw
  while idle/strafe/backing up. Facing refreshed after movement. Release returns
  to normal follow. Full KeepOn1 framing/collision still pending.
- Added missing source rupee melody, BF4/F4/BF4 +24, over quieter backing layer.
  Looping source wave uses 64 bytes; 96-tick/sec sequence scheduled at vblank.
  Bank 39,832 bytes, 104 spare. Envelope/sample-duration approximation remains.
- Pause lists gameplay, lock/re-centre, look, roll and menu controls. C items
  explicitly pending; diagnostics chord shown only in diagnostic builds.
- Normal, clean and hi-res discs rebuilt. 278 tests pass, one skip.
  Emulator visual/listening confirmation still pending.

## Rupee HUD and pickup feedback repair (2026-09-18)

- Counter was rejected by SGL: screen-space sprite depth 1 was inside near
  limit 30. Depth 31 fixes submission; host test now checks actual SDK limit.
- Hi-res HUD doubles screen Y/height explicitly.
- Rupee collection routes original OoT sample layer to dedicated SCSP slot 29.
  Reduced single-layer chime; full original layered sequence still absent.
- Exact silent tails trimmed to fit bank: existing audible PCM unchanged.
  39,764 bytes; 172 sound-RAM bytes remain.
- Normal, clean and hi-res discs rebuilt. 274 tests pass, one skip.
  Emulator visual/listening confirmation still pending.

## Rupees and grass drops (2026-09-18)

- Eight original room rupees; green +1, blue +5, child wallet caps at 99.
- Cut grass rolls rupee subset of real source drop tables. Hidden until cut,
  visible hop before pickup, no repeated credit. Non-rupee drops still absent.
- Original rupee HUD art and digits; world billboards share icon silhouette.
  Source green tint, blue recolour. +3,584 VDP1 bytes, guarded offline.
- Both discs rebuilt. 273 tests: 272 pass, one skip. No new emulator capture.

## Grass sprites and movement audio (2026-09-18)

- Original OoT grass cutout now renders as VDP1 sprite at each grass actor.
  Room/distance culling, shared texture, and cut-state hiding implemented.
- Successful jump voice, roll voice/body sounds, walking/running footsteps
  wired to physics/animation events. Idle, blocked movement and airborne travel
  produce no footsteps. Forest uses one footstep material for now.
- Music unchanged. Action bank 39,168 bytes; 768 sound-RAM bytes spare.
- Both player discs rebuilt. 264 tests: 263 pass, one skip. No new emulator
  visual/listening confirmation.

## Equipped limbs and sound effects (2026-09-18)

- Original OoT hand display lists now show equipped sword/shield on correct
  bones. No gear before pickup; no duplicate back sword/shield. Equipped gear
  stays in hands for baseline play. Full draw/sheath transitions still absent.
- Swing, guard, cut, equip and dialogue/menu effects wired to events; sword
  attacks rotate four real child Link voice samples. Effects are reduced
  single-layer sample adaptations, not complete N64 sequencing.
- Separate SCSP slots/tail bank preserve music resources; offline/runtime
  boundary guards retained. 33,486-byte effect bank fits with 3,378 bytes spare.
- 261 tests: 260 pass, one skip. Background Kronos capture blank; runtime visual
  and listening confirmation still needed. Player discs contain no probe mode.

## Combat/menu repair (2026-09-18)

- Sword and shield state now drive imported OoT slash/recovery and guard poses.
  Previous code only chose locomotion clips, so combat had no visible pose.
  Slice attack timing remains approximate; held-gear geometry and SFX pending.
- Gameplay action clock now runs per 30 Hz step, including catch-up. Menu input
  blocks look/action leakage; closing frame suppresses movement/jump. Debug HUD
  no longer paints over dialogue/inventory. Menu clears its full text area.
- Clean player display includes pickup/equip instructions, controls and action
  feedback. Streaming enabled by default; binary room-bank policy checks added.
- 256 tests: 255 pass, one legacy single-bank suite skips; separate binary-bank
  check passes. In-emulator action/menu visual verification still outstanding.

## Latest: textures restored; overlap unresolved

User stopped experiments. Floor/water texture sampling restored; failed
actor-order probe disabled. [Claude Opus instructions and evidence](game/docs/CLAUDE_OPUS_FLOOR_OCCLUSION.md).

## N64 room streaming and texture warp: prototype, not finished (2026-09-18)

User-approved direction and future-session checkpoint:
[real N64 rooms, object culling, tunnel loading](game/docs/N64_ROOM_STREAMING.md).
Experimental room build succeeds in isolated workspace. Root player images not
promoted. Latest water-order fix and tunnel traversal still unverified; only
2864 bytes remain below work area in latest probe. Older test/budget claims below
not validation of this prototype. Next session must read checkpoint before changes.

## Saturn pad control remap (2026-09-18)

- Approved layout landed: D-pad moves, B toggles walk/run, Y jumps, A interacts,
  X attacks, L recenters, R shields, hold C + D-pad emits the four N64 C
  buttons, hold Z + D-pad aims a bounded look camera. Start still toggles title.
- One VBlank snapshot feeds one mapping layer (`game/src/player_input.c`); the
  fixed step only applies its decisions. Priority is Z, then C, then movement,
  and a consumed direction never leaks into locomotion.
- Walk is 3 units/step vs run's 5.5; both normalize diagonals, and the walk clip
  is chosen from distance actually travelled.
- PENDING, no system to drive yet: A interact, X attack, R shield, the C item
  interface, pause on Start, and full Z-targeting. Each is routed and counted in
  the diagnostic overlay, never substituted with other behavior.
- L+R diagnostics chord is compiled out of the clean player image so targeting
  and shielding can be pressed together there.
- 186 host tests pass (39 new); standard and clean images built. Controller feel
  and the look-camera rates still need Kronos confirmation.

- Fixed jump/fall visual sinking: remove FALL clip's ~82-world-unit authored
  root descent, keeping rotations. Physics alone owns airborne travel. Added
  actual-skinned-mesh bounds/run-transition regression, not just data parity.

## Manual jump (custom feature)

- Y jumps only from ground (was A before the 2026-09-18 remap); one jump per press, no airborne retry or held repeat.
- Existing gravity/air steering/airborne clip; roughly 52-unit jump height.
  Swept head clearance stops upward motion at low ceilings.
- Host physics checks pass; controller feel still needs runtime confirmation.
- Development moves to `dev` after the main checkpoint.

- Clean player-test image: `game/build/game-clean.cue` (`./game/build.sh --clean`).
  No in-game diagnostic HUD; independent objects/image, safety checks retained.

## Title flights (2026-09-16)

- Replaced low tunnel routes with eight elevated main-village fairy shots:
  clearing traverses, pull-back reveals, rising cranes and diagonal flybys.
  Ten seconds each, eased travel, cuts between subjects. No stationary swivels.
- Subjects frame beside the logo at x=60/260, not behind its centre. Baked aim
  replaces rounded path-tangent steering. Runtime remains integer-only.
- Builder checks flight segments and sampled sight lines against collision.
  Native test runs actual camera C across every tick of all eight shots,
  checks travel, bounded changes and subject projection outside logo centre.
- Both images rebuilt; 141 tests pass. Existing world clipping is separate.

## Link model ownership and face (2026-09-16)

- Fixed 24 ignored matrix loads: bone ownership captured per vertex, not limb.
- Shared OoT Flex ownership helper rejects unsupported transforms. Import rules
  and regression requirements now in DOSEI-LEGEND-BIBLE.md, linked from CLAUDE.md.
- Preserve local precision, tiny animated faces and fractional world output;
  use native near head with artwork. Background actor capture shows joined
  limbs and coherent face. All poses/sorting cases not visually certified.
- 140 tests pass; normal/hi-res images rebuilt without inspection mode.
- Actor texture growth reduces adaptive forest texture budget by 7392 bytes;
  geometry unchanged. Floor penetration and large-plane clipping still open.

## FPS regression and camera height (2026-09-16)

- Removed SH-2 software float in skinning: measured ~97 ms -> ~7 ms.
- Forest partition avoids redundant copies; invisible fog palettes untouched;
  channel lookup preserves colors; stationary view reuses preparation.
  Fog samples ~17 ms -> ~3-4 ms. Fixed-view 15 -> 20 VDP1 FPS. Moving samples
  reach 19 but fluctuate; sustained 30/60 is NOT verified.
- Corrected FRT conversion/accounting and added nested stage timing.
- Follow aim = feet + height + offset, verified in decomp. Background capture
  frames Link; camera/terrain collision remains absent.
- Animated Link no longer culls against stale bind-pose normals. Flat baking
  and sorting artifacts are separate remaining issues.
- Human's repeatable floor penetration OPEN: nearby host replay did not
  reproduce it. HUD records Y now. Nearby-safe recovery retained.
- No-FPU rule in CLAUDE.md; testing stays background-only.
- Down no longer chases opposite facing; rear-half-plane yaw held unless L
  recenters. Host regression passes; interactive feel check pending.
- 125 tests pass; normal and hi-res discs rebuilt without autonomous probes.
  Last moving capture: VDP1 19, WORK 31.3 ms, sync 18.8 ms. Not a full FPS fix.

## Low-FPS lost button presses

- Background capture confirms VDP1 8 / VDP2 58, zero submission refusals.
- Start/L now latch rising edges at VBlank until slow gameplay consumes them.
  100 host tests pass. No speculative camera/render optimization applied.
- FPS bottleneck still open. Existing emulator was not restarted or disturbed;
  runtime confirmation of rebuilt latch fix remains pending.

## Gameplay controls supersede the viewer

- Removed R orbit from gameplay; actor-mode controller ignores both shoulder
  orbit bits. 87 host tests pass, including shoulder yaw invariance.
- Settled digital-pad layout and real OoT camera implementation assignment
  recorded for Claude at the top of OPUS_HANDOFF.md. Only orbit removal landed
  in this change; the remaining actions/camera parity are explicitly pending.

## Digital-pad speed and camera follow-up

- Child outdoor run speed corrected to 165 native world units/s, including
  fractional travel and normalized diagonals; free camera unchanged.
- Animation slowed to a tuned 20 source frames/s with pose interpolation and
  decimated-fall timing corrected. Exact N64 action-specific cadence remains
  outside this change; gameplay feel still needs confirmation.
- L recenters behind Link; full targeting is not implemented. Remaining pad
  remap is a proposal in OPUS_HANDOFF.md, not silently applied.
- Standard and hi-res images rebuilt; 81 host tests pass. No claim of runtime
  visual verification; user's desktop/game focus was not touched.

## Animation frame decoder correction

- Fixed player animation record stride: 134 bytes, not 132. The missing
  trailing face word corrupted every nonzero frame's root and limb data.
- Added independent nonzero/decimated-frame regression fixtures; 75 tests pass.
- Rebuilt standard and hi-res images. Runtime blinking/tumbling and smoothness
  still need gameplay confirmation; no controls or physics changed.

Scope: [VERTICALSLICE.md](VERTICALSLICE.md). Update this file as work changes;
older handoff snapshots are not the current checklist.

## Snapshot — 2026-09-16

Layout update: active Jo project is now `game/`; the performance reorganization
is integrated into main. See [Opus's next task](game/docs/OPUS_HANDOFF.md).
Shared code/assets are under `shared/`; launcher and tri/quad workshop recovered
under root `tools/`. Legacy libyaul work is archived and excluded from active
builds. Standard/hi-res builds and 39 game plus 10 workshop tests pass after moves.
The workshop still produces editing candidates, not runtime-ready quads.

| Area | Status | Next useful step |
| --- | --- | --- |
| Forest | Hybrid textures and capped close-ground/treeline subdivision implemented; moving Kronos probe checked | Human close-view playability check; remaining affine distortion is not declared eliminated |
| Title/prompt | Implemented and observed in Kronos | Preserve |
| Playable Link, camera, collision | Implemented; 30 Hz gravity follows ramp/ledge departures | Confirm fall feel in Kronos |
| Animation | Runtime skinning; idle/walk/run/fall/landing/roll driven by actual motion | Human check of the walk/run read and landing feel in Kronos |
| Music | Two banks and reusable player in `b8e1642`; later streaming/timing edits included in this checkpoint | Good enough; no timing gate |
| NPC/dialogue | Not implemented | One complete proximity conversation |
| Menus | Title toggle exists; gameplay menu not implemented | Functional navigation/confirm/cancel |
| Sound effects | Not implemented | Movement, interaction and menu feedback |
| Hi-res | Separate 320x480i image built; forest/title observed in Kronos | Human visual comparison; not a warping fix |

## Acceptance boundaries

- Earlier captures showed title/gameplay with zero submission refusals; that does
  not prove warping fixed or all collision/camera cases correct.
- Music timing diagnostics are not an acceptance gate.
- Native hardware hi-res appearance is unverified.
- Bosses and dungeons are excluded.

## Next

1. One NPC with prompt and advance/dismiss dialogue.
2. Menus and sound effects, then a short slice playthrough.

## Update convention

Record date, behavior delivered, brief evidence and user-visible limitations.
Do not turn this into a benchmark checklist.

- 2026-09-16: Human confirmed the near-camera warping is playable, closing that
  priority. Link is now animated: idle, walk, run, fall, landing and roll are
  baked from the US 1.2 animations and posed at runtime by a skeletal skinner
  (`game/src/link_anim.c`), rather than pre-baked per frame -- one POINT table
  is ~3.9 KB and only ~9.4 KB of .bss was free. Locomotion is driven by the
  distance collision actually moved Link, so walking into a wall idles instead
  of running on the spot. Landing follows OoT's own branch, verified against
  z_player.c: short landing under 80 units, landing roll under 800 with forward
  motion. The roll is a landing behavior, not an automatic mid-air roll.
  Jo's malloc arena was trimmed 221,184 -> 180,224 bytes to pay for the clip
  tables; measured demand is ~17 KB and the A overlay now prints heap usage.
  Both images build (27,088 / 26,864 bytes of .bss headroom) and 69 tests pass,
  including a check that re-posing the bind pose from the skinning tables
  reproduces LINK.BIN's own vertices. Not yet confirmed in Kronos: how the
  walk/run threshold and the landing transitions actually read in motion.

- 2026-09-16: Astra took over the texture work. Source-UV hybrid rendering is
  now active, with shared repeating tiles, larger ground bakes and limited
  geometry splits. Old near-treeline disappearance reproduced; new split path
  retains it on the approach/turn probe with zero refusals. 52 game tests pass.
  Total with Link: 2,446 polygons / 2,112 vertices / 425,288 VDP1 texture+CLUT
  bytes. Collision and title/music unchanged. Render-component metadata exists
  for future hut/tree visibility; runtime culling is not implemented.
  Details/evidence/fallback: [texture handoff](game/docs/TEXTURE_PLAN.md).

- 2026-09-16: Established scope/progress tracking. Preserved current Link,
  collision and music-transition work for the main-branch checkpoint. Added
  a separate hi-res comparison path without replacing the standard launcher.
  Both builds passed their link-time memory checks; 39 viewer tests passed.
  Hi-res boot capture: `game/build/generated/hires-check.png` (local/ignored).

- 2026-09-16: Added persistent vertical velocity and floor landing for Link.
- 2026-09-16: Added map-wide void recovery to Link's most recent grounded
  position, and made gravity probe from his feet so overhead bridges cannot
  mask the ground below him.
- 2026-09-16: Added OoT's 11-unit grounded floor tolerance to downhill actor
  movement. Link now follows walkable ramp geometry continuously without the
  gravity/landing bounce, while larger ledges still start a fall.
- 2026-09-16: Replaced the title's fixed-position spin with the former hybrid
  texture probe's 12-second ground and Great Deku Tree camera tour. The route
  is driven by VBlank time and does not alter the gameplay follow camera.
- 2026-09-16: Expanded the title attract sequence to five shots covering the
  village, central field, Great Deku Tree room, and Lost Woods/training room.
  Added an OoT daytime blue horizon gradient on the Saturn back screen and
  animated fairy billboards at the ten original Kokiri/Saria/Mido homes; NPC
  models remain deliberately absent.
  Gravity is fixed-point and time-scaled from OoT's normal -1 acceleration and
  -20 terminal velocity at 20 Hz to this slice's 30 Hz update. Link now falls
  after leaving ramps and ledges instead of remaining at the ramp's peak.

- 2026-09-16: Split Link's scene clearance from the old free-camera sphere.
  Child Link now uses OoT-sized wall/ceiling checks (radius 14 at 26 units
  above his feet), allowing him under the low Kokiri bridge while preserving
  the free camera's larger collision volume.

- 2026-09-16: Fixed the missing title by moving the sky table away from SGL's
  fixed B1 font storage. Replaced direct back-screen register overrides with
  slBackColTable; padded the table and final scanline black for the border.
  Added yellow-olive palette fog, checkerboard fading, and a 1,310-unit cutoff
  (50% of the original forest renderer range). Replaced the five straight/probe
  shots with wider, slower collision-validated routes, with passage-centre
  preference and checked corner smoothing. Background PrintWindow capture now
  allows emulator inspection without desktop capture or taking keyboard focus.
  Standard/hi-res images rebuilt; 59 existing tests passed. All five generated
  routes passed dense segment-clearance checks. Standard and hi-res background captures
  show the restored title, black surround, and olive haze. Shared-tile fog is
  a conservative approximation, not per-pixel N64 fog.

- 2026-09-16: User assigned Claude walking/running/falling/rolling animation next.
  Current handoff and constraints are in `game/docs/OPUS_HANDOFF.md`; root
  `CLAUDE.md` points there. Conditional landing-roll behavior located in the
  original player source for Claude to verify. Implementation not started by
  this handoff; no Claude invocation tool/CLI was available to launch it here.
