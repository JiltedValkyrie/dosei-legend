# Plan: bulk decomp pipeline ("oot-core" on Saturn)

## Context
Hand-port 1 system at time -> guess behavior, bugs pile up (BUG log long). zeldaret/oot at
D:\Workspace-Claude\game-decomps\n64\oot already extracted (ntsc-1.2) + built. 456 actor .c.
Want: compile REAL decomp game code for SH-2 in bulk, convert float in bulk, convert all music
in bulk. Our Saturn renderer/audio stay as backend. 4 MB cart required -> code room exist.

## Hard truths (must design around)
- f32 everywhere (`typedef float f32` ultratypes.h:24). SH-2 no FPU. Soft-float = ~10x slow. Not ship.
- Fixed 16.16 overflow: OoT pos up to ±~10000 units, distSq overflow fast. Blind swap break math.
- Actors draw via N64 Gfx display lists (gSPDisplayList, matrices). Need shim, not VDP1 native.
- RAM: OoT code ~1 MB + overlays. Fit cart if overlays load per scene like N64.

## Status — Phase 0 (2026-10-02)
Code in place (host-verified, target compile-verified; runtime numbers pending human run):
- `tools/oot_core_import.py` mirrors decomp `include/`+`src/` headers and listed sources into
  `build/oot-core/decomp/` (`.c` -> `.cpp`). Mechanical fixups only, counted in
  `build/oot-core/import_report.txt`: float literals -> `FXL()`, MtxF/`_words`/CamParamData
  anonymous aggregates named, MIN/MAX/ABS/CLAMP -> `OOT_SEL`, xstdio long double.
- `oot-core/include/oot_prelude.h` (force-included): `float`/`double` -> `Fx`, C++ keyword renames
  (`this` etc.), `OOT_SEL` mixed-type ternary. `oot-core/shim/`: assert.h, math.h.
- `oot-core/include/fx.h`: **Fx = int64, Q39.24** (not 32-bit Q16.16). Reasons found by probe:
  decomp builds floats past s16 (`Rand_ZeroOne()*0xFFFF`, distSq ~1e8) -> 32-bit saturates;
  16 frac bits lose 6% on reciprocals (Math3D_DefPlane normal). Mul fast path 1 dmuls when both
  fit 32 bits, 2 when one does. All ops constexpr. (Phase 1: GCC 9 still emits ctors for some
  file-scope tables, so the blob runs its own ctor table from `OotCoreEntry.init`.)
- Replaced (float bit tricks / libc): `oot-core/src/oot_math.cpp` (sqrtf isqrt64, sinf/cosf Q30
  poly, floor/round...), `oot_rand.cpp` (qrand same LCG, mantissa -> exact Fx).
  NOTE: N64 `sintable` samples i*pi/(2*1023); do not interpolate it as /1024.
- Compiles for SH-2 (sh2eb-elf-g++ 14.3, linked by Jo gcc 9.3), **zero soft-float calls**:
  z_lib, sys_math, sys_math_atan, sys_math3d, math64, sins/coss, **z_actor, z_collision_check,
  z_bgcheck, z_en_item00, En_Kusa** (~240 KB text). Also syntax-clean: z_player, z_camera.
- Host probe `oot-core/tests/run_host_probe.sh`: 458 values (sin/cos/sqrt/atan2/dist/plane/
  SmoothStep/Approach/StepTo/Rand) Fx vs real float, **0 over tolerance, worst 0.017%**.
- Target: `./build.sh OOT_CORE=1` builds `OOTCORE.BIN` (Phase 0: 10.6 KB), linked at the
  cached cart alias (now 0x027C0000, carve RAM_CART_OOTCORE), loaded + cache-purged at boot, called via
  its entry table. Debug panel rows 13-14 show ns/call (ma dv ss / ds sn at). Work RAM untouched
  by decomp code (standard image 6,832 B spare). Default/Clean builds unchanged (flag off).
  This blob is the Phase 1 pattern: decomp code lives in the cart, not work RAM.

## Status — Phase 1 (2026-10-02): steps 2-3 linked, not run
- Carve 256 KB at 0x027C0000 (`RAM_CART_OOTCORE_BYTES` 0x40000, `RAM_CART_FIXED_BYTES` 0xC2400,
  makefile `OOT_CORE_LOAD_ADDR`/`OOT_CORE_MAX_BYTES`). Blob compiled **-Os**: 203 KB in carve
  (OOTCORE.BIN 170 KB; -O2 was 425 KB). 0 soft-float symbols. Standard image 6,832 B spare.
- Decomp file list lives ONLY in `tools/oot_core_import.py` SOURCES; importer writes
  `build/oot-core/sources.mk`, makefile includes it. Linked now: z_actor, z_collision_check,
  z_bgcheck, z_en_item00, En_Kusa + batch 1/2 leaf systems: sys_matrix, z_skin_matrix,
  TwoHeadArena, z_lights, z_eff_ss_dead, z_bg_collect, z_bg_item, z_inventory, z_rcp,
  lookathil, mtxutil, z_effect, z_effect_soft_sprite(+old_init), z_eff_blure/spark/shield_particle,
  z_malloc, __osMalloc_n64.
