# Kokiri gameplay completion plan

> **Endpoint superseded 2026-09-25** by [DEMO_PLAN.md](DEMO_PLAN.md): the demo
> continues into the Deku Tree, Gohma, Lost Woods and Hyrule Field. Steps 1-5
> here remain useful detail for DEMO_PLAN M1-M3; step 6 "return to title" is void.

Status: proposed implementation sequence, 2026-09-22. No gameplay changes in
this planning task. Implement on `dev`. Latest user requirements supersede
older control mappings and the dungeon scope in OOT_PROGRESSION_PLAN.md.

## Finish line

New file -> opening -> explore Kokiri and its homes -> crawl through the maze,
avoid the boulder, open the sword chest -> earn rupees and buy/equip the Deku
Shield -> satisfy Mido -> hear the Deku Tree's request -> accept -> mouth opens
-> enter the authorized dungeon entrance -> return to title.

No dungeon, Gohma, Emerald, post-dungeon story, or forest departure in this
slice. Returning to title is a deliberate slice endpoint, not dungeon completion.
Keep source quest conditions; never grant later rewards/flags to end the demo.

## Findings checked against current code and local US 1.2 ROM/decomp

- `build_scene_table.py` currently includes only Link's house and Kokiri Forest.
  The loader/door/collision framework exists; remaining homes are not wired.
- `build_actors.py` still supplies temporary ground sword/shield pickups. Replace
  these with the real chest/shop progression, not additional free copies.
- Current targeting selects nearby NPCs with a simplified distance/angle rule.
  Old mapping uses L to target and Z to look. Manual roll/dodge and source
  traversal are not complete; landing roll alone does not satisfy the request.
- Direct `spot04_room_2` actor-list extraction from the verified ROM confirms
  **En_Goroiwa**, the rolling boulder: (-245,120,1870), params **0x0C02**.
  Sword chest **En_Box**: (-232,178,2245), params **0x04E0**. The maze's hazard
  is this boulder; do not invent a separate maze enemy. The default room list
  contains no ordinary enemy actor. Audit alternate headers before finalizing
  the complete spawn manifest.
- The default Deku clearing (`spot04_room_1`) contains **En_Karebaba** actors.
  Include these source enemies in the forest actor audit and combat work.
- Scene table confirms five additional interiors: Know-It-All Brothers
  (`kokiri_home`), Twins (`kokiri_home3`), Mido (`kokiri_home4`), Saria
  (`kokiri_home5`), and Kokiri Shop (`kokiri_shop`), alongside `link_home`.
- Mido checks **equipped** Kokiri Sword and Deku Shield. Owning them is not
  enough. Successful dialogue sets `EVENTCHKINF_04` and moves him aside.
- `Bg_Treemouth` distinguishes meeting (`EVENTCHKINF_0C`) from agreeing to
  enter (`EVENTCHKINF_05`). Its yes/no branch chooses mouth-opening versus
  ask-again cutscenes. Do not collapse these into the Mido flag.
- Shop source prices the Deku Shield at **40 rupees**. Extract the full Kokiri
  shelf and purchase checks; do not implement a shield-only placeholder menu.

Source anchors: `src/overlays/actors/ovl_player_actor/z_player.c`,
`ovl_En_Goroiwa/z_en_goroiwa.c`, `ovl_En_Karebaba/z_en_karebaba.c`,
`ovl_En_Md/z_en_md.c`, `ovl_En_Ko/z_en_ko.c`, `ovl_En_Sa/z_en_sa.c`,
`ovl_En_Ossan/z_en_ossan.c`, `ovl_En_GirlA/z_en_girla.c`,
`ovl_Bg_Treemouth/z_bg_treemouth.c` and its cutscene data,
`ovl_En_Elf/z_en_elf.c`, `src/code/z_actor.c` attention functions,
`include/tables/{scene,entrance,actor}_table.h`. Paths relative to the configured
local OoT decomp. ROM placements are extracted, not hand-authored replacements.

## 1. Record controls, moves, actors and progression before adding behavior

