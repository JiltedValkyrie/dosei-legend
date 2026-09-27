# M2 draft: combat, hearts, death and continue

Draft by Astra, 2026-09-25. Requested as side planning while Claude owns M1.
This expands DEMO_PLAN.md M2. On 2026-09-26 the human confirmed water and
requested continuation, with Astra already owning ongoing implementation.
M2a input/source/storage work is started; see M2_INPUT_CONTRACT.md and
M2_SOURCE_CONTRACT.md. Boot-unique actor handles are the first M2b prerequisite.
Live heap peak capture and full contact integration remain pending. This does not close
remaining M1 issues or claim full M1 camera acceptance.

## Playable result

Child Link can use the agreed sword moves, guard and reflect a valid projectile,
lock onto enemies, evade, take damage, die, save from Game Over, and continue.
A source-based Karebaba proves the complete combat/reward loop in Kokiri Forest.
Dungeon resume rules get host fixtures now and an in-scene check in M5.

Keep Saturn controls: X sword, R shield, Z hold targeting, L look, Y manual jump,
A context action. Digital D-pad moves; 3D stick moves with proportional speed.
3D D-pad is C directions outside menus, menu navigation inside them. Preserve
commits 256e315 (3D Pad) and 5065e4c (stable slow-walk facing).

Human scope update, 2026-09-26: real starter equipment moves from M3 to
**M2b.1**, after current M2b contact/body work and before M2c human combat
testing. Required scope, priority P1, tracked as FEAT-001.

Out of scope: full dungeon enemies/Gohma, full shop/NPC conversion, complete C-item
use and pause subscreens, magic spin, bottles/fairy revival, adult weapons.
Bring forward only dependencies needed to make M2 acceptance real.

## Menu rendering requirement (human, 2026-09-25)

All menus use VDP2: text, panels, icons, cursors and prompts. Reserve no VDP1
texture memory or sprite commands for menu content. Game Over/save/continue and
pause follow this rule. Budget VDP2 character/pattern-name/palette storage and
layer ownership explicitly; do not assume VDP2 memory is unlimited. Existing
world actors remain on VDP1; menu previews must not add a VDP1 render path.

## Current foundation and gaps

- `actor_sys.[ch]`: 64-slot fixed cart pool, lifecycle and nearest-attention
  query exist. Gameplay integration, stable target identity and source attention
  eligibility still need work. A nearest-XZ query alone is not OoT targeting.
- `collide.[ch]`: AT/AC/OC, cylinders/capsules, damage tables and mass push exist.
  No complete shield bounce/contact-priority contract. One hit pointer per
  collider is not a complete multi-target attack/event policy.
- `gameplay.[ch]`: single timed swing, grass cuts, shield state and NPC targeting;
  swing timing explicitly approximate. Replace the relevant rules incrementally.
- `save_state` already stores health/capacity in sixteenths and has damage helpers.
  It has no stick/nut inventory fields. Save v2 must not silently grow.
- `game_mode` has GAME_OVER, but the complete death/save/continue path is pending.
- Budget snapshot from last clean build: 3,488 bytes below SGL, malloc arena
  51,200 bytes. This is not a budget for M2; M1 changes must be measured again.
  Actor pool uses `ram_cart_fixed`, not allocator-backed work RAM. Old 104-byte
  sound-spare and older map figures in umbrella plans are historical.

## M1 handoff contract before code

Agree concrete interfaces with the M1 owner after their review; names below
are responsibilities, not a second competing API implementation.

| M1 supplies | M2 consumes or finishes |
|---|---|
| Feet-space position, velocity, grounded/action state | Hurt displacement, knockdown, death and combat transitions |
| Floor/wall/ceiling contacts, normals, surfaces and owner | Sword wall rebound, evasion clearance and collision-safe recoil |
| Dynamic collision lifetime and movement queries | Moving-platform combat, room teardown and OC push through world collision |
| Traversal action ownership and interruption rules | No sword/guard/hurt handler fighting climb/crawl/swim in the same tick |
| Fall/water hazard event and safe respawn context | One health/death policy; distinguish void/drown recovery from Game Over |
| Source-time conversion and animation/root-motion ownership | Attack windows, combo buffering, invulnerability and evasion timing |

