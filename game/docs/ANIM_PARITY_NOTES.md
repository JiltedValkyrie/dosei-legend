# Animation and platforming parity — for Astra to check against the decomp/ROM

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

### 1. Fall distance scale — the big one

**ASSUMED.** OoT's 80 and 800 are model units on Player's scale. Claude first
transferred them directly, assuming this project's world units matched. They do
not. The user reports **a real fall here is about 11 world units**, so an
80-unit gate meant *no fall ever registered as a landing at all*.

Current values in `game/src/link_anim_state.c`:

```c
#define SHORT_LANDING_FALL  4     /* was 80  */
#define ROLL_LANDING_FALL   40    /* was 800 */
```

These were scaled from the user's 11-unit observation, keeping OoT's roughly
10:1 ratio. **Nobody has derived the true conversion factor.** Worth doing
properly: work out the model-unit-to-world-unit ratio for this project's scale
(`source.json` uses 0.0145 for the mesh, but collision and gravity are in
native source units, which is a different question), then recompute both gates
from OoT's 80/800 rather than from a single observed drop. If the real ratio
disagrees with 4/40, trust the ratio.

Related: `LINK_VOID_DROP` and `EYE_HEIGHT` (90) in the collision code are on
the same scale and may help pin the factor down.

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

### 5. Landing/fall blip suppression

**ASSUMED — and this is a workaround, not a model of OoT.**
`kokiri_collision_fall()` only reports grounded when Link sits *exactly* on the
floor plane, so ground following drops the flag for single steps on slopes and
stairs. That made him "land" continuously, and with any movement that fired the
roll — the bug the user saw as "rolling all over my screen".

Two guards were added:

- `FALL_STATE_STEPS 4` — consecutive ungrounded steps before the fall clip
  takes over.
- A landing now also requires `fall_units > SHORT_LANDING_FALL`.

Both numbers are guesses. The cleaner fix is probably in the collision layer:
OoT tracks an explicit grounded/`actor.bgCheckFlags & 1` state with tolerance
rather than an equality test. If you rework that, these two guards should
shrink or disappear.

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

**Edge flickering, black ↔ fog.** The skinner ran inside the draw callback,
between the forest submission and the HUD, doing ~4,800 fixed-point multiplies
per posed frame — enough to overrun the field. Two fixes: skinning moved into
the 30 Hz update step (once per frame, after catch-up steps settle), and
`FIXED_MUL` switched from an `int64_t` expression to `slMulFX`. The `int64_t`
form compiled to a libgcc call rather than the SH-2's 32x32->64 instruction.
**Worth watching:** if flicker returns under load, the skinner is still the
most expensive thing Link costs, and the next lever is posing at 15 Hz or
skinning only limbs whose rotation actually changed.

**Continuous rolling.** Covered in item 5 above.

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
