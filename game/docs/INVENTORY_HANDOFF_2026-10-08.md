# Inventory wiring handoff - 2026-10-08

Implemented, host-tested and target-built: the first repair pass for source projectile firing,
sprite-path collision work, aim presentation and adult equipment selection.
This does **not** complete all inventory actions or the mandatory real Player
migration. The usual Clean image is rebuilt and byte-checked as recorded below.
No emulator or human gameplay acceptance is claimed here.

The request is to wire all Link inventory through decomp behavior, preserve the
digital Saturn controller crosshair, and allow source-derived sprites when
first-person meshes do not fit. Follow-up equipment reports concern Biggoron's
Sword, Mirror Shield and Hylian Shield artwork. The initial coverage record is
[INVENTORY_SOURCE_AUDIT_2026-10-08.md](INVENTORY_SOURCE_AUDIT_2026-10-08.md);
its table describes the tree **before** these repairs. Visual details and exact
asset budgets are in
[INVENTORY_VISUAL_HANDOFF_2026-10-08.md](INVENTORY_VISUAL_HANDOFF_2026-10-08.md).

## Firing and source gameplay repairs

- `oot_core_init` now supplies `R_UPDATE_RATE = 3`, as source
  `src/code/game.c:GameState_Init` does. Previously the bridge bound a zeroed
  RegEditor, and `Regs_InitDataImpl` never filled this register. Original and
  imported `z_actor.c:Actor_UpdatePos` multiply velocity by
  `R_UPDATE_RATE * 0.5`: arrows and hooks could advance timers while remaining
  stationary. The regression executes the actual init, register setup, trig,
  projectile-speed and movement functions with production Fx32, reproduces the
  zero-rate failure, and verifies the restored rate and scaled turns. This is
  a global source register: other actors' movement and scaled updates also
  resume, so in-scene NPC/enemy behavior needs target acceptance too.
- `bridge_items.cpp:OotCore_ToolStep` preserves gameplay formerly performed by
  source Draw. `EnArrow_Draw -> func_809B4800` supplies the arrow trail anchor
  and finite swept AT quad. `ArmsHook_Draw` supplies the hook tip and weapon
  endpoints used by `ArmsHook_Shoot` scenery tests; initial and previous tips
  are coherent away from world origin. Boomerang retains a finite source-size
  swept quad. These bounded anchors replace draw-side matrix work, not the
  source actors' movement/action functions.
- Hook flight is no longer classified as held merely because
  `ArmsHook_Wait` assigned `actor.parent = Player`. Released hooks now reach
  host contacts. Retraction/cancellation/death clear the proxy's matching
  parent/child/held pointers; pointer liveness is checked against actor lists.
  Deferred arrow initialization retains `unk_A73` release grace. Boomerang
  lifecycle checks use its actual `ACTORCAT_MISC` category.
- `EnBom_Explode` retains its growing explosion radius. The sprite bridge
  writes the body's sphere center directly instead of calling matrix-based
  `Collider_UpdateSpheres` and overwriting that radius. After detonation the
  center stays fixed as in source Draw; the host view uses that same sphere
  center, so moving a held bomb's hand cannot drag the blast. Bomb/Bombchu admission shares
  a limit of three supported explosives.
- A lodged arrow no longer prevents every later shot. Admission is bounded by
  the eight available tool views, with failure reported before host ammo or
  magic is charged. Source actors still own projectile lifetimes.
- Restored source-rate arrows travel approximately 225 units per core tick.
  The importer adaptation for `EnArrow_CarryActor` now uses
  `OotFx_DotRatio3` for its projection: storing that squared displacement in
  Q16.16 saturated it. Source sign, minimum-step and wall-clipping behavior
  remain; the fixture exercises axial and diagonal carry at the restored rate.
- Tool views carry previous/current source positions, source damage flags and
  amount, and stable spawn identity. The C contact bridge sweeps the full
  source step, including host frames without a core update, instead of testing
  only the fast projectile's endpoint. Explosions retain radius-based contacts.
  Core/host ABI is **24**; both binaries must be rebuilt together.
- Hook pull cadence now follows the source update multiplier. At 20 Hz, source
  displacement is velocity times 3/2; a 30 Hz host step uses the supplied
  velocity directly. The earlier extra 2/3 reduction slowed the pull.

## Admission, controls and equipment

`oot_core_tool_use` validates ownership/age and commits ammo/magic only after
source actor admission. Fire/Ice/Light Arrow costs remain 4/4/8. Following
`z_player.c:func_8083442C`, insufficient/unavailable magic launches an ordinary
arrow without changing the equipped elemental item or consuming magic. A bow
and arrow ammo are still required. This is a limited host-side reproduction of
that source decision, not a complete source magic-state service.

The aim entry path now rejects stale empty or wrong-age assignments. Existing
controls remain: tap to enter aim, release holds aim, another assigned-slot tap
fires, B exits, targeting permits a direct shot, and the camera applies this
step's look before calculating the shot. The VDP2 `+` crosshair stays at the
same position. Its glyph remains approximately three pixels off exact screen
center; this task does not change that presentation alignment.

