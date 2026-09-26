# M9 draft: release validation and demo package

Astra side draft, 2026-09-25. Expands DEMO_PLAN M9 after reviewed M8.

## Release result and scope

A reproducible clean ISO/CUE plus README package has a verified fresh-file route
from title through Kokiri, Deku Tree/Gohma, Emerald, Saria bridge and Field owl;
save/load/death/continue work, and a second supported emulator completes its smoke
check. Publish only claims backed by the actual candidate tested.

This is a bounded release audit, not a new-feature milestone. Renderer investigations
are limited to the named issues and fixes required for playability. Candidate
packaging is local preparation; publishing/uploading is a separate human-directed
action. Never include user backup RAM or private ROM inputs in the release bundle.

## Entry criteria and candidate identity

Require prior milestone reviews, resolved Meadow scope, closed required deferred
cases, VDP2-only menu audit, current source/drop ledgers and tester documentation.
Every remaining issue has severity, reproducible steps, affected route/platform,
workaround if real, and owner. A missing required gameplay system is not a cosmetic
known issue. Real hardware remains outside the emulator-only release gate.

Record source commit plus any explicit diff, tool/dependency revisions, build
options, save version, asset inputs by identifier/hash, image/CUE hashes and build
log. Do not overwrite unrelated working changes to obtain a clean checkout; use an
isolated candidate checkout if needed. Final release identity must identify the
exact source and artifacts, not an ambiguous stale image in the build directory.

## Evidence sources

- DEMO_PLAN plus individual M2-M8 plans and milestone handoffs: promised behavior,
  named deferred checks and approved scope decisions.
- Source/asset manifests: room/layer/actor completeness, drop/grant behavior and
  required flags; compare against current candidate, not historical test counts.
- `build_sgl_area.py --verify --map`, VDP1 reports, allocator/cart instrumentation,
  SCSP bank reports and SH-2 disassembly: resource/target gates.
- `SAVE_CRASH_2026-09-25.md`: buffer/layout and dependency regression record.
- `FOREGROUND_WARP_FAILURE_2026-09-18.md`: renderer investigation restrictions.
- Current emulator configuration and actual runs: platform claims. Consult exact
  version documentation during implementation if needed; do not guess compatibility.

## Delivery checkpoints

### M9a: candidate build and static gates

Build **clean only** under the current human instruction. Normal/hires are not
release artifacts or silently claimed tested. Verify dependency rebuild correctness
and generated assets; record command, exit/result and final image timestamps/hashes.
A script printing "built" is not by itself proof all earlier build steps succeeded.

Check worst-room VDP1 texture/command costs, SGL boundary, cart allocation intervals,
measured heap peak, collision/actor capacity and audio banks. No guessed arena cuts.
Audit changed runtime math for software float and large-coordinate overflows.
Verify every generated asset reference/8.3 name and scene/room boundary.

Confirm menus allocate no VDP1 texture space and issue no menu VDP1 commands;
inspect VDP2 bank/palette bounds and gameplay restoration. Run focused host suites
separately where the known combined Python crash remains; list harness/environment
failures explicitly. No claim that a skipped or uncompilable test passed.

Review: reproducible candidate identity, complete gate report and unresolved issue
classification before spending time on full runtime acceptance.

### M9b: primary-emulator full route

Use the documented Kronos version with 4 MB cart; preserve existing user saves and
use isolated test slots/backups. Record actual emulator build/config/controller.
Run title -> new file -> opening -> sword maze/chest -> shop shield -> Mido -> Tree
mouth -> dungeon items/puzzles -> Gohma -> rewards -> Emerald/death -> forest ->
Saria bridge -> Field intro/owl -> explore/return. No debug grant or warp shortcuts.

Capture checkpoints/state evidence rather than a claim based on boot alone. Exercise
source rewards, inventories, flags and scene bank restoration along the route.
Include required side-content routes and every named M1-M7 deferred acceptance
case; use a coverage table linking each to evidence. Gold token exclusions follow
the source capability/night ledger, not a blanket promise of all collectibles.

Use both controller layouts across meaningful gameplay and menu segments. Check
analog creep/turn stability, Z lock, C routing, item aim, shop/menu VDP2 rendering,
ocarina and shot skip. Host tests cannot establish camera/render/audio feel.

Review: route completed, checkpoints recorded, no progression dead ends or missing
required content. Frame-rate observations are factual; no invented performance
threshold overrides earlier project policy.

### M9c: save, continue and repeatability matrix

