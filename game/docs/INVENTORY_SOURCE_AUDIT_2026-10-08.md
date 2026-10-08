# Link inventory source audit — 2026-10-08

Source inspection of the shared tree at task start, before this task's repairs.
This is a coverage and preservation record, not a passing gameplay test or
completed Player migration. No emulator was run for this audit. Later repair
evidence belongs in the task handoff and current RECOMP_PLAN.

Follow-up firing root cause, implemented and host-tested in this task:
`oot_core_init` bound a zeroed RegEditor but omitted `GameState_Init`'s
`R_UPDATE_RATE = 3` (`src/code/game.c:493`). `Regs_InitDataImpl` does not set
that register. Both original and imported `Actor_UpdatePos` multiply velocity
by `R_UPDATE_RATE * 0.5`, so arrows, hooks and other source actors had zero
velocity-based displacement despite their action timers advancing. Core init
now supplies the source rate. `test_core_update_rate.py` executes the actual
init and imported source register, trig, projectile-speed, velocity, position
and scaled-turn functions with production Fx32. It reproduces frozen movement
at rate zero, then verifies rate three survives scene register setup, moves
arrow/seed/hook speeds, applies pitch/gravity/collision displacement, and
advances scaled turns. WSL host check passes (one test). Target/runtime
acceptance is separate; this check uses real movement instead of a mock.

Source checkout: `D:/Workspace-Claude/game-decomps/n64/oot`. Source references
below use its `src/overlays/actors/ovl_player_actor/z_player.c` unless stated
otherwise. Saturn paths are relative to `game/`.

## Ownership and request

Keep the digital-controller crosshair. First-person tools may use sprites when
meshes cannot fit; presentation must retain source item behavior. Existing world
tools already use baked `ITM*.SPR`. Real Player remains the required destination:
`bridge_player.cpp` is the live Player profile; the actual Player sources are
still isolated under the migration staging tools. Repairing its temporary item
bridge does not complete that migration.

Current dispatch is `recomp.c` -> `gameplay_step` -> `oot_core_tool_use` ->
`OotCore_ToolCommand` -> `tool_use`. Legacy action IDs 1/2/3/4 mean stick,
slingshot, nut, and ocarina; other actions encode `0x20 + inventory slot`.
All 24 inventory slots can exist and appear in the menu. Possession and C-button
assignment do not mean the corresponding action is implemented.

## Coverage by source inventory slot

