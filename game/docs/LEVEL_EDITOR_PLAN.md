# Dosei Legend visual editor

Human direction, 2026-09-29: make the game editable by humans without relying
on an agent for asset publishing, layout inspection or routine baking. The
long-term target is an engine-style GUI with a 3D room viewport, hierarchy,
properties, enemies/actors, triggers and clear build results.

## Current delivery

Mesh Workshop has an inventory of local asset files with type/search/sort,
current room publication state and recorded UTC publish dates. Existing mesh
publishing validates and installs OBJ/MTL/textures and the room build selection
together. Music Workshop likewise publishes audio plus its named song route.
Map Workshop (standalone, or opened from Mesh Workshop) provides a Level viewport for the three Kokiri Forest
rooms and Deku Tree entry room. It reads current baked geometry and original
verified ROM metadata, with a searchable World Outliner and Details panel.
See the Workshop README for controls and fidelity limits. Named variants support forest grass/sign/chest XYZ and sign/chest yaw, plus
per-object mesh XYZ/yaw/scale, OBJ/MTL/texture replacement and re-import. Original
mode decodes raw ROM triangles independently of baked meshes. Map Workshop has
source code links, diffuse texture preview, material/image exchange, production
UV/budget validation and the Clean build dialog. Gizmos, broader actor/event
editing, collision variants and runtime verification remain future work.

## Jo Engine tool assessment

The official [Jo Map Editor page](https://jo-engine.org/mapeditor/) documents
MAP/sprite editing and OBJ/Collada conversion. It does not document importing
OoT scene commands, actor parameters, collision surfaces, entrance graphs or
cutscene triggers into an engine-style scene editor. Treat those as custom
Dosei tooling work, not an existing Jo feature we can merely expose.

Keep Jo/SGL as the Saturn runtime and the current converters as the bake
backend. A desktop editor shell can inspect original data and launch existing
builders; it need not inject a running SH-2 game into the host editor. A host
preview and a Kronos run are separate views with different fidelity.

## Read-only scene inspector: first version delivered

Implemented: room picker, palette-average solid/wireframe geometry, source
actor/enemy markers, collision, exit surfaces, player spawns and transition
markers, selection, framing, native-coordinate properties and UE-style camera.
Remaining: textures, alternate scene headers, camera volumes, exact trigger
semantics, additional registered rooms, and manual comparison against gameplay.
The CPU painter renderer is an inspection aid, not an accurate Saturn preview.

1. Open the configured decomp and verified ROM extraction through the existing
   project path settings. Report missing inputs inside the GUI. Never download
   copyrighted game data or rewrite original extraction files.
2. Reuse the decoders behind build_scene_table.py, build_room_scene.py and the
   existing actor/mesh builders. Produce a versioned host scene description
   with stable scene/room/actor IDs and original parameters/provenance.
3. Provide scene/room picker, 3D viewport, hierarchy and property panel. Toggle
   meshes, original collision, actors/enemies, entrances, camera volumes and
   supported trigger overlays independently. Identify unsupported commands
   explicitly instead of inventing empty objects or incorrect behavior.
4. Click a placed actor to inspect original actor ID, params, position, rotation,
   room and source. Use an identified marker when its model is unavailable.
   Trigger descriptions must come from decoded original data and semantics;
   a collision exit index is not an arbitrary editor box.
5. Navigation: orbit/pan/fly, frame selection, wireframe and collision overlay.
   Preserve native coordinates and the Bible's handedness rules. Prove the
   first room's doors/floors and actor placements against source and gameplay.

Acceptance: a human opens Kokiri Forest and Deku entry room, finds an enemy or
door by search, selects it in 3D, sees its source parameters, and understands
what is supported. Previewing produces no edits or game asset replacements.

## Following delivery: editable layout and baking

Add undo/redo, transform gizmos, typed/range-checked actor properties and
explicit Save/Publish. Store overrides in tracked host-side manifests keyed by
stable IDs. Avoid hand-editing generated C, raw ROM addresses or CD filenames.
The asset registry should grow from file inventory to logical assets and
dependency relationships rather than treating duplicate baked files as new
game entities. Retain publication provenance across revisions as that grows.

Implement one actual edit path end-to-end before exposing all controls: change
a supported actor placement, save, bake, and verify the result in Kronos. Mesh,
collision, room bounds and transition changes need their own validated paths;
the current visual OBJ override does not modify collision.

Bake UI should show progress/logs, VDP1/sprite/polygon/work-RAM/file-table
budgets and actionable failures. Use the existing Clean builder. Publish the
asset and its selection/provenance together with rollback for ordinary write
failures. Offer Run in Kronos only after a successful build and respect any
already mounted disc. The editor must explain when changes are only a host
preview, published source, built disc, or verified runtime behavior.

For the full game, plan indexed asset bundles before thousands of loose files
reach the current directory table. Editor JSON/metadata remain host-side;
compile stable constants/tables and pack runtime assets as appropriate.

Keep runtime changes bounded to the verified edit/bake path. Changes to the
renderer, collision format or Jo/SGL behavior need concrete acceptance tests
and must follow the existing renderer-prevention rules. First deliver the
read-only inspector, then the smallest verified edit/bake workflow.

See [Map Workshop Help](../../tools/map-workshop/README.md) for the current workflow.
