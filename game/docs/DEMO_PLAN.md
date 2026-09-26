# Dosei Legend — public demo plan: Kokiri Forest → Deku Tree → Hyrule Field

Status: approved by the human 2026-09-25. **Current work plan for Claude, Astra
(Codex) and the human.** Supersedes the "return to title" endpoint of
`KOKIRI_VERTICAL_SLICE_PLAN.md` and the scope of `VERTICALSLICE.md`. Keeps the
architecture, verified gate table and flag research of `OOT_PROGRESSION_PLAN.md`.

## Co-coding rules

- Human assigns each milestone/task an owner in the table below. An agent only
  starts a task marked with its name; unassigned → ask the human.
- One owner per file set at a time. Before editing: check branch (`dev`), log
  and working diff; leave the other agent's uncommitted work alone.
- Each checkpoint: new top entry in `game/docs/OPUS_HANDOFF.md` with what
  changed, changed files, verification (host / build / Kronos, stated
  separately), and remaining gaps. Update `VSLICEPROGRESS.md`.
- Code work stays an uncommitted diff until the other agent reviews it
  (Astra-review rule), unless the human says commit.
- Human relays messages between agents; address handoff notes to the other agent.
- Every new actor: check real OoT drop code + spawn tables in the same task
  (Bible rule). Record gaps; never silently drop rewards.

| Milestone | Owner | Status |
|---|---|---|
| M0 scope, face-only textures, naming, actor pool, SFX banks | Claude | code review approved 2026-09-25; uncommitted; remaining runtime checks pending |
| M1 traversal | Claude | cleared to start 2026-09-25; world-collision contract first |
| M2 combat core, hearts, death | unassigned | not started |
| M3 Kokiri Forest alive (NPCs, interiors, shop, chests) | unassigned | not started |
| M4 items, C buttons, pause subscreens | unassigned | not started |
| M5 Deku Tree + Gohma + Emerald | unassigned | not started |
| M6 post-Emerald Kokiri + Lost Woods | unassigned | not started |
| M6b grottos, gold skulltulas, scrub shops | unassigned | not started |
| M7 Hyrule Field (explore, owl, music, ocarina free play) | unassigned | not started |
| M8 demo polish | unassigned | not started |
| M9 release checks + package | unassigned | not started |

## Context

Human want downloadable demo for online testers: full N64 opening, Kokiri Forest
with all shops/homes/NPCs, all child combat + crawl/climb + dialogue, full Deku
Tree + Gohma, Kokiri Emerald, Deku Tree death, Saria bridge ocarina, then Hyrule
Field (explore + owl + music only; no field enemies/other content). Target:
emulators with 4 MB cart (Kronos/SSF/Mednafen). Real hardware not a gate.

Review corrections: `DEMO_PLAN_REVIEW.md` (Astra, 2026-09-25) applied —
child Lost Woods Mido gate was wrong; save version moved to M0; M1 collision
contract added.

Human decisions (2026-09-25): full Deku Tree + Gohma yes; emulator-only target;
all 10 Lost Woods rooms exist with source-exact access gates; include grottos, gold skulltula tokens,
Deku Scrub shops, Lost Woods owls.
Supersedes: `KOKIRI_VERTICAL_SLICE_PLAN.md` "no dungeon, return to title" endpoint
and `VERTICALSLICE.md` "no bosses/dungeons". Merges with `OOT_PROGRESSION_PLAN.md`
(approved 09-21) — keep its architecture, gate table, and verified flags.

**Character rule (human, repeated):** NO texture on any character (Link, NPCs,
enemies, boss, owl) EXCEPT face. Hair goes flat too — current code keeps reduced
hair textures (commit 8fb5b5d, `game/tools/character_textures.py`); change policy
to face-only. Eyes/mouth on enemies/Gohma count as face.

## Current standing (reviewed 2026-09-25, branch `dev`, clean)

