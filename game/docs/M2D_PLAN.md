# M2d plan: shared attention + Deku Baba (En_Karebaba)

Claude, 2026-09-27. For Astra review before code. Scope from
[M2_COMBAT_PLAN.md](M2_COMBAT_PLAN.md) M2d. M2c Kronos checks stay open.

## Today (explored)

- Z target = `int16_t gameplay.target`, index into `kokiri_npcs[]`
  (gameplay.h:233). `find_target` gameplay.c:1034: nearest XZ, 320 range,
  +-90 cone, forest only. Hold only. Never checks death/unload.
- Camera gets a bool only (`oot_follow_target`, demo.c:1289). Navi gets
  Link focus only (`navi_step`). No target coupling.
- `actor_sys` has handles (boot-unique), `ATTN_*` kinds, `focus_y`,
  `actor_sys_nearest_attention` (XZ, no cone). Nothing sets `ATTN_*`.
  NPCs are not actors. Only push_block spawns.

## M2d.1 shared attention (first, small)

1. **Target = handle.** `gameplay.target` -> `actor_handle_t`. Resolve each
   step; fail -> `drop_target` (TARGET_OFF). Death/unload/reuse covered by
   existing handle rules.
2. **NPCs into registry.** Kokiri NPCs spawn as lightweight `ATTN_NPC`
   actors (profile holds npc index; draw/talk code unchanged, looks up
   index from actor). Mido live copy keeps working. Forest-only rule
   becomes room ownership.
3. **One query.** `actor_sys_nearest_attention` gains the facing cone
   (source Attention_FindActor range per ATTENTION_RANGE_*; nearest
   by weighted distance). Occlusion: source BgCheck line test Link focus
   -> target focus against static collision; enemies only (NPCs as now).
   Keep 320/420 hold/drop until per-actor range table lands.
4. **Focus.** Facing aims at target focus (x, focus_y, z). Camera stays
   bool this step (Battle1 simplification agreed in M2 plan); camera pos
   input logged, not built.
5. **Navi.** `navi_step` takes optional target focus: hover point moves to
   target focus + lockOnArrowOffset scaled (2500 * 0.01 = 25 for Karebaba)
   per Attention_SetNaviState; colour switches to source per-kind
   naviInner/Outer (NPC green-ish, enemy yellow) -> closes one BUG-038 gap.
6. **Tests.** Handle target drops on kill/unload/slot reuse; cone;
   occlusion; NPC talk via locked NPC actor; Navi goes to target and back;
   existing 12 targeting tests stay green.

## M2d.2 Deku Baba (En_Karebaba)

Source: `ovl_En_Karebaba/z_en_karebaba.c`, object_dekubaba.

- **Spawns:** 5 in spot04 room 1 child-day list (Deku Tree approach),
  params 1 -> start Idle. Emit through `tools/build_actors.py`.
- **States 1:1:** Grow, Idle (wake xz<200, |dy|<30), Awaken, Upright
  (40, retract if Link >240 from home), Spin (40, head orbit r60),
  Retract, Dying (g -0.8, vy 4, speed 3), DeadItemDrop (200, blink <=40),
  Dead (200), Regrow -> Idle. Infinite respawn. 20 Hz source timing on
  our 30 Hz step via the same frame-scaling rule as M2c.
- **Colliders:** body AC 7/25 HARD (upright/spin: 15/80 HIT6, sword/
  boomerang, child masks jump-master); head AT 0x08 + OC 4/25 (+spin
  grow). Health 1, DamageTable 1. Sword hit -> Dying.
- **Drop (bible rule):** always one Deku Stick via GI_DEKU_STICKS_1,
  pickup window 200, blink last 40, nothing else. Needs **stick count +
  capacity in save** -> save version bump with migration test. C-use of
  sticks stays M4. Pickup refused at capacity (GI shared code) - check
  source Item_Give for capacity branch and match.
- **Model:** build_actor_model.py entry `dekubaba` (gDekuBabaSkel, 8
  joints, FastChompAnim only). Character rule: flat material; enemy has no
  face, so all flat (confirm). Stem 3 DLs + leaves + stick-drop DL.
  Circle shadow reuse if present, else logged.
- **SFX:** DUMMY482 (awaken), DEKU_JR_MOUTH (chomp), DEKU_JR_DEAD,
  DODO_M_GND. Measure bank bytes; add to area bank.
- **Effects:** Hahen dirt burst and smoke puffs -> simple sprite stand-ins,
  logged gap if not 1:1.
- **Memory:** model/anim in cart via jo_malloc bank2 (cutscene_actor
  loader pattern, but a gameplay actor). Work-RAM delta measured; Clean
  free now 23,616 B.

## M2d.1 status 2026-09-27: code done, Kronos pending

- `src/attention.[ch]` new: find (all filters before winner), retain
  (targetable + attention + leash, no cone/sight), focus XYZ, Navi hover
  state (lock > arrow > Link, 4 source-frame move, colour on arrival).
