# Foreground warp failure — 2026-09-18

Owner: Astra / Codex. My changes made the user's experience worse. This record
is about my decisions, not blame on the user or another agent.

## What user wanted

Fix severe foreground texture warp during real movement. Keep checker mesh.
Keep controls, camera, collision, and existing gameplay. Later: stop the failed
experiments and use original polygon clipping.

## What I did wrong

1. **Changed renderer before proving the failing path.** I inspected source and
   static captures, but had not traced the exact bad surface through import,
   clipping, projection, and drawing during movement.
2. **Turned a separate finding into the main fix.** Import discarded combiner
   state, primitive tint, and second texture layers. That was worth recording.
   It did not establish the cause of the reported warp. I nevertheless changed
   material baking while investigating clipping and ordering.
3. **Bundled another unproven renderer change.** I added runtime 4x4 subdivision
   for up to three nearby ground surfaces, scratch texture repacking, selection,
   and extra submissions. This introduced several new failure paths at once.
4. **Changed the comparison baseline.** Scratch VRAM reservation reduced the
   offline texture budget. Grid-on images therefore could not be compared with
   older material-only images as a pure subdivision test.
5. **Tested movement too late.** Fixed station captures and host tests came
   first. The user had already said the failure happened in play. Real walking,
   turning, and jumping then exposed large missing-floor regions.
6. **Overweighted proxy evidence.** 209 host tests passed and the build fit
   memory limits. Neither proved correct clipping, stable textures, readable
   gameplay, or acceptable target cost. I reported those numbers repeatedly
   while the user's actual problem remained.
7. **Replaced normal build artifacts with experiments.** Diagnostic builds used
   the normal image path. That left an experimental image available for play
   before visual acceptance. A user-facing image must not be the test scratchpad.
8. **Resolved “original” too late.** I said I was restoring original clipping
   before identifying whether the user meant pre-SORT_MAX Jo/SGL or the older
   libyaul CPU clipper. I should have identified the exact implementation first.
9. **Spent too much time and explanation on experiments.** The user needed a
   focused repair. I added scope, tool churn, and repeated status claims instead.

## Evidence and limits

- User explicitly reported the result was worse.
- Movement captures showed large pale/missing-floor areas during turns. That
  invalidated visual acceptance; it did not, by itself, prove which stage caused
  every missing surface.
- Local, ignored evidence: `game/build/generated/astra-movement-*.png`,
  `astra-grid-*.png`, `astra-material-*.png`, and `astra-move-nogrid-*.png`.
- These captures are not a clean, matched-frame causal proof. Do not describe
  them as zero-noise A/B evidence or proof that subdivision fixed anything.
- The exact remaining warp cause was **not established**. Do not replace that
  uncertainty with another confident diagnosis.

## Rollback status

My material rewrite, runtime grid, scratch-budget changes, new tests/helpers,
and movement/capture changes were removed. Normal and clean images were rebuilt
without my diagnostic options. The prior 195-test suite passed.

Pre-existing uncommitted work remains, including SORT_MAX, the earlier offline
subdivision redistribution, and Claude's probes/audit. Rollback of my changes
was **not** restoration of the older CPU clipper and was **not** a warp fix.
Checker policy was not removed by this experiment. No fix was committed.

## Mandatory rules for the next attempt

1. **Name the baseline first.** Record commit, dirty changes, image, build flags,
   texture path, and active clipper. Preserve a runnable baseline image separately.
   Ask one short question if “original” still has multiple possible meanings.
2. **Reproduce in movement first.** Use real collision, follow camera, animation,
   walking, turning, and jumping. Do not substitute pinned poses for this gate.
3. **Trace one visible failure.** Record camera/pose, source face IDs, transformed
   vertices, clip result, UV result, and emitted primitive. Locate the first wrong
   result. A plausible importer deficiency is not proof of the warp cause.
4. **Read the original clipper before replacing it.** Check its geometry and UV
   handling, scratch limits, and overflow behavior. Do not assume an archived
   renderer is drop-in compatible or automatically correct.
5. **One correction at a time.** Keep material, density, subdivision, sorting,
   and clipping changes separate. Do not shrink texture allocations while
   claiming a geometry-only comparison. Park unrelated discoveries in notes.
6. **Keep experiments out of player images.** Use separate output locations or
   an isolated worktree. Track executable and generated-asset provenance.
   Rebuild every object affected by changed probe defines.
7. **Judge the actual symptom.** Check movement before promotion: floor remains
   visible, textures do not sweep across Link, walls still occlude correctly,
   checker remains, and responsiveness does not regress. Inspect target hot
   paths; integer math and capacity checks alone do not prove speed.
8. **Regression means stop and revert that change.** Do not stack another theory
   on top. Preserve evidence, restore the baseline, then report the unresolved
   fact. Never make the user discover an unaccepted experiment in normal play.
9. **Report only what happened.** Tests passed is not warp fixed. Build fits is
   not playable. Code rollback is not old clipper restored. Keep updates short.

The earlier handoff's adaptive-subdivision prescription is not an approved fix.
Do not resume this failed grid/material experiment merely because code or
captures remain in generated output.
