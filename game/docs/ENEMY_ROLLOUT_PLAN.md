# Plan: every non-boss enemy, every map — real decomp actor, baked sprite

## Context

Current human ordering (2026-10-08): implement Hyrule Field, then Water Temple
enemies, obstacles and puzzle actors. This supersedes the earlier W0b import
ordering gate, not source gameplay or verification requirements. Field now has
four source actor profiles and six effect profiles in a scene-owned pack, API25,
73 generic sprite clips and 32 view/cel entries. Focused host and isolated target
checks pass; the usual Clean Field disc is built. Human accepts the shown adult
Poe defeat/soul dialogue; other era, bottle and population checks remain open.
Water Temple source/water ownership work is active, with no temple pack staged.
Current evidence and
Player/horse dependencies: [Field handoff](FIELD_ENEMIES_2026-10-08.md).

Inventory follow-up (2026-10-08) changes the shared baseline to core API24 and
initializes the previously zero source `R_UPDATE_RATE` to 3. Source velocity
movement and scaled updates now advance; older stationary-actor observations
are not performance or behavior acceptance. Tool quads, hook anchors, bomb
blast placement and swept host contacts are repaired without new actor imports.
Use the matching final artifacts and memory evidence in
[INVENTORY_HANDOFF_2026-10-08.md](INVENTORY_HANDOFF_2026-10-08.md) for subsequent
pack builds and Player/actor fit work. Runtime acceptance remains separate.

Human follow-up (2026-10-08): all retail maps must fit, beyond the original
20 enemy registrations. Registration is now an immediate parallel task for
all 101 retail maps; the missing 26 retain source collision and use bounded
room detail. Nine debug-only maps are absent from the retail input ROM.
This advances map availability only; actor imports and wave acceptance remain
gated. Per-scene C collision allocation is temporary until the unified core
collision/Player cutover; heap capacities stay unchanged. All 101 maps are now
registered and target-built; evidence and open runtime checks are in
[ALL_MAPS_HANDOFF_2026-10-08.md](ALL_MAPS_HANDOFF_2026-10-08.md).

Current owner: Astra, 2026-10-08, branch `oot-core`. The five handoff questions
are settled in [ENEMY_DESIGN_REVIEW.md](ENEMY_DESIGN_REVIEW.md). W0a shared
groundwork is implemented; its earlier no-enemy-import status is superseded by
the Field pack above.
Host/target/runtime evidence is recorded separately below. The human's Field and
Water Temple order now precedes the earlier W0b sequence. Player migration stays mandatory
and runs alongside this work; grab/capture/gear hooks wait for real Player.

Human want all enemies on all maps wired, sprites, bosses excluded. Permanent
contract already says so (`game/docs/ACTOR_SPRITE_ROLLOUT_PLAN.md`); this plan
make it real for enemies.

Pre-W0a baseline (scouted 2026-10-08; changes tracked below):
- Zero decomp enemies run. Six hand-ported C mesh enemies (`src/dekubaba.c`,
  `karebaba.c`, `skulltula.c`, `wall_skull.c`, `gohma_larva.c`, `hintnuts.c`)
  live only in Kokiri Forest / Deku Tree. Core room spawn drops every enemy id
  (`oot-core/src/oot_core_api.cpp:124,193-221`). Kill-all doors in generic
  scenes can never open (no enemy ever counted).
- No per-scene code loading. Core carve 589,824 B; Player-migration partition
  leaves ~2.5 KB (`docs/PLAYER_MIGRATION.md:345-371`). Enemy SH-2 code ≈455 KB
  total (≈0.8× N64 overlays), worst scene Spirit ≈145 KB → enemies can NOT be
  resident.
- Scene carve `RAM_CART_SCENECOL` 256 KB (`src/ram_cart.h`, loader
  `src/oot_core_host.c:315-348`) holds `.OOC` (max today 51 KB) + tiny sprite
  `.OOB` objects → ~200 KB spare per scene. Home for enemy code packs.
