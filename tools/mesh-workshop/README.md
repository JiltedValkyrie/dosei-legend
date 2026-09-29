# Mesh Workshop

Double-click open-mesh-workshop.bat. Requires Python, Tkinter and Pillow.
Help > Mesh Workshop guide (or F1) opens this guide offline inside the program.

## Put an edited mesh in the game

1. Choose Game room: Kokiri Forest room 0, 1 or 2, or Deku Tree entry room 0.
2. Select your edited OBJ in the browser and click Publish mesh. If the selected
   asset is not an OBJ, Publish mesh opens a file picker instead. Keep its MTL
   and texture files beside it. No separate Store step is required.
3. Wait for Installed. Existing files for that room are overwritten without
   another confirmation. Close Kronos, rebuild Clean, then open
   game/build/game-clean.cue.

The program copies the OBJ, MTL and texture into
 game/assets/room-meshes/<room>/ and updates game/assets/room_imports.json.
These files belong in Git; commit them together. Every normal Clean build
uses the selection automatically. No environment variables or agent needed.
The currently running game/disc does not change until rebuilt.

Only the chosen room's visual geometry changes. Collision, doors, actors,
spawns and other rooms stay as before. Moving a wall or floor does not move
its collision. This does not install Link or other actor meshes.

## Asset browser

The list inventories local files in game/assets, game/levels, shared/assets,
game/build/generated, game/build/cd, workspace/meshes and generated CD tracks.
Source, Generated, Staged, Shared and Workspace locations distinguish editing
inputs from build output. This is the complete inventory of those local roots,
not a claim that every asset in the original ROM has already been extracted.

Search matches path, type, location, publish state/date and assigned room names;
multiple words all match.
Choose a type or publish state to narrow the list. Click any column heading
to sort; click again to reverse it. Bytes sort numerically. Scrollbars cover
long lists/paths. Open asset folder opens Explorer at the selected file.

Publishing updates room_imports.json and records a UTC date, the input OBJ's
hash, and hashes of all installed mesh/material/texture files in the same
transaction. Failed publication leaves the previous record intact. No date
is invented from file modification times. Refresh rescans and verifies hashes.

- Published: matches the active recorded room publication.
- Modified: a recorded installed file or the source OBJ has changed.
- Missing: an active publication references a missing file.
- Assigned: an older/manual room override has no recorded publication hashes.
- Not published: no active Mesh Workshop publication record for this file.
- Not tracked: another asset type without Mesh Workshop publication metadata;
  for example, this browser does not invent Music Workshop publish dates.
- Staged: generated disc input, without a Mesh Workshop publication record.

Last publish is the active room record's actual successful publish time.
Unknown / never means no recorded date; earlier manual installs stay unknown.
This tracks current room overrides, not a historical audit log of superseded
versions. The record covers installed dependencies; source OBJ hashes do not
track later changes to external source MTL/texture files. Published means ready
for the next Clean build, not proof that the currently running disc includes it.

Every file type is browsable. Export OBJ remains limited to supported KFR1
meshes; room publishing remains limited to edited OBJ bundles and the four
registered room targets. The browser does not claim to publish animations,
enemies, collision or triggers. Select a published asset with one assigned
room to automatically select that target; you can then choose another room.

## Toward the 3D level editor

The asset browser is the first part, not a 3D editor yet. The implementation
plan and acceptance criteria are in game/docs/LEVEL_EDITOR_PLAN.md. It covers
reading decomp/ROM scene data, a room viewport, placed enemies/actors, collision,
triggers and a reversible edit/bake workflow without requiring an agent.

## Export and edit

Select a source, then Export OBJ. Open workspace finds exports and optional
stored revisions under workspace/meshes. Those revisions are Git-ignored;
Publish mesh copies the needed files into the game.

FOREST.BIN contains the combined forest, not one room. Do not install the
whole forest into a single room. Supply only the intended room geometry.
Generate Deku room previews from the repository root with:

    python game/tools/deku_mesh_catalog.py

Refresh and choose YDAN_ROOM_0 for the playable Deku entry room. Other Deku
room previews are for editing but are not playable/install targets.

In Blender use Forward -Z, Up Y and scale 1 on both import and export.
Keep native world coordinates; do not center the room or apply extra rotations.
Keep UVs in [0,1], material names flags_0 through flags_3, and one shared atlas.
Export UVs and materials with the OBJ. Flags retain backface culling and
screen-door transparency. Triangles and planar convex quads are accepted.

Split incompatible quads keeps valid quads and splits recoverable concave or
bent quads along a valid diagonal. Crossed/degenerate faces and n-gons fail.
Store edited OBJ is optional: it saves a separate editing revision without
selecting a game room. You can install that revision's mesh.obj later.

Exported textures are resampled previews of Saturn tiles, not original N64 UVs
or a pixel-identical round trip. Preserve seams when joining triangles.

## Troubleshooting and undo

- Build Clean once if Link's generated mesh is missing. The installer needs
  it for the room memory check. Geometry, textures, sprites and forest actor
  reservations are checked before replacing an installed mesh. The final
  build also checks current assets and runtime memory limits.
- A room needs one shared atlas. Bake multiple textures into one atlas first.
- A ROOM_IMPORTS environment variable takes precedence over the Workshop
  file. Clear it before a normal Workshop build in PowerShell:

      Remove-Item Env:ROOM_IMPORTS -ErrorAction SilentlyContinue

- To restore a room's original artwork, remove its entry from
  game/assets/room_imports.json and rebuild Clean. An empty {} restores all
  original room meshes. Git can restore an earlier installed version.
- Failed validation leaves installed assets unchanged. Ordinary write
  failures restore files already replaced during the operation.

## Developer checks

    python tools/mesh-workshop/mesh_workshop.py --smoke-test
    python -m unittest discover -s tools/tests -p "test_mesh*.py"
    python -m unittest discover -s tools/tests -p "test_asset_catalog.py"
    python -m unittest discover -s game/tests -p "test_room_imports.py"
# Map Workshop

Click **Map Workshop** to open the room/layout editor, or launch
`../map-workshop/open-map-workshop.bat` directly. It provides UE-style camera
navigation, named layout variants, individual mesh replacement/placement,
material and texture exchange, source code links, UV bake validation and the
Clean build dialog. Mesh Workshop remains the asset inventory/whole-room tool.

See [Map Workshop guide](../map-workshop/README.md) or press F1 inside the editor
for controls, save/build workflow, supported formats and current limitations.
