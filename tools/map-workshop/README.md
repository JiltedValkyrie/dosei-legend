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

1. Select a Mesh object in Original or a named alternate. These are real ROM
   display-list groups; one group can contain several props. They are not
   guessed semantic objects such as "one tree".
2. Open Selected object. Set X/Y/Z, yaw in **degrees**, and uniform scale, then
   **Apply placement**. Original-object moves preserve their original UVs and
   textures. Collision is separate and does not move with the visual mesh.
3. **Export OBJ / MTL / atlas** writes the selected object in local Y-up units.
   Edit it in Blender or another mesh tool. The bundle includes diffuse atlas
   PNG and MTL. Exports are resampled UV patches, not lossless source textures;
   use Export texture PNG for the original individual image.
4. **Replace OBJ...** replaces only that object. It uses the current placement
   fields. Keep OBJ vertices local, scale in source units, UVs in 0..1, and
   include MTL plus each material's diffuse `map_Kd` image. Triangles and convex
   quads are accepted; incompatible quads are split. Material names may be
   arbitrary single words. Only diffuse maps are imported, not shader graphs
   or MTL lighting parameters. Exported flags_0..3 preserve cull/mesh flags.
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
object, and stages a new object bundle. This operation rebakes its UV atlas;
use OBJ/MTL re-import for dimension/UV changes or an externally edited material
bundle. Alpha is retained. Full N64 combiners and UE material graphs are not
implemented. Replacing a texture does not globally replace shared ROM textures.

## Save, choose and build

Changes go into a draft. **Save as** creates a named alternate; **Save** updates
it. Actor placements and individual mesh overrides can share one alternate.
Forest grass/sign/chest XYZ edits remain available in the main Details area;
sign/chest yaw uses native signed angle units, unlike mesh/camera degrees.

**Use for next build** chooses the saved layout. Then **Build Clean...** opens
the existing build dialog with Clean selected. Merely previewing or saving does
not change the selected version or an existing ISO. Save a draft before building
it; the build uses the saved next-build selection, not the live preview.

**Reset to original** changes the preview without deleting saved alternatives.
Use for next build selects that baseline for the image. **Current baked** shows
the last baked geometry; Use for next build there restores legacy whole-room
Mesh Workshop publishing with original actors. Legacy whole-room imports are
bypassed by Original/named layouts; use named per-object replacements instead.

Variants and immutable mesh bundles live under `game/assets/layouts/`; keep
referenced files in Git. Re-import makes a new content-addressed bundle, so old
saved alternates keep their old mesh/material versions. Draft imports can leave
unreferenced bundles; they do not become active without saving/selecting them.
Clean freezes the saved choice, verifies fingerprints and runs normal capacity
checks. Host JSON is not added to the Saturn disc.

Limits: no collision editing, general actor additions, dialog/event editing,
transform gizmos, undo stack, alternate scene headers or gameplay simulation.
Test moved/replaced geometry in Kronos after baking. Original collisions may
no longer match moved visuals; mesh edits do not imply matching collision edits.
