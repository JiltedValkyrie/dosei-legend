# Bug and feature log

## Human rule - effective for future work, 2026-09-25

Prioritize getting the game playable. Fix severe current blockers immediately;
record small bugs, potential issues and optional features here, then continue the
assigned milestone. Do not turn every finding into a prerequisite or side project.
This rule applies going forward only: existing M1a review/fix requirements remain
unchanged. Do not reopen, downgrade or waive those findings under this rule.

### Triage

| Priority | Meaning | Action |
|---|---|---|
| P0 - severe | Crash/hang, save loss/corruption, memory corruption, cannot boot/build the required image, or required gameplay/progression cannot proceed | Fix now before dependent work; notify the current owner when their files are involved |
| P1 - important | Confirmed gameplay defect with a workable path, or a defect in a system not yet used by the current playable route | Log with impact and a concrete revisit trigger; fix in the relevant milestone, without blocking unrelated work |
| P2 - minor | Cosmetic defect, small behavior mismatch, maintainability issue or unconfirmed potential problem | Log evidence/uncertainty; defer until related work or polish |
| Feature | Optional improvement or new scope | Record benefit and dependencies; implement only when assigned or approved as part of the plan |

Priority follows actual impact and reachability, not how easy a problem is to
imagine. A suspected severe failure warrants a bounded check now; call it confirmed
only when evidence supports that. Escalate deferred issues when a new feature makes
them active, their impact increases, or they block a required route.

Existing required milestone features remain required; this log does not silently
make them optional or declare unfinished work complete. Link planned work to its
milestone instead of duplicating its full specification here. No extra permission
is needed for fixes already within assigned scope. Coordinate shared-file ownership
without editing another agent's active implementation behind them.

### Review and work discipline

- Review reports separate severe blockers from nonblocking follow-ups. A minor or
  potential issue alone does not hold the next milestone; record it and continue.
- Make one concise entry per issue. Include observed evidence or mark suspicion,
  player impact, priority, owner (or unassigned), status and revisit milestone/trigger.
- For bugs, include reproduction/expected versus actual behavior when known. For
  features, include intended benefit, scope and dependencies. Link detailed review
  notes instead of repeating them. Do not invent a repro or claim a test was run.
- Keep investigation proportional. Do not derail playable work for broad cleanup,
  speculative hardening, refactors or optional source-parity improvements.
- On fixing an entry, record verification and commit when available. Keep a short
  resolved record so another agent does not rediscover or silently reopen it.
- Follow existing clean-only build, VDP2-menu, source/drop and milestone review
  requirements. This rule changes triage, not technical constraints or ownership.

## Issue tracking format

Use GitHub-style issue records below. These are local records, not published
GitHub issues. If later moved to GitHub, link the real issue and use its number;
do not invent GitHub issue numbers or claim an issue was filed remotely.

Labels: `bug` or `enhancement`; `priority: P0`, `priority: P1` or `priority: P2`
for bugs; `needs-triage` for unconfirmed findings. Feature priority is assigned
when scoped. Track assignee and milestone separately, as on GitHub.
State is **Open** or **Closed**; resolution is **Completed**, **Not planned** or
**Duplicate**. Open does not imply blocked: severity and dependencies determine
whether work stops. Optional features stay in backlog until assigned.

### Issue index

| ID | Title | Labels | Assignee | Milestone / revisit trigger | State |
|---|---|---|---|---|---|

