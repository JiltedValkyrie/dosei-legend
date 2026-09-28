# M6b draft: grottos, gold tokens and Deku Scrub shops

Astra side draft, 2026-09-25. Expands DEMO_PLAN M6b after reviewed M6.

## Playable result and scope

Source-accessible Kokiri/Lost Woods grottos work with correct interior contents
and return locations. Gold Skulltulas can yield persistent, once-only tokens shown
in Quest Status. Reachable business scrubs sell their source goods/upgrades with
correct transaction checks. Lost Woods owls remain owned by M6.

Scope is reachable child-day content with the demo's actual capabilities. No bombs,
new songs or night cycle are granted to open otherwise inaccessible content.
Record excluded night-only or capability-gated cases individually, with source
reason. Human's "include all" means all agreed reachable content, not every actor
from every layer. Sacred Forest Meadow expansion, if chosen, requires its own
explicit scope ledger rather than silently changing this milestone.

## Dependencies and data contracts

Reuse M3 shop/choice/get-item/drop systems, M4 inventory/quest display and capacities,
M5 dungeon gold-enemy integration, M6 room/entrance graph, and M1 traversal/collision.
Gold behavior first needed in M5 should already have a common actor/token contract;
finish and audit it here instead of forking it. M6 business scrubs expose placements
and IDs; this milestone owns complete sales and reachable grotto interiors.

Grotto destination data must retain parent scene, entry identity and return spawn.
Many holes can share an interior template; scene ID alone cannot distinguish all
persistent rewards or return routes. Trace source params/flags and design stable
serialization before assigning project IDs. Save version/size/buffers update as
one change if token or grotto identity fields extend persistent state.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Source | Required evidence |
|---|---|
| Door_Ana, parent scene actor params and kakusiana headers | Hole opening condition, destination template/content, return identity |
| Obj_Bombiwa and other actual blockers | Equipment/condition gate; do not infer from visual appearance |
| En_Sw and En_Si | Gold variant params, kill/token separation, token flag and pickup |
| Skulltula flag helpers/save context and quest UI | Unique bit mapping, persistent count and completion display |
| En_Shopnuts, En_Dns and related transaction code | Defeat/surrender, price/item table, repeat sale/capacity upgrade behavior |
| Grotto actor lists and individual drop code | Chest/placed/random rewards, fish/stone/scrub behavior where relevant |

Do not assume every visible gold enemy is obtainable without Boomerang/Hookshot.
For each token, verify spawn conditions and whether the actual player can collect
it with available movement/items. Do not widen pickup radius or add magnetic
collection to make inaccessible tokens count as supported.

## Delivery checkpoints

### M6b-a: reachable-content manifest

Enumerate every candidate hole, gold actor and scrub in Kokiri, Lost Woods and
Deku Tree; record layer, params, requirements, reward, flag identity and planned
acceptance route. Classify reachable now, source-blocked, night-only or requiring
a pending scope decision. Every exclusion needs evidence and a test/inspection.

Define persistent token bits/count, scrub upgrade/purchase state and grotto reward
identity using source ownership. Count is derived or updated atomically with the
unique flag so repeated callbacks cannot create extra tokens.

Review: manifest, persistence schema, capacity checks, M5/M6 integration ownership
and measured resource allowance for interiors and new faces/audio.

### M6b-b: grotto routing and contents

Load the source-selected grotto template/population, with correct entrances,
camera/water/music and return route. Shared template geometry may be reused, but
chest flags and content selection follow each hole's identity.

Bring props/rewards through M3 systems, not duplicate implementations. Trigger entry
only under source conditions and coordinate transition ownership with M1 movement.
Preserve parent return context through death/save/reload according to the source
resume policy; do not serialize an unsafe arbitrary last position.

Review: enter/exit each reachable hole, two holes sharing one template, repeated
visits, collected chests, room churn, interrupted entry and valid resume destination.

### M6b-c: gold enemies and token grant

Finish En_Sw gold variants and En_Si token behavior with source damage/collection
rules. Killing an enemy, spawning its token and permanently collecting it are
separate states. Unload/death before pickup must use source respawn semantics;
a collected token must never return after save/reload.

Integrate count and quest screen using VDP2. Confirm source audio/text/grant and
cancel/timeout behavior where applicable; do not substitute an ordinary rupee drop.
Use the already reviewed dungeon actor path rather than another copy of En_Sw.

Review: each reachable token, duplicate collision/grant prevention, leave-before-
pickup, save/reload, count/bit agreement and maximum index serialization.

### M6b-d: business scrubs

Connect encounter/deflection/surrender to source sale dialogue. Reuse one purchase
transaction: availability, price, capacity, grant, money debit and permanent flags.
Distinguish ordinary repeat stock from once-only upgrades based on actor params.

Support nuts/sticks/seeds and actual capacity upgrades in the reachable manifests.
Full-wallet/full-ammo/exact-price/insufficient-funds paths and decline leave state
correct. UI/text/choices/cursors use VDP2; the world scrub remains a world actor.

Review: encounter -> purchase -> leave/revisit -> save/reload, no charge without
grant, repeated A while rendering slowly, duplicate upgrades and correct no-sale
responses. Unsupported rewards cannot be quietly replaced by another item.

## Acceptance and later obligations

- Every reachable manifest entry completed with runtime evidence; every excluded
  one has a source gate/time/capability reason, not an implementation convenience.
- Shared grotto templates never share unrelated chest/token flags or return spawns.
- All obtainable dungeon tokens close M5 deferred cases. Night-only overworld cases
  stay explicitly N/A while day-only scope remains in effect.
- Scrub prices/rewards/capacities and persistent upgrades match extracted data.
- M7 does not add Field grottos/enemies: Field remains explore-only unless human
  changes scope. Document that boundary, do not expand this milestone implicitly.

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