The new bounded `ITMAIM.SPR` atlas displays slingshot, bow or hookshot hand/tool
art from source first-person display lists and ready poses. Elemental arrows
share bow art; longshot shares hookshot art. Boomerang retains crosshair aim
without a new first-person picture. The atlas is a static lower-right screen
approximation, not source draw/release animation or full first-person arms.
It adds no runtime skeleton/mesh load. One cel costs 2,080 B VDP1 and one sprite
slot; the whole atlas costs 10,296 B cart heap and preloads for later pickups.

The pause equipment menu now admits source-owned sword/shield categories even
when its old `gameplay.owned` cache is empty. `save_equip_source` still validates
the exact piece and age. Tests execute the actual pause handler, state machine
and save functions for source-only Biggoron/Mirror ownership, absent pieces,
adult max equipment switching, and child refusal. Read-only tracing found no
additional adult max-loadout save reset after unpausing. Child Hylian remains
explicitly refused by the existing presentation restriction; that differs from
the source's either-age shield rule and is not resolved here.

The adult gear renderer previously suppressed base placeholders for
Biggoron/Mirror even when its optional replacement bank failed. That can make
both look unequipped while Hylian falls back to plain base geometry. Exact
duplicate gear tiles now share storage (325 -> 196 tiles; 8,256 B VDP1 and 129
slots saved). Valid gear geometry survives absent/short artwork or a full
texture bank, using baked fallback colours: blue Hylian face, red Mirror frame
and silver center. A later room can restore source texture IDs. Invalid or
missing skin/geometry remains a loader failure. The generated header and all
four `LGEAR*` assets must be staged together.

## Host verification recorded for this task

These are separately run suites/targeted cases, not a claim that all repository
tests were discovered or that full scenes ran. Counts are individual unittest
cases. The coordinating agent reports the first eight rows and asset regressions;
specialist runs provide the equipment/source/visual checks.

| Check | Passed cases | Environment / evidence |
| --- | ---: | --- |
| `test_item_aim.py` | 7 | Windows; actual routing/projection blocks, item variants and age/empty guards |
| `test_inventory_tools.py` | 3 | Windows; admission/debit/fallback, pause equipment path, full-step C contacts and hook pull |
| `test_player_controls.py` | 71 | Windows; controller preservation |
| `test_gameplay.py` | 207 | Windows; existing gameplay regressions |
| Graphics backend targeted checks | 4 | Windows; selected `test_graphics_backend.py` cases |
| `test_core_views.py` | 2 | Windows; view boundary |
| `test_core_sprites.py` | 6 | Windows; sprite boundary |
| `test_sprite_clock.py` | 1 | Windows; animation clock |
| `test_equipment_draw.py` | 7 | Windows; real selector/draw extraction, SGL-sized records, hand/back/ocarina variants and source tunic colours |
| `test_core_update_rate.py` | 1 | WSL; real init and imported Fx32 source motion, zero-rate reproduction |
| `test_combat_bridge.py` | 6 | WSL specialist run; source/host combat bridge regressions |
| `test_link_shield.py` | 9 | WSL; source materials/culling/live normals, fallback and repeated texture restoration |
| `test_item_sprites.py` | 2 | WSL; complete source bake and three distinct bounded aim cels |
| `test_room_pixel_budget.py` | 9 | Windows; texture capacity and source geometry preservation |
| `test_vdp1_budget.py` | 6 | Windows; final staged rooms, actors, resident sprites and gear fallback |
| `test_all_map_registration.py` | 5 | Windows; all 101 retail maps, final staging/collision/OOC admission; `build/inventory/map-regression.log` |
| **Total** | **346** | **321 coordinating-agent cases + 25 specialist cases; no skips** |

Additional standalone check passed:
`oot-core/tests/run_tool_actor_probe.sh`. It compiles the actual imported
`En_Arrow`, `Arms_Hook`, `En_Bom` and `En_Boom` actions with the live item bridge,
real source movement/trig and the live `Player_UpdateWeaponInfo` helper.
Coverage includes normal/elemental arrow flags and movement, pitch/carry,
eight-view capacity, failed/deferred spawn, source seed motion, hookshot versus
longshot range timers, flight/return/pull/cancel, boomerang category/return,
mixed explosive cap and a held bomb's growing blast. The final rerun also passes
body-to-blast transition, hand movement without moving either source/view blast
center, radius growth and end-of-fuse carry cleanup. Evidence:
`build/inventory/tool-actor-probe.log`.

The standalone fixture substitutes engine allocation, audio/rendering and
collision-query inputs; it verifies real actor actions and AT registration,
not a complete source collision world. It does not execute Bombchu crawling.
The source seed test proves the core path only: the live C-button slingshot is
still the existing C `player_items.c` path. Offline aim art was inspected;
rendered Saturn gameplay has not been accepted.

## Explicit remaining inventory work

- Live Link remains handwritten C plus `bridge_player.cpp` proxy. The real
  Player migration remains mandatory. These repairs must transfer to its
  authoritative action/input/collision owner; a larger proxy does not finish it.
- Stick, slingshot and nut remain C actions. Ocarina retains its existing
  Saturn/source message integration and song/story gaps. The source burning
  stick helper still returns false for core consumers.
