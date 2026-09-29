# M5: what each file does, and where the original behavior lives

Read alongside [M5_SOLO_GUIDE.md](M5_SOLO_GUIDE.md). Start with its read-only
inventory, then use this reference when you do not know which file to open.
Examples are teaching scaffolds, not finished dungeon features.

Update: the room-0 entry shell is now implemented. For all 14 room mesh exports,
manual runtime import selection and UV modes, use
[DEKU_MESH_WORKSHOP.md](DEKU_MESH_WORKSHOP.md).

## Four different kinds of files

| Kind | Purpose | Edit it? |
|---|---|---|
| Decomp `.c` / `.h` | Human-readable reconstruction of Nintendo's logic and data structures. Read to learn behavior. | Usually no: reference, not our Saturn implementation. |
| Original ROM / extracted assets | Actual placements, parameters, models, animations and textures for the selected version. | Never edit the original ROM to fix a Saturn bug. |
| Our Python exporter in `game/tools` | Reads original data and writes a Saturn-friendly format offline on the PC. | Yes, when conversion or exported data needs changing. |
| Our runtime `.c` / `.h` in `game/src` | Executes gameplay/rendering on Saturn. | Yes, when behavior or loading needs changing. |

An exporter does not run on Saturn. Generated files are rebuilt from source.
Changing `build/generated/foo.h` alone will disappear at the next build.

The data path is:

```text
US 1.2 ROM + decomp names/XML
           -> Python exporter
           -> generated headers + BIN/COL/MSH/texture files
           -> build packages disc and compiles C
           -> Saturn loader reads data
           -> gameplay updates state
           -> renderer draws current state
```

## Where to look in the decomp

Root on this machine: `D:/Workspace-Claude/game-decomps/n64/oot`.
Open that folder in a second VS Code window for searching. Keep edits in the
Saturn project. The following paths are relative to the decomp root.

| Question | Open/search here |
|---|---|
| Which scene is Deku Tree? | `include/tables/scene_table.h`: search `ydan` / `SCENE_DEKU_TREE`. |
| Which spawn does an entrance use? | `include/tables/entrance_table.h`: search `SCENE_DEKU_TREE` and `SCENE_DEKU_TREE_BOSS`. |
| Which files contain rooms/models? | `assets/xml/scenes/dungeons/ydan.xml`, `ydan_boss.xml`; object XML under `assets/xml/objects`. |
| Extracted dungeon art/data | `extracted/ntsc-1.2/assets/scenes/dungeons/ydan/` and `ydan_boss/`. Contents depend on extraction output; use XML and the ROM parser if no readable C file exists. |
| Which actor does a numeric actor ID name? | `include/tables/actor_table.h`. |
| How does Tree mouth open? | `src/overlays/actors/ovl_Bg_Treemouth/z_bg_treemouth.c` and its `.h`. |
| How does a shutter door work? | `src/overlays/actors/ovl_Door_Shutter/z_door_shutter.c`. |
| How do webs burn/break? | `src/overlays/actors/ovl_Bg_Ydan_Sp/z_bg_ydan_sp.c`. |
| How does a torch work? | `src/overlays/actors/ovl_Obj_Syokudai/z_obj_syokudai.c`. |
| How does a floor/eye switch work? | `src/overlays/actors/ovl_Obj_Switch/z_obj_switch.c`. |
| How do the puzzle scrubs work? | `src/overlays/actors/ovl_En_Hintnuts/z_en_hintnuts.c`; projectile logic in `ovl_En_Nutsball/z_en_nutsball.c`. |
| How does Gohma work? | `src/overlays/actors/ovl_Boss_Goma/z_boss_goma.c`; larvae in `ovl_En_Goma/z_en_goma.c`. Leave these for later. |
| What does an actor drop? | Its death/break function, then `src/code/z_en_item00.c`; check the spawn params too. |
| What do flags/scene headers mean? | `include/scene.h`, `include/actor.h`, `include/bgcheck.h`; follow called helpers in `src/code/z_actor.c`, `z_scene.c`, `z_room.c`. |
| How does Link use an item? | `src/overlays/actors/ovl_player_actor/z_player.c`, plus helpers in `src/code/z_player_lib.c`. |