Works: title → file select (3 slots, backup RAM, checksum) → full opening
cutscene chain (sleep/nightmare/Navi flight/wake-up) → Link's house + Kokiri
Forest (3 rooms, En_Holl streaming). Walk/run/Y-jump/fall/land/roll, single
sword swing, hold shield, Z strafe + NPC-only targeting, L look. NPC dialogue
with save-state-evaluated text rules (`build_dialogue.py`), Navi follow
(`navi.c`), grass cut (rupee-only drops), rupee pickups + HUD, pause
(sword/shield/save), save_state with OoT flag arrays (`save_state.c`),
game_mode machine incl. unused GAME_OVER, integer cutscene baker/player.

Missing (everything else): other 5 interiors, Lost Woods, Deku Tree, boss room,
Hyrule Field gameplay scene; NPC models (people are fairy markers); actor pool;
enemies; chest/pot/sign/boulder; damage/hearts/death; choice boxes; shop;
items (slingshot/nuts/sticks/ocarina); ledge/climb/crawl/push/lift/sidehop/
backflip/jump slash/combos/spin; C buttons; A-label HUD; pause subscreens;
scene-transition fades; per-area music; all story cutscenes after opening.

Hard limits that drive design:
- VDP1 VRAM 512 KB, worst forest room ~5 KB spare → character flat shading is
  mandatory, textures stream per room.
- Sound RAM 104 B spare → **SFX must become per-area banks** before any new sound.
- `.bss` gap 2–8 KB → all new runtime state goes to cart (`jo_malloc` zones).
- SGL ~2600 polys, 2048-command Kronos cap (project-local Kronos fixes it; demo
  README must tell testers which emulator/version works).
- No FPU: integer/fixed only in runtime (CLAUDE.md rule). Offline Python may float.
- Open renderer bugs: near-camera warp, floor-over-Link sort, intermittent opening
  crash. Not rewritten here; each gets a bounded "release blocker check" in M9.

## Source facts (decomp `D:/Workspace-Claude/game-decomps/n64/oot`, ntsc-1.2)

Scene data: `extracted/ntsc-1.2/assets/scenes/<cat>/<name>/` (room actor lists,
exits, spawns per alternate header; layer 0 child day, 1 child night, 4+ cutscene).

| Scene | Rooms | Notes |
|---|---|---|
| spot04 Kokiri Forest | 3 | have; add layer-aware actor lists |
| link_home | 1 | have (prerender) |
| kokiri_home / home3 / home4 / home5 | 1 each | Know-It-All, Twins, Mido (4 chests), Saria (hearts) |
| kokiri_shop | 1 | En_Ossan + En_Tana, 8 items |
| spot10 Lost Woods | 10 | **room 5 = bridge** (Saria ocarina, Demo_Sa); only En_Md is room 3 alt list = layer 2 adult day → **no child Mido gate** (review 09-25) |
| ydan Deku Tree | 12 | 4516 tris, 9 Door_Shutter, 3 En_Holl |
| ydan_boss | 2 | Boss_Goma + 8 En_Kusa |
| spot00 Hyrule Field | 1 | ~1639 tris, 1579 col polys (< 2048 cap), bounds 18k×18k |

Key exits: spot04 exit 2 → `ENTR_LOST_WOODS_9` (bridge, room 5); spot10 exit 8
→ `ENTR_HYRULE_FIELD_3`. `z_demo.c` `Cutscene_HandleConditionalTriggers`: on
LOST_WOODS_9 with `!EVENTCHKINF_C1` → give Fairy Ocarina, play
`gLostWoodsFairyOcarinaCs` → destination HYRULE_FIELD_3 → `gHyruleFieldIntroCs`
(`EVENTCHKINF_A0`). Owl `EN_OWL 0x004C` (OWL_OUTSIDE_KOKIRI) at (4284,182,7877).

