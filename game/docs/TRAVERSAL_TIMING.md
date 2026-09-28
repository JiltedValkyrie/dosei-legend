# Traversal timing: OoT 20 Hz source -> 30 Hz runtime

Rule for every M1+ port of player/actor motion constants. Read before pasting
any number from `z_player.c` or an actor.

## Source clock

- NTSC gameplay updates at 20 Hz: `R_UPDATE_RATE` = `SREG(30)` = 3 VIs
  (`GameState_Init`, game.c). Every per-frame constant is a 20 Hz value.
- `Actor_UpdatePos` (z_actor.c) moves by `velocity * speedRate`, with
  `speedRate = R_UPDATE_RATE * 0.5` = **1.5**. Velocity is then changed by
  gravity once per frame (`Actor_UpdateVelocityXZGravity`), with no rate factor.

## Conversion (runtime step = 1/30 s)

| Quantity | Source unit | Port |
|---|---|---|
| Velocity / speedXZ | u per 20 Hz frame, applied x1.5 | **same value**, u per 30 Hz step (1.5 x 20 = 30 u/s per unit) |
| Acceleration / gravity | velocity change per 20 Hz frame | **x 2/3** per step |
| Frame counts, timers | 20 Hz frames | **x 3/2** steps (round, say which way) |
| Animation playback | `playSpeed * R_UPDATE_RATE * 0.5` = 1.5 x playSpeed frames per update (z_skelanime.c LinkAnimation_Loop/Once) | **playSpeed frames per step**. Locomotion clips keep the slower presentation tuning (2/3 per step, `phase_ninths` +6; BUG-004). M1c ledge climbs use the source rate (1.3 per step) |
| Distances, heights, radii | world units | unchanged |

Examples: gravity -1.0 -> -0.667 u/step^2 = **-171 Q8**; terminal velocity
-20 -> **-5120 Q8**; a 6-frame wait -> 9 steps; a 3-frame delay -> 4.5 -> state
the rounding (5 steps = the source's frame boundary after the delay).

## Current runtime vs this rule

- Gravity fixed in M1b: `GRAVITY_Q8 -171`, `TERMINAL_VELOCITY_Q8 -5120`
  (were -114 / -3413, missing the 1.5). Y jump velocity 1792 -> 2208 Q8 keeps
  its 51-unit apex; airtime 31 -> 25 steps.
- Automatic jump launch (func_8083A4A8, child boots): 7.5 -> 1920 Q8, or
  1.25 + 0.4 * speed; values carried unchanged per the velocity rule.
- Run/walk speeds (`LINK_RUN_SPEED_Q8`) already include the 1.5 factor.
- Scope: this is the Actor_UpdatePos / gravity baseline. Audit each player
  handler's own timers and speeds before converting them (Astra, M1A_REVIEW).

- M1c ledge climb: delay timer 3 / 6 frames -> 5 / 9 steps (rounded up), cap
  100 -> 150; shape.yOffset step 150 per update (1.5 units) -> 1 unit per step.
- M1e climb: playSpeed = |stick| x 0.05 (x 0.0325 sideways), 1.0..3.35 frames
  per step; ladder ends 4/3; turn toward the wall 800 per update x 1.5 ->
  800 per step. Root motion at actor scale 0.01 (AnimTask_ActorMovement).
- M1d hang: grab/wait clips at playSpeed 1.0 (1 frame per step), pull-up 1.3;
  air speedXZ decay 0.1 per frame -> 17 Q8 per step; the departure step's
  drop (-4 glue + gravity) -> 4.67, taken as 5.

## Root motion

M1k water: buoyancy acceleration .1 becomes 17 Q8 per step, velocity damping
terms also use x2/3. Swim stroke deceleration (.02*speed+.05) becomes roughly
speedQ8/75+9; stroke animation runs one source frame per step. Dive frame 20
sets velocity -2 unchanged; source scale depth limits 120/240/360 are distances.
The submerged hazard eligibility counter 300 becomes 450 steps, not a death
timer. Dive turnaround currently approximates the source pitch condition with
8 steps (BUG-025), so it must not be described as a source timer conversion.

Clips are pose-only; collision owns translation. A traversal clip with
authored root travel (climb, ledge, crawl) either has its root replaced by
the standing reference (as `fall` is, build_link_model.py) or drives the
position once from the clip -- never both.

Child root adjustment (M1c): z_player_lib.c scales a child's root translation
by 0.64 unless the clip plays with DISABLE_CHILD_ROOT_ADJUSTMENT.
build_link_model.py applies it offline to every gameplay clip; the opening's
child-authored clink_op3_* clips stay raw. The step-ups keep their root (the
actor moves once, at the start, as the source does) and shape.yOffset hides
the difference.

## Feet vs camera anchor

`bg_*` queries (kokiri_collision.h) take FEET. The legacy movement API keeps
the floor+90 eye anchor. New player code works in feet and converts once at
the boundary; do not mix the two in one function.