| BUG-001 | Wall line-hit precedence | `bug`, `priority: P2` | Unassigned | Before wall-damage contact use | Open |
| BUG-002 | Failed collision decode mutates live data | `bug`, `priority: P2` | Unassigned | Scene-load recovery / M8 | Open |
| BUG-003 | Locomotion tests match obsolete source text | `bug`, `priority: P2` | Unassigned | Next locomotion-test edit | Open |
| BUG-004 | Locomotion clip cadence 2/3 of source | `bug`, `priority: P2` | Unassigned | M8 polish / locomotion anim work | Open |
| BUG-005 | M1c wall/ledge subset gaps | `bug`, `priority: P2` | Unassigned | Wall-sensitive actions (M1e-M1h) | Open |
| BUG-006 | Talk claims A before ledge climb | `bug`, `priority: P2` | Unassigned | M3 NPC placement near ledges | Open |
| BUG-007 | Floor jump/land SFX and second climb voice missing | `bug`, `priority: P2` | Unassigned | SFX bank rework / M8 | Open |
| BUG-008 | Source-snippet tests no longer compile | `bug`, `priority: P2` | Unassigned | Next edit of demo.c/cutscene.c/kokiri_sgl.c tests | Open |
| BUG-009 | Link drawn 1.45x source child vs source headroom | `bug`, `priority: P2`, `needs-triage` | Unassigned | Human visual check / M8 | Open |
| BUG-010 | 250 jump has no mid-air ledge grab | `bug`, `priority: P1` | M1d | M1d hang | Closed |
| BUG-011 | Released digital pad can interrupt climb early | `bug`, `priority: P2` | Unassigned | Next climb/input integration | Open |
| BUG-012 | 250-jump retained air speed cleared before launch | `bug`, `priority: P2` | Unassigned | Next air/grab integration | Closed |
| BUG-013 | Point-in-poly slack was 1 unit, source is detMax 300 | `bug`, `priority: P1` | Claude (M1e) | Fixed M1e; Kronos walk check | Closed |
| BUG-014 | Climb port subset gaps | `bug`, `priority: P2` | Unassigned | Vine-heavy scenes (M5) | Open |
| BUG-015 | House ladder descent from the porch unverified | `bug`, `priority: P2`, `needs-triage` | Unassigned | Human check vs real OoT | Open |
| BUG-016 | Grounded ceiling check missed the -7.5 dy | `bug`, `priority: P1` | Claude (M1f) | Fixed M1f; Kronos check | Open |
| BUG-017 | Crawl port subset gaps | `bug`, `priority: P2` | Unassigned | M1l camera / M8 | Open |
| BUG-018 | M1g turn/bonk source subset gaps | `bug`, `priority: P2` | Unassigned | M8 polish; M7 bonk actors | Open |
| BUG-019 | Bonk/hang voice sounds wrong to human | `bug`, `priority: P2`, `needs-triage` | Unassigned | Next Link SFX pass | Open |
| BUG-020 | Push-block live integration and source subset | `bug`, `priority: P2` | Unassigned | Before Deku Tree room 5 acceptance | Open |
| BUG-021 | Grass patch behaves like a raised floor | `bug`, `priority: P1` | Astra | Human pass 2026-09-26 | Closed |
| BUG-022 | Carry props and full reward integration pending | `bug`, `priority: P2` | Unassigned | M3 liftable props / M1i acceptance | Open |
| BUG-023 | Slope/fall runtime and M2 damage integration pending | `bug`, `priority: P2` | Unassigned | M1j runtime / M2 health | Open |
| BUG-024 | Grass overlap rustle effects and sound | `bug`, `priority: P2`, `needs-triage` | Unassigned | M3 grass / M8 feedback | Open |
| BUG-025 | Water traversal source subset and runtime acceptance | `bug`, `priority: P2` | Astra | M1k human check; M2/M5 integration | Open |
| BUG-026 | Dialogue special characters and missing dither backdrop | `bug`, `priority: P2` | Unassigned | Next dialogue/UI pass | Open |
| BUG-027 | Traversal camera source subset and runtime acceptance | `bug`, `priority: P2` | Astra | M1l human check / M8 | Open |

Original M1a blocking findings are resolved by the 2026-09-26 re-review in
[M1A_REVIEW.md](M1A_REVIEW.md). The following are nonblocking follow-ups.
Use local IDs `BUG-001`, `FEAT-001`, etc.; never reuse an ID. Add one index row and
one issue body per finding. Templates below are examples, not open issues.

## Open issues

### BUG-001: Wall sphere pass drops line-hit precedence

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** before wall-damage contact consumers.
**State:** Open.

#### Description and evidence

M1a disclosed that `bg_wall` does not seed the sphere pass with its line-test
polygon. Source preserves a prior data1 bit-27 wall when choosing contact identity.
Code-inspected gap; no player-visible failure reproduced. See M1A_REVIEW.

#### Steps / expected versus actual

Construct a line hit on a bit-27 wall followed by another sphere-pass wall.
Expected source contact precedence; current sphere pass starts without the line
polygon. Add an exact geometry repro when integrating that consumer.

#### Acceptance criteria

- [ ] Preserve source precedence and test the two-contact case.
- [ ] Ordinary wall movement remains unchanged where precedence is irrelevant.

### BUG-002: Malformed collision decode can damage live scene data

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** scene-load recovery / M8.
**State:** Open.

#### Description and evidence

`scene_flow.c` reuses the active collision buffer; `bg_mesh_decode` writes before
all metadata validation completes. A later rejection may leave the old scene's
collision partially replaced. Code-inspected and disclosed by Claude; normal
built assets/human smoke have not demonstrated a failure. Not an active blocker.

#### Steps / expected versus actual

Load a valid scene, then inject a same-size collision asset with invalid late
metadata. Expected safe failure with intact old scene or stopped gameplay;
current decode can partially overwrite live arrays before returning false.

#### Acceptance criteria

- [ ] Validate before mutation, stage the decode, or stop gameplay safely on failure.
- [ ] Malformed-load regression proves no continued use of partial collision data.

### BUG-003: Locomotion timing checks assume pre-analog implementation text

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next locomotion-test edit.
**State:** Open.

