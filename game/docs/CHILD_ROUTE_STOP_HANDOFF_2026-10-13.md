# Child route stop handoff — 2026-10-13

## Stop instruction and artifact identity

Human explicitly stopped this run after reporting 91% of weekly tokens used:
**“Stop now; save exact handoff.”** Do not resume implementation/builds without
a new instruction. Scope remains Field owl through King Dodongo, including
Ranch, Kakariko, Goron content, prerequisites, optional child interactions,
shops/items/enemies/cutscenes and full chest-jingle playback. It is unfinished.

Branch `oot-core`; HEAD `0cd9cd8` (earlier checkpoint). This batch is uncommitted.
No new playable image was produced. Preserved Clean 14 `eb25f08b` and Debug
`6117a58c` predate this batch. Current `build/cd` is partial/mixed staging and
must not be used as evidence of those images or mastered as-is. No emulator
was run; human owns runtime testing. All agents were told to stop. Their
long-running jobs are stopped; root jobs have exited.

## What is implemented, versus verified

- Real source Player/core collision remain authoritative. No completed C
  gameplay retirement or R1 single-writer-state claim. API35, scene format4,
  OAP v2 with 96-byte header/service ABI2 require matching artifacts.
- Source EnOwl actions/dialogue/repeat/transport; source `z_demo`, scene-local
  complete scripts, subcameras/splines/letterbox and per-scene OnePoint engine.
  Courtyard Zelda/Impa/Ganondorf, Lullaby/letter and Saria prerequisites have
  source adapters and isolated fixtures. Camera details:
  [camera handoff](CHILD_ROUTE_CAMERAS_2026-10-13.md).
- Source Darunia/Gorons/guards/carpenters/Cucco lady; six shops with fifty stock
  entries; Ranch horses/Malon/Talon/Ingo/cucco/cow and original timed bottle
  game; common Market/Kakariko NPCs, dogs/Dampe/token-family rewards, mask
  actors and twelve minigame actors. Nonboss presentation is baked sprites,
  clip clocks and offline semantic contacts. Scene NPC view code now lives
  in scene packs; resident core keeps bounded output storage/Player/Ko/Md.
- Thirteen DC/Meadow enemy adapters include Dodongos, Armos, Lizalfos,
  merchants/scrubs/projectiles, Beamos, Skulltulas/tokens, Wolfos and Deku
  Scrubs. Castle guard/bridge/box/pad dependencies added. Original actor
  action, collision and drop bodies retained where adapted.
- King Dodongo retains full source actions, poses and nineteen contact
  spheres, twenty limb meshes, fire, lava cooling, heart and child warp/Ruby.
  Mountain/city props, source effects, Three Goddesses and Great Fairy have
  isolated source/bake work. Details and last unverified edits:
  [dungeon handoff](DODONGO_ACTORS_2026-10-13.md).
- Get-item atlas tool bakes source `z_draw` recipes; synthetic object0xfff
  uses GID+1 keys. Scene preload no longer silently caps archive libraries at
  64. Full atlas run is currently FAILED (below), so this is not complete
  reward presentation. Other sprite batches mostly have isolated bakes;
  the final combined generic bake was interrupted by the stop instruction.
  Session19578 was stopped cleanly. Log `build/child-route-generic-bake.log`
  ends at G09715.SPR; generic_sprites.json/.h remain Oct12 while sheets are
  partially overwritten. Archives and coverage regeneration never ran.
- Save v14 adds ocarina memory-game round; old v13 loads default zero. Core
  token groups/count, added inventory upgrades and reward mirrors are wired.
  Last Fairy magic/defense persistence, healthAccumulator drain and minigame
  score/HUD patches are not certified by a matching final target build.

## Chest/audio work

Chest sequence43/font3 now exports all 8.56 seconds, 643 sectors and 276 notes
including release tail. CD completion follows actual drive status. Item
fanfares queue behind chest; BGM changes and data reads wait. Source input
edges/held input are cleared while the frozen world waits. Eight-entry source
audio requests are serviced on the joined master. This is implemented and
host-tested, not heard on a new Saturn image.

Music trigger padding now stores source channel identity without changing its
eight-byte size; Malon vocal/melody controls, spatial mix, temporary sequences,
timed-game tempo and once-bank pinning are wired. Source SFX pitch has a
Q6 command adapter; owl motion/flap functions and transposed notes added.
River pitch is applied directly; original forty-frame frequency interpolation
is still missing. Single-bank source music mixing is an explicit approximation.