- `oot_core_roots.cpp`: pointer table that keeps Actor_InitContext/UpdateAll/DrawAll/Spawn,
  BgCheck_Allocate, CollisionCheck_AT/OC, En_Kusa/En_Item00 profiles alive under gc. Step 4
  replaces it with the real API.
- Bridges (`oot-core/src/`): `bridge_tables.cpp` actor + effect-ss overlay tables built from
  the decomp table headers, all entries internal, **weak profiles** (import a file = registered;
  not imported = NULL profile, spawn must check). `bridge_play.cpp` REAL/HOST/STUB tagged:
  Play_GetCamera/ActiveCamId real; Item_Give, Health_ChangeBy, sfx -> `OotCoreHost`
  (`oot-core/include/oot_core_host.h`, global `gOotCoreHost`, not wired yet); Object_* = always
  loaded; Overlay_Load/Fault/os*/Player_* (InCsMode, ExplosiveHeld, ReleaseLockOn)/Magic_Reset/
  GetItem_Draw/Camera_RequestMode stubs. `bridge_assets.cpp`: 41 one-word placeholder asset
  symbols (gameplay_keep DLs/textures, object_kusa DLs) = draw-shim keys. `bridge_libc.cpp`.
- gSaveContext and gSegments are defined in bridge_play (zeroed). C side must fill what
  actors read (e.g. save inventory) before step 5.
- **Step 4/5 hazard:** Actor_UpdateAll and most actors read GET_PLAYER(play). Our Link is C,
  so step 4 needs a proxy Player actor in the PLAYER category, synced from C Link each frame.

## Status — Phase 1 step 4 (2026-10-02): built, runtime pending
- Kronos fix: Kronos fetched code only from 0x020xxxxx in CS0 -> blob hung after SEGA logo.
  `build/kronos-fix/kronos.exe` (BUILD.md 26). Boot now reaches title (human, 2026-10-02).
- API `oot-core/include/oot_core_api.h` (entry v3): init(host), play_bytes, play_init(block,
  scene, colHeader, player pos/yaw), set_player, update, draw (no-op until Phase 2), spawn
  (refuses non-imported ids), actor_count. `oot-core/src/oot_core_api.cpp` follows z_play
  Play_Init/Play_Update order for systems we have (lights, effects, effect-ss, colchk,
  bgcheck, actor ctx; AT/OC/Damage/Clear, Actor_UpdateAll, Effect/EffectSs_UpdateAll).
  gRegEditor now points at a real RegEditor (REG macros deref it).
- Player proxy `oot-core/src/bridge_player.cpp`: Player_Profile with real header, update copies
  C Link feet pos/yaw. Focus height 40 is APPROXIMATE. Yaw convention C vs OoT not verified.
- Play block (PlayState 78 KB + THA 192 KB + ZeldaArena 128 KB) in low work RAM carve
  RAM_LOW_OOTPLAY (0x71500, 0x64000; OOT_CORE builds only).
- Scene collision: importer SCENE_COLLISION cuts the CollisionHeader + arrays verbatim out of
  extracted `spot04_scene.c` -> `SPT04COL.BIN` (34 KB, 1692 polys) linked at 0x02780000
  (`oot-core/scenecol.ld`, carve RAM_CART_SCENECOL 256 KB before OOTCORE; OOTCORE address
  unchanged). Passed to BgCheck_Allocate.
- Host `src/oot_core_host.c`: boot loads both blobs, init, bench. `oot_core_frame()` after
  gameplay_step (30 Hz): in Kokiri Forest only, play_init on entry, set_player, update on 2 of
  every 3 steps (decomp = 20 Hz). Debug row 15: `oc p<playing> pl pr mi` actor counts.
  Expected in Kokiri: `oc p1 pl1 pr0 mi0`. Host callbacks still NULL.
- Next = step 5: spawn En_Kusa from Kokiri's room actor list, wire OotCoreHost (sfx,
  give_item, health) to action_audio/save, hide the matching world_props grass.

**Gate numbers (human, Kronos kronos-fix, Debug, -Os, blob in cart) 2026-10-02:** ns/call
ma 8582, dv 20901, ss 15864, ds 59799, sn 49818, at 28630. ~240 cycles for one Fx mul-add:
far too slow for bulk actors. Unknown split: cart (A-bus) code fetch / Kronos timing vs Fx
cost. Next: rerun the same bench from work RAM (low WRAM) to separate them before step 4.

Open / next:
- Human: run OOT_CORE=1 Debug build, read rows 13-14 (gate numbers). See NEXT SESSION below.
  Blob is -Os now: numbers from this build supersede any earlier -O2 reading.
- ROM data holding IEEE floats (CutsceneCameraPoint.viewAngle, some cutscene cmds) must be
  converted to Fx offline when that data is loaded.