- Hammer, Lens, Din/Farore/Nayru, beans, bottle uses/catch/release, adult trade
  actions and child trade/mask use remain unwired. Their inventory/save/UI
  presence does not establish gameplay. Preserve the original receivers,
  timers, rewards, drops and scene prerequisites when importing them.
- Elemental `En_Arrow` damage parameters exist; `Arrow_Fire`, `Arrow_Ice` and
  `Arrow_Light` child actors/effects and full magic service do not. The new
  magic fallback does not complete elemental puzzle/effect behavior.
- Source item/ammo/bottle/magic values are mirrored inward each host frame;
  general outward inventory mutation is still absent. `save_copy_out` mainly
  commits flags/time/quest/dungeon state. Future source consumption needs one
  outward transaction, or host mirroring will overwrite it. Never debit twice.
- C/source collision and target ownership are still divided. Host sweeps can
  deliver damage to C actors, but do not provide the full source actor-hit,
  arrow attachment or hook pull-actor handshake for those actors. Boomerang
  source homing cannot assume the C attention handle is a core Actor pointer.
- Moving/airborne explosive handling, complete Bombchu floor traversal,
  hookable/nonhookable surfaces in real rooms, source actor hits and all return
  paths still need scene testing. Held-bomb damage/drop remains approximate:
  the C damage path lacks source Player's earlier hurt detachment.
  `EnBom_Explode` clears held state
  at the end of its ten source steps, so this is bounded rather than a carry
  softlock; the explosion view now exposes damage to C victims. Arrow-carried
  collectible interaction also needs the live backend/scene check. Tool world
  sprite availability after a new pickup remains tied to resource refresh;
  the always-loaded aim atlas alone
  does not solve that world-art lifecycle. Missing/budget-rejected art can
  still leave an admitted source tool invisible.
- Strength/scales/tunics/quest ownership, contextual fishing and source story
  exchange flows remain broader Player/actor integration requirements.

Next acceptance checks: both ages, repeated shots and zero ammo/magic, declined
spawn without debit, wall/source-actor/C-actor contact, hook pull/return/cancel,
boomerang return, bombs in hand and thrown, Bombchu traversal, pause/talk/scene
changes, save/reload, and adult gear texture/fallback restoration. Preserve
digital/analog control and the visible crosshair throughout.

## Target and delivery evidence

- **Target compile/link:** Full WSL assets/main link passes in
  `build/inventory-build.log`; matching core and usual Clean mastering pass in
  `build/inventory-disc-build.log`. Main .bss ends at `0x06083900`: **1,792 B**
  remain before SGL, 448 B less than the previous water/menu build. Heap and
  actor capacities are unchanged. Core text/data/BSS are 401,340/46,512/62,332 B,
  **510,184 B total**, 1,624 B above the prior resident core. Core end is
  `0x027ec8e8`, inside its unchanged carve. These are resident-only numbers,
  not proof that the outstanding real Player replacement fits.
- **Asset/VRAM budgets:** All 388 retail room records pass: 359 mesh banks,
  28 image rooms and one streamed Field. Six final staged VDP1 checks and five
  all-map checks pass. `ITMAIM.SPR` reserves 2,080 B and one slot beside room
  and actor budgets. Gear dedup saves 8,256 B: net VDP1 improvement is 6,176 B.
  Worst-case forest actors leave 10,112 B of their reserve for 12,576 B gear,
  so the verified flat fallback remains necessary. The atlas adds 10,296 B heap
  and smaller staged gear saves 8,736 B: combined net heap addition is 1,560 B.
- **Integer/wide-helper audit:** Both matching ELFs pass with zero forbidden
  sites outside libgcc. Main has 599 and core 1,390 allowed native multiply
  sites. Logs: `build/inventory/game-wide.log`, `core-wide.log`; section sizes
  are recorded beside them. No software-wide or soft-float helper was added.
- **ISO/artifact:** `build/game-clean.cue` / `build/game-clean.iso` rebuilt at
  2026-10-08 15:33:55 America/New_York. ISO is **151,592,960 B**. All **1,458**
  files are byte-identical to staging, including API24 core, all four gear
  payloads and `ITMAIM.SPR`. All 101 OOCs and seven SP2 libraries are present;
  no test actor pack is staged. The 1,536-entry GFS directory guard passes.
  Evidence: `build/inventory/iso-audit.json`. The old image was confirmed
  unlocked before mastering. No emulator was launched or stopped for this task.
- **Emulator/hardware/human acceptance:** NOT RUN / NOT ACCEPTED in this
  handoff. A successful build or ISO does not close the runtime checks above.

Final ISO SHA-256:
`d7341d83b8491cb4b52efcd1b97a0998cb2d98bbea49a9cff466bb419e7f55aa`

Main disc payload SHA-256:
`ae55af22a7b5b27db134a02156129e22daae6b404c40cc41fcdcd28fb6f9c281`

Core disc payload SHA-256:
`93cc89cf52764dd345ba06e69b36bd48d52acf5f17f43f0c3e58fa7760ac36d8`
