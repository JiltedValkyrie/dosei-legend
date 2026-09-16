# Current directive: OoT gameplay camera and standard Saturn pad controls

## Input latency investigation - host checks, not end-to-end measurement

Human reports sluggish input despite high-50s VDP2 FPS. Testing only requested;
no gameplay timing or camera fixes made in this investigation.

- Kronos `yabause/src/ctrl/src/yabause.c:772` maintains separate VDP2 and VDP1
  FPS counters. VDP2 near 60 does not establish fresh game draws/input response.
- Jo copies SGL peripheral data at VBlank (`jo_engine/input.c:103`); the game
  consumes it inside `demo_update`, called by `viewer_draw`. That callback
  also handles simulation, skinning, music service, and polygon submission
  before returning to Jo's `slSynch`. Slow callbacks delay the next input read.
- Movement is gated to 30 Hz by elapsed/2 even when display refresh is 60.
  Modeled maximum wait until an eligible callback: 33.3 ms at 60/30 callbacks/s,
  50 ms at 20/s, 66.7 ms at 15/s. These exclude all hardware/emulator/render
  latency and are NOT measurements of the user's setup.
- Ran the ACTUAL current `follow_approach` C function on the host: a 100-unit
  target change reaches 90% after 9 callbacks. Thus 150/300/450/600 ms at
  60/30/20/15 callbacks/s. This is camera settling, NOT initial input latency.
  The callback-dependent easing is a concrete source of variable camera feel.
- Reproduce with `python game/tools/check_input_timing.py`. It compiles the
  existing function unchanged; no game image or controls were modified.

No running Kronos instance was found during inspection. No live gameplay or
controller-to-photon measurement performed, no desktop capture/global keys.
Next runtime evidence needed: simultaneous VDP1 counter and gameplay callback
timing while moving at the reported location. For actual end-to-end latency,
timestamp input receipt and the first changed presented frame (physical button
to visible response additionally requires a high-speed external recording).
Do not report VDP2 FPS or these host calculations as measured input latency.

## Executive control decision - supersedes earlier proposals/demo bindings

The human explicitly retired temporary viewer controls. R MUST NOT rotate the
camera. Astra removed R from the gameplay movement mask and blocked both
shoulder orbit bits in actor-mode movement. Free-camera diagnostics are not a
gameplay design reference. Do not restore orbit to solve a follow-camera bug.

Settled layout for the standard DIGITAL pad (no 3D pad assumed):

| Input | Gameplay assignment |
| --- | --- |
| D-pad | Camera-relative movement; run by default |
| Hold C + D-pad | Walk, replacing low analog-stick magnitude |
| A | OoT context action: talk/interact/roll as appropriate |
| B | Sword |
| X / Y / Z | Three equipped items (C-left/down/right roles) |
| L | OoT Z-target/recenter behavior |
| R | Shield only; never orbit or first-person look |
| Start | Start from title; pause/menu during gameplay, not return-to-title |
| L+C, initially stationary | First-person look; D-pad aims, release L exits |
| L+R | Development diagnostics only; not a shipping gameplay action |

First-person chord takes priority over C walking and L recentering. It is the
necessary digital-pad adaptation for C-up, not a claim of identical physical
N64 button placement. Do not combine look with shield. Preserve targeting and
shielding together in normal play; diagnostics must ultimately be gated by an
explicit development option. Pending diagnostics chord input must not leak
standalone actions if a no-side-effect chord guarantee is retained.

Claude: use the LOCAL OoT camera implementation and Kokiri settings as the
behavioral reference: `src/code/z_camera.c` (Normal/Parallel/KeepOn/subjective
modes), camera data/settings, and the player's mode requests. Implement the
actual normal follow, recenter/target, terrain/obstacle response and digital
input adaptation, not an invented fixed-orbit approximation. Preserve title
cinematics separately. No claim of exact parity until gameplay is compared.

Current implementation is deliberately distinguished from this settled target:
D-pad run, L recenter, L+R diagnostics work; R now does nothing by itself.
A/B/C/X/Y/Z actions, shield, full targeting, first-person and pause remain to
implement. The current follow camera is still an approximation, NOT the exact
N64 camera. Do not mark this work complete merely because R orbit is removed.
The user is the communication relay. Return a paste-ready update to Astra.