Story order to implement (flags verified in OOT_PROGRESSION_PLAN gate table):
Mido refuse (0x102F) → sword chest (En_Box 0x04E0, crawl maze, En_Goroiwa) →
buy Deku Shield (40 rupees) → equip both → Mido 0x1033 sets EVENTCHKINF_04 →
Bg_Treemouth meeting (0C) → choice 0x1016 → mouth (05) → ydan intro (A8) →
dungeon → Gohma (70 start) → heart container + Door_Warp1 → Emerald →
Deku Tree death cutscene (Parts 1/7/9 in spot04; 2/3/8 hiral_demo, 4/5 spot09,
6 spot16 — flashback shots) → post-Emerald Mido (1C) → exit guard lifts →
bridge → Saria ocarina → Hyrule Field intro → owl talk → free explore.
Verify during M6: which En_Ko type guards the bridge exit pre-Emerald
(`z_en_ko.c`), and Saria bridge flag C1 behavior.

Player reference: `ovl_player_actor/z_player.c` (16218 lines). Action handler
table 4167–4311; crawl `Player_TryEnteringCrawlspace` 7607 / leaving 7737 via
wall types 5/6; climb `func_8083EC18` 7486 (wall flags 1/3); ledge probe
11235–11306 (child: <27 hop, 27–39 step100, 39–47 step150, ≥47 jump250);
hang 5727/12748; push 12611–12690 (wall type 7); lift 5613/10314; sidehop/
backflip 6366; attack table `D_80854190` 1569, combo 4452; jump slash 6311;
spin 9874/4360; crouch stab 8954; shield 9156; Z-target 3879; damage 4624/4815;
death 3630/9440; get item 5688/13865; chest 7329; doors 5370/10283; ocarina 13784.
Drops `src/code/z_en_item00.c` `sItemDropIds` 101, `Item_DropCollectibleRandom`
1274, `func_8001F404` 1164. Damage tables `z_collision_check.c` 3068.
HUD `z_parameter.c`, `z_lifemeter.c`; pause `ovl_kaleido_scope/`; game over
`z_game_over.c` + kaleido 4367–4675.

## Detailed milestone drafts and menu requirement

Human requirement (2026-09-25): all menus use VDP2, including panels, text,
icons, cursors, maps and prompts. No VDP1 menu texture allocations or sprite
commands. Budget VDP2 layers, tiles, pattern-name tables and palettes; preserve
prerender/gameplay state across opening/closing. This supersedes any draft UI
approach that spends VDP1 memory on menus.

Individual side drafts below expand this plan; they do not assign implementation
owners, advance milestones or override unresolved human scope decisions.
Current human build instruction is clean only, superseding all-three build steps
below unless changed again. Record other variants as not built.

- [M2 combat](M2_COMBAT_PLAN.md)
- [M3 Kokiri](M3_KOKIRI_PLAN.md)
- [M4 items and pause](M4_ITEMS_PLAN.md)
- [M5 Deku Tree](M5_DEKU_TREE_PLAN.md)
- [M6 Lost Woods](M6_LOST_WOODS_PLAN.md)
- [M6b side content](M6B_SIDE_CONTENT_PLAN.md)
- [M7 Hyrule Field](M7_HYRULE_FIELD_PLAN.md)
- [M8 polish](M8_POLISH_PLAN.md)
- [M9 release](M9_RELEASE_PLAN.md)

## Architecture additions (reuse existing, don't rewrite)

Reuse: `scene_flow.c` (door/exit surfaces), `kokiri_sgl.c` room streaming
(`kokiri_scene_update`, `room_load_bank`), `save_state.c`, `game_mode.c`,
`gameplay.c` host-testable rules layer + ctypes tests, `build_cutscenes.py` +
`cutscene.c` baked integer tracks, `message.c` coloured text, `build_dialogue.py`
rule extraction, `build_actor_model.py` / `flex_vertex_owners.py` (per-vertex
matrix ownership, KFR1 meshes), `cutscene_actor.c` cart-resident actor meshes,
`character_textures.py` texture policy, `vdp1_budget.py`, `build_sgl_area.py
--verify --map`, `capture-kronos.ps1`.