Metronome samples/actual completion clocks unblock source memory game. Original
message/Skull Kid rounds execute through 5/6/8 notes, success and wrong-note
branches. Final bank: 158,804 resident bytes, 37,804 area bytes; metronome
duration is 15/8 source ticks. Old area `box_item` sample is still budget-trimmed;
the full dedicated chest CD track is separate. Preserve that distinction.

Latest root audio run: **43 tests passed**, covering CD/mixer/master queue,
chest export and action playback (before the agent's final metronome timing
adjustment). Agent's later runs: six ocarina and 26 action-audio checks passed.
Do not add counts as distinct coverage. Logs under `build/child-route-core`.
Area music rerun: **33 baked, zero blocked**. Interior music rerun exited zero.
Both generate partial staging; they do not create a disc image.

## Latest integration results and concrete failures

1. Latest full resident SH-2 core link passed: `_oot_core_end=0x027FF208`,
   3,576 bytes free in unchanged 640 KiB core carve; Low BSS `0x9ECC` in
   `0xA000` (308 bytes free). This is not a final post-stop-tree rebuild.
   NPC views and OnePoint services were moved to scene packs to fit. Export
   generation now scans actual `*_profiles.o` callbacks as well as actors.
2. Scene carve is 256 KiB at `0x02720000`; core stays `0x02760000`. This took
   64 KiB from cart heap. Guards remain enabled. Earlier DC 235,456-byte pack
   pass predates many additions and is NOT the current pack/budget result.
3. Latest `oot-scene-packs` FAILED. Exact unresolved symbols in
   `build/child-route-core/packs.log`:
   - `gDust5Tex`, `D_01000000` from `DemoKankyo_DrawClouds`.
   - `Play_ReturnToMainCam(PlayState*, short, short)` from King Dodongo.
   - `Rumble_Override(FxSq, unsigned char, unsigned char, unsigned char)`.
   - `Audio_SetGanonsTowerBgmVolumeLevel(unsigned char)` and
     `Audio_PlayNatureAmbienceSequence(unsigned char)` from River Sound.
   Missing declarations/definitions must get real source/backend semantics
   or proven-unreachable profile pruning, not silent success stubs.
4. Latest reward atlas run FAILED at scene SZ: `GID_FAIRY`, `GID_SOLDOUT`
   recipes missing. Earlier failure `GID_SKULL_TOKEN_2` was given the source
   object_st recipe and baked, but no successful all-scene rerun followed.
   Log `build/child-route-core/get-items.log`; old budget JSON is stale.
5. Newly imported drawbridge contains unresolved fixed-point range debt:
   source literals 37,500 and 1,024,000 saturate. Correct the importer
   arithmetic before accepting that actor. Other historical audit warnings
   remain; inspect `import.log` rather than treating link as math acceptance.
6. No final host raw build, combined pack high-water mark, combined
   heap/VRAM/texture-slot/directory check, matched ISO verification or runtime
   traversal. Prior host RAM numbers are historical: Debug16B/Clean3632B spare.
   Root audio/host rendering additions must be measured, not assumed to fit.
7. Pack validator fixture TEST.OAP is stale v1/header80. Native results:
   seven pass, three platform skips, one stale-fixture error; actual Linux
   registration/constructor/service bind/release passes. Rebuild the fixture
   against OAP v2/header96. Scene view fixture passes source variants/clones/
   visibility; SH-2 audit38 native products, zero failures.

Last unverified dungeon edits: `oot_core_reward_sync.h`, reward sync in
`oot_core_api.cpp`, host magic command IDs, `health_hud_acquire`, updated Fairy
fixture, score delta commit, effect0xf9 snapshots and score/HUD rendering in
`kokiri_sgl.c`/host dispatch. `run_child_fairy_assets.sh` was written, NOT run.

## Explicit remaining route content