- Asset headers come from `extracted/ntsc-1.2`; decomp `build/` only has ntsc-1.1 objects.
- SaturnMath++ (MIT, github robertoduarte/SaturnMathPP, clone ../../SaturnMathPP @8bdc355) is
  32-bit-only fixed point (16.16/24.8/8.24) -> cannot hold decomp floats; NOT the Fx type.
  Borrowed: its SH-2 divider register pattern -> `fx_div` hardware path when |quotient| < 2^30
  in Q24 (else libgcc __divdi3). Target-only; runtime unverified. Not interrupt-safe if an ISR
  uses the divider. Candidates later: its trig/atan2 LUTs if bench shows sinf/atan slow;
  Vector/Matrix/Frustum for Saturn-side renderer/draw shim (needs C++23).
- Work RAM: solved by the OOTCORE.BIN cart blob (carve 256 KB at 0x027C0000, 203 KB used).
  Grow it (src/ram_cart.h OOTCORE + FIXED bytes, makefile LOAD_ADDR/MAX_BYTES together; ram_cart.c
  checks the address) as actors are added. Each 64 KB taken shrinks bank-2 jo_malloc space.

## ALL SCENES (2026-10-02, human request "create every map and room, add to level select")
Build only, runtime NOT checked. Level select (title secret menu) now cycles 75 scenes
(11 slice + 64 generic, ids 11..74, names from SceneId). Pipeline: tools/build_all_scenes.py
(generic mode: segments 06-0D fallback = black texture/empty DL, room G_MTX ignored, G_BRANCH_Z
walked: all APPROXIMATE) -> build_scene_table.py _extra_scenes (caps filter) -> build_room_scene
copies banks. Generic scenes: save id SAVE_SCENE_COUNT+n (no persistent flags), doors between
registered scenes resolve from ROM exits, En_Door/other room transitions skipped (rooms only via
level select), image rooms use the shop RGB backdrop path (multi-bg: first picture only),
no actors, Kokiri music/sfx defaults. Not registered (26): see build/all-scenes/registered.json:
collision over 2321 tris (Forest/Fire/Spirit Temple, Ice Cavern, Ganon's Tower/Castle, GTG,
Ganon's Castle, hakasitarelay), small cap overflows (pixels/tiles/verts: Dodongo, Jabu, Water,
Shadow rooms, Barinade, Zora's/Lake/Gerudo/Desert/Lon Lon/Death Mountain/Kakariko field?,
etc.), moribossroom/hiral_demo converter errors.
Area music (2026-10-02): scene header seqId per scene (scene_entry_t.seq). Generic scenes play a
songs.json route or a disc bank M<seq>.HDR/.PCM/.LVL (tools/build_area_music.py, runtime
src/music_area.c, tables in jo heap). All 17 baked (converter now: channel io ports, delay1, notes before instr skipped). Effects omitted (build_title_audio OMITTED): combfilter, reverbidx, env, releaserate. Slice scenes keep their
hand music. Work RAM spare (Debug) 304 B. Next: raise caps (RAM cost) to admit the
near-misses; multi-bg camera selection; per-scene music; En_Door room switches.

## NEXT CHAT START HERE (written 2026-10-03, state = commit 736982c + docs)
Human goal: ALL NPCs in EVERY zone, ALL dialogue, spawn/talk/events checked against
save flags and triggers exactly like OoT. Must work in BULK for all actors (importer
and library level, no per-actor hand work) and stay fast, or the game is unplayable.
Human rules this chat: caveman talk; big batches, one Kronos test per batch; never leave
the playable game worse (the fast C slice is the baseline: targeting, talk, combat).
SATURN CUTS ALLOWED (human 2026-10-03). Must keep: the game functions, combat works,
story progresses (right NPCs/events/text by save state, flags, triggers). Everything
else may be cut or simplified for speed and memory:
- animation: lower rate, fewer frames, no head/torso turns, no limb callbacks, baked or
  simplified clips, LOD (far actors static or hidden);
- textures: flat colours, smaller tiles, shared palettes, faces only where it matters;
- assets streamed per scene/room from disc into the 4 MB cart (load at room change,
  never mid-play while CD-DA music plays);
- fewer simultaneous actors drawn, simpler effects, no 1:1 RDP features.
Rule: never hand a system to the decomp if it is slower or works worse than the C
version it replaces. Measure on the debug rows first.

Current runtime facts (human Kronos, Debug, 2026-10-03):
- Kokiri: C NPCs/Mido/signs/wonder spots again (oot_core_owns_kokiri_npcs() false),
  decomp = grass + drops only. C talk works. REGRESSION: decomp grass no longer exists
  after the FX_FRAC 24->16 change (suspect EnKusa_SnapToFloor -> BgCheck raycast fails
  -> Actor_Kill). The Kokiri boy never blocked the bridge exit in the C game (only Mido does):
  not a regression; the real En_Ko blocker comes back when Kokiri moves to the decomp (G).
- Lon Lon (generic scene): decomp runs (p1). Only Ingo spawned (others: real spawn
  flags). Ingo update 1.0 ms; decomp draw phase 12.8 ms; Ingo invisible (VRAM 99%:
  skin texture upload skipped). Buildings cannot be entered in ANY non-Kokiri map.
