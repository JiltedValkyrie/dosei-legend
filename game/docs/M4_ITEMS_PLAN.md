# M4 draft: items, C buttons and pause subscreens

Astra side draft, 2026-09-25. Expands DEMO_PLAN M4 after reviewed M3.

## Playable result and scope

Assign and use Deku Sticks, Deku Nuts and Slingshot through the C interface.
Pause exposes Items, Equipment, Quest Status and dungeon Map/Compass information.
Ammo, ownership, capacities and drops agree with saved state. This is a flat 2D
OoT-style layout, not the rotating pause cube; disclose the presentation difference.
Fairy Ocarina assignment can exist when owned, but instrument play ships in M7.

C-up remains the source view/Navi context action; do not invent a fourth assignable
item slot. Verify the exact context priority before wiring the four C directions.
Digital pad uses C+D-pad for C actions, ordinary D-pad for movement/menus. 3D Pad
uses D-pad for C actions, stick for movement, D-pad for open menus. L looks and Z
targets. Aiming must use the stick on 3D Pad and D-pad on digital pad without
turning aim directions into item activations or locomotion.

## Dependencies and module boundaries

Reuse M2 attack/contact/effect handling, M3 item grant/capacity/shop logic, shared
save state, input mapper, message ownership and M1 action/physics contract.
Do not add parallel ammo or equipment inventories in the UI. Item assignment is
persistent; aim/charge/burning/equipped-use state is transient unless source says
otherwise. Reconcile earlier minimal stick/nut fields before extending saves.

M5 owns actual dungeon switches, torches, webs and enemy population. M4 needs
bounded representative fixtures for their interaction contracts; full geometry
checks stay pending until M5. Do not import the dungeon just to call M4 complete.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Source | Required evidence |
|---|---|
| Player item/action handlers and item tables | Equip/use/put-away, available action states, aiming and cancellation |
| ovl_kaleido_scope item/equipment/quest/map code | Assignable C slots, cursor movement, disabled/empty slots and ownership display |
| z_parameter.c and inventory helpers | Ammo capacities, button icons, grant/clamp and equipment restrictions |
| Deku stick player handlers; Obj_Syokudai; Bg_Ydan_Sp | Ignition, burn lifetime, transfer, break and web interaction |
| Deku Nut use/effect and enemy damage tables | Flash radius/effect/immunity, ammo charge and repeated overlap policy |
| En_Arrow/slingshot-related source and eye switches | Projectile speed/lifetime, hit flags, wall impact and switch acceptance |
| z_en_item00.c, func_8001F404 | Ownership and capacity-dependent drop adjustments |

Names above are research targets; identify exact child action symbols and projectile
params before baking constants. Never equate the reflected Nutsball from M2 with
a fired Slingshot seed or a Deku Nut flash.

## Delivery checkpoints

### M4a: inventory, assignment and input ownership

Define source-based inventory/capacity/assignment tables, save layout and version
policy. Validate old-version rejection, highest slot/capacity and round-trip data.
Assignments reference valid inventory identities rather than ephemeral actor IDs.

Specify input context order: pause/dialogue/cutscene/death, item aiming/use, C-up
hint/view, normal movement/combat. Preserve held/released edges through slow draws;
changing context or controller must not fire a queued item. Decide conflicting C
press behavior from source rather than relying on loop order in the current mapper.

Review: both controller layouts, C-up versus three item slots, blocked actions,
empty/capped inventory and save compatibility. Publish a concise control table.

### M4b: pause subscreens and HUD

Build Items/Equipment/Quest/Map screens on current pause ownership. Cursor data
comes from inventory, not drawn strings. Assignment/equipment changes apply once
per action; cancel restores the correct parent screen. Heart pieces, Emerald,
token count and capacities display shared fields when available. Map/Compass use
per-dungeon state; unowned information stays hidden according to source.

Human requirement: every menu element uses VDP2, including ROM-derived item icons,
text, panels, cursor and map artwork. No VDP1 menu textures, sprites or preview
models. Define VDP2 layer/character/pattern-name/palette budgets, compatible color
formats, upload timing and restoration of gameplay/prerender state. Tile or page
large maps within that budget; never fall back to VDP1 on overflow.
Keep gameplay frozen and
clear every old prompt/cursor glyph on page change. Equipment preview/rotating cube
is not required; do not let a presentation shortcut change inventory semantics.

Review: all cursor boundaries, denied assignments, save/reload assignments,
controller changes, pause during safe/unsafe action states, no stale text.

### M4c: sticks and nuts

Stick uses existing attack/contact code with its own damage classification and
source animation/length behavior. Implement lighting, burn timer, flame transfer,
put-away/extinguish/break and ammo debit at source-defined points. Do not apply
burn damage or consume sticks merely because the draw callback ran.

Nut use consumes ammo once, applies the source stun effect only to eligible
colliders and respects enemy reactions/immunities. Share timing/effect ownership
with combat so stun cannot strand an actor after damage or room unload.

Review: torch -> stick -> second torch/web fixture, expiry/break/cancel, last ammo,
full/empty grants, immune enemy and one effect per valid use at variable draw rate.

### M4d: Slingshot and integration

Implement equip/raise/aim/fire/put-away, first-person camera, seed ammo and projectiles.
3D stick has deadzone and proportional aim; digital D-pad keeps reliable aim. Use
source fire/release behavior and preserve Z targeting/first-person transitions.

Projectile simulation is fixed-step, world/actor collision is swept as needed,
and pooled entities release on impact, timeout and unload. Eye-switch acceptance
uses the correct damage/category flags; damage effects follow enemy tables.
Reconcile ownership-dependent drops now that all three item families exist.

Review: target at range, nearby wall, thin switch, multiple projectiles, empty ammo,
last seed, camera exit, target loss, pool exhaustion and room transition while aiming.

## Acceptance and later obligations

- Every owned item can be assigned, selected, used, exhausted, replenished and
  reloaded without desynchronizing HUD, save state and action state.
- C-up hint/view never overwrites an item assignment; menu navigation never uses an
  item. Simultaneous directions and held buttons have documented deterministic rules.
- Ammo/debits/effects independent of render rate, pause and 50/60 Hz VBlank.
- Dungeon fixtures prove API behavior; M5 verifies actual torch/web/eye-switch and
  Skulltula/Gohma encounters. Map artwork/markers checked with M5 room data.
- M6 supplies Fairy Ocarina acquisition; M7 supplies music play. No invented songs
  or free item grants in the clean release to mask those dependencies.

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
