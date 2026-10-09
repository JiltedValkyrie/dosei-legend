# Real Player migration — working inventory, 2026-10-06

## Cutover plan (human-approved 2026-10-08)

Goal: one authoritative source Player and one collision world; C Link retired;
main work RAM freed; decomp enemies targetable and shieldable. Today's C Link
build stays as rollback (`PLAYER_SOURCE=0`) until human acceptance.

| Phase | Work | Owner | Gate |
| --- | --- | --- | --- |
| 0 | Remeasure retention/placement against the current core | Claude | done below |
| 1 | Move scene-specific resident actors into per-scene OAP packs (Field pack path) | Astra | free >= deficit + 24 KB; pack fits worst scene carve; NPC/prop tests unchanged |
| 2 | One collision world: port 22 files / 110 C call sites to core bgcheck via `bg_core_shim.c`; C dyna props become core proxies; retire C collision storage (~130 KB heap) | Claude | **code + host + Clean target done 2026-10-09** (below); human runtime batch open |
| 3 | Frame bank (strict) as `AnimTaskQueue_AddLoadPlayerFrame`, common set + cache handles, whole-cutscene preload/pin | Claude | decoder/cache tests, real cutscene manifests fit |
| 4 | Link real Player behind `PLAYER_SOURCE=1`: regions loader, 9 duplicates deleted, 46 hooks as host adapters, link skeleton blobs | Claude | resolved link, region guards, wide audit 0, main .bss margin |
| 5 | Host becomes I/O: input adapter (+ Y jump, B walk, custom jump), camera reads core focus/lock-on, Saturn renderer fed from jointTable/model types, one-way state snapshots, source Attention replaces `attention.c` | Claude + Astra review | per-row host tests |
| 6 | Parity pass over the preservation table below; human Kronos batches: movement / combat+items / water+climb / talk+cutscenes / era switch | both | human acceptance per batch |
| 7 | Delete C Link (`player_*.c`, `link_anim_state.c`, C Link paths in recomp/gameplay, C seeds, `attention.c`, magic mirror); then C enemies per enemy plan | Claude | measured main RAM freed |

Rules carried: no FPU/soft 64-bit helpers, no CD reads during play, sprite-only
NPCs, bosses exempt, Clean image name, Linux builds, RECOMP_PLAN updated per phase.

### Phase 0 remeasure (Claude, 2026-10-08)

`measure_player_placement.sh` (WSL, current Clean objects; the tool now takes
the live object set from `build/oot-core/oot-core.map`, so Field pack objects
are excluded, and records the ld -r vs final-link gap instead of aborting).

| Item | Bytes |
| --- | ---: |
| Resident core ELF (`_oot_core_end` - load) | 522,904 |
| Probe baseline (ld -r; link packing gap 2,216) | 520,688 |
| Core + Player, duplicates removed | 671,564 |
| + 521 LinkAnimationHeader records | 675,732 |
| Player net growth (code+data+bss) | 150,876 (+4,168 headers) |
| Capacity: core carve 589,824 + low 0x21D800 40,960 | 630,784 -> **-44,948** |
| + retired cart MUSICTRG 20,480 + FAIRY 4,096 | 655,360 -> **-20,372** |
| + low gap 0x2FB000 20,480 (was 24,576 at 0x2FA000) | 675,840 -> **+108** |

All before the ~8.9 KB hooks, frame-bank adapter (2.7 KB), cache (6.2 KB),
region loader and alignment: **real deficit about 20-25 KB**, target free
space ~45-50 KB. Unresolved in the probe: 3,250 symbols (692 new with Player).

Resident actors that phase 1 can move to packs (bytes in the current core
link map): En_Kanban 12,918, En_Ta 11,216, En_Niw 10,734, En_Ko 10,399,
En_In 8,402, En_Gs 7,740, En_Md 7,546, En_Cow 4,200, En_Wood02 3,900,
Obj_Tsubo 3,704, En_Ma1 3,290, Obj_Kibako 3,208, En_Ma2 3,194,
En_Wonder_Item 2,844, Obj_Syokudai 2,623, Obj_Mure2 2,298, En_Wonder_Talk2
1,370. NPCs alone (Ta/Niw/Ko/In/Md/Cow/Ma1/Ma2/Kanban/Gs) are ~87 KB. Tools,
magic arrows, En_Item00 and En_Kusa stay resident. Other large residents for
later review: z_message 47 KB, oot_core_draw 26 KB, z_eff_blure 14 KB (Player
sword trails need it), lookathil 7.8 KB.

### SGL-aware slave scheduling (Claude, 2026-10-09, autonomous; not run)

Eighth reading (`fr667`, `sc156`) showed the scene draw stuck at ~15.6 ms
whether the prepare ran on the master or the slave. Cause, from SGL 3.02j
code (`LIBSGL.A`, objdump): `slPutPolygon` (sglC08.o) hands the whole PDATA
to the slave only when the slave command queue is empty (read pointer at
0x260FFC44 == write pointer at GBR+72); otherwise the MASTER runs
CalcVertices itself and queues only the registration. `slSlaveFunc`
(sglA15.o) appends to the same queue and signals the slave at once.
`slSynch` queues its end-of-frame op and waits on the vblank counter. So any
job of ours on the slave when the forest is submitted made the master
transform all 2047 forest vertices.

New schedule:
- Frame start (recomp_update, before the steps): `link_anim_frame_start`
  poses Link's limb matrices on the master (the steps read them; no waits)
  and queues the vertex skin on the slave, which is otherwise idle during
  the game steps. Only kokiri_link_draw and pose writers wait
  (`link_anim_sync`).
- Draw start: `oot_core_async_kick` snapshots every core view the actor
  draws read (NPC sprites, draw items, tools, effects, grass/drop actor
  views) and queues the core update; `kokiri_frame_slave_kick` queues the
  scene prepare. The master submits the actors from the snapshot.
- `kokiri_scene_draw` waits for the prepare and an empty SGL slave queue
  (`sgl_slave_drain`, bounded 8 ms, overlay row 15 `dr`), so the slave
  transforms the forest while the master transforms Link.
- C collision queries while the slave runs: shadow floor misses are deferred
  and resolved after the join (`kokiri_shadow_resolve`).
Side-frustum cull (scene_prepare, `side_out`): polygons wholly beyond one
side plane of the pitched view (+32 units) are no longer submitted, so SGL
skips their per-polygon work on whichever CPU transforms the forest. Exact
conservative bound (pitched depth <= depth*cos + |dy|*|sin|), off when the
camera rolls; tests/test_side_cull.py runs the production function on random
cameras/quads against a float projection (0 visible quads culled, >50 %
culled). Prepare reuse also keys on screen distance and roll.
Also: per-scene index lists instead of whole-table scans every step for
portals (438, dungeon_doors.c and kokiri_scene_update) and scene exits
(1356, scene_flow_door_at); world_props_step finds spawned props with one
pool scan (was 32 x 96 slots per step).

### Link skin + scene prepare on the slave SH-2 (Claude, 2026-10-09)

Second human reading: 15 FPS (`fr667`), slave core job only 7-9 %. Second
slave job per frame (`kokiri_frame_slave_kick`, queued first in the draw):
Link's skin from the Player joints (`link_anim_take_joints`), then the scene
prepare (`scene_prepare`: vertex depth, cull/partition, sort keys, tile fog;
split out of `kokiri_scene_draw`, which now waits and submits). Every master
reader of Link's bones/points calls `link_anim_sync` (waits for the skin, or
skins on the master if no job took it). Prepare skips frame timers on the
slave (`prep_on_slave`). Bottom line `S` = skin/prepare job + core job.

### Core update on the slave SH-2 (Claude, 2026-10-09, human GO)

Human: carve logic into clean pieces; one CPU for logic, one for drawing.
Code (Debug build, not yet run):
- Host steps (30 Hz) queue decomp updates (`core_due`, 2 per 3 steps, cap 2)
  instead of running them. `main.c` submits everything that reads the core
  first (grass, drops, NPC/prop/tool/effect views), then
  `oot_core_async_kick()` runs the queued `ENTRY->update()`s on the slave via
  `slSlaveFunc` while the master submits the scene, Link and Navi from host
  copies; `oot_core_async_join()` before text/HUD does the post-update work
  (read_player, tool bits, magic, meshes/sprites, En_Ko push).
- Slave job: own 16 KB stack in Low RAM (`RAM_LOW_SLAVE_STACK`, SGL's slave
  stack is ~3.5 KB), slCashPurge before the update; master purges after the
  join. Flags/queues the other CPU polls are cache-through (0x2xxxxxxx).
- Core callbacks while busy: SFX queued and replayed at the join; fatal,
  scene_file, sprite_memory deferred/refused (fatal at the join); profiling
  ticks return 0 (the master FRT extension is master-only). Save/HUD
  callbacks (health, rupees, ammo, magic, bottles, items) run on the slave:
  plain C save memory, no hardware.
- Master entering the core between kick and join is counted (`ENTRY` guard,
  overlay row 15 `cv`); C bg_* queries then miss and are counted (`bv`).
  Link's shadow uses OotCorePlayerView.floor_y (API v30), no query.
- Join waits at most 250 ms, then `jo_core_error` (slave never ran the job).
- First run (human): runs, `st` 37 -> 16 ms, join wait 0, no violations;
  ~12 FPS. Camera stopped swinging on sideways runs (fixed: "moving" held 3
  steps). Bottom line now M/S per SH-2. The 11.8 ms `r1` was the heart HUD
  rebuilding in VRAM every pulse (fixed in health_hud.c).
- Also: sky gradient rebuild only every 16 frames of plain colour drift
  (fades/scene changes immediate); `slScrAutoDisp` only on a layer change in
  live gameplay (r1 was 11.8 ms).

### Navi = decomp En_Elf + speed batch (Claude, 2026-10-09, human directive)

Human: Navi and Kokiri fairies need no shadow or collision; Navi goes to
the decomp. Code (Debug build, not yet run):
- `z_en_elf.c` + `z_elf_message.c` in the core. The real Player spawns
  FAIRY_NAVI (Player_SpawnFairy); C-up hints use QuestHint. Saturn cuts
  (importer MACRO_REWRITES): no skeleton (SkelAnime_Init/Update removed),
  no sparkle trail, no floor raycast/shadow. Stubs in bridge_play.cpp:
  Environment_AdjustLights (no-op), Play_CheckViewpoint (false),
  Environment_LerpWeight (source), func_800F4524 (plain SFX).
- API v29: OotCorePlayerView `navi[3]`, `navi_shown` (EnElf_Draw test),
  `navi_colour` (focusActor category). Host draws her glow sprite
  (`kokiri_navi_draw_colour`); the C Navi step (navi_step_hover) is off
  under PLAYER_SOURCE; C Navi sparkles not drawn.
- No fairy shadow (fairy_draw): Navi, Kokiri fairies, drop fairies.
- Kokiri fairies stay C: their parents (Kokiri kids, En_Ko/En_Md) are C
  since a8c238e (cost). Decomp FAIRY_KOKIRI comes with decomp En_Ko.
