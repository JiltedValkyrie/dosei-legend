# Jo Engine / SGL port plan

## Branch and objective

User requested a fresh port branch from the regular integration branch, main.
`joengine-port` starts at `f545532` with only these planning docs added. The later
performance experiments, Mesh Workshop, quad changes and launcher GUI are NOT
merged into this branch. The existing main-branch libyaul implementation remains
as reference; this is not an empty repository.

All current experimental work is checkpointed on `performance` at `dad76ea`.
Nothing was pushed. Do not merge that branch wholesale to begin this port.

Goal: use Jo Engine's SGL rendering path for Kokiri Forest and establish actual
ISO performance before migrating the rest of the game. Start with a small,
isolated viewer; do not reproduce the custom libyaul renderer under a new SDK.

## Available inputs

- Local Jo Engine: `D:/Workspace-Claude/saturn-homebrew/joengine` (`../joengine`
  from repository root). Do not modify the shared SDK or its samples in place.
- Examples: `Samples/demo - 3D`, `Samples/demo - 3D - programmatically`,
  `Samples/demo - advanced 3D`, `Samples/demo - 3D map`.
- Build reference: `Samples/demo - 3D/makefile`, `compile.bat`, `compile.sh`.
  Adapt their SDK/compiler paths to the new project; do not assume the current
  libyaul makefile/toolchain options are compatible with Jo's build system.
- Original scene: `title-screen/cd/FOREST.BIN`, KFR1 version 2, 488184 bytes,
  1268 shared vertices, 2060 triangle records. Includes texture/CLUT data and
  collision. Preserve all texture/material layers, even on coincident geometry.
- Main's source audio/scene/conversion code is available under `title-screen/`.
  Use approved US 1.2 audio as the eventual reference, not retired Ponesound work.
- Later diagnosis/results: `git show dad76ea:title-screen/docs/perf/BASELINE.md`.
- Quad workflow and candidate caveats:
  `git show dad76ea:title-screen/docs/perf/QUAD_HANDOFF.md`.
- Local-only mesh candidate remains under
  `title-screen/mesh-workspace/3fd66b9e8dab/imports/20260915-193945-ba1824b8/`.
  It is NOT the first viewer's input. Imported quad UVs/layers need separate work.

Ignored build artifacts and mesh files physically survive branch switches. They
are not new-branch builds. Never use their timestamps/existence as evidence that
the new source was compiled. Local Git excludes keep them out of this checkpoint;
do not clean or delete the user's mesh workspace.

## Implementation order for Claude

1. Create a separate project directory, e.g. `jo-viewer/`, with private object,
   generated asset, CD staging and image directories. Leave `title-screen/`'s
   source, images and SDK installation intact. Build a minimal Jo/SGL scene first.
2. Convert the ORIGINAL scene into shared SGL POINT/POLYGON/ATTR data. In the
   local SDK `jo_3d_mesh_draw()` calls `slPutPolygon()`. Jo's convenience mesh
   constructor allocates four points per polygon; avoid expanding our 1268 shared
   vertices unnecessarily. Represent triangles using the appropriate repeated
   fourth corner. Verify texture palette, winding, one/two-sided and mesh flags.
3. Render a fixed, textured Kokiri view through SGL. Match source-space camera
   (-300,91,0), yaw/pitch zero, framing, resolution and draw policy deliberately;
   document axis/FOV differences instead of assuming matching camera APIs.
   Do not carry over CPU texture resampling automatically: first understand SGL's
   near/screen clipping and texture behaviour. Check floor and edge-crossing faces.
4. Produce an explicitly labelled Jo viewer ISO and measure in the same emulator
   configuration as the unchanged libyaul baseline. Verify visible coverage and
   textures before comparing performance. Record frame pacing/sync divisor,
   geometry counts and audio/profiler differences. A silent viewer versus the
   full baseline is exploratory evidence, not a clean renderer-only speedup.
5. If the viewer is correct and promising, bring camera controls and collision
   across, then title/background and approved audio. Jo/SGL owns initialization,
   frame synchronization and callbacks: do not blindly transplant libyaul IRQ or
   SCSP initialization. Preserve the original as a working reference at every step.
6. Only after that compare quads/other optimizations. Keep results expressed as
   actual rendered frame throughput as well as local CPU savings. A new SDK alone
   is not evidence of a speedup.

## Guardrails and existing evidence

- Trace before changing; no speculative control changes. Keep required work out
  of assert expressions. Test floor visibility, near clipping, movement, turning,
  height controls and music. Host tests/build success do not prove runtime fidelity.
- 4 MB expansion cartridge may be assumed present. It is not assumed faster RAM.
- Prior texture CPU savings did not improve frame throughput. Staging and early
  per-face sphere culling did not demonstrate a frame improvement at the tested pose.
- Baseline reports showed seven callbacks per rendered frame. Counts per callback
  do not independently establish milliseconds without verified field frequency.
- Cache-toggle test reportedly gave no improvement. Do not repeat it as a fix.
- Flat/wireframe ablations do not prove a universally CPU-only bottleneck.
- No Jo Engine build, performance measurement or port implementation has been
  performed for this branch setup. There is no promised FPS target yet.

## References

- [Jo Engine](https://jo-engine.org/)
- [Jo 3D API/source](https://jo-engine.org/doxygen/3d_8h_source.html)
- [User's Saturn manual index](https://segaxtreme.net/threads/saturn-documentation.16403/)
  (original resource list preserved at `dad76ea:.claude/hitlists/logic/RESOURCES.txt`).
- Follow the index's SGL tutorial/reference and VDP1 manual for rendering rules.
  Some old compressed links fail; use mirrors of the same Sega document numbers,
  and distinguish manual hardware guarantees from SDK implementation behaviour.

Immediate deliverable: an isolated, textured Jo/SGL viewer ISO, documented launch
command and honest visual/performance comparison. Avoid another tooling detour.