New modules (all integer, host-tested where logic-only):
1. `game/src/actor_sys.c/.h` — fixed pool in cart RAM, per-type
   init/update/draw/destroy table (OoT ActorProfile shape), room ownership
   (kill on room unload unless persistent), per-scene flag hooks
   (chest/switch/clear/collect), attention category + focus point.
2. `game/src/collide.c/.h` — simplified OoT CollisionCheck: cylinders + sword
   quad/capsule, AT/AC/OC channels, 32-byte DamageTable per actor, invincibility.
3. `game/src/player_*.c` — split Link state machine by source action group
   (move / traverse / combat / items / talk-get). Keep `link_anim_state.c` as
   clip selector; source handler order drives transitions.
4. `game/src/hud.c` — hearts (1/16 units), rupees, A-action label, B/C icons,
   ammo, small key count (dungeon), boss HP none (OoT has none).
5. `game/src/drop.c` — port `Item_DropCollectibleRandom` + FLEXIBLE + age/health
   adjustments, table data generated from z_en_item00.c.
6. `game/src/choice.c` in message layer — TWO_CHOICE / THREE_CHOICE, shop
   yes/no, ocarina staff later.
7. `game/src/sfx_bank.c` — per-area SFX bank swap (core bank + area bank), same
   loader discipline as `music_banks.c`.
8. Tools: parameterise `spot04` in `build_kokiri_scene.py:36`,
   `build_hybrid_scene.py:29`, `build_room_scene.py:12,69-70`, `build_actors.py:134`
   by scene+room count; keep collision `polyType` (bgCam, exit, floor, wall,
   material); actor list extraction per layer; generic NPC/enemy model importer
   (flat, face-only texture) from `build_actor_model.py`.

Runtime data per scene: `S<id>R<n>.MSH/.TEX/.COL/.ACT` + scene table (exits,
spawns, BGM, SFX bank, layer rules). Check asset naming limits for > 9 scenes /
> 9 rooms (ydan has 12, spot10 has 10) — fix naming first.

## Milestones (each = playable disc checkpoint, reviewed before next)

Each milestone: host tests for rules, build all three images (launcher
Rebuild), short Kronos check of what changed (background capture only, no
focus steal), VSLICEPROGRESS + OPUS_HANDOFF updated, left uncommitted for
Astra review. Check drop code for every new actor in same task (Bible rule).

### M0 — scope, policy, foundations (small)
- Rewrite `VERTICALSLICE.md` to this scope; mark KOKIRI_VERTICAL_SLICE_PLAN
  endpoint superseded; CLAUDE.md next-task pointer → this plan (copy into
  `game/docs/DEMO_PLAN.md`). Done 2026-09-25 with this document.
- Texture policy face-only: flatten hair in `character_textures.py`, rebuild
  Link, verify VRAM freed.
- Asset naming for ≥10 scenes/rooms; scene id table grows past 6
  (`save_state` per-scene flag array size).
- Actor pool + collide module skeleton with host tests.
- SFX bank split: core (Link, UI, rupee, sword) resident; area banks swap on
  scene load. Measure bytes; free room for Navi dash, enemies, chest, door.