- Cart carves: SCENECOL 0x40000 -> 0x30000 (largest scene + objects + pack
  fits; build_actor_packs checks), core 0x90000 -> 0xA0000 at 0x02760000.
  Core end 0x027F19C8 (~58 KB spare).
- Speed: Link skinning inline 32-bit (sk 7.1 -> 3.4 ms), anchor pass every
  8th idle update, shadow floor cache on 16-unit cells (16 entries),
  overlay rows 12-14 timers. Kokiri 2026-10-09 reading before this batch:
  ~10-11 FPS (fr 89.7 ms). Goal 20 FPS.

### Real Player live in Clean: phases 1, 3, 4, 5 first cut (Claude, 2026-10-09)

Human: "replace all of the player C with decomp then we will test"; Claude
took phase 1 (human choice). `PLAYER_SOURCE=1` (default with OOT_CORE=1);
`PLAYER_SOURCE=0` keeps the C Link + bridge_player.cpp proxy rollback.
- **Phase 1 (packs):** `tools/scene_pack_actors.py` moves 19 NPC/prop actors
  (En_Ko/Md/Ta/Niw/In/Ma1/Ma2/Cow/Gs/Kanban/Wood02, Wonder_Item/Talk2,
  Obj_Tsubo/Kibako/Syokudai/Mure2/Hana, Bg_Spot01_Objects2) out of the core.
  Each scene's OAP carries what its room/transition lists spawn plus child
  spawns (63 packs, SA keeps the Field enemies; tightest SA 116 KB free).
  Core 543,764 -> 442,892 B.
- **Phase 4 (link):** importer adds z_player_call/z_player_lib/z_player
  (`OOT_PLAYER_SRCS`), generated `player_anim_headers.cpp` (segment = bank id,
  aliases by data symbol), resident object_link_boy/child skeletons with
  `.keep_ph` DL placeholders. bridge_player_source.cpp: 46 hooks (camera/
  audio/scene-flow adapters, REAL z_parameter/z_play bodies, HOST inventory
  callbacks: ammo, magic, bottles; C save stays the one owner). Duplicates
  guarded in bridge_play/bridge_items. Low BSS (oot_core_draw + oot_core_bg,
  36,516 B) moved to Low RAM 0x0021D800 (`RAM_LOW_OOTCORE_BSS`, NOLOAD,
  cleared at boot). Core 576,128 / 589,824 B.
- **Phase 3 (frames):** bank tool made fail-safe (every clip the Player or
  C clips name; GC probe optional): `bank_full`, 521 clips, ALL.PFB
  626,212 B = `PLAYANIM.PFB`, loaded once at boot (no CD during play),
  replaces LINKANIM/ADULTANM. C cutscene/chest/get-item poses read the same
  bank (`link_clip_bank.h`, child root x0.64 as before). Demand loading per
  the 2026-10-06 directive is still open (whole bank resident instead).
- **API v28:** player_bank, player_view (pos, focus, yaw, jointTable,
  state flags, hand/sheath models, boots/tunic/shield, blade, ground/water,
  invincible, hidden, door room request), player_damage (C enemies ->
  Player_InflictDamage), player_pose, player_jump (Saturn Y: func_80838940,
  v 8.0), player_warp (host moves). OotCoreSave + c_slots/tunic ->
  buttonItems/cButtonSlots; Player_SetEquipmentData on equip change.
- **Phase 5 (host):** recomp.c PLAYER_SOURCE step: Saturn pad -> N64 pad
  (A=A, X=B, R=R, Z=Z, C items, B-held walk = 40% stick), core update, read
  view -> recomp_link/yaw; Saturn camera, doors, pause/HUD, story, Navi,
  C actors unchanged; C pushers/doors/web landings move recomp_link and the
  Player is warped there. Link drawn from the jointTable; sword-in-hand from
  the left-hand model type. Core Player_Draw (pose split) runs each update
  for anchors, its display list dropped. Stick Y held outside text boxes.
- **Known gaps (test will show more):** C push blocks, C pot/grass lifting,
  C sword grass cutting, C torches, C enemy knockback (damage+flash only),
  host lock-on camera, Navi actor (En_Elf not imported), door rooms from
  source doors (request surfaced, host loading not wired), Player sword
  trail, Player camera settings/door cams, sequence/filter audio hooks.
- Clean target (WSL, 2026-10-09): built; core 576,128 / 589,824 B; low
  BSS 36,516 / 40,960 B; main .bss ends 0x06078380 (48,256 B spare); core
  and main wide audits 0 failing; 1,434 disc files (COL/LINKANIM/ADULTANM
  parked in build/disc-retired); ISO 81,901,568 B, SHA256
  `a11475c6cb94effaf93c4e188603924e43faa0d5994fdb29c4ce4fd7861f4962`.
  No runtime test yet.
- C Link code (player_*.c, link_anim_state.c, physics in recomp.c) is not
  run with PLAYER_SOURCE=1 but stays for the rollback until acceptance;
  phase 7 deletes it.

### Phase 2: one collision world, live in Clean (Claude, 2026-10-09)

`CORE_COLLISION=1` (default with `OOT_CORE=1`): core z_bgcheck is the only
collision. `CORE_COLLISION=0` links the old C library unchanged (rollback).
- Core API v27: `OotCoreEntry.bg_api` -> bg API v2 (`oot_core_bg.h`): adds
  `sphere` (source SphVsFirstPolyImpl), `frame` (core step count), `ready`;
  `floor` ignore bit 8 = floor-class only; every entry misses with no
  PlayState; `dyna_carry` works on any live BgActor, not only proxies.
- `src/bg_core_shim.c`: all C bg_* over the core; carry applied once per core
  step (core Actor_UpdateAll owns the frame boundary); scene camera view cached
  per scene; `bg_water_bind` no-op (core water read directly).
- `src/bg_core_link.c`: C Link wrappers (`kokiri_collision_floor/clear/spawn/
  move/move_actor/fall/jump/actor_*`) on the shim, same constants and order.
- `scene_flow_load` calls `oot_core_scene_enter` inside the loading screen, so
  the core scene exists before spawn placement and C prop registration. No C
  scene buffer, XZ index or dyna carve init; core->C dyna mirror and water bind
  compiled out. `BG_DYNA_MAX` = 50 core bgIds. Proxy store 192 tris (worst
  C-prop room: Deku Tree room 3, 108 tris).
- Probe part 4 (`run_bg_port_probe.sh`, `bg_link_scenario.c`,
  `compare_bg_link.py`): Kokiri floors 1,477/1,638 exact, rest +-1-2 (float
  truncation vs C rounding), 3 hit/miss; spawn (-300,90,0) vs C (-300,91,0);
  camera spheres 71/71; walks 1,079/1,872 rows exact, wall slides follow source
  push-out (worst end drift 105 units on one diagonal wall run). Parts 1-3
  unchanged (known Fx corner + line 2981 still open). No-scene guard passes.
- Host: focused 212-case batch; only 6 errors, all pre-existing on HEAD
  (hit-tint test fixtures, -fPIC fixture links). test_core_sprites updated.
- Clean target (WSL): builds; core 543,764 B (carve 589,824; oot_core_bg.o
  19,224 B); main .bss ends 0x060818A0, **10,080 B** below SGL (was 80-208 B).
  Core + main wide audits 0 failing. ISO 84,604,928 B, SHA256
  `9610cb1bbb34f857cf01671fcd1a53c3f886abade2476347bf4397419f4b2d30`.
- Freed per scene: C scene buffer (scene-sized jo heap, up to ~200 KB for
  ganontika), 20 KB index, core-dyna mirror copies. RAM_CART_DYNA (18 KB)
  is unused under CORE_COLLISION but still reserved: release it in phase 4
  placement. No speculative credit taken.
- Open: speed vs C not measured (human judges on normal Clean play, CPU~);
  runtime acceptance batch (walk/slopes/walls/ledges/ladder/crawl/water shore,
  push blocks, webs, Deku mouth, platforms, Kakariko gallery, scene round trips,
  failed-warp restore). Core play now starts at boot's title scene load too;
  watch title heap. C callers still query through the shim until phase 4/7.

Inventory preservation follow-up (2026-10-08): human requests all inventory via
source Player paths, retaining the digital aiming crosshair. Source first-person
sprites are allowed when meshes cannot fit. Preserve Biggoron/Mirror equip fixes
and blue Hylian / red-and-silver Mirror fallback when their textures cannot fit.
The detailed action/source/gap map is
[INVENTORY_SOURCE_AUDIT_2026-10-08.md](INVENTORY_SOURCE_AUDIT_2026-10-08.md).
The active first wave repairs source projectile motion/Draw-side collisions,
source-to-C sweeps, magic-arrow admission, aim art and gear presentation. Host
checks and the matching Clean target pass; human runtime acceptance remains open.
Evidence: [INVENTORY_HANDOFF_2026-10-08.md](INVENTORY_HANDOFF_2026-10-08.md).
These repairs retain temporary C Player ownership and do not complete migration.
Every source inventory mutation needs one owner and a matching save commit;
the current mirror must not overwrite new core bottle/ammo/magic changes.

Current memory gate (2026-10-08): W0a and inventory repairs change the resident
core and its shared services. The 2026-10-06 core/Player retention and partition figures below are
historical measurements, not current available space. Before Player cutover,
rerun combined retention and region placement against the current inventory ELF/BIN and
matching objects, including current adapters, collision proxies, animation
cache/metadata, alignment and scene-load peaks. Do not carry forward the old
20,692 B, 11,808 B or 2,514 B margins, or infer fit by adding an old Player
delta to the new core size. Require a resolved link, region/overlap guards and
actual allocation budgets; preserve heap/actor capacities. The matching inventory
build (`build/inventory-disc-build.log`) measures resident core text 401,340 B,
data 46,512 B and BSS 62,332 B: **510,184 B total**. Main .bss ends at
`0x06083900`, leaving **1,792 B** before SGL. This supersedes W0a's 508,560 B
core/288 B main margin, all-map's 3,824 B margin and water/menu's 2,240 B margin.
Combined Player retention, region placement and resulting fit remain pending
remeasurement. Preserve the all-map allocation changes: entries/portals in
SCENETAB.BIN, exact large collision allocations and pre-load resource teardown;
see [ALL_MAPS_HANDOFF_2026-10-08.md](ALL_MAPS_HANDOFF_2026-10-08.md). Exact large
C collision remains temporary migration debt, not the unified core world.

Astra shim review (2026-10-06; source inspection, tests not rerun):
The isolated shim/proxy implementation and integer bounding-center importer fix
are present. Reported 177-row host comparison is not live integration acceptance.
Before Player cutover, initialize the proxy DynaPolyActor.transformFlags using
the proper core flags/initializer: registration currently stores only the private
Proxy.transform byte. api_dyna_carry reads that byte and calls carry helpers
straight away, but the real DynaPolyActor_TransformCarriedActor path reads
actor.transformFlags, currently zero. Test carry through the normal core actor
path as well as the C shim. Choose one frame-boundary owner and test actual order.

