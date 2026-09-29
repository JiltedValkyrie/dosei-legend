## Clean build update (2026-09-28)

Human authorized the Clean build. Assets and target code rebuilt into the existing
`game/build/game-clean.cue`. Verified map: BSS ends at 0x06082800, leaving
**6,144 bytes below SGL at 0x06084000**. The first link exceeded SGL by 4,752 B.
Moved forest vertex depth, tile depth/fog and mesh flags (10,763 B of arrays)
from high BSS into guarded Low Work RAM carves at offsets 0x5000..0x97FF.
Heap, sprite and polygon limits unchanged. Low RAM performance needs Kronos checks.
No commit or Kronos run. Earlier no-build checkpoints below are historical.

Additional renderer checks exposed an outdated forest host adapter (missing SGL
members/constants) and three room-bank assertions expecting 0x67 instead of the
exported 0x66 sort mode. These checks are not green; no renderer behavior was
changed to satisfy them. PowerShell reports NativeCommandError for compiler stderr,
but the build reached disc creation and the final successful map boundary check.

# Vertical slice progress

## M3c/M3d Astra source checkpoint (2026-09-28, unbuilt)

- Human released shared files after Claude finished; requested no build.
- Source drop tables/filtering, pots/rocks/carry/throw, signs, placed hearts,
  decorative props/gossip hit reaction, five animated chests and get-item pose.
- Save v6 migrates forest collectible bits; prior saves remain readable.
- Claude shop preserved; primary-texture heart/nut scrolling added. Fado and
  conversation flags wired; old Navi timer branch bug fixed.
- Last built Clean gap 7,424 B predates these changes. Current RAM/VRAM unknown.
- No disc regeneration, Kronos test or commit. Exact coverage, tests and remaining
  source-parity work: [M3c/M3d checkpoint](game/docs/M3CD_IMPLEMENTATION.md).


## M3b Astra integration checkpoint (2026-09-27, uncommitted)

- Four remaining Kokiri interiors wired; six interiors total with Link home/shop.
- Scene-aware NPCs: 17 placements, including three child Know-It-All brothers.
  Fixed the rotZ adult-variant filter and preserved original forest identities.
- ROM meshes and initial source clips for Mido, Saria and all 13 Kokiri types;
  per-vertex flex ownership, flat body/hair, textured faces. Room-safe transient
  VDP1 bank, source head pivots and animated attention focus. Exit guard follows
  its source 80-unit ring. Full tracking/talk-animation/fade/blink parity pending.
- Original house/shop sequences, seven cart trigger banks; fixed carve 0x7C000.
- BUG-006 ledge-before-talk fixed in code. Clean RAM gap 7,152 B.
- Host checks pass for gameplay, actors, model tracks/head math, actor pool,
  character materials, area music and ledge priority. Opening-audio harness still
  has pre-existing missing camera/menu-duck stubs. No Kronos acceptance claimed.
- Disc keeps the normal `game/build/game-clean.cue` name. Nothing committed.

## M3a contracts (2026-09-27, uncommitted)

- Full child-day actor manifest for forest + 6 interiors (docs/M3A_ACTOR_MANIFEST.md);
  30 unported kinds listed, none hidden.
- One Item_Give/shop-buy path; save v5 adds Deku Nuts (older saves migrate).
- Generic 2/3-choice text with En_Ko branches. Death Save No / Continue fixed
  in code; RAM freed (SGL gap 13,616 B). Kronos checks pending.

## M2b.1 starter route (2026-09-26, uncommitted)

