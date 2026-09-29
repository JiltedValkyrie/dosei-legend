# Dosei Legend — public demo plan: Kokiri Forest → Deku Tree → Hyrule Field

Status: approved by the human 2026-09-25. **Current work plan for Claude, Astra
(Codex) and the human.** Supersedes the "return to title" endpoint of
`KOKIRI_VERTICAL_SLICE_PLAN.md` and the scope of `VERTICALSLICE.md`. Keeps the
architecture, verified gate table and flag research of `OOT_PROGRESSION_PLAN.md`.

Status refresh: **2026-09-29**. Current Clean disc is
`game/build/game-clean.cue`; latest CD-handle fix BSS ends at `0x06083c30`, leaving **976 B below
SGL**. M3 code and assets are built. Human confirmed hearts, plant transparency,
carry animation and on-screen text instructions look good in Kronos. This is
partial runtime acceptance, not completion of every M3 check.
Human reports hut-exit behavior improved after the CD-handle fix and approved
committing/pushing this checkpoint. Full greeting and dungeon review remain open.

Baseline committed as `249cef5`; regression fixes remain uncommitted at this
refresh. Human authorized Claude to commit them locally and continue required
M3 work, then M4. No push authorized. BUG-035 peak measurement remains deferred
P2; outstanding death/save issues retain their existing severity.

## Co-coding rules

### M5 entry shell / human mesh handoff (2026-09-28)

Astra wired the original forest exit collision to Deku Tree room 0 and its
return exit to forest spawn 1 / room 1. Only room 0 is registered for gameplay;
dungeon transitions, actors and progression remain unfinished. Clean build
passes at `game/build/game-clean.cue`: BSS ends `0x060834b0`, **2,896 B below
SGL**, including the concurrent Saria work. Kronos entry/return is unverified.
All 12 Tree rooms plus two boss rooms are exposed to Mesh Workshop.
Explicit per-room `ROOM_IMPORTS` supports keep/transfer/flat UV modes; visual
imports leave source collision unchanged. See
[Deku Mesh Workshop instructions](DEKU_MESH_WORKSHOP.md).

- Human assigns each milestone/task an owner in the table below. An agent only
  starts a task marked with its name; unassigned → ask the human.
- One owner per file set at a time. Before editing: check branch (`dev`), log
  and working diff; leave the other agent's uncommitted work alone.
- Each checkpoint: new top entry in `game/docs/OPUS_HANDOFF.md` with what
  changed, changed files, verification (host / build / Kronos, stated
  separately), and remaining gaps. Update `VSLICEPROGRESS.md`.
- Code review does not authorize publication. No commit, merge or push until
  the human checks the changes and explicitly approves those Git actions.
- Human relays messages between agents; address handoff notes to the other agent.
- Every new actor: check real OoT drop code + spawn tables in the same task
  (Bible rule). Record gaps; never silently drop rewards.

| Milestone | Owner | Status at 2026-09-28 |
|---|---|---|
| M0 scope, face-only textures, naming, actor pool, SFX banks | Claude | Foundations implemented; review approved 09-25. Cart-table boot/camera/music verification pending after latest RAM move |
| M1 traversal | Claude; Astra water/camera work and reviews | Core through M1l implemented, with reviewed checkpoints. Water, camera and actor/dungeon integration checks remain; not blanket-complete |
| M2 combat core, hearts, death | Claude; Astra review/UI fixes | M2a-e implemented; starter route and boulder gameplay passed. Death/save regressions and runtime checks remain; not closed |
| M3 Kokiri Forest alive (NPCs, interiors, shop, chests) | Claude: remaining work; Astra: review and verified bush fix | M3a-d implementation built in Clean. Hearts, plant cutout, carry animation and instructions passed human review. Saria greeting/source-parity work and full progression/save acceptance remain open |
| M4 items, C buttons, pause subscreens | Claude: next after required M3 work; Astra: delivered UI/assignment subset | Pause pages, counts, saved assignment and preferences pulled forward. C-item HUD and stick/nut/slingshot use still pending |
| M5 Deku Tree + Gohma + Emerald | unassigned | Not started |
| M6 post-Emerald Kokiri + Lost Woods | unassigned | Not started |
| M6b grottos, gold skulltulas, scrub shops | unassigned | Not started |
| M7 Hyrule Field (explore, owl, music, ocarina free play) | unassigned | Not started |
| M8 demo polish | unassigned | Main pass not started; deferred bugs recorded |
| M9 release checks + package | unassigned | Not started |

### Active order

0. RAM relocation implemented: title paths and music triggers now load into cart;
   fresh-boot validation remains pending. Preserve allocation/budget guards.