- Debug rows: 15 `oc p pl pr mi`, 16 `ou` total + talk/msg/npc/colliders/draw items,
  17 `op` phase times (0.1 ms: collision/actors/message/draw), top-3 actor ids x count =
  cost, `o<n>w<n>` talk-offer fail reason (1 player busy, 2 height, 3 talk dist, 4 range).
- Static RAM spare: Debug 640 B, Clean 4672 B. FREE RAM FIRST before any C addition
  (candidates: move C tables to cart; archive C systems the decomp replaced).

Roadmap (each step = one batch, build both images, one human test; gate before next):

PHASE 1: make the decomp path cheap (nothing new until these pass)
 A. Grass back: host bgcheck probe (z_bgcheck + scene blob on host, raycast down at every
    Kokiri En_Kusa spawn, Fx vs float); fix the Fx/bgcheck issue in the library.
    Gate: row 15 pr24 in Kokiri.
 B. Cheap NPC skeletons: no Actor_Draw/Gfx walker for NPCs. Limb matrices straight from
    SkelAnime.jointTable in 32-bit ints, no callbacks, every other step, nearest N only;
    far NPCs frozen pose or hidden. Gate: Ingo draw < 1 ms (row 17).
 C. True 32-bit Fx in bulk: FX_STORAGE32 switch; Debug traps overflow + logs caller PC;
    importer rules fix the patterns everywhere (squared distance -> distance compare or
    64-bit helper; Rand*0xFFFF -> s16 wrap). Gate: host probe 0, target 0 traps on a
    Kokiri + Lon Lon walk, actor update cost far below 64-bit (row 17).
 D. Update budget: cull actor updates outside a range / off-camera (real OoT culls too),
    lower update rate for far actors. Gate: decomp step < 5 ms in Kokiri with all NPCs.

PHASE 2: memory and streaming
 E. Free static RAM (Debug 640 B spare): move C tables/text to the cart, archive C systems
    the decomp replaced (Kokiri children, signs, wonder spots once G1 passes).
 F. Per-room streaming in the cart: object data blobs, skins and meshes load at room
    change into a cart pool (not just at scene load); texture budget per room with
    flat-colour fallback when VRAM is full (never invisible: draw flat). Debug row shows
    pool/VRAM use. Gate: Lon Lon NPCs visible, VRAM < 95%.

PHASE 3: the world works
 G. Talk for every decomp NPC (row 17 `w` reason -> fix proxy talk path). Navi/Z-target
    proxies generic for any decomp NPC (from the Kokiri registry code).
 H. Doors, grottos, exits in every registered scene (C scene flow: En_Door, Door_Shutter,
    Door_Ana, scene exit table). Gate: enter Lon Lon buildings, Kakariko houses, shops.
 I. Combat with decomp enemies: proxy player AC (damage to C Link), C sword vs decomp AC
    already works; knockback via player_push. Gate: fight Deku Babas/Skulltulas from decomp.

PHASE 4: content in bulk, zone by zone (story order)
 J. Kokiri (back to decomp: kids, Mido blocking, signs, Saria via C cutscene hand-off),
    Deku Tree, Lost Woods, Hyrule Field, Lon Lon, Market + Castle, Kakariko, Graveyard,
    Death Mountain, Goron City, Zora's River/Domain, Lake Hylia, Gerudo, ...
    Per zone: importer lists (actors + objects), skins/meshes build automatically, a
    checklist from the decomp (every actor in the room lists, spawn conditions by age /
    day-night / flags, text ids by flag state, events and item gives), save mirror both
    ways. Human checks a story sample per zone. Each zone's C counterpart moves to legacy/.
 K. Later systems as needed for story: z_demo cutscenes, get-item hold-up (sprite),
    ocarina songs, day/night clock, adult Link.

 Known gaps to keep logged: Navi targeting of decomp actors needs C proxies (done for
 Kokiri NPC registry, generalise in G); no Saria (z_demo cues); ocarina; get-item hold-up.