- Ground sword/shield gone. Sword from maze chest (En_Box 0x04E0), shield
  bought in new Kokiri Shop scene for 40 rupees (VDP2 Buy/Don't buy choice).
- Rupees before sword: source En_Item00 + En_Wonder_Item triggers, 43 total.
- Mido blocks the Deku Tree path until sword AND shield equipped, then walks
  aside; flags persist. Gear is owned on grant, equipped on the pause screen.
- 75 gameplay tests pass. Clean built; work-RAM gap 5,488 B (BUG-033).
  Human route check passed (2026-09-26). Stand-ins BUG-031 and boulder
  BUG-032 remain pending; BUG-033 memory work is next priority.

## M1l traversal camera core (2026-09-26, uncommitted)

- Hang/climb framing, eased return and traversal camera collision added;
  malformed crawl-camera paths fall back without hiding Link. Normal follow
  behavior preserved. Source adaptation gaps remain BUG-027/017/025.
- 161 focused tests pass. Clean built; SGL gap 16,592 B. Human camera check pending.
- Human has no available pond test; water acceptance remains pending.
- Dialogue special-character rendering and VDP2 dither backdrop logged separately
  as BUG-026, per human request. No dialogue UI change this turn.

## Astra continuation through M1k water core (2026-09-26, uncommitted)

- BUG-021 grass pass-through and pickup height fixed; human test passed.
  Rustle FX/SFX follow-up is BUG-024.
- M1g turn/bonk human pass. M1h push core, M1i lift hooks/strengthless bush
  failure, M1j slope motion/fall policy added; remaining live actor and health
  integration is explicit in BUG-020/022/023. Push-block live fixture deferred.
- M1k swim, A-held dive/release, float and sloped-bank exits wired; six clips
  in cart animation data. 14 water tests and 210 affected tests pass. Real
  forest pond-to-bank and ydan water-room filtering tested on source geometry.
- Clean image built, SGL gap 18,144 B. New water runtime needs human check.
  BUG-025 tracks source subset gaps and M2/M5 drowning/dungeon dependencies;
  full M1 is not complete. Remaining traversal camera modes come next.

## Demo M1f crawlspaces (2026-09-26, uncommitted)

- A at a crawlspace hole enters; crawl forward/back; exits at the far wall
  or backs out. Real sword-maze tunnel host-tested both ways.
- Fixed grounded ceiling range (BUG-016) and still-standing wall contact.
- Clean image built. Kronos check pending.

## Demo M1e ladder and vine climbing (2026-09-26, uncommitted)

- func_8083EC18 starts (walk into a ladder / vines / FLAG_2 top, jump onto a
  tall climbable wall, walk off onto vines); Player_Action_8084BF1C climbs by
  the clips' root motion (15-unit rungs), stick speed, vine sideways, A lets
  go; ladder top/bottom step-offs, vine top pull-up.
- Link's house ladder climbed up onto the porch and the forest vine wall
  (host tests on S1.COL). Climb-down from the porch: see BUG-015.
- Source point-in-poly slack (BUG-013) fixed; BUG-012 fixed.
- 12 new host tests. Clean image built. Kronos check pending.

## Demo M1d ledge hang, pull-up, let go (2026-09-26, uncommitted)

- Walking off a drop deeper than 45 hangs on the face just left
  (func_8083A6AC); a descending jump or fall grabs a ledge ahead
  (Player_Action_8084411C), including the 250 jump from M1c.
- Hanging: stick pushed pulls up (fall_up / jump_climb_up), A held lets go.
  Six new clips; LINKANIM 103,752 B.
- BUG-011 fixed (released pad no longer interrupts a climb).
- 10 new host tests (test_player_bg 37, controls 53). Clean image built.
  Kronos check pending.

## Demo M1c step-up, wall/ledge probe, ledge climbs (2026-09-26, uncommitted)

- Link's movement follows Actor_UpdateBgCheckInfo's order: wall sphere
  (r14 at +26), ceiling headroom 40, floor ray from +50. Steps up to 24
  are walked up (before: walked through, or blocked at 15+); 25+ block at
  the wall. Roofs lower than 40 stop him.
- Player_ProcessSceneCollision wall/ledge probe + Player_ActionHandler_12:
  hop (25-26), 100 step up (27-38), 150 step up (39-46), 250 jump start
  (47+; mid-air grab is M1d, he lands back). Timer 9 steps, or A.
- Child root x0.64 in every gameplay clip (source); ground shift +18.
  New clips step100/step150/jump250. CLIMB_END voice added.
- 28 new host tests (incl. real S1.COL ledges). Clean image built. Kronos
  check pending.

## Demo M1b gravity + automatic ledge jump (2026-09-26, uncommitted)

- Source gravity (-171 Q8, terminal -20/step). Y jump keeps 51 apex.
- Running off an edge auto-jumps per func_8083AA10/func_8083A4A8 (run_jump
  or jump clip, run_jump_end landing). Walking off falls. Floor property
  7/8 and swinging block leaving.
- 13 new host tests. Clean image built. Kronos check pending.

## Demo M1a world-collision contract (2026-09-25, uncommitted)

- S<n>.COL now KBG2: raw SurfaceType words, poly ignore/conveyor flags, water
  boxes, bgCams. `.SUR` retired. Runtime `bg_*` queries report hit poly,
  owner (static 50 / dyna id), surface bits; D_80119D90 wall flags.
- DynaPoly slots (cart carve): register/set/enable/remove/carry; real
  gPushBlockCol mesh host-tested. Old movement API unchanged, sees dyna.
- Link clip frames moved to LINKANIM.BIN in cart: clean SGL gap
  4,624 -> 49,568 bytes.
- 19 new contract tests on real S1/S0/PUSHBLK. Clean image built.
  Kronos check pending (no emulator run).

## Save crash repair and permanent shot skip (2026-09-25, uncommitted)

- Save crash traced to stale save_device.o: 220-byte v1 stack buffer called
  the 300-byte v2 packer. Compiler header dependencies now rebuild consumers;
  makefile edits invalidate all objects, including SDK configuration.
- Permanent Start confirmation: "Skip? Press Start Again", two-second window,
  current source camera shot only. Final shot follows normal sequence cleanup.
- Work-RAM malloc arena now 51,200 bytes; cart remains allocator fallback.
- Focused host tests pass. Fixed save/skip still need a player replay in Kronos.

## Demo M0 foundations (2026-09-25, uncommitted)

- Face-only character textures (hair flat); Link 143 tiles.
- Base-36 scene/room asset names (36 scenes x 36 rooms, still 8.3).
- Save v2 with 11 scenes; old saves rejected as older version.
- Actor pool (cart carve) + actor collision check skeleton, host tested.
- Area SFX banks: core + swappable area slot; forest bank holds grass cut.
- Builds: all three images; Kronos check still pending.

## Opening freeze, sound and close-up (2026-09-22)

- Reproduced nightmare stall at Kronos's 2048-command guard; project-local
  emulator fixes it and launcher config selects that executable. Replay passed
  into scene 2. See `game/docs/OPENING_FREEZE_2026-09-22.md`.
- Rain geometry now survives SGL's deferred slave reads. Automatic text uses
  source post-reveal delay without the added length-based wait.
- Nine source-derived opening effects use a 32,836-byte bank in the existing
  action-SFX tail. Music starts at Ganon's frame-330 cue; music fades leave SFX
  slots audible. Source layers/envelopes are reduced; audible mix remains
  unreviewed, not claimed as exact original sound parity.
- Nightmare Link uses source scale/origin. Bridge fly-by gets a smooth side
  arc and head aim, visually checked at frame 185 without face clipping.
- 86 focused tests pass. Normal/clean builds pass SGL boundaries with
  8,544 / 19,248 bytes spare. Player discs contain no camera-test frame hold.

## Opening readability and scenery (2026-09-22)

- Text/NONE commands no longer erase an unread message at its hold boundary.
  Automatic fade pages retain the source delay after reveal; the extra
  length-based hold was removed after feedback. Button pages retain marks.
- Cutscene panels use a small padded charcoal mesh fill and bright cyan text.
  Overlay depth follows the shot near plane; separate X/Y sprite scaling fixes
  the oversized panel. Full-cover narration keeps UI sprites visible.
- `CS_TRANS_TRIGGER_INSTANCE` is no longer an opaque black fade. In original
  `z_demo.c` it changes transition control, not screen-fill alpha; the old mapping
  hid the Deku Tree from frame 70 through his speech.
- House shots use the four original `vr_LHVR_static` pre-rendered panorama faces,
  with source palette order and cube orientation. Ordinary house gameplay keeps
  its fixed JPEG. Kronos showed the doorway/Navi and sleeping Link against the
  panorama with zero rejected draws.
- Navi's flight uses banks derived from all three streamed forest room meshes,
  retaining trees and huts across room boundaries. Banks cover 100 camera frames;
  textures outside the span's possible fog view are omitted, distant faces are
  flat fog colour, and runtime faces beyond fog range draw flat. This is bounded
  per-shot residency, not a new per-frame VRAM allocator. Forest bank textures
  occupy 54,656–307,488 bytes; the house panorama uses 135,168 bytes.
- 72 focused cutscene/message/room tests pass. Final colour/panel sizing and the
  complete forest bank-switch flight still need a player check; the background
  emulator later entered BIOS setup. No global input or desktop capture used.

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

## Item counts, assignment and text recoil (2026-09-27)

Items shows live stick/seed counts and Down/Left/Right bindings. Plain D-pad
navigates; hold Saturn C + Down/Left/Right assigns an owned item on either pad.
Gold marks assigned items; blue marks cursor. Save v4 appends bindings; v2/v3
migrate with empty slots. Live stick/slingshot weapon actions remain pending.
Baba events are per-step and consumed once: first-stick fanfare no longer
restarts during text. Text/menu blocks knockback and weapon recoil, clearing
residual push. 265 focused host checks pass; Clean build passes, .bss ends
0x06083E40 (448 B below SGL with concurrent UI changes). No Kronos run or commit.
Human review: first-stick sound, text after hurt/rebound, counts, all assignment
directions on digital/analog pads, save/reload. Preserve concurrent UI edits.
## 2026-09-29 forest capacity repair

Screenshot follow-up: GFS open-handle exhaustion identified. Music holds one
handle across frames; project now reserves two. Clean rebuilt, 976 B below SGL;
host regression reproduces old failure and passes new capacity. Runtime pending.
Permanent all-agent CD-handle rule added to DOSEI-LEGEND-BIBLE.md.

Clean rebuilt with explicit NPC/prop texture reservation, staged budget gate,
and atomic actor-bank cache completion. Saria startup now stops gameplay
catch-up. 213 focused checks pass; minimum forest VRAM spare 33,504 B, high RAM
gap 1,232 B. First-exit greeting and walking blue-screen fix await Kronos review.
Existing save greeting flags unchanged. Work uncommitted.