#### Steps to reproduce / evidence

Run `python -m unittest discover -s game/tests -p test_locomotion_timing.py`.
Previous review observed one failure and one error: source checks require old
`kokiri_camera_input_heading(demo_yaw, walk` and
`link_anim_roll_input(kokiri_camera_walking()` strings. Analog integration replaced
those calls; these checks predate M1a. Not rerun during this bounded re-review.

#### Expected versus actual

Tests validate current heading/roll cancellation behavior; stale text matching
instead fails even when that behavior remains valid.

#### Acceptance criteria

- [ ] Update checks for actual behavior/current integration without weakening roll rules.
- [ ] Module passes and still detects incorrect heading/roll cancellation.

### BUG-004: Locomotion clips play at 2/3 of the source rate

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M8 polish or the next locomotion
animation task. **State:** Open.

#### Description and evidence

z_skelanime.c LinkAnimation_Loop/Once advance `playSpeed * R_UPDATE_RATE * 0.5`
= 1.5 x playSpeed frames per 20 Hz update, i.e. playSpeed frames per 30 Hz
step. TRAVERSAL_TIMING.md said 2/3 frame per step; its row is corrected (M1c).
Locomotion clips keep the existing 2/3 presentation tuning (ANIM_PARITY_NOTES
item 4); M1c ledge climbs use the source rate. Code inspection, no report.

M1g handoff adds a roll-specific duration mismatch (reported by Claude, not
independently timed in Kronos): source Player_Action_Roll ends at frame >= 20
with playSpeed 1.25, about 0.8 s; the port plays all 32 frames at its slower
cadence, about 1.6 s. This predates M1g. Revisit both the end frame and playback
rate during roll timing/polish work; do not fix only the shared cadence.

#### Acceptance criteria

- [ ] Decide per clip: source rate (plus the source's per-action playSpeed) or
  the documented tuning; keep foot sliding acceptable.

### BUG-005: M1c wall/ledge port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** wall-sensitive actions (climb, crawl,
push). **State:** Open. Disclosed by Claude, M1c; code inspection.

- `unk_880` wall run-speed cap (Player_ProcessSceneCollision) not ported.
- Fixed M1f: a step with no horizontal move now runs the wall sphere at
  rest (kokiri_collision_actor_probe_still), as the source does.
- Air steering: M1d keeps an action's speedXZ (hop 2.5, 250 jump 1.0, let go
  0.8) with the stick centred, decaying 0.1 a frame; with input, the input
  speed replaces it at once instead of func_8083DFE0's 0.05 a frame rise.
- Hang: the feetFloorFlag auto-drop (Player_Action_8084BBE4) is not ported;
  the source's stick-forward wall climb from a jump at yDist >= 150 and the
  vine/ladder start from a walk-off (floor property 6, WALL_FLAG_3) are M1e.
- Headroom revert: the source's one-frame y = floor at the new x/z, and the
  crushed flag for a ceiling on another bgId, are not reproduced.
- Floor snap uses the floor-class query (as gravity does); RaycastDown's
  up-facing steep walls and isSoft -1 are not floors there.
- Crawl wall radius/height (10/15/30) belongs to the crawlspace milestone.

#### Acceptance criteria

- [ ] Port each item when its consumer lands, with a regression test.

### BUG-006: Talk takes an A press before the ledge climb

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M3 NPC placement. **State:** Open.

Source list8 checks Player_ActionHandler_12 before TALK; gameplay_step()
consumes A for talk/pickup/menu first, and only an unclaimed A reaches the
ledge climb. Only differs with an NPC in talk range facing a 27+ ledge.

- [ ] Reorder when the action-handler list is ported, or confirm no such spot.

### BUG-007: Floor jump/land SFX and the second climb-end voice are missing

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** SFX bank rework / M8. **State:** Open.

No NA_SE_PL_JUMP / NA_SE_PL_LAND (+ floor offset) sample exists; every jump,
landing and step-up plays voices only. M1d hang: NA_SE_VO_LI_HANG_KID,
NA_SE_PL_SLIPDOWN and NA_SE_PL_CLIMB_CLIFF are also missing (the footstep
stands in for NA_SE_PL_WALK_GROUND and the landing; CLIMB_END plays). NA_SE_VO_LI_CLIMB_END_KID picks rand 2
of EFFECT_35/36; only EFFECT_35 fits (core bank now 852 sound-RAM bytes spare).

- [ ] Add floor jump/land sounds and EFFECT_36 when sound RAM allows.

### BUG-008: Source-snippet host tests no longer compile

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next edit of these tests. **State:** Open.