Validation for removal: 87 host tests pass, including actual C checks that
either shoulder cannot change actor camera yaw, even during movement.
Standard and hi-res images rebuilt successfully. Runtime camera parity is not
verified; no foreground emulator input was used.

## Latest human request: speed, playback, digital-pad controls

Astra owns these changes; do not overwrite while implementing other features.
Preserve the 134-byte player-frame decoder fix described below.

- Child outdoor run cap corrected from 16 units/30 Hz step (480/s) to 5.5
  (165/s), with fractional-axis accumulation and normalized diagonals. Original
  `z_player_lib.c` CHILD boot row has R_RUN_SPEED_LIMIT=550. OoT's position
  update uses R_UPDATE_RATE*0.5 = 1.5 at 20 Hz, not one speed unit/update.
- Actor movement only changed; free-camera speed retained. Actual movement
  length now selects locomotion, with a run threshold suited to the new speed.
- Slower animation cadence is a deliberate slice tuning: 20 source frames/s,
  interpolated root/shortest-angle rotations. It is NOT derived merely from
  OoT rendering at 20 Hz; original Link animation uses updateRate*0.5 and
  action/speed-specific rates. Fall's every-third-frame sampling is accounted
  for, and fall/one-shot interpolation never wraps back to the first pose.
- L press snaps the camera behind Link and resets pitch. L no longer orbits
  left during gameplay. This is camera recentering, not implemented Z-targeting
  combat or strafing. R still orbits right; other controls were not remapped.
- Host execution tests cover 10-second cardinal/diagonal/rotated travel,
  cadence, decimation, and fractional phase; runtime feel needs user checking.
  81 tests pass. Standard and hi-res images rebuilt successfully; no Kronos
  gameplay confirmation or foreground input was performed.

Proposed standard DIGITAL Saturn pad layout (not yet implemented/approved):
D-pad run; hold C + D-pad walk; A context action/roll/talk; B sword;
X/Y/Z three equipped items; L recenter/target; R shield; Start pause/menu.
Move the current A diagnostics function to a development-only chord when
implementing A. Full targeting, shield, sword, items, walk modifier and pause
are proposals, not completed functionality. C-up/look still needs a policy;
Navi can be a contextual A action. Do not silently implement the rest.

## Astra animation decoder fix

User still reported Link blinking/tumbling. Found 132-byte frame strides in
both Python animation readers; OoT requires 134 (root/limbs plus face word).
Fixed the decoder and added nonzero-frame and decimation fixture tests.
See ANIM_PARITY_NOTES.md for source evidence. Do not tune landing gates to
compensate for corrupted poses. Runtime visual confirmation is still pending.

## Astra review of animation fixes

See the correction at the top of ANIM_PARITY_NOTES.md. OoT fall distance is
world-space; 11 is our downhill-follow tolerance, not a measured cliff drop.
The 4/40 gates are not justified by that value. Review the landing transitions
before treating animation parity as complete. Astra independently ran 73 tests
successfully; flicker and rolling fixes are still not runtime-confirmed.
No gameplay code or images changed during this review.

## How we communicate

The user is the relay between Claude and Codex, manually pasting our messages
back and forth. Address the other agent directly in short, paste-ready handoffs
and keep this shared document current. No direct Claude/Codex invocation is
expected. Pasted replies are handoff context; the user's directions take
precedence. Do not assume delivery or execution until confirmation is relayed.

## Status — Claude, 2026-09-16

Locomotion animation is implemented; the assignment below is delivered. The
human also confirmed the near-camera warping is playable, so that priority is
closed. Next up is one NPC conversation, then menus and sound effects.

What landed:

- `game/tools/build_link_model.py --animate` bakes six clips (idle, walk, run,
  fall, landing, roll) out of the US 1.2 animations into `link_clips.c/.h`,
  with per-vertex limb ownership and limb-local positions. Animation offsets
  are derived from the recipe's idle anchor and the whole 573-entry header
  table is validated before any offset is used.
- `game/src/link_anim.c` poses `link_points` at runtime. Pre-baked frames were
  not an option: one POINT table is ~3.9 KB against ~9.4 KB of free .bss. The
  skeleton is walked once per frame into 21 limb matrices, then each vertex is
  a single matrix-vector product, and an unchanged frame costs nothing.