1. **M3a implemented:** actor manifest, shared grant/charge path, save v5 nuts,
   two/three-choice messages. Three-choice runtime check remains pending.
2. **M3b built, remaining work owned by Claude:** four remaining interiors added beside the existing
   shop and Link home. Original NPC models/clips, head tracking, scene filtering
   and house/shop music integrated. Know-It-All has **three** child brothers:
   two extra type-7 records are adult variants selected by rotZ. Seventeen
   NPC placements total, including conditionally hidden house Mido/Saria.
   BUG-006 ledge-before-talk preflight fixed and host-tested. Full source
   tracking modes/torso motion, dialogue animation changes, fade/blink polish
   and Kronos acceptance remain; do not label M3b fully complete.
3. **M3c built, partially verified in Kronos:** original pots/rocks, source rock ring,
   decorative rocks/bush, gossip-stone hit reaction, readable/cuttable signs,
   placed hearts, inventory-aware random drops, five animated/persistent chests,
   and Link get-item pose. Carry uses locomotion legs with a source upper-body
   overlay. Human passed carry animation, heart orientation and plant cutout;
   full lift/put/throw, reward and chest persistence checks remain pending.
   Save v6 migrates old forest collectible bits. Exact visual/physics differences
   and acceptance cases are recorded in `M3CD_IMPLEMENTATION.md`.
4. **M3d built, full shop acceptance pending:** shop includes cursor, spin and hold
   repeat. All merchandise uses flat face colours by human directive; nut/heart
   texture scrolling was removed. Fado now has source dialogue;
   Kokiri/Saria closing flags and house Mido rules are wired. Removed automatic
   nutsball debug emitter. Saria greeting camera remains M3b work; its text closes
   the greeting flag as an explicit interim adaptation.
5. **Next (Claude):** commit verified regression fixes, finish required M3 gaps
   including Saria greeting camera/cues, and verify the fresh-file route: earn
   rupees, obtain maze sword, buy/equip shield, Mido steps aside, reload preserves
   chests and purchases. Do not stall on optional polish or deferred P2 sampling.
6. **Then M4 (Claude):** C-item HUD and stick/nut use, followed by slingshot per
   [M4 item plan](M4_ITEMS_PLAN.md). Do not mark M3 or M4 accepted prematurely.

Human wants feature progress and later batch testing. Do not wait for a new
BUG-035 heap peak reading. Actual crashes/allocation failures still require
severity-first triage; BUG-052 remains an open save/load recovery blocker.

### Latest shop checkpoint and forwarded work (2026-09-28)

Source-based EnOssan shop flow is built. Full runtime acceptance remains pending:

- Shopkeeper model, En_Tana shelves and eight En_GirlA items. Fixed-view
  counter masks sort 16 units behind their farthest pixel to cover Link's head.
  Offline check found no in-front standing points wrongly hidden; this is not
  proof of correctness during movement. Shopkeeper remains behind the counter.
- Talk switches to the shop panorama browsing camera and hides Link. Left/right
  turns 30 degrees toward shelves; directional selection follows source shelf
  layout, returning to the shopkeeper across the inner edge. Exit restores the
  fixed view. Masks apply to the shop fixed view; a source-derived counter mesh
  now supplies occlusion in browsing view. Its Kronos acceptance remains pending.
- Hello -> talk/quit -> item descriptions -> A Buy/Don't buy. B or Don't buy
  returns from the buy prompt; elsewhere B ends the exchange.
- First shield/nut/stick purchase uses get-item text with Link in the fixed
  view, then continue shopping/quit. Repeat buys use quick thanks and resume
  browsing. Insufficient funds/capacity/ownership refusals charge nothing;
  seeds/arrows refuse without bag/bow, and recovery heart refuses at full health.

Shop and forwarded status:

1. Cursor, selected-item spin and held-stick repeat are built. Merchandise is
   flat-coloured; texture scrolling is no longer a requirement. Shelves/counter
   retain original materials.
2. Navi timer branch-order and fractional reset fixes pass focused host tests.
3. Still verify both pads: shop choices, shelves, purchases/refusals, view
   restoration, counter occlusion, VRAM and frame rate.
4. The 4-pixel speaker gap is built; no separate human acceptance claimed.
5. Check/Grab/Drop/Throw action labels and the expanded HUD map reservation are
   built. Human says text instructions look good; full context/preset matrix
   remains pending.