| Slots / items | Original Player path and dependent actors | Current owner / gap at task start |
| --- | --- | --- |
| 0: Deku Stick | `Player_InitDekuStickIA`, melee actions; source burning-stick checks and ammo | C `player_items.c` plus `gameplay.c`: hold, slash, ignition, expiration, break, put-away, torch/web contact. Core `Player_IsBurningStickInRange` always returns false, so source consumers do not observe the real burning tip. |
| 1: Deku Nut | `Player_UseItem` -> `func_8083C61C` -> `Player_Action_8084E604`; `En_Arrow(ARROW_NUT)` -> `En_M_Fire1` | Handwritten C projectile/flash and C damage registration. Source nut actor and flash are not the owner. Preserve stun, source range, ammo, grounded use, and once-only consumption. |
| 2: Bomb; 8: Bombchu | `Player_InitExplosiveIA`, `Player_UpperAction_CarryActor`, `func_8084409C`; `En_Bom`, `En_Bom_Chu` | Real actor imports plus temporary spawn/hold/throw bridge and host ammo. Source limit is three actors in the whole EXPLOSIVE category; bridge counts three separately per actor ID. Moving/airborne throw, drop, fuse-in-hand, cancellation and draw-owned explosion placement need source-driven checks. |
| 3: Bow; 6: Slingshot | `Player_InitBowOrSlingshotIA`, `func_80834380`, `func_8083442C`, upper-body release; `En_Arrow` | Bow uses real En_Arrow through bridge, slingshot uses C `player_items.c`. Bridge permits only one live En_Arrow and releases immediately; actual Player owns aiming/draw/release. Arrow source collision registration is missing from the sprite path. Human reports bow does not fire. |
| 4/10/16: Fire/Ice/Light Arrows | Same bow path, `sMagicArrowCosts={4,4,8}`; `Arrow_Fire`, `Arrow_Ice`, `Arrow_Light` spawned by `EnArrow_Update` | En_Arrow parameters and source damage flags exist; elemental child actors are not imported. Host spends magic on spawn and denies low-magic use; source falls back to an ordinary arrow if `Magic_RequestChange` refuses consumption. No complete magic-state owner. |
| 9: Hookshot/Longshot | `Player_InitHookshotIA`, source aim/release, `Player_UpdateUpperBody` -> `Player_Action_HookshotFly`; `Arms_Hook` | Source hook actor plus temporary Player fields and C pull movement. Hook draw-owned scenery endpoints are incompletely restored; parent ownership is incorrectly treated as held in host damage views. C-only hookable actors are not unified source targets. Human reports no firing. |
| 12: Boomerang | `Player_InitBoomerangIA`, `func_808359FC`; `En_Boom` with target and return timer | Source actor and temporary throw/return flags exist. Host target handle is not a core Actor pointer; `player->focusActor` is maintained for source talk, so source homing requires explicit target ownership. Current initial throw yaw/pitch can still follow C attention. |
| 7: Fairy Ocarina/Ocarina of Time | `Player_UseItem` -> `Player_ActionHandler_13` -> `Player_Action_8084E3C4`; source message/ocarina engine and song actors | Existing Saturn input/audio + source message recognition works structurally. Preserve B cancel, five notes, source restrictions, source result ownership, Saria hints, Sun reload and explicit Saturn Time-song age shortcut. Song puzzle actors, Scarecrow/memory game, dungeon Sun stun and Temple sword story travel remain incomplete. |
| 5/11/17: Din's Fire/Farore's Wind/Nayru's Love | `Player_UseItem`, `Player_ActionHandler_13`, `func_8083AF44`, `Player_Action_808507F4`, `Player_SpawnMagicSpell`; `Magic_Fire`, `Magic_Wind`, `Magic_Dark` | `tool_use` has no cases: denied. Spell actors are not imported. Need source magic spend/state, cast readiness/cues, fire damage, barrier timer/damage rules and Farore return/respawn/scene state. Source normal costs are Din 12, Farore 12, Nayru 24. |
| 13: Lens of Truth | `Player_UseItem` -> `Magic_RequestChange(MAGIC_CONSUME_LENS)` and `Actor_DisableLens`; actor lens visibility and magic update | Denied; no live lens toggle/drain/render visibility path. A HUD icon or toggle alone cannot implement invisible actors/walls. |
| 14: Magic Beans | `Player_UseItem`, `Player_ActionHandler_13`, `EXCH_ITEM_MAGIC_BEAN`; `Obj_Bean` | Denied; bean exchange receiver is not imported. Source consumes ammo only when the correct exchange is accepted; keep scene switch, age growth, song and platform behavior. |
| 15: Megaton Hammer | `Player_InitHammerIA`, `Player_ActionHandler_7`, source hammer melee and `DMG_HAMMER_SWING/JUMP` | Denied. Hammer is a Player melee action, not a free projectile spawn. Need real swing/impact frames and puzzle contacts; reusing sword damage would break hammer switches/rocks. |
| 18–21: Four bottles, all contents | Empty: `Player_Action_SwingBottle` and `sBottleCatchInfo`. Drink: `Player_Action_8084EAC0`. Fairy: `Player_Action_8084EED8`. Release: `Player_Action_8084EFC0`. Letter/Poes: exchange path. `Inventory_UpdateBottleItem`, `Inventory_ConsumeFairy` in `z_parameter.c` | All bottle C uses denied. Empty/milk grants and persistence exist. Need slot-specific content replacement and C assignment refresh; potion/milk health/magic, milk half state, catching/releasing fish/bugs/blue fire/fairies, Poes, Ruto letter, death fairy consumption. Catch/release actors `En_Fish`, `En_Insect`, `En_Ice_Hono`, `En_Elf` are not imported by current production importer. |
| 22: Adult trade sequence | `Player_UseItem` -> `Player_ActionHandler_13` -> `Player_Action_ExchangeItem`; source exchange receivers, timers, get-item offers | C use denied. Dawn egg replacement is supported separately; it does not cover Cojiro through Claim Check trades, spoilage timers or rewards. Host `Item_Give` supports only a small grant subset. |
| 23: Child trade / masks | Same exchange path for egg/chicken/Zelda letter; `Player_UseItem` mask toggle and `Player_ProcessItemButtons` mask removal; `Player_GetMask` / face reactions | C use denied. Egg hatch storage exists. Proxy exposes `currentMask` to actors but no live item action sets it. Need mask wear/put-away, source reactions, sales and repayment/save flags; preserve mutually exclusive slot contents. |
| Equipment / quest / upgrades | Real Player equipment properties, melee/shield/boots, inventory grants, source quest and scene actors | Saturn sword/shield/boots/equipment UI and save bits exist. Owning tunics/strength/scales/quest bits must connect to actual Player/environment/puzzle rules. Test max gear does not prove those abilities or unlock story flags. Fishing pole is a source contextual Player item outside the 24 slots; Fishing actor/action integration remains open. |

