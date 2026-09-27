# M2 source/action and storage contract — 2026-09-26

Implementation owner: Astra, under the human's continuing takeover instruction.
This checkpoint adds tested source data, allocator profiling and actor handles.
It does not claim new live sword moves, enemies, contact resolution or M2 completion.

## Sword data traced in local OoT source

`z_player.c`: `D_80854190`, `func_8084285C`, `func_80833A20`,
`Player_Action_808502D0`, `Player_Action_80844AF4`, `func_80837948`,
`D_80854488`, `func_80837818` and `D_80854480`.
`z_player_lib.c`: `Player_UpdateMeleeWeaponInfo` gates damaging quads on positive
weapon state. The winding-up state -1 is not a damaging hitbox.

`player_attack.h` records these bounded child one-handed entries. Host tests
compare every threshold against all corresponding local source table rows.

| Source action ID | Action | Positive weapon state, inclusive source frames |
|---|---|---|
| 0 / 2 | Forward slash / combo finish | 1–4 / 0–5 |
| 4 / 6 | Right slash / combo finish | 1–4 / 2–8 |
| 8 / 10 | Left slash / combo finish | 0–4 / 0–6 |
| 12 / 14 | Stab / combo finish | 0–3 / 1–9 |
| 16 / 17 | Flip / jump start table rows | 1–10 / 1–11 |
| 18 / 19 | Flip / jump landing finish | 1–2 / 1–2 |
| 20 / 21 | Backslash right / left | 1–5 / 1–4 |
| 24 | Nonmagic spin | 0–12 |

Airborne jump-slash action overrides the start rows: before frame 6 weapon state
is 0; frames 6 to below 7 are -1; frames 7–99 are positive. Landing switches to
the finish action. Do not apply the ordinary ground-action row while airborne.

Adjusted slash animation speed is 2/3 source frame per 30 Hz simulation step
(`PLAYER_ANIM_ADJUSTED_SPEED`, combined with LinkAnimation update scaling).
Store frame thirds; do not round this to one frame/step. Contact evaluation and
pose/socket sampling must share this timeline. The existing 14-step slice swing
is still in use pending M2b/c integration and is not claimed source-exact.

Damage flags: ordinary sword quads, including nonmagic spin, use
`DMG_SLASH_KOKIRI`. IDs 16–19 use `DMG_JUMP_KOKIRI`. The magic Thunder cylinder
uses `DMG_SPIN_KOKIRI`; it is separate, outside M2. Never assign generic damage
amounts from these flags: the victim's source DamageTable owns that mapping.

Selection from `func_80837818`: still + untargeted selects right slash; still +
targeted selects forward slash. Forward input selects stab when targeting and
forward slash otherwise. Source left/back directions select right slash; source
right selects left slash. A qualifying stick-spin selects spin first.
`Player_CanSpinAttack` is a stick-history test, not a held-X charge timer.
Combo counters/recovery/charge transitions remain to port in M2c.

## Input/action precedence for integration

| Context | Action owner / decision |
|---|---|
| Title, cutscene, pause, dialogue, look | Consume/cancel combat edges; require release of cancelled X hold |
| Climb, crawl, hang, pull-up, step-up, push, bonk, slide | Traversal owns pose; no new sword/guard overlay |
| Water | X stroke, A dive; no land sword/guard/Y jump |
| A claimed by talk, item, menu or traversal | Keep existing context action; do not also evade |
| Unclaimed A, Z held, none/forward direction, sword available | Jump slash (source launch speedXZ=5, velocityY=5) |
| Unclaimed A, source side/back direction | Sidehop/backflip through M1 collision and animation owner |
| Remaining unclaimed A | Existing roll fallback where allowed |
| R guard plus X | Source crouch-stab action; must not become an ordinary slash overlay |
| X land attack | Source selection above; later charge/combo state owns held/released X |
| Y manual jump | Saturn extension retained; an accepted context/combat action wins a simultaneous press |

Source `Player_ActionHandler_10` excludes indoors, floor type 7 and floor effect
1. `func_8083BCD0` gives sidehop speedXZ=8.5, velocityY=3.5; backflip speedXZ=6,
velocityY=5.8. Velocity/acceleration conversion follows TRAVERSAL_TIMING.md.
This table specifies M2c integration; it does not claim those actions are wired.

## Budget and allocator evidence

The 51,200-byte work-RAM arena is unchanged. SDK `jo_memory_usage_percent()`
combines all zones, including cart RAM, so it cannot justify a smaller arena.
`heap_profile.c` compiles the selected SDK allocator inside a local wrapper;
the shared SDK stays untouched. Every allocation/free is observed from boot.

`dosei_heap_profile` is retained in Clean, readable through the ELF/map debugger:
zone base, capacity, live allocated block bytes, peak live bytes, current extent
and peak extent, plus global failed-allocation count. Headers, alignment and
whole-block reuse slack are counted. Extent includes holes; live excludes them.
Compaction updates extent without erasing peaks. Zone 0 is the work-RAM arena.
Host tests run the actual SDK allocator, including spill into another zone.

No live Kronos heap dump has been collected. Instrumentation is not a measured
runtime high-water result. Boot/opening/forest/house/scene-change peaks still need
capture before any arena reduction or large new persistent allocation.

Measured generated asset budget at this checkpoint:

- Link animation body 262,548 bytes, 16-byte header; cart allocation.
- Fixed cart carve 32,768 bytes: actor reservation 8,192, DynaPoly 18,432;
  6,144 bytes outside those reservations remain. Actor identity adds four bytes
  per actor inside its existing reservation, not work RAM or a new allocation.
- Forest texture report: 440,664 / 445,432 bytes, 4,768 bytes spare. Enemy face
  assets are not imported yet; this is not permission to exceed the current cap.
- SCSP core action bank 35,774 bytes; area slot 4,162 bytes, forest bank 3,310,
  852 bytes unused. Earlier spare figures are historical. Enemy/heart audio
  needs an explicit bank budget before addition.
- All menu/HUD panels, icons, prompts and text stay on VDP2.

Final Clean code/BSS gap and test results are recorded in OPUS_HANDOFF.md.

## Actor lifetime and next contact loop

`actor_handle` / `actor_resolve` use boot-unique 32-bit identities stored in the
fixed cart actor records. Handles reject killed actors before deferred reap,
unloaded actors, reused slots and pool reinitialization. Persistent actors retain
their identity across scene unload. Counter exhaustion refuses further spawn
rather than reviving an ancient handle. No handle-bearing save data is permitted.

M2b contacts and targeting must retain handles, then validate at consumption;
raw pointers remain usable only within their owning update. The existing
`collide` result pointers are not yet replaced. Next: bounded contact storage,
shield/hard-body priority, attack-instance victim tracking and fixed-step live
registration. No claim that the existing collision module already supplies them.

2026-09-26 update: collide.c now supplies bounded events/overflow, validated
handles, AC_HARD bounce, guard-first consumer check and attack-instance victim
tracking (host-tested). Only live consumer: slice sword sector vs grass, same
step. Body/shield/OC live registration and next-tick damage remain.

## Save decision

Keep v2 unchanged until Karebaba's real stick grant lands. Introduce explicit
stick count/capacity-upgrade state with save v3 at that integration checkpoint;
update length, all buffers and host tests together. Retain the existing clear
older-save rejection policy instead of an implicit migration or repurposed bytes.
Karebaba grants `GI_DEKU_STICKS_1`, not a substitute rupee. Full reward and
capacity rules must ship with the live actor. This checkpoint changes no saves.