Create a source-backed matrix: source action/state, input, conditions,
animation, collision/root-motion owner, effects, current implementation,
missing behavior and acceptance case. Audit all child-Link actions, rather
than treating every imported clip as implemented gameplay. Mark actions
requiring unavailable later equipment/age explicitly outside this slice.

Planned Saturn mapping, following the latest request:

| Input | Behavior |
|---|---|
| D-pad / B | Move / existing walk-run toggle |
| Hold Z + D-pad | Source target-facing movement; strafe/back up even without a target |
| Z targeting | Acquire/hold/release valid target; source recenter behavior when none |
| A | Context action: talk, inspect, open, climb/crawl entry, grab; roll when appropriate |
| Z + A + direction | Source sidehop/backflip/jump-attack selection and restrictions |
| X / R | Sword attack / shield; include source attack variants and guard states |
| Y | Preserve requested manual jump extension; keep separate from N64 auto-jump |
| Hold L + D-pad | Move old Z-look function here so look remains available |
| C + D-pad / Start | Existing C-button routing / pause inventory |

The L-look reassignment is a plan choice to resolve the old Z-look conflict;
update help, mapper, tests and handoff together. N64 has no dedicated manual
jump button: preserve this existing user-requested exception without claiming
it is original behavior. Define simultaneous-input priority and consume each
press once across menus, dialogue, targeting and traversal.

Inventory moves to audit include running/turning, ledge auto-jump, falling,
landing, damage/knockback, manual roll and wall impact, target movement,
sidehop/backflip/jump slash, sword combos/thrust/spin, shield/crouch-stab,
ladder/vine climbing, ledge grab/hang/pull-up/drop, crawl entry/travel/reverse/
exit, pushing/pulling and lifting/carrying/throwing where reachable, shallow
water/swimming/diving where supported by the forest, talk/read/open chest/
door, and use/aim of available child items. Audit unavailable-item actions too,
but do not add adult or dungeon equipment just to demonstrate them.

Acceptance: every action has a disposition and source reference; no silent
"pending input" for a move/item reachable before entering the Deku Tree.

## 2. Complete collision-driven movement and camera

Preserve original surface flags, crawl entrance/exit walls, climb types and
source path data in extraction. Use the existing indexed collision queries;
do not identify ladders/crawl holes through guessed coordinate boxes.

Implement mutually exclusive movement states, source transition conditions,
integer physics and animation/root-motion ownership. Port roll/dodge and
target movement, then climbing/ledge states, then crawl alignment and travel.
Use `Player_TryEnteringCrawlspace` / `Player_TryLeavingCrawlspace` and the
surrounding player actions as crawl references. Camera follows each state,
clears walls, and restores cleanly after exits or interruptions.

Acceptance: Link's ladder works both ways; valid ledges/climb surfaces work;
maze crawlspace works forward and backward; standing cannot bypass its low
opening; interrupted moves cannot leave Link stuck or double-apply root travel.
Test roll, sidehop and backflip with/without a target and near walls/ledges.

## 3. Stream all Kokiri interiors and flat-shaded NPCs

Extend scene/save identities, entrances, spawns, collision, room shapes,
camera data and source actor manifests for all six homes/shop including Link's.
Use each source room's actual presentation: prerendered image where specified,
mesh where specified. Preserve exit destinations/facing and door re-arm logic.
Separate scene identities from temporary cutscene render-bank numbers; current
single-digit asset naming/bank limits must be checked before adding scenes.

Load all applicable Kokiri NPCs, including distinct interior occupants and
shopkeeper, from their source spawn params and story/time conditions. Use
untextured flat-colour polygons with original silhouettes, animation and bone
ownership. No NPC texture/CLUT allocations; Navi effects and existing scenery
remain separate. Retain source interaction focus points and collision.

Acceptance: each door round-trips to its proper exterior spawn; no immediate
door bounce, stale forest actors, lost collision index, or duplicate residents.
NPCs animate without seams and add **zero texture bytes** to VDP1 usage.

## 4. Wire dialogue, items, shops, hazard and enemy behavior