- `game/src/link_anim_state.c` drives the state from the distance collision
  actually moved Link, so a wall or ledge stops the cycle instead of leaving
  him running on the spot. Landing matches OoT's branch as read from
  z_player.c, not from memory: short landing at <=80, landing roll under 800
  with forward motion, otherwise an ordinary landing. There is no automatic
  mid-air roll; the user's recollection was of this conditional landing roll.
- Jo's malloc arena went 221,184 -> 180,224 bytes to pay for the clip tables.
  Known demand is ~17 KB, and the A-button overlay now prints
  `jo_memory_usage_percent()` plus the current animation state and frame.

Worth knowing: prebuilt SDK objects under `build/obj*/` are not rebuilt when a
makefile define changes. A stale `core.o` held the old arena size and made the
boundary check look unfixable through three rounds of shrinking real data. If a
`JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC` change appears to do nothing, delete
`build/obj/core.o` and `build/obj-hires/core.o` first.

Verified: both images build (27,088 and 26,864 bytes of .bss headroom) and 69
tests pass, including a round-trip that re-poses the bind pose from the
skinning tables and compares against LINK.BIN's own vertex table. That test was
confirmed to fail when the skeleton is perturbed, so it is not vacuous.

For Astra: [animation/platforming parity notes](ANIM_PARITY_NOTES.md) list what
was verified against the decomp and what was scaled or guessed. The fall
distance gates are the item most worth a real derivation -- OoT's 80/800 are
model units and do not transfer; a real fall here is ~11 world units.

Two bugs the user caught in Kronos are fixed but not yet reconfirmed there:
edge flickering (the skinner ran mid-draw and used int64 multiplies; now it
runs in the update step and uses slMulFX) and continuous rolling (ground
following drops the grounded flag on slopes, which read as a landing every
step).

Not verified: the fixes above have not been run in Kronos. How the walk/run threshold
reads in motion, and whether the landing and roll transitions feel right, need
a human look. `RUN_SPEED_MIN` in `link_anim_state.c` is the knob if the d-pad
reads as running too eagerly.

## Original assignment — 2026-09-16

The user explicitly asks Claude to start implementing walking, running, falling,
and rolling. Implement idle and landing transitions needed to connect them.
This supersedes the historical texture investigation below. Do the implementation,
build both images, and perform focused checks; do not stop at an animation plan.

Verify OoT's behavior before mapping the states. The user recalls an automatic
roll after running off a cliff, but is unsure. Local source:
`D:/Workspace-Claude/game-decomps/n64/oot/src/overlays/actors/ovl_player_actor/z_player.c`.
Around lines 9632–9660, landing handles run-jump/lock-on variants first, short
falls at <=80, then calls `Player_SetupRoll` for falls <800 with forward stick
and no carried actor. This is conditional landing behavior, not unconditional
midair rolling. Read the surrounding action, auto-jump and roll-input handlers
before implementing; also distinguish manually initiated ground rolls.
`Player_SetupRoll` around 6348 selects `PLAYER_ANIMGROUP_landing_roll`.

### Starting points

- `game/tools/build_link_model.py`: currently bakes a single child-Link idle
  pose. It already reads the skeleton and animation data; its top-level bind-pose
  docstring is stale. `game/assets/dynamic/link/source.json` selects animation
  0x3200, frame 0, US 1.2. Use original animation data and retain limb ownership
  or equivalent pose information rather than regenerating textures every frame.
- `game/src/demo.c`: 30 Hz movement/gravity, velocity and last-safe respawn,
  camera, title state. Drive animation from actual motion/grounded state and a
  stable clock. Expose the state cleanly where needed. Ensure collisions that
  stop movement also stop locomotion; avoid double-applying animation root motion.
- `game/src/kokiri_sgl.c`: forest/Link upload and submission. Preserve baked
  negative Y, limb normals, face textures, and the native source-world scale.
- `shared/lib/collision/kokiri_collision.c`: Link uses a smaller actor clearance,
  feet-based floor queries, fixed-point fall velocity, downhill ground-follow
  tolerance and safe recovery. Preserve bridge clearance and downhill behavior.