test_title_flights slices demo.c from title_showcase_camera to recover_link;
M1b put link_standing/link_leave_ground in that slice, so it no longer
compiles. test_opening_audio (cutscene.c), test_forest_partition and
test_equipment_draw (kokiri_sgl.c/main.c) fail the same way on code M1c did
not touch. Seen in the M1c full run (628 tests: these 4 errors + BUG-003's 2).

- [ ] Extract by stable markers or compile the real units; all four pass.

### BUG-009: Link drawn at 1.45x the source child against source headroom

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** human visual check / M8. **State:** Open.

The Link recipe draws at 0.0145 (source actor scale 0.01): 63 units tall,
the source child is about 44. M1c movement uses the source headroom
(ceilingCheckHeight 40), so under a 40-62 ceiling his drawn head can clip.
S1.COL has no ceilings in that band over its floors (scan, M1c). The
step-up rise constants use the drawn scale, so the climb reads correctly.
M1d root transfers (pull-up x/z, let-go pelvis) also use the drawn scale:
letting go of a hang puts the actor ~60 below the top where the source's
child goes ~35.

- [ ] Human judges the scale; if changed, rebuild RISE and Navi LINK_HEAD.

### BUG-010: 250 jump has no mid-air ledge grab yet

**Labels:** `bug`, `priority: P1`

**Assignee:** M1d. **Milestone:** M1d hang. **State:** Closed (2026-09-26).

Human decision 2026-09-26: M1c starts the source 250 jump on ledges 47+;
Player_Action_8084411C's grab (ledgeClimbType >= 2, yDist < 150, total > 45)
and the hang/pull-up are M1d. Until then Link hops at the wall and lands back
below. No snap-to-top shortcut. Full ledge-climb acceptance waits for M1d.

- [x] M1d: grab, hang, pull-up and drop from the 250 jump and from walk-off
  (host tests, test_player_bg). Code accepted in M1d review (2026-09-26).
  Human Kronos check confirms tall-ledge jump/grab, hang, A drop and pull-up;
  porch slow walk hangs. Runtime acceptance recorded 2026-09-26.
- [x] M1e: pull-up and let-go now measure from sSkeletonBaseTransl
  (-57, 3377, 0) x 0.64, not 0 (about 1 unit).

### BUG-011: Released digital pad can interrupt climb early

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next climb/input integration.
**State:** Open.

#### Description and evidence

M1c review, code inspection: `player_input_motion` writes digital walk/run speed
before returning whether a direction is held. `demo_update` passes that speed to
`link_anim_roll_input` even with no direction. `climb_step` uses only
`roll_input_speed_q8 > 0` to interrupt the last four frames. Consequently a released
digital pad still looks like movement to the climb interrupt; centered analog does
not. No Kronos repro performed. No blocked gameplay demonstrated.

#### Steps / expected versus actual

Fixed in M1d (code accepted 2026-09-26; Kronos check pending): demo.c hands link_anim_roll_input 0 unless
player_input_motion reports a held direction.

Start a 100/150 step-up on a digital controller, then release directions. Expected:
finish the un-interrupted clip. Current wiring supplies nonzero speed and can end
in the last-four-frame interrupt window, resetting the draw offset early.

#### Acceptance criteria

- [ ] Climb interrupt uses actual requested movement, independent of roll-facing policy.
- [ ] Released digital and centered analog finish normally; held movement still interrupts.
- [ ] Regression covers demo input-to-animation wiring, not only direct state calls.

### BUG-012: 250-jump retained air speed is cleared before launch

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next air/grab integration.
**State:** Closed (2026-09-26; code review and human Kronos check).

#### Description and evidence

M1d code review: demo.c assigns `link_air_speed_q8 = 256` when starting JUMP250,
then the final `if (grounded || intent_speed)` clears it on grounded preparation
steps. The frame-8 launch sets vertical velocity but does not restore air speed.
Thus the claimed retained 1.0 speed is unavailable with centered input, including
as the speed required by player_hang_grab. This differs from the disclosed gradual
air-speed approximation. Holding direction still provides a path; no severe route
block demonstrated. No Kronos reproduction performed.

#### Steps / expected versus actual

Start a 250 jump, release direction during preparation and leave it centered through
descent. Expected retained launch speed permits the applicable grab. Code path
clears it before launch, so speed-dependent grab can be refused.

M1e review: fix attempted, but incomplete. The frame-8 launch sets
link_air_speed_q8 256 along the facing, then the same update's final cleanup
clears it again: grounded was computed before launch and remains true.
Keep P2/open. Cover the actual launch/cleanup integration order when fixing.
See [M1E_REVIEW.md](M1E_REVIEW.md); no Kronos reproduction claimed.

Second-fix review: the `launched` guard now prevents grounded cleanup on the
launch update. Accepted by code inspection. Keep open for runtime verification;
no host test executes this demo_update path. Existing clean map gap: 34,944 B.

#### Acceptance criteria

- [x] Initialize/preserve action air speed at actual launch without retaining stale ground speed.
- [x] Manual launch/grab check: human reports tall-ledge jump works, hangs, drops with A in response to the requested check.
- [x] Human reports normal movement good; existing hop/let-go paths unchanged by the launch guard.

Resolution: second launch-guard fix accepted. Human Kronos check on 2026-09-26
supersedes the pending-runtime notes above. No automated demo_update integration
test exists; manual acceptance does not claim one. Human subsequently confirmed
pull-up works too.

### BUG-013: Floor/ceiling/wall point-in-poly slack

**Labels:** `bug`, `priority: P1`

**Assignee:** Claude, M1e. **Milestone:** fixed in M1e; close after review
and a Kronos walk check. **State:** Closed (2026-09-26).

M1a ported the "Approx" tests (CollisionPoly_CheckYIntersectApprox1/2,
Check{X,Z}IntersectApprox -> Math3D_TriChkPointPara{Y,X,Z}Impl) as a flat
1-unit edge tolerance. Source: box +1, near a vertex, edge determinants
within 300 (about 300/edge-length units), or within 1 of an edge for a poly
facing the axis. Lines (detMax 0) were right. Found in M1e: a 400-wide
25-high step blocked instead of being walked onto; narrow polys were too
strict. Fixed in kokiri_collision.c `inside_approx` for bg_floor, bg_ceiling
and the wall sphere. The legacy kokiri_collision_floor (gravity, standing)
keeps its strict inside test.

- [x] Source test ported; M1c step boundary retested (25 climbed, 26 blocks).
- [x] Kronos: human reports normal movement all good (2026-09-26).

Resolution: source tolerance fix accepted by code review, host regressions and
human runtime check.

### BUG-014: Climb port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** vine-heavy scenes (M5). **State:** Open.

- Player_Action_8084BF1C's own Actor_UpdateBgCheckInfo (wall push radius 6,
  ceiling) is not run; func_8083F360's 12-unit hold does the positioning.