No second health counter, player position, physics integrator or respawn table.
If M1 deferred an interface, list it explicitly and implement that minimal
bridge first. Do not label a fixture-only dungeon check as gameplay verified.

## Source ledger and decisions to settle in M2a

Local source root: `D:/Workspace-Claude/game-decomps/n64/oot` (ntsc-1.2 assets).
Use symbols and checked data; old plan line numbers are navigation aids only.

| Area | Source entry points / files | Required extraction or check |
|---|---|---|
| Sword/actions | `ovl_player_actor/z_player.c`, `D_80854190`, `Player_CanSpinAttack`, `Player_UpperAction_Sword` | Child attack selection, chain windows, active frames, charge/release, thrust/crouch, jump slash, rebound |
| Damage/guard | same player file, `Player_InflictDamage`; `z_collision_check.c` | Damage units, effects, shield coverage/bounce, i-frames, hit priority, hurt/death transitions |
| Enemy | `ovl_En_Karebaba/z_en_karebaba.c` | Params, body/head colliders, hard body, masks, `DamageTable_Get(1)`, animation, attack, death/regrowth |
| Reward | `EnKarebaba_DeadItemDrop`, get-item grant code, `z_en_item00.c` | Actor-specific reward, capacity/ownership, pickup/timeout/regrowth; random tables only where actually called |
| Reflection | `ovl_En_Nutsball/z_en_nutsball.c` | `AT_BOUNCED`, shield eligibility, enemy-to-player attack type and changed damage flags |
| Attention/camera | `z_actor.c`, player targeting, `z_camera.c` Battle1 | Eligibility, focus, acquisition/retention, occlusion policy, release and simplified camera differences |
| HUD/death/resume | `z_lifemeter.c`, `z_game_over.c`, `z_sram.c`, `ovl_kaleido_scope/z_kaleido_scope.c`, respawn code | Heart display/critical threshold, save choices, memory versus saved state, restart location and health |

Verified while drafting: Karebaba's dead-item state offers `GI_DEKU_STICKS_1`
through `Actor_OfferGetItemNearby`; it is not a generic rupee or random-drop
substitute. Do not assume the larger Deku Baba's nut/stick selection applies.
`En_Nutsball` changes reflected attack allegiance and uses `DMG_DEKU_STICK`.
This is a scrub projectile, not blanket reflection of player Deku Nut flashes.
Game Over source explicitly remaps Deku Tree boss entrance to dungeon entrance
and assigns health `0x30` on continue. Trace the preceding save/respawn branches
before specifying all forest/interior resume behavior.

Record each source symbol, units, timing conversion and deliberate approximation
in the implementation review. No guessed universal damage or i-frame constants.

## Delivery order and review checkpoints

### M2a: contracts, source tables and budget

1. Reconcile M1 handoff and player action priority. Define interaction/roll versus
   Z+A jump slash, directional sidehop/backflip and Y manual-jump precedence from
   source plus existing Saturn decisions. Document the context table before wiring.
2. Define held/pressed/released X input for charge; consume buffered inputs once
   per fixed step and cancel them on menu, scene, death and cutscene transitions.
3. Record source 20 Hz versus runtime 30 Hz conversion. Use rational accumulated
   time or explicit converted durations; do not copy frame counters unchanged.
4. Measure code/BSS, cart peak use, heap high-water, enemy face VRAM and audio.
   Do not cut the malloc arena again based on guesswork. Choose bounded storage
   for collider/actor state; actor slots have only eight per-type data words.
5. Settle minimal stick inventory/grant support for the Karebaba reward. If the
   persistent layout changes, version/save-size/buffers/tests change together;
   old saves reject cleanly unless an explicit migration is implemented.