- `actor_t`: `focus[3]`, `arrow_y`, `range` (sAttentionRanges table).
- `gameplay.target` / `gameplay.arrow` = handles. Kokiri NPCs spawned as
  ATTN_NPC actors, synced every step (Mido live), killed outside forest.
- Navi: `navi_step_hover` (hover actor = straight flight, dash cue while
  hover moves, colour swap after arrival). Glow sets NPC / enemy.
- demo.c: Link focus into gameplay input; `attention_sight_blocked` =
  bg_line ALL + one face, camera-ignored skipped, projectile-ignored pass.
- Tests: test_gameplay 127 OK (+16 M2d). Suite: same 4 old errors.
  Clean 21,040 B free (was 23,616). No float / 64-bit helpers.
- Gaps: BUG-040, BUG-038 note.

## M2d.2 stick pickup trace (source, 2026-09-27)

- En_Karebaba DeadItemDrop calls `Actor_OfferGetItemNearby(GI_DEKU_STICKS_1)`
  every frame: Actor_OfferGetItem xz < 50, |dy| < 10, player not dead /
  spin-charging / in states 13,14,18-21, no explosive held, not carrying.
  Positive getItemId -> `Player_ActionHandler_2` takes it with NO A press
  and sets actor->parent (Karebaba HasParent -> Dead).
- `Item_CheckObtainability(ITEM_DEKU_STICK)` = inventory slot. Empty slot
  (first stick ever) -> ITEM_NONE -> get-item show (hold-up anim, text
  0x37, OBJECT_GI_STICK). Owned -> `func_8083E4C4`: field 0x0D, no 0x80 ->
  `Item_DropCollectible(ITEM00_STICK | 0x8000)` + `Item_Give` +
  NA_SE_SY_GET_ITEM.
- `Item_Give(ITEM_DEKU_STICK)`: first = 1 (slot set), else +1 clamped to
  CUR_CAPACITY. **Never refused at capacity**: pickup still consumes the
  drop, count stays at max.
- `Item_DropCollectible(.. | 0x8000)` spawns EnItem00 in its collected
  state (15-frame float-up at Link, visual). Its Init re-offers
  GI_DEKU_STICKS_1, but ActionHandler_2 sets getItemId = GI_NONE right
  after func_8083E4C4 returns, so no second stick. Match: visual only.
- Capacities {0, 10, 20, 30} (z_inventory.c). First stick:
  `Inventory_ChangeUpgrade(UPG_DEKU_STICKS, 1)` -> cap 10, ammo 1. Save
  needs stick slot/owned, ammo, stick upgrade level.

## M2d.2 status 2026-09-27: code done, Kronos pending

- `tools/build_dekubaba.py`: gDekuBabaSkel on all 24 FastChomp frames +
  stem top/middle/base, base leaves, stick drop; flat colour, 14.9 KB,
  cart carve. `src/karebaba_draw.c` draws per EnKarebaba_Draw.
- `src/karebaba.c`: full state machine, source numbers, 20 Hz ticks,
  colliders fixed at spawn (source quirk), AC hits latched across the
  skipped 30 Hz step, targetable/hostile cleared on the ground and back on
  regrow. Spawns from `build_actors.py` (5 in room 1, child day).
- Drop: one stick, auto-take within 50/10, first stick text 0x0037,
  later NA_SE_SY_GET_ITEM, full bag consumes and clamps, 200 expiry,
  no double reward. Save v3 (sticks + naviTimer), v2 migrates.
- Navi: C-Up on a locked baba reads 0x0609; Hey! Listen! on lock.
- Sound RAM: music banks half rate (human), SFX region 200 KB. Navi
  hello/call x3/chime/talk, lock-on x2, baba x4, last damage, get item.
- Tests: gameplay 145, action audio 15, save 22, follow 33. Gaps
  BUG-042/043/044.

## Order and review points

1. M2d.1 code + tests -> Clean build -> Astra review -> human Kronos
   (lock NPC, Navi flies to target, release).
2. M2d.2 model import + static draw at 5 spawns -> review stills.
3. State machine + colliders + hit/death/regrow -> tests.
4. Stick drop + save bump -> tests. Human Kronos fight.

## Astra review 2026-09-27 (binding)

- M2d.1 approved. Handle valid is not enough: recheck TARGETABLE +
  attention every step (Karebaba clears them dying, stays alive to regrow).
- Filter cone + occlusion BEFORE picking the winner; a blocked nearest must
  not hide a valid farther one. Acquisition and retention rules separate.
- Focus is full XYZ (Karebaba focus != origin). NPC actor positions stay
  synced every step, Mido included.
- Flat colour approved. Save bump approved for M2d.2: keep old saves, test
  migration and stick limits.
- Correction: Item_Give clamps sticks at capacity. "Pickup refused" is
  unproven: trace Actor_OfferGetItemNearby -> player acceptance first.
- M2c Kronos checks fine (closed).

## Open questions (answered above)

- Deku Baba all flat (no face)? Default yes.
- Save bump for stick fields now OK (M2 plan allows if version checked)?
