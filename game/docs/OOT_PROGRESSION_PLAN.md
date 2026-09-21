# Full OoT opening vertical slice on Saturn — game state, progression, three areas

## Context

Today `game/` is a **sandbox, not a game**. One scene (Kokiri Forest, spot04),
no quest flags, no save, no scene transitions, no health, and a single
`title_visible` boolean where a mode machine should be. `gameplay_reset()`
(`game/src/gameplay.c:34`) wipes everything on every entry to the world.

Two consequences the user already hit:

1. **NPCs speak later-quest lines.** `game/tools/build_dialogue.py:38-39` hardcodes
   `MIDO_TEXT = 0x1045` and `SARIA_TEXT = 0x1002`. Verified against the decomp:
   - `EnMd_GetTextIdKokiriForest()` (`ovl_En_Md/z_en_md.c`) returns `0x1045` only
     under `CHECK_QUEST_ITEM(QUEST_KOKIRI_EMERALD)`. The true no-flag baseline is
     **`0x102F`** — "you can't go see the Great Deku Tree without a sword and a
     shield". Mido is literally speaking end-of-dungeon text.
   - `EnSa_GetTextId()` (`ovl_En_Sa/z_en_sa.c`) baseline is **`0x1001`**; `0x1002`
     requires `INFTABLE_SARIA_GREETED_LINK`.
   - The 11 `En_Ko` child ids are **correct** — their flag-gated returns come
     first and the fall-through the tool takes is the real baseline. Don't touch.
2. **Talking changes nothing**, because there is nowhere to record that it happened.

Goal: Title → New Game/Load → Kokiri Forest → Lost Woods → Great Deku Tree →
Gohma → Kokiri Emerald, following the N64 progression, with real saves.
Gameplay correctness is the target; **performance is explicitly not a gate**.

### Decisions taken by the user

- **Areas**: Kokiri Forest (spot04), **Lost Woods (spot10)**, Great Deku Tree
  (ydan) + Gohma (ydan_boss), through to the Kokiri Emerald.
- **Save**: real Saturn backup RAM, N64-style file select.
- **Cutscenes**: full OoT cutscene playback.
- **Models**: real ROM models for all NPCs and enemies.
- **Combat**: full hearts, damage, death and Game Over.
- **The game now requires the 4 MB RAM expansion cart.**

### Scope docs that must change first

`VERTICALSLICE.md` says "No bosses, dungeons, full overworld". That is now
**superseded**. Rewrite it in step 0 so it stops contradicting the work, and note
the cart requirement in `game/README.md` and the launcher.

### Honest scale note

This is much larger than the current slice — it is the difference between a
renderer with interactions and an actual game. The plan is staged so each phase
is independently playable and testable; do not treat it as one delivery.

## What the 4 MB cart does and does not buy

