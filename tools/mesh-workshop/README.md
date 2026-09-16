# Mesh workshop

Double-click **open-mesh-workshop.bat** here. Requires Python with Tkinter and
Pillow (already used by the project converters). No Blender installation is
required to export or import files.

The list discovers supported KFR1 v2 visual meshes in `game/levels/`,
`game/assets/` and `game/build/generated/`. FOREST.BIN is the static level;
LINK.BIN is a generated actor mesh after a game build. Executable files are not
meshes. Collision is neither exported nor replaced.

## Workflow

1. Select the scene and click **Export OBJ**. Each export creates a new folder
   under `workspace/meshes/<mesh-id>/exports/` containing mesh.obj,
   mesh.mtl, atlas.png and source provenance. Use **Open workspace** to find it.
2. Import OBJ in Blender with Forward **-Z**, Up **Y**, scale **1**. Use the same
   axes/scale on export. Do not apply an additional axis rotation. Verify native
   dimensions; the workshop rejects coordinates beyond signed 16-bit range.
3. Merge suitable triangles into planar convex quads. Preserve UV seams and
   material boundaries; keep `flags_0` through `flags_3` material names. Mixed
   triangles/quads are allowed. Disable **Triangulate Faces** when exporting OBJ. Export UVs
   and materials alongside it, keeping the referenced atlas available.
4. Optionally check **Split incompatible quads on import**, directly below
   **Prefer quads**. This keeps valid quads and splits recoverable non-planar or
   concave quads into two triangles, preserving corner UVs/materials. Crossed or
   unsplittable degenerate faces and n-gons still fail validation. With the option
   off, incompatible quads are rejected as before. Splits choose the shortest
   valid interior diagonal in the dominant projection; this may differ from
   Blender's diagonal for a bent surface. No vertex positions are changed.
   Restart an already-open GUI after updating to see this checkbox.
5. Click **Import edited OBJ**. It validates the mesh and stores a normalized,
   self-contained candidate under a fresh `imports/` revision. Originals and
   earlier revisions are never overwritten. The completion dialog reports quads
   kept, quads split, and output triangles; `mesh.json` also records split OBJ line
   numbers and hashes. An explicitly split import may contain zero remaining quads.
6. **Prefer quads** saves the desired selection in `workspace/meshes/preferences.json`.

## Build support is not implemented yet

The current ISO loader, clipping and texture baking are triangle-only. This GUI
does NOT modify Makefile or replace FOREST.BIN. The preference is recorded for
future build integration; it has **no effect on current ISO builds**. Imported
candidates are explicitly `runtime_ready: false`. The selection helper always
returns the original asset until genuine quad support is implemented. Nothing is
silently triangulated, and a candidate is never advertised as build-ready.

The atlas is a **resampled preview** of already-baked per-triangle Saturn tiles,
not original N64 material UVs or a pixel-identical round trip. Many triangle
boundaries are UV seams; indiscriminate triangle-to-quad conversion can distort
the preview. Correct runtime quad texture baking will need separate work.
Avoid moving geometry: unchanged collision would no longer match it.

Workspace files are local and Git-ignored. Back up edited revisions explicitly
if needed. Editing operations never overwrite existing source meshes or revisions.

The layout migration preserves existing Forest export/import revisions and
preferences in `workspace/meshes/`, retaining the Forest's original catalog ID.
Historical provenance may still say `cd/FOREST.BIN`; it is not rewritten to
pretend those revisions were created from the new directory layout.

Validation without opening a window:

```powershell
python tools/mesh-workshop/mesh_workshop.py --smoke-test
python -m unittest discover -s tools/tests -p "test_mesh_workshop.py"
```