Search actor filenames if paths change. An actor mentioned in a plan is not proof
it appears in a particular room: confirm its placement in the ROM actor list.

## Which ROM, and how to inspect it

Our extractor `shared/tools/build_kokiri_scene.py` uses the verified US 1.2 `.z64`
with MD5 `57a9719ad547c516342e1a15d5c28c3d`. It reads segment names from
`baseroms/ntsc-1.2/segments.csv` and the DMA table location from `config.yml` in
that directory. Actual ROM location may instead come from `oot_roms` in the
project's `config.ini`.

You normally do **not** open the whole ROM in a hex editor. Use `extract()` to
get the named scene/room bytes; use existing header parsers to read their lists.
That handles compressed segments and verifies the ROM version. XML offsets name
objects within a segment; they are not necessarily file offsets into the ROM.

An N64 address such as `0x06001234` often means segment 6, offset `0x1234`.
Resolve it using the object's segment mapping. It is not a Saturn pointer.

Example Python binary read:

```python
actor_id, x, y, z, rx, ry, rz, params = struct.unpack_from('>HhhhhhhH', room, offset)
```

`>` means big-endian; `H` is unsigned 16-bit; `h` is signed 16-bit. First find
`offset` and count from the **correct room header/layer**. Do not scan arbitrary
bytes looking for a plausible actor. See `build_actor_manifest.py` for this
repository's actual header/layer handling.

## How to read one original actor

For a first exercise, open `z_obj_syokudai.c` without porting it yet:

1. Find the `ActorProfile`: object dependency, category and entry functions.
2. Read `Init`: which bits of `actor.params` choose variant, flag or behavior?
3. Read `Update`: what is checked each frame, and which state functions run?
4. Follow every state transition relevant to your placed variant.
5. Read collision registration and accepted hit flags. A visible flame alone
   does not implement ignition or puzzle completion.
6. Read flag writes and `Destroy`. Separate temporary timer state from saved
   switch state. Understand cleanup before implementing room unload.
7. Read `Draw`: display lists, animation, scale, texture scroll and colors.
8. Search for drops/rewards; explicitly record none if source gives none.

Write a behavior table before C:

| Current state | Event/condition | Next state | Side effect | Source function |
|---|---|---|---|---|
| Fill from source | Fill from source | Fill from source | Timer, flag, sound, collision or reward | Exact name |

Do not copy Nintendo's whole C file into the Saturn project. Types such as
`PlayState`, `SkelAnime`, display lists and N64 collision APIs need adaptation.
Port a small behavior with our existing systems, then test that behavior.

## What the boilerplate files do

For a new mechanism called `deku_torch` (example name, not an existing module):

| File | Job | What does not belong here |
|---|---|---|
| `game/src/deku_torch.h` | Public function declarations and necessary types. Other modules include this contract. | Function bodies or large global data. |
| `game/src/deku_torch.c` | States, timers, source parameter decoding, collision/flag decisions. Prefer platform-free integer code. | Raw ROM parsing or drawing-specific SGL calls if avoidable. |
| `game/src/deku_torch_draw.h/.c` | Load/upload/free model assets and draw a snapshot of current state. | Puzzle progression, rewards or advancing gameplay timers per render frame. |
| `game/tools/build_deku_torch.py` | Optional exporter if no existing exporter handles its assets. Read source models/placements; emit documented binary records. | Runtime gameplay or editing the ROM. |
| `game/tests/test_deku_torch.py` | Host test invoking actual behavior code; assert state, events, flags and timing. | A second copy of the implementation that can agree with the same bug. |
| `game/docs/M5_ROOM_NOTES.md` | Source evidence, placed variants, dependencies and omissions. | Unsupported claims of exact parity. |