Jo support is already compiled in (`joengine/Compiler/COMMON/jo_engine_makefile:196`
defines `JO_COMPILE_WITH_RAM_CARD_SUPPORT` unless explicitly disabled, and the
project's makefile does not disable it). Detection reads `*(char*)0x24FFFFFF`;
`0x5C` = 32 Mbit. Kronos emulates it contiguously at `0x22400000`
(`Kronos/yabause/src/sys/memory/src/cs0.c:1503`) with `Cartridge/Type = 7`.

**Jo leaves half the cart unused.** `jo_init_memory()`
(`joengine/jo_engine/core.c:173-178`) adds only `0x200000` at `0x22400000` for
`CART_32MBits`; the second 2 MB at `0x22600000` is never registered. Claim it with
one extra `jo_add_memory_zone((unsigned char *)0x22600000, 0x200000)` at startup,
after verifying the cart is present. (`JO_MALLOC_MAX_MEMORY_ZONE` is 9, so there
is room for the zone.)

| Resource | Cart helps? | Consequence |
|---|---|---|
| `jo_malloc` arena / dynamic data | **Yes**, +4 MB | Collision, room staging, actor/enemy state, flags, save buffers, cutscene tracks live here |
| `.bss` vs SGL work-area gap | **No** — `.bss` is work RAM | Measured 2026-09-21 with the backup module compiled in: **24,080 bytes gap**, `.bss` ends `0x060ac830`. Healthier than the ~6 KB the old handoff recorded, but still finite — prefer cart allocations for anything large |
| VDP1 texture VRAM | **No** — fixed 512 KB | **The binding constraint.** Spare VRAM is per resident room, and the rooms are very uneven: the roomiest reports ~173 KB spare but the tightest only **~5 KB**. Plan every new texture against the *worst* room, not the average. Textures must swap per area/room |
| SCSP sound RAM (104 B free) | **No** — fixed 512 KB | Music/SFX banks still swap per area |

The cart removes the *data* ceiling, not the *VRAM/sound* ceiling. Streaming stays
mandatory — which is fine, because it already works.

## Existing machinery to reuse (do not rewrite)

- **Room streaming + portals**: `kokiri_scene_update()` `game/src/kokiri_sgl.c:397`
  transforms Link into portal space and defers `room_load()` (`:319`) until VDP1 is
  idle (`JO_VDP1_EDSR & 2`). Scene doors are this plus a bank swap.
- **Rules layer**: `game/src/gameplay.c/.h` — platform-free integer code with a
  ctypes host harness (`game/tests/test_gameplay.py`). All progression logic goes
  here so it stays host-testable without a Saturn.
- **Collision**: `shared/lib/collision/kokiri_collision.{c,h}` is scene-agnostic;
  `collision_triangles()` (`shared/tools/build_kokiri_scene.py:291`) already accepts
  any scene blob.
- **Baked integer camera tracks**: `game/tools/build_title_paths.py` bakes
  collision-checked camera routes to integer per-frame data. **This is the
  cutscene solution** (see Phase 5).
- **Save**: `jo_backup_save()` / `jo_backup_load_file_contents()`
  (`joengine/jo_engine/jo/backup.h`), currently off (`game/makefile:9`).
- **Generated-from-ROM discipline**: every table comes from the verified ROM or
  decomp, never hand-authored. Keep this for all new data.

## Architecture

Three new platform-free modules beside `gameplay.c`, all integer-only and all
host-tested, plus generalisation of the offline tools.

### 1. `game/src/save_state.c/.h` — the missing spine

Mirror of the parts of OoT's `SaveContext` this slice needs, nothing more:

- `event_chk_inf[4]` (u16 each), `inf_table[8]`, `item_get_inf[2]`
- `equips` (sword/shield), `inventory` (deku stick/nut/slingshot), ammo
- `quest_items` (Kokiri Emerald), `rupees`, `health`, `health_capacity`
- Per-scene flags: `chest[N]`, `switch[N]`, `clear[N]`, `collect[N]` — OoT keeps
  these per scene; store an array indexed by our small scene id set
- `entrance` / `spawn` for load-game resume

Accessors named after the originals so the source trace stays obvious:
`save_get_event_chk_inf()`, `save_set_event_chk_inf()`, `save_get_inf_table()`,
`save_check_quest_item()`, etc. **Split `gameplay_reset()`** into
`save_new_game()` (persistent) and `gameplay_reset_scene()` (volatile: target,
swing, talk, pause, per-room drops). This split is the single most important
change — it is what makes progression possible at all.

Backup RAM: enable `JO_COMPILE_WITH_BACKUP_MODULE = 1`, three file slots, a
version word and a checksum so a stale or corrupt save is rejected rather than
loaded. Saturn BUP blocks are small; the struct above is well under 1 KB.

### 2. `game/src/scene_flow.c/.h` — mode and scene machine

Replaces the `title_visible` boolean (`demo.c:40`) with an explicit mode:
`TITLE → FILE_SELECT → LOADING → PLAY → PAUSE → DIALOGUE → CUTSCENE → GAME_OVER`.

Scene transition = pick destination from the collision surface's `exitIndex`,
fade out, swap banks (mesh/texture/collision/audio), place Link at the entrance
record, fade in. Driven by a generated `scene_table` (scene id → file names,
room count, entrance list, BGM id).

### 3. `game/src/actor_sys.c/.h` — actors with behaviour

Today actors are static placement rows. Needed: a small fixed-capacity actor pool
(allocated from cart RAM) with per-type update/draw, health, hitboxes, and the
OoT-accurate drop tables the project's own rule already demands
(`DOSEI-LEGEND-BIBLE.md` — check real drop code in the same task).

Types needed for the three areas: `En_Ko`, `En_Md`, `En_Sa`, `En_Kusa`, `En_Box`
(chests), `En_Item00`, `Obj_Switch`/`Bg_*` (Deku Tree switches, webs, platforms,
ladders), `En_Dekubaba`, `En_St`/`En_Sw` (Skulltula), `En_Firefly` (Keese),
`Boss_Goma`, plus `En_Holl` room transitions already extracted.

### 4. Offline tool generalisation

`spot04` is hardcoded in four places — `shared/tools/build_kokiri_scene.py:36`
(the segment filter in `extract()`), `build_hybrid_scene.py:29`,
`build_room_scene.py:12,69-70`, and `build_actors.py:134`. Parameterise all four
on a scene prefix + room count. Then per scene emit `S<id>R<n>.MSH/.TEX/.COL`.

**Collision extraction must stop discarding `polyType`.** `collision_triangles()`
returns geometry only, but the dungeon needs the surface fields. Layout from
`include/bgcheck.h:219`:

| Field | Location | Needed for |
|---|---|---|
| `bgCamIndex` | data[0] bits 0–7 | per-surface camera setting |
| `exitIndex` | data[0] bits 8–12 | **scene transitions** |
| `floorType` | data[0] bits 13–17 | void/damage floors |
| `wallType` | data[0] bits 21–25 | **climbable walls / ladders** |
| `material` | data[1] bits 0–3 | **per-surface footstep sound** (also closes the existing "one footstep material" gap) |

## Status of this document

Approved by the human on 2026-09-21. This is the current work plan for the
gameplay/progression effort and supersedes `GAMEPLAY_NEXT_STEP.md` as the
next-task pointer. Both agents (Claude and Astra/Codex) should work from it.
Nothing below has been implemented yet — Phase 0 is the starting point.

## Phases

Each phase ends playable and host-tested. Do not start the next before the
previous runs in Kronos.

**Phase 0 — scope and platform.** Rewrite `VERTICALSLICE.md` for the new scope.
Enable the backup module, claim the second cart bank, add a startup check that
refuses to run without the cart with a clear on-screen message. Set
`Cartridge/Type = 7` in the Kronos launcher so the human's normal run path works.

**Phase 1 — game state and the dialogue bug.** Add `save_state.c/.h`; split
`gameplay_reset()`. Rewrite `build_dialogue.py` to extract the **full branch tree**
of each text-id function rather than one hardcoded constant, emitting a small
condition list per conversation that the runtime evaluates against `save_state`.
This fixes Mido and Saria and makes every NPC line quest-correct for free. Extend
the `--verify` pass to re-parse and compare the whole tree, so a decomp change
still breaks the build loudly.

**Phase 2 — save and file select.** Backup RAM save/load, three slots, N64-style
file select between title and play, Game Over → save → continue.

**Phase 3 — scenes and transitions.** Generalise the extractors; add Lost Woods
(spot10, 10 rooms), the Deku Tree (ydan, 12 rooms), Gohma's room (ydan_boss) and
the shop (kokiri_shop, 1 room). Surface-driven exits, per-scene bank swap,
per-area music (sequences 24 dungeon, 27 boss, 33 boss clear; 60 kokiri already
done). Walk the whole map with nothing in it yet.

**Phase 4 — actors, combat and health.** Actor pool, real ROM models, hearts HUD,
damage/invincibility/knockback, death and Game Over. `En_Box` (the Kokiri Sword
chest, already in `spot04_room_2`), the `kokiri_shop` Deku Shield purchase, Deku
Babas, Skulltulas, Keese, the slingshot, and the OoT drop tables for each — per
the standing Bible rule, check the real drop code for every actor in the same
task that adds it.

**Phase 5 — cutscenes.** Extract the cutscene scripts from the scene binaries
(scene header command `0x17`). **Parse and bake offline in Python**: evaluate the
camera splines at build time and emit integer per-frame eye/at tracks in exactly
the form `build_title_paths.py` already produces, plus a timed event list (text,
actor cue, transition, music, destination). The Saturn runtime then needs only a
small integer interpreter — no runtime float, no runtime script parsing, no
N64 segment pointers. This is the only way full cutscene playback is affordable
on an FPU-less SH-2.

**Phase 6 — the progression itself.** Wire the opening script end to end: Navi
intro, Saria, Mido's demands, sword + shield, Deku Tree entry, the dungeon,
Gohma, the Kokiri Emerald, and the closing cutscene. Each gate reads and writes
`save_state`, so the whole chain is replayable in host tests.

## The opening gate table (verified against the decomp)

Flags are plain bit arrays — `Flags_GetEventChkInf()` (`src/code/z_actor.c:4891`)
is just `eventChkInf[flag >> 4] & (1 << (flag & 15))`. A direct, trivial port.

| Gate | Condition | Effect / flag set |
|---|---|---|
| Mido blocks the Deku Tree path | `EnMd_BlockPath` while `!EVENTCHKINF_04` in `SCENE_KOKIRI_FOREST` (`z_en_md.c:707`) | — |
| Talk to Mido, unarmed | baseline → text **`0x102F`** | on close: `EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS` (0x02) + `INFTABLE_0C` (`z_en_md.c:514-516`) |
| Talk to Mido again, unarmed | `INFTABLE_0C` set → text `0x1030` | — |
| Talk to Mido with sword **and** shield | `CUR_EQUIP_VALUE(SHIELD)==DEKU && CUR_EQUIP_VALUE(SWORD)==KOKIRI` → text `0x1033` | talk state ACTION → `SET_EVENTCHKINF(EVENTCHKINF_04)` (`z_en_md.c:777`); Mido steps aside |
| Mido after standing down | `EVENTCHKINF_04` → text `0x1034` | — |
| Mido blocks Lost Woods | `SCENE_LOST_WOODS && !EVENTCHKINF_0A` | talking sets `EVENTCHKINF_0A` |
| Saria, first talk | baseline **`0x1001`** | `INFTABLE_SARIA_GREETED_LINK` |
| Saria, after Mido refused | `EVENTCHKINF_MIDO_DENIED_DEKU_TREE_ACCESS` → `0x1031`/`0x1032` | `INFTABLE_SARIA_WAS_TOLD_ABOUT_MIDO` |
| Kokiri Emerald awarded | blue warp after Gohma: `Item_Give(play, ITEM_KOKIRI_EMERALD)` (`ovl_Door_Warp1/z_door_warp1.c:530`) | `questItems \|= QUEST_KOKIRI_EMERALD` (`z_parameter.c:1436`) |
| Deku Tree cleared | `EVENTCHKINF_09` — gates most post-dungeon NPC lines | — |
| Meet the Deku Tree | `Bg_Treemouth`: `!EVENTCHKINF_05 && !EVENTCHKINF_0C`, child, within 1658 units | sets `EVENTCHKINF_0C`, plays `gDekuTreeMeetingCs` (`z_bg_treemouth.c:152-175`) |
| Mouth opens | choice box `0x1016` answered yes | sets `EVENTCHKINF_05`, plays `gDekuTreeMouthOpeningCs` |
| Deku Tree interior intro | entering `ENTR_DEKU_TREE_0` with `!EVENTCHKINF_A8` | sets `EVENTCHKINF_A8`, plays `gDekuTreeIntroCs` (`z_demo.c:128` entrance-cutscene table) |
| Gohma fight starts | `!EVENTCHKINF_BEGAN_GOHMA_BATTLE (0x70)` | sets it; spawns `Door_Shutter` to lock the room |
| Gohma dies | — | spawns `Item_B_Heart` + `Door_Warp1`; `Flags_SetClear(room)` |
| Post-Emerald Mido | `QUEST_KOKIRI_EMERALD && !EVENTCHKINF_1C` | after his walk: sets `EVENTCHKINF_1C`, `Actor_Kill` — he leaves for good |

**Two details that change the implementation:**

- **Mido tests `CUR_EQUIP_VALUE`, not `ALL_EQUIP_VALUE`** (`save.h:476-477`) — the
  sword and shield must be *equipped*, not merely owned. The existing pause equip
  menu therefore becomes load-bearing, not decoration.
- **Mido's "four demands" are not a counter.** They are narrative text inside
  `0x102F`/`0x1030`; the actual gate is the single equipment state check that
  selects `0x1033`. Do not build a four-step counter.

Exact placements confirmed from the ROM: Kokiri Sword chest `En_Box` params
`0x04E0` (`GI_SWORD_KOKIRI`, chest flag 0) at `(-232,178,2245)` in spot04 room 2,
behind a crawlspace and an `En_Goroiwa` rolling boulder. Slingshot `En_Box`
params `0x00A1` (`GI_SLINGSHOT`, chest flag 1) in ydan room 2.

`spot04` exit list already names our whole map: `ENTR_DEKU_TREE_0`,
`ENTR_LOST_WOODS_0/9`, `ENTR_KOKIRI_SHOP_0`, `ENTR_LINKS_HOUSE_1`, and others.

New save state (`Sram_InitNewSave`, `z_sram.c:100-225`): `healthCapacity = 0x30`
(3 hearts), Kokiri tunic + boots only, `questItems = 0`.

Per-scene flags are `SavedSceneFlags` (`save.h:96-104`) — `chest`, `swch`,
`clear`, `collect` as u32 each, 0x1C bytes × 124 scenes in the original. Our
scene set is tiny, so index a small table instead of carrying 124 entries. The
`temp*` halves are deliberately not persisted; keep that split.

**Deku Tree dungeon content** (ydan, 12 rooms) is fully enumerated in the scout
report: web floors/walls (`Bg_Ydan_Sp`), the rotating log ladder
(`Bg_Ydan_Maruta`), bridges (`Bg_Ydan_Hasi`), push blocks (`Obj_Oshihiki`),
floor and eye switches (`Obj_Switch`), torches (`Obj_Syokudai`), Deku Babas,
withered Babas, Skulltulas (`En_St`/`En_Sw`), baby Gohmas (`En_Goma`), the Deku
Scrub order puzzle (`En_Hintnuts`, rooms 9/1/4), Map and Compass chests. Boss
room preloads `OBJECT_WARP1` and `OBJECT_GI_HEARTS` so Gohma can spawn the blue
warp and Heart Container on death.

Safe to stub or omit entirely: `En_River_Sound`, `Object_Kankyo`, `En_A_Obj`,
`Obj_Hana`, `Obj_Mure2`, `En_Wonder_Talk2`, `En_Wonder_Item`, `Elf_Msg`/`Elf_Msg2`
(Navi hint volumes), gold skulltulas.

Only remaining research gap: the spot10 (Lost Woods) room actor lists, which the
scout did not reach. Mido also blocks there while `!EVENTCHKINF_0A` and listens
for Saria's Song. That affects Phase 3 only.

**Verified actor placement** (dumped from the ROM room actor lists):

- `spot04_room_0` — 78 actors, including **Mido `0x016D`** and **Saria `0x0146`**.
- `spot04_room_2` — 12 actors, including **`En_Box` `0x000A`**: the **Kokiri Sword
  chest**, already inside a room the streamer loads today. No new scene needed.
- `spot04_room_1` — 9 actors; the Deku Tree side of the blocked tunnel.

**One extra scene is unavoidable**: the Deku Shield is *bought*, not found, so
Mido's second demand requires **`kokiri_shop`** (`kokiri_shop_scene` +
`kokiri_shop_room_0` — a single room, cheap) and a minimal shop/buy interaction.
Faking the shield as a ground pickup would break the N64 progression the user
asked for, so budget for the shop in Phase 4.

Still worth a confirming pass before Phase 6: the full ydan actor/room breakdown,
Gohma's own state machine, and the Deku Tree internal switch/web/ladder gates.
Phases 0–5 do not depend on that detail.

## Verification

- **Host tests first.** Progression, flags, save round-trip and dialogue
  selection are all integer rules in `gameplay.c`/`save_state.c`; drive them
  through the existing ctypes harness (`game/tests/test_gameplay.py` pattern). A
  full Kokiri → Emerald playthrough should be expressible as a host test with no
  Saturn involved.
- **Build gates stay on.** The VDP1 budget guard and the
  `build_sgl_area.py --verify --map` boundary check must keep passing; per
  `CLAUDE.md`, never disable them to get an image out.
- **Decomp verification.** `build_dialogue.py --verify` must re-parse the text-id
  functions and fail on mismatch. Do the same for any new extracted table.
- **In Kronos, per phase**, with `Cartridge/Type = 7`: confirm the actual
  behaviour changed, not just that it built. Respect the standing rule — the
  human plays other games on this machine, so use background
  `game/tools/capture-kronos.ps1`, never focus steal or global input.
- **Report honestly**: a green build is not a fixed bug, and host tests do not
  prove target behaviour. Say what was verified where.