- Dyna wall carry while climbing (wallPolyActor prevPos) not ported.
- SkelAnime_UpdateTranslation turns prevTransl by prevRot; the port turns the
  whole step's delta by the current facing (differs only while turning).
- Climb sounds: NA_SE_PL_WALK_GROUND + wood/vine offsets use the footstep
  sample; the ladder-end landing uses it too.
- Swimming/iron-boots start conditions and PLAYER_STATE2_12 idle flag unused.

### BUG-015: Climbing down Link's house ladder from the porch

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** human check against real OoT.
**State:** Open.

S1.COL's lip at the ladder top (polys 784/785, wall type 3 = WALL_FLAG_2) is
20 high. func_8083EC18's climb-down start needs BGCHECKFLAG_WALL; the wall
sphere's centre (+26) is outside the lip's box (+1), so under the ported
rules walking at it starts nothing and Link walks off (hang/fall rules
apply). Climbing UP onto the porch works (host test on S1.COL). If real OoT
climbs down here, something in the start path is still missing.

- [ ] Human: on real OoT, walk from the porch to the ladder top; record result.

Human Kronos observation (2026-09-26): ladder ascent works; slow walking from
the porch hangs, running jumps off. No ladder descent. Original OoT comparison
still pending; keep P2 open, nonblocking for M1f.

### BUG-016: Grounded ceiling check ignored the glue dip

**Labels:** `bug`, `priority: P1`

**Assignee:** Claude, M1f. **State:** Open (tunnel fix accepted; remaining checks below).

Actor_UpdateBgCheckInfo checks ceilings over ceilingCheckHeight + dy - 10.
A grounded actor has dy = -7.5 each update (velocity -4 glue + gravity,
x1.5). The M1c port used dy 0, so headroom was 40 not 32.5, and crawling
30 not 22.5: the sword maze's 24-high crawlspace refused all motion. Fixed:
the ground dip is 7 (integer-exact for 7.5), kept as a distance. The +50
floor ray's start is not lowered by the dip (step-up up to 7.5 higher than
source; logged here).

- [x] Crawlspace passes; headroom retested (32 blocks, 33 passes).
- [x] Crawlspace: human reports current build good; M1f code review accepted.
- [ ] Kronos: check other low roofs explicitly; location/result not yet recorded.

Remaining floor-ray height approximation is deferred, nonblocking for M1g.

### BUG-017: Crawl port subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M1l camera / M8. **State:** Open.

- OnePointCutscene 9601/9602 (crawl exit camera) not ported (M1l).
- Camera_Subj4 first person ported (M1f); its 10-frame zoom-in and the
  eyeLerp yaw sway are not.
- Crawl sound lists (D_808548B4, D_808548D8) not played.
- Fixed in M1l: require crawl camera setting 0x1E, valid vector range and
  nonzero XZ line before enabling first person. Invalid data keeps the normal
  camera and Link visible. Host checks include real sword-maze bgCam 9.
