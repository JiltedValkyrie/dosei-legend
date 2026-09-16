# Animation and platforming parity — for Astra to check against the decomp/ROM

## Astra speed/timing follow-up

Native outdoor child run cap is 5.5, from PLAYER_BOOTS_KOKIRI_CHILD in
`z_player_lib.c`. `Actor_UpdatePos` multiplies velocity by R_UPDATE_RATE*0.5,
which is 1.5 at NTSC gameplay's 20 Hz. Thus 165 world units/s, or 5.5 per
30 Hz step in this port. Actor movement now preserves fractions and normalizes
diagonals. Free camera retains its previous speed.

Animation now uses a slower tuned 20-source-frame/s phase and interpolated
poses. This is intentionally NOT labeled exact N64 cadence: Link's original
animation update has the same *0.5 timing factor plus speed/action-dependent
playback. A blanket "OoT 20 Hz therefore 20 animation fps" is not valid.
The decimated fall advances at one third of that stored-frame rate and holds
the final pose. Run selection was adjusted for the corrected movement speed.

L camera reset is implemented; full targeting is not. See OPUS_HANDOFF.md for
the current vs proposed digital-pad layout and remaining control decisions.

## Astra fix: corrupted animation frame decoding

Following the user's continued blinking/tumbling report, found a concrete
importer defect independent of landing gates and skinning performance:
Link animation records are 134 bytes (22 Vec3s plus a two-byte face field),
but both Python readers advanced by 132. Frame zero worked; every subsequent
frame progressively misread root translation and limb rotations. The original
bind-pose test only exercised frame zero and could not detect this.

Evidence: local OoT `z_skelanime.c:900-901` loads each player frame using
`sizeof(Vec3s) * limbCount + 2` for both offset and size. Player initializes
22 entries with flags 9 (root plus 21 skeleton limbs).

Fixed `read_animation()` stride and made `read_animation_frames()` share that
reader. Added independent packed-fixture tests for nonzero and decimated
frames, including a sentinel face word. This corrects corrupted pose data;
it does not establish that all flicker is solved or playback has full parity.
No state-machine, collision, controls, or rendering changes in this fix.
Kronos gameplay verification still required; do not call it visually confirmed.

## Astra review: correction to the scale premise

The scale explanation in item 1 below is incorrect. In the local OoT
`z_player.c:5831`, `fallDistance` is `fallStartHeight - actor.world.pos.y`
(with an integer cast), so it is a WORLD-space distance, not mesh/model units.
`shared/tools/build_kokiri_scene.py` reads native collision coordinates and
packs them without a scale conversion. The Link mesh recipe's 0.0145 does not
rescale collision or falling distances.

The 11-unit value is `ACTOR_GROUND_FOLLOW_DROP`, the downhill floor-following
tolerance. It is NOT a measured cliff fall or a basis for converting 80/800
to 4/40. Those replacement thresholds have no demonstrated parity basis.
Also, `kokiri_collision_move_actor()` already follows nearby downhill floors;
the equality check in `kokiri_collision_fall()` alone does not prove ordinary
slope motion loses grounded state. Reproduce and trace the transition first.

Code review confirms posing is called from the update code and multiplication
uses `slMulFX`. That does not establish the claimed cause or resolution of
visual flicker. I independently ran all 73 host tests successfully. Runtime
flicker and repeated rolling remain UNVERIFIED; no gameplay input or desktop
capture was used, and no code or images were changed in this review.

Gravity still needs a full trace: normal player setup at `z_player.c:6993`
sets minVelocityY through `FRAMERATE_CONST(-20, -24)` and gravity from REG(68),
which `z_player_lib.c` populates from boot registers. Do not infer the normal
gravity solely from the -1 assignment in the special exit-grotto action.

The original notes below are retained as Claude's report, not validation.

Written for: Astra (Codex), reviewing Claude's animation work against the
ntsc-1.2 decomp and ROM.

Claude implemented Link's locomotion animation and hit two bugs the user caught
in Kronos. The fixes are in, but several values here were chosen by
**observation and scaling, not by reading the decomp**. Those are the ones worth
your time. Everything flagged **ASSUMED** is a guess that needs checking against
`z_player.c` / `z_player_lib.c` and the real game feel; everything flagged
**VERIFIED** was read out of the source.

Source of truth: `D:/Workspace-Claude/game-decomps/n64/oot`, ntsc-1.2, ROM md5
`57a9719ad547c516342e1a15d5c28c3d`.

## What was verified against the decomp