Budget the full replacement storage, not only the retired C allocations:
sProxies[BG_ACTOR_MAX] contains full DynaPolyActor and CollisionHeader objects,
plus source vertices/polys/surfaces, the core transformed pool, shim conversion
scratch/surface scratch, camera views, code and stack. The 192-triangle cap alone
is not a memory-fit proof. Scene teardown/reload must reset both shim ownership
and core proxy/water bookkeeping before core IDs can be reused; SetPlay currently
only changes the pointer. Cover a scene round trip, not just remove/re-register.
The remaining Fx corner fall-through and line miss remain explicit regressions.
Continue isolated caller ports/resolved linking; no Clean or runtime claim here.


Astra follow-up collision review (2026-10-06, source inspection only):
The probe now feeds identical coordinates to C and core and checks input identity
between Fx and float runs. The owner-local dynamic polygon index now subtracts
polyStartIndex; the real-matrix dyna probe covers two owners, removal and slot
reuse. These earlier source-review gaps are closed. Reported Fx/float residuals:
floor 0, wall 7, ceiling 0, line 3; no numerical/runtime equivalence claimed.
Normal-first plane arithmetic and direct dyna-normal division are importer fixes
that affect the next live core rebuild. No new Clean build or runtime acceptance.

Remaining focused checks: preserve the one Fx line miss as a regression case
and classify its gameplay significance; validate transformed slopes and moving
platform contact during proxy integration. The flat-normal test currently allows
normal.y >= 32700 and distance +/-2, rather than asserting exact flat normals.
compare_bg_port.py is a diagnostic report: exit zero checks identical inputs,
not absence of collision differences. Host reports are not target timing evidence.
Continue C shim, dynamic proxies and caller ports toward the real resolved link;
retain current Saturn behavior inventory and include adapter/storage peaks.

Cache handle/manifest/reservation fixes are reported implemented and host-tested;
the earlier Ready-loop gap review is historical, not the current implementation.
The 64 KB cutscene result covers cutscene-exclusive Link clips only. Common
Player call-graph reach (~400 clips) does not prove simultaneous need. Determine
state/cue/branch-specific animation requirements and account for every actual
participant before claiming a full cutscene set fits. Preserve whole-cutscene
preloading/pinning and zero per-shot loads. Common set/CD servicing/start gates
and actual runtime peaks remain open.


Historical Astra demand-cache review (2026-10-06; superseded by handle fixes):
Cache/rollback are isolated prototypes, not completed production demand loading.
Common-set selection, actual cutscene dependency manifests, CD/audio servicing
and real Player start gates remain open. Continue independent collision API/ports
and resolved-link work, but close these cache issues before playback integration:
- Ready requests members individually and pins only after all report ready.
  Completed members of a pending set remain evictable. Reserve/admit the entire
  deduplicated set and protect it during loading; use an owned request handle
  with one acquire/release lifecycle, cancellation and no repeat-pin leaks.
- NO_SPACE must distinguish temporary contention from impossible admission.
  A clip/set larger than the arena, or more than 64 cache entries, cannot become
  ready by waiting; the current loop can evict/reload members indefinitely.
  Preflight actual bytes/slack/entry limits, existing pins and fragmentation.
  Return explicit cannot-fit for intrinsically oversized sets; solve the whole
  cutscene budget before playback. Never stream per shot to escape this failure.
- Init lacks a manifest-length argument and does not validate clip offsets,
  monotonic ranges or archive bounds before Request sizes/starts a read. Add
  length-aware, overflow-safe archive-index validation before mutating cache state.
Required focused regressions: impossible whole set, pending-set members surviving
unrelated pressure, repeated polling/cancel/release and malformed manifest ranges.
Streaming 510 clips serially through 48 KB proves eviction/decoding, not that any
complete real cutscene fits; test real whole-cutscene manifests before acceptance.


## Demand-loaded Player animation (human, 2026-10-06)

Load only animations required by current play or an upcoming requested action.
Unused cutscene/rare-action clips stay on disc; "skip" means skip their load,
never skip a required action or substitute a silent pose. This supersedes the
all-reachable-clips-resident assumption and the blanket prohibition on animation
CD reads outside scene loading. The real Player migration remains mandatory.

Implementation contract:
- Keep a measured common gameplay set ready for immediate movement, combat,
  damage and recovery. Select additional needs by age, equipment, scene and
  current action; retain a manifest of every supported clip on disc.
- Prefetch at known scene/actor/cutscene triggers. Before a cutscene starts,
  load and validate its COMPLETE animation working set: every shot, participant,
  reachable branch, blend and uninterrupted chained segment. Pin that full set
  through playback and the final transition back to gameplay. No per-shot loads,
  mid-cutscene animation CD reads, cache eviction of later-shot clips or waits
  between shots. Include this complete set in the peak-memory budget. If it does
  not fit, revise packing/placement before playback; do not split loading across
  shots, omit animation or degrade playback flow. Rare actions
  request their dependencies before committing action state. Cache miss is an
  expected load request, not the missing-asset fatal error. Defer start while
  loading if prefetch has not finished; never promise instant CD access.
- Add request/readiness handling above frame decoding. The decoder only consumes
  validated resident clips. Do not block on CD inside per-frame decode or start
  an action and then advance cues/root motion/rewards while its pose is absent.
  Preserve input/event ownership and commit each action/reward once.
- Use a bounded cache. Pin active, blend/morph, queued-task and imminent required
  clips until no consumer references them. Evict unreferenced clips after the
  action/cutscene; reuse warm clips while space allows. Never retain every scene's
  or boss's animation set together. Unknown dependencies require resolution or
  a safe pre-start request, not silent omission or permanent global residency.
- Service loads through existing CD/audio ownership rules. Read bounded indexed
  clips/groups with correct staging and 8.3 disc names; do not require one file
  per animation. Budget common set + active/prefetched clips + decode/load
  scratch + metadata + recovery state. Preserve heap/actor capacities.
- Distinguish not-yet-loaded, unknown clip, corrupt data and I/O failure. Only
  a validated ready set may be published. Load failures remain explicit and
  recoverable where possible; never resume with stale pointers. Existing
  loading-screen reload rollback remains available when old clips were evicted.

Status (Claude, 2026-10-06): isolated request/cache layer implemented and
host-tested (`oot-core/src/player_anim_cache.cpp`, not in live sources):
- disc manifest = ALL.PFB header; asynchronous host reads; bounded arena
- every block validated before it is published to the decoder
- states: absent / loading / ready / unknown / corrupt / I/O fail / no-space
  (no-space = defer, not an error)
- `Ready(ids)` is the start gate: requests (prefetch) all needed clips and
  pins them only when every one is ready
- `Release` unpins; LRU eviction of unpinned clips withdraws the decoder slot
  before the bytes are reused
- cutscene rule: the whole set (all shots/branches) gates playback and stays
  pinned until the end
- harness: 510 clips streamed through a 48,156 B arena, 4,450 evictions
  checked, pinned and cutscene clips survive floods, corrupt/I/O failures
  never published
- SH-2: 1,904 B text, 2,848 B bss
Still pending: common-set inventory, CD/audio servicing, action-start wiring
in real Player, peak/latency measurement.
Previous status: directive and design recorded only. Next animation work: inventory the common set,
add indexed clip requests/cache ownership and action-start readiness, then
measure peak memory, CD/audio behavior and latency alongside Player integration.
Older whole-bank size reports remain comparison data, not the required runtime
residency target. No new build, runtime test or claim of final memory fit.


Astra integration review (2026-10-06): GO for isolated collision API/ports and
resolved linking. Scene-pack rollback by reloading the old pack from CD during
the same loading screen is approved. Stop Player/animation consumers, unregister
old pack slots before overwriting, retain old scene/pack identity and state, and
publish new state only after complete load/validation. On new-pack failure,
restore/revalidate the old pack and matching state before resuming. If restoration
also fails, stay out of gameplay and report a recoverable loading error or safe
error screen; never resume with missing/stale animation pointers. No mid-action CD.
Use the strict bank as reference; cutscene-only relaxation remains unproven.

Source-review blockers before adapter acceptance: PlayerFrameBank_Register
currently validates shallow offsets/counts, not full decoder input. Validate
stride/block size, kept-frame counts, widths/shifts, all block/stream extents and
padding with overflow-safe range checks; reject duplicate IDs and unintended
resident/scene collisions before publishing slots. Add malformed-block checks
that prove slots unchanged and decoding cannot divide by zero/read out of bounds.
The claim "validates a whole bank" is not yet supported by this implementation.
Same-sized chunks alone do not prove equal fragmentation: match lifetime/order,
headers/alignment, load scratch and largest-free-block needs. Partition report is
not a resolved-link fit; account for frame decoder, loader and all new adapters
in their actual regions. Low-RAM versus cart speed is unmeasured here, not an
established slower/faster result. No production cutover or new runtime acceptance.


Grok (2026-10-06) finished the measured bank pass: real delta blocks,
per-channel shifts, spawn-proven scene packs. 0.5 limit kept. Worst scene
688,068 B vs 423,472 B LINKANIM. No fit. Loader and cutover not started.

Branch: `oot-core`, fast-forwarded from cf9ba39 to 869d797 to preserve all
current main fixes. Owner: Codex. This is the first staging checkpoint, not a
replacement acceptance. C Link and the proxy still own the playable build.

## Evidence and first implementation

`tools/stage_player_migration.py` imports actual `z_player_call.c`,
`z_player_lib.c` and `ovl_player_actor/z_player.c`, plus source headers, through
the production importer fixups into ignored `build/player-migration`.
It records source/output SHA256s, range warnings and ownership blockers in
`report.json`. It does not change the live source list, assets or disc.
`oot-core/tests/check_player_migration.sh` is a reproducible isolated syntax
gate. Run in Linux with `OOT` pointing at the extracted source checkout.

Executed in WSL: staging succeeds; all three real Player translation units pass
host C++ syntax after source-scoped production-importer fixes:

- `Player_UpdateBodyShock`: enum `PLAYER_BODYPART_MAX` minus Fx was ambiguous;
  an explicit integer conversion preserves the random range.
- `Player_DetectRumbleSecrets`: closestSecretDistSq is FxSq; direct subtraction
  from Fx is invalid. Original 200000/4000000 values also exceed Q16.16.
  Accumulator now uses units /256; distance is divided by 16 before squaring,
  with threshold 15625. No storage widening or saturated source constants.
  `test_player_migration.py` executes the imported function using actual Fx32:
  204 distances (0..201, 1000, 30000), 500 ticks each match integer source pulse
  timing; absent quest item leaves accumulator/pulses untouched. Both tests pass,
  including a fail-closed check for changed source patch anchors. Fractional
  distances retain fixed-point approximation, not proven exact source timing.

No target build, link, wide-helper audit, game image rebuild or runtime check
in this checkpoint. Syntax success does not prove gameplay or memory fit.

### Range closure and SH-2 object audit (Claude, 2026-10-06)

Remaining FX RANGE literals fixed in `fix_player_migration` (fail-closed anchors):

- `func_8083FC68` (z_player): `|s16 diff| / 32768.0f` -> raw `|diff| * 2`.
  Exact. Test sweeps all 65,536 diffs x 241 speeds vs double source thresholds.