Replace temporary sword/shield pickups. Implement source sword chest opening,
get-item handoff, chest flag and reload behavior. Import the boulder's authored
path, loop/direction/speed and collision/damage/knockback; do not make it a
killable enemy with invented drops. Audit the clearing's En_Karebaba behavior,
combat reactions, rewards and respawn conditions from source.

Wire every applicable resident/sign/tutorial branch to save state. Preserve
choices, repeat lines, event writes and item handoffs. Implement the full
Kokiri shop shelf: browsing, descriptions, yes/no, affordability, capacity,
ownership/equipment/bottle prerequisites, rupee deduction and successful item
grant. Failed/cancelled purchases must change nothing. Provide equip UI and
usable behavior for items obtainable in this slice.

Implement original chest/collectible/grass/rock/pot rewards and pickup effects
where those actors occur. Follow random/FLEXIBLE drop tables and conditions,
including hearts, ammo or no-drop branches. An unsupported reward is an explicit
gap, never silently replaced by rupees. Add/save only source persistent flags;
keep temporary room flags and actor respawns separate.

Acceptance: fresh save can earn enough rupees, retrieve sword and buy shield
without debug grants; purchases and chest rewards cannot duplicate on reload;
insufficient funds/capacity and repeat dialogue take their correct branches.

## 5. Navi attention and target selection

Build one actor-focus/attention registry shared by player targeting and Navi.
Derive eligible actors/POIs, categories, ranges, visibility, focus points,
priority and hint eligibility from source attention/En_Elf/scene hint actors.
Navi may draw attention without forcing Link into lock-on. Implement fly-to/
hover/return, category cues, applicable sound and player-requested hint text;
preserve source forced hints only where scripts require them. Prevent repeated
alert spam and discard targets on unload, occlusion or invalid story state.

Acceptance: source POIs attract Navi, player can respond, target selection is
stable, and switching rooms or opening dialogue never leaves a stale pointer.

## 6. Enforce the complete Deku Tree gate and slice endpoint

Implement source order: Mido equipment check and completed success dialogue ->
Mido steps aside -> Deku meeting cutscene/dialogue -> decline/ask again or yes
-> mouth-opening cue/collision -> authorized entrance transition.

Use source meeting, acceptance and mouth animation flags separately. Restore
their behavior on load. Gate both physical access and the transition handler;
walking/jumping/clipping onto an exit triangle must not skip dialogue or an
unfinished mouth-opening sequence. Equipment alone cannot open the mouth.
Prevent leaving the forest through other exits contrary to source progression.

At the authorized `ENTR_DEKU_TREE_0` transition, substitute return-to-title for
the dungeon load. Stop scene effects, release targets, clear transient input,
restore title music/camera/assets and the appropriate game mode. Preserve
earned source progress under existing save rules; do not set dungeon-intro,
completion or Emerald flags. Continuing and starting a new file both work.

Acceptance matrix: no gear; owned but unequipped gear; equipped gear without
Mido talk; Mido dialogue incomplete; Deku dialogue declined; accepted but mouth
still opening; authorized entry; save/reload at each persistent gate. Only the
final authorized case returns to title. No dungeon assets load.

## 7. Integrated vertical-slice validation

Use meaningful host tests for movement transitions, collision metadata,
dialogue/quest flags, purchases, drops and entrance authorization. Keep normal
and clean player builds free of diagnostic auto-confirm/frame holds. Verify
SH-2 integer-only hot paths, SGL work-RAM boundaries, cart allocations, VDP1
commands/textures and sound-bank budgets with every milestone.

Run complete fresh-save and continue-save paths in Kronos, including repeated
interior visits, crawl turns, boulder damage, shop failures, Navi attention,
Mido refusal, Deku decline/retry and return to title. Keep bottom VRAM/CPU
estimates and existing development/load diagnostics. Observe moving NPCs and
camera transitions; passing host tests alone does not establish visual parity.

Known opening crash/striped-screen report and cap/ear colour artifact remain
recorded issues, not declared fixed by this plan. Investigate if reproduced;
do not expand this task into another unproven renderer rewrite. Full opening
stability is required before declaring the finished slice ready.

Deliver each numbered implementation phase as a reviewable checkpoint with
source references, verification and remaining gaps. Do not start dungeon work.
