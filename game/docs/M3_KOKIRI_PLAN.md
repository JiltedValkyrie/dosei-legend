# M3 draft: Kokiri Forest fully alive

Astra side draft, 2026-09-25. Expands DEMO_PLAN M3 after M2; see
[M2_COMBAT_PLAN.md](M2_COMBAT_PLAN.md) for combat and reward foundations.

## Playable result and scope

Human update (2026-09-26): M2b.1 now owns the first sword-maze chest, 40-rupee
shop shield purchase, pre-sword rupee route, Mido equipped-both gate and removal
of ground-equipment shortcuts (FEAT-001). Maze boulder moves forward too, with
damage complete by M2 acceptance. M3c/M3d below extend these shared systems;
do not defer this starter route to M3 or implement it twice. Full stock,
remaining chests/props/NPCs and shop presentation remain M3.

A fresh file earns rupees, crawls the maze, obtains the Kokiri Sword from its
chest, buys/equips a Deku Shield, and earns passage past Mido. All five additional
Kokiri interiors, NPC conversations, shop shelves, source props and local rewards
work and survive reload. Temporary ground sword/shield grants are removed only
when their real acquisition paths work end to end.

M3 does not implement the Deku Tree dungeon or repeat M2 combat. Import the actual
child-layer populations, not every actor type named in a planning list. Optional
butterfly/fish decoration must not displace required NPCs, props or rewards.

## Dependencies and ownership boundaries

| Required foundation | M3 responsibility |
|---|---|
| M1 crawl, climb, carrying, dynamic collision | Validate maze/boulder/ladder/props in real Kokiri geometry |
| M2 live pool, attention, damage and Karebaba | Integrate source placements; do not implement a second enemy or target registry |
| M2 minimal item grant and save extension, if added | Extend one shared ownership/capacity/grant API for shop/chests/drops |
| Existing message extraction and save flags | Choice boxes, full NPC branch effects and once-only rewards |
| Existing room/audio streaming | Correct interior spawn, bank, camera and return route |

Shop purchases and random drops need nut/stick capacities before M4 item use.
Bring their minimal persistent representation/grant checks forward if M2 did not;
do not sell items into nonexistent inventory or silently substitute rupees.
M6b owns grotto interiors. A Door_Ana cannot lead into unloaded content: keep that
acceptance pending until M6b; no invented permanent closure of a source-open hole.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Research target | Evidence to record before port |
|---|---|
| spot04 and Kokiri interior scene/room headers | Child-day actor params, paths, alternate headers, entrances/exits and chest flags |
| En_Ko, En_Md, En_Sa actor sources | Type-specific text, paths, visibility, head tracking, flag writes and Mido equipment gate |
| En_Ossan, En_GirlA, En_Tana | Actual eight-slot shelf, descriptions, price, availability/capacity/age checks and purchase completion |
| En_Box and player get-item handlers | Chest content decoding, flag timing, animation, GI text and interruption behavior |
| En_Kanban, Obj_Tsubo, En_Ishi, En_Kusa, Obj_Mure2 | Cut/break/lift rules, spawn/drop params, pieces and persistence |
| En_Wonder_Item, En_Item00, Obj_Hana, En_Gs, En_Cow | Hidden/placed rewards, decoration, gossip-stone interactions and reachable cow behavior |
| En_Goroiwa; M2 En_Karebaba | Path/collision/damage and existing enemy/reward integration |
| z_en_item00.c / shared get-item code | Random/FLEXIBLE table, ownership/health adjustments, pickup and capacity rules |

Do not inherit the umbrella plan's generic "sticks/nuts" label for Karebaba.
The M2 audit found its dead-item state offers GI_DEKU_STICKS_1; inspect each actor's
actual path. No bottle/song grants for the cow beyond reachable source behavior.

## Delivery checkpoints

### M3a: population, inventory and dialogue contracts

Export a per-scene/layer/room manifest with actor ID, params, position, path,
object bank and persistent flags. List unsupported records explicitly. Allocate
actor/model/face/audio budgets for the worst simultaneous population. Define one
transaction for validate -> presentation -> grant/charge -> persistent flag,
with source-appropriate ordering and cancellation. A repeated update must not
repeat a purchase, grant or flag write.

Add TWO_CHOICE/THREE_CHOICE and branch effects to the message layer. D-pad owns
choices on both controllers; stick movement/C items must not leak. Test rejected,
repeated and cancelled conversations before adding all NPCs.