Review artifact: API/action table, source-derived attack/damage data, memory
budget, and explicit save decision. No whole-player rewrite.

### M2b: live actor and combat-contact loop

Wire pool lifecycle and combat registration into the fixed update, not drawing.
Specify order of movement, pose/socket sampling, registration, contact resolution
and reaction consumption against the source. If results are consumed next tick,
state that explicitly; never mix same-tick and next-tick assumptions.

Provide sword sweep, body hurtbox, guard surface and OC body. Sword endpoints
must follow attack pose at simulation cadence even when expensive skinning only
runs once per draw. No tunnelling across slow frames or skipped animation frames.
Add attack-instance/hit identity so overlap cannot damage repeatedly by accident.
Preserve source exceptions for separate attacks and multiple victims.

Shield and hard-body bounce must win over a body hit when appropriate, independent
of registration order. Resolve OC through M1 world constraints, not an unchecked
position addition that pushes Link through walls. Bound registration/event storage
and expose overflow during tests. Deferred destruction must invalidate targets and
contacts before slot reuse; use validated identity, not a dangling slot pointer.

Review artifact: deterministic multi-hit/guard/teardown host tests and one live
contact path, with grass cutting still working and no duplicate reward events.

### M2b.1: real starter equipment for early human testing

Owner: current M2 implementer (Claude). Approved required scope, not a backlog
suggestion. Reuse M1 crawlspace and source maze geometry.

1. Place the source sword chest (`En_Box` params 0x04E0; verify scene entry),
   with opening/get-item presentation, text, sword grant and persistent chest
   flag. One opening grants once.
2. Wire Kokiri Shop entrance/exit and its Deku Shield offer for **40 rupees**.
   Use source shop/grant rules, confirmation, cancellation and insufficient-funds
   paths. Grant/debit together, once. Ownership and equipment stay distinct.
   All shop/choice UI uses VDP2. Full eight-item browsing remains M3.
3. Prove a fresh file can earn 40 rupees from reachable, source-audited rewards
   before owning a sword. Bring forward needed placed rupees/props; audit full
   drops for every added actor. No debug money or sword-required economy loop.
4. Implement Mido's source equipment/dialogue/flag gate on the **Kokiri Forest
   path to the Deku Tree**: sword AND shield equipped, not merely owned. No child
   Lost Woods gate. Broader NPC conversion stays M3.
5. Remove temporary ground sword/shield spawns when the route works. Preserve
   previously earned equipment on load; do not reinterpret shortcut pickup flags
   as real chest flags or silently reset inventory.
6. Bring forward the maze rolling boulder's source path/collision. Connect its
   damage/knockback to shared M2 health when available. If damage awaits M2e,
   disclose that in the early gear check and finish before final M2 acceptance;
   do not postpone the first chest/shop human test until M3.

Human acceptance: fresh file -> crawl maze -> sword chest -> earn 40 rupees ->
shop shield -> equip both -> Mido passage. Check neither/one equipped refusal,
39-rupee refusal, purchase cancel, exact debit, repeated chest interaction,
room transitions and save/reload. No debug equipment grants. Final M2 also
requires boulder damage and no duplicate grants/payments.

M3 extends these implementations to other chests, props, shop stock and NPCs;
do not create a second item-grant/shop system.

### M2c: sword, guard and evasion

Implement slash variants/combo, thrust, jump slash, nonmagic charge/release spin,
crouch stab and wall rebound. Port source attack classifications/effects, not one
radius damage pulse for every move. Keep animation, hit windows and root motion
on the same action timeline. Preserve intended movement facing at low speed.

Implement directional guard/recoil, sidehop/backflip and landing transitions using
M1 clearance/physics. Prove reflection with a minimal source-based Nutsball actor
or explicitly labelled test encounter; full Deku Scrub puzzle remains M5. Any new
actor gets its own source/drop audit, including a documented no-drop result.

Review artifact: input precedence and attack-window matrix, wall/shield tests,
Kronos checks for animation/contact agreement and both controller layouts.

