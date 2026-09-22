# Kokiri slice action matrix (plan step 1)

Audit only. No gameplay code changed in this task. Branch
`feature/kokiri-slice-actions`, cut from `dev`.

Source root: `D:/Workspace-Claude/game-decomps/n64/oot` (US 1.2 aligned).
Player source: `src/overlays/actors/ovl_player_actor/z_player.c` unless noted.
Crawlspace entry/exit: `Player_TryEnteringCrawlspace` (z_player.c:7607),
`Player_TryLeavingCrawlspace` (z_player.c:7737), used at :7804 and :13047.

Saturn-side current implementation lives in `src/player_input.c`,
`src/link_anim_state.c`, `src/gameplay.c`.

## Planned control mapping (supersedes the 2026-09-18 mapping)

| Input | Behavior | Now |
|---|---|---|
| D-pad | Move | done |
| B | Walk/run toggle (slice exception, N64 has analog) | done |
| Hold Z + D-pad | Target-facing movement, strafe/back up with no target | done |
| Z | Acquire/hold/release target; recenter when none | done (NPCs only) |
| A | Context: talk, inspect, open, climb/crawl entry, grab; roll | partial |
| Z + A + dir | Sidehop / backflip / jump slash | missing |
| X | Sword attack | basic swing |
| R | Shield / guard | hold guard only |
| Y | Manual jump (slice exception, not original) | done |
| Hold L + D-pad | Look around (moved off Z) | done |
| C + D-pad | C-item routing | edges only |
| Start | Pause/inventory | menu exists |

The Z/L swap is the plan's fix for the old Z-look conflict. Help text, mapper,
host tests and OPUS_HANDOFF must change in the same task as the code.

## Action matrix

Columns: action | input | source condition | animation | motion owner |
current | gap.

### Locomotion
- Idle | none | `Player_Action_Idle` | idle clip | none | implemented | needs idle variants/fidget.
- Walk / run | D-pad (+B mode) | speed thresholds from analog magnitude | walk/run cycles | collision-driven | implemented | slice uses two discrete speeds, not analog ramp.
- Turn in place | D-pad against facing | `Player_Action_TurnInPlace` | turn clips | rotation only | missing | Link snaps to new heading.
- Fall | leaving ground | airborne action | fall clip | gravity | implemented | no long-fall scream/damage tier.
- Land | regain ground | fall distance chooses soft land / land-roll | landing, roll | one-shot lock | implemented | roll threshold not verified against source fall distance.
- Manual roll | A while moving | `Player_Action_Roll` | roll clip | root travel in source | implemented: A rolls when nothing else claims the press, and the roll carries Link forward with a decay to a stop | no wall-impact bonk, no invulnerability window; source uses a speed target with a floor, which is now matched.
- Wall impact | roll into wall | source bonk | bonk clip | stop | missing | —
- Damage / knockback | enemy or boulder contact | damage actions | hurt clips | impulse | missing | required by step 4 boulder.
- Slide on slope | steep floor | `Player_Action_SlideOnSlope` | slide clip | collision | missing | check Kokiri slopes before deciding scope.

### Targeted movement
- Target on/off | Z | attention system, `z_actor.c` | — | — | L-hold toggle vs NPC list only | needs shared registry (step 5), non-NPC targets.
- Strafe / back up | Z + D-pad | target-facing locomotion | sidestep/back clips | collision | implemented, with and without a target | still uses the walk/run clips; no dedicated sidestep/backstep clips.
- Sidehop / backflip | Z + A + dir | jump state selection | hop clips | root arc | missing | —
- Jump slash | Z + A forward with sword | attack jump | jump slash | root arc | missing | —

### Traversal
- Ledge auto-jump | run off a valid edge | source edge check | hop clip | arc | missing | N64 has no manual jump; keep Y as the stated exception.
- Ledge grab / hang / pull up / drop | approach wall edge | wall flags | hang clips | snap to edge | missing | needs collision wall metadata preserved in extraction.
- Ladder / vine climb | A at climb surface | wall type | climb cycle | snapped travel | missing | Link's house ladder is the slice case.
- Crawlspace enter / travel / reverse / exit | A at crawl wall | `Player_TryEnteringCrawlspace` / `Player_TryLeavingCrawlspace` | crawl clips | axis-locked travel | missing | maze route; standing must not bypass the low opening.
- Push / pull / lift / carry / throw | A at grabbable | grab actions | grab clips | object-linked | missing | only if a source grabbable exists in Kokiri; audit in step 4.
- Shallow water / swim / dive | water surface | water actions | swim clips | buoyancy | missing | Kokiri stream is shallow; decide wade-only after collision audit.

### Combat and items
- Sword swings, combo, thrust, spin | X, held X, Z variants | attack table | attack clips | small root step | single swing only | no combo, thrust, spin, or attack root motion.
- Shield guard / crouch stab | R, R+A | guard actions | guard clips | none | hold-guard only | no crouch stab, no deflect reaction.
- Talk / read / open chest / open door | A | `Player_Action_Talk`, `Player_Action_TryOpeningDoor` | talk, open | none | dialogue partial | chest open and door open animations missing.
- C-item use / aim | C + D-pad | `PLAYER_IA_*` table | item clips | — | edges reported only | slingshot, sticks, nuts are outside the slice unless earned here.

### Explicitly out of slice
Adult actions, hookshot/longshot, bow, hammer, magic, masks, ocarina,
time travel, swimming gear, Din's Fire, boomerang: no child-reachable source
grant before entering the Deku Tree, so they stay unimplemented by design.

## Input rules to define with the mapping change

1. Chord priority: Z, then L, then C, then locomotion.
2. A direction consumed by a modifier never reaches locomotion.
3. Each press consumed once across menu, dialogue, targeting, traversal.
4. Dialogue or pause open: no movement, attack, guard, jump or traversal edge
   leaves the mapper.

## Acceptance status

Every reachable action above has a disposition. Nothing in the slice scope is
left as an unexplained "pending input": the remaining gaps are named as
missing work for plan steps 2-5.