### M1 — traversal (Link moves like OoT)
Prerequisites (review 09-25): world-collision contract first — queries return
hit polygon, surface bits and owner (static vs dynamic bgId) for floor/wall/
ceiling + clearance probes; DynaPoly-style moving/removable collision owned by
actors (push block `Obj_Oshihiki` registers DynaPoly) with one small
representative actor; export+query water boxes (CollisionHeader waterBoxes),
not floor types. Port `z_bgcheck.c` wall type → flag mapping (types 2/3/4 ≠
WALL_FLAG_1/2/3; `func_8083EC18` also checks flag 2). Ledge thresholds pick a
category only; keep source rejects (<18, ceiling, obstructed top, normal, wall
flags) and handler timing. Physics feet separate from floor+90 camera anchor;
convert 20 Hz source timing to 30 Hz, no double root motion. Use symbols, not
line numbers. Fall damage/drown/lift/ydan cases: bring minimal hooks/fixtures
forward or mark pending until M2/M3/M5 — never mark M1 done from forest-only
tests. Liftables need source drops same task.
Order: collision metadata (wall types, floor types, bgCam) → ledge hop/step-up
by source heights → ledge grab/hang/pull-up/drop → ladder/vine climb (Link's
house ladder, Deku Tree vines/web walls) → crawlspace enter/travel/reverse/exit
(sword maze) → turn-in-place, roll wall bonk → push/pull block (wall type 7,
needed ydan room 5) → lift/carry/throw (bushes, pots, rocks) → slide on slope,
fall damage table `D_80854600` → shallow water wade + swim/dive (ydan room 0
basement water; drown respawn) → camera modes per state (crawl SUBJ4, climb
Jump2, hang Unique1).
Accept: every traversal case in Kokiri + ydan geometry works forward/back;
no stuck states; standing can't bypass crawl hole.

### M2 — combat core
Sword: slash variants + combo table, thrust, jump slash (Z+A), spin (hold X
charge + release, no magic spin), crouch stab, wall rebound. Shield: guard,
deflect (Deku nut/seed reflect), recoil. Z-targeting: shared attention registry
(enemies, NPCs, signs, POIs) used by Link + Navi; sidehop/backflip; enemy lock
camera (Battle1 simplified). Damage to Link: hurt/knockdown, invincibility
frames, hearts HUD, death anim, Game Over → save prompt → continue (dungeon
entrances remap to dungeon start). Fairy-in-bottle revive not needed (no bottle
pre-Hyrule) — record as N/A.
Accept: test dummy (Karebaba first) takes source damage, Link takes and dies,
continue respawns correctly, save after game over works.

### M3 — Kokiri Forest fully alive
- NPC models: En_Ko (all types incl. Fado), En_Md, En_Sa, Know-It-All, twins,
  shopkeeper, from ROM, flat + face texture, skeleton anims (idle/walk/talk),
  source paths (En_Ko type 3 path 0), look-at-Link head turn.
- All five interiors wired with exits/spawns/prerender or mesh per source; door
  open anim + fade transitions; Link's house ladder + cow + pot.
- Objects: En_Kanban signs (read + cuttable pieces), Obj_Tsubo pots, En_Ishi
  rocks, En_Kusa full drops (hearts/seeds/nuts via FLEXIBLE), Obj_Mure2 rings,
  En_Wonder_Item hidden rupees, En_Item00 placed hearts/rupees, Obj_Hana
  (decor), gossip stone (En_Gs: talk w/o Mask of Truth = hit reaction only),
  Door_Ana grotto entry (interiors in M6b). Butterflies/fish optional decor.