- `Player_DrawHookshotReticle` (z_player_lib): 38600/77600 local units under
  Link's 0.01 matrix. Now transforms a 1000-unit local step and extends it in
  world space by 38.6/77.6 (386/776 world, fits). Tested within 1 unit.

Staging report now lists no FX RANGE literals. `test_player_migration.py`: 5 pass.

`TARGET=1 OOT=... bash oot-core/tests/check_player_migration.sh` (WSL, Linux
sh-elf 9.3, makefile target flags) compiles the three objects into
`build/player-migration/sh2/`, runs `audit_oot_core_wide.py` and
`tools/player_migration_symbols.py` -> `symbols.json`. Results:

- SH-2 compile PASS all three. Wide audit: 0 helpers/soft-float; 293 dmuls (allowed).
- Size (pre gc-sections upper bound): z_player 134,755 B, z_player_lib 15,994,
  z_player_call 300 = **151,049 B**. At this checkpoint the live blob ended at
  501,840 B of the 0x90000 carve: **87,984 B headroom. Did not fit.** These
  figures predate W0a and are not current headroom. Retiring C Link frees main RAM,
  not this carve. Memory placement is the first blocker before any link.
- Strong duplicates (retire live owner, never suppress): Player_Profile,
  Player_UpdateWeaponInfo (bridge_player); Player_GetMask, Player_InCsMode,
  Player_ReleaseLockOn, Player_GetExplosiveHeld (bridge_play); Player_HoldsHookshot,
  Player_InBlockingCsMode, Player_IsBurningStickInRange (bridge_items).
- Unresolved vs live clean objects (libgcc excluded): 521 gPlayerAnim_*
  (gameplay_keep link animations), 144 Link draw assets (object_link_boy/child
  DLs/textures/skeletons, ice/hover effects), 2 tables (gObjectTable,
  gEntranceTable), 46 engine functions (Camera x7, Audio x8, Inventory, Magic,
  Room, Interface, Environment, Kaleido loader, DmaMgr, Map_Save, gu matrices,
  osCreateMesgQueue, OnePointCutscene, Scene transition, several func_800*).
  Full lists in `symbols.json`.

## Carry-forward inventory and verification map

### Astra memory follow-up (2026-10-06)

Added optional `--gc-ld` to `tools/player_migration_symbols.py`. Executed with
Linux SH-2 ld, nm and size against Claude's three objects and the 80 existing
Clean core objects. `build/player-migration/memory.json` records input hashes,
root sets, output hashes and static low-RAM gaps; `gc/*.map` records discarded
sections. These are relocatable `ld -r --gc-sections` probes, **not a resolved
game link**. Missing dependencies contribute no bytes; existing ELF/objects
were not rebuilt as one matching artifact in this follow-up.

| Probe | Retained bytes | Player_Draw retained |
| --- | ---: | --- |
| Source Player_Profile plus every Player service referenced by live objects | 147,178 | yes |
| Init/Update/Destroy plus those services, without call wrapper/profile | 146,878 | yes |

Root validation accounts for C++-mangled overlay entry points and fails if any
required root is absent/dropped. Simple GC saves only 3,871 B from the full
profile. Comparing the existing ELF's 87,984 B headroom, the full probe leaves
a **59,194 B deficit before missing dependencies and final alignment**, without
credit for retiring old owners. This is not a final integrated fit verdict.

Static `ram_low.h` gap audit: 69,768 B total, fragmented. Largest spans are
0x0021D800..0x00227800 (40,960 B) and 0x002FA000..0x00300000 (24,576 B).
Other gaps: 1,536 B at 0x00219200, 256 B at 0x002F1500 and 2,440 B at
0x002F7678. These are header-unassigned spans, not runtime-validated allocations.
No whole-Player contiguous slot exists. Cart bank 1 belongs to Jo's heap;
bank 2 below the fixed carves is also registered as heap. Growing the current
core carve downward would reduce heap capacity and is not an approved solution.
The previous 272 B main-RAM margin is not newly measured here.

Crucial dependency correction: excluding the profile does **not** discard native
Draw. Two source actions assign `this->actor.draw = Player_Draw` (staged lines
14775 and 15767). Player_InitCommon passes gPlayerSkelHeaders to
SkelAnime_InitLink twice. Draw calls Player_PostLimbDrawGameplay; body anchors
are consumed by movement, weapons and water logic. Do not blanket-placeholder
all 144 asset references: skeleton metadata and gameplay anchors require real
adapter implementations. Only proven unused display-list/texture references
can become inert symbols after their execution paths are separated.

### Pose-pass split measured (Claude, 2026-10-06)

`PLAYER_POSE_SPLIT` in `oot_core_import.py` swaps three whole functions
(each source span hash checked; a decomp change stops the import):
Player_Draw, Player_DrawGameplay, Player_DrawImpl. Kept: source lod and
override choice (first-person/crawl), damage flicker counter, one normal-pass
SkelAnime_DrawFlexLod walk with Override/PostLimbDrawGameplay. So limb matrices,
bodyPartsPos, weapon tips, held actor, sGetItemRefPos and feet keep source timing.
Cut (presentation only): fog flicker, actor lights, STATE2_26 mirror copy (the
normal pass runs last and owns anchors), ice fragment, get-item model, masks/
bunny-ear matrices, hover circle, eye/mouth/tunic segments, gauntlet/boot/bracelet
DLs. Face indices stay in jointTable[22] for the Saturn renderer. Test 6 checks
kept/cut calls and hash fail-closed. 6/6 pass; SH-2 gate 0 wide helpers.

| GC probe | Before | After split |
| --- | ---: | ---: |
| source_profile | 147,178 | 143,437 |
| gameplay_roots | 146,878 | 143,137 |

Saves 3,741 B. Deficit vs 87,984 B headroom still **55,453 B** before missing
dependencies. Link asset refs 144 -> 127. Pause draw was already discarded by
GC. Only remaining draw-only code is Player_DrawHookshotReticle (840 B); the
rest of the retained draw-named code (PostLimbDraw 2,268, Override*
~1.9 KB) produces anchors or limb DL choice that the Saturn gear renderer needs
(hand/sheath/shield model type). **Rendering separation cannot close the gap:**
about 97% of retained Player is the gameplay action machine. The remaining 127
asset refs are limb DL selections and skeleton headers; resolve them through the
existing object pipeline (real skeleton/limb data, placeholder DL keys walked by
oot_core_draw.cpp), not inert stubs.

Placement levers, all still to be measured: split Player .text across the core
carve plus the 40,960 B and 24,576 B low-RAM spans (sum 153,520 B vs 143,437 B
before deps: thin, likely insufficient once 46 engine functions and alignment
land); retire live duplicates (bridge_player 2,803 B total, parts of bridge_play/
bridge_items); C Link gameplay code freed in high work RAM (address-gap estimate
from the Clean ELF, LTO lower bound, ~23 KB across player_*.c and
link_anim_state.c; player_input/player_camera adapters stay). No carve, heap or
capacity change made.

### Combined retention and placement decision (Astra, 2026-10-06)

New `oot-core/tests/measure_player_placement.sh` runs
`tools/measure_player_placement.py`. It compiles temporary bridge copies with
the nine duplicate definitions removed (declarations/callers kept), then runs
relocatable section GC over **all 80 core objects at that checkpoint plus Player**, including
actual SH-2 libgcc. No duplicate-symbol suppression. Entry, ctor and keep_ph
roots match the production linker. A third case compiles and retains real
source player_anim_headers.c metadata. Missing backends, frames and skeleton
data remain unresolved, never replaced with zero-byte definitions.

Executed WSL results (`build/player-migration/placement/report.json` and maps):

| Retained set | Bytes |
| --- | ---: |
| Existing core baseline, including libgcc | 501,840 |
| Core + Player, old duplicate owners removed in temporary copies | 655,076 |
| Above + 521 actual LinkAnimationHeader records | 659,244 |
| Existing core carve + 40 KiB + 24 KiB low-RAM spans | 655,360 |

Baseline size exactly matches the existing ELF's end minus load address; hashes
of input objects, libgcc and that ELF are recorded. This verifies the measurement
baseline, not a new coherent full-game build. Player adds **153,236 B net**, more
than the standalone 143,437 B estimate because its dependencies retain additional
engine code. The 4,168 B animation headers already leave the original candidate
**3,884 B short**, before remaining backends, skeletons, frame buffers or region
alignment. C Link retirement gets no memory credit. Combined disassembly passes
the wide audit: 1,700 allowed hardware multiplies, zero failing sites.

Candidate placement design recorded at this checkpoint: **one statically linked
resident core across five regions**, retaining the core base/entry address.
Remeasure with the final W0a baseline before accepting this partition:

| Region (cached address) | Bytes | Intended use |
| --- | ---: | --- |
| 0x02770000 existing core carve | 589,824 | main core, remaining Player code/state |
| 0x0021D800 low-RAM gap | 40,960 | Player/engine code |
| 0x002FA000 low-RAM gap | 24,576 | Player/engine code |
| 0x026EC800 retired cart MUSICTRG reservation | 20,480 | Player readonly data/code overflow |
| 0x02683800 retired cart FAIRY reservation | 4,096 | small resident section group |

Total candidate capacity **679,936 B**; the historical probe left **20,692 B
before missing dependencies/alignment** with measured headers included. This
is not current W0a headroom. These are design
addresses, not installed allocations or proven final fit. Source audit finds no
runtime consumer of either retired cart reservation; main.c loads MUSICTRG into
RAM_LOW_MUSICTRG, and fairy rendering uses sprites. Existing ram_cart layout
guards are their only C references. Reuse requires explicit new names/guards,
not resizing RAM_CART_FIXED_BYTES or lowering heap/actor capacities. The tool
fails if a runtime source consumer of those old reservations appears.

Use one ELF for cross-region references; emit a payload per region, with an
explicit versioned load/zero table. Load/validate all regions at core boot,
initialize BSS, then run ctors/expose the entry. Never objcopy a flat binary
across address gaps. Regions stay resident through scenes; no CD reads during
Player actions. Do not rely on the existing one-carve loader's zero/size rules
for outlying sections. Input/camera adapters and C Link stay in current memory
while replacement acceptance is pending.

Before accepting placement: implement/size remaining engine hooks, real skeleton/
limb and animation-frame backing with explicit buffer budgets; partition actual
sections with alignment/assertions; complete a resolved link and loader/overlap
checks. This probe includes existing engine dependencies and real animation
headers; it is **not** full dependency closure. Unresolved lists also contain
existing linker-script/object-address symbols; their count is not a count of
missing engine functions. No live owner, carve, heap, blob or disc changed.

### Hooks + real skeletons sized (Claude, 2026-10-06)

`TARGET=1 HOOKS=1 check_player_migration.sh` runs `tools/size_player_hooks.py`
(-> `build/player-migration/hooks/report.json`). Live refs are read from
relocations in kept sections, because `nm -u` on an `ld -r` output also lists
names used only by dead code. Kept Player code references 46 hooks, 510 of 521
animations and 93 of 127 Link assets. guLookAt/guPerspective appear only in the
discarded pause draw: 0 B.