- In the tunnel the source draws the held tunnel_start frame with its raw
  x/z root (movementFlags cleared); the port keeps x/z pinned.
- Fixed: the enter prompt now shows "A: Enter" on the prompt row (ahead of
  Talk, as handler 5 precedes TALK).

### BUG-018: M1g turn/bonk source subset gaps

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M8 polish; M7 when bonk actors appear.
**State:** Open.

The light analog band now supplies direction without movement. Above that band,
speed retains the existing linear curve, not Player_CalcSpeedAndYawFromControlStick's
curved mapping. Revisit with analog locomotion polish; no current route blocked.

Roll bonk plays the climb-end voice. BODY_HIT's sample, screen shake and rumble
remain absent. Add the source sound when revisiting the core SFX budget. Roll's
pre-existing duration mismatch is BUG-004, not corrected by M1g.

Tree actor overlap and large-crate break/drop signaling remain for integration
when those actors exist. Claude's source audit found no relevant bonk-drop actors
in current Kokiri/Lost Woods actor lists; Hyrule Field trees belong to M7. Apply
the drop rule when adding them; wall bonk alone does not implement their rewards.

- [ ] Source speed curve chosen/ported with analog feel check.
- [ ] Body-hit SFX and feedback implemented or explicitly scoped out.
- [ ] Relevant actor bonk signaling and source drops implemented with actors.

### BUG-019: Bonk/hang voice sounds wrong to human

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** next Link SFX pass. **State:** Open.

Human M1g Kronos pass: movement/bonk works, but Link sounds like a girl on
bonk/hang. Bonk currently uses ACTION_CLIMB0. Exact hang event/sample is not
identified. Compare source child sample selection, tuning and runtime playback
pitch before replacing the voice; no incorrect sample or pitch has been proven.

- [ ] Reproduce both cues and identify samples/pitch.
- [ ] Compare source playback and obtain human acceptance.

### BUG-020: Push-block live integration and source subset

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** before Deku Tree room 5 acceptance.
**State:** Open.

Human deferred the proposed live push-block test setup. No diagnostic block is
inserted in Kokiri Forest. Actor core and Link interaction have host coverage,
but scene asset loading/spawning/drawing and a live dynamic actor are still
required; M1h is not runtime accepted merely because its helper tests pass.

Supported core: real collision mesh, small/medium/strength-gated size variants,
20-unit push/pull, cooldown, wall checks, five-point floor support, falling and
rider carry. Source switch-dependent immobility, stacked-block movement, full
floor-switch signaling, rotated support corners and block/push SFX remain
integration work. Current core does not claim full Obj_Oshihiki parity.

- [ ] Source room 5 spawn/params/mesh/draw and switch semantics integrated.
- [ ] Push, pull, obstruction, ledge/fall and rider behavior pass in game.
- [ ] No invented block drops: source Obj_Oshihiki has no Item_Drop path.

### BUG-021: Grass patch behaves like a raised floor

**Labels:** `bug`, `priority: P1`

**Assignee:** Astra. **Milestone:** Clean runtime check.
**State:** Closed. Human reports "Test good" on 2026-09-26.

Human marked this important (P1). Human reports Link steps onto grass patches
and rupees/items appear on top.
Expected: walk through the grass at ground level; grass can visually hide ground
pickups. Human also recalls a small grass/rustle effect and sound when walking
through it; confirm those details against source before implementing them.

Confirmed source scene grass polygons have entity-ignore flags. The modern
bg queries respected those flags, but legacy player floor/head-sphere queries
and build_actors' floor placement did not. Both now filter by source flags;
camera spheres use the camera-ignore flag. No scene geometry was removed.
Real examples: (60,-430) and (-480,190) have grass at y=28, ground y=1;
(-570,1720) has grass at about y=144, ground y=120.
Sword/shield placements now resolve to y=1. Their draw height also no longer
adds the artificial 46-unit grass-clearance offset (16px icon at scale two now
centres 16 units above ground, with a small bob).

Host tests cover the three real patches, player movement through grass, and
source-data pickup floor extraction. The old ledge test at (172,28,-483)
stood on ignored grass: from real ground y=1 it is a 59-unit 250-jump ledge.
Human: walk across the two item patches, collect items/rupees, and check grass
can obscure them. Rustle sprite/sound moved to separate minor BUG-024;
source behavior still needs verification. No grass drop behavior changed.

- [x] Identify affected patch and its source actor/collision data.
- [x] Host checks: Link walks through at ground height; pickups use correct floor.
- [x] Human confirms movement and pickup visibility in Clean.
- Rustle sprite/sound verification remains BUG-024.

### BUG-022: Carry props and full reward integration pending

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M3 props / M1i acceptance. **State:** Open.