- En_Box chests (sword chest, Mido's 4 chests) with open anim, get-item
  sequence (`link_demo_get_itemA`), GI text, chest flags persistent.
- En_Goroiwa boulder: path, speed, damage/knockback.
- En_Karebaba withered babas (room 1): combat, drops per source (sticks/nuts).
- Kokiri shop: En_Ossan + En_GirlA full 8-slot shelf, browse camera
  (PIVOT_SHOP_BROWSING), descriptions, yes/no, price/capacity/age checks,
  arrows show "can't buy" per source. Remove temporary ground sword/shield.
- Dialogue: all Kokiri text trees extracted (En_Ko 11 types, Md, Sa, Ossan,
  signs, Know-It-All) with flag writes; choice boxes. Navi C-up hints
  (Elf_Msg volumes optional), "Hey! Listen" prompt + sound.
- Kokiri music indoors per source (house/shop sequences), Saria greeting cs.
Accept: fresh file earns rupees, gets sword via maze, buys shield, equips, Mido
steps aside; no debug grants; reload keeps chests/purchases.

### M4 — items and C buttons
C+D-pad item use, pause Items subscreen (assign to C), Deku Stick (swing, burn
from torch, break), Deku Nut (flash stun), Slingshot (first-person aim with
D-pad, seeds ammo, hits eye switches/Skulltula), Fairy Ocarina free play later
(M7). Ammo HUD, capacity, drop tables adjust to owned items (func_8001F404).
Pause: Items / Equipment / Quest Status (Emerald, hearts pieces) / Map
(dungeon map + compass from ydan chests; world map optional static image).
Keep it OoT layout, 2D not rotating cube (Saturn cost) — say so in README.

### M5 — Great Deku Tree dungeon + Gohma
- Bg_Treemouth meeting/choice/mouth-opening/ask-again cutscenes; ydan intro cs.
- Import ydan 12 rooms + ydan_boss 2 rooms with streaming, Door_Shutter (+
  lock-on-clear), En_Holl, dungeon music (seq 24), boss music (27), clear (33).
- Actors: Bg_Ydan_Sp webs (burn with stick, jump-break floor web), Bg_Ydan_Maruta
  rotating log, Bg_Ydan_Hasi bridges/platforms, Obj_Lift, Obj_Oshihiki push
  block + Obj_Makeoshihiki, Obj_Switch floor/eye, Obj_Syokudai torches (light
  stick), Bg_Breakwall (nut? — check source), Deku Babas En_Dekubaba, Karebaba,
  Skulltula En_St, Skullwalltula En_Sw (gold → token counter only), baby Gohma
  En_Goma larva+egg, Deku Scrubs En_Hintnuts 2-3-1 puzzle + En_Nutsball
  (deflect), Keese if present, Map/Compass/Slingshot chests, Elf_Msg Navi hints.
- Boss_Goma (2174 lines): ceiling crawl, eye stun by slingshot/nut, egg drop,
  larva spawn, damage, death sequence, heart container (Item_B_Heart),
  Door_Warp1 blue warp → Emerald get → leave.
- Deku Tree death + Emerald cutscene chain; flashback shots use flat-shaded
  banks like the dream Hyrule Field precedent (`build_cutscene_scene.py`).
Accept: full dungeon clear from fresh file, no debug; save/continue inside
dungeon returns to dungeon entrance; boss beatable with source weakness.

### M6 — post-Emerald Kokiri + Lost Woods bridge
- Post-Emerald text trees (EVENTCHKINF_09/1C), Mido walk-and-leave, bridge exit
  guard lifts per source.
- Human: all 10 Lost Woods rooms EXIST, but reachability is 1:1 with game code
  at this story point — no invented walls or open paths. Whatever source gates
  (wrong-way loop exits, bomb rocks, Saria's Song checks, child/day layer)
  block, stays blocked the same way; whatever source
  lets a post-Emerald child reach, is reachable. Import geometry + source actors:
  En_Kusa, En_Okuta, En_Shopnuts business scrubs (sell per source table),
  En_Skj Skull Kid (talk; Saria's Song branches closed), En_Dnt_Nomal target
  game (needs slingshot — child OK), owls room 2/8 (En_Owl talk + fly), Lost
  Woods wrong-way loop-back exits per source. **No child Mido meadow block**:
  child-day layer has no En_Md in spot10 (review 09-25). Obj_Bombiwa rocks
  stay (no bombs pre-Hyrule, source-correct). Sacred Forest Meadow: source
  leaves it reachable for child → **open human scope decision** (acknowledged
  demo boundary vs add meadow). Do not invent a Mido gate.
- Saria bridge cutscene (Demo_Sa, gLostWoodsFairyOcarinaCs), Fairy Ocarina GI.

### M6b — side content (human: include all)
- Grottos (`kakusiana`, Door_Ana): Kokiri Forest grotto + Lost Woods grottos
  reachable without bombs/songs (check Door_Ana params → grotto type; bomb-rock
  grottos stay closed). Chest grotto, scrub grotto, gossip stone per source.
- Gold Skulltulas (En_Sw gold): kill, token En_Si pickup, count in Quest
  Status. Kokiri (night-only ones → record N/A: no night), Deku Tree ones.
- Deku Scrub shops (Lost Woods En_Shopnuts / En_Dns): prices, yes/no, items
  (nuts/sticks/seeds/capacity upgrades per source).
- Lost Woods owls (covered in M6).

### M7 — Hyrule Field (explore only)
- Import spot00 (1 room, 1579 col polys): aggressive distance culling / LOD
  (flat far triangles like forest-bank fog rule), texture streaming by zone or
  flat-shade distant; measure first.
- gHyruleFieldIntroCs, EN_OWL 0x004C talk (0x2064+ text, yes/no repeat),
  owl flies away; other 3 owls: static talk or omitted (record).
- Hyrule Field day music + child day only (no day/night cycle — record;
  Stalchild/Peahat omitted per human scope). Ocarina free play (6 notes,
  staff UI, sound) since Link now has it; no songs yet.
- Exits other than back to Lost Woods: blocked with "demo ends here" boundary
  message (only invented gate in the demo — say so in README); drawbridge
  static. General rule everywhere else: access = source code, 1:1.
- Demo end card / credits screen reachable (optional).

### M8 — demo polish required for testers
- Transitions: fades on all doors/scene loads, loading icon.
- Audio: all area music, per-area SFX coverage checklist (enemy, chest, door,
  item get fanfare, heart get, damage, low-health beep, game over).
- Title screen "DEMO vX.Y" + build hash; pause controls help page for Saturn
  pad; README-DEMO (emulator versions, 4 MB cart setup, controls, known issues,
  bug report template, how to send save file/screenshot).
- Crash handler: on exception show PC/PR/build hash on screen (existing
  DEBUGGING notes) so testers can report.
- Save versioning: done in M0 with the scene-count change (v2); bump again on
  any later layout change, reject old saves cleanly.
- Clean player image only (no diagnostics).

### M9 — release checks (bounded)
- Full fresh-file playthrough title → owl in Kronos; continue-save path; game
  over path in forest and dungeon.
- One bounded check each on known renderer bugs (warp, floor-over-Link,
  opening crash). Fix only if blocker for playability; else list in known issues.
- Second emulator smoke test (SSF or Mednafen w/ 4 MB cart) — boot, play 5 min.
- Build gates green: VDP1 budget, SGL boundary, no software-float in hot paths
  (disassembly grep), cart allocations inside zones.
- Package: ISO/CUE + README zip.

## Size estimate (rough, for pacing)

Biggest: M1 traversal, M2 combat, M5 dungeon+Gohma (≈ half total). Many actors
(~60 types). Do per-actor tasks as small reviewable units: import model → port
state machine → drops → host test → Kronos check.

## Risks

- VRAM: dungeon/field textures + actor faces; mitigate flat actors, per-room
  texture banks, fog-flat distance.
- Poly cap / FPS with enemies in view: actor LOD (skip far anims), cull.
- Sound RAM: bank split in M0 is prerequisite, else no new SFX.
- Hyrule Field scale: largest single room; may need offline partition into
  pseudo-rooms for streaming.
- Emulator compatibility: project-local Kronos fix for 2048-command cap — testers
  on stock emulators may hit it; reduce command count or document.
- Scope creep: day/night cycle, field enemies, Sacred Forest Meadow, anything
  past Hyrule Field — record as out of scope, don't build.

## Verification (every milestone)

- Host: `python -m unittest` in `game/tests` (existing harness pattern
  `test_gameplay.py`); add full-story host test Kokiri→Emerald→Field on
  save_state rules.
- Build: launcher Rebuild (all three images); `build_sgl_area.py --verify --map`;
  `vdp1_budget.py`; `build_dialogue.py --verify`.
- Runtime: `game/run-kronos.bat` with Cartridge/Type=7; background capture
  `game/tools/capture-kronos.ps1`; state exactly what was seen vs not.
- Disassembly check changed hot paths for software-float helpers.