Camera/text delivered: five houses use original panorama/overhead views;
C-Up toggles the interior view or enters outdoor first person; L toggles the
minimap. Human reports no dialogue flicker, correct dynamic labels, and good
interior C-Up behavior in the tested session. Bible now requires dynamic action
labels for all player-facing controls text, resolved before wrapping, with
retained text rows to prevent flicker. Bold names and 4-pixel outer padding are
implemented; the reduced speaker gap remains a separate visual check.
Outdoor view/exit cases, broad pad/preset coverage, three-choice lessons, and
Link drawing with/without sword and shield after the Low Work RAM move remain
pending. No frame-rate regression has been accepted for that move yet.

### Human review: passed versus pending

Latest Clean passes reported by human: **field hearts upright, plant background
transparent, carry animation looks good, text instructions look good**. The pale
plant triangle was traced to missing VDP1 cutout flags, corrected and visually
accepted. It is no longer an unidentified field-triangle blocker. Diagnostic
draw toggles remain available but are not the fix.

Verification evidence: Sonnet reports 984 host tests with the same seven existing
failures (including setup errors), 13 lift and 10 geometry tests passing; 12 HUD
tests pass after the map reservation fix. Astra ran six asset tests successfully.
Clean build passes its SGL boundary check. No blanket all-tests-green claim.

Passed in human review: BUG-016 ceiling, BUG-032 boulder movement/damage/
knockdown/escape, BUG-047 audio, cutscene Navi, pause carousel/menus, save v4,
and first-stick fanfare. These passes do not close later regressions or all
source-parity follow-ups. Boulder mesh rolling remains BUG-051 (P2).

Controller labels and item assignment also received positive human feedback.
Do not infer every preset/pad/slot/save-reload combination was tested. The
missing assignment-modifier hint was fixed afterward; its visual recheck is pending.

| Pending check / issue | Current disposition |
|---|---|
| BUG-033 longest NPC text | Open longest text; no crash or garbled text |
| Knockback with text open | Fix in code; verify hurt then open text produces no residual push |
| Labels and item assignment matrix | Every preset on both pads; assign Down/Left/Right on digital/analog, save/reload |
| BUG-048 Save No | Fixed in code; death-menu Yes/No runtime check pending |
| BUG-049 Continue sky/freeze | Resident-scene respawn/fallback changed; original cause probable, runtime check pending |
| BUG-052 Game Over save reloads into death | Open P0; fix/verify save on death then reload as living, controllable Link |
| BUG-053 corrupted pause after Continue | Live page/font reads exactly two sectors late after mounted ISO rebuild; cold-boot unchanged-image retest pending |
| BUG-043 moved cart tables | Build gap improved; fresh boot must load tables, move title camera and play title/forest/cutscene music |
| M3b interiors/NPCs/music | Enter/leave all six interiors, reload inside, talk/target from multiple angles, cross forest room banks, hear house/shop/forest transitions |
| BUG-006 climb versus talk | Host fix passes; check A while walking into a climbable ledge beside an NPC, then normal talk and open-text advance |
| BUG-035 heap peak | P2, measurement deferred to batch playtest; historical reading is not a new measurement |
| BUG-050 child death voice sounds adult | P3, deferred audio polish; cause unresolved, no death-voice-specific quality fix accepted |

Fresh batch: die in forest/house, Save Yes/No, Continue Yes/No, load a Game Over
save, both pads. **Cold boot a completed image; never rebuild its mounted ISO
or audio tracks during play.** The old running session cannot validate new
cart layouts. See [corruption evidence](CONTINUE_MENU_CORRUPTION_2026-09-27.md)
and [bug log](BUG_FEATURE_LOG.md). No blanket M2 or M4 acceptance claimed.

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

**Character rule:** face textures only, including enemy/boss eyes and mouths.
Body, clothing, equipment and hair are flat colours. Shared offline policy is
implemented in `game/tools/character_textures.py`; new imports must mark facial
materials and preserve per-vertex bone ownership. See the project Bible.

## Current standing (2026-09-28, branch `dev`, shared uncommitted work)

Implemented: title/file-select/opening flow; Link's house, three-room Kokiri
Forest and Kokiri Shop; starter sword chest, 40-rupee shield purchase, pre-sword
rupee route and equipped-both Mido gate. Shared actor/contact pools, traversal
core through water/camera, sword combos/spin/evasion, shield/recoil, attention
for NPCs/enemies, Navi hints, withered Deku Baba and stick grant, boulder damage,
hearts/hurt/death/Game Over code are present. Remaining regressions and source
approximations stay explicit in the bug log.