### M2d: shared attention and one complete enemy

Share registry identity/focus between Link and Navi. Preserve existing NPC talk
and Z release/recenter behavior. Enemy lock tracks moving focus with the agreed
Battle1 simplification; validate target death, unload, slot reuse, distance and
source occlusion rules. Signs/POIs need registry fixtures, not full M3 actors.

Implement actual `En_Karebaba` behavior and source child-layer placements for the
bounded encounter, including head/body collider differences, rewards and regrowth.
Use the ROM model/animations, flat material except face, and measured area SFX.
Bridge stick grant/ownership/capacity now; C-assignment and stick use remain M4.
Do not call an immortal dummy or a reward-less enemy complete.

Review artifact: player/enemy damage in both directions, source reward pickup and
persistence, target/Navi agreement, room unload/reload without stale state.

### M2e: hearts, hurt, death, save and continue

One damage entry point receives enemy and M1 fall/hazard events. Handle source
reaction, knockback/knockdown, i-frames and lethal transition exactly once. Freeze
combat timers appropriately in pause/cutscene; do not count rendered frames.
Add hearts HUD, fractional display, hurt feedback and low-health audio, with
measured core/area bank allocation. No boss HP bar.

Connect death animation -> GAME_OVER -> save choice -> continue/title flow.
Backup writes belong to the device-owning layer, not host gameplay rules. Report
failure and allow recovery; never claim success or overwrite a different slot.
Separate continuing current session state from reloading the last disk save.
Implement source destination policy, health restoration and volatile-state reset;
retain intended progression/inventory/scene flags. Do not respawn at the death
position or replay opening/story cutscenes because transient state leaked.

Review artifact: forest/interior continue live, dungeon/boss remap fixtures,
save yes/no/failure/cancel tests, file reload, and explicit deferred M5 runtime case.

## Acceptance matrix

- Progression: M2b.1 real sword chest, 40-rupee shield and equipped-both Mido
  gate; fresh-file economy, refusal/cancel/repeat and save/reload checks.

- Combat: first/last active frame, combo bounds, charge interruption, one hit per
  permitted attack, two victims, simultaneous hurt/shield, back-side guard miss,
  reflected allegiance, wall bounce, invulnerable target, zero-damage effect.
- Lifecycle: full pool/list limits, target unload/death/reuse, projectile teardown,
  no duplicate grants and no collision callback into freed actor data.
- Movement: digital walk and analog creep stay stable, Z strafe holds heading,
  jump slash/evasion land correctly, collision-safe knockback near walls/ledges,
  attack attempts in crawl/climb/swim use the agreed M1 action table.
- Timing: identical fixed-step results at different draw rates; 50/60 Hz clocks
  preserve durations; pause/unpause does not spend i-frames or release stale attacks.
- Health/resume: saturation and fractional hearts, lethal once, fall/drown policy,
  save failure, continue versus title/reload, equipment/flags preserved, dungeon
  entrance mapping and health recovery. Check new save version if fields change.
- Runtime: fresh/loaded file, fight Karebaba, collect its stick, shield projectile,
  die, decline/accept save, continue, reload; both pad types; room transitions.

Run relevant test files separately (whole-suite Python crash previously reported).
Build **clean only**, per current human instruction; record other variants as not
built. Verify map/SGL, VDP1 budgets, fixed cart bounds, audio bytes and changed hot
path disassembly for software float. Host results do not prove Kronos feel.

## Completion and handoff

Each checkpoint records source parity, intentional simplifications and deferred
checks. Final M2 review gets changed files, test counts, clean build/budgets,
actual runtime observations and save compatibility. Update OPUS_HANDOFF and
VSLICEPROGRESS at implementation checkpoints. Leave code uncommitted for review
unless human requests a commit. M3 waits for milestone review.

M5 owns real dungeon/boss continue acceptance and full enemy population; M4 owns
complete item-use/UI. Track those obligations by name instead of declaring them
verified from the Kokiri test encounter. This draft alone completes no M2 work.
