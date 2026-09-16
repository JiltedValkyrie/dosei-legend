# Opus: texture-path implementation handed back

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