Conservative child day/night admission scan is saved at
`build/child-route-admission-gaps.json`. It includes false positives for
resident/C-owned/adult-only actors; classify before adding profiles. Confirmed
unadded actors: Market EnMu/EnNiwGirl, Ranch EnCrow, bowling BgBomGuard.
Other candidates: Kakariko windmill/well structures; Graveyard BgSpot02Objects,
BgHaka, EnIt, EnWonderTalk/weather; Goron ObjTimeblock/EnLight; DMT flags/rocks/
ShotSun; optional Woods EnDntNomal/EnOkuta. BgBomGuard was inspected only.
Reachable quake/title/environment lightning/rain presentation and complete
route transitions still need closure. Production demand animation remains
separate unfinished migration work; do not claim whole-cutscene production
preload/pinning merely because script fixtures pass.

## Next bounded checkpoint, only after human resumes

1. Read this handoff and the two agent handoffs; inspect shared diff. Fix only
   the listed link/atlas/range blockers first. Validate last Fairy/score patches.
2. Resume the interrupted normal sprite bake, generate archives and fresh
   coverage, stage boss/room/mesh banks normally. Do not hand-merge isolated
   index files. Include synthetic reward atlas cost and all reachable effects.
3. Reimport and link matched core/packs, then build host raw with old images
   protected. Audit math and actual memory/VRAM/directory/load peaks. Resolve
   capacity with implementation/bake changes, never actor omission/cap cuts.
4. Produce one matched review image only when all mandatory guards pass.
   Human checks chest audio and owl camera, then fresh-file story/fight,
   optional content and save/reload. Mark remaining actors/presentation gaps
   explicitly; a build alone does not finish the original “everything” scope.

Useful ignored scripts: `build/child-route-core/link.sh` (imports then core
link) and `packs.sh` (scene packs). Paths assume WSL/Linux and local decomp
`D:/Workspace-Claude/game-decomps/n64/oot`. Do not run on this stopped turn.

## Resume 2026-10-13 (Claude)

Astra handed the stopped route to Claude for one playable checkpoint. No
emulator run, commit or push. Old Debug files copied to
`build/preserved-debug-2026-10-12/`; `build/game.{iso,cue,elf,map,raw}` are
still the old matched Debug set. Unmastered new host link:
`build/child-route-core/game-new-unmastered.{elf,map}`.

Fixed and checked:
- Pack links (`make -k oot-scene-packs`, log `packs-k.log`): all 81 packs.
  `Play_ReturnToMainCam` (source body, resident camera bridge);
  `Rumble_Override` (no rumble device, as Rumble_Request); River Sound
  `Audio_PlayNatureAmbienceSequence` (source main-BGM replace; host renders
  silence) and `Audio_SetGanonsTowerBgmVolumeLevel` (source table; no
  filter/reverb/level-7 delay); `Audio_PlayCutsceneEffectsSequence` flags
  unsupported bit 64; `Audio_SetMainBgmTempoFreqAfterFanfare` -> new host
  command `OOT_CORE_AUDIO_TEMPO` (tempo only, no pitch); pack.ld aliases
  `D_01000000`=gIdentityMtx and `D_06000000`=0x06000000; DemoKankyo clouds
  drop the unread segment-8 word; keep placeholder `gBoulderFragmentsDL`;
  EnOkarinaTag windmill/Door-of-Time scripts weak + import proof
  (`check_okarina_pack`; those scenes do not admit the actor).
- Capacity: Dodongo's Cavern 305,136 B, DMT 271,648 B > 256 KiB. Scene carve
  now 0x50000 at 0x02710000 (BUILD.md 112). Tightest DC 22,544 B free.
  Bank-2 cart heap is 64 KiB smaller again; peak heap unmeasured.
- Drawbridge Fx: adapter rewrites both literals exactly (child_castle_sources).
- Reward atlases: EnGirlA shelf rows add GID_SOLDOUT/GID_FAIRY; scan uses
  compiled (adapted) source, so unadmitted DemoEffect medallions drop out.
  101 scenes, 98 recipes, peak 58,408 B.
- Fairy probe passes incl. new reward copy/repeat/cap checks (host only).
- Build fixes: field audio and MUSICTRG trigger rows carry channel byte;
  host defines NA_BGM_NATURE_AMBIENCE/TIMED_MINI_GAME (1/108).
- Full `./build.sh OOT_CORE=1` asset stages complete: rooms rebaked, generic
  sprites 538 sheets, archives, atlases. Non-fatal: gGossipStoneMaterialDL
  mesh left out (`min() arg is an empty sequence`).