Not every actor needs six new files. Reuse shared mesh loading, drops, collision,
save flags and existing exporters. `karebaba.c/.h` and `karebaba_draw.c` show the
logic/render separation. `world_props.c` shows pool handles and shared rewards.

### Minimal pool actor shape (reference only)

This illustrates the actual `actor_profile_t` callbacks. It intentionally does
nothing useful; do not add it to the game and call the torch implemented.

```c
/* deku_torch.h */
#ifndef DEKU_TORCH_H
#define DEKU_TORCH_H
#include "actor_sys.h"
extern const actor_profile_t deku_torch_profile;
#endif

/* deku_torch.c */
#include "deku_torch.h"

static void torch_init(actor_t *actor)
{
    /* Decode the SOURCE params here; document each data[] slot you use. */
    actor->data[0] = 0; /* placeholder state, not an OoT torch state */
}

static void torch_update(actor_t *actor)
{
    (void)actor; /* replace with one tested source behavior */
}

static void torch_destroy(actor_t *actor)
{
    (void)actor; /* unregister any collision/resources this instance owns */
}

/* Replace TORCH_PROJECT_ID with a checked, non-conflicting project actor ID.
 * This placeholder intentionally will not compile until you choose the ID. */
const actor_profile_t deku_torch_profile = {
    .id = TORCH_PROJECT_ID,
    .category = ACTORCAT_PROP,
    .flags = 0,
    .init = torch_init,
    .update = torch_update,
    .draw = 0, /* separate renderer may draw this actor type */
    .destroy = torch_destroy
};
```

`actor_t *actor` means a pointer to one live instance. `actor->data[0]` accesses
that instance's first state word. `static` on a function keeps it private to
this C file. The `extern` declaration lets another C file reference the profile.
The header guard prevents repeated declarations when several includes reach it.

The pool has eight `data[]` words per actor. Do not enlarge it casually: it
changes every actor slot and its cart allocation. Keep persistent references as
`actor_handle_t`, resolved with `actor_resolve`, not stale pointers after unload.

Choose one update owner: actor profile callback **or** the existing central
type-specific step loop. Do not call the same update through both paths. The
same rule applies to drawing and destruction. Count actual game update ticks
before converting N64 timers; rendering FPS is not a gameplay clock.

## Wiring a file into the game

Creating `foo.c` is not enough:

1. Add a runtime C file to `SRCS` in `game/makefile`. Do not add `.h` files there.
2. Include its header where the API is used. Avoid circular headers; expose only
   the data the caller needs.
3. If new assets are needed, integrate the exporter in `game/build.sh` before
   the loader's files are packaged. Define loader validation and cleanup too.
4. Spawn from the correct scene/room/layer list, using original placement and
   params. Handle `actor_spawn()` returning null; the pool is finite.
5. Register collision, attention and persistence with existing systems as needed.
   A render mesh is not automatically solid, targetable or saved.
6. Wire scene/room unload to cleanup. Do not keep a torch collider after leaving.
7. Add behavior tests, then check real Saturn build budgets and play the case.

For host-test boilerplate, read `game/tests/test_player_lift.py`: it builds C
into a temporary DLL with host GCC, then Python calls it with `ctypes`. Start
with the smallest behavior that needs no Jo/SGL headers. Stub unrelated services,
but do not stub the very behavior the test claims to validate.

For geometry/export tests, read `test_world_prop_assets.py` and
`test_room_scene.py`. Temporary outputs keep tests from overwriting the mounted
disc. Match our existing test pattern instead of setting up a new framework.

## Your next concrete task

Today: run the inventory from the solo guide. Then locate **one actual room-0
actor**, map its ID through `actor_table.h`, and fill its source behavior table.
No new runtime file until you can explain what Init, Update, Draw and Destroy
must do for that actor's placed parameters. This is how you avoid writing
boilerplate that builds but implements the wrong thing.
