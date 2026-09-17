# Vertical slice progress

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