- Sprite path built for six NPCs: clock hooks only `SkelAnime_InitFlex`
  (`tools/oot_core_import.py:958`; most enemies use `SkelAnime_Init`); draw
  skipped (`oot-core/src/oot_core_draw.cpp:467-472`) but enemies place colliders
  in Draw/PostLimbDraw; one sheet per (object, limb count) (cow key-collision
  bug); 8 slots / 16 views, unstable slots, whole-bank reupload; no hit flash,
  alpha, scale; sheets read from CD mid-room; one SPR file per clip (disc dir
  limit 1536, 919 used).
- Combat: C sword → core via proxy quad only (`oot-core/src/bridge_player.cpp`);
  core enemy AT never hurts C Link; `src/attention.c` cannot target core actors;
  EffectSs overlays NULL, effects never draw; decomp SFX map is a hand switch
  (`src/action_audio.c:426`); no battle BGM (seq 26/56 not baked).
- 35 scenes unregistered (`docs/WORLD_ROUTE_AUDIT.json`), 20 of them hold
  enemies: collision > 2321 C tris, room texture/tile/vertex caps.

Human decisions (2026-10-08):
1. Boss exemption by decomp category: `Boss_*`, `En_Ik`, `En_Torch2` and other
   ACTORCAT_BOSS keep models. Every ENEMY-category mini-boss (Stalfos, Lizalfos,
   Wolfos, Flare Dancer, Dead Hand, Big Octo, Poe Sisters, Gerudo) → sprite with
   baked hit anchors.
2. Run parallel with mandatory Player migration. Grab/capture/gear enemies
   (Wallmaster, Floormaster, ReDead/Gibdo, Like Like, Dead Hand, Gerudo guard,
   Skull Kid) wire only after real Player cutover. No throwaway C-Link hooks.
3. Hazards (spike trap, scythes, flame trap, arrow trap, flying pot, fake door,
   blue fire) included: decomp logic, geometry visuals (props rule).
4. Registering the 20 unregistered enemy scenes is IN scope.

Outcome: every reachable enemy placement/spawn in every scene, era, time and
layer runs its real decomp actor, drawn from baked sprite cels, with source
damage, stun, projectiles, death, drops, flags, SFX — within measured budgets.

## Roster (scope)

Generated inventory: [ENEMY_ROSTER.json](ENEMY_ROSTER.json), with repaired
[ACTOR_COVERAGE.json](ACTOR_COVERAGE.json). Source categories determine boss
exemption, not the draft names below. The current source has 20 boss-category
profiles; `En_Bdfire` is ENEMY and is not boss-exempt. The expanded closure
includes conservative prop/Gold Skulltula/child-spawn candidates; these are
neither simultaneous peaks nor accepted scene coverage. The original 20
unregistered enemy scenes remain approved registration scope. Additional
`spot15` Hyrule Castle candidates are inventory/follow-up, not extra W0a scope.

| Class | Actors |
| --- | --- |
| Sprite enemy | En_Dekubaba En_Karebaba En_St En_Sw(+gold→En_Si) En_Hintnuts En_Dekunuts En_Shopnuts En_Goma(non-boss eggs) En_Okuta En_Tite En_Peehat En_Po_Field En_Skb En_Reeba En_Crow En_Firefly En_Poh En_Bb En_Wf En_Dodongo En_Dodojr En_Am En_Vm En_Zf En_Bili En_Bubble En_Tp En_Ba En_Bx En_Brob En_Eiyer En_Vali En_Bigokuta En_Test En_Po_Sisters En_Fd En_Fw En_Bw En_Ny En_Sb En_Weiyer En_Anubice En_Fz En_Attack_Niw |
| Player-gated sprite | En_Wallmas En_Floormas En_Rd En_Rr En_Dh En_Dha En_GeldB En_Skj; En_Mb (spear charge carries Link: PLAYER_STATE2_7 + parent); En_Am pushable-statue params variant only (roster gates by params) |
| Sprite projectile/child | En_Nutsball En_Skjneedle En_Anubice_Fire En_Fd_Fire En_Si (gold token), En_Bdfire (ENEMY, not exempt); En_Bom explosions reuse resident tool actor |
| Logic-only spawner/timer | En_Encount1 En_Encount2 Obj_Roomtimer En_Anubice_Tag |
| Hazard, geometry | En_Trap Bg_Haka_Sgami En_Honotrap En_Arow_Trap En_Tubo_Trap Door_Killer En_Ice_Hono; plus enemy-category non-characters En_Yukabyun (flying tile) and En_Fire_Rock (falling rock) — ledger records reason |
| Spawner props needed | Bg_Po_Event/Bg_Po_Syokudai (Poe Sisters), Bg_Bdan_Objects (Big Octo), En_Wood02/Obj_Kibako2/Obj_Makekinsuta (→En_Sw) |
| Boss-exempt | Exact 20 ACTORCAT_BOSS profiles in generated roster, including Boss_*, En_Ik, En_Torch2, En_Clear_Tag, En_Sda, En_Ganon_Organ/Mant, Demo_Geff, En_Fhg_Fire, En_Vb_Ball; Goma retains gohma.c and its boss larva path |