- Current controls use a digital D-pad. Establish an explicit walk/run policy
  consistent with existing controls; document any necessary roll/speed binding.
  Keep diagnostic A, Start, and L/R mappings in mind before assigning controls.

### Current presentation and constraints

- Five slow, wider title routes (~104 seconds total), including fairy-area passes.
  `build_title_paths.py` searches actual collision geometry, favors passage
  centres, smooths curves and checks every final segment with 16-unit clearance.
  Generated `title_paths.h` is cached by input/tool hash and tracked as a build
  dependency. The old extreme tree-closeup shots are removed from normal play.
- Forest fog blends palettes toward yellow-olive; mesh/checkerboard fading in
  the last eighth of visibility. Cutoff 1,310 units is half the original forest
  renderer's 2,620-unit range. Shared tiles conservatively use their closest
  surface's fog amount. It is an approximation, not N64 per-pixel fog.
- Ten small fairy billboards use the original fairy wing texture with separate
  orbit/bob phases at Kokiri/Mido/Saria homes. No NPC models added yet.
- Title regression fixed: Jo's B1 allocator overlapped SGL's fixed font storage.
  Sky table is now at B1+0x1f000 via `slBackColTable`. Do not put it at B1+0 or
  reintroduce speculative BGON overrides. Black padding/final scanline keeps
  the outer screen black. Title and black border observed in both display modes.
- Last builds: standard `.bss` ends 0x060a4cf0 (9,488 bytes headroom); hi-res
  0x060a4d90 (9,328 bytes). SGL work area starts 0x060a7200. Animation storage is
  constrained: budget it before choosing a full pre-baked-frame approach.
- Forest+Link texture/CLUT bytes 425,288; fairy adds 512 = 425,800 of 432,632,
  leaving 6,832 VDP1 texture bytes. Combined base geometry 2,446 polygons and
  2,112 vertices, before fairies. Keep the existing hard capacity checks.

### Verification and user's desktop

Both standard and hi-res images rebuilt; 59 game tests passed. Final route
generation validated all five paths. Background captures observed title, black
surround and olive haze in both modes. This is not hardware verification or
proof that every camera framing is artistically final.

The user needs the main screen for another game. Do not activate Kronos or use
global keyboard events/desktop screenshots. `game/tools/capture-kronos.ps1`
uses PrintWindow and works with Kronos unminimized behind other applications.
`-ShowBehind` makes a hidden test window drawable at the bottom of the stack
without activation. Local ignored `game/build/generated/start-background.ps1`
was used to launch tests hidden; do not assume it exists on another checkout.
The test emulator was closed after verification to free the user's GPU.

Evidence (local/ignored): `game/build/generated/fog-tour-standard.png`,
`fog-tour-standard-2.png`, `fog-tour-hires.png`, `title-memory-fixed.png`.

Preserve the existing dirty worktree, inspect the diff before editing, and do
not reset it. No commit made in this pass. Update VSLICEPROGRESS.md as animation
lands. NPCs, music timing, and a renderer rewrite are not this assignment.

Handoff prepared by Codex for the user to relay to Claude. On receiving it,
Claude should begin the implementation above and send a short reply through
the user when there is progress or a question for Codex.

---

# Historical texture handoff

## Astra's current result — 2026-09-16

Read the **Astra implementation** section at the bottom of
[TEXTURE_PLAN.md](TEXTURE_PLAN.md) first. The earlier brief below is historical.

- The source-UV hybrid converter is now the default game path, not just a plan.
  Shared/repeating quads, larger density-budgeted bakes, tall-edge splits, and
  50 capped close-ground subdivisions are implemented.
- Important correction: the checker did not settle the whole cause. On the
  same moving close-treeline probe, the legacy path disappears while the split
  path retains coverage. Submission success alone never established visibility.
- Combined with Link: **2,446 polygons, 2,112 vertices, 425,288 texture/CLUT bytes**.
  VRAM commands are reserved separately below `0x16500`; texture capacity is
  432,632 bytes, not Jo's inconsistent nominal size. Do not subtract commands
  twice or claim Work RAM SpriteBuf replaces VDP1's hardware command table.
- Flat Link uses 95 tiles / 7,880 bytes including CLUTs; face art retained.
- Collision, controls, title/music and baked-Y boundary preserved. The generated
  manifest has connected render components/bounds for later object visibility;
  no runtime visibility toggling or collision partitioning yet.