Pause now has full-colour VDP2 Items/Map/Quest/Equipment/System pages with
scale/slide carousel, frozen world, music ducking, item counts, equipment and
three saved C-item bindings. Save v5 adds nut ownership/ammo/upgrade and loads v2-v4 saves; older saves
receive no nuts, and pre-v4 saves receive empty C bindings.
Saved controller labels/custom jump are separate preferences; enemy-map cheat
is session-only. Live C-item icons/ammo HUD and stick/nut/slingshot use remain
M4. Current controls and options: [README](../../README.md).

Interiors and NPC models/population are integrated; their full runtime/source
acceptance remains pending. Shop flow is in code with the follow-ups above.
Still pending: broad prop/drop/chest integration; full item actions; Deku Tree,
Gohma, Lost Woods, Hyrule Field gameplay and later story cutscenes. An existing
stand-in or core module does not satisfy its full milestone acceptance.

### Current budgets and checks

- Required 4 MB cart. Sprite limit remains **2400**; do not lower without evidence.
- Latest Claude-reported shop Clean build: **9,056 B below SGL**. Earlier
  7,152/14,032/11,344 B checkpoints are superseded for the shared tree. Link
  sword/shield copies moved to Low Work RAM, saving about 16.6 KB; runtime
  equipment visibility/FPS checks remain. Standard has no new reported number.
  Build/map evidence is not a runtime peak reading.
- `MUSICTRG.BIN`: **24,444 B**, seven banks including original house/shop
  sequences; `TITLEPTH.BIN`: **5,208 B**. Music triggers moved to offset
  **0x76000**, capacity **0x6000**; fixed cart carve ends **0x7C000**.
  Title paths remain **0x6F800**; dialogue occupies **0x71000/0x5000**.
  Header/count/size guards reject stale or missing files at boot.
  Temporary boot heap buffers are freed; runtime camera/music check pending.
- Work-RAM heap remains **51,200 B**; historical peak **50,692 B** on 09-26,
  cart peak about **719 KB**. BUG-035 stays P2; no new peak reading claimed.
- VDP1 assets retain capacity guards and forest headroom policy. Sound uses
  core/area SFX banks and half-rate samples, including voices; music banks also
  use the approved reduced budget. Measure actual generated budgets per build;
  the old 104-byte sound-RAM margin is not current.
- Runtime uses integer/fixed math (SH-2 has no FPU). Keep SGL/VRAM/cart guards.
- Latest shop gameplay checks: **169 pass, 1 fail**; Navi timer baseline
  comparison pending. Earlier camera/text focused checks passed at their
  checkpoint; do not treat them as a fresh shop regression run. Claude reports
  eight pre-existing host compile failures, including title_flights, reproduced
  with/without table relocation; do not describe the entire suite as green.
- Clean is the default build; Standard only for needed developer checks,
  Hi-res on request. Latest relocation has no fresh-boot Kronos acceptance yet.

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

Module responsibilities (some already implemented; extend existing code rather
than creating duplicates; all runtime math integer):
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

## Milestone scope (acceptance targets; status and sequencing above take precedence)

Each milestone: host tests for rules, build the Clean image only for Kronos
tests (Astra 09-25; other images on request), short Kronos check of what changed (background capture only, no
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
Human update 2026-09-26: add **M2b.1 starter-equipment route** after contact/body
work, before M2c human combat testing (FEAT-001). Maze sword chest, shop shield
for 40 rupees, reachable pre-sword rupee income and Mido equipped-both gate move
forward from M3. Remove ground equipment once this works; verify fresh file and
save/reload. Maze boulder path/collision moves forward; damage complete by final
M2 acceptance. M3 extends the shared systems. See M2_COMBAT_PLAN.md M2b.1.

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
Human working without an agent: start with [M5 solo guide](M5_SOLO_GUIDE.md)
and [file/boilerplate/decomp reference](M5_CODE_AND_SOURCE_MAP.md). Read-only
inventory and room-loading research can proceed while earlier dependencies finish.

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
- Build: Clean image (`build.bat -Variant clean`), others on request; `build_sgl_area.py --verify --map`;
  `vdp1_budget.py`; `build_dialogue.py --verify`.
- Runtime: `game/run-kronos.bat` with Cartridge/Type=7; background capture
  `game/tools/capture-kronos.ps1`; state exactly what was seen vs not.
- Disassembly check changed hot paths for software-float helpers.


## Requested camera/text follow-up (2026-09-28)

Human requests C-Up outdoor first-person and source-supported alternate
interior views to replace temporary free look. Brother control lessons must
match implemented behavior and saved controller labels. Long-page text
blinking is a separate current bug; address it first. See
[implementation plan](CAMERA_TEXT_PLAN.md). Planned, not implemented/accepted.