New blockers (no image produced):
1. `check_disc_directory.py`: 1,956 entries > 1,536 (`JO_FS_MAX_FILES`,
   GfsDirName table fills the 0xA000 low-RAM FS carve). New since the old
   1,434-file ISO: 101 I??.SP2 atlases, ~130 OOB, ~99 Q/K MSH, 93 area
   music HDR/PCM/LVL, 18 OAP. Needs a design choice: ID-type GFS table plus
   name hashes (same RAM, ~2,300 entries), a larger table elsewhere, or
   bundling (OOB into OOC alone saves only 156).
2. Debug host `.bss` ends 0x06086EF0, 12,016 B above SGL base 0x06084000
   (previous Debug had 16 B spare). Prior batch host audio/HUD/score code.
   Clean not measured (no Clean rebuilds in perf phase).
Still open after those: matched ISO verify, heap/VRAM peaks, human runtime
(chest audio, owl camera, story/fight, save/reload), unadded actors above.

## Resume part 2 (Claude, 2026-10-13): both blockers fixed, heap measured

Matched Debug image built: `build/game.iso` md5 7580a290…, cue/elf/map/raw
from the same build. Old Debug kept in `build/preserved-debug-2026-10-12/`;
Clean untouched. No emulator, commit or push.

- Disc directory: ID-only GFS table + exact packed 8.3 keys (BUILD.md 113).
  Capacity measured first: 0xA000 low carve holds 2,560 ID entries
  (12 B) + GFS work; keys use the retired cart MUSICTRG gap (20 KiB, no
  heap). Staging 1,956/2,560; post-mastering ISO order/key check passes;
  all 1,954 ISO files match staging byte for byte. SDK GFS_NameToId is no
  longer referenced (11 call sites use the exact lookup). jo_fs_cd kept.
  Test: `tests/test_fs_directory.py` (C keys == checker keys, order,
  rejections) passes in WSL.
- Debug RAM: map delta vs perf-kokiri baseline was text +10,400, data
  +1,600, bss +256 (audio service, item grant, file select, shop cursor,
  HUD/score, sprite rows). No duplicates proven retirable (C Deku Tree
  puzzles/webs/mouth still run). Cold const tables moved to cart `.cart`
  section HOSTCOLD (15,824 B; BUILD.md 114). `.bss` now ends 0x060834F0,
  2,832 B below SGL base. Boundary/heaps/guards unchanged.
- Focused checks: pack tests 11/11, chest audio, cdda mix, fs directory;
  core wide audit 1,815 hw multiplies, 0 failing; 81 pack audits 0 failing.
  `test_all_map_registration` errors only because core builds park .COL
  files in build/disc-retired (pre-existing).
- Audio gaps logged as unfinished (BUG_FEATURE_LOG): nature ambience is
  silence, cutscene-effects sequence not played, windmill pitch/tower filter.

### Heap peak model: route does NOT fit

`tools/heap_peak_model.py` (+ `tests/test_heap_peak_model.py`, currently
failing on the disc test) replays Jo's allocator over 101 scenes x rooms x
ages with door/warp predecessors. Conservative: all conditional props, full
tool inventory, one predecessor level, PLAYANIM.PFB (626 KB) resident.
Reports: `build/child-route-core/heap*.json`.

Child route failures (scenarios failing / modelled):

| scene | 0x19A800 (prior batch) | 0x1AA800 | now 0x1AF800 |
|---|---|---|---|
| spot00 Field | 15/15 | 15/15 | 15/15 |
| spot20 Ranch | 6/6 | 6/6 | 6/6 |
| spot16 DMT | 7/7 | 7/7 | 7/7 |
| ydan_boss Gohma | 10/10 | 10/10 | 10/10 |
| ddan Dodongo's Cavern | 17/136 | 68/136 | 68/136 |
| spot10 Lost Woods | 0/90 | 0/90 | 20/90 |
| spot01 Kakariko | 0/13 | 3/13 | 3/13 |
| spot04 Kokiri | 3/36 | 3/36 | 3/36 |

Causes: 85% sprite guard (CORE_SPRITE_HEAP_PERCENT) and no contiguous
block. Field sprite archives ~1.36 MB plus STM; GOHMA.ANM needs one
1,361,516 B block (cart1 max hole 1.27 MB). Matches the human's 2026-10-08
Field "sprite preload failed" report. The new image therefore is a build
checkpoint, not yet a route-playable one. Decisions needed (not done):
smaller sprite bakes for Field/Ranch/DMT/DC (allowed by sprite rule),
demand-loaded Player animation (existing directive) instead of resident
PLAYANIM.PFB, Gohma ANM streaming/split, or guard policy review.

