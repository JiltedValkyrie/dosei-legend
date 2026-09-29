# M5 solo guide: start here

Written for the human, 2026-09-28. This is a practical companion to
[M5_DEKU_TREE_PLAN.md](M5_DEKU_TREE_PLAN.md), not a claim M5 is implemented.
Instructions and paths below were checked against the current checkout.
Claude may change M3/M4 before you start: check the latest handoff first.

For file purposes, C boilerplate, and exact decomp/ROM research locations, use
[M5_CODE_AND_SOURCE_MAP.md](M5_CODE_AND_SOURCE_MAP.md).

## Your first goal

**Room 0 entry is now wired in code.** The original forest exit collision enters
the Tree; its exit returns to the forest's correct spawn room. Only room 0 is
playable. Test this in Kronos before extending the dungeon.
All 14 dungeon/boss rooms are available for editing; see
[Deku Mesh Workshop](DEKU_MESH_WORKSHOP.md) for export/import and UV instructions.
Next, inventory the dungeon actors and implement its room transitions.

You can do inventory and geometry work before M4 finishes. Burning webs and
slingshot puzzles depend on working M4 items; leave those until their dependency
exists. Do not fake item grants or remove gates to declare progression complete.

## Before editing

In VS Code, open Terminal -> New Terminal. Use PowerShell at the repository root:

```powershell
Set-Location 'D:\Workspace-Claude\saturn-homebrew\dosei-legend'
git status --short
git log -3 --oneline
```

If status lists changed files, they may be Claude's unfinished work. Do not
discard, reset, or mix them into your first experiment. Let Claude finish the
authorized checkpoint, or record exactly what is still pending before editing.
Once the baseline is committed, create your own branch:

```powershell
git switch -c human/m5-shell
```

This branch starts from your current checkout. Confirm you started from the
intended `dev` checkpoint. Creating a branch does not isolate uncommitted files.

Read these in order:

1. Top of [OPUS_HANDOFF.md](OPUS_HANDOFF.md): what changed most recently.
2. [DEMO_PLAN.md](DEMO_PLAN.md): scope and what remains unfinished.
3. [M5_DEKU_TREE_PLAN.md](M5_DEKU_TREE_PLAN.md): M5a is your first stage.
4. [Bible](../../DOSEI-LEGEND-BIBLE.md): coordinates, actor drops and asset rules.

## First session: run a read-only dungeon inventory

Paste this whole block into the root PowerShell terminal. It uses the existing
ROM extractor to print room segment names and entry spawns. It does not build a
disc, modify scene registration, or enable dungeon access.

```powershell
@'
from pathlib import Path
import sys
sys.path.insert(0, str(Path('shared/tools').resolve()))
import build_kokiri_scene as source
oot = Path('D:/Workspace-Claude/game-decomps/n64/oot')
for prefix in ('ydan', 'ydan_boss'):
    segments = source.extract(oot, prefix=prefix)
    rooms = sorted(n for n in segments if n.startswith(prefix + '_room_'))
    print(prefix, 'rooms:', len(rooms))
    for name in rooms:
        print(' ', name, len(segments[name]), 'bytes')
    print('spawns:', source.spawn_points(segments[prefix + '_scene']))
'@ | python -
```

If `python` is missing, use the Python executable configured in the launcher or
`config.ini`. If ROM extraction fails, check that configured decomp/ROM paths
exist. Do not download another ROM or change offsets to make the error disappear.

Create `game/docs/M5_ROOM_NOTES.md`. Copy the output there. The M5 plan expects
12 dungeon rooms and two boss rooms; verify rather than force that count.
Segment sizes are disc data sizes, **not** resident Saturn memory costs.

Add a small table: room, outgoing room, door actor, parameters, required item,
switch/chest flag, source reference. Unknown is a valid entry. Do not invent it.
Later use the layer/header parsing in `build_actor_manifest.py` as a model;
that tool currently has its own M3-only `SCENES` list. Its existing output is not
an automatic complete dungeon manifest.

Success today: the notes identify real rooms and spawns. No game changes needed.

Verified when writing this guide: the command runs successfully and finds 12
`ydan` rooms and two `ydan_boss` rooms. Dungeon spawn 0 is (-4, 0, 603), yaw
32768; spawn 1 is (-850, -1880, -894), yaw 4005. Boss spawn 0 is
(321, -640, 772), yaw 37319. These are original source coordinates, not a recipe
for teleporting Link without loading the matching room/collision.

## Where the code lives

Use Ctrl+Shift+F in VS Code to find the named function. Names are more useful
than line numbers, which change as Claude works.

| File | What to inspect |
|---|---|
| `game/tools/build_scene_table.py` | `SCENES`, `entrance_table`, `NEW_GAME_SCENE`, `NEW_GAME_SPAWN`. Source entrances become generated scene/spawn/door tables. |
| `game/tools/build_room_scene.py` | `emit_rooms`, `transitions`, `pack_room`. Geometry/texture banks and room transition data. |
| `game/tools/build_actor_manifest.py` | Scene/header/layer parsing and actor/object inventory. M3 coverage is hardcoded. |
| `game/src/scene_flow.c` | `scene_flow_load`, `scene_flow_spawn`, `scene_flow_door_at`, `scene_flow_index_for_save`, collision loading. |
| `game/src/demo.c` | `take_door`: transition, spawn placement, camera/player reset and failure handling. Trace a working house door here. |
| `game/src/kokiri_sgl.c` | `room_load_bank`, `kokiri_scene_load_bank`, `kokiri_scene_update_room`. Last one still selects forest banks explicitly. |
| `game/src/save_state.h` | Existing `SAVE_SCENE_DEKU_TREE` and `SAVE_SCENE_DEKU_TREE_BOSS`. Save IDs are not scene-table indices. |
| `game/src/ram_cart.h`, `ram_low.h` | Fixed memory allocations and overlap guards. |
| `game/tools/asset_names.py`, `game/src/asset_names.h` | Matching disc-name encoding: room 10 is `A`, room 11 is `B`. |
| `game/build.sh` | Asset generation order. New exporter output must exist before disc packaging. |