M1i player action hooks cover attach frame 4, stationary put frame 4, throw frame
3 (speed +8, vertical 12), throw-only props and safe cancellation. Only the
strengthless bush failure is wired to current forest props. Successful carry
needs actor ownership/hand transforms, carrying locomotion, thrown collision,
break effects and source rewards; it is not yet live gameplay. Large/heavy rocks
need their separate strength/actions. Failure voice/prompt remain polish.

Source audit: EnKusa_DropCollectible uses spawn-selected random tables for types
0/2, seeds/hearts for type 1; thrown impact uses that drop path. Existing
build_actors.py grass_rupee_slots is explicitly rupee-only and is insufficient
for adding successful bush throws. Obj_Tsubo/En_Ishi must likewise retain their
own params, restrictions and reward paths. No new prop/drop actor was added here;
failed lifting neither cuts a bush nor awards a drop.

- [ ] Successful pot/rock/bush carry and throw integrated with actual actor owner.
- [ ] Source drops, conditions and collectibles supported in the same prop task.
- [ ] In-game carry, put, throw, wall impact and scene transition checks pass.

### BUG-023: Slope/fall runtime and damage integration pending

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** M1j runtime / M2 health. **State:** Open.

Slope movement/poses are wired; needs forest slope check. Slip sound, dust,
animation morph and exact pushed-speed interactions remain approximations.
Sliding uses source grounded floor tolerance plus the omitted downward glue
distance (18 integer units), preventing steep slopes from becoming free falls;
ordinary locomotion's previous ground-follow tuning remains unchanged.

D_80854600 fall damage policy is implemented/tested: distances 400..799 deal 8
health units, >=800 deal 16, floor types 6/9 exempt. It is not applied to live
health yet. M2 owns damage reactions, invulnerability, death and continue, which
must be integrated together; do not mark all fall consequences or M1 complete.

- [ ] Forest sliding, uphill resistance, flat exit and jump/ledge behavior verified.
- [ ] Landing calls policy once and M2 owns health/reaction/death consequences.

### BUG-024: Grass overlap rustle effects and sound

**Labels:** `bug`, `priority: P2`, `needs-triage`

**Assignee:** Unassigned. **Milestone:** M3 grass / M8 feedback. **State:** Open.

Human recalls a small grass sprite/rustle sound while passing through scene
grass. BUG-021 collision and item-height fix passed the human check; this is
the separate feedback follow-up. Confirm source effect triggers and material
audio selection, including the entity-ignore grass surface above the solid floor.
Do not restore solid collision or force pickups above foliage for visibility.

- [ ] Verify source overlap effect and sound, then implement missing feedback.
- [ ] Keep grass pass-through and ground pickup placement from BUG-021.

### BUG-025: Water traversal source subset and runtime acceptance

**Labels:** `bug`, `priority: P2`

**Assignee:** Astra. **Milestone:** M1k human check; M2/M5 integration.
**State:** Open.

Child swim entry/exit, buoyancy, A dive/hold/release, depth cap, return to surface,
wall/floor/roof collision and sloped-bank exits are wired. X supplies a stroke;
land sword, shield, roll and Y jump are suppressed while water owns the step.
Current source subset: no entry splash/ripples, water SFX, underwater filter,
full body pitch/animation morph, HUD dive prompt, targeted/back/side swimming, water-specific
ledge exits or running-jump water animation. Dive-turn uses an 8-step recovery
instead of the source pitch condition. Movement rates use fixed-point source
values but the input speed curve remains the existing port's approximation.
General follow camera is retained until the traversal camera pass.

Human subsequently reports "Water is good. Continue next" (2026-09-26).
Record water runtime acceptance; individual unreported cases and dungeon water
remain to be checked. This supersedes the earlier unavailable-pond note.

The 450-step submerged hook corresponds to source's 300 updates before the
environmental hazard is eligible; it is NOT a drowning deadline. M2 must wire
health-dependent environmental timers, death and respawn together. An obstructed
rise currently remains swimming under the roof; death/respawn is still pending.
No scale upgrade in live inventory yet (base 120 depth); host input tests can
exercise the 240/360 limits. Do not mark all M1 water consequences complete.

Real source ydan water boxes belong to rooms 3, 5, 9, not room 0. Host test uses
all 2321 source collision polygons and checks those room filters. The current
disc collision exporter cap is 2048, so M5 must budget/raise that cap or partition
the collision before staging ydan. Host coverage does not prove dungeon runtime.

- [x] Human reports water works in Kronos (2026-09-26).
- [ ] Explicit pause/resume and dungeon-water acceptance when available.
- [ ] Verify missing animation/FX/audio and ledge-exit behaviors against source.
- [ ] Integrate drowning, death and respawn with M2; exercise ydan in M5.