**VERIFIED — the landing branch shape.** `z_player.c` around 9632: landing
handles run-jump and lock-on variants first, then `fallDistance <= 80` selects
the short landing, then `fallDistance < 800` with the stick forward and no
carried actor calls `Player_SetupRoll`, which picks
`PLAYER_ANIMGROUP_landing_roll` (around 6348). The user's recollection of an
automatic roll after running off a cliff is this conditional *landing* roll.
There is no unconditional mid-air roll, and the implementation does not add one.

**VERIFIED — the animation header table layout.** gameplay_keep holds the
573 `LinkAnimationHeader`s as one contiguous 8-byte array in the same order as
`assets/objects/gameplay_keep/player_anim_headers.c`. `build_link_model.py`
anchors on the recipe's known idle offset (0x3200) and derives every other
symbol by index, then validates all 573 entries (plausible frame count, zero
pad, segment-7 pointer) before using any of them.

**VERIFIED — limb pose composition.** Limbs translate by `jointPos` in the
parent's frame then rotate, ZYX, with limb 0 taking the animation's root
translation. The runtime skinner reproduces this, and a test re-poses the bind
pose from the emitted tables and compares against `LINK.BIN`'s own vertices.

## What is ASSUMED and needs your check

### 1. Fall distance scale — RESOLVED, Astra was right

**CORRECTED.** Claude rescaled `SHORT_LANDING_FALL`/`ROLL_LANDING_FALL` from
80/800 to 4/40 on the theory that OoT's values were model units. They are not:
`z_player.c:5831` computes `fallDistance` as `fallStartHeight - world.pos.y`,
world-space, and this project keeps native collision coordinates without a
scale conversion. The 11 the rescale was built on is
`ACTOR_GROUND_FOLLOW_DROP`, a downhill floor-following tolerance, not a
measured cliff drop.

**80 and 800 are restored** and a test now pins them with that reasoning.
Nothing further needed here unless the gravity trace (item 2) changes the
picture.

### 2. Gravity and terminal velocity

**ASSUMED / NOT CHECKED.** `shared/lib/collision/kokiri_collision.c` applies
`GRAVITY_Q8` and clamps to `TERMINAL_VELOCITY_Q8` at 30 Hz, described as OoT's
20 Hz gravity time-scaled. Claude did not verify those constants against
`Player_UpdateCommon` / the actual `gravity` and `terminalVelocity` fields, and
the whole fall-distance question above depends on them. If the gravity curve is
wrong, the distances will never line up no matter how the gates are tuned.

### 3. Walk vs run threshold

**ASSUMED.** `RUN_SPEED_MIN 10` and `WALK_SPEED_MIN 1`, in world units per
30 Hz step. Chosen to suit the digital d-pad, not derived from OoT's speed
bands. Real OoT picks the walk/run animation from `linearVelocity` against
analog stick magnitude, and blends; a digital pad can only ever approximate
this. Decide whether the slice wants a single run speed or a genuine walk/run
split, and whether the threshold should come from OoT's own speed constants.

### 4. Animation playback rate

**ASSUMED.** Clips advance one frame per 30 Hz gameplay step, i.e. every clip
plays at 30 fps regardless of its authored rate. OoT's `SkelAnime` advances by
`playSpeed` at 20 Hz and interpolates between keyframes. Two consequences worth
checking: clips may be playing at the wrong speed relative to Link's actual
movement (feet sliding), and nothing interpolates, so decimated clips will look
steppier than the original. `fall` is currently sampled every 3rd frame.

### 5. Repeated rolling — CAUSE STILL UNKNOWN

**WITHDRAWN.** Claude attributed the continuous rolling to the equality test in
`kokiri_collision_fall()` dropping the grounded flag on slopes, and added a
`FALL_STATE_STEPS` debounce plus a landing distance gate. Astra is right that
this does not hold: `kokiri_collision_move_actor()` snaps `y` onto the floor
plane when it follows ground downhill, which is exactly what the equality test
then sees, so ordinary slope motion keeps the flag. **Both guards have been
removed** and the landing branch is back to OoT's shape.

Two other theories were checked and also do not explain it:

- *Stale state across sessions.* `link_anim_reset()` only cleared the skinner's
  cached pose, never the state machine. Real gap, and `link_anim_reset_state()`
  now exists and is called on spawn — but `demo_link_active` is never cleared,
  so spawn runs once per boot and stale state cannot carry over. **Not the
  cause.**
- *A one-shot looping.* A landing or roll only advances while grounded and
  hands back to locomotion when its clip ends, so it cannot self-sustain on
  flat ground.

So the cause is genuinely not established, and no more guesses are going in
until it is traced. The A-button overlay now prints the state machine's actual
inputs on row 3:

```
g<grounded>  L<landings seen>  d<fall distance at the last landing>
```

Read `s` first. If Link **looks** like he is rolling while `s` is not 5, the
pose is wrong and the landing logic is innocent -- that is the corrupted-frame
case, and the frame-stride bug found in `read_animation()` (134-byte stride,
not 132) is a strong candidate for having caused exactly that appearance. If
`s` is 5 and `L` climbs on flat ground, a real grounded transition is firing
and `d` names the gate that chose the roll. That measurement is the next
step, and it needs a Kronos run.

### 5b. Pad layout — decided, proposed, and open

**IMPLEMENTED.** Diagnostics moved from A to a held **L+R** chord. The chord
consumes both buttons, so requesting diagnostics never also recenters (L) or
triggers whatever R becomes. The edge is detected in `demo_update()` with the
rest of the input rather than sampled again in `main.c`, so the two cannot
disagree on the frame one button arrives first. A is now free for the action
button. Start was not used for this: it would risk the title transition.

**IMPLEMENTED.** The overlay prints state and landing evidence on one line:
`s<state> g<grounded> L<landings> d<fall distance>`. They were on separate
rows, which is precisely how the corrupted-pose case gets misrecorded as a
state bug. See item 5 for how to read it.

**PROPOSED, NOT IMPLEMENTED.** A = action/roll/talk, B = sword, C = hold to
walk, X/Y/Z = three equipped items, R = shield, Start = pause/menu. C-to-walk
is the strongest of these for a digital pad: walk/run already keys off the
distance actually moved, so C only has to clamp movement speed and the existing
threshold picks the clip with no state-machine change. B = sword additionally
needs a clip baked into `CLIPS`; none exists yet.

**OPEN — first-person look has no home.** R + D-pad was suggested and
withdrawn: it consumes directional input while shielding, and shield stance and
look mode need an explicit distinction before sharing a button. Unresolved.

### 6. Manual ground roll is unbound

**NOT IMPLEMENTED.** `link_anim_update()` takes a `roll_pressed` argument and
`demo.c` always passes `false`. The landing roll works; a deliberate roll has
no button. Diagnostic A, Start and L/R are taken, so this needs a control
decision before it can be wired.

### 7. Root motion

**INTENTIONAL DIVERGENCE.** Translation comes entirely from collision; the
clips are pose-only and their root translation is used for limb placement but
never applied to Link's world position. OoT's locomotion is partly root-driven.
This avoids double-applying movement, but it does mean foot placement will not
match the original exactly.

## Two bugs found in Kronos, and what caused them

Recording these because both were invisible to the build and the tests.

**Edge flickering, black ↔ fog.** Astra is right that the code change alone
does not establish the cause. What is certain: the skinner ran inside the draw
callback doing ~4,800 fixed-point multiplies per posed frame, which is real
per-frame cost in the wrong place. Whether that was *the* cause of the flicker
is unproven, and the back-screen table (written once at init, at B1+0x1f000)
was not touched by any of this work. Two fixes: skinning moved into
the 30 Hz update step (once per frame, after catch-up steps settle), and
`FIXED_MUL` switched from an `int64_t` expression to `slMulFX`. The `int64_t`
form compiled to a libgcc call rather than the SH-2's 32x32->64 instruction.
**Worth watching:** if flicker returns under load, the skinner is still the
most expensive thing Link costs, and the next lever is posing at 15 Hz or
skinning only limbs whose rotation actually changed.

**Continuous rolling.** Cause not established; see item 5. The fix Claude
committed for it has been reverted, so this bug should be assumed present.

## Build note that cost real time

Prebuilt SDK objects under `build/obj*/` are **not** rebuilt when a makefile
define changes. A stale `core.o` held the old
`JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC` and made the `.bss` boundary check look
unfixable through three rounds of shrinking genuine data. If a define change
appears to do nothing, delete `build/obj/core.o` and `build/obj-hires/core.o`.

The arena is now 180,224 bytes (was 221,184) to pay for the clip tables.
Measured demand is ~17 KB; the A overlay prints `jo_memory_usage_percent()`
alongside the animation state and frame, so the real figure can be read in
Kronos rather than guessed at again.

## Current state

Both images build clean with no warnings; 73 tests pass. Headroom is 26,992
bytes standard / 26,800 hi-res, against 9,488 before this work.

Kronos-verified by the user: the flicker and the rolling bug were both reported
from Kronos and the fixes are built but **not yet confirmed there**. Nothing
about walk/run feel, landing feel or fall distances has been signed off.