Generated files under `game/build/generated` and `game/build/cd` are outputs.
Edit the Python generator, not its generated C header or binary.

## Second session: understand a working doorway

Follow Link's house before making a dungeon door:

1. `build_scene_table.py` describes the original house/forest entrance mapping.
2. Find its generated entries in `game/build/generated/scene_table.*`.
3. Follow `scene_flow_door_at` into `take_door` in `demo.c`.
4. Follow `scene_flow_load`, then player placement from `scene_flow_spawn`.
5. Find `door_armed`. It prevents an arrival from immediately sending Link back.

Write this call chain in your notes. A scene load, a room change, and a spawn
placement are different operations. A successful file read alone does not prove
Link stands in the correct room on the correct collision mesh.

## First game change: one-room development fixture

This is an implementation checklist, not a one-line patch. Work one part at a time.

1. Add dungeon scene registration only after checking the inventory. Use the
   existing save IDs; do not renumber established scenes or saves casually.
2. Inspect every loop over `SCENES` before changing it. Adding `ydan` can make
   exporters process all its rooms and raise global buffer maxima. A room-0
   playtest does not mean only room 0 was exported or budgeted.
3. Check generated collision counts against `SCENE_COLLISION_MAX` (currently
   2321). The full Tree collision added 10,374 bytes to dynamic allocation,
   not static BSS. Check actual allocator headroom in Kronos.
4. `scene_flow_load` now chooses the source spawn's room and rejects rooms that
   are not registered. Tree spawn 1 (room 9) remains unavailable.
5. Check `kokiri_scene_update_room`: forest-specific transition data and
   `SCENE_SPOT04` loads must not run for the dungeon. Generalize selection using
   the loaded scene and its transition records; preserve working forest behavior.
6. Check scene-specific grass/NPC/prop draw and update paths. A dungeon is a
   mesh scene too; `!scene_flow_is_interior()` does not mean Kokiri Forest.
7. Use a clearly named development-only entry fixture if the mouth is not ready.
   Keep release/new-file progression unchanged. Document exactly how to enter
   the fixture and remove or disable it before release.

First playable success: room 0 draws, Link stands on its real floor, movement and
camera work, and loading the forest again works. This is **M5a shell**, not a
finished entrance or dungeon. Keep actors/puzzles outside this first change.

## Build and test loop

Close Kronos before building. From the root terminal:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/launcher/build-game.ps1 -Variant clean
```

Open `game/build/game-clean.cue` in Kronos after a successful build. Keep that
name. Do not rebuild while Kronos has the image mounted.

Read the final boundary line. The last verified baseline had **4,528 B below
SGL**, but your next build is the authority. Code and static data both cost
high work RAM. Disc size is not RAM usage. Never disable the boundary check,
overlap a carve, or shrink the heap simply to obtain an image.

For room-format/exporter changes, start with this focused test module:

```powershell
python -m unittest game.tests.test_room_scene -v
```

This does not prove doors or dungeon gameplay. Add a regression test for the
specific behavior you change. If using full-suite results, compare named failures
with the baseline: seven failures/setup errors were previously reported, but a
matching total does not prove they are the same failures.

Keep one short manual checklist per change: enter, floor, camera, exit, re-enter,
forest unchanged. Add save/reload/Continue only once those paths are implemented;
never call them passed just because ordinary entry worked.

## When something breaks

| Symptom | First investigation |
|---|---|
| Build error | First actual error, not the last `make` failure. Save its text. |
| Scene load fails | Exact requested filename, generated file existence, format/capacity guard. |
| Link falls or appears in the sky | Spawn room, feet/eye offset, loaded collision and rebuilt collision index. |
| Wrong room after crossing | Scene ID versus save ID, transition selection, hardcoded forest bank load. |
| Disappearing geometry/actors | SGL rejection counts, vertex/polygon limits and texture/sprite budgets. |
| Room 10 or 11 missing | Shared base-36 name helper; no hand-built decimal room filenames. |
| Plants have solid backgrounds | Source alpha, baked zero-index pixels and VDP1 cutout flag; do not erase plant geometry. |

Stop the current change when you cannot explain the failure. Keep notes and work
on the read-only room/actor inventory instead. That is useful progress without
turning one unexplained failure into several.

## Save your work in small checkpoints

After a working task, inspect and stage only its named files:

```powershell
git diff --stat
git diff --check
git diff -- game/tools/build_scene_table.py
# Example only: stage your actual reviewed file, not every changed file.
git add game/docs/M5_ROOM_NOTES.md
git diff --cached
git commit -m "Document Deku Tree room inventory"
```

Do not use `git reset --hard`, `git clean -fd`, or restore whole files to remove
one bad edit. VS Code Undo or a small corrective edit is safer around shared work.

Use this entry in `game/docs/HUMAN_DEV_LOG.md` after each session:

```text
Date / branch / last good commit:
Small goal:
Files and functions changed:
Original OoT source checked:
Tests run and results:
Build result / RAM gap:
Kronos steps and observed result:
Still broken or unknown:
Next smallest step:
```

After the shell: one source door, then the mouth greeting/gate, then one puzzle
mechanism. Follow M5a/M5b ordering in the detailed plan. Do not duplicate existing
push-block, lift, drop or item systems. Every added actor includes its original
spawn parameters, reward rules and persistent flags in the same task.