## Systems to build (shared infra first)

### A. Roster + ledger (tools)
- Regenerate `docs/ACTOR_COVERAGE.json` (stale: misses tools + gallery);
  fix `tools/build_actor_coverage.py:145-148` profile misfile (En_Goma vs
  Boss_Goma, Boss_Dodongo, En_Heishi1, En_Vb_Ball, En_Bdfire, En_Fhg_Fire);
  fix sheet path (`build/generated/npcs` vs `build/cd`); drop `ACTOR_FLAG_*` noise.
- New `tools/build_enemy_roster.py` → `docs/ENEMY_ROSTER.json`: per
  scene/room/layer placements + params; transitive spawn closure incl.
  non-enemy spawners; objects; EffectSs types; SFX ids (Actor_PlaySfx /
  Audio_PlayActorSfx2 / DeadSound args); player-hook gate (Play_TriggerRespawn,
  Player_SetCsAction*, Inventory_DeleteEquipment, PLAYER_STATE2_7 grab);
  drop sites; class (table above); wave; per-room peak instances/kinds.
- Gate: unknown spawn target, unclassified enemy, or wrong boss set = fail.

### B. Per-scene actor code packs `<scene>.OAP`
- Enemy/hazard/effect TUs compiled once (pack-only list, not resident SOURCES).
- New `oot-core/pack.ld`: two-pass fixed link per scene at top of scene carve
  (`carve_end - align16(size)`), core symbols via `--just-symbols` of
  `oot-core.elf` + `obj_syms.ld`. Same fixed-address idea as `scenecol.ld`.
  Exact raw SH-2 ABI and core binary fingerprint must match; runtime relocation
  and blanket weakened engine objects are rejected by the design review.
- Engine helpers core gc'd (Actor_SetColorFilter, EffectSs*_Spawn, BodyBreak_*,
  Actor_SpawnFloorDustRing…): stateless → copied into pack; stateful → KEEP-
  exported from core (measured, coordinate with Player owner). Tool fails if a
  pack copy touches engine statics.
- Header: magic/version/link base/size/bss/ctor range/actor table/EffectSs table.
- Loader beside `load_scene_blob`: load during scene load only, `slCashPurge`,
  zero bss, run ctors, register profiles into overlay table (hook decomp
  Actor_Spawn overlay branch / `Overlay_Load` stub, `bridge_play.cpp:91-95`).
  Exit: kill all actors + clear EffectSs BEFORE pack overwrite; follow Astra
  scene-pack rollback rule (restore old or safe error, never stale pointers).
- Build gate per scene: OOC + OOBs + OAP ≤ 256 KB; report named costs.
- Bonus to offer Player owner: move never-spawned resident actors (En_Ko, En_Md,
  En_Wonder_Item, En_Wonder_Talk2, Obj_Mure2, En_Kanban ≈38 KB) into packs.

### C. Importer for enemies (`tools/oot_core_import.py`)
- Sprite clock also for `SkelAnime_Init(` (+ Free/Change hooks), `bridge_npc.cpp`.
- Per-actor Update-side semantic anchors replace Draw gameplay side effects:
  bounded 32-bit points/radii/quads, source clip clocks and cull predicates.
  Offline FK validates recipes. No runtime limb transforms, skeleton replay,
  pose tracks or head tracking. Each import audits all Draw clock/flag effects.
- BodyBreak shim must preserve waits, drops, Stalchild head-break state and
  Stalfos child-counter/revival timing. No immediate-success shortcut. The five
  waiting sprite actors and boss-exempt En_Ik are listed in the design review.