## Resume part 3 (Claude, 2026-10-13): heap fits in the model; checkpoint NOT route-ready

Astra approved: smaller sprite bakes where needed, real Player demand
loading, a Gohma fix; keep the 85 % guard; no carve growth. Human owns
runtime. No commit/push. Clean and old Debug images untouched.

### Model validation first
- `tests/test_heap_model_allocator.py`: the game's real allocator
  (`src/heap_profile.c` + joengine `malloc.c`, host-compiled with
  `tests/fixtures/jo_shim`) and `heap_peak_model.Heap` replay 10 random
  traces (fast/reuse/same-size, frees, OOM merge + retry): identical block
  layouts and zones after every operation.
- Sites checked by hand against C: sprite preload (lengths[] + archives
  largest first, +15+4 guard alloc), Field STM split load (pixels then
  geometry REUSE, five FAST tables), story owl sheets, scene_flow_load order.
  Fixed in the model: Field C owl sheets load only when the scene pack lacks
  source EnOwl (Field pack has it: model over-counted 215 KB).
- Remaining assumptions are printed by the tool (full C-item worst case,
  every cutscene layer for both ages, warp = 3 heaviest steady states).

### Changes (all measured with the model after each step)
1. **Per-layer objects (OoT rule).** Scene blob format 5 carries per-layer
   object masks; sprite preload and object slots follow only the destination
   layer (child Field: 405 KB sprites instead of 1,355 KB). Host picks the
   layer after `mirror_save` and halts if `play_init` picks another.
2. **Gohma CVQ1.** 564 source poses kept; 8-bit per-pose ranges (max error
   0.468 world units) in 32-pose sector-aligned chunks: 695 KB in 18 blocks
   instead of one 1.36 MB block. Hitboxes (GOHMAPOS.BIN) unchanged.
3. **Player demand clips.** `split_player_bank.py`: PLAYC.PFB (157 KB, all
   Saturn C cutscene clips, boot), PLAYRES.PFB (309 KB common set, first scene
   load until file/level select), groups HORSE 41 KB (adult, horse scenes),
   SWIM 11 KB (water boxes), FISH 5 KB (pond), BOTTLE/MAGIC/HAMMER/BOOM/HOOK
   (C items), 31 scene cutscene packs (all shots/branches, pinned until scene
   unload). Loads only behind the loading screen or when the pause menu closes;
   a CD-DA fanfare keeps the menu up. `Player_UseItem` refuses an item whose
   group is absent (cold action waits, no state change). Was 626 KB resident.
4. **Music levels chunked.** `shared/lib/music/music.c` envelope tables are
   32 KB chunks (FIELD.LVL 302 KB had no contiguous hole after most doors).
5. **Sprite pose caps (approved cut):** child Zelda and Impa 2 poses/clip
   (Field Zelda-escape layers), running man 2, Lizalfos 3. Clips, timing,
   contacts and drops unchanged.
6. **Ranch object limit.** Lon Lon Ranch lists 32 objects; the old limit 30
   rejected its blob (Ranch could not load). Union limit 32 (mask width), one
   layer's objects still <= 30 slots (import check).
7. Host `.bss` fit: cold loaders (Player groups, PLAYRES, mesh/CVQ1 loads) run
   from the HOSTCOLD cart section (`.cartt`).

### Result (tools/heap_peak_model.py on the built staging)
FITS: 101 scenes, 26,174 scenarios (both ages, every room and scene layer,
door/warp/title predecessors) + opening CS0-CS3 + three emerald chains.
0 fatal, 0 degraded (music/cutscene/save never refused).
Worst fitting peak 2,276,960 of 2,475,008 B (Field adult layer 4 from
Gerudo Valley); min sprite-guard margin 59,940 B (Field child from DMT);
min cart2 free 1,228 B (KAKARIKO house, adult); largest block NAVIPOOL.TEX 566 KB.
Child route peaks: Field 2.28 MB, DC 2.26 MB, DMT 2.21 MB, Gohma 2.05 MB,
Kakariko village 1.94 MB, Lost Woods 1.90 MB, Ranch 1.85 MB.
Before this batch: 542 fatal scenarios (9 scenes) and the opening chain.