| Item | Owner | Bytes |
| --- | --- | ---: |
| Magic/Inventory/Item_CheckObtainability/func_800849EC (z_parameter), Health_IsCritical (z_lifemeter): 8 | real source, same-file closure | 2,124 |
| 6 further z_parameter deps not in live core | host bridge estimate | 252 |
| Audio 12, Camera 9, scene flow 10 (incl. gEntranceTable field), UI 2 = 33 | host adapters, 42 B mean of measured live HOST bridges | 1,386 |
| gObjectTable, DmaMgr, osCreateMesgQueue, Kaleido manager/call = 5 | Saturn resident dispatch, same estimate | 210 |
| object_link_boy + object_link_child blobs (real skeleton/limbs, 267 + 237 one-word DL/texture keys) | existing object pipeline + object.ld | 4,912 |
| **Total** | | **8,884** |

Against that checkpoint's 20,692 B slack: about **11,808 B left**, before frame
bank, alignment and adapter growth. This estimate predates W0a and must be
remeasured. It assumed both age skeletons resident (2,576 adult
alone). Real sources not used: z_scene_table 6,224 B and object_table 3,216 B
(adapters replace them). z_camera, z_kankyo and z_scene do not compile yet;
they are host-owned anyway, so not needed. The 42 B mean is from simple
forwarders: camera/scene adapters may be larger, and their C side lives in main
RAM (not counted here). Still estimates, not a resolved link.

### Frame bank budget (Claude, 2026-10-06) — DOES NOT FIT

`FRAMES=1 check_player_migration.sh` -> `tools/size_player_frames.py` ->
`build/player-migration/frames.json`. 134 B/frame (22 Vec3s incl. root + face).
Root motion = joint 0 of each frame (0 extra B); blend/morph tables are Player
struct fields (in core size). Aliased headers counted once.

| Set | Bytes |
| --- | ---: |
| All headers | 2,510,222 |
| Reachable from kept Player code (510 headers) | 2,261,518 |
| Child bank (shared + child-only) | 2,204,166 |
| Adult bank | 2,261,518 |
| Transactional swap peak (both banks) | 4,465,684 |
| Current C bank (LINKANIM/ADULTANM, jo heap) | 423,472 |
| Current swap peak | 846,944 |

Age split saves only ~57 KB: nearly every clip is shared. Compression probes on
the real ROM data: int8 deltas fit 73.6% of channel steps; keyframe-8 + int8
delta = 2,000,231 B; zlib whole segment = 1,452,440 B (and kills random
access). By name: cutscene/demo/ocarina/get-item-style clips 634,356 B,
everything else 1,875,866 B. **Raw or lossless frames cannot fit the existing
allocation.** Step 3 (sections + loader) stays blocked until a frame-bank
design fits; decision for human/Astra. Measured levers, still need picking:
8-bit angles (74 B/frame, ~55%); cutscene clips loaded per scene behind the
loading screen (not mid-play); every-other-frame with source morph between kept
frames (~50%, Saturn cut). Example stack: gameplay 1,875,866 x 0.55 x 0.5 ~=
516 KB resident, still above 423,472 B, no swap needed if age-shared. Missing
clip at runtime must fail loud (AnimTaskQueue_AddLoadPlayerFrame adapter).

### Shared frame-bank prototype (Claude, 2026-10-06) — still NO FIT

`tools/build_player_frame_bank.py` (offline, ~90 s in WSL) ->
`build/player-migration/frame_bank*.json`. One shared bank, each source data
array once; no age banks.

Residency comes from real triggers, not names. Clips reachable from Player
Init/Update/Draw/Destroy without going through the cutscene action tables are
global. Cutscene-action clips are global if any actor, lib or Player code
outside those tables can start that action. They go into a scene pack only when
that scene's own cutscene data cues them (CS_PLAYER_CUE -> sCueToCsActionMap).
Anything unclassified stays resident. Result: 474 of 510 clips resident, 18
scene packs (largest link_home 49,667 B; then spot00 17,696; tokinoma 17,533).
1 clip has no start site at all.

Encoding: fixed-width frames, one block per clip, any frame readable directly.
Root translation and face word stored every source frame at full precision, so
duration, event frames, root motion and face are unchanged. Only the 63 limb
rotation channels are reduced: 16/12/10/8 bits and/or keep every 2nd or 3rd
pose, with explicit shortest-arc interpolation in the reference `decode()`.
Each clip gets the cheapest encoding that passes. Pass = every frame, both real
skeletons (T·Rz·Ry·Rx), every limb origin plus a blade point on each hand
within tolerance. Clips that fail every reduction keep full precision.

Complete budget = resident + worst scene pack + 12 B/clip lookup table + 804 B
decoder scratch. Transition peak = resident + two largest packs (old pack kept
for rollback).

| Anchor tolerance (world units) | Resident | Transition peak |
| --- | ---: | ---: |
| 0.5 (mostly 10-bit, every frame) | 1,164,594 | 1,238,881 |
| 1.0 | 941,580 | 1,008,464 |
| 2.0 | 851,203 | 911,927 |
| raw reference | 2,021,524 | — |

Existing allocation: LINKANIM 423,472 B steady, 846,944 B during today's era
swap. **No tolerance fits 423,472 B.** At 2.0 units the peak is close to today's
swap peak, but staying at that size steady takes more heap than now, which is
forbidden. Stride/precision results show anchors need rotation bits: most
clips reject stride > 1 at 0.5 units.

Remaining measured levers (no new RAM): lossless root+face packing. Face = 1
byte exact; root = int8 delta with escape. Root+face is 8 B x ~16.8k frames
≈ 135 KB, so maybe ~80 KB saved. Not enough on its own. Fit needs a memory
decision (an extra verified free region not already counted for Player code)
or a looser per-move tolerance with in-game checks of climb/ledge/weapon
moves. Decoder/adapter not implemented; nothing installed.

### Packed bank v1: real bytes, source anchors (Claude, 2026-10-06) — NO FIT yet

Fixed anchor check. The old 1,304/695 blade guess is gone. Each frame is now
checked against z_player_lib.c limb-local points on both skeletons:
- left hand: sword tip 0 at x = 3000/4000/5500 (all lengths, both ages), fixed
  tips 1/2 (5000), three blade bases, held actor (398,1419,244)
- right hand: shield quad (4 vertices), D_80126184/D_80126190
- sheath: back-shield quad
- head: focus point
- feet: foot point (age-specific) and footprint (0,-300,0)
- plus every limb origin
Tolerance unchanged: 0.5 world units. Root, face, duration and event frames
stay exact.

Format: `tools/player_frame_pack.py`. One independent block per clip, so any
frame decodes with bounded work (stream A once, at most two poses). Each of the
67 channels gets its own circular base and bit width; constant channels cost
0 stream bits. Rotations may be quantised per clip (16..8 bits) or keep every
2nd/3rd pose. Interpolation is explicit shortest-arc with C truncating
division, identical in Python and C.

Real bytes emitted to `build/player-migration/bank/`: RESIDENT.PFB plus one
S_<scene>.PFB per scene ('PFB1', count, u32 offsets, blocks, 4 B tail pad).
Round trips:
- Python byte decoder == reference for all 510 data arrays.
- C decoder `oot-core/tests/player_frame_decode.c` (host) matches every value of
  all 474 resident clips / 15,086 frames.
- SH-2 `-O2 -m2`: 684 B code, wide audit 0 sites. Calls are pfb_pose and
  32-bit divide helpers.
- Cost estimate from code (not timed on hardware): ~1.6k instructions per pose.
  An interpolated frame = 2 poses + 63 divides. A per-frame reciprocal would
  remove the divides.

| 0.5 world-unit tolerance | Bytes |
| --- | ---: |
| Raw reachable | 2,261,518 |
| Per-channel range packing, all clips | 759,516 |
| Same with 8-pose delta blocks (measured size, not emitted) | 661,058 |
| RESIDENT.PFB file (474 clips) | 688,548 |
| Largest scene pack (link_home) | 35,656 |
| Lookup (u16 per header) + decoder scratch | 1,020 + 804 |
| Worst scene | 726,028 |
| Transition peak (two largest packs) | 737,644 |
| Existing LINKANIM block | 423,472 |

Down from 1,238,881 at the same tolerance with stricter anchors. Delta blocks
would save about 13% more (~600 KB resident estimate). Still about 180-310 KB
over the existing block. Encodings chosen: mostly 12-bit every frame (282) or
10-bit every frame (153). Weapon/shield anchors are why lower bits fail.

### Delta blocks + per-channel shifts (Grok, 2026-10-06) — still NO FIT

Emitted format in `tools/player_frame_pack.py`. Each clip is independent.
Kept poses are groups of 8: one absolute pose plus signed per-channel deltas.
Random access reads one group (at most 7 deltas) and, for in-between frames,
two kept poses. Root, face, duration and event frames stay exact. Each of the
63 rotation channels has its own shift (8/10/12/14/16). Pass is still every
source anchor within 0.5 world units on both skeletons.

Scene packs now include an action only when every actor that starts it has a
proven spawn/alt-header/room list, or a proven parent spawn chain. Unknown
actors stay resident. No clip dropped. One unreachable header remains
(`gPlayerAnim_clink_demo_get1`).

| 0.5 world-unit tolerance | Bytes |
| --- | ---: |
| Packed delta blocks, all reachable arrays | 755,156 |
| RESIDENT.PFB (439 clips) | 653,616 |
| Largest scene pack (link_home) | 32,628 |
| Lookup + decoder scratch | 1,020 + 804 |
| Worst scene | 688,068 |
| Transition peak | 710,632 |
| Existing LINKANIM block | 423,472 |
| Shortfall, worst scene | 264,596 |

Round trip: Python byte decoder matched every encoded frame (mismatches []).
Host C decoder matched ALL.PFB: 509 clips, 16,837 frames. SH-2 `-O2 -m2`
text 928 B. Relocs: `___udivsi3`, `___sdivsi3`, `___ashlsi3_r0`,
`___lshrsi3_r0`. Hardware multiply via `sts macl`. No soft-float, no
`___muldi3`. Not timed on hardware. Interpolated frames still divide.

Stride mix: 435 at stride 1, 26 at stride 2, 49 at stride 3. Channel-shift
counts across clips: 8-bit 10,891, 10-bit 7,974, 12-bit 13,226, 14-bit 39,
16-bit 0. Most combat clips still need stride 1.

Blocker: this measured format does not fit 423,472 B. Sections, loader and
real Player cutover stay blocked. No new RAM, no dropped moves, no looser
tolerance. Next decision is a memory source or a per-move tolerance the human
accepts after in-game checks.

### Blame-based precision + action context (Claude, 2026-10-06, Astra revised direction)

Two selection bugs fixed in `tools/build_player_frame_bank.py`:

1. Precision search. Old `choose()` raised every channel with any error at once.
   New search computes, for each anchor over its limit, blame per rotation
   channel = that channel's angular error at that frame x its lever (limb
   origin to anchor), only over limbs that actually move that anchor. Each
   round raises the 3 most blamed channels by 2 bits. Test: a clip moving
   only limb 15 raises only limb-15 channels.
2. Anchor sets per action. Sword lengths per age (child 3000; adult 4000 and
   5500). Weapon anchors stay gameplay-tight only for clips used by code that
   turns the melee weapon on (`func_80833A20` non-zero, `func_80837918`,
   `D_80854190` attack table, or tables those read); 75 data arrays.
   Held-actor anchors stay tight for carry code (34). Clips referenced from
   z_player_lib or unknown code stay fully tight. Always tight: limb origins
   (bodyPartsPos), focus, feet, both shield quads. Age-only clips use one
   skeleton (9 adult-only). Other anchors use a visual limit.

Root, face, duration and event frames stay exact. Bytes emitted, Python
mismatches none, C decoder PASS 509 clips / 16,837 frames for both runs.

| Run | Worst scene | Transition peak | Resident file |
| --- | ---: | ---: | ---: |
| Grok (old search, 0.5 everywhere) | 688,068 | 710,632 | 653,616 |
| Blame search, 0.5 on every anchor | 552,756 | 571,908 | 525,852 |
| Blame + action context (0.5 gameplay, 2.0 visual) | 531,876 | 550,368 | 506,196 |

Correct selection alone saves 135 KB with no accuracy change.

**Same lifecycle stage, worst scene, normal play.**
- Old system: LINKANIM 423,472 + C collision 129,670 = 553,142 B. Collision
  verified in source: scene buffer 2,321 x 38 + tables = 94,854 (scene_flow.c
  `SCENE_COLLISION_BYTES`, jo heap), index 16,384 (jo heap), dyna carve 18,432
  (`RAM_CART_DYNA_BYTES`).
- New system, core collision only: 552,756 (strict) / 531,876 (context).
- Strict fits by 386 B; context leaves 21,266 B. Both are before adapter code
  and the remaining collision-caller ports.

The saving is real only once every C collision caller uses core bgcheck.
Callers today: recomp.c, recomp_camera.c, recomp_collision.c, scene_flow.c,
main.c, link_anim_state.c, player_climb.c, player_crawl.c, push_block.c,
oot_core_host.c, kokiri_sgl.c, dekubaba.c, gohma.c, gohma_larva.c,
skulltula.c, dungeon_puzzles.c, dungeon_torches.c, dungeon_webs.c,
tree_mouth.c, wall_skull.c. Old playable build stays as rollback; both
complete systems never need to be resident together.

Not proven yet: era-switch peak at the same stage (scene loader frees assets
first; measure in the integration build), adapter/port code size, the 2.0
visual limit (human eye check), SH-2 decode time.

Next (integration, not more codec work): section partition + loader per the
five-region design, frame-bank adapter (`AnimTaskQueue_AddLoadPlayerFrame`
-> `PlayerFrameBank_Decode`, missing clip fails loud), and collision-caller
port list with sizes. Final fit is proven by the resolved link and runtime.

### Isolated integration step 1 (Claude, 2026-10-06, Astra GO)

Classification fix: uncertain stays strict. Weapon and held-actor anchors are
now tight for every clip reachable from ordinary Player actions (418 data
arrays). Only clips reachable solely through the cutscene action tables are
relaxed. That rule is a CANDIDATE pending call/state-flow proof that the weapon
collider is off in cutscene actions. Strict bank = integration reference.
Global bank ids: file format PFB2 carries a u16 id per clip; `ids.json` maps
each LinkAnimationHeader to its id (importer writes it into `.segment`).

| Bank | Resident file | Worst scene | Old same stage |
| --- | ---: | ---: | ---: |
| Strict (reference) | 526,732 | 554,668 | 553,142 |
| Candidate (cs-only relaxed) | 525,148 | 551,860 | 553,142 |

Placement against real allocations (`tools/place_frame_bank.py`; old sizes
intended for reuse at the same lifecycle points; fragmentation/lifetime proof
remains open).
Resident chunks: LINKANIM heap 423,472 / collision heap 94,854 / index heap
16,384 / dyna carve 18,432. Scene packs live in the LINKANIM block tail.
- Strict: worst pack 25,092 fits the 26,348 tail.
- Candidate: 23,868 fits 27,932.
- Rollback that keeps old and new scene packs in RAM together does NOT fit
  (needs about 44 KB). Proposed: on a failed new-pack load, reload the old
  pack from disc during the same loading screen (no CD during play). Needs
  approval. This proposal is now approved under the Astra review above.
- The era switch no longer reloads frames: one shared bank serves both ages.
  Today's 2x LINKANIM swap peak goes away.

Adapter `oot-core/src/player_frame_bank.cpp` (not in live sources):
- Validates a whole bank before publishing any slot.
- Per-id slot table; scene pack unregister.
- `AnimTaskQueue_AddLoadPlayerFrame` replacement under `PFB_CORE`.
- Missing id / bad frame / bad header go to `PlayerFrameBank_Fail` (loud).
- Host test `oot-core/tests/player_frame_bank_test.cpp` (both banks, resident
  + 32 packs): every registered frame matches; the one untriggered id fails
  loud; frame overrun and unloaded pack fail loud.
- SH-2: 480 B text + 2,184 B bss.

Loader `src/oot_core_regions.c/.h` (not in makefile SRCS):
- 'ORG1' table, five allowed spans.
- Validates every region (inside a span, 4-aligned, no overlap, BSS in the
  main carve and not covered) before copying anything, then copies and zeroes
  BSS.
- Host test: good load, and five bad files leave memory untouched.
- SH-2: 877 B. Wide audit 0 sites.

Partition `tools/partition_core_regions.py` -> `build/player-migration/regions/`
(regions.json + oot-core-regions.ld). Input: Astra's GC map of
core+Player+anim headers, 664,763 B in 3,461 sections. Entry/data/ctors/
keep_ph/bss stay in the main carve; text/rodata fill LOWA 40,960, LOWB 24,576,
MUSIC 20,480, FAIRY 4,096 completely. Main carve: 587,310 used incl. 12,332
reserved (hook adapters 8,884 est., slot table, adapter code); 2,514 B free
in that historical partition. W0a invalidates this as a current free-space
claim; regenerate from the final matching core objects before Player placement.
Plan only, not a resolved link. Relative Low RAM/cart execution cost is
unmeasured; compare target timing.

Collision ports `tools/collision_port_list.py` -> `collision_ports.json`:
22 files, 110 call sites. Visible C library code 4,072 B (LTO lower bound).
- Retire with source Player (not ported): recomp.c Link paths (31),
  player_bg/climb/crawl/slope/water/camera, link_anim_state.
- Port to core bgcheck through new core API entries (bg_floor, bg_wall,
  bg_surface, bg_water, dyna):
  - dungeon_webs 13, dungeon_puzzles 12 (incl. water surface), push_block 9,
    tree_mouth 3, oot_core_host dyna bridge 4, scene_flow 6 (load)
  - recomp_camera / player_camera floor
  - enemies and bosses: dekubaba, gohma, gohma_larva, skulltula, wall_skull
  - kokiri_sgl, main.c spawn
- C dyna props must become core DynaPoly actors (host-owned BgActor proxy)
  before the dyna carve is freed.

Next: core collision API entries + port the non-Player callers (camera and
bosses included), then the resolved whole build: real allocation peaks, era
rollback, decoder timing; then strict-vs-candidate in-game comparison.

### Adapter hardening + approved rollback (Claude, 2026-10-06)

`PlayerFrameBank_Register` now proves every decoder input before publishing:
- header counts (frames, kept vs stride grid, blocks vs blockK)
- stride/blockK non-zero; per-channel shift even and <= 8
- widths <= 16 - shift, delta widths <= 17 - shift
- pad bytes zero; exact block-table bit offsets
- stream A/B sizes inside the block; 32-bit window inside the file
- offsets increasing; ids in range; no duplicate id in a file; no id another
  registered bank owns (no silent resident/pack replacement)
Harness refuses 13 corrupted/duplicate banks and publishes nothing. Real banks
still decode exactly, one scene pack at a time.

Scene-pack change follows the approved rules
(`PlayerFrameBank_ChangeScenePack`). Caller pauses animation consumers; Load
fails loud during the swap. Old slots are unregistered before the overwrite;
the new pack is validated before commit (0). On failure the old pack is
reloaded from disc and re-registered (1: caller restores matching scene
state). If that also fails (-1), the bank stays stopped and the caller stays
on the error/loading screen. Tested: commit, rollback, double failure.

Corrections to earlier claims (Astra review):
- Same-sized chunks do NOT prove heap fragmentation unchanged. Allocation
  order, lifetime and temporary buffers matter; measure in the real build.
- "Low work RAM executes slower than the cart" was NOT measured. Time it.
- Strict bank is the integration reference. Cutscene-only relaxation stays
  experimental until gameplay effects are checked.
- Partition fit excludes final decoder, loader, adapters and allocation
  overhead. No production-fit claim.

### Cache handles + real cutscene sets (Claude, 2026-10-06, Astra review fixes)

`player_anim_cache.cpp` now works in one handle per action/cutscene:
- `Open(ids)` validates the whole set first. Unknown or failed clips are
  rejected, and so are sets that can never fit (bytes > arena or > 64 entries:
  TOO_BIG, fix the budget). Nothing loads for a rejected set.
- `Reserve(h)` is all-or-nothing. It allocates every missing member in one
  call, evicting only unpinned warm clips, and pins every member from that
  moment. A set that fits but is blocked by other handles' pins returns WAIT
  and issues no reads.
- `Poll(h)` returns READY / LOADING / error and never adds pins.
- `Close(h)` releases or cancels: unpins, keeps ready clips warm, frees failed
  ones.
- Init takes the manifest buffer length and validates every archive range
  (after header, non-empty, at least a descriptor, inside the archive) before
  any allocation or read.
Harness: manifest corruption refused; impossible sets refused with zero reads;
200 flood handles never evicted an early-finished member of a pending set;
contention waits and proceeds after close; pinned bytes equal exactly the open
set (polling adds none) and 0 after close; corrupt and I/O errors stay
distinct and are never published. SH-2: 3,240 B text, 2,944 B bss.

Real cutscene manifests (`tools/cutscene_clip_sets.py`, strict bank;
102 CutsceneData arrays from scenes and actors; all cues and branches):
- Cutscene-only clips (reached only through cutscene action code): largest
  link_home wake-up 27,260 B / 8 clips; most entries 21 (Temple of Time first
  adult). All 102 fit a 64 KB arena and the 64-entry limit.
- But cutscene actions also call the shared Player update, which statically
  reaches ~395-399 ordinary gameplay clips (~470 KB). Those must come from the
  common resident set, or a finer cue/state analysis must narrow them, before
  a cutscene handle can be called complete. Common-set inventory is therefore
  a prerequisite; static reachability alone over-approximates it.
Production demand loading stays pending: common set, CD/audio servicing and
Player start gates are not wired.

### Core collision queries + Fx line-test fix (Claude, 2026-10-06)

