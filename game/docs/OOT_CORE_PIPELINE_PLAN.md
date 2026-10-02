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

## NEXT SESSION: Phase 1 start (do in this order; stop hand-porting)
Rule: game logic comes from decomp source via `tools/oot_core_import.py`. Do not rewrite a
system by hand that the decomp already has. Our C code stays only as the Saturn backend
(render, audio, VDP2 UI, file IO). Read game/docs/BUILD.md first (Linux/WSL build only).

1. Gate numbers: the human runs the Debug build (`./build.sh OOT_CORE=1`, game/build/game.cue) and
   reads rows 13-14. A large ns/call (e.g. dv or at) gets fixed before bulk import: SaturnMath++
   LUT/DIVU.
2. DONE 2026-10-02 (see Phase 1 status). Grow the cart carve to 256 KB+. Add z_actor, z_collision_check, z_bgcheck, z_en_item00,
   En_Kusa to OOT_CORE_SRCS. The link fails on undefined symbols: that list IS the Phase 1 backend
   work list. `--gc-sections` keeps only what's reached.
3. FIRST PASS DONE 2026-10-02 (links, 0 undefined; stubs listed in status). Next: wire
   `OotCoreHost` from C, then replace stubs as files get imported. Write `oot-core/src/bridge_*.cpp` for each undefined group. Keep them thin:
   - PlayState/ActorContext/ObjectContext: one global PlayState owned by oot-core; Object_* =
     "always loaded" for imported objects.
   - Gfx_*, gSPDisplayList, OPEN/CLOSE_DISPS: record DL segment address + current MtxF -> a draw
     list the C side submits as prebuilt Saturn meshes (Phase 2 shim; start with a stub cube).
   - Audio_PlaySfx*/SfxSource_*: map sfxId -> our existing action_audio PCM bank.
   - EffectSs*_Spawn: stub (count calls) first, then port the effects that are needed.
   - BgCheck: decide between z_bgcheck over our converted collision (preferred; needs the
     CollisionHeader in decomp format from the ROM) and a bridge to kokiri_collision.
4. BUILT 2026-10-02 (see step 4 status; runtime pending). Entry table grows (v2 already has `init` = ctor runner; add the proxy Player) (oot_core_bench.h -> oot_core_api.h): init(play), update(), draw(list),
   spawn(actorId, params, pos). The C main loop calls them for scenes flagged "decomp actors".
5. First live actor: En_Kusa in Kokiri Forest with its real drop table via z_en_item00. Replace
   world_props grass for that scene only. Human verifies in Kronos.
6. Then bulk: import every Kokiri actor overlay the scene spawns (scene actor list from the ROM),
   one per commit, each with a drop check (CLAUDE.md drop rule comes free from real code).
7. Phase 2 draw shim in parallel: build_actor_model.py converts object DLs to KFR1, keyed by DL
   segment address so the bridge can look them up. Faces textured only (VRAM rule).
8. Music bulk (independent): run shared/tools/build_title_audio.py over all sequences, list
   unsupported opcodes, implement them once in shared/lib/music/music.c.

Known hazards: ROM IEEE-float data must be converted to Fx at load. Keep every Fx op
constexpr (no .ctors). Stock Kronos freezes over 2048 VDP1 cmds; use the patched build
(BUILD.md 17). WSL git can't read this worktree; run git from Windows.

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