### BUG-026: Dialogue special characters and missing dither backdrop

**Labels:** `bug`, `priority: P2`

**Assignee:** Unassigned. **Milestone:** next dialogue/UI pass. **State:** Open.

Human screenshot: Mido's "Mr. No Fairy" line shows stray yen-like symbols
around the quoted nickname. Character dialogue draws over the scene without
the readable dither backdrop used by cutscenes. Human explicitly requests
logging this separately while milestone work continues.

Trace source message decoding, text encoding and glyph mapping before changing
the string: do not guess whether the visible symbols are control bytes, escapes
or unsupported glyphs. Dialogue should render intended special characters and
use a cutscene-style dither backdrop. Keep UI on VDP2; no VDP1 texture allocation.

- [ ] Mido line renders intended punctuation without stray symbols.
- [ ] Other supported special characters and message controls remain correct.
- [ ] VDP2 dither backdrop covers each dialogue page and clears on close.

### BUG-027: Traversal camera source subset and runtime acceptance

**Labels:** `bug`, `priority: P2`

**Assignee:** Astra. **Milestone:** M1l human check / M8. **State:** Open.

New traversal adapter uses Normal0 Unique1 hang offset/pitch and Jump2 climb
offsets/near-end pitch, scaled to the existing 62-unit model camera. Hang holds
entry yaw; climb follows the wall-facing heading even when stationary. At-point
eases through entry/exit and camera-ignore-aware line collision shortens the eye
ray. Normal mode still uses the existing follow behavior.

This is a fixed-point adaptation, not a complete port of Camera_Jump2/Unique1:
source waist-based hang-entry yaw, climb yaw freedom after entry, cached floor
state, distance-envelope logic, per-field rate interpolation, FOV variants and
Jump2's alternative collision ray remain follow-ups. Only traversal/return
gets the new collision ray; general Normal1 camera collision is still pending.
Crawl special exit shots and entry zoom/sway remain BUG-017. Swim Jump3 remains
BUG-025. No claim of full M1 camera parity or full M1 acceptance.

- [ ] Human checks ladder/vine ascent/descent, hang/pull-up/drop framing.
- [ ] Human checks nearby walls and smooth return to walking camera.
- [ ] Port remaining source camera details in the relevant polish pass.

## Bug report template

### BUG-NNN: Brief description of the failure

**Labels:** `bug`, `priority: P2` (or appropriate priority), `needs-triage` if unconfirmed

**Assignee:** Unassigned

**Milestone:** Relevant milestone or Backlog

**State:** Open

**Revisit trigger:** Specific dependency, affected feature integration or polish pass

#### Description

What fails and how it affects the player. State whether reproduced or suspected.

#### Steps to reproduce

1. Start from the relevant scene/save/controller state.
2. Perform the triggering action.
3. Observe the failure.

#### Expected behavior

Describe the intended result; link source behavior or an agreed requirement.

#### Actual behavior

Describe what was observed. For a potential issue, state that reproduction is
pending and give the code evidence; do not invent observed behavior.

#### Environment

- Build/commit:
- Emulator/version and 4 MB cart configuration, or host-test environment:
- Controller mode:
- Scene/room/save state:

#### Evidence and related work

Logs, screenshots, test output, relevant file/symbol and linked reviews/issues.
Include only available evidence; do not require screenshots for a code-only finding.

#### Acceptance criteria

- [ ] Reproduction no longer fails, or suspicion resolved with evidence.
- [ ] Relevant gameplay path remains working.
- [ ] Appropriate verification recorded; runtime versus host evidence distinguished.

#### Resolution

Fill when closed: fix summary or reason not planned/duplicate, verification,
commit/PR if available and date. Keep the issue record after closing.

## Feature request template

### FEAT-NNN: Brief description of the requested capability

**Labels:** `enhancement`

**Assignee:** Unassigned

**Milestone:** Backlog until assigned

**State:** Open

**Scope decision:** Proposed / approved with reference

**Revisit trigger:** Relevant milestone or explicit assignment

#### Problem or player benefit

What need this solves and why it matters to playable progress.

#### Proposed behavior

Concrete player-facing result. Separate required scope from optional additions.

#### Alternatives considered

Briefly list meaningful alternatives, including existing behavior if sufficient.
Omit if none are relevant; do not invent extra research work.

#### Dependencies and scope

Required systems/assets, affected files/owner, source reference where applicable,
and what remains outside the request. Link existing milestone plans rather than
duplicating their required features. A logged request is not authorization to start.

#### Acceptance criteria

- [ ] Agreed player-facing behavior works.
- [ ] Dependencies and applicable source/drop rules satisfied.
- [ ] Appropriate tests/runtime evidence recorded.

#### Resolution

Fill when closed: delivered behavior or reason not planned/duplicate, verification,
commit/PR if available and date.
