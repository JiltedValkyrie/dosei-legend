# Map Workshop

Open `open-map-workshop.bat`, or click **Map Workshop** in Mesh Workshop.
This is the room/layout editor. Mesh Workshop remains the asset inventory and
whole-room mesh publisher. No new Python dependencies: Tkinter and Pillow.

The current room picker covers Kokiri Forest rooms 0-2 and Deku Tree room 0.
Decomp and verified US 1.2 ROM paths come from launcher Config. Original mode
reads ROM geometry directly; actor models are labelled markers, not animated
gameplay. Original ROM/decomp files are never overwritten by this tool.

## Navigate and inspect

| Action | Input |
|---|---|
| Look / fly | Hold RMB; mouse looks, WASD moves, Q/E down/up |
| Change speed | RMB + wheel |
| Orbit selection | Alt + LMB |
| Pan | MMB or Alt + MMB |
| Dolly | Wheel or Alt + RMB |
| Select / frame | LMB click or Outliner; F or double-click row |
| Hide overlays / immersive | G / F11; Escape releases camera |
| Exact camera transform | Camera button (XYZ, yaw/pitch degrees, speed) |

Search the World Outliner by name, kind or source parameters. Inspect native
XYZ and original actor parameters in Details. Open **Selected object /
Materials / Code** for the selected item. Source paths distinguish original
decomp actor code, project converters, and mapped runtime implementations.
Open a selected source in VS Code; if unavailable, choose an editor executable.
An original actor's code existing does not mean its behavior is ported.

Choose **Textured** for a diffuse texture inspection view. It uses cached
32-pixel triangle patches and affine, depth-sorted CPU rendering at up to
640x400, scaled to the viewport. During mouse navigation it uses Solid for
responsiveness. This is not the Saturn renderer or N64 combiner/lighting;
intersecting faces can sort incorrectly and near-clipped faces use solid fill.
Current baked mode has only palette colours; texture inspection/editing uses
Original or a named layout. Collision/exits/spawns cover the whole scene.

## Move or replace one mesh object

1. Choose **Save as** to create a named alternate first; Original is read-only.
   Select a Mesh object in the alternate. These are real ROM
   display-list groups; one group can contain several props. They are not
   guessed semantic objects such as "one tree".
2. Right-click its World Outliner row for **Export**, **Import / replace**, or
   **Re-import last OBJ**. Export also works on Original; editing does not.
   Imports refresh the current map and retain camera position and selection.
   Alternatively, open Selected object. Set X/Y/Z, yaw in **degrees**, and uniform scale, then
   **Apply placement**. Original-object moves preserve their original UVs and
   textures. Collision is separate and does not move with the visual mesh.
3. **Export mesh** opens Save As: choose a filename such as `Water platform.obj`.
   It writes that OBJ, a matching MTL, original full texture PNGs and
   `Water platform.materials.json`. Textures retain their source dimensions and
   decoded RGBA pixels; shared images are exported once, never as triangle tiles.
   OBJ stays local Y-up. Edit the PNGs or mesh in your normal editor.
4. **Replace OBJ...** replaces only that object. It uses the current placement
   fields. Keep OBJ vertices local, scale in source units, finite UVs (tiling
   outside 0..1 is supported, up to +/-4096), and
   include MTL plus each material's diffuse `map_Kd` image. Triangles and convex
   quads are accepted; incompatible quads are split. Material names may be
   arbitrary single words. Only diffuse maps are imported, not shader graphs
   or MTL lighting parameters. Keep the exported `.materials.json` with the OBJ/MTL: it preserves repeat,
   mirror, clamp, mask periods, primitive tint and cull/mesh flags on re-import.
   Source scale/shift/origin are absorbed into OBJ UVs. Do not rename exported
   dosei_* materials without updating the sidecar. Missing metadata fails
   instead of silently changing texture wrapping. Third-party OBJ without a
   sidecar defaults to repeating diffuse textures; legacy bundles stay unchanged.
5. **Re-import OBJ / UV** rereads the last file used for this object in the
   current session, including its MTL/images. After restarting, choose it again.
   UV changes come from the imported OBJ; this is not an automatic UV unwrapper.
6. **Validate room / rebake UV** runs the production room converter and capacity
   checks in temporary storage. This checks the entire room with the draft
   replacement and regenerates Saturn-compatible texture tiles. Results refer
   to the draft snapshot taken when clicked. It does not update the disc.

**Restore original object** removes only that object's mesh override.
Placement uses the original bounds centre as pivot. Export of an already
placed object removes its placement transform so re-import does not apply it
twice. Mesh XYZ accepts finite source units; scale must be 0.001-1000 and final
geometry must fit signed 16-bit world coordinates and production budgets.

## Materials and textures

