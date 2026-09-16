# Quad mesh handoff: Astra to Claude / Opus

2026-09-15. User requests wiring the imported mesh into an experimental build.
This document records the exchange tool and next implementation work; runtime
quad support has NOT been implemented. Target actual ISO performance, not more
profiler expansion. Keep the normal game and current baseline intact.

## Implemented

- GUI: `tools/mesh-workshop/open-mesh-workshop.bat` (Python/Tkinter + Pillow).
- `mesh_assets.py` discovers KFR1 v2 visual scene containers in `cd/`, currently
  FOREST.BIN. A.BIN is executable code, not a mesh. Forest is one combined visual
  mesh, not separate room entries. Collision is excluded from OBJ exchange.
- Exports OBJ, MTL, preview atlas and source provenance into timestamped revisions
  under `mesh-workspace/<id>/exports/`. Source assets are never replaced.
- Imports mixed triangle/quad OBJ with UVs and flags_0..flags_3 materials. Stores
  normalized OBJ/MTL, copied textures and mesh.json in a new `imports/` revision.
- Explicit, default-off **Split incompatible quads on import** preserves valid
  quads and splits recoverable non-planar/concave faces using a valid interior
  diagonal. It preserves corner UVs/materials, not a guarantee of Blender's
  chosen diagonal. Crossed/unsplittable degenerate faces and n-gons still fail.
  The strict planarity threshold is 0.05 native units, not Blender's angle limit.
- GUI reports quads retained, quads split and final triangle count. Metadata
  records split OBJ line numbers. No vertex positions are moved by this step.
- **Prefer quads** defaults on and is saved in `mesh-workspace/preferences.json`.
  It is currently a preference ONLY: `build_selection()` returns the original
  asset, and imported metadata has `runtime_ready: false`. No Makefile selection
  or runtime consumption exists yet. Do not treat the checkbox as wired up.
- Workspace revisions/preferences are Git-ignored local assets. Preserve them;
  collaborators on another machine need the entire candidate bundle separately.

## Verified user candidate

All paths below are relative to `title-screen/`:

`mesh-workspace/3fd66b9e8dab/imports/20260915-193945-ba1824b8/`

Use this normalized **mesh.obj**, its **mesh.mtl**, referenced PNG and **mesh.json**,
not an earlier export or the unprocessed Blender OBJ. The preference file points
to this revision and `prefer_quads` is true.

- 1,268 vertices; 1,187 triangles; 333 retained quads; 237 quads split on import.
- 1,520 face records versus original 2,060: 26.2% fewer records, NOT a measured
  command-count reduction or speedup. Vertex count is unchanged.
- Candidate OBJ SHA256:
  `ff58ec40a47c5495da20a0cd3b8abcdd23ab26306143c260784d0006fcb40199`.
- Source FOREST.BIN SHA256 matches recorded provenance:
  `e28af8904ae585c31accfd95e9fada7154bdae09dc5b153da5712f75eff3f5c1`.
- The earlier 94-split report was from a prior read of the edited file; the saved
  candidate metadata and user screenshot both say 237. Use 237 for this revision.

Important geometry check: 1,187 + 2*333 = 1,853 triangle equivalents, not 2,060.
This does not prove missing geometry (planar regions can be simplified), but it
does mean topology counts alone cannot establish a pure pairwise merge. Verify
surface coverage, winding, holes, bounds and camera/floor views before calling
this equivalent geometry. Check axis/scale and deliberate float-to-int rounding.

## Wire-up sequence

1. Add an explicit quad-test build with its own objects, generated assets, CD
   staging tree and ISO/CUE. Do NOT overwrite `cd/FOREST.BIN`, shared CD staging,
   the normal image or the performance baseline. Keep ablations/early-cull off
   for the first quad comparison. Add one GUI launcher entry once the image exists.
2. Resolve the saved candidate when prefer-quads is requested; validate its source
   hash and resources. An explicit quad test must fail clearly on missing/stale/
   unsupported input rather than silently benchmark triangles. Normal builds
   continue using the original. Record the selected revision/hash in build output.
3. Implement an offline mixed triangle/quad asset converter and texture bake.
   Preserve original collision data, flags and native scale. Version/identify the
   new asset contract and validate capacities with real checks, not assertions
   whose required work disappears in release builds.
4. Implement true quad handling throughout culling, sorting, clipping and emission.
   `face_t` has four indices but the current renderer uses only three. Update
   all-vertex outcodes, far/fade tests, safe projection, bounds/needed-vertex marks,
   and input polygon length. Mixed face depth sorting needs comparable depth keys
   (raw three-vertex versus four-vertex sums are not comparable). Clip all four
   corners and preserve UVs; triangle barycentric resampling is not a quad mapper.
   Unclipped retained quads should issue one proper four-corner command, not
   immediately become two triangles. Retain overflow diagnostics and guards.
5. Verify fixture quads, both windings, clipped quads, mixed faces, degenerate
   cases and buffer bounds. Then build and run the textured quad ISO. Check floors,
   seams, textures, collision, movement/turning/height and audio in normal play.
   Compare fixed-pose frame/CPU counts against the unchanged baseline. Report
   actual visible/command/texture counts; do not demand equal face counts here.

## Texture caveat: do not skip

The exported atlas is a resampled preview of already-baked per-triangle tiles,
NOT original N64 material UVs and NOT a pixel-identical round trip. Adjacent
triangles often occupy disconnected atlas islands. Retaining four corner UVs on
a merged quad can sample unrelated regions between them. A generic bilinear
quad bake cannot restore a lost internal UV seam.

Inspect this candidate's UVs against the source. Use source-aware rebaking for
merged surfaces or retain seam-incompatible triangles; never silently claim
visual equivalence. Do not solve this by shipping flat shading or disabling
textures. Quantization/bake changes require visual comparison and explicit notes.

## Validation at handoff

Ten focused mesh-workshop tests pass (rerun for this handoff), covering export,
safe selection, import resources, quad preservation/splitting, both windings,
UV/material retention, crossed-face rejection and unchanged source files.
GUI smoke test passed after the split-checkbox change. These are host-tool tests,
not evidence of Saturn rendering or ISO performance. No new runtime edits, builds
or emulator runs were performed for this documentation handoff.

User instructions: preserve controls/audio/scene; 4 MB RAM cart may be assumed
present, but do not assume its memory is a fast staging target. Finish a bounded
implementation and measure the ISO; avoid another profiler detour.
