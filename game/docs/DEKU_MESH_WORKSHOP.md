# Deku Tree: room entry and Mesh Workshop

## Current scope

The forest's original exit collision now leads to Deku Tree room 0, spawn 0.
The room's original exit returns to forest spawn 1 in forest room 1.
The full original dungeon collision is loaded, but only room 0 is rendered.
Dungeon doors, other room transitions, enemies, puzzles and Gohma are not implemented
by this change. Do not walk beyond room 0 expecting the rest of the dungeon.
The mouth story sequence and progression gates remain separate work.

## Export all areas

From the repository root in PowerShell:

```powershell
python game/tools/deku_mesh_catalog.py
tools/mesh-workshop/open-mesh-workshop.bat
```

Refresh/reopen the workshop after generating. Select `YDAN_ROOM_0` through
`YDAN_ROOM_11`, or `YDAN_BOSS_ROOM_0` / `YDAN_BOSS_ROOM_1`. All 14 source rooms
are available. The generated catalog files live in `game/build/generated/deku-edit`.
They are editing previews, not runtime room banks.

Use Export OBJ, edit in Blender, then Import OBJ. Each export/import creates a
revision under `workspace/meshes/<asset-id>/exports` or `imports`. Keep OBJ, MTL
and atlas together. Keep native world coordinates, scale 1, Y up; do not center
the room. Use the workshop's Blender axis guidance. Keep triangles or convex
quads. Split invalid/non-convex quads before importing.

The exported UVs use a baked preview atlas, not the original N64 UV layout.
The workspace is ignored by Git: keep your own backup of finished edits.

## Point the game build at an edited room manually

Create `workspace/deku-imports.json` (paths below are examples; replace them):

```json
{
  "ydan_room_0": {
    "obj": "meshes/YOUR-ASSET-ID/imports/YOUR-REVISION/mesh.obj",
    "atlas": "meshes/YOUR-ASSET-ID/imports/YOUR-REVISION/atlas.png",
    "uv_mode": "keep"
  }
}
```

Paths are relative to the JSON file, or absolute. Use the actual filenames in
your revision folder. Then, with Kronos closed:

```powershell
$env:ROOM_IMPORTS = (Resolve-Path workspace/deku-imports.json).Path
powershell -NoProfile -ExecutionPolicy Bypass -File tools/launcher/build-game.ps1 -Variant clean
```

Open the same `game/build/game-clean.cue`. Build output must contain
`room import: ydan_room_0` and your OBJ path. The generated
`game/build/generated/rooms_manifest.json` records the chosen path and UV mode.
The GUI preference checkbox alone does not select a runtime replacement.
Do not use `AUTHORED_OBJ` for this: that older option replaces the forest path.

To restore original source geometry in the next build:

```powershell
Remove-Item Env:ROOM_IMPORTS
```

Other room keys follow the same naming (`ydan_room_1`, `ydan_boss_room_0`, etc.),
but a key is consumed only when that room is registered for runtime export.
Currently only `ydan_room_0` is registered. Export/import all other rooms for
editing now; add dungeon room streaming before enabling them in gameplay.

## Keep, change, transfer or ignore UVs

* **Keep/change:** `uv_mode: "keep"` uses OBJ `vt` coordinates exactly. Edit UVs
  in Blender's UV Editor, export UVs, and point `atlas` at the matching image.
  A single atlas is supported. Bake multiple materials into one atlas first.
* **Ignore:** set `uv_mode: "flat"` and `colour: [140, 120, 80]`. Omit `atlas`.
  UVs/textures are ignored; every face gets that RGB colour. An OBJ without UVs
  can go directly into this JSON hook even if the GUI importer rejects it.
* **Transfer:** set `uv_mode: "transfer"`, `uv_from` to the original exported
  OBJ, and `atlas` to that export's atlas. UVs are sampled from the source mesh
  using vertex positions. `uv_tolerance` defaults to 24 world units; exceeding
  it fails the build. This suits nearby geometry edits, not a rebuilt layout.

Example flat entry:

```json
{"ydan_room_0": {"obj": "my-room.obj", "uv_mode": "flat", "colour": [140,120,80]}}
```

Optional `units_per_texel` (default 6) and `max_tile` (default 32) control texture
bake density. The importer checks its geometry/VRAM budget including Link.

**Visual imports do not change collision.** Moving a floor or wall in Blender
does not move its solid surface. Original collision comes from
`game/tools/build_scene_table.py`; runtime entry/loading lives in
`game/src/scene_flow.c`. Room-bank import/export lives in
`game/tools/build_room_scene.py` and `game/tools/room_imports.py`.

## First Kronos checks

Walk into the Tree entrance, check room 0 ground/camera, walk back out. Confirm
forest return position and actors. Check RAM/VRAM and reload behavior. Then test
one small visible mesh edit with `ROOM_IMPORTS` and restore the source build.

## Validation / handoff, 2026-09-28

Clean disc built successfully; BSS ends at `0x060834b0`, leaving 2,896 bytes below
SGL with concurrent Saria changes. No emulator verification yet; no commit made.
The shared build also needed the Saria cue-channel constant exposed in
`gameplay.h` so `npc_draw.c` could compile; gameplay uses the same constant.

All 14 catalog files pass the workshop reader. Three room-import tests and ten
existing Mesh Workshop tests pass. A real room-0 export was reimported and packed:
585 vertices, 927 faces, 322,944 texture bytes (preview round-trip, not the default
disc geometry). Original source room banks remain selected on the built disc.
The existing room-bank policy test still assumes every face uses sort byte
0x67; the established floor policy emits 0x66 on qualifying faces. It fails on
the three forest banks and now the dungeon bank too. No renderer policy changed
to satisfy that outdated assertion.