## Immediate wiring defects and checks

1. Sprite-only item paths must preserve gameplay work originally done in Draw.
   `EnArrow_Draw` calls `func_809B4800`, which updates the arrow tip/AT swept
   quad. `OotCore_ToolStep` restores boomerang and hook quads but does not restore
   arrows. An actor that moves without registered AT cannot hit source receivers.
   Execute real EnArrow flight and collision registration in a focused test.
2. `ArmsHook_Draw` writes `unk_1E8` from the current tip transform;
   `ArmsHook_Update` copies it to `unk_1F4`, and Shoot uses both for scenery
   intersection. Bridge only updates a generic quad; restore coherent tip and
   previous-tip anchors at source cadence, including the first shot away from
   world zero. Keep source hookable surface and actor predicates and retraction.
3. `ArmsHook_Wait` sets `actor.parent = Player` while the hook flies. Current
   `ToolView.held` equates that parent pointer with a held item; C contacts skip
   every such hook. Classify actual source action state, not parent presence.
4. Tool bridge spawn/state code must respect initialization, 20 Hz tick order,
   `unk_A73` release grace, cancellation and destruction. Preserve pending input
   over skipped core ticks and consume the firing edge once. Current live input
   bridge mainly supplies A/B/message notes, not complete real Player controls.
5. Source inventory mutations currently have no general outward save transaction.
   `oot_core_set_save` copies items/ammo/bottles/magic inward every host frame;
   `save_copy_out` only writes flags, time, quest and dungeon state. New source
   consumption or bottle replacement would be overwritten unless ownership and
   outward commits change together. Never debit both core and C for one action.
6. `tools_load` silently hides an unavailable/over-budget sheet and loads owned
   tools on asset loads. Budget all reachable items/effects before use; source
   actor success alone does not establish visible firing or first-person art.
   Current main draw intentionally hides Link during item aim and draws the
   crosshair; there is no current first-person hand/tool presentation.

These are source-inspected failure paths, not proof each caused the human's
particular firing report. Confirm repairs with executing tests and the usual
Clean target; human checks remain required.

## Preservation and implementation order

- Preserve `main.c`'s VDP2 `+` crosshair, already shared by bow/magic arrows,
  hookshot and boomerang through `recomp_slingshot_aiming`. Preserve digital and
  analog look, tap to enter aim, further taps to fire, release doing nothing,
  B cancel, target quick shot and same-tick camera direction before shot origin.
  The current crosshair is about three pixels off exact screen center; retain
  its usability while any later centering fix keeps the projectile ray aligned.
- First repair imported projectile actor lifecycle/anchors/contact and visible
  outcomes. Keep these bridge repairs explicitly temporary. Source actors stay
  authoritative for flight, impact, hook pull/return, fuse and boomerang return.
- Complete the required real Player link/region/animation-readiness work from
  PLAYER_MIGRATION. Then make `Player_ProcessItemButtons` / `Player_UseItem`
  own each migrated action and retire its duplicate C dispatch after acceptance.
  Do not bolt every absent Player action into a second handwritten machine.
- Bring in source inventory/magic services with one save transaction and import
  each missing item actor with bounded sprites/effects and original collision,
  rewards, drops and scene prerequisites. First-person sprites change draw only;
  source pose/cue/weapon anchors still need the correct gameplay timing.
- Required tests cover both ages, ammo/magic empty and successful use, held and
  released edges over 30/20 Hz cadence, spawn/allocation failure without debit,
  pause/talk/cutscene suppression, wall/actor hit, hookable versus non-hookable
  surfaces, moving targets, return/cancel, bottle slot mutation, scene changes
  and save/reload. Retain working stick/seed/nut/Ocarina and controls regressions.

Existing relevant tests: `test_gameplay.py`, `test_player_controls.py`,
`test_core_save.py`, `test_save_state.py`, `test_save_file.py`, `test_ocarina.py`,
`test_core_views.py`, `test_combat_bridge.py`, `test_equipment_draw.py` and the
isolated Player migration tests. This audit did not rerun them; generic combat
identity tests do not establish projectile launch/hit/return coverage.