## NEXT SESSION: GAME CONTENT ROUTE (approved by human 2026-10-02)
Goal: the actual game through the decomp: NPCs, dialogue paths, event triggers, actors
present/absent by progress flags, child/adult and day/night layers. No more perf tuning
unless a real frame-time problem blocks content (row 16 `ou` = decomp update us/step).
Rules: decomp HUD/pause/text stay on VDP2 (bridge their draw); held-up get-items are sprites,
not 3D GI models. Old C game code: when a decomp system works in game, move the C version to
legacy/ (archive, reference only) in the same batch; it still works slice start -> Field.
Steps (in order):
 0. DONE (build only): `./build.sh --quick ...` skips asset steps (C/C++/oot-core changes).
 1. DONE (build only): gSaveContext mirror both ways each step: eventChkInf/itemGetInf/
    infTable/scene flags (copy back after update), age (child), night (0), dayTime (noon).
 2. DONE: every registered scene gets a blob (<scene>.OOC, all room layers:
    main + AltHeaders); play_init in any scene, layer = Play_Init rule, per-room fallback =
    Scene_CommandAlternateHeaderList. Decomp grass/drops drawn in any scene. Scene-level alt
    headers (spawns, transition actors) not yet. Steps 0-2 runtime: human 2026-10-02, Kokiri
    grass test "no issue" (e57ec80). Second grass scene not reported separately.
 3+4+5a. BUILT, runtime NOT checked (API v9, Debug static RAM spare 432 B, Clean 4352 B,
    blob 392 KB of 448 KB carve). First decomp NPC = En_Ko (all Kokiri children):
    - Imported: z_skelanime, z_message, z_kanfont, z_construct (real Message_Init +
      Regs_InitData), z_face_reaction, z_path, gfxalloc, z_memory_utils, En_Ko.
    - Objects like N64: importer OBJECTS (os_anime, km1, kw1, fa) -> O<id hex>.OOB data
      blobs linked at segment 6 (oot-core/object.ld): skeletons/limbs/anims verbatim,
      DLs/textures one-word placeholders. obj_syms.ld gives OOTCORE their 0x06 addresses.
      Each OOC lists the built objects its room ObjectLists name; host loads them after the
      OOC in the scene carve; set_objects fills objectCtx slots. Object_GetSlot real search;
      unbuilt object ids = resident slot 0 (gameplay_keep etc.), built-but-unloaded = -1.
      SEGMENTED_TO_VIRTUAL/OS_K0_TO_PHYSICAL without K0BASE, gSegments[2]=0x02000000.
    - Scene paths: OOC carries Path lists per scene layer (Scene_CommandPathList).
    - Text from ROM: NESMSG.BIN = baserom nes_message_data_static in cart carve
      RAM_CART_MSGDATA; entry table offsets from the ROM's own table in `code`
      (importer msg_syms.ld). Japanese table emptied (English only, language set ENG).
    - z_message runs for real: Message_Update + Message_Draw each decomp step, Gfx to a
      scratch buffer (bridge_message.cpp). oot_core_views.cpp lays the decoded page into
      38x4 cells + colours; C oot_core_message_box() prints it on the VDP2 rows 20-25 with
      the VDP1 panel and prompt mark (decomp box replaces the C box while up).
    - Player proxy talk: copy of Player_ActionHandler_Talk / StartTalking / SetupTalk /
      Action_Talk close; real player body cylinder (OC) -> push sent to C Link.
    - C: Kokiri children absent from C logic while decomp plays (gameplay_npc_present);
      npc_draw draws each En_Ko with its type's baked model at decomp curFrame + decomp
      head/torso turn. A goes to the decomp while it offers talk or talks, B while it talks; Link frozen
      (gameplay_blocks_world) while the decomp text box is up.
    - APPROXIMATE / missing (log, not blockers): one baked clip per type (decomp anim
      changes not shown), glyph widths = 1 cell, item icons not drawn, no Z-target/C-Up
      talk to decomp NPCs, no talk anims for Link, Navi hints about children may still be
      C, no ocarina in messages, player name fixed "Link". Mido/Saria stay C (next batch).
    Human check (Debug, one pass): Kokiri Forest - kids visible where OoT has them, look at
    Link; walk up, A opens real ROM text, A pages/closes, choices (if any) by D-pad; kid
    blocking the exit pushes Link; row 15 `oc p1 ...` no freeze; one Kokiri house; heap row
    no failed allocations (bank-2 heap is now 598 KB, was ~1 MB).
    Human 2026-10-02 on 82c0ac4: C Mido talks and blocks; decomp grass NOT cut by sword.
    Cause found: Actor_UpdateAll only updates actors with INSIDE_CULLING_VOLUME (set by
    Actor_DrawAll's culling, which never runs) or UPDATE_CULLING_DISABLED; En_Kusa clears
    the latter once ready, so it stopped updating. Fix: OotCore_CullActors (sphere of the
    actor's culling distance around the player) before Actor_UpdateAll. APPROXIMATE.
 5a. BUILT, runtime NOT checked (API v10; Debug spare 6320 B, Clean 10272 B after the Jo
    work-RAM malloc arena 51200 -> 45056, overflow goes to cart zones):
    - En_Md (Mido, object_md blob, drawn as model 0 by npc_draw), En_Wonder_Item,
      En_Wonder_Talk2, Obj_Mure2, En_Kanban (object_kanban blob).
    - C Mido, C wonder spots, C sign read/cut off while the decomp plays; C still draws
      signs, parts from decomp partFlags (prop_query). Flying sign pieces not drawn.
    - Null-profile guards (importer): spawning a not-imported actor/effect returns
      nothing (Obj_Mure2 rock circles -> En_Ishi not imported yet).
    - Debug row 16 adds `t<talk> m<msgMode> x<textId> n<npcs> c<AT>/<AC>/<OC>`.
    Human check: grass cuts again; kids/Mido visible; Mido blocks the Deku path (push)
    until sword+shield, talks ROM text; signs read with A (ROM text), sword cuts pieces off;
    hidden wonder spots drop items; row 16 numbers if anything is wrong.
 5b. Phase 2 generic draw, BUILT, runtime NOT checked (API v11; Debug spare 5104 B,
    Clean 9072 B; blob 395 KB of 448 KB):
    - oot_core_draw.cpp: per generic-draw actor, real Actor_Draw into scratch Gfx
      (now in the low-WRAM play block, RAM_LOW_OOTPLAY 0x70000), then a Gfx walker
      (G_MTX/POPMTX/DL/ENDDL/segment) turns each call of a placeholder DL into a draw
      item: mesh key + transform as translate*Ry*Rx*Rz*scale (no raw SGL matrix).
    - Placeholders are indexed: keep ones in section .keep_ph (importer KEEP_PLACEHOLDERS,
      append only, keep_ph.txt); object ones after an 'OOB1' header in each .OOB
      (O<id>_ph.txt). tools/build_core_meshes.py builds K<idx>.MSH / Q<obj><idx>.MSH
      with build_shop_props.static_mesh at scale 1 for every DL the generic actors name.
    - C (oot_core_host.c): loads the scene's meshes after set_objects, uploads them last
      in npc_draw upload_visible (a full bank skips them, never errors), draws items in
      world_props_draw via actor_mesh_draw_euler (Y flip negates pitch/roll).
    - Generic-draw actors (importer GENERIC_DRAW_SOURCES): Obj_Tsubo, En_Gs, Obj_Hana,
      En_Wood02 (trees/bushes), Obj_Syokudai (torches), Obj_Kibako (crates). Meshes load
      only for generic actors the scene's room lists contain (mesh_list, C cap 40).
      set_camera passes the C camera yaw (Camera_GetCamDirYaw for torch flames). API v12.
      They spawn ONLY in generic scenes (save scene >= SAVE_SCENE_COUNT); slice scenes keep
      the C copies, so Kokiri is unchanged by this step. En_Ishi left out (38 KB, needs
      carry). Gossip stone material/squished DLs fail the converter (only base DL drawn).
    Human check: level select into a generic scene with pots/gossip stones/flowers (e.g.
    Kakariko, Death Mountain trail, a dungeon room with pots): props appear at the right
    place/size/orientation; sword breaks a pot (drop appears). If props are mirrored or
    tipped: report it (pitch/roll sign in actor_mesh_draw_euler is the first suspect).
 5c. Real NPC animation by runtime skinning, BUILT, runtime NOT checked (API v13):
    - Matrix_Init now runs in play_init (was missing: any Matrix_* call wrote through
      NULL; affected En_Kanban updates and every draw).
    - En_Ko/En_Md are drawn for real each step (Actor_Draw -> SkelAnime_DrawFlex); the
      blob copies the flex matrix array (gSPSegment 0x0D, dListCount entries) per actor
      and exposes it in OotCoreNpcView.mats.
    - build_npc_models.py writes NPCnn.SKN (per vertex: matrix slot = depth-first index
      of limbs with a DL, limb-local position). C actor_mesh_draw_skinned transforms the
      baked model's vertices with the live matrices: every animation, blink-free pose and
      head/torso turn comes from the decomp. Falls back to the baked idle clip when the
      table or matrices are missing.
    - Scratch opaque display list 64 KB (RAM_LOW_OOTPLAY 0x78000).
    Human check: kids/Mido animate like OoT (sitting, standing, digging...), turn heads,
    no exploded limbs. Exploded or inside-out limbs = slot order mismatch (report which
    kid type).
 5. Next: more generic actors, En_Sa (needs z_demo cues), other areas.
    Archive the C Kokiri child/Mido/sign code to legacy/ once confirmed.
 6. Later: z_demo cutscenes, z_player, z_camera. Then archive C counterparts.

## SPEED (2026-10-02, human Kronos kronos-fix, Debug, ns per call, cart)
Low-WRAM copy (OOTBENCH.BIN, rows 16-17) is NOT faster than cart: cost is the math, not the bus.
Fixes: fx.h dmuls.l inline 32x32 path + 32-bit shift helpers + always_inline (61769fc);
oot_math sqrtf = divider Newton, sinf/cosf = Q30 table + interpolation, after SaturnMath++
(bec381b, e810ba3). Host probe 0 over tolerance each time.
  ma 9015 -> 7549, dv 20901 -> 19922, ss 15864 -> 14362, ds 59799 -> 39371, sn 49818 -> 10553,
  at 28630 -> 26350 (decomp code, unchanged). Kronos SH-2 timing is approximate: a ~60-instruction
  loop shows ~200 cycles. Next: real per-frame cost row (Actor_UpdateAll time), real hardware
  run if possible. 32-bit Fx would halve again but needs an overflow audit (not started).
  dv still slow: check fx_div hardware path is taken (FX_RUNTIME / range test) before more work.

## NEXT SESSION: Phase 1 step 5 (first live decomp actor)
Rule: game logic comes from decomp source via `tools/oot_core_import.py`. Do not rewrite a
system by hand that the decomp already has. Our C code stays only as the Saturn backend
(render, audio, VDP2 UI, file IO). Read game/docs/BUILD.md first (Linux/WSL build only;
gotchas 20-29 are oot-core). Run git from Windows. Human runs Kronos (`build/kronos-fix`).

State at handoff (commit 8bfdb92, branch oot-core, not pushed): steps 2-4 done (see status
sections above). Step 4 runtime CONFIRMED by human 2026-10-02 (Kronos kronos-fix, Debug):
row 15 `oc p1 pl1 pr0 mi0` in Kokiri Forest, no freeze. Gate speed numbers are slow
(ma 8582 ns); human said fix later, do not block on them.

Step 5 progress (2026-10-02, Debug build OK; tasks 1-3 runtime CONFIRMED by human):
- DONE 1: importer cuts each room's main-header ActorEntryList into the scene blob (SPT04COL.BIN
  now starts with OotSceneBlob, oot-core/include/oot_scene_blob.h; section .scene_header).
  load_room_actors (oot_core_api.cpp) copies only ids in sRoomActorIds (= ACTOR_EN_KUSA) into
  play->actorEntryList; Actor_UpdateAll spawns them. API version 4.
- DONE 2: play_init takes room; entry set_room(room) = Room_RequestNewRoom + FinishRoomChange
  (func_80031B14 kills old-room actors). Host calls it each frame with kokiri_scene_room().
  NOTE: KOKIRI_STREAM_ROOMS is not defined, so room is always 0 -> room 2 grass (4) never spawns
  (same as C grass, which also filters room 0).
- DONE 3 (partial): OotCoreHost wired. play_sfx -> action_audio_decomp_sfx (PLANT_BROKEN, GET_RUPY,
  GET_ITEM, HP_RECOVER; others silent); Audio_PlaySfxGeneral (SFX_PLAY_CENTERED) now routes too.
  give_item maps decomp ItemId -> save_item_give; health_change -> save_heal/save_damage.
  En_Item00 seeds/nuts/stick use GetItem offer (Actor_OfferGetItem), not Item_Give: task 5.
- Human confirmed 2026-10-02: Debug, Kokiri, L+R row 15 `oc p1 pl1 pr12 mi0`, no freeze.
- DONE 6 (build only, runtime NOT checked): entry set_sword (API v5). Host sends
  gameplay_sword_active() + gameplay_blade_points() each step; player proxy (bridge_player.cpp)
  owns meleeWeaponQuads[0] (z_player D_80854650), sweeps prev->cur line with a copy of
  Player_UpdateWeaponInfo, dmgFlags DMG_SLASH_KOKIRI. APPROXIMATE: one blade line, one quad
  (real: two lines/quads); jump/spin dmg flags not passed. Human check: cut Kokiri grass,
  row 15 `mi` should rise above 0 when a drop spawns (drops are invisible, not collectable yet).
- Human confirmed 2026-10-02: sword cuts decomp grass.
- DONE 4+5 batch (build only, runtime NOT checked; API v7, work RAM spare 3,760 B):
  - Room lists now also spawn ACTOR_EN_ITEM00 (9 floor rupees in room 0).
  - oot_core_owns_kokiri_props() (src/oot_core_host.h): while decomp plays Kokiri, C grass
    (gameplay.c tufts) and C floor rupees stop cutting/collecting; kokiri_sgl.c draws decomp
    En_Kusa (uncut, object ready) with the grass billboard and decomp En_Item00 with
    kokiri_drop_draw (params = ITEM00 type) via entry actor_view. Wonder-item drops stay C.
  - Rupees/hearts: En_Item00 collects by distance (real code) -> Item_Give -> C save.
  - Seeds/nuts/stick: player proxy handles Actor_OfferGetItemNearby (PlayerProxy_GetItem):
    APPROXIMATE, given at once (no hold-up, no first-get text).
  - Entry set_save mirrors C save into gSaveContext each step (health, capacity, rupees,
    stick/nut/slingshot + ammo; child; no magic/bombs/bow) so the real drop table and
    Item00 filters see the real state. Floor rupees use temp collectible flags (0x24-0x27):
    they respawn on scene re-entry, as in OoT (C used to keep them taken in the save).
  - Missing (logged): Kusa lift/throw with A (Actor_OfferCarry), Item00 collect rise anim,
    two-quad sword, room 2 (no room streaming).
- Human check (one pass): Debug, Kokiri, L+R. Cut grass -> grass sprite vanishes, drop
  visible, walk over -> rupee/heart counted with sound; grass regrows later; floor rupees
  visible and collectable; seeds only drop with slingshot owned; no double cut sound.

Step 5 tasks, in order:
1. Room actor lists: importer cuts each Kokiri room's ActorEntryList verbatim out of
   extracted `spot04_room_<n>.c` (main header lists `spot04_room_0_03000094`,
   `spot04_room_1_03000088`, `spot04_room_2_03000084`; AltHeaders = other scene setups, later),
   same way as SCENE_COLLISION. Put them in the SPT04COL blob (data, fixed address) or the
   oot-core blob. Spawn via `play->actorEntryList`/`numActorEntries` (Actor_UpdateAll spawns
   them, real behaviour) or entry `spawn`. Start with ACTOR_EN_KUSA entries only; leave all
   other ids to the C game until imported (step 6).
2. Rooms: actors carry `room`; set `play->roomCtx.curRoom.num` from `kokiri_scene_room()` so
   room-bound actors behave (check z_actor Actor_Spawn/room kill logic).
3. Wire `OotCoreHost` (`oot-core/include/oot_core_host.h`) in `src/oot_core_host.c`:
   play_sfx -> action_audio (map decomp NA_SE_* ids used by En_Kusa/En_Item00), give_item and
   health_change -> save_state / existing item_drop pickup code. En_Item00 calls Item_Give.
4. Hide the C grass that the decomp now owns: world_props grass in Kokiri Forest only
   (world_props.c / world_props_draw.c). Grass is invisible until Phase 2 draw shim, so for
   testing either keep C grass drawn but non-interactive, or add a debug marker. Pick the
   option that keeps the slice playable; record it in DEMO/plan.
5. Collectibles: En_Item00 spawned by Item_DropCollectibleRandom must be picked up by the
   player proxy (needs player cylinder / Actor_HasParent etc. — check what En_Item00 tests;
   bridge only what is missing). Drops must match the real table (CLAUDE.md drop rule).
6. Debug row 15 shows prop/misc counts; human cuts grass with sword: grass needs the C sword
   to hit decomp colliders -> C sword AT must enter `play->colChkCtx` (CollisionCheck_SetAT)
   via a host->blob call (add entry `set_sword(...)`). This is the first C->decomp combat link.

After step 5:
6. Bulk: import every Kokiri actor overlay the scene spawns, one per commit, each with a drop
   check. Stand-in player and stub list (bridge_play.cpp STUB tags) shrink as files import.
7. Phase 2 draw shim: real GraphicsContext + Actor_DrawAll; gSPDisplayList(seg addr) ->
   prebuilt Saturn mesh (build_actor_model.py, keyed by bridge_assets.cpp symbols). Faces
   textured only (VRAM rule).
8. Music bulk (independent): shared/tools/build_title_audio.py over all sequences.

Known hazards: ROM IEEE-float data must be converted to Fx at load. Keep Fx ops constexpr.
Blob code runs from the cart only on build/kronos-fix Kronos (BUILD.md 26). Blob 200 KB of
256 KB carve: grow carve (ram_cart.h + makefile together) before it overflows. Work RAM spare
5,696 B: new C host code must stay small. Boot markers on row 20 (oot_core_host.c).

## Approach (phased, each phase gate)
### Phase 0 — spike, prove or kill (do first)
1. New dir `game/oot-core/` (or `shared/oot-core/`). Build decomp C files as **C++** for SH-2 with
   `f32` = `Fx` class (32-bit store, int64 mul/div, saturate/assert on overflow in debug).
   Mechanical: no hand edit of logic. Script `tools/oot_core_import.py` copies listed decomp files,
   applies regex fixups for C-vs-C++ (void* casts, designated init) only.
2. Math lib: sinf/cosf/sqrtf/atan2 -> tables + SH-2 DIVU. `Math_*`, `Math3D_*` dist functions
   get int64 internal path (fix distSq overflow at source, once).
3. Port tiny slice: z_actor.c core + z_lib.c + 1 simple actor (En_Kusa grass, has drop table) +
   z_collision_check minimal. Stub libultra/gfx (`Gfx` writes -> recorder).
4. Measure on target: cycles per actor update (SH-2 disasm check no `__adds f`/soft-float).
   Gate: if update cost too high or overflow everywhere -> stop, report.

### Phase 1 — core systems bulk
z_bgcheck (collision), z_collision_check, z_actor, z_camera, z_player, z_play loop, z_message,
save. Replace our hand ports gradually behind flag; keep our renderer.

### Phase 2 — draw shim
Offline: convert actor/object display lists -> our VDP1 mesh format (extend
`game/tools/build_actor_model.py`). Runtime: `gSPDisplayList(seg addr)` -> lookup prebuilt mesh +
current matrix -> existing kokiri_sgl draw. No runtime F3DEX parse of triangles.

### Phase 3 — actors in bulk
Import actor overlays scene by scene (Kokiri first). Each actor: compile, link draw shim. Drops
come free (real code).

### Music bulk (parallel, independent)
`shared/tools/build_title_audio.py` already convert OoT seq -> SCSP score, fail on unknown opcode.
Run over ALL sequences, collect unsupported-opcode list, implement missing opcodes once in
`shared/lib/music/music.c`. Output full bank. SFX same path later.

## Critical files
- new: `game/oot-core/**`, `game/tools/oot_core_import.py`, fixed `Fx` header
- `game/makefile` (add C++ objects, SH-2 g++ from sh2eb-elf)
- `shared/tools/build_title_audio.py`, `shared/lib/music/music.c`
- `game/docs/DEMO_PLAN.md` (record strategy + phase status, required rule)

## Verification
- Host: compile oot-core natively, run actor update vs real float build, compare outputs (diff tolerance).
- Target: build clean image, disasm check no soft-float helpers, cycle count report.
- Human runs Kronos/Saroo test (no emulator launch by agent).
- Music: build all seqs, report coverage %.

## Risk
Phase 0 may fail perf. Then fallback: keep hand-port but drive it from decomp source per system
(current way) + bulk music still win.