`oot-core/src/oot_core_bg.cpp` (isolated) answers the C contract of
`kokiri_collision.h` (floor / wall / ceiling / line / water, hit = poly, owner,
raw SurfaceType) with the real z_bgcheck. Next step: a C `bg_*` shim calls
these, so callers stay unchanged and the C storage can be dropped (dyna props
still need core DynaPoly proxies).

Parity probe `oot-core/tests/run_bg_port_probe.sh`: same Kokiri Forest scene
through the C library (S1.COL) and the core (S1 blob). Built twice: fx = Saturn
Q16.16 core, hw = same source on host floats.

**Severe live-core bug found and fixed.**
`CollisionPoly_LineVsPoly` and `CollisionPoly_GetPointDistanceFromPlane`
multiplied the raw s16 normal (+-32767) by a world position before the trailing
`* COLPOLY_NORMAL_FRAC`. Q16.16 saturated and plane distances were garbage: Fx
the pre-fix probe reported 765/1589 line mismatches against C (not a direct
Fx-versus-float comparison). This affects
every core user of line tests and point-plane distance today (wall checks
too). Fix: source-scoped importer rewrite in MACRO_REWRITES
(`src/code/z_bgcheck.c`) scaling each normal component first
(`COLPOLY_GET_NORMAL`). Fails closed if the source changes.

| Probe, 1,589 samples | fx before | fx after | hw float |
| --- | ---: | ---: | ---: |
| Line mismatches vs C | 765 | 105 | 88 |
| Wall mismatches vs C | 144 | 41 | 45 |
| Ceiling | 4 | 4 | 3 |
| Floor height > 1 (of 4,959) | 82 | 82 | 75 |

Separate Fx/float mismatch totals improved but do not establish per-query
agreement. Residual causes remain unclassified; compare identical inputs
directly before attributing differences to the C library. The existing floor probe is
unchanged (277/5005 over tolerance before and after; floors don't use these
paths). test_core_bgcheck / test_core_dyna / test_player_migration: 22 pass.
**Live impact:** the next Clean build's core gets the normal-first scaling fix.
Full query correctness remains unverified. No Clean rebuild or runtime check done yet;
watch line-of-sight, hookshot, camera and wall behaviour of core actors.

### Collision parity redone + dyna contract (Claude, 2026-10-06, Astra review)

Probe fixed: every query now uses identical inputs (all coordinates derive
from the C floor, which is the same in both builds). Rows carry hit, position,
owner, poly and raw surface for C and core. `compare_bg_port.py` compares per
query, three pairs (Kokiri Forest; floors 4,959, others 1,589 each):

| | Floor | Wall | Ceiling | Line |
| --- | ---: | ---: | ---: | ---: |
| fx vs hw (Fx error only) | 0 | 7 | 0 | 3 |
| C vs hw (C library vs real source) | 89 | 42 | 2 | 26 |
| C vs fx (what porting changes) | 96 | 40 | 3 | 26 |

Fx-vs-float differences are now small. Mostly 1-2 unit wall push-outs and
shared-edge poly picks; one line test misses where float hits. The earlier
"Fx matches float" claim came from separate inputs and is withdrawn; this
table replaces it.
C-vs-source floors: 65 of 89 are the same polygon and surface 2 units apart,
mostly steep ground-facing wall polys; ~10 pick a different polygon at shared
edges with the same surface; 1 differs in surface. Partly explained (C plane
math/rounding vs source), not fully proven. Walls and lines show the same mix
plus 6 / 2 hit-miss cases. Ported callers get source behaviour there; check
in game.

Dynamic polygon contract fixed: `OotCoreBg_*` reported the index in the shared
dyna pool. Now index inside the owner's mesh (pool index - owner's
polyStartIndex). `bg_dyna_probe.cpp` (real DynaPoly, real z_skin_matrix):
two owners, the second's mesh at pool index 2 reports poly 0/1; owner removal
moves it to the pool start and ids stay; a new owner reusing the freed slot
reports its own polys; the removed place no longer hits. PASS.

Second live-core Fx bug found by that probe and fixed: dyna poly normals were
normalised by multiplying with 1/|n|. For long edges the reciprocal is a few
raw Q16 units and truncates (flat 200-unit floor: normal.y 0.906, dist -2719
instead of -3000). That skewed slope tests and plane distances for every
DynaPoly actor with large polys. Importer now divides (MACRO_REWRITES,
z_bgcheck.c, fail-closed). Probe asserts unit normal and exact distance.
Host stubs no-op'd SkinMatrix, which hid this: the dyna probe links the real
z_skin_matrix (`BG_REAL_SKIN_MATRIX`). All tests pass: core bgcheck/dyna/
migration and the floor probe (unchanged).
Live impact (next Clean build): correct dyna normals/distances. Runtime check
pending: platforms, elevators, Kakariko gallery bridge.

### C bg_* shim + DynaPoly proxies + third Fx fix (Claude, 2026-10-06)

New, all isolated (not in live SRCS/blob):
- `oot-core/include/oot_core_bg.h`: one core collision API table.
  Floor/wall/ceiling/line, water level set/reset, poly vertices/plane,
  scene water + bgCam data, DynaPoly proxies (register/set/enable/remove),
  rider carry (source DynaPolyActor_UpdateCarriedActorPos/RotY), step/update.
- `oot-core/src/oot_core_bg.cpp` implements it on the real z_bgcheck.
  Proxies convert C meshes once into CollisionHeaders in a static store
  (192 triangles, 64 surfaces). Proxy id = the core bgId that hits report.
- `src/bg_core_shim.c`: the C library's bg_* functions with the same
  signatures and the same miss contract (floor miss clears owner+surface;
  ceiling/line miss leave outputs alone; wall sets owner NONE first). Callers
  don't change. No scene buffer, no index, no dyna carve (bg_dyna_init ignores
  its buffer). Proxy changes take effect at the next query (lazy lookup
  rebuild).
  bg_scene_mesh() returns a view (water boxes + bgCams, no triangles).

Test (`run_bg_port_probe.sh` part 3): one bg_*-only scenario
(`bg_shim_scenario.c`) built with the C library and with the shim over the
core. 177 rows: flat platform, ramp rotated 45 degrees, 12-triangle box
rotated 30 degrees with an 81-point footprint scan, wall/line/ceiling on them,
rider carried 10 frames while the platform moves and turns, disable/enable,
removal, slot reuse.
- Core on host floats: 0 of 177 rows differ from C.
- Fx core: 1 row differs: platform corner point (local 20,20) falls through
  to the scene floor. Tracked as a known Fx case, printed every run, together
  with parity line ('L', 2981). Both still unexplained.

**Third live-core Fx bug found and fixed.** The rotated box vanished entirely
in the core. The DynaPoly bounding-sphere centre summed transformed vertices
in Fx: 18 vertices at y 2500 = 45,000 > Q16.16 max, so the centre saturated
(y 2500 -> 1819 -> 909 as triangles were added), and floors/walls of larger or
higher dyna meshes went missing. Importer now sums the stored integer
vertices in s32 and divides once (MACRO_REWRITES, z_bgcheck.c, fail-closed).
Live impact: every DynaPoly actor whose vertex count x height exceeds
~32,767 (platforms, elevators, bridges, Kakariko gallery). Runtime check
pending in the next Clean build.

Host-test traps fixed on the way: core `u32` is 64-bit `long` on Linux, so a
local struct copy of the hit with `u32` misread fields (use the shared header
with `unsigned int`). The new API needs z_bg_collect/z_bg_item/z_skin_matrix
in probe links; matching host stubs are guarded by BG_REAL_SKIN_MATRIX.
Remaining integration items: one owner of the dyna frame boundary (core Play
update vs bg_dyna_step), proxy store sizing per scene, then porting the
callers (camera and bosses included) and the real link.

### Proxy carry path, frame owner, scene reset, memory (Claude, 2026-10-06)

Astra review fixes, all isolated and host-tested:
- Real carry path: proxies now set `DynaPolyActor.transformFlags` (BG_DYNA_POS/
  ROT_Y = DYNA_TRANSFORM_*). C riders go through the same
  `DynaPolyActor_TransformCarriedActor` core riders (Player, actors) use; no
  private transform check is left. Rider rows still match C (10 frames moving
  + turning).
- One frame-step owner: `bg_core_shim_frame_owner(true)` in the game (core Play
  update owns prev = cur); `bg_dyna_step` then only flushes proxy changes.
  Tests drive frames themselves (false).
- Scene exit/re-entry: `bg_core_shim_scene_reset()` -> core `reset`: deletes
  every proxy, clears the bgId map, restores authored water levels; the shim
  forgets owned ids. Scenario checks: raised water back to authored after
  re-entry, old box and platform gone, fresh registration gets a clean slot and
  its surface.
- Memory, SH-2 -Os, measured:
  - core proxies (`oot_core_bg.o`): 4,942 B code + 11,638 B bss (16 proxy
    actors mapped from core bgIds, 128-triangle store, 64 surfaces)
  - shim (`bg_core_shim.o`): 2,084 B code + 760 B bss
  - C meshes are read in place at registration (no scratch copies)
  - Transformed copies use the core DynaPoly pool (512 polys / 512 vertices /
    1000 nodes, already allocated in the core play arena). Proxies now share
    it with core actors: count per scene before cutover.
  This isolated checkpoint measured replacement ~19.4 KB vs C storage
  129,670 B (+ C library code, ~4 KB LTO lower bound), about 110 KB net on
  paper. This is not an installed free region or current W0a allocation credit;
  remeasure the combined replacement and prove C storage retirement first.
Scenario: 185 rows, only the tracked Fx platform-corner case differs. Fx line
miss ('L', 2981) is also still open. Neither is explained yet.
All tests pass (test_player_migration incl. new collision-probe test, core
bgcheck/dyna).
Next: port callers onto the shim (link bg_core_shim.c instead of the C bg_*,
keep kokiri_collision_* Link wrappers until real Player), then the real link.

Paths below are relative to `game/`. Each row is a required preservation unit.
Tests are existing evidence/next regression targets, **not newly rerun passes**.
Unless explicitly accepted in the dated handoffs, implementation remains
runtime-unaccepted. This is the subsystem inventory; extracting every individual
test case and auditing every inline fix in the large gameplay/recomp files
remains an explicit prerequisite to cutting over the corresponding subsystem.