Review: manifest, shared transaction/save schema and source text/flag fixtures.
Any save layout change bumps version and all packing/device buffers together.

### M3b: NPCs and interiors

Import ROM skeletons/animations using per-vertex matrix ownership and face-only
textures. Replace fairy stand-ins with actual NPCs while retaining shared Navi
attention identity. Port type-specific paths, talk focus and head turns.

Wire the five new interiors plus existing Link home to their actual entrances,
return spawns and cameras. Preserve prerender alignment where the source uses it;
no substitute orbit camera. Integrate doors/fades and house/shop music now; M8
will audit coverage rather than invent these fundamentals later.

Review: enter/leave every house/shop, reload inside, talk from multiple angles,
check room unload and pool/model-bank lifetime. M1 validates the house ladder.

### M3c: maze, props, drops and chests

Finish sword-maze crawl/boulder interaction, source sword chest and Mido's chests.
Implement get-item presentation and persistent chest flags; saving/reloading
cannot duplicate content. Port liftable/cuttable props and their exact drop paths,
including no-drop conditions, heart/ammo ownership adjustments and pickup limits.

M2 owns Karebaba behavior; extend placement/asset integration here. Use source
collision for boulder damage and M1 carrying physics for thrown props. Cut signs
retain the appropriate text/pieces behavior. Hidden/placed items need their own
source persistence rules rather than the grass respawn policy.

Review: every introduced actor has a spawn/drop ledger and visible pickup check.

### M3d: shop and progression closure

Build the source eight-slot shop UI and browsing camera, descriptions, choices,
price/capacity/age restrictions and purchase fanfare. All shop/choice/menu panels,
text, icons and cursors use VDP2; no menu allocations in VDP1. World shop actors
remain in the existing world render path. Budget VDP2 layers/tiles/palettes and
prerendered interior coexistence before building the UI. Arrow purchase denial follows
source; owning rupees alone is insufficient. Prevent repeated charge while the
accept button is held or on slow frames. Failed/cancelled purchases preserve money.

Connect equipment checks to Mido's actual dialogue/flag sequence. Port Saria's
forest greeting where reachable, and Navi C-up hints using the shared attention/
message ownership rules. Remove debug acquisition shortcuts from the player path.

Review: fresh file -> sword -> 40-rupee shield purchase -> equip -> Mido passage,
then save/reload each checkpoint and verify exact persistent consequences.

## Acceptance and later obligations

- All source-required child-day NPCs/interiors reachable; no missing actor hidden
  by an import filter or merged alternate list.
- Shop: insufficient funds, exact funds, full capacity, unavailable gear, cancel,
  repeat and reload. Chests: first grant, opened state, interrupted presentation.
- Drops: source table/params, full health, absent ammo ownership, capped inventory,
  pickup once, room unload, collection persistence and actor pool exhaustion.
- Traversal: sword maze rejects standing bypass, boulder hurts correctly, carried
  prop cannot escape collision constraints; signs/chests remain interactable.
- Both pad layouts navigate dialogue/shop/pause without moving Link or firing C.
- Record grotto entry pending M6b and item use pending M4 by named case. Full
  dungeon gate/Tree mouth behavior belongs to M5, not an invented M3 completion.

## Review and verification rules

Planning only; no implementation owner assigned here. Start code after preceding
milestone review and human owner assignment. Recheck current source and working
diff before taking files; M1/other active work stays with its owner. Dependencies
below describe required behavior, not permission for a parallel rewrite.

At each implementation checkpoint: focused host tests in separate processes,
**clean image only** per current human instruction, SGL map boundary, worst-room
VDP1 budget, cart bounds/heap high-water and audio bank bytes. Inspect changed
runtime hot paths for software float. Do not cut the malloc arena by guesswork.
Runtime checks use the project's non-focus-stealing workflow or human play;
report observed versus pending checks separately. No build/runtime checks were
performed for this draft. Source references are implementation research targets
unless explicitly marked verified; umbrella-plan actor lists are not spawn proof.

Record changed files, source parity, approximations, save compatibility, measured
budgets and deferred acceptance in OPUS_HANDOFF and VSLICEPROGRESS when code lands.
Code stays uncommitted for review unless human requests commit. Planning does not
complete a milestone or authorize the next one. All new actors include source
spawn/drop audits in the same task; characters use flat materials except faces.

All menus must use VDP2 for text, panels, icons, maps and cursors. Budget VDP2
storage/layers and restoration explicitly; no VDP1 menu textures or commands.