### Build and checks
Matched Debug `build/game.iso` md5 11244013 (1,996/2,560 directory entries,
ISO keys exact). `.bss` ends 0x06083820, 2,016 B below SGL; HOSTCOLD
18,976/20,480 B; core end 0x027FF678 (2,440 B free). Previous image
(7580a290) copied to `build/preserved-debug-2026-10-13/`.
SH-2 audits: core 1,815 hw multiplies 0 failing; host 600, 0 failing; 81
packs 0 failing. Tests (Linux): fs_directory, actor_packs 11, core_sprites 7
(+layer case), heap_model_allocator 2, heap_peak_model 6 (fit), player_bank_split
3, player_pose_cache 5, all_map_registration 5 (core-aware: OOC poly counts,
layer masks; .COL from cd or disc-retired), scene_exits 3, scene_transitions 3,
cdda_mix 11 (+chunk row), music_area_trim, music_cd, chest_audio; Windows:
gohma 7, heap_profile 7, story_music 4. Fixed stale/broken fixtures:
map registration macro limits, transitions pack-admission stub, music area
trim, story music.

### Not done / human checks
- Runtime: nothing run. Image is a build checkpoint, NOT route-ready.
- Human checks: chest jingle, Field (day/night/Zelda escape), Ranch loads,
  DC Lizalfos look at 3 poses, Gohma motion, equip a bottle/slingshot then
  close pause (should be instant), new-game opening Navi flight.
- Item gate is host/model-checked only; no runtime proof of cold-item wait.
- Audio gaps unchanged (nature ambience, cutscene effects: silence = unfinished).

### Demand-loading proof (source review, 2026-10-13; image 11244013 frozen for human test)
Claim checked: a cold action never stays lost, since its clips arrive before any retry.
- Only item actions are gated (`OotCore_PlayerItemReady` at the top of `Player_UseItem`,
  before any state change). Gated: bottle (all PLAYER_IA_BOTTLE..BOTTLE_FAIRY, Ruto's
  letter included), the three spells, hammer, boomerang, hookshot/longshot. A refused
  press changes nothing; the next press retries.
- An item reaches a C button only via pause assign (gameplay.c c_assign), file load,
  level select or a new file. Pause close loads its group first (behind the menu, waiting
  out a CD-DA fanfare). Every scene load loads scene | C-item groups before `play_init`.
- C buttons hold inventory slots. Core item awards keep the group: bottle contents stay
  in the bottle slot, longshot replaces hookshot in its slot. Item_Give never puts a new
  item on C. A newly awarded boomerang/bottle/spell needs pause equip, which loads it.
- Forced item use outside C: Player_UseItem(ITEM_FISHING_POLE) loads per scene (fishing
  pond = FISH). ITEM_BOW (3) and ITEM_SWORD_CS are not gated. Fairy revive plays no bottle clip.
- Other group clips are not item-gated. Swim: all 27 scenes with WaterBoxes (checked against
  every `numWaterBoxes` in the extracted scenes). Horse: adult in Field, Lake Hylia,
  Gerudo Valley, Fortress, Ranch. Fish: fishing pond.
- Cutscenes: each scene's PCS pack covers every layer, shot and branch cued in that
  scene, plus actor-started cutscene actions placed by actor scene. Unproven actions stay
  resident. Group clips a pack needs set that group's bit in the scene. The pack loads
  before `play_init` and is freed only at scene unload. A chain into another scene loads
  that scene's pack at its own scene_enter. Saturn C cutscenes use PLAYC (resident from boot).
- Save/reload: session reset releases PLAYRES; scene_flow reloads it before the next scene.
  The fallback scene_enter in oot_core_frame only retries after a failed load, with PLAYRES
  already present.
- OPEN GAP (Astra correction): a heap failure at pause close is silent and UNRESOLVED.
  Retries happen at every later pause close and scene load, but recovery is not
  guaranteed. The heap model supports a fit; that is not runtime proof. Logged in
  BUG_FEATURE_LOG.

Human test order (Astra): 1) new game → Navi → Field/owl, chest jingle fully finishes;
2) Ranch entry/exit, Field day/night, Zelda escape; 3) equip bottle/boomerang, close pause,
use at once; 4) Gohma motion, Lizalfos combat, Zelda/Impa look; 5) full run through King
Dodongo, Ruby warp, save/reload.