The selected-object window lists diffuse textures/material names, dimensions,
original texture address and sampler properties. Select one to see its image.
**Export texture PNG** exports the image without resampling. **Replace texture
PNG** accepts the same dimensions, affects only that material on the selected
object, and stages a new object bundle with intact images and source UVs;
use OBJ/MTL re-import for dimension/UV changes or an externally edited material
bundle. Alpha is retained. Full N64 combiners and UE material graphs are not
implemented. Replacing a texture does not globally replace shared ROM textures.

## Save, choose and build

Changes go into a draft. **Save as** creates a named alternate; **Save** updates
it. Actor placements and individual mesh overrides can share one alternate.
Forest grass/sign/chest XYZ edits remain available in the main Details area;
sign/chest yaw uses native signed angle units, unlike mesh/camera degrees.

### Preview in the actual game: two steps

Close Kronos before rebuilding a disc it has open.

1. Click **1. Save + build this map...**. The editor saves your draft and selects
   the visible map automatically. In the build window, leave **Clean** selected
   and click **Build**. Wait for success, then close that window.
2. Click **2. Play in Kronos**. This launches `game/build/game-clean.cue` through
   the configured launcher. Enter the forest to inspect your replacement.

The persistent preview bar says whether edits exist only in the editor, a build
window is open, or the saved map is in a verified Clean image. Play enables only
when the successful-build receipt matches this map and its saved edits, and the
ISO/CUE still match that receipt. Images built before this workflow have no
receipt: build once to enable Play. This checks the map version, not every other
source-code/audio change. The build remains the real game, not editor Play mode.

**Save map** stores edits without building. **Save as...** makes another named
alternate. **Reset to original** restores the preview baseline without deleting
alternates; Step 1 then builds Original if that is what you are viewing.
**Current baked** shows the latest baked geometry; Step 1 in that mode uses
legacy whole-room Mesh Workshop publishing with original actor placements.
Named layouts instead use their own per-object replacements.

Variants and immutable mesh bundles live under `game/assets/layouts/`; keep
referenced files in Git. Re-import makes a new content-addressed bundle, so old
saved alternates keep their old mesh/material versions. Draft imports can leave
unreferenced bundles; they do not become active without saving/selecting them.
Clean freezes the saved choice, verifies fingerprints and runs normal capacity
checks. Host JSON is not added to the Saturn disc.

Limits: no collision editing, general actor additions, dialog/event editing,
transform gizmos, alternate scene headers or gameplay simulation.
Test moved/replaced geometry in Kronos after baking. Original collisions may
no longer match moved visuals; mesh edits do not imply matching collision edits.

## Undo / Redo

Toolbar Undo/Redo or Ctrl+Z / Ctrl+Y (also Ctrl+Shift+Z) restores draft editing
actions: mesh import/re-import, placement, texture replacement, restore-object,
and supported actor placement edits. The map refreshes after undo/redo, including
returning to the affected room. A new edit clears redo. Save keeps history; undo
after Save makes the draft unsaved again. Switching layouts clears history.

Original is read-only: create/select a named alternate before changing anything.
Undo changes the draft, not files previously saved/exported or an already built
image. Save and rebuild to publish an undone/redone state. Camera navigation,
file exports and build selection are not document-edit history actions. Imported
bundles remain available so undo/redo can restore prior mesh/material versions.

## Names and source textures

Right-click a mesh and choose **Rename**, or select it and press **F2**. Names
are saved in the named alternate, remain searchable in World Outliner, and
support Undo/Redo. Stable source IDs stay unchanged. A blank name restores the
source label. Export suggests the Outliner name, but you can choose any legal
OBJ filename. Original stays read-only; Save as an alternate before renaming.

The old triangular checker atlas was an editor exchange approximation, not the
original game texture. New export never creates it. Original mode exports actual
decoded ROM images; previously imported old-atlas meshes still contain their old
atlas until restored/replaced from Original. N64 images may be tiny (for example
16x32) because they repeat over geometry. Texture PNG export does not enlarge or
repaint them. The Saturn build converts source UVs/images into VDP1 tiles; the
CPU preview is still an approximation, not proof of in-game appearance.

Standard OBJ/MTL cannot express every N64 sampler or combiner. The sidecar keeps
wrap/mirror/clamp behavior for Map Workshop and the game bake. A DCC may need
its texture-node wrapping configured to match; per-vertex lighting and full N64
combiner behavior are not exported. Keep the sidecar filename/MTL comment when
exporting an edited mesh, or copy it beside the renamed OBJ with the same stem.

Blender may rename OBJ/MTL and remove custom MTL comments. Keep the original
exported MTL and sampler JSON beside the edited files. Re-import now recovers
the sampler through matching material names AND exact texture paths in that
original MTL. Conflicting matches fail; no filename-stem guessing is used.
An explicit edited-OBJ-name.materials.json still takes precedence.