- Custom recipes for non-SkelAnime enemies (En_Rr, En_Fz, En_Ny, En_Bubble,
  En_Bili/Vali bodies, En_Bx, En_Yukabyun).
- Visual-only engine calls (Lights_*, quake, rumble) → host shake / no-op, logged.
- Fx range literals per actor cleared in `import_report.txt`.
- Routing: `load_room_actors` (`oot_core_api.cpp:193-221`) routes roster ids to
  core in ALL scenes once the scene pack has them; C spawner for same id
  disabled in same build (never double). Room lists reach 89 entries (Goron
  City cs, Kokiri 78, Field 73, Zora's River 66) > `ROOM_ENTRIES_MAX` 64:
  prefilter lists per scene/layer at OOC build time and point
  `actorEntryList` into the OOC (no copy, no cap, no new resident RAM).

### D. Enemy sprite bake (`tools/build_enemy_sprites.py`, reuse `build_npc_sprites.py`)
- Recipe table per actor: object/skeleton, semantic clips (idle, move,
  attack, hurt, death, special), poses per clip, height cap, view family
  (5+mirror default; asymmetric 8; wall En_Sw; ceiling En_St; flyer),
  CLUT variants by params (Keese fire/ice, Tektite red/blue, Poe kinds,
  Lizalfos/Dinolfos, Stalchild sizes), multi-part where needed (Peahat rotor).
- SPR2: one file per (object, skeleton) holding all clips (fix disc-file
  pressure), per-clip crop/layout, key = skeleton + anim symbol from linked
  `obj_syms.ld` (extend `tools/build_sprite_keys.py`; fixes cow collision).
- Anchors: offline FK derives compact gameplay descriptors only; test source
  contact points within the chosen tolerance. No runtime limb/pose data in OOB.
- Bake cache by source+recipe+format hash; parallel per actor (Python raster slow).

### E. Sprite runtime v2 (`src/npc_sprite.c`, `src/oot_core_host.c`, `src/kokiri_sgl.c`, `oot-core/src/oot_core_views.cpp`)
- Preload every roster sheet at scene load (no CD mid-play); missing = MISS
  diagnostic + scene not ready.
- Cel cache in actor VRAM reserve keyed (sheet, clip, pose, dir), shared by
  instances; stable entries; no whole-bank reupload.
- View export adds: skeleton key, colour filter, alpha, scale, orientation,
  lens-only flag, shadow. Raise view cap (16) from roster peak, within budget.
- Tinted CLUT per sheet (red hurt, blue freeze/stun, white flash) for
  Actor_SetColorFilter; half-transparency/mesh for alpha (Poes); hide lens-only
  unless Lens; scale = actor scale / bake scale.
- Ground shadows via existing `kokiri_actor_shadow`.

### F. Combat bridge (C Link era; retired at Player cutover)
- Proxy AC hit → C Link: damage, knockback (Actor_SetPlayerKnockback* fields),
  i-frames, burn/freeze/shock element, per frame-skip rule
  (`docs/OOT_CORE_PIPELINE_PLAN.md:1176-1189`). Remove direct Health_ChangeBy path.
- Proxy AT: spin, jump slash, Deku Stick (incl. burning); proxy shield
  collider (reflect Octorok rocks / scrub nuts). Slingshot seeds + thrown Deku
  Nuts spawn core En_Arrow (ARROW_SEED / ARROW_NUT) like the bow already does
  (`oot-core/src/bridge_items.cpp`) — source path, hits core enemies natively;
  C contact pass kept only while C enemies live (until K).
- Core tools (arrows, bombs, boomerang, hookshot) already hit core enemies
  core-to-core; verify, no bridge needed.
- Proxy mirrors meleeWeaponState, shielding, lock-on, invincibility, mask, boots.
- `src/attention.c`: target core enemies (flags/arrow height), Navi enemy
  colour/hints, lock sound, Battle1 camera, minimap.
- Enemy BGM: bake seq 26 (enemy) + 56 (mini-boss); source rule
  `z_actor.c:3486-3488` (bgmEnemy within 500).
- Fix found bugs: Skulltula drop table clamp (`src/item_drop.c:23`), repeated
  tool-hit tag reuse (`src/oot_core_host.c:626-627`).

### G. Effects
- Roster EffectSs overlays (DeadDb, DeadSound, DeadDd/Ds, HitMark, Hahen,
  EnFire, EnIce, DtBubble, Bubble, GRipple, GSplash, KiraKira, Lightning,
  FCircle, KFire, Sibuki, DFire, Blast) compiled into packs; update in core.
- New effect view → C billboard sprites from small resident effect bank
  (smoke, flame, spark, ice shard, bubble, ripple, bolt, debris); per-frame cap,
  oldest dropped (visual only). DeadSound must play its SFX.

### H. SFX + music
- Enemy sources use 5-12 SFX each (325 distinct NA_SE_EN_* overall); sound RAM
  area bank has ~1 KB spare worst case. So: per-scene enemy SFX library
  (half rate, `tools/build_action_audio.py`) loaded to cart heap with the scene;
  per-ROOM active subset copied cart→sound RAM area region on room change
  (RAM copy, no CD read). Generated sfxId→slot header replaces hand switch
  (`src/action_audio.c:426`).
- Gates: scene library ≤ cart budget, room subset ≤ SFX_AREA_LIMIT; over →
  named list, priority hit/death/attack, then shorter tails/lower rate;
  omissions logged, never silent.

### I. Drops, flags, rewards
- Source Item_DropCollectible* + En_Item00 (resident), incl. dropFlag/adult rules.
- En_Si gold tokens → save token count (replace wall_skull path).
- Big Poe bottle (Player-gated with bottles), Poe Sisters flames/flags, room
  clear → existing door policy (`oot_core_api.cpp:795-799`) + chests,
  Obj_Roomtimer, switch/collectible flags saved; re-entry respawn per source.
- Save mirror (`src/oot_core_host.c` ~265) carries inf_table but NOT source
  gsFlags: add gsFlags to save + mirror (save version bump, migrate C
  wall_skull token flags / `save_skull_count`) so En_Sw gold + En_Si persist.
  Check every flag word roster enemies read/write is mirrored.
- Lens-only enemies/hazards (Shadow, BotW) need Lens of Truth item (open in
  RECOMP_PLAN) — dependency recorded for W3/W4.

### J. Scene registration (expanded to every retail map)
Human directive 2026-10-08 expands this from the original 20 enemy scenes to
all 101 retail maps. The separate all-map fix is implemented: bounded optional
subdivision and room texture density preserve source faces within existing
renderer limits. Complete C collision uses exact per-scene allocations and a
20 KiB XZ index inside the existing heap. The 5,096-triangle maximum needs
194,520 B; collision admission failures retain the previous world. Raw file bytes use
the existing shared load scratch. This removes registration's dependency on
the future core collision cutover; it does not complete that cutover.

Scene entries and portals move into SCENETAB.BIN to recover main RAM. Keep the
original 75 IDs stable and append 26 maps. Nine debug-only source-table entries
have no retail payload. All 388 room rows bake, all 101 OOCs validate, and the
matching Clean target is built. The separate fix also releases old core assets
before new native scene loading and trims inactive music tables while idle;
it removes the measured Ranch-to-Gohma heap overlap. Runtime acceptance remains
pending. Enemy admission still needs per-room actor VRAM reserves
sized from the roster, full simultaneous population checks, and scenecol budget
(OOC + OOB + OAP). Existing room reserve checks do not prove future enemy fit.

### K. Slice scenes + C enemy retirement
- After parity tests (damage/stun/shots/drops/rewards/SFX), route Kokiri
  Forest / Deku Tree enemies to core; retire dekubaba.c, karebaba.c(+draw),
  skulltula.c, wall_skull.c, hintnuts.c, non-boss part of gohma_larva.c,
  their meshes/area SFX; keep gohma.c boss + its larva path.

## Waves (each = one big batch, one combined human Kronos test)

| Wave | Content | Gate |
| --- | --- | --- |
| W0a | Infra only, no actor import: A, B loader/pack.ld with a test pack, D/E runtime v2 on existing NPC sheets (fixes cow key, slots, preload), F damage both ways, G effect view, H generator | none (parallel with Player) |
| W0b | Pilots end-to-end in generic scenes (no C copy there): En_Okuta (Zora's River), En_St (Bottom of the Well) | Wave 0 Fx32 open items closed ("No actor import until Wave 0 closes") |
| W1 | Child overworld/registered: Kokiri, Deku Tree, Lost Woods, SFM, Field (Encount1/Skb/Reeba, Peahat, Po_Field), Ranch, Lake, Zora's River, Graveyard, Kakariko GS, DMC, Royal Tomb; K retirement | W0 accepted |
| W2 | Child dungeon/overworld actors: DC, Jabu (Big Octo), BotW non-grabbers, Grottos, DMT, Zora's Domain/Fountain, Gerudo Valley | W1; actor budgets |
| W3 | Player-gated: Wallmaster, Floormaster, ReDead/Gibdo, Like Like, Dead Hand, Gerudo guard capture, Skull Kid, Big Poe bottles | real Player cutover |
| W4 | Adult dungeon/overworld actors: Forest, Fire, Water, Shadow, Spirit, Ice, GTG, Ganon's Castle/Tower (non-boss), Colossus, Wasteland, Windmill; hazards | prior waves; actor budgets; Player gates where required |
| W5 | Closure: every roster row × scene × era/time/layer; disc payload audit; ledger statuses | all |

## Budgets (build-time gates, per scene/room)
- Scene carve: OOC + OOBs + OAP ≤ 256 KB.
- ZeldaArena 128 KB: room peak instance bytes (sizeof from compiled TUs ×
  roster peak + spawned children); room lists prefiltered in OOC (no 64 cap).
- VDP1: room textures + roster actor reserve ≤ 445,432 B; cel cache entries.
- Cart heap: roster sheets + effect bank under 85% guard.
- Sound RAM: area bank ≤ SFX_AREA_LIMIT.
- Disc ≤ 1536 files. Work RAM .bss margin reported.
- Wide audit (`tools/audit_oot_core_wide.py`) on ELF, blob AND every OAP.
- No slower than replaced C in Kokiri/Deku Tree (human FPS compare). Per-actor
  update cost via existing actor-update profiling wrapper; report worst rooms,
  tune only if severe (content focus, no perf campaign).

## Verification

W0a scope is shared infrastructure only. The effect snapshot API does not
implement effect imports/billboard recipes; the audio generator does not enable
enemy sound banks. NPC v2 covers identity/preload/shared cels; tint, alpha,
scale/orientation and Lens fields wait for importing waves. The temporary
combat boundary covers ordinary damage, source melee flags, shield contacts
and C reaction/iframe ownership. Elemental responses, exact vertical knockback,
seed/nut core spawning, targeting/Navi, BGM and grab/capture hooks remain explicit
later requirements. Do not label all of systems C-I complete from W0a.

Implemented W0a scope (2026-10-08):
- A: 429 correctly associated profiles, 26 already imported; 98 scoped roster
  actors with the exact 20 bosses. Unknown dynamic peaks remain unresolved;
  `--require-ready` fails, rather than treating candidate counts as proven peaks.
- B: OAP1 fixed link, exact core binding, ctor/BSS validation and profile
  lifecycle, safe scene error/retry, scene carve admission. Isolated SH-2 fixture
  has no actors/effects: 124 B file + 4 B BSS/alignment, one constructor.
- D/E: all 34 existing generic NPC clips packed into seven SPR2 archives;
  394,912 B files, Ranch complete set 394,919 B including Jo terminators before
  allocator overhead. 32px/4 poses, full gameplay clip clocks, 16 shared cel
  slots and 16 views. Complete scene-object preload; no same-room sprite reads.
- F/G: one C-owned hit queue, matching source melee flags and shield AT/AC,
  source knockback heading/horizontal speed, unique per-spawn tool hit IDs,
  drop tables 13/14 fixed, bounded pointer-free EffectSs snapshots.
- H: generated existing SFX mapping; half-rate ESF1 scene/room bank generator
  with explicit sound/cart byte gates and named unsupported sounds. River's
  conservative sound set currently fails its 79,462 B area limit (208,892 B
  required including retained sounds); no enemy bank is silently staged.

Current verification is recorded in
[ENEMY_W0A_HANDOFF_2026-10-08.md](ENEMY_W0A_HANDOFF_2026-10-08.md).
Final W0a host run: 91 passing checks, no skips. Matching Clean image built;
main .bss has 288 B spare, resident core 508,560 B. Exact-core test pack,
wide audit, all 892 ISO/staged file comparisons and 75 OOC checks pass.
Host and target checks do not establish runtime/human acceptance. No actors,
effects or missing scenes were imported/registered by this infrastructure batch.

The following are full-rollout verification requirements, not a list of W0a
passes; enemy-specific probes/recipes await their importing waves:

- Host: `tests/test_enemy_roster.py`; `tests/test_actor_packs.py` (header
  validation, malformed/oversize packs, ctor run, register/unregister, rollback);
  `tests/test_enemy_sprites.py` (SPR2 validator, keys, anchors vs FK, alpha/pivots);
  extend `test_core_sprites.py` (cel sharing, tint, alpha, scale, preload);
  new `oot-core/tests/enemy_probe.cpp` (model `bgcheck_probe.cpp` +
  `bgcheck_host_stubs.cpp`): spawn each enemy, hit per damage table, stun,
  die, drop distribution vs source tables over seeds, flags, SFX ids;
  `test_combat_bridge.py`; audio bank budgets; `test_vdp1_budget.py`;
  `test_world_routes.py` for new scenes; `test_item_drops.py` (table 14 fix).
- Target: WSL `./build.sh --clean OOT_CORE=1` (BUILD.md); .bss margin; pack
  fit report; wide audit; disc audit (no enemy mesh/skeleton/DL bytes in
  OOB/OAP/SPR2); usual `build/game-clean.cue/.iso`.
- Human per wave: L+R shows MISS 0; each enemy appears, animates
  attack/hurt/death, hurts Link + gets hurt, stun/reflect/projectiles work,
  dies with effect + SFX, drops, room-clear doors/chests, re-entry, save/reload.

## Handoff to Astra (Claude stopped 2026-10-08, tokens)

Received as a plan-only handoff. This file and both plan links were already
present when Astra began; preserve those human edits. Decisions 1-4 above are
final. Source/design review is now complete; see ENEMY_DESIGN_REVIEW.md.

Resolved review questions (source evidence and limits in the review document):
1. Pack link: fixed top-of-carve + `--just-symbols` + weakened engine objects
   vs runtime relocation (two-base link diff). Check sh-elf 9.3 C++ mangling,
   init_array ctors, -fdata-sections statics.
2. Registration hook: decomp Actor_Spawn overlay branch
   (`build/oot-core/decomp/z_actor.cpp` ~3205-3260) + `Overlay_Load` stub;
   what dangles at pack unload (actor/effect pointers, overlay table counts).
3. Anchor replay vs per-actor Update-side anchor patches — read En_St, En_Test,
   En_Wf draw code.
4. BodyBreak: list enemies that wait on BodyBreak_SpawnParts to die.
5. ZeldaArena 128 KB / THA limits per worst room.
Received handoff evidence: N64 map `game-decomps/n64/oot/build/ntsc-1.1/oot-ntsc-1.1.map`
(overlay sizes), SH-2 `game/build/oot-core/oot-core.map` (ratio ~0.8),
`docs/ACTOR_COVERAGE.json` placements (stale at handoff; regenerated in W0a).
Review closed; W0a implementation and verification are in the linked handoff.
Human runtime checks remain open. W0b still waits for Wave 0 Fx32 closure;
continue mandatory Player migration in parallel. Later waves retain all
elemental combat, effects/audio, registration and per-scene budget gates above.

## Docs + coordination
- Update together: `ACTOR_SPRITE_ROLLOUT_PLAN.md` (enemy section + decisions),
  `RECOMP_PLAN.md` (whole-doc reconcile), `OOT_CORE_PIPELINE_PLAN.md`
  NEXT SESSION, `BUILD.md` gotchas, restore `BUG_FEATURE_LOG.md` entries
  (deleted in 536140e) for found bugs.
- Coordinate with Player owner (Astra/Codex): core KEEP exports for packs,
  proxy changes, bg_core_shim timing, moving unused resident actors out.