Test fresh/loaded files; save/load in forest, interiors and dungeon; death and
continue in forest/dungeon/boss; accept/decline Game Over save; title/reload; already
cleared boss/rewards; repeated bridge/intro visits. Verify correct slot, capacity,
health, inventory, entrance and persistent flags. Avoid destroying user save data.

Exercise storage failure/corrupt/old-version cases with isolated fixtures. No
misleading success message, stack overwrite, duplicate reward or unintended opening
replay. Verify save header/size/checksum ordering and newly added field round trips.

Test normal cutscene playback and rapid current-shot skips through story grants.
Repeat room/bank churn and pause/restore to catch stale pointers, retained targets,
texture/palette corruption and orphan audio. Include slow rendering and controller
loss where practical; distinguish host-injected cases from observed emulator ones.

Review: matrix with pass/fail/pending, source-state differences and exact candidate
identity. A code or asset fix invalidates affected results and needs a new hash.

### M9d: bounded renderer checks and second emulator

For near-camera warp, floor-over-Link sorting and intermittent opening crash:
record a reproducible route/view, candidate, observed behavior and impact. Trace
the specific source-to-draw path before edits. Identify the requested original
clipping implementation before touching it; no speculative material/subdivision
rewrite. Keep experimental images separate from the tested clean candidate.

Fix blockers for required playability; record tolerable visual issues honestly.
A crash, lost floor/collision or route-blocking missing geometry is not waived by
calling it cosmetic. Retest affected movement and route after any bounded fix.

On SSF or Mednafen with the required cart, record exact version/setup and perform
boot plus at least five minutes of play, menu/save smoke checks where supported,
and representative 3D/room transition behavior. Do not infer full-game parity from
that smoke test. If unavailable or failing, keep the release gate pending and state
why; do not silently rename one-emulator testing as multi-emulator validation.

Review: known-issue decisions and actual supported-platform matrix. Project-local
Kronos command-cap patches must be disclosed with exact build/setup requirements.

### M9e: local package and final review

Prepare a staging directory with clean ISO/CUE, README, version/build identity,
checksums, tested emulator/configuration notes and known issues. Validate CUE paths
and case, extract the archive into a fresh directory and boot that packaged copy.
Exclude ROM inputs, saves, internal debug images, logs containing private paths and
unneeded build intermediates. Ensure required redistributable files are identified;
resolve any packaging permission questions before distribution rather than bundling
private source assets by accident.

Record final archive/image hashes and a concise release checklist. Present the
concrete package for human review; no external upload/release publication is implied
by this drafting request or local packaging work. Any later rebuilt artifact needs
its own identity and appropriate revalidation; do not swap it under old test evidence.

## Release decision and handoff

- Required route and side-content/deferred checks complete on the primary emulator.
- Save/Game Over/continue and story-skip matrix passed for the same candidate.
- Resource/build/VDP2-menu gates passed; current failures/omissions explicitly listed.
- Second-emulator smoke test observed; hardware testing remains N/A by agreed scope.
- Local extracted package boots, README matches it and hashes identify it exactly.
- Human receives package location, source/build identity, verification summary and
  remaining known issues. Publication waits for explicit instruction.

## Review and verification rules

Planning only; no implementation owner assigned here. Start code after preceding
milestone review and human owner assignment. Recheck current source and working
diff before taking files; M1/other active work stays with its owner. Dependencies
below describe required behavior, not permission for a parallel rewrite.

At each implementation checkpoint: focused host tests in separate processes,
**clean image only** per current human instruction, SGL map boundary, worst-room
VDP1 budget, cart bounds/heap high-water and audio bank bytes. Inspect changed
runtime hot paths for software float. Do not cut the malloc arena by guesswork.
Runtime checks use the project's non-focus-stealing workflow or human play;
report observed versus pending checks separately. No build/runtime checks were
performed for this draft. Source references are implementation research targets
unless explicitly marked verified; umbrella-plan actor lists are not spawn proof.

Record changed files, source parity, approximations, save compatibility, measured
budgets and deferred acceptance in OPUS_HANDOFF and VSLICEPROGRESS when code lands.
Code stays uncommitted for review unless human requests commit. Planning does not
complete a milestone or authorize the next one. All new actors include source
spawn/drop audits in the same task; characters use flat materials except faces.

All menus must use VDP2 for text, panels, icons, maps and cursors. Budget VDP2
storage/layers and restoration explicitly; no VDP1 menu textures or commands.