| Behavior/fix to preserve | Current source | Destination owner | Verification / known gap |
| --- | --- | --- | --- |
| A interact, X attack, Y jump; custom jump mapping; R shield | src/player_input.c, src/recomp.c, src/gameplay.c | Saturn input adapter feeds real Player; Y is explicit Saturn action extension | test_player_controls.py, test_player_attack.py; preserve HUD labels |
| B held walk; short tap cancel/put-away; claimed presses cannot act again on release | src/player_input.c | input adapter + source action dispatch | test_player_controls.py; no duplicate cancel/walk |
| Analog proportional movement and triggers; digital C+D-pad vs analog direct D-pad C; pause navigation/assignment | src/player_input.c | input adapter, UI ownership retained | test_player_controls.py; preserve edge/release counters across skipped core steps |
| 20 Hz core, render cadence, pause and closing-press consumption | src/oot_core_host.c, src/recomp.c | one core Player tick; host input latch | test_ocarina.py, test_core_views.py; audit catch-up and no-step frames before cutover |
| Right-handed world, screen-right negative X at yaw zero, recenter/target Z | src/player_camera.c, src/recomp_follow.c, src/recomp.c | Saturn camera reads core pose/focus | test_player_camera.py, test_player_controls.py; keep world units/yaw conversion |
| C-Up first person and house views; aim owns pad; L minimap | src/player_input.c, src/recomp_camera.c, src/gameplay.c | camera/UI adapters + source focus/aim | test_player_controls.py, test_room_visuals.py |
| Field overhead default; regular elsewhere; L+R+B two-view toggle; reversed Z/B+Z eased quarter-turns and UI tick | src/player_camera.c, src/recomp_camera.c, src/recomp.c | retained Saturn camera | test_player_camera.py, test_player_controls.py; human turn/ground/fade acceptance open |
| Ground movement, slopes, walls, ceilings, floor surface flags and departure history | src/player_bg.c, src/player_slope.c, src/recomp_collision.c | real Player + core z_bgcheck | test_player_bg.py, test_player_slope.py, test_core_bgcheck.py; one collision world still missing |
| Run-off auto-jump thresholds, shallow fall, jump hold, terminal gravity, short landing before roll; manual Y jump | src/player_air.c, src/link_anim_state.c, src/recomp.c | source Player actions + explicit Y extension | test_player_air.py, test_link_animation.py; age-specific thresholds required |
| Ledge hang/pull-up, root movement and blocked movement | src/player_bg.c, src/recomp.c, src/link_anim.c | source Player and animation movement adapter | test_player_bg.py, test_link_animation.py; migrate prior-contact semantics |
| Ladder/vine entry, alternating hands, end/let-go; child/adult special clips | src/player_climb.c, src/link_anim.c | source climb actions + Saturn pose/root adapter | test_player_climb.py; some adult specials currently child-authored |
| Child crawl enter/leave/reverse, tunnel dimensions and Enter prompt | src/player_crawl.c, src/recomp.c | source crawl actions + collision | test_player_crawl.py; preserve age gate |
| Push/pull, lift failure/strength, attach once, carry, throw/put; prop owns drops | src/player_push.c, src/player_lift.c, src/gameplay.c | source Player handshakes + actor owner | test_player_lift.py, test_gameplay.py; never duplicate release/reward |
| Water enter/leave hysteresis, age-specific float heights, stroke/dive/scales, guarded shore step-up with swim clip, underwater timer | src/player_water.c, src/gameplay.c | source Player and core WaterBox | test_player_water.py; gallery bridge omits water, cannot become final world |
| Sword combo/spin/jump and shield state, damage/invulnerability/knockback | src/gameplay.c, src/player_attack.h, src/recomp.c | source Player combat; retain Saturn hit anchors | test_player_attack.py, test_gameplay.py; proxy jump/spin damage flags incomplete |
| First sword frame hits only current blade, no sheath sweep; unchanged pose catch-up keeps hit active | oot-core/src/bridge_player.cpp, src/oot_core_host.c | source weapon collision with cadence-aware Saturn anchors | test_core_views.py, test_gameplay.py; re-evaluate timing against real Player, preserve outcome |
| Age/equipment sword damage, Biggoron two-handed, boots reflected to actors | oot-core/src/bridge_player.cpp, src/gameplay.c | source Player/save equipment | test_gameplay.py, test_core_save.py; no simultaneous proxy/source hit registration |
| Stick/slingshot/nut and ammo; bow/arrows/magic, bombs/Bombchu carry, boomerang, hookshot movement | src/player_items.c, src/gameplay.c, oot-core/src/bridge_items.cpp | real Player item actions; tool actors remain source | test_gameplay.py, test_item_aim.py, test_inventory_tools.py, test_core_update_rate.py and actual tool actor probe; source rate, finite quads, swept host contacts, carry ratio and source magic fallback repaired. C-only hook targets and full target feedback remain open; hammer/lens/spells/beans still deny |
| Iron underwater walk, Hover grace, tunics, sheath cooldown and stowing during special actions | src/gameplay.c, src/recomp.c | source equipment/actions + Saturn render selection | test_gameplay.py, test_equipment_draw.py; draw fixture repaired, seven checks pass including adult Biggoron/Mirror variants |
| Original child/adult mesh, matrix ownership, root correction, upper-body overlays, airborne origin, shield winding | src/link_anim.c, src/recomp.c, tools/build_adult_link.py, tools/build_link_model.py | retained Saturn renderer; source animation intent adapter | test_link_geometry_precision.py, test_link_shield.py, test_adult_link.py |
| Gear hands/back variants/boots, tunic masks, actor-first gear bank allocation and flat fallback | tools/build_link_gear.py, src/kokiri_sgl.c, src/recomp.c | retained Saturn gear renderer | test_equipment_draw.py, test_link_shield.py, test_inventory_tools.py; source-owned adult gear admission and missing-art/VRAM/slot fallback pass host tests, runtime acceptance open |
| Digital aim crosshair and source first-person hand/tool sprites | src/main.c, src/oot_core_host.c, src/npc_sprite.c, tools/build_item_sprites.py | retained Saturn aim/input/render adapters | test_item_aim.py, test_item_sprites.py; same tap/fire/cancel controls, no runtime tool mesh/skeleton; static source-pose art is approximate |
| Transactional era asset switch: validate/stage/fence then publish, rollback on failure, single resident bank | src/link_anim.c, src/recomp.c | Saturn age/render adapter, core age state commits once | test_adult_link.py; preserve low-RAM guards and original 672-poly adult |
| Talk range/focus, page reveal vs advance, choices, item grants/parent handshake and source drops | src/gameplay.c, oot-core/src/bridge_player.cpp, oot-core/src/bridge_message.cpp | source Player talk/get-item; message backend retained | test_core_dialogue.py, test_dialogue_core_handoff.py; instant proxy get-item lacks hold-up; C quest callbacks not yet source actors |
| Five Ocarina notes, B cancellation, source songs/warp restrictions, Saria hints, Sun reload | src/gameplay.c, src/oot_core_host.c, oot-core/src/bridge_message.cpp | source Player/message plus Saturn notes/audio | test_ocarina.py; source puzzle actors, dungeon Sun stun, Scarecrow/memory game missing |
| Added Song of Time bidirectional era shortcut, repeated use, failed-load rollback | src/gameplay.c, src/recomp.c | explicit Saturn extension after source song result | test_ocarina.py; Temple sword story travel remains missing |
| Inventory/quest/C assignments, hearts/HUD, save mirroring, test loadout isolation | src/save_state.c, src/save_file.c, src/gameplay.c, src/oot_core_host.c | core gameplay state; Saturn UI/persistence serialize once | test_core_save.py, test_save_state.py, test_save_file.py; capped items opt-in, no fake story flags |
| Damage/death/respawn, entrance/room change, failed warp request consumed and old scene restored | src/gameplay.c, src/recomp.c, src/scene_flow.c | source Player/scene state plus Saturn scene loading | test_gameplay.py, test_ocarina.py; full entrance graph and respawn parity audit open |
| Cutscene input lock, cues, skipping, equipment/pose restore and audio events | src/recomp.c, src/scene_flow.c, src/link_anim.c | source Player cue state + Saturn presentation | test_cutscenes.py, test_cutscene_skip.py, test_cutscene_parity.py; retain opening/story behavior |
| Dynamic contact bg IDs, moving/rotating platforms, switches, prior transforms, enable/delete | src/oot_core_host.c, shared/lib/collision (repo root), core z_bgcheck | shared core collision, C callers query adapter | test_core_dyna.py, test_core_bgcheck.py; gallery Y-only/X-scale bridge lacks rider feedback |

## Ownership/dependency cutover map

1. `z_player_call` provides the single Player_Profile. Its KaleidoManager
   relocation/loading must become explicit resident Saturn dispatch; syntax
   acceptance does not mean the overlay loader exists.
2. `z_player_lib` replaces duplicate Player functions in bridge_play and
   Player_UpdateWeaponInfo in bridge_player. List and resolve definitions
   before linking; do not suppress duplicate symbols or leave gameplay stubs.
3. `ovl_player_actor` supplies Init/Destroy/Update and the action machine.
   Link Draw remains Saturn. Source animation completion, root translation,
   body/weapon/held anchors and collision work normally performed in Draw
   must still execute at the correct cadence. A no-op Draw is not sufficient.
4. `oot_core_api.cpp` currently receives C pose/sword/save state; host and
   bridge_items also apply gameplay results. Replace these writes with
   explicit input and one-way core snapshots per migrated subsystem. Stop C
   movement, damage, item use and reward paths at ownership transfer.
5. `z_bgcheck` becomes the only collision storage/solver. Inventory C camera,
   prop, enemy and scene callers before removing their world. Preserve water,
   surface/camera metadata and dynamic contact history; query bridging alone
   does not complete Player migration.
6. Object/link animation assets, source registers, camera queries, message,
   audio, effects, save initialization and tool actors need dependency/link
   evidence. NPC sprite and boss rendering rules remain unchanged. No actor
   imports or renderer conversions are authorized by this staging step.

Remaining integration under the current demand-loading contract:
1. Remeasure combined core/Player retention and the candidate five-region
   design against the current inventory ELF/BIN and matching objects. The 659,244 B
   retention / 679,936 B capacity comparison is a historical checkpoint, not
   current fit. Include all retained dependencies and adapters, then regenerate
   section/loader guards and obtain a resolved link before fit acceptance.
   No heap reduction or speculative C-Link-retirement credit. Preserve actor
   capacities and Clean margin; budget cache/load/recovery storage explicitly.
2. Animation data: 521 gPlayerAnim_* need a Saturn link-animation bank (source
   anim headers/frames; reuse current Link anim conversion, not N64 DLs).
   Sizes (Claude, 2026-10-06): source frames = whole link_animetion ROM segment,
   2,513,968 B (22 Vec3s + face word = 134 B/frame). N64 DMAs one frame at a
   time. The historical baked LINKANIM.BIN covered 131 of 521 anims in
   423,472 B (per-age bank swap, decimated, Saturn pose format). That comparison
   does not define the required residency target. Implement the bounded common
   set, indexed demand loads and readiness/pinning contract above; preload every
   complete cutscene set before playback. Remeasure cache, metadata, decode/load
   scratch and recovery peaks with W0a consumers present. A cold known clip is a
   load request, not a missing asset; never advance an action without its data.
3. Resolve remaining 127 Link asset references by actual consumers. Preserve skeleton,
   pose and gameplay anchors; only unused DL/texture references may be placeholders
   after native draw execution is removed. Source actions also restore Draw.
4. Retire 9 duplicate live owners as each subsystem cuts over; resolve 46
   engine functions (Camera/Audio/Inventory/Kaleido dispatch etc).
Do not link into the playable profile until input, animation, collision and
state ownership are ready.