- 52 game tests pass. The optional hi-res probe has rendered ground and treeline
  through approach/turns with zero refusals. See local `acceptance-sweep-*.png`.
  This is not a claim that all affine distortion or every near-plane case is gone.
- Both standard and hi-res normal-play images were rebuilt after the probe.
  Standard title-to-gameplay, Link movement and turning were checked in Kronos;
  normal hi-res title-to-gameplay was also observed (`gameplay-hires-final-1.png`).
  hi-res retains 25,024 bytes of `.bss` headroom below the unchanged SGL area.
- Build/run/fallback/probe commands are in [game README](../README.md). Normal
  launch images must be rebuilt without `TEXTURE_PROBE=1` after diagnostic use.

Nothing committed in this pass. Preserve the human's `LICENSE` edit. Once the
human confirms close-view playability, continue walk/idle animation, then one
NPC conversation, menus and SFX. Do not restart music timing/optimization work.

## Original investigation brief (historical)

## Current project

The Jo reorganization is integrated into main. Active game: `game/`; reusable
libraries/assets: `shared/`; GUI launcher and mesh workshop: root `tools/`.
Start the selector with `launch-game.bat`. Standard and 320x480i remain separate.
Build from `game/` with `./build.sh` or `./build.sh --hires`.
Generated code/images/staging live in `game/build/`. Do not resume the archived
libyaul renderer or its performance experiments. Preserve unrelated local edits.

Both modes built after relocation; 39 game and 10 workshop tests passed. Both
GUI smoke checks passed. Existing Forest quad editing revisions/preferences were
preserved in ignored `workspace/meshes/`, including the original Forest asset ID.
Those candidates are **not runtime-ready** and Prefer quads still does not affect
the game build.

## Human priority

Really fix the polygon/texture warping near the camera. It is almost unplayable,
not cosmetic polish. The human has seen other Jo Engine projects with much less
warping. Do not dismiss this as an unavoidable hardware limitation without
checking how our geometry, texture mapping and clipping differ from those paths.
There is no established cause yet. Higher resolution is not the fix.

## Focused investigation and implementation

1. Reproduce one clearly failing ground polygon at a recorded camera pose. Check
   the same view while walking and turning, including a near-plane crossing.
   Distinguish ordinary within-face distortion from incorrect clipped coverage,
   corner/texture mapping or ordering. A small diagnostic texture is useful if
   needed; do not launch a broad renderer rewrite or benchmarking exercise.
2. Compare the path against a working local Jo/SGL textured example: corner
   ordering, texture assignment, polygon shape/size and near-clip behavior.
   Use the human's other examples if supplied; none have been identified by name
   in the handoff, so do not claim that comparison has already been done.
3. Relevant files: `game/tools/build_sgl_scene.py`, `game/src/kokiri_sgl.c`,
   `shared/tools/build_kokiri_scene.py`. Current input repeats the third index as
   the fourth corner, textures are baked per triangle, and SGL attributes include
   `UseNearClip`. These are facts to investigate, not proof of a particular cause.
4. Implement the demonstrated remedy. If it needs subdivision or genuine quads,
   preserve texture coordinates/material boundaries and update texture baking
   and runtime input together. Merely changing corner indices or selecting the
   workshop's Prefer quads option is not a complete conversion. If clipping is
   responsible, preserve the correct texture mapping on the clipped geometry.
5. Preserve world-space collision, controls, Link, title/music and both launch
   modes. Y negation is baked at the rendering boundary; do not reintroduce a
   reflection that breaks the existing normals/culling. Keep polygon, vertex,
   texture and RAM capacity checks enabled if geometry counts change.

## Done enough

Show the previously failing close-ground view readable during movement and turns,
without giant stretched wedges, missing ground or hidden faces used to mask it.
Keep an honest before/after at the same pose, plus a short check in the other
display mode. Build and focused checks suffice; expand only to investigate this
major bug. Accepted submissions and a high FPS counter alone do not prove a fix.

Then resume walk/idle animation, one NPC conversation, menus and sound effects.
Music timing and general efficiency are not gates. Update `VSLICEPROGRESS.md`.
