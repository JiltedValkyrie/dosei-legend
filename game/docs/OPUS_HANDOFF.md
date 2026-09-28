## Pre-regression commit checkpoint (2026-09-28)

Human authorized committing accumulated work before Sonnet starts the M3 regression
fixes. This checkpoint includes existing M3 implementation, camera/dialogue work,
audio quality changes, RAM moves and earlier visual fixes. It is not M3 acceptance.
Last Clean build: 6,064 B below SGL; 339 focused gameplay tests and five asset tests
passed in their respective runs. No new build or runtime verification for commit.

Known remaining regressions: giant pale plant-textured triangle in the forest,
upside-down field hearts, frozen legs while carrying a rock, and missing contextual
Check/Grab/Drop/Throw HUD actions. Sonnet's reviewed regression plan follows this
checkpoint. Preserve flat-colour shop items and dynamic controller labels. Also
verify shop browsing counter occlusion and field actor visibility in Kronos.
Earlier entries below are historical; their "nothing committed" notes predate this
checkpoint. No push authorized or performed.

> Latest Clean disc rebuilt (2026-09-28): `game/build/game-clean.cue`.
> BSS end 0x06082850; **6,064 B free below SGL**. Five asset tests pass.
> Includes Link draw priority, sign material setup, flat shop items and browsing
> counter mesh. Kronos verification pending. Nothing committed.

## Shop visuals follow-up (2026-09-28)

Human explicitly requested flat colours for every shop item. Exporter now uses
solid-colour face tiles for all seven item models; runtime no longer loads or
updates nut/heart scroll tracks. Four asset tests pass, including all flat items.
Browsing lacked the counter because fixed-camera masks are disabled in panorama
view. Export COUNTER.BIN from the original room depth mesh's counter region,
projecting its original backdrop material onto subdivided triangles. Draw only
while browsing; fixed view keeps its existing masks. Verify counter, owner legs,
shelf turns and sprite/VRAM/performance in Kronos; this is not runtime-proven.

## Field visibility / sign regression follow-up (2026-09-28)

Human reports Link often missing and multicolored sign faces in the new Clean disc.
Source fix: EnKanban material display list 0x000C30 now runs before each fragment
export, matching EnKanban_Draw. Gameplay Link now submits after terrain but before
props/NPCs/grass, so newly added actors cannot exhaust SGL work space before him.
Depth sorting is unchanged; this is budget priority, not an always-on-top overlay.
Exporter tests: 3 pass. Runtime cause of Link loss still needs Kronos confirmation.
Not rebuilt: Kronos is open on the existing disc; waiting for human to close it.

## Clean build update (2026-09-28)

Human authorized the Clean build. Assets and target code rebuilt into the existing
`game/build/game-clean.cue`. Verified map: BSS ends at 0x06082800, leaving
**6,144 bytes below SGL at 0x06084000**. The first link exceeded SGL by 4,752 B.
Moved forest vertex depth, tile depth/fog and mesh flags (10,763 B of arrays)
from high BSS into guarded Low Work RAM carves at offsets 0x5000..0x97FF.
Heap, sprite and polygon limits unchanged. Low RAM performance needs Kronos checks.
No commit or Kronos run. Earlier no-build checkpoints below are historical.

Additional renderer checks exposed an outdated forest host adapter (missing SGL
members/constants) and three room-bank assertions expecting 0x67 instead of the
exported 0x66 sort mode. These checks are not green; no renderer behavior was
changed to satisfy them. PowerShell reports NativeCommandError for compiler stderr,
but the build reached disc creation and the final successful map boundary check.

# Astra to Claude: M3c/M3d source checkpoint (2026-09-28)

Human confirmed you finished and assigned remaining M3c/M3d to Astra. **No build**
was run; existing disc untouched; nothing committed. Shared-file edits are finished
for this checkpoint. See [implementation, gaps and checks](M3CD_IMPLEMENTATION.md).

- Added source grass/rock/pot drops, placed hearts, carry/put/throw, prop bodies,
  readable/cuttable signs, decorative props/gossip reaction, five animated chests
  with source flags/rewards and Link get-item clip.
- Save v6 migrates old forest pickup bits; v2-v5 compatibility retained.
- Preserved your shop cursor/spin/repeat; added heart/nut primary-texture scroll
  tracks and safe VDP1 updates. About 205 KB cart data added; runtime budget unknown.
- Fado dialogue now exported; Kokiri/Saria close flags and house Mido rules wired.
  Greeting camera is still M3b work; 0x1001 close currently sets greeting flag.
- Removed automatic nutsball emitter. Fixed old Navi timer failure from the
  source talking/idle branch split; passes both standalone and in suite.
- Changed shared files: gameplay/save/demo/main, actor mesh loader, npc_draw,
  kokiri_sgl; actor/dialogue/Link/shop/prop exporters, makefile/build asset list.
  New world_props/world_signs/item_drop modules and tests. Last built gap remains
  **7,424 B before this work**. Do not call it current; no link/map measured.
- Verification: 339 focused host tests pass; SH-2 syntax-only checks pass for
  twelve changed C files. No target objects/link/map or Kronos verification.
- Next authorized build must regenerate all assets/headers together using the
  existing disc name. Check RAM/VRAM/sprite budget and Kronos checklist before
  declaring M3 accepted. Source-parity visual/physics gaps are listed explicitly.

# Claude: shop cursor, spin, hold repeat (2026-09-28, uncommitted)

- Cursor: EnOssan_DrawCursor port. gSelectionCursorTex IA4 mirrored to
  32x32, blue (0,80,255), 4 baked pulse steps (UpdateCursorAnim, faded by
  VDP1 half-transparency, hidden near alpha 0), x1.5, at the cursor item's
  projected focus (pos+5). CURSOR.RGB in cart carve 0x8800/0x2000.
- Item spin/slide: EnGirlA yRotation +0x1F4 while cursor/selected/refused,
  SmoothStepToS back; shopItemSelectedTween 0.15 to sSelectedItemPosition.
- Hold repeat: EnOssan_UpdateJoystickInputState port (push moves, accum
  past 500 repeats; reverse/release resets; zeroed while turning). New
  player_input menu_hold_x/y: D-pad +-70, analog stick scaled to N64 +-80.
- Navi test test_c_up_reads_the_hint: fails identically on HEAD 46edf80
  (worktree build) -> predates shop work. Not fixed.
- GAP (logged): heart/nut GetItem texture scroll (segment 8 TwoTexScroll)
  still static: VDP1 has no UV offset; needs per-frame tile rewrite.
- Clean gap 7,424 B. Gameplay+controls 234 run, only that Navi fail.
  main.o is newer than main.c: Astra's 4 px speaker gap is in the build.

# Claude: Kokiri Shop complete flow (2026-09-28, uncommitted)

- Shopkeeper model NPC15 (km1 + masterkokirihead + masterkokiri anim).
- Occlusion masks (build_interior_masks.py, interior_mask.c): room depth
  mesh -> per-surface 16px backdrop tiles, sort at farthest pixel + 16.
  Offline check: 0 in-front points hidden. Shop only; fixed view only.
- En_Tana shelves + 8 En_GirlA items (build_shop_props.py), source offsets.
- Browse view: talk -> Play_SetShopBrowsingViewpoint: SKYBOX_KOKIRI_SHOP
  (KSVR, 2 faces, rot.y 0.8) as panorama bank S4R2, Camera_Data4 eye
  (0,60,40) yaw 0x8000 + cameraFaceAngle, Link hidden (PLAYER_STATE2_29).
- EnOssan flow in gameplay.c: 0x9E hello -> 0x83 talk/quit, D-pad L/R turns
  30 deg to a shelf, cursor per EnOssan_CursorLeft/Right/UpDown, item text,
  A -> buy prompt (Buy/Don't), EnGirlA_CanBuy via save_item_buy: fanfare
  -> get text (locked view) -> 0x6B continue/quit; quick buy 0x84; 0x85/0x86
  refusals. Seeds/arrows refuse (no bag/bow). B ends (TestEndInteraction).
- Clean gap 9,056 B. test_gameplay 170: 1 fail test_c_up_reads_the_hint
  (navi timer 3001 vs 3002, code not touched by shop; check baseline).
- Not done: item spin when selected, analog stick hold-repeat, cursor
  sprite, item scroll textures. Kronos: whole flow, VRAM, frame rate.

# Astra: speaker gap reduced to 4 pixels (2026-09-28)

Human found the 8-pixel separator too large. main.c now shifts the bold name
four pixels down using two reserved font cells per distinct character; body
and marker stay put. Panel top moves down four pixels to preserve outer
padding. Retained rows still update only when changed. Reserved cells are
reused per name, with blank checks before first ownership. No global text/HUD
scroll. Kronos is open, so no rebuild; current disc still has the 8-pixel gap.
Build and visual verification pending. Same disc name; nothing committed.

# Astra: dialogue polish after human acceptance (2026-09-28)

Human confirms no text flicker, dynamic labels good, interior C-Up good.
Bible now records that limited acceptance and regression rules. Follow-up in
main.c only: fix bold speaker fallback (destination must be blank, not inked),
force white name glyphs, add 4 px top/bottom panel padding, and one blank
8-pixel row between speaker and body (human follow-up). Panel and page marker
grow/move with the body; gap cleared only on open, preserving retained text. Verified cause with
read-only live Kronos font inspection. No changes to npc_draw.c/build_actors.py;
Claude retains shop ownership. Clean build completed after Kronos closed;
same game/build/game-clean.cue. Current shared-tree boundary: .bss ends
0x060813b0, 11,344 B below SGL (not an isolated measurement of this UI edit).
Log: game/build/dialogue-polish-build.log. New spacing/bold still needs visual
Kronos verification; earlier human acceptance predates this polish.

# Astra to Claude: camera/text plan implemented (2026-09-28, uncommitted)

main.c is done. Final Clean build passes, including your ram_low.h equipment
move. Real final boundary: .bss ends 0x06080930, **14,032 B below SGL**.
Log: game/build/camera-clean-build.log (use the final boundary, not the
pre-link check of the previous ELF). Same game/build/game-clean.cue.

- Five houses start in original CI8 panorama; C-Up toggles original overhead
  JPEG. Shop remains fixed by source rule. Bank 4 room suffix = scene index.
  Collision remains the actual scene. Renderer cannot stream forest over it.
- Outdoor C-Up first-person: Navi first, grounded/free-action entry, full yaw,
  stick-relative pitch, 45-degree FOV, hidden Link, head-focus eye + collision.
  Exit actions consumed; pause/text/damage/death/doors restore valid view.
  C-Up edges latch until simulation; digital modifier cannot tilt view on entry.
- Hold-L free look retired; L toggles minimap. Both digital and analog routed.
- Dialogue writes changed rows only; glyph probes offscreen. Runtime tokens
  resolve before wrapping, preserve overflow pages and keep choices together.
  Menu vs gameplay tokens differ, including assignment's required modifier.
  1248 B cached text uses old cart slot 0x8000, guarded within 0x500 B carve.
- Clean target checked; new camera object has no software float imports.
  Host tests: gameplay/text 165, controls 63, camera 9, follow 36, room 4,
  interior assets 2, message parser 28. Label preference checks also run.

No Kronos acceptance claimed. Human checks: five houses both views and doors,
Brother long pages/choices, both pads/presets/custom jump, outdoor C-Up/Navi/
exit/pause/damage, sword/shield after Low Work RAM move. Source camera-entry
blend and separate interior talk framing remain omitted. Full audit and
limitations: CAMERA_TEXT_PLAN.md. Nothing committed; preserve shared changes.

# Claude: lock-on camera KeepOn1/Battle1 framing (2026-09-28, uncommitted)

oot_follow.c lock_frame: integer port of Camera_KeepOn1 (friendly) and
Camera_Battle1 (hostile) yaw swing + pitch + distance. Target is held
swingAngle off view centre (friendly 25..45 deg, hostile 10..80, by
distRatio), view turns by the source off^2/t1 curve when outside it, drifts
(0.02/0.05 x2/3 per 30 Hz step) when still. Pitch lerp init/final, head and
at pitch terms, clamp 0x3200/0x2AA8. Distance 120..140 / 180. Lock with a
target no longer runs the behind-Link Parallel swing. Not ported: animTimer
eye blend, BG collision pull-in, roll, fov, speedRatio (moving = 1).
Tests: 3 new (30.3 deg friendly, 17 deg hostile, turn-toward); oot_follow
36 OK. Clean build OK. RAM WARNING: gap 1,648 B. Another agent edited
cutscene.c/main.c/npc_draw.c/build_actors.py in the same window; cutscene.o
now pulls __divdi3 (596 B). Lock code is -Os. Kronos pending: lock on a
Kokiri and a Deku Baba, target visible beside Link, no jitter/spin.

# Astra: Navi flythrough Kokiri restored (2026-09-28)

Cause: main.c excluded all NPC drawing during cutscenes, and the flythrough
loaded scenery directly without NPC models. Gameplay placements are not the
correct substitute: SPOT04 layer 7 has seven EnKo (types 0..6) plus Mido,
with different positions/yaws (notably punching child at -641,120,454).

- build_actors now exports navi_npcs.h from actual room alternate headers,
  layer 7 selecting gKokiriForestIntroNaviFlyingCs. No Saria/Fado in this cast.
- Cutscene start releases prior NPC models; Navi loads just its eight models.
  Main draws the cast only during visible CUTSCENE_NAVI_FLY frames.
- Visibility uses source camera-eye distance / 4, instead of Link in house;
  conservative view-sphere culling avoids submitting offscreen NPC vertices.
- Source camera tracking uses +40 offset, preset 2 head+torso (type 0 exempt).
  Existing source idle/work clips and shared pose math retained. No gameplay
  registry, dialogue, target or save-state side effects.
- Source fade interpolation and NPC companion fairies still not implemented
  for this pass; do not claim full N64 cutscene parity.
- Actor/model tests 10 pass, new cast/bounds checks 2 pass. Camera-track
  offline sweep peak: three NPCs, 1284 polygons / 759 vertices at frame 553;
  plus full 2106-poly/1511-vertex scenery fits 3750/3200 SGL limits.
  Offline sweep is not target performance proof.
Clean build passes: 1344 B below SGL, log navi-npc-build.log.
Same game-clean.cue; Kronos flythrough visual/performance checks pending.
Nothing committed. Preserve Claude's parallel gameplay/camera work.

# Claude: BUG-009 Link scale fixed to source 0.01 (2026-09-28, uncommitted)

Link recipe 0.0145 -> 0.01 (44 units, matches Kokiri). Camera rescaled to
Player_GetHeight 44 (oot_follow.h dist 93/139, y -9; player_camera hang -37,
climb -14/-5). kokiri_collision head sphere 36. Tests updated to 44.
Clean build OK, gap 4,416 B. Full suite: 931 run; only failures are the 4
old host-compile errors + test_room_bank_policy sort 0x66 vs 0x67 (not from
this change; room bank code untouched). Kronos pending (see BUG-009).

# Astra: castle torch flames and chain cutouts (2026-09-28)

Human requested the N64 castle lantern flames in the Hyrule nightmare,
and removal of black rectangles behind drawbridge chains.
- Chains: source texture alpha already bakes zero-index holes. The opaque
  display-list flag made runtime enable SPdis, drawing those holes black.
  build_cutscene_props now sets chain transparency explicitly; dark metal
  stays intact. No whole-chain checker required.
- Flames: BgSpot00Hanebasi_DrawTorches + gEffFire1DL are the reference.
  Two billboards at (+/-260,128,690), source .008 scale (64x128 world).
  Original I4 scrolling noise and I8 silhouette combine with yellow/red
  primitive/environment colours. 32 prebaked scroll phases, 16x32 tiles;
  ordered alpha coverage replaces N64 blending. GATEFIRE.BIN is 9944 B,
  texture data 9216 B, 32 sprite slots; two extra quads per frame.
- Runtime loads/free/uploads with existing nightmare actor bank; draws only
  in visible nightmare world. No new permanent forest texture allocation.
  Original dynamic torch lighting/sound not added by this visual task.
- Six focused prop/room checks pass; generated-room tests now check the
  restored far-sort ground tags rather than requiring centre sort on all.
- Clean build passes: 4416 B below SGL; log castle-fire-build.log.
  Same game-clean.cue. Kronos visual check pending:
  flames stay at lanterns as camera/bridge move, animate, no black quad;
  chain gaps reveal background, chain links still readable.
No commits; preserve Claude's concurrent dialogue/camera work.

# Claude: dialogue names/bold/width + music rebake (2026-09-28, uncommitted)

- Music: all 7 banks rebaked for +33% budget (0x50000). Title/Kokiri/3
  cutscene RAW regenerated; house/shop bake in build. All <= 327,680 B.
- Text width: build_dialogue MAX_COLUMNS 34 -> 38 (box prints 38). Fixes
  clipped "I'm the one" line (0x100A). Choice rows still 36 after cursor.
- Speaker names: Fado (type 12), Know-It-All Brother (7/8/11), else Kokiri
  Girl/Boy by kw1/km1 body. OoT itself shows no names (human request).
- Bold name: main.c print_bold copies 1px-smeared Latin glyphs into unused
  SGL kana cells 0xA1..0xDF, found via slPrint map entries. Self-checks
  (space blank, one-ink glyphs, kana cell != ASCII alias) else plain text.
  Kronos check: name bold, no kana shown, pause/menus text unharmed.
- Clean gap 4,784 B. Gameplay/model tests 165 pass.
- Open P1: lock-on camera Link blocks target; OoT Battle1/KeepOn1 swing
  camera aside (our oot_follow.c is behind-Link only). Awaiting go.

# Astra: ground-over-actors streamed-room fix (2026-09-28)

Human supplied three angles at same spot: floor visibly covers Link/NPC bodies.
Texture warp is explicitly acceptable; this task is occlusion/order only.
Read-only live snapshot in build/ground-order-evidence: NPC type 4 at
(669,0,521); floor faces 25,337,362,444,478 are horizontal upward ground
(normal 0,-65536,0), large spans, but runtime attributes all have sort 0x67.
The resident exporter marks such ground SORT_MAX; pack_room hardcoded 0x67
for every face, so streamed rooms lost the mark consumed by forest_face_flags.

Fix: shared floor_uses_far_sort helper used by both exporters; streamed
textured and flat floor faces now carry 0x66. Existing runtime above-eye
centre-sort guard remains. Walls, small faces and downward faces keep 0x67.
No clipping, geometry, materials, texture density or actor-placement changes.
Room/exporter tests: 12 run, one skipped, remaining pass. Existing forest
partition host harness fails compilation from stale missing scene/ATTR stubs;
not counted as a pass. Build waits for human to close mounted Kronos.
Need human replay same angles and walk/turn/jump, plus walls/overhead checks.
Not visually verified, not committed. Use same game-clean.cue only.

# Astra: title freeze cause found and fixed (2026-09-28)

Reproduced the unchanged Clean disc in Kronos. Master SH-2 repeatedly stuck
at 0x0602fa74/0x0602fa80 in dosei_allocator_malloc, behaviour 2, request 12 B
(20 B with header). Stack returns through action_audio_init (0x060222fc).
Work zone begin 0x0606a078, high=end 0x06076878: all 51200 B claimed.
Cart zones still have room. SDK SAME_BLOCK_SIZE mode rescans the full first
zone forever because its append-failure branch only advances for TRY_REUSE.
This prevents the sound callback registration from finishing, before draw
registration. VBlank music continues; no VDP1 scene frames are submitted.

Fix: heap_profile.c routes exact-size allocations through a bounded scan,
preserves exact-hole reuse, and advances to the next zone when full. Shared
SDK unchanged. Five heap tests pass, including full-zone spill, total
exhaustion and exact-hole reuse. Clean rebuild passes: 5568 B gap (160 B cost). Runtime retest pending.
After-fix background Kronos attempts stalled before emulated CPU initialization;
no after-fix runtime pass claimed. Test processes stopped. Human cold boot needed.
No commit. Same game-clean.cue name.

# Astra: fresh-boot title rendering blocker (2026-09-28)

Human screenshot: title logo/copyright and background visible, music playing,
VDP2 58/60 FPS but VDP1 00 FPS; no title 3D scene. Human confirms fresh boot.
Observed game-clean.iso timestamp 08:43:05; Kronos PID 42768 start 08:51:02.
This does not match BUG-053's mounted-image rewrite evidence.
Latest m3b-audio.log reports successful Clean build, 5728 B gap.
Generated ACTION_PCM_BASE is 0x50000; later build picked up audio changes.
Astra has not rebuilt or changed runtime code; human build hold remains.

Diagnostic leads, NOT proven causes: music uses VBlank, so it can continue
without main-loop progress. Boot order: scene/demo init -> music init ->
action_audio_init -> viewer_draw registration -> jo_core_run. Check action
upload completion and callback registration, then first viewer_draw,
demo_update/room update and SGL sync. Draw callback registration result is
unchecked. Need live execution evidence before choosing a fix.

# Claude: M3b NPC head/torso/body tracking (2026-09-28, uncommitted)

Ported Npc_TrackPoint + Npc_TrackPointWithLimits (z_actor.c) with all 13
sNpcTrackingPresets and Math_SmoothStepToS, 20 Hz (npc_pose.c, pure C).
- Modes per source: EnKo ChildStart/ChildStone table by type (D68/E18/034/
  F70/EB0/F20), preset 2 or 5, func_80A97BC0 yOffset, lookDist 180/240+20;
  EnMd_UpdateTalking (Walk NONE, Watch/talk FULL, <170 in-front HT);
  EnSa forest FULL. trackPos = Link feet.
- FULL_BODY turns shape.rot.y: gameplay_npc_turn/gameplay_npc_yaw. Live
  copies (gate Mido, type-3 ring) keep own facing. Reset on scene load.
- NTR2 tracking file: flags bit0 head, bit1 torso subtree; per frame adds
  torso-parent basis/origin (54 B/frame). Torso override per source axis
  order: EnKo Rx(-y)Rz(x) limb 8, EnMd Rx(x)Ry(y) TORSO, EnSa Ry(y)Rx(x)
  limb 9. Head then torso applied; focus follows both.
- RAM: npc_draw + cold pose code built -Os. Clean gap 5,728 B (was 7,152).
Verify: Clean build OK; 218 focused tests pass (new track/limit test).
Not ported (logged here): fidget tables, AUTO_TURN (no slice user), dialogue
animation swaps, blink/fade. Kronos pending: NPC turn/head/torso look right
from several angles, talking Kokiri turns to face Link, no torso tearing.

# Astra: M3b integrated checkpoint (2026-09-27, uncommitted)

Human assigned M3b to Astra. This supersedes the stopped Claude note below.
Use normal Clean disc name only: `game/build/game-clean.cue`. Human rejected
the separate review-disc name; those review image files were removed.

Implemented/reviewed:
- Existing four new interiors build. Stable scene-first NPC ordering preserves
  forest identities. Fixed EnKo type-7 rotZ filtering: Know-It-All has THREE
  child brothers, not five. Seventeen placements including hidden house Md/Sa.
- `build_npc_models.py`: 15 ROM models, original initial animation clips,
  per-vertex flex ownership, source head-parent tracking bases and face-only
  textures. Corrected EnKo ENV cloth/boot tint handling after offline preview.
- `actor_mesh.h` shares the existing KFR1/CVA1 loader in cutscene_actor.c.
  `npc_draw.c` owns scene allocations and uploads visible model types after
  the room's textures; room generation invalidates the NPC bank. Interiors
  draw their NPCs too. `npc_pose.c` applies integer source head-pivot math;
  focus updates the existing actor/attention identity. No second registry.
- EnKo type 3 follows its source 80-unit home ring; Mido uses live facing.
- House/shop sequences 31/85 baked at approved sample budget. Seven-bank
  MUSICTRG is 24,444 B at cart 0x76000/0x6000; fixed carve now 0x7C000.
  Dialogue stays 0x71000/0x5000, title paths 0x6F800. Fast door changes retry
  their desired music after an in-flight fade instead of losing the request.
- BUG-006: valid ledge climb claims A before talk; existing text/menu retains A.

Verification: Clean build/map gap 7,152 B (.bss end 0x06082410).
Host gameplay 162, actors 7, pool 42, character materials 7, model/pose 2,
area audio 2, ledge priority 1, text recoil 1 pass. Opening-audio harness
still fails compiling its pre-existing missing camera/menu-duck stubs.
Logs in game/build/m3b-*.log. Offline model preview is not a Kronos check.

Still open: full per-type torso/auto-turn modes, dialogue-triggered animation
changes, blink/fade parity and post-Emerald path/pose behavior (M5/M6).
Shopkeeper/shelves/full stock remain M3d. NPC body collision coverage needs
source review; the existing Mido gate collision remains. Do not call M3b
fully source-complete from this checkpoint.
Kronos pending: every interior enter/return/reload; visible models, head turns
and focus from multiple angles; forest room-bank changes; source music and
fast doors; three-choice tutorial; ledge beside NPC on both pads. Standard
peak RAM/sprite readings remain deferred by human. No commits/approval asked.

# Claude: M3b WORK IN PROGRESS - stopped mid-task (2026-09-27, tokens out)

State: uncommitted, NOT BUILT, NOT TESTED since these M3b edits. Resume here.
Done in code:
- build_scene_table.py: 4 interiors added (kokiri_home/3/4/5, save ids
  6-9); doors both ways generated; backdrops S3..S6 R0.RGB built. Clean
  built OK after this step (13,008 B).
- build_actors.py: interior people added with new `scene` field in
  kokiri_npc_t; En_Ko child types per EnKo_CanSpawn (forest <7 + Fado 12,
  shop 10, Know-It-All 7/8/11, Twins 9, Mido/Saria houses none). 19 people.
- gameplay.c: gameplay_npc_present() (scene + EnMd_ShouldSpawn/EnSa_GetType
  child rules), gate_mido() (only forest Mido runs the gate), presence used
  in sync_npc_actors, find_speaker, gameplay_npcs_present, close_talk Mido
  check; kokiri_sgl.c fairy draw loop filters. save_state.h adds
  EVENTCHKINF_OBTAINED_ZELDAS_LETTER 0x40.
Next steps:
1. Clean build; fix compile errors. Run test_gameplay (fixture may need
   scene field / save_state.scene_id), test_actors, test_dialogue tests.
2. Check other in_forest() NPC paths (Navi attention, minimap, 2349 area).
3. Verify dialogue convos exist for ENKO types 7-11 (Know-It-All/Twins/
   shop kid); house Mido texts (EnMd_GetTextIdMidosHouse) not exported yet
   (house Mido hidden until EVENTCHKINF_1C, M5).
4. Interior music still forest theme (PENDING note in enter_world).
5. Then real NPC models (M3b main), BUG-006 near ledges.
Pending human: three-choice runtime, Astra code review, all Kronos checks.

# Claude: pool count clarified + required-spawn retry (2026-09-27)

57 INCLUDES the existing 10 forest NPCs (room 0 Ko 8/Md/Sa) and 5 Babas
(room 1). Reserve 39 of 96. Required spawns: NPCs already retried every
step (sync_npc_actors). Bug fixed: karebaba_sync returned early once any
Baba lived, so a pool-full miss lost that Baba (and its stick drop) for the
room visit. Now missing placements retry each sync, no duplicates; a failed
spawn clears its stale handle; dead Babas stay pooled (no respawn/reward).
Rewards (chest/rupees/wonder/grass) are static tables, not pool. New test:
full pool -> 2 Babas, retry no dupes, free -> all 5. Clean 13,472 B.

# Claude: pre-M3b dialogue carve + actor pool budget (2026-09-27)

Dialogue carve moved 0x8000/0x3000 -> 0x71000/0x5000 (20 KB; 8,896 B free
for M3 text). Fixed carve 0x71000 -> 0x76000. 0x8000..0xAFFF now unused.
ram_cart.c has compile-time guards: all 15 carves in order, no overlap,
inside RAM_CART_FIXED_BYTES. main.c static-asserts pool fits its carve.

M3 pool budget (docs/M3A_ACTOR_MANIFEST.md; child night = main header in
spot04, same counts). Owners:
- gameplay.c static tables, NOT pool (unchanged, one owner each): En_Kusa
  16, En_Kanban 10, En_Item00 rupees, En_Wonder_Item 12, En_Box, grass drops.
- Pool today: forest NPCs 10 (scene-wide), Karebaba 5, push block (Deku Tree).
- Pool candidates to port, child day: room 0: Ko 8, Md, Sa, A_Obj 8, Ishi 4,
  Gs 1, Sw 1, Wonder_Talk2 4, Bean, Hana 5, Makekinsuta, Mure2, Door_Ana,
  River_Sound, Kankyo = 39; room 1: Treemouth, Gs 2, Karebaba 5, Kankyo = 9;
  room 2: Goroiwa 1. All three rooms at once = 49.
- Runtime: Obj_Mure2 params 0x0202 -> 8 children. 49 + 8 = 57 worst.
- Reserve for drops (Item00 from rock/pot/Baba), Navi, effects: 39 slots.
ACTOR_POOL_MAX 64 -> 96 (72 B SH-2 actor_t: 6,912 B, same 0x2000 carve,
no move). actor_spawn full-pool misses now counted
(actor_sys_spawn_failures), never silent. Existing tests cover stale
handles, deferred reap, room unload keeping scene-wide actors; new check
on counted failure. Clean .bss 0x06080B20, 13,536 B below SGL. No Kronos.
Interiors (<=8 actors each) far below budget.

# Claude: M3a contracts landed (2026-09-27, uncommitted)

1. Manifest: tools/build_actor_manifest.py -> docs/M3A_ACTOR_MANIFEST.md.
   Forest + 6 interiors, all layers (child night/adult fall back as source),
   params decoded (GI/ITEM00 enums), objects, transition actors, and a table
   of 30 child-day kinds NOT ported (interior NPCs, Tsubo, Ishi, Mure2, Gs,
   Hana, Tana, Cow, Wonder_Talk2, heart Item00 x7, Mido's 4 chests...).
   Budget: forest room 0 = 78 actors vs ACTOR_POOL_MAX 64; static-table kinds
   (grass/sign/item/wonder) must stay out of the pool or pool must grow (M3b).
2. One grant path in save_state.c: save_item_give (Item_Give subset: rupees,
   heart, stick 1/5/10, nut 1/5/10, sword, Deku shield), save_item_can_buy /
   save_item_buy (EnGirlA_CanBuy order: owned/full, then rupees, fanfare on
   first get; refusal changes nothing, success charges once). Chest, shop,
   rupees, Karebaba stick now call it.
3. Save v5: nut_owned/ammo/upgrade appended (301 B payload); v2-v4 load
   with no nuts. Save format change: old v4 files migrate.
4. Choices: build_dialogue THREE_CHOICE + dialogue_branch[] (En_Ko 0x1035,
   0x1038, 0x103E per EnKo_UpdateTalkState). Cursor vertical, clamped; NPC
   choice A/B/C-Up confirm cursor (Message_ShouldAdvance); shop keeps B =
   cancel (EnOssan_TestCancelOption). Shop cursor now clamps, no toggle.
Clean .bss 0x06080AD0, 13,616 B below SGL. DIALOG.TXT 11,584/12,288 B.
Focused host tests pass (+10 item_give, +1 save, +3 choice). No Kronos.
Human: shop buy/deny/cancel both pads, old save loads, chest/rupee/stick.
Next: M3b interiors + NPCs.

# Claude: proceed M3a; defer BUG-035 measurement (2026-09-27)

Human chooses feature work now and batch testing later. BUG-035 stays P2,
open/deferred; new peak readings are NOT a prerequisite for M3a. Proceed with
M3a under the existing authorization. Keep capacity/allocation guards and cart
placement for large buffers. Do not report the old peak as a current reading.

Cart-table change reported by Claude: Clean SGL gap 14,656 B, Standard 11,360 B;
not independently runtime-verified. Title camera and title/forest/cutscene music
checks remain pending for fresh-boot batch playtests. No Git publication.

The open Kronos corruption was traced to its mounted ISO being rebuilt during
play (BUG-053), with exact +2-sector page/font reads. That older session cannot
validate the newly moved tables. Cold boot the completed image; never rebuild
mounted disc files during a test. Preserve separate BUG-048/049/052 recovery
acceptance checks; this peak-reading deferral does not close death/save bugs.

# Claude: do not rebuild mounted test ISO (2026-09-27)

BUG-053 investigated live in open Kronos, read-only. After Continue in Link's
room the System page/font are corrupt. BOTH live buffers match current ISO
exactly two sectors late: PAUSE50 2813 instead of 2811; PAUSEFNT 2888 instead
of 2886. Session started 22:13:01, ISO rewritten 22:15:58. Running binary still
has old cart layout. Mounted media replacement invalidated cached file positions.
No renderer fix made; no fresh-boot Continue pass claimed. Preserve current
session until human cold boots finished image. Stop rebuilding mounted media;
close emulator first or use immutable test disc copy including audio tracks.
Details: CONTINUE_MENU_CORRUPTION_2026-09-27.md. BUG-049/052 still need their
own runtime checks. Do not infer their resolution from this diagnosis.

# Claude: BUG-043 RAM freed, cart tables (2026-09-27)

Astra option 1. New tools/build_cart_tables.py (build.sh after title paths)
writes MUSICTRG.BIN (5 banks' triggers, 9,792 B) and TITLEPTH.BIN (8x65
points, 5,208 B). main.c text_file_load puts them in new fixed carves
0x6D000 (0x2800) / 0x6F800 (0x1800); RAM_CART_FIXED_BYTES 0x70000->0x71000.
Bind checks magic, per-bank counts, exact size; missing/stale = boot error
like DIALOG.TXT. Music banks now non-const; triggers pointer set by bind.
Sprite limit stays 2400. Clean .bss 0x060806C0, 14,656 B below SGL (was
~240-288 B); Standard 11,360 B. Boot reads file via temp heap then frees.
BUG-049 fallback: failed other-scene load reloads resident scene (collision
may be half-replaced, BUG-002), spawn 0, mode PLAY.
Focused tests OK. 8 host tests (title_flights etc.) fail with or without
this change (host gcc DLL compile), pre-existing. No Kronos.
Human: Standard build row 27 heap `w<live>/<peak>` in forest, maze, shop,
house, after death+Continue; title camera moves; title/forest/cutscene music.

# Claude: Game Over save reloads into death (2026-09-27)

Human reports saving on Game Over, then loading that save starts Link dying.
Logged BUG-052, P0, M2e save/load recovery blocker; prioritize before further
M3 expansion. Cause unverified. Inspect saved health, load restoration and
transient death-state reset; do not assume save corruption. Separate from
BUG-049 Continue freeze. See bug log for acceptance checks. Logged only;
no implementation changes or agent runtime verification this turn.

# Human priority update: BUG-050 deferred (2026-09-27)

Death voice downgraded to P3 / audio polish at human request. Keep open;
no blocker for RAM work or M3. Human identifies adult Link's voice; built
sample/playback cause remains unresolved despite source mapping checks.
Keep half-rate policy. Revisit at M8 audio polish or next death-audio work.

# Item assignment hint correction (2026-09-27)

Human says controller labels and item assignment look good. Do not infer that
all pad combinations or save/reload were tested. Screenshot shows missing
modifier in analog pause: gameplay UI_KEY_C intentionally returns empty there.
Pause now uses its own physical-modifier label: C / Xbox LB / PlayStation L1;
N64/GameCube show Sat C because no native modifier mapping is defined. Hint
shows bracketed modifier + D-Pad on either pad; gameplay mapping unchanged.
Five preference tests pass; all five modifier strings checked nonempty and
hints fit 30 columns. Clean log reports ISO/CUE built, .bss 0x06083F10
(240 B below SGL with concurrent changes). PowerShell wrapper returned 1
despite completed build log. Visual check pending. Preserve other agents' work.

# Claude: death-flow fixes + RAM report (2026-09-27)

Uncommitted, demo.c only. BUG-048 Save No: dialogue flag now stays set
while dead (was reset each step, D-pad edges dropped). BUG-049 Continue:
new respawn_after_game_over() respawns in resident scene without disc
reload; failed load never sticks in LOADING; stale step abandoned. Cause
probable, not reproduced. BUG-050: source mapping verified; likely 5.5 kHz
bandwidth, human decision. BUG-016/032/047 closed; BUG-051 boulder no roll.
Clean: .bss 0x06083EE0, 288 B below SGL. 253 focused checks pass. No Kronos.
Human: die in forest + interior, Save No/Yes, Continue Yes/No, both pads.
RAM candidates for M3 (Astra pick): title paths 5.2 KB + triggers 9.3 KB
.data -> disc/cart; JO_MAX_SPRITE 2400 cut needs human `sp` peak reading.
Heap arena 51,200 B; last peak 50,692 B (BUG-035), unchanged.

# Claude: child death voice report (2026-09-27)

Human reports child Link sounds like adult Link when dying (BUG-050, P2).
Check age-specific sample selection and playback pitch/rate; cause unverified.
Keep half-rate samples at correct pitch. Check with M2e death-flow repairs;
BUG-049 Continue freeze remains the priority. Logged only, no code change.

# Claude: human-reported death-flow blockers (2026-09-27)

Human asks to log two runtime bugs: BUG-048 (P1), death Save Yes/No only allows
Yes; BUG-049 (P0), Continue Yes loads Link into sky/nowhere then freezes.
See BUG_FEATURE_LOG.md for evidence and acceptance checks. No diagnosis,
agent reproduction or fix yet. M2e owner Claude: prioritize the Continue blocker
before further M3 expansion; this is not BUG-045's cosmetic follow-up.
This turn records bugs only; no runtime code changed.

# Human directive to Claude: start M3 (2026-09-27)

Claude: the human now asks you to start M3, Kokiri Forest fully alive.
Use M3_KOKIRI_PLAN.md; preserve the working sword chest, shield shop purchase,
Mido gate, M2 combat and concurrent pause/item fixes. This authorizes starting
M3 despite the earlier sequencing note; it does not declare M2 review complete.
Keep outstanding M2 runtime checks visible and fix severe blockers first.

Inspect current dev diff before editing; shared work is uncommitted. Extend
remaining interiors, NPC dialogue, props/rewards, chests and full shop from the
M3 plan. Check original actor/drop behavior in each actor task. C-item HUD and
stick/nut/slingshot use remain M4, not this start request.

Last shared Clean build: .bss 0x06083E40, only 448 B below SGL; retain capacity
guards and account for memory before adding resident data. Build Clean; run
focused checks and report actual runtime verification separately. Read the
updated root README for current controls/options. No commit, merge or push
without the human's explicit approval after review.

## Item counts, assignment and text recoil (2026-09-27)

Items shows live stick/seed counts and Down/Left/Right bindings. Plain D-pad
navigates; hold Saturn C + Down/Left/Right assigns an owned item on either pad.
Gold marks assigned items; blue marks cursor. Save v4 appends bindings; v2/v3
migrate with empty slots. Live stick/slingshot weapon actions remain pending.
Baba events are per-step and consumed once: first-stick fanfare no longer
restarts during text. Text/menu blocks knockback and weapon recoil, clearing
residual push. 265 focused host checks pass; Clean build passes, .bss ends
0x06083E40 (448 B below SGL with concurrent UI changes). No Kronos run or commit.
Human review: first-stick sound, text after hurt/rebound, counts, all assignment
directions on digital/analog pads, save/reload. Preserve concurrent UI edits.

# Codex: full-colour pause carousel - 2026-09-27

Map marker follow-up: larger white/gold current-region marker, with a slow
two-second gold brightness pulse on the live UI clock. White ring and dark
outline stay visible. Drawn into VDP2 page cells; no extra VDP1 sprite or asset
allocation. This marks Kokiri Forest, not Link's exact position. Also supplied
the missing local `analog` in the concurrent Items-page label block to compile.
Human Kronos review pending; no commit, merge or push.
Pulse validation: 6 renderer tests pass. Clean log reports ISO built and
.bss end 0x06083e40 (448 B below SGL with concurrent gameplay edits).
PowerShell wrapper returned 1 despite the completed build log.

Uncommitted map-frame follow-up: the enlarged map now has an eight-pixel
rim made from the original page's stone border. Frame sits outside the
288x171 map; terrain, aspect ratio and VRAM allocation are unchanged.

Uncommitted readability fix after human screenshot: replace thresholded,
downsampled OoT glyphs with Jo's native 8x8 bitmap (same 1024-byte font asset).
System has opaque dark text beds; pad row moved 21->20 and controls 23->22,
with shorter OK wording to fit PlayStation labels. All page text uses the
native font, still rasterized into RGB so the carousel carries it. Preview:
build/generated/system-readable-preview.png. Human Kronos check pending.
Do not commit, merge or push this follow-up before human check/approval.

Clean build passes; .bss end 0x060836B0, 2,384 B below SGL. 29 focused checks
pass (12 pause/health assets/state, 6 actual renderer, 11 minimap). Packed
map/System previews inspected. No Kronos run. RAM remains tight (BUG-043).

Supersedes the NBG2/4bpp pause layout below. Every pause page is now direct
RGB555 (153600 bytes), not a 13-colour or regional-palette approximation.
World map keeps aspect ratio; reduced cloud opacity preserves unvisited-region
shading while revealing terrain. System's baked SAVE heading is replaced by
repeating its own clean border strip, including the topmost lettering pixels.

Pause temporarily uses NBG0 RGB cells and hardware reciprocal zoom/scroll.
Pages zoom/slide out and the next page zooms/slides in (12 ticks each at
60 Hz). Text is rasterized from the original OoT glyphs into the same page,
so labels move with it. This is a scale/slide carousel, not a 3D perspective
rotation. NBG1 keeps the frozen interior bitmap; VDP1 world remains frozen.
Font, HUD, scroll/window state and VRAM fetch schedule restore on close/failure.

Memory: cells B0 0..0x1FFFF plus B1+0x8000..0xD87F (last cell transparent).
Two-word names use A1+0x1C000..0x1FFFF: unused bottom 16 rows of the existing
512x256 bitmap, outside the visible 320x240 room. B1 font and sky untouched.
Pause borrows these ranges only, with exact cart backup. Fixed cart carve now
0x70000: page/font at 0x1D000/0x26000, backup at 0x43000/0x29880. No VDP1 cost.
RGB uses legal ZOOM_1 enlargement (1.0x to 1.2x), not sub-1x RGB reduction.
Cycle schedule: 4 RGB fetches + 4 CPU slots per B bank; 1 NBG0 name + 4 NBG1
bitmap fetches + 3 CPU slots in A1. No pause palette allocation.

Human Kronos: all five pages in forest AND Link's house; both turn directions,
fast taps and Start during animation; System heading, save failure, owned-item
colours, map terrain, font/HUD/interior restore after closing. No emulator run.
SGL reciprocal zoom reference:
https://docs.exodusemulator.com/Archives/SSDDV1R1E/refe/func3/func62.htm

# Earlier: controller preferences, pause backdrop and map - 2026-09-27

Urgent Navi follow-up: cutscene cue channel 8 now calls the gameplay fairy
renderer with the scripted position, neutral white/blue glow, animated wings,
heading smoothing and the same 12-unit pulsing body. Removed legacy 16-unit
static glow-only sprite. No additional textures or VRAM. Human opening check
pending; existing dialogue checkerboard is separate from Navi's glow.

Final Clean build passes: .bss end 0x06082B60, 5,280 B below SGL. 250 focused
checks pass (155 gameplay, 61 controls, 11 pause/health, 7 button HUD,
11 minimap, 5 preferences/audio/freeze). Packed map preview inspected;
hardware palette/keycap alignment and backup persistence await human Kronos.

Saved Saturn/Xbox/N64/GameCube/PS4-5 label presets, custom jump and Reset are
on System. Separate DOSEICFG record; no adventure save-format change. Presets
only change labels; jump binding replaces its selected physical button's
gameplay action, menus unchanged. N64 default jump remains Y with no HUD label.
Pause freezes visible world animation, grey dither reveals it, music ducks
6 dB independently of fades/SFX. Enemy-map status hidden unless cheat enabled.
Map enlarged 216x128 -> 288x171 with near-exact source aspect and eleven
regional palettes (up to 165 colours). Clouds retained. Clean L/R keycaps have
only runtime preset labels, no original letters underneath.
VDP2 ownership: label maps B0+0x12000..0x13FFF reserved (5344 B used); map
CRAM 848..1023, record 39952 B inside existing 0xA000 cart carve. No VDP1 cost.
Human review: all label modes on both pads, custom jump/reset and power-cycle
settings, failed settings save, pause music restore/world freeze, map clarity,
L/R labels and HUD restoration after leaving every page. No Kronos run/commit.

# Earlier: System page, selection colours, session enemy-map cheat - 2026-09-27

Clean rebuilt successfully; .bss ends 0x06083470, 2,960 B below SGL.
193 focused checks pass (155 gameplay, 17 game mode, 10 pause/health, 11 minimap).
No Kronos run or commit. Preserve Claude's Baba collider and digital Z/C fixes.

Start -> R from Equipment now reaches SYSTEM (fifth page). Save opens the
existing real backup save confirmation. Load and Title show Yes/No with
"Unsaved progress will be lost", default No; B cancels. Load opens the existing
file-select screen only after Yes. No automatic save. Start closes any prompt.
System also reports Controller 1's actual detected type and enemy-map ON/OFF.
A 3D pad in digital mode reports as a digital pad; hardware gives no distinct
3D identity in that mode. Selection outlines are light blue, equipped gold.

Cheat repair: old renderer only knew debug launcher/projectile, so Clean showed
no new Babas. It now scans the active actor pool for hostile enemies/bosses in
any mapped scene. The code's completing Start is swallowed until release,
so it no longer immediately pauses and hides the map. Other Start presses work.
Live-play acknowledgement uses SCSP; the CD fanfare is limited to frozen UI.
State persists across scene/room changes and in-session respawn, never enters
save data, clears on new/load file or ending the session at title/load menu.
Tests compile real cheat state functions and actual VBlank Start routing.

Files: main.c, demo.c, gameplay.c/.h, game_mode.c, minimap.c/.h,
pause_window_state.c/.h, pause_windows.c, build_pause_windows.py and focused
tests. New PAUSE50.BIN is the System-page background. No extra VRAM allocation.
Human batch: System save/no/yes, Load/Title No and B preserve play, Yes changes
screen; digital/3D/disconnect labels; blue vs gold; enter cheat, change rooms,
see Baba dots, save, load again and verify OFF. No checks claimed on hardware.

# Codex to Claude: pause windows and live heart HUD ready - 2026-09-27

Human requested four OoT pause pages on VDP2, owned items only, then hearts.
Implemented Items / Map / Quest Status / Equipment and save window with original
page artwork. Start opens/closes, L/R pages, D-pad cursor, A equips real owned
sword/shield; B opens save confirmation. Actual backup-device result is shown.
New menu_dx/menu_dy/menu_page fields preserve menu_step for dialogue/file select.
Keep these additions when touching player_input/demo/gameplay for M2e.

HEART HUD READY FOR DAMAGE: health_hud.c reads save_state.health and
save_state.health_capacity directly, 16 units/heart. No call or notification
needed from Claude's damage/healing/death/continue code. Original five fill
textures, source fraction thresholds, pulse and up to two rows of ten hearts.
No VDP1 slots: NBG2 cells/palette, atlas in VDP2 RAM. Pause uses a 40 KB cart
carve at 0x1D000; RAM_CART_FIXED_BYTES is now 0x27000. See PAUSE_HUD_UI.md for
VDP2 ownership; do not reuse these cells/CRAM for Game Over windows.

Final Clean build passed with current Game Over changes; .bss ends 0x06082DF0,
4,624 bytes below SGL. 153 gameplay + 7 pause/health + 6 button HUD + 8 minimap
checks passed. No Kronos run, no commit. Human batch review still pending.
Window coverage is implemented, not full KaleidoScope parity: 3D page flips,
animated Link portrait, OoT proportional item-name font and future item/quest/
dungeon actions remain. Owned-only display is deliberate. See BUG-046.
Files: pause_windows.c/.h, pause_window_state.c/.h, health_hud.c/.h,
health_hud_state.h, build_pause_windows.py, build_health_hud.py; small edits in
main/minimap/gameplay/demo/player_input/build integration. Preserve shared edits.

# Codex: silent Clean audio startup fix - 2026-09-27

Human reported no sound. music_banks.c still hardcoded TITLE_PCM_BYTES=480046
after music was halved to 240048 bytes. music_init rejected the stale size
against MUSIC_SAMPLE_LIMIT before SCSP setup; main then skipped action_audio_init.
This affects any rebuilt variant, not a deliberate Clean mute.
Removed the hardcode; title generator and current title_score.h now export
TITLE_PCM_BYTES. main reports a failed music load even with Clean HUD hidden.
Title-size regression reproduces the missing metadata and now passes;
15 action-audio tests also pass. Clean rebuilt successfully; human listens.
Files: shared/tools/build_title_audio.py, shared/assets/audio/title/title_score.h,
game/src/music_banks.c, main.c, tests/test_title_audio_size.py. Audio samples
and Claude's action-audio logic were not changed by this fix.

# Codex: gameplay button HUD implemented - 2026-09-27

Human expanded the UI request to the gameplay button cluster and selected
Saturn labels: A interact, X sword, C directions. Codex owns minimap.c/.h,
build_minimap.py, new build_gameplay_hud.py/gameplay_hud_state.h and HUD tests.
Small main.c edit removes the old A: Talk/Open/Enter text; makefile adds header
dependencies. Claude should keep ownership of hint/gameplay/input/audio logic.
Graphics reads existing gameplay.navi_calling and prompt/equipment fields;
no new gameplay callback or control remap required. No external message sent.
Implementation complete: original button/sword/action/empty-C/Navi artwork,
Saturn A/X/C identifiers, independent map/button visibility and source-timed
Navi blink. Empty C slots remain empty until actual item assignments exist.
The direction label switches live to D-PAD for a connected 3D pad in analog
mode, and back to C in digital mode/disconnect, using the same Jo input-type
check as demo.c. An eight-cell patch avoids duplicating the HUD variant maps.
Label follow-up: 6 HUD tests pass; Clean rebuild passed with current shared
M2 code (2,384 B work-RAM gap). Earlier 12,304 B figure below was the prior build.
BUTTONS.BIN uses 3,552 VDP2 bytes, no VDP1 slots; minimap stays pixel-aligned.
Clean built, 13 focused checks pass, 12,304 B work RAM spare. Human graphical
review pending with full M2. See NAVI_PROMPT_PLAN.md for files and limitations.
Do not duplicate this UI implementation while continuing M2 gameplay work.

# Codex: obsolete action notices removed - 2026-09-27

User requested removal of bottom-left Sword swing / Grass cut text and related
obsolete notices. Removed main.c action_hint declaration, call and function,
including Shield raised and sword/shield-equipped control notices. Existing
interaction prompts remain. Source/diff checks pass; include in Claude's next
Clean build with ongoing M2 work. No emulator run or separate build performed.

# Codex to Claude: Navi prompt implementation plan - 2026-09-27

Implement the N64-style on-screen Navi C-Up prompt alongside the hint flow.
See [NAVI_PROMPT_PLAN.md](NAVI_PROMPT_PLAN.md) for source artwork, coordinates,
blink/visibility rules, existing VDP2 allocations and integration checks.
Proposed path: shared NBG2 HUD cells, fixed screen-coordinate page, independent
minimap/prompt visibility; no VDP1 sprites. Palette reservation needs audit.
Codex changed docs only. Claude retains code ownership; human checks final M2.

# Human directive to Claude: finish M2 before human review - 2026-09-27

- Claude owns continued implementation; Codex is relaying this directive,
  not taking over the M2 work.
- Continue and finish all remaining tasks in M2_COMBAT_PLAN.md before asking
  for human review. Do not wait on the M2d.1 Navi acquisition visual check
  or request separate human approval for each camera/attention step.
- Complete remaining lock-camera work and M2 milestones with source checks,
  focused tests and Clean builds. Record pending visual checks together for
  one human review of the completed M2 batch. Do not claim untested parity.
- Human handles Kronos. No agent background emulator checks.
- Fix severe blockers as found; log minor gaps without stopping M2 progress.

# Codex: forest load capacity fix - 2026-09-27

- BUG-041: six attention glows exposed an incomplete resident VRAM budget.
  Old S1R0/S1R1 exceeded capacity by 1,952/2,080 bytes; sprite slots fit.
- Budget now includes all 40 runtime sprites, 20,160 bytes. User accepts
  lower detail for stability: forest density allocator reserves those plus
  32 KiB; rebuilt banks leave 33,504/34,784 bytes (92.5%/92.2% used).
  Geometry and glows retained. Mirror reuse still pending. Bible updated.
- Changed tools/vdp1_budget.py, tools/build_hybrid_scene.py, capacity diagnostics in
  src/kokiri_sgl.c, tests/test_vdp1_budget.py. Existing shared edits preserved.
- Clean image built and 4 focused tests pass. Human Kronos check: no visible
  difference after texture reduction. BUG-041 closed.
- Human handles Kronos testing; do not run background emulator checks.

# Claude to Astra: Navi anchor, glow, sparkles - 2026-09-27

- Anchor traced: Attention_SetNaviState -> naviHoverPos = player focus.pos
  (head limb x sPlayerFocusOffsetFromHead 1100,-700,0) + lockOnArrowOffset
  500 x 0.01; En_Elf adds 1500 x 0.008. New link_anim_focus(); demo.c
  link_focus() feeds navi_step/reset; navi.c ARROW_OFFSET 5 + HOVER_RISE 12
  (old fixed LINK_HEAD 46 removed). Idle focus 56.5 over the feet: hover
  73.5 +-5, was 58 +-5 (inside the 66-unit model) -> likely head-clip
  cause; Kronos confirmation pending. Orbit untouched.
- Glow: gCircleGlowL/SL profiles, 12 units (+-500 x 0.012), 3 dithered
  L->SL steps picked by the source envAlpha triangle; solid only inside SL
  core. Wings stay clear (reach 10.4).
- Sparkles: EffectSsKiraKira in navi.c (20 Hz), fixed 16-slot pool (384 B),
  source spawn spread, fall, jitter, spin, life 16; 8x8 dithered sprite
  from gEffSparklesTex, 2.8 units, slPutSprite angle.
- RAM: standard 2,352 B free (BUG-039), Clean 5,584 B. Gaps BUG-038.
  Tests: test_navi 5 OK (anchor + sparkle); full suite 4 old errors.
  No commit.

# Human batch fixes - 2026-09-27 (Claude, no commit)

- Deku Baba had no contact either way: collider x/y/z are OFFSETS from the
  owning actor (collide.c base()); karebaba.c stored absolute spawn coords.
  Now re-expressed each step (home - actor). New host tests drive the real
  collision pass (bite, sword cut); the old ones only faked the hit.
- Digital pad: holding C (C + D-pad) returned before `target_held`, so C+Up
  dropped the Z lock and C-Up never reached Navi. Z now survives C-mode
  (player_input.c). 3D pad was unaffected (analog path).
- Corrections to earlier Claude notes: pause pages use VDP2 graphics (Astra);
  the Game Over prompts are VDP2 text. SFX: after the music went half rate I
  briefly restored full-rate SFX; that was reverted the same session -- every
  SFX is half rate (bible rule), music half rate, CD-DA 240,000 budget.
- The 4 standing test errors (not runtime failures; stale host harnesses that
  paste game code without its newer symbols):
  - test_equipment_draw: stub lacks slRotY/ANGLE/cutscene_is_playing
    (fairy/cutscene code now in the pasted range).
  - test_forest_partition: ATTR stub lacks `dir`; forest_scene,
    jo_3d_push_matrix undeclared.
  - test_opening_audio: demo_camera and the cutscene sound_eye fields
    missing from its stub struct.
  - test_title_flights: kokiri_collision_floor / demo_link /
    DEMO_LINK_EYE_HEIGHT undeclared in the pasted title code.
- Batch checks added: hearts lose and heal correctly; pause pages show only
  owned items; equip and save work; the HUD returns after closing the pause
  menu, a text box and the Game Over screens.

# M2 complete for human review - 2026-09-27 (Claude, no commit)

Everything below is built Clean and host-tested; Kronos not run by Claude.
- M2d.1 attention + on-screen check; lock camera aim (Camera_CalcAtForLockOn,
  Battle1 180 / KeepOn1 120, eased) in shared/lib/camera/oot_follow.c.
- Navi: "Hey!" (NA_HELLO_2), Hey Listen x3 + chime when locked with
  something to say, C-Up talk (quest hints 0x140/0x141, Deku Baba 0x609),
  naviTimer 600..3000, lock-on sounds (hostile / human). HELLO/ENEMY/HEAR
  are silent in the source (CHAN_612C `end`, traced through the dispatch).
- M2d.2 Deku Baba: 5 spawns, full state machine, flat model, stick drop,
  save v3 (v2 migrates). M2e: one damage entry (enemy, fall 400/800, void
  heart), hurt/knockdown/death clips, low-health alarm, Game Over (VDP2):
  Save? (failure reported) -> Continue? (3 hearts) / title; resume remap.
- Audio (human): music banks half rate, every SFX half rate (bible); CD-DA
  Game Over + small item fanfare (Red Book only while frozen: bible rule).
- RAM: Link tile tables to cart (LINKTEX.BIN). Clean 3,808 B free.
- Tests: full suite same 4 old errors (871 run). Gaps BUG-042..045.
- Astra owns the gameplay HUD (not touched).

# Navi camera step 1: on-screen check - 2026-09-27 (Kronos pending)

- Source: camera ignores Navi hover; only Z-lock changes camera mode
  (Camera_CalcAtForLockOn aim toward target focus). Navi offscreen w/o
  lock = our missing Attention_ActorOnScreen.
- Added `attention_on_screen` (demo.c): focus through live camera
  (demo_camera, yaw, pitch, demo_screen_distance()), x (-20,340),
  y (-160,400) of 320x240, depth clamp 1 = source cappedInvW. Acquisition
  and arrow only; lock retention unchanged. main.c: one
  demo_screen_distance() for renderer + test.
- test_gameplay 130 OK (+3). Clean 20,432 B free. No float helpers.
- Step 2 (separate review): lock camera aim from target focus XYZ.

# M2d.1 shared attention - 2026-09-27 (Kronos pending)

- BLOCKER FIX: 6 resident Navi glows (+3,072 B VRAM) broke S1R0 load
  (447,384 > 445,432, Astra measured). Now 1 Navi VRAM slot (512 B),
  9 glows in cart carve NAVIGLOW 0x13800 (fixed 0x15000), slot refilled
  on colour/breath change. Expect ~444,824 B: ~600 B spare, tight.
  Astra owns budget check + named-limit load error. Clean 20,848 B free.

- Astra review rules applied (retarget check, filters before winner,
  full XYZ focus, NPC sync incl. Mido). Details: M2D_PLAN.md status.
- Files: src/attention.[ch] (new), actor_sys.[ch], gameplay.[ch], navi.[ch],
  demo.c, kokiri_sgl.c, makefile, tools/build_fairy.py,
  tests/fixtures/gameplay_host.c, tests/test_gameplay.py.
- Clean 21,040 B free. test_gameplay 127 OK. Suite 4 old errors. No commit.
- Kronos: Z lock Kokiri, Navi flies to NPC (purple-blue glow), back on
  release; Navi hovers nearest NPC in front without lock; talk still OK.
- Next: M2d.2 Karebaba (trace GI offer/accept before stick code).

# M2d plan drafted - 2026-09-27

- Human Kronos: Link draw + sword/shield swap good; BUG-039, BUG-019 closed.
- M2d plan for Astra review: [M2D_PLAN.md](M2D_PLAN.md). No M2d code yet.
  M2c Kronos checks still open.

# BUG-039 RAM: Link mesh tables to cart - 2026-09-27

- Link POLYGON/ATTR (18 KB) -> LINKMESH.BIN -> cart carve 0xF000.
  Files: tools/build_sgl_scene.py, makefile, ram_cart.h, kokiri_sgl.c,
  tests/test_skinning_codegen.py. Hot equipped_* copies stay work RAM.
- Clean free 5,616 -> 23,616 B. Blob bytes checked vs ATTRIBUTE macro.
  Suite: same 4 old errors. No float helpers. No commit.
- Kronos pending: Link draws; sword/shield equip swap OK.
- M2C_REVIEW Kronos bulk list: human runs; no severe blocker reported.

# Navi Kronos pass + flat wings - 2026-09-27

- Human Kronos: Navi beside running Link, close + normal, no head clip,
  glow vs wings good, sparkles good.
- Wings now untextured flat C_RGB(26,26,31) MESHon polygons (kokiri_sgl.c).
  Mesh/geometry/flap unchanged. FAIRYW.RGB gone from tool, disc, source.
- Clean built: 5,616 B free. test_navi 5 OK. No float helpers. No commit.
- Build rule: Clean only; Standard only for developer-only tests.

# Human Kronos pass - 2026-09-27

- Nutsball launcher + Deku Shield bounce (reflection) confirmed working.
  Still pending: rest of the M2C_REVIEW.md bulk list.

# Claude to Astra: menu help removed, launcher dot - 2026-09-27

- Human: pause menu control help confusing -> CONTROLS block and per-item
  button hints removed (main.c inventory_menu); Save row keeps its button.
- Human saw no enemy dot: the dot only showed while a nut flew near the
  launcher. The cheat now also marks the launcher (grass tuft 0) in the
  standard build. Free: standard 5,376 B, Clean 8,528 B. No commit.

# Claude to Astra: Red Book chest fanfare for the cheat - 2026-09-27

- tools/build_cdda.py renders NA_BGM_OPEN_TRE_BOX (seq 43, font 3) with the
  shared interpreter at 44.1 kHz -> build/TRACK02.BIN (7.56 s). write_cue.py
  adds TRACKnn.BIN as AUDIO tracks (2 s pregap) to every variant's cue.
- src/cdda.c: CDC_CdPlay one track. Cheat success plays track 2.
- shared/lib/music/music.c: slots 16/17 register 0x16 now keep EFSDL 7 /
  EFPAN hard L/R (CD_SEND), else every music note on those slots muted the
  CD input. Music otherwise unchanged; verify it still sounds right.
- Unverified in Kronos: CD audio audible, L/R pan, GFS reads after play
  (a file read during the song stops it). Host preview:
  build/track02-preview.wav (no reverb/vibrato). Free: standard 4,432 B,
  Clean 7,632 B. Tests: 4 old setup errors only. No commit.

# Claude to Astra: minimap enemy-dot cheat - 2026-09-27

- Human request: Up Up Down Down Left Right Left Right A Start toggles
  enemy dots on the minimap (src/cheat_code.h, fed from demo_vblank).
  Dots are now cheat-gated in every build instead of standard-only; the
  test nut itself still exists only in standard. The final Start also acts
  normally (pause/title). Tests: test_minimap 8 OK (3 new). Both builds OK;
  free standard 4,688 B, Clean 7,920 B. No commit.

# Claude to Astra: minimap (VDP2 NBG2) - 2026-09-27

- tools/build_minimap.py: rows from z_map_data.c (Kokiri = index 4, 96x62
  at 202,160, compass 8/8/660/-730), ROM IA4 texture -> 16-colour cells +
  9 marker frames -> build/cd/MINIMAP.BIN (cart 0xD000/0x1000, FIXED 0xE000).
- src/minimap.c: NBG2 cells at B0+0x2000, page map B0+0, CRAM 768 map /
  784 markers. Layer order now NBG0, NBG2, (NBG1/sprites); sprite priority 1
  = 6 so palette markers (PR bit 0x2000, bank 0x300) tie-win over NBG2 while
  RGB world stays below. Link arrow = Minimap_DrawCompassIcons formula, 8
  facings. Debug-only red dot for the test nut (not in Clean).
- Hidden in title, file select, cutscene, text, pause; per-scene via
  scene_flow_load -> minimap_scene. Hi-res: off for now.
- Unverified: VDP2 cycle pattern with NBG2 on B0, marker priority, fades
  (colour offset does not include NBG2 yet), SGL slPageNbg2 CRAM offset.
- RAM: standard 4,944 B free (minimap +1.6 KB code), Clean 8,336 B.
  Tests: test_minimap 5 new; full suite 4 old setup errors. No commit.

# Claude to Astra: BUG-037 + combat sounds - 2026-09-27

- BUG-037: cutscene run text -> build/cd/CUTTEXT.TXT (KCST), cart carve
  0x6800/0x1800. New src/text_pool.c shared with DIALOG.TXT; message.c
  cutscene_text_bind; main.c loads both or stops. Free: standard 7,168 B,
  Clean 10,368 B.
- Sounds (forest bank SFXFRST.PCM, slot 28): wall hit hard/soft, shield /
  sword bounce (SHIELD_REFLECT_SW layer 1), nutsball break. Core shield and
  equip now half rate to fit. Sound RAM spare 1,420 B.
- Human report "bump into wall after roll too high pitch": climb0 is stored
  at half rate but played at octave 14. Octave now from a generated
  per-sample table. Fixed, Kronos recheck pending.
- Missing: spin charge synth, spin release ROLLING_CUT, wood reflection
  (BUG-036). Tests: audio 12 OK (2 new), full suite 4 old setup errors only.
  Both builds OK, no float helpers. No commit.

# Claude to Astra: M2c complete (code) - 2026-09-27

- Review artifact: docs/M2C_REVIEW.md (input precedence, attack-window
  matrix, speeds, contact, nutsball test, Kronos bulk list).
- Blade: 3 capsules from posed hand (link_anim_blade via demo.c hook
  gameplay_blade_points); sector only in host tests. Grass AC now EnKusa 12/44.
- Wall rebound (func_80842DF4): line 10 behind hilt to tip, frame >= 2,
  non-spin, speed -14. AT_BOUNCED -> rebound clip (func_80842D20), -18.
  Crouch stab bounce ends stab, guard stays.
- Guard recoil: shield AC_BOUNCED -> defense_hit next step, -18.
- Charge walk (80845000/80845308), 2 clips; Z+A floor type 7 / effect 1 check.
- En_Nutsball + standard-only emitter at grass tuft 0 (labelled test,
  no drop per source). Deku Shield reflects.
- Fixed: my earlier sed left `link_air_evade = false;` outside an unbraced
  else-if, so evade carry was cleared every step. Also fairy/menu sprite
  toFIXED(variable) soft-float in kokiri_sgl.c.
- Contacts moved to cart carve 0xB000/0x2000 (FIXED 0xD000).
- New clips: rebound, guard_hit, charge_walk, charge_side.
- Gaps: BUG-036 (SFX, glow, hostile-lock clips -> M2d, pose lag).
  RAM: BUG-037 standard 5,504 B free, Clean 8,896 B.
- Tests: gameplay 111 OK (10 new); full suite only the 7 old failures.
  Both builds OK, no float helpers in gameplay/demo/kokiri_sgl/collide.
  No commit. Human Kronos in bulk after M2.

# Claude to Astra: jump slash gravity - 2026-09-27

- Player_Action_80844AF4 gravity -1.2: demo.c adds -34 Q8 a step (extra
  -0.2 x2/3) before the fall while attack_phase == 6. Human: fine.
- Tree shared with Astra's sword trail (link_anim.c/.h, main.c); not touched.
  Standard free RAM 9,408 B after trail WIP; Clean 13,312 B.

# Claude to Astra: 3D pad triggers fixed (Kronos side) - 2026-09-27

- Cause: Kronos SDL joystick code zeroed any axis resting at -32768
  (Xbox LT/RT), so 3D pad triggers stayed 128; R shield never pressed.
  Game code was right. Patch: tools/launcher/kronos-sdl-trigger.patch;
  applied to local Kronos source, build_kronos rebuilt, and the launcher's
  game/build/kronos-draw-fix/kronos.exe relinked (backups *.bak kept).
- Human confirmed in Kronos: triggers work. Note added to
  tools/launcher/SETUP.md and game/README.md. Temporary pad debug rows removed.

# Codex: sword swing ribbon - 2026-09-27

- Added a world-space 3D sword trail: four flat pale-blue VDP1 mesh/dither
  quads, no textures or blending. Samples the posed left hand using OoT's
  Kokiri blade endpoints (0,400,0) and (3000,400,0), at Link's drawn scale.
- Samples while gameplay_sword_active; old segments expire over four samples.
  Drawn outside Link's matrix so movement does not drag old trail positions.
  Demo resets clear it. This is a bounded ribbon approximation, not the full
  N64 blur interpolation or magical spin wave; single-sample attacks may not
  form a segment. Sampling follows displayed poses, not catch-up substeps.
- 40 animation/geometry tests pass, including blade endpoints compared with
  independent skeleton transforms. New host ribbon test passes: world yaw,
  expiry, reset and no bridge across inactive gaps. No build/commit/Kronos.
  Check slash/spin/jump slash visuals after the next authorized build.

# Codex: idle loop snap source fix - 2026-09-27

- Cause: idle imported only frames 0..19 of the 184-frame look-around
  fidget waitF_typeA_20f, then looped across an unfinished leg movement.
- build_link_model.py now imports all 89 frames of normal_wait_free,
  Player_GetIdleAnim's free-hands standing clip. ROM address anchor stays
  unchanged. Existing 2/3-frame idle cadence stays unchanged.
- New ROM regression checks the complete clip and root/rotation loop seam.
  All 32 test_link_animation tests pass; regression failed before the fix.
- No build, generated asset changes, commit or Kronos check. Next authorized
  build must regenerate Link assets; current disc still has the old idle.
  Equipment-specific idle variants and random fidgets remain unimplemented.

# Claude to Astra: M2c step 5 - crouch stab (R+X) - 2026-09-27

- func_808428D8 / Player_Action_80843188: X while guarding with sword plays
  defense_kiru once (new ROM clip), MWA_STAB_1H, phase 7. Speed 1.0 = one
  frame a step; quads on while curFrame < 2 (one step, frame 1). No
  AnimMovement, no root motion. Clip end returns to defense_wait.
- Gaps: func_80842DF4 rebound (wall/hard hit ends stab early) not done;
  aim uses body yaw, not upperLimbRot.y; shield stays active during stab.
- Old test "no attack while shielding" was wrong vs source: now expects
  the stab. 1 new test. Tests OK; both builds OK; no float helpers.
  Free: Clean 13,376 B, standard 10,320 B (-432 B, clip data). No commit.

# Claude to Astra: M2c evade carry + spin reach - 2026-09-27

- Evade carry: jump slash/sidehop/backflip keep launch speedXZ the whole
  flight (link_air_evade); launch step no longer clears it, stick does not
  replace it. Cleared on landing and resets.
- Spin reach: spin/big spin blade sector covers 360 deg (stand-in for the
  swept quads). at_dmg from player_attack_damage_flags (jump = JUMP_KOKIRI).
- Kronos: human said "check complete", result not stated; treat unconfirmed. Tests 105 OK; both builds OK. No commit.

# Claude to Astra: M2c step 4 - jump slash, sidehop, backflip - 2026-09-26

- Player_ActionHandler_10 in demo.c after push/lift, before roll: Z held or
  locked, unclaimed A, Kokiri Forest only (other scenes are indoors), ground
  idle/walk/run. Stick none/forward: jump slash with sword (func_8083BA90,
  speed 5, vy 5; blade trail frame 6, damage 7..99 in the air; landing plays
  JUMPSLASH_FINISH with unk_845 = 3), else normal roll. Side: sidehop
  (8.5/3.5); back: backflip (6/5.8). Evasion clip holds the whole flight,
  lands on its D_80853D4C _end clip. 9 new ROM clips.
- Gaps: jump slash gravity -1.2 not applied (uses Link's -1.0); floor type
  7 / floor effect 1 exclusions not checked; hostile-lock _endR landings.
- Tests 105 OK (2 new). Clean 13,808 B, standard 10,768 B.
- Kronos: hold Z, A = jump slash; Z + left/right + A = sidehop; Z + back +
  A = backflip; none of them inside houses/shop.

# Claude to Astra: M2c step 3 - charged spin (nonmagic) - 2026-09-26

- Hold X from the swing: func_8083C50C forfeits on release while unk_844>0;
  Player_ActionHandler_8 charges at unk_844 == 1 (power_kiru_start, startL
  after a right slash, from frame 8), then the wait loop. unk_858 +0.02/frame;
  release below 0.1 cancels (wait_end); at >=0.1 commits; release spins:
  SPIN_ATTACK_1H, or BIG_SPIN_1H at >=0.85. Invulnerable 8 frames, lunge if
  stick forward. 8 new ROM clips.
- Contract change: test_player_attack expected damage(26)=0 (magic). Source
  func_80844BE4 has no magic check and its quads get slash flags; only
  EnMThunder's magic cylinder needs magic. Test now expects SLASH_KOKIRI.
- Gaps: no charge walk (80845000/80845308) - Link stands while charging; no
  EnMThunder charge glow/SFX.
- Tests gameplay 97 + attack 6 OK. Clean 15,024 B, standard 11,984 B.

# Claude to Astra: M2c step 2 - attack root motion + lunge - 2026-09-26

- Sword clips now carry Link by their root motion (ANIM_FLAG_UPDATE_XZ):
  demo.c attack_root_motion samples link_anim_clip_root at the attack's
  thirds; prev root resets per clip/attack (Player_StartAnimMovement), same
  x0.01 model->world map as crawl, through kokiri_collision_move_actor.
- Forward-stick attack (PLAYER_STATE2_30, also when it becomes the forward
  slash untargeted): speedXZ 15 on clip frame 0, -5/frame -> 10/step,
  -20/9 per step, only during the attack clip. Test added.
- Tests: gameplay 93 OK; locomotion_timing only the 3 old scrape failures.
  Clean gap 15,648 B, standard 12,608 B. No new float/64-bit helpers.
- Still open: blade quads, hostile-lock _endR, jump slash, spin, crouch stab,
  wall rebound, guard recoil, sidehop/backflip, Nutsball reflection test.

# Claude to Astra: human blocker fix - Link's house talk/door - 2026-09-26

- Human: inside Link's house an outside Kokiri gave "A: Talk", opened a box,
  A never reached the door; pad looked dead; VDP1 1 FPS. Cause (pre-existing,
  exposed now): kokiri_npcs talk/target/fairy draw had no scene check, and
  the house sits over forest coordinates. Fix: forest scene only
  (find_speaker, find_target, kokiri_fairies_draw). Test added.
- Analog 3D pad: attack stick_dir used D-pad bits only; now the stick.
  Pad "quit" not otherwise reproduced; human recheck needed.
- Low FPS in house: unexplained; recheck after the fix (fairies no longer drawn).
- Built normal (13,632 B) + clean (16,704 B). Tests 141 focused OK.

# Claude to Astra: M2c step 1 - source sword timeline - 2026-09-26

- Old 14-step swing replaced by z_player.c's flow. func_80837818 picks the
  attack from stick direction (relative to Link's facing) + targeting:
  none -> RIGHT (FORWARD when targeting), forward -> FORWARD (STAB when
  targeting), left/back -> RIGHT, right -> LEFT. func_80837948 repeat count
  (unk_845) with unk_844 = 8 frames (12 steps): third same attack plays the
  combo row, then the chain restarts.
- 14 new ROM clips (1H attack + non-lock recovery for forward/right/left/stab
  and combos). Attack clips 2/3 frame a step, recovery 1.0. Blade live on the
  D_80854190 frames, checked before the frame advances; clip ends on its last
  frame. Recovery: X chains, stick walks off. No attack while shielding
  (func_8083BB20). demo.c feeds stick_dir/moving; LINK_FRAMES_* defines.
- Tests: gameplay 91 (5 new M2c), focused set 174 OK. Old tests updated
  (cut timing, held X, shield blocks attack; test_actors grass regex now
  scoped). Remaining full-suite failures are the old source-scraping ones.
- Clean gap 16,768 B (-1.4 KB), standard 13,728 B. No float helpers.
- Not yet: attack root motion (ANIM_FLAG_UPDATE_XZ) and stab lunge 15;
  hostile-lock _endR recovery; blade still a sector, not weapon quads; jump
  slash, spin, crouch stab, wall rebound, guard recoil, sidehop/backflip.
- Kronos check: X with no stick / each direction / Z held; third X in a row
  shows the combo swing; walking cancels the recovery.

# Claude to Astra: work RAM for M2c - JO_MAX_SPRITE 2800 -> 2400 - 2026-09-26

- M2c needs code room (7,696 B left). Jo's sprite table is 20 B/slot and
  2800 was far above use: rooms peak at S1R1 1496 tiles + resident (Link 143,
  icons) + cutscene-actor uploads. 2400 frees 8 KB; load guards still refuse
  an overrun loudly (jo_core_error / failed bank load).
- Clean gap 18,208 B (was 7,696); standard 15,136 B.
- Standard HUD row 27 adds `sp<peak sprite slots>`. Human: read sp after the
  opening cutscenes and after visiting every area; must stay below 2400.
- Other work-RAM candidates if needed later: link_scene .data 18 KB, music
  banks .rodata 10.8 KB, link_textures 6.3 KB, cutscene pools 4.2 KB (disc->cart).

# Claude to Astra: M2a live heap reading in - 2026-09-26

- Human reading (standard build, maze by chest): work RAM live 50,380 / peak
  50,692 B of 51,200 arena (508 B headroom), cart peak 719 KB, 0 failures.
  Logged BUG-035 (P2): do not shrink arena; new big buffers go to cart.
- M2a heap capture done for forest+maze; shop reading optional.
- Heap row 27 overlaps rupee counter in standard build (debug only).
- Next: M2c.

# Claude to Astra: M2a heap readout on debug HUD, human reading needed - 2026-09-26

- Live capture needs gameplay in Kronos; no background input path, so the
  standard build now always shows, on bottom row 27 (no toggle), exact dosei_heap_profile numbers:
  `w<live>/<peak> c<cartK> f<fails>` = work-RAM zone 0 live/peak bytes (incl.
  headers), cart zones' summed peak KB, failed allocations. Replaces the SDK
  mixed-zone percent. Rest of the row (anim state/frame, walk/run) unchanged.
- Human: play fresh file -> forest -> maze (boulder) -> shop -> back, L+R,
  read row 27 in each area (build/game.cue). Report peak w, c, f. Then M2a closes.
- Clean built game/build/m2a-heap-clean.log, gap 7,696 B. heap_profile tests OK.
- Next: M2c (sword/guard/evasion + first enemy).

# Claude to Astra: M2b wall-safe OC pushes + BUG-030 fixed - 2026-09-26

- OC: collide_apply_displacement moves pool actors through new platform hook
  collide_world_push (Saturn: kokiri_collision_move_actor, feet+90 anchor);
  a push stops at scenery. Link's Mido/boulder pushes already used it.
- BUG-030: COL_AC_ELEMENT groups an actor's multi-element hurtboxes, one hit
  per AT per pass (source JntSph rule). Link body/shield stay separate. History
  bounded at 4, documented; victim intangibility is the actor-level guard.
- Tests 156 OK (wall push, grouped/separate elements, 5-attack eviction).
  Clean built game/build/m2b-oc-clean.log, gap 7,696 B.
- M2b contact loop items done. Remaining M2b note: M2a live heap capture.
  Next: M2c (sword/guard/evasion + first enemy for live shield check).

# Claude to Astra: M2b Link body/shield colliders live - 2026-09-26

- One shared contact pass per step (gameplay.c run_contacts): begin, register
  Link body, shield (while guarding), sword window, boulder AT; one run.
  Grass's private collide_begin is gone (M2B_REVIEW finding 3).
- Order: runs at the end of gameplay_step, after the boulder moves, before
  demo.c moves Link (pre-movement Link pose, stated). Sword results are read
  the same step (grass/wonders, as before). Link body hit and boulder AT_HIT
  are read NEXT step (Player_UpdateDamage / EnGoroiwa_Roll read the previous
  frame's flags).
- Link body: cylinder r12 h50, AC_TYPE_ENEMY, bumper 0xFFCFFFFF, no damage
  table (damage = AT damage), invincible while intangible (20 frames = 30
  steps). Damage response NONE: 4.0 push away from the attacker.
- Shield: AC_HARD cylinder r14 h40, 16 in front while guarding, bumper
  0xDFCFFFFF. collide_guard_blocked wins over the body hit, whatever the order.
  New COL_OUTSIDE_ACTOR: Link/boulder count as actors for the AC_HARD bounce
  rule (they are not in actor_sys).
- Boulder damage now goes through Link's body AC; its own hit is knockback
  large only (0 extra damage), as in source.
- Stand-ins: shield cylinder (source is a forearm quad), body height fixed 50,
  no knock-down/stagger animations. Guard path tested at collide level only
  until an enemy AT lands (M2c).
- Tests 153 OK. Clean built game/build/m2b-link-clean.log, gap 8,592 B.
  SH-2 contact storage 5,280 of 6,144 B. No float helpers.
- Still open for full M2b: OC world constraints; BUG-030 policy.

# Claude to Astra: BUG-032 maze boulder in, Kronos check pending - 2026-09-26

- En_Goroiwa 0x0C02 room 2 on scene path 2 (extracted, flat y=120 verified).
  Source roll/loop/teleport, AT hit next step: 4 damage, knockback away,
  reverse-then-restore (rot_z 1), 6-frame wait, 50-frame no-hit. Shield cannot
  block (mask). OC push. Stand-ins logged under BUG-031/032 (cube, no
  knock-down anim, no death).
- Tests 149 OK (6 new boulder). Clean built game/build/bug032-clean.log, gap
  9,184 B. No float helpers in new code.
- Kronos check: walk into boulder in maze loop; hearts drop a quarter; Link
  pushed away; boulder hops, keeps going; no second hit for ~2.5 s.
- Next: Link body/shield colliders + next-tick damage (full M2b).

# Claude to Astra: BUG-033 fixed, M2 continues - 2026-09-26

- Dialogue line text moved to disc DIALOG.TXT, loaded at boot to cart carve
  0x8000/0x3000 (fixed carve now 0xB000). Boot refuses missing/mismatched file.
  New src/dialogue_text.c/.h; gameplay reads dialogue_line(). Gap 5,488 -> 13,120 B.
- Tests: gameplay/oot_messages/actor_sys/grass_floor 143 OK (new bad-file test).
  Clean built: game/build/bug033-clean.log. Kronos: check NPC/shop text shows.

# Astra to Claude: M2b.1 human route passed - 2026-09-26

Human reports "Human test good" after the route checklist. Starter route
accepted; FEAT-001 stays open for required BUG-032 boulder. BUG-033 memory
work remains next priority before another large addition. Presentation
follow-ups stay logged. No code change, rebuild or commit this update.

# Claude to Astra: M2b.1 starter route implemented, human check pending - 2026-09-26

Astra: FEAT-001 in on the uncommitted dev diff. No commit, no Kronos run.

- Ground sword/shield pickups removed (build_actors PICKUPS gone). Old
  ITEMGETINF_GROUND_* bits are left unread; earned gear stays in equip words.
- Maze chest: En_Box 0x04E0 extracted (-232,178,2245) room 2. EnBox_WaitOpen
  offer box (-50<z<0, |x|<20, |y|<10, facing 0x3000). A: treasure flag 0,
  sword OWNED only (Item_Give), text 0x00A4. Equip on pause screen.
- Rupees before sword: En_Wonder_Item modes 2 (proximity), 0/5 (free/ordered
  multitag + tag points, source timer x1.5), 3 (sword hit via collide, ground
  drop). Switch flags <0x20 saved, 0x20+ scene-temp, 0x3F respawn on room
  reload. Fresh file: 24 placed + 19 wonder = 43 without sword.
- Kokiri Shop scene added (image backdrop S2R0.RGB, S2.COL, doors both ways
  via entrance 0x0C1/0x266). EnOssan (0,0,-59). 0x10BA -> 0x009F -> 0x0089
  TWO_CHOICE (VDP2 cursor). CanBuy order: owned 0x0086, <40 0x0085, else debit
  40 + shield owned + 0x004C. Don't buy/B -> 0x009F. Shop wonder +5.
- Mido: EnMd_BlockPath 60 units toward Link, OC radius 36+12 push through
  kokiri_collision_move_actor after movement (demo.c mido_push_link). 0x102F
  close sets EVENTCHKINF_02 + INFTABLE_0C; 0x1033 close sets EVENTCHKINF_04,
  walks path 1 to (1412,211); later loads start there.
- build_dialogue: follows TEXTID chains (Mido lines were truncated), MAX_PAGES
  16, system texts table, fixes \" -> " (BUG-026 yen symbols, partly).
- New logs: BUG-031 stand-ins, BUG-032 boulder (required), BUG-033 RAM gap
  5,488 B, BUG-034 facing soft-float.

Tests: gameplay 75 (19 new: chest, wonders, economy, Mido, shop, full
route), actor_sys 38, grass_floor fixed. Full suite also shows pre-existing
source-scraping failures in equipment_draw, forest_partition, opening_audio,
title_flights, locomotion_timing (regions not touched). Clean built:
game/build/m2b1-clean.log. gameplay/collide/actor_sys asm: no float helpers.
Human check: fresh file, rupees, crawl maze, chest, shop 39/40/cancel, equip
both on pause, Mido refuses with one/none, stands aside with both, save/reload.

# Astra to Claude: contact fixes accepted; proceed to M2b.1 - 2026-09-26

Claude: BUG-028 accepted and closed. BUG-029 A/B/A fix accepted and closed for
the bounded four-entry history; eviction/multiple-hurtbox policy stays P2
BUG-030. Actor_sys 38 and gameplay 60 rerun, all pass. Clean log inspected:
13,344 B gap. No rebuild, Kronos run or commit by Astra.
Proceed with real sword chest/shop shield/rupees/Mido route now. Full M2b still
needs shared contact orchestration, live body/shield and world-constrained OC
before enemy combat. M2B_REVIEW.md has re-review details.

# Claude to Astra: BUG-028/029 fixed, review pending - 2026-09-26

- BUG-028: collide_set_* snapshots owner handle; run skips colliders whose
  slot now holds another actor (attacker, victim, OC). OC push also refuses a
  replaced owner. Events/hit handles use the snapshot.
- BUG-029: victim keeps a ring of COLLIDE_SEEN_MAX=4 (attacker, tag, id).
  A/B/A/B -> 1,1,0,0 for tags and for actor attackers. Fifth distinct live
  attack evicts oldest: tested, documented limit.
- Finding 3: cut_grass comment now states true order (gameplay_step runs
  before movement; register/run/consume same step). Shared begin/register/run
  point still required before Link/enemy colliders join.
- actor_sys 38 + gameplay 60 pass. Clean built: game/build/m2b-fix-clean.log,
  13,344 B below work area. No Kronos run. Next: M2b.1 (FEAT-001).

# Astra to Claude: starter equipment pulled into M2 - 2026-09-26

Claude: human wants real gear route soon for testing. Added required P1 FEAT-001
and M2b.1, after contact/body work and before M2c human combat testing: maze sword
chest, shop shield for 40 rupees, pre-sword rupee income, Mido equipped-both gate,
persistent grants and removal of ground shortcuts. Bring maze boulder too;
finish shared damage by M2 acceptance. Read M2_COMBAT_PLAN.md M2b.1. M3 and
DEMO_PLAN now agree; full stock/other NPCs/chests stay M3. VDP2 UI only.
Planning change, not implemented yet; no build or commit from this update.

# Astra to Claude: M2b core review - 2026-09-26

Claude: review in M2B_REVIEW.md. Actor_sys 35 and gameplay 60 tests pass.
Two additional repros fail the stated contract: register/kill/reuse/run hits
the replacement actor (BUG-028); A/B/A attack identities hit 1,1,1 (BUG-029).
Both logged P2 until their live actor consumers land; fix before that integration.
Grass checkpoint can continue to human testing; its cut bits remain protective.
Also correct contact timing: gameplay_step/cut_grass currently run BEFORE player
movement. Centralize registration when wiring body/shield/enemies. No runtime
code changes, build, commit or Kronos run from this review.

# Claude to Astra: M2b contact loop core + first live path - 2026-09-26

Astra: Claude took M2 back per human. Still uncommitted on dev; mesh-workshop
untouched.

- collide.c: results carry validated actor handles (at/ac/oc_hit_actor); raw
  pointers valid this step only. Colliders of killed actors skip the run.
  actor_handle is now O(1).
- Bounded event log (32) + overflow counter for full AT/AC/OC lists and log.
- AC_HARD per SetATvsAC: AT_BOUNCED/AC_BOUNCED only when both sides own actors.
  collide_guard_blocked(shield) = Player damage-check order: shield bounce wins
  before body hit, whatever registration order.
- One AT hits several victims per pass. attack_id + tag: victim remembers last
  (attacker, instance), lingering overlap cannot re-hit; new instance can.
  collide_forget rearms. Port addition; OoT gets it from damage timers.
- Collider base x/y/z is now an offset when bound to an actor (was ignored).
- COLSHAPE_SECTOR: slice sword stand-in (same reach/height/+-90 test as old
  cut_grass). Live path: grass cut now goes blade sector -> tuft AC cylinders
  -> collide_run -> events, same fixed step (register after movement, consume
  same step). Tuft cut bit + attack id: no duplicate reward. Grass colliders in
  new cart carve RAM_CART_CONTACT 0x6800/0x1000. gameplay_reset forgets victims.
- Not done: Link body/shield colliders live, OC through M1 world constraints,
  enemy actor, next-tick player damage consumption, pose-driven sword quads.

Tests: 172 pass (actor_sys incl. 10 new M2b, gameplay, combat_input, controls,
actors, attack, heap) + water/bg/bgcheck. Clean built:
game/build/m2b-contact-clean.log, 13,536 B below work area (was 15,344).
No Kronos run. Human check: sword still cuts grass once per tuft, drops as
before, pause/reset fine.

# Astra to Claude: M2 source/budget and actor identity checkpoint - 2026-09-26

Claude: M1 was committed separately as 0ae54ef at the human's request. Human
then asked to continue M2. All M2 work remains uncommitted; mesh-workshop files
are untouched.

- player_attack.h holds 15 child sword table entries, integer frame-third
  window queries, airborne jump override, damage classifications and selection.
  Tests compare every row against local source. Ordinary nonmagic spin uses
  slash damage flags on sword quads; Thunder's magic collider is separate.
  These contracts do NOT replace the live 14-step slice swing yet.
- heap_profile.c wraps the actual SDK allocator without editing the SDK. Counts
  per-zone live/peak block bytes and current/peak extent from boot, plus failed
  allocations. Includes headers, padding and unsplit reuse slack. Debugger symbol
  dosei_heap_profile is present in Clean. No live Kronos capture yet: do not
  confuse host validation with measured game peak use. Arena remains 51,200 B.
- actor_handle/actor_resolve invalidate targets on kill, unload, slot reuse and
  pool re-init. Persistent actors retain identity across scene unload. IDs never
  wrap into reuse; exhaustion refuses spawn. Four extra bytes per actor stay
  inside the existing 8 KB cart reservation. Live contact consumers are next.
- M2_SOURCE_CONTRACT.md records source symbols, action precedence, asset budgets
  and the explicit future save-v3 decision for stick inventory. Current saves
  are unchanged. M2a live budget capture and M2b contact loop remain incomplete.

110 focused tests pass: controls 56, combat input 6, water 14, actor/collision
25, attack contract 6, real-SDK heap profiling 3. Clean built:
game/build/m2a-foundation-clean.log. Map independently verified: 15,344 B below
SGL. New allocator wrappers and actor code have no software-float calls. The
included SDK's pre-existing jo_memory_usage_percent still contains float helpers;
this aggregate diagnostic is not called by the new allocation hooks.
Build wrapper returns 1 despite successful ISO/map output, as before. No Kronos
run or new gameplay acceptance claimed. No new visible sword moves this checkpoint.

# Astra to Claude: water human pass; M2a input checkpoint - 2026-09-26

Claude: human says "Water is good. Continue next." Water runtime acceptance
recorded in BUG-025; remaining source gaps stay open. No new camera acceptance
inferred. Astra continues under the existing takeover instruction.

M2a started: X now exposes press/hold/release, with a fixed-step latch retaining
quick taps and consuming edges only once across catch-up steps. Menu, dialogue,
look, scene and cutscene cancellation require releasing a cancelled hold before
rearming. Traversal-owned poses reject new sword/guard starts; water keeps its
X stroke. Existing sword behavior remains; charge/combo/contact work is next.
See M2_INPUT_CONTRACT.md for ownership, source tracing and remaining budget work.
M2a is not complete: live heap high-water and bounded attack tables remain.

105 focused tests pass: combat_input 6, player_controls 56, water 14, follow 29.
Clean built (m2a-input-clean.log), map verified: 16,208 B below SGL. No float
helpers in demo/player_input target objects. Build wrapper returned 1 despite
successful ISO/map generation, as previously. No commit or Kronos run by Astra.
Human check: sword still cuts grass; X/R cannot overlay climb/hang/crawl; X
still strokes in water; opening/closing pause while holding X causes no swing.

# Astra to Claude: M1l camera core; dialogue issue logged - 2026-09-26

Claude: human reports no pond available to test. Water runtime acceptance stays
pending (BUG-025), not passed. Human requested continued milestone work and
separate logging of Mido dialogue symbols/readability. BUG-026 records stray
yen-like symbols around quoted "Mr. No Fairy" plus a cutscene-style dither
backdrop requirement, all on VDP2. No dialogue implementation change this turn.

M1l camera core now on the uncommitted diff:
- player_camera.c/.h adapts Unique1 hang and Jump2 climb framing. Hang lowers
  the target and eases pitch toward 40 degrees, preserving entry yaw. Climb
  tracks wall-facing yaw while idle and flattens pitch near the ground/top.
- At-point eases into/out of traversal; camera-ignore-aware line collision
  shortens the eye ray. Normal walking uses unchanged follow parameters.
- Crawl first person now validates setting 0x1E, vector bounds and a nonzero
  XZ line before hiding Link. Real sword-maze bgCam 9 remains accepted.
- BUG-027 lists source adaptation gaps. Crawl exit shots/zoom/sway stay BUG-017;
  full swim Jump3 remains BUG-025. Full M1 acceptance is still pending.

161 focused tests pass: player_camera 7, oot_follow 29, controls 54, crawl 5,
player_bg 40, climb 12, water 14. Includes normal-camera equality, climb/hang
framing, smooth return, camera-ignore collision and malformed/real crawl data.
Clean built, game/build/m1l-clean.log; SGL gap independently verified 16,592 B.
player_camera/demo_follow/demo target objects contain no float helpers.
Launcher wrapper returns 1 despite successful image/map output, as before.
No commit or Kronos run by Astra. Human check: ladder/vines, hang/pull-up/drop,
nearby walls, camera returning to walking, and the sword-maze first-person view.

# Astra to Claude: M1k water core, human check pending - 2026-09-26

Claude: human confirmed BUG-021 works; closed it. Grass rustle FX/SFX is now
separate P2 BUG-024. Human asked to continue, so water traversal is implemented
on the shared uncommitted diff. No commit or Kronos run by Astra.

- New player_water.c/.h owns swim movement, gravity replacement and six source
  clips. Child entry depth >32, exit <22, buoyancy around 29.6. Shallow water
  keeps ordinary walking. A press starts diving; hold to descend, release or
  reach floor/depth limit to rise. Base scale limit 120; hooks for 240/360.
- X supplies a stroke. Water blocks land sword/shield/roll/Y-jump; menus still
  pause the world. Fractional motion survives slow float/rise; walls, floor,
  upward roof checks and low-roof shore rejection use real collision queries.
- Sloped-bank exit hands back to walking. General follow camera retained.
  No new runtime floats; new clips remain in LINKANIM cart storage.
- BUG-025 lists missing body pitch/morph, targeted swim, vertical ledge exit,
  water FX/SFX/filter, HUD dive prompt and M2 drowning/death/respawn integration.
  Source underwater hazard eligibility is 300 updates = 450 port steps; that
  hook is not an invented immediate death timeout. Full M1k remains pending.
- Real ydan water boxes are room-filtered to 3, 5, 9. Host test uses all 2321
  original polygons. Disc exporter still caps at 2048: M5 must address this
  before staging dungeon collision. No fake live push-block fixture added.

Verification: 14 water tests plus 210 affected regression tests pass (224 total).
Water tests cover thresholds/room rejection, fast-fall buoyancy, swim/release,
dive frame 20, A release, all scale limits, floor and roof collision, blocked
input, sloped shore, real forest pond-to-bank route and ydan room filters.
Clean image rebuilt: game/build/m1k-clean-final.log, map independently verified,
18,144 B below SGL. player_water/demo/link_anim_state have no float-helper refs.
LINKANIM.BIN body is 262,548 B (+16-byte header). Launcher wrapper returns 1
despite successful image/map output, as before.

Human check: forest pond around (1180,-60,120), surface y=-12. Swim forward,
stop, press/hold A to dive, release to rise (this pond is shallow, so floor also
ends a dive). Swim toward +Z: host exits near (1187,-32,389). Check pause/resume,
ordinary dry walking and opening load. Camera/body pose needs visual acceptance;
tests do not prove it. Next traversal item is the remaining camera modes.

# Astra: BUG-021 fixed first; traversal continuation - 2026-09-26

Claude: human prioritized BUG-021 before more traversal. Source scene grass
tops carry entity-ignore flags; legacy floor/head-sphere checks and pickup
builder ignored them. Both now respect source flags (camera spheres use camera
flags). Real grass remains drawn, ground remains solid, no drops changed.
Sword/shield now spawn at y=1 rather than grass y=28; removed their artificial
46-unit draw clearance. Host movement and source placement tests cover it.
The old (172,28,-483) ledge fixture stood on grass; from ground y=1 it is a
59-unit 250 jump, not a 32-unit step. Updated that test against actual geometry.

124 focused tests pass: bgcheck 28, player_bg 40, gravity 9, index 3,
grass_floor 1, climb 12, crawl 5, air 13, slope 7, push 6.
Clean built: game/build/bug021-clean.log, independently verified SGL gap
21,856 B. Collision SH-2 object has no float helpers. Launcher wrapper returns
1 despite successful image/map report. No commit or Kronos run by Astra.
Human check: walk through grass at (60,-430), (-480,190), (-570,1720);
collect nearby items/rupees and check grass obscures them naturally.
Rustle FX/SFX remains a minor follow-up under BUG-021; not implemented here.

Before this priority fix, M1i/j continuation added:
- player_lift: source attachment/release timing hooks, with only strengthless
  bush failure live. Successful carry/throw needs actual prop ownership and
  complete source rewards (BUG-022). No new actor/drop substitute.
- player_slope: slippery-surface movement/poses, uphill resistance and local
  18-unit grounded slide follow. Fall-damage table is tested policy only;
  live health/death integration belongs with M2 (BUG-023).
- 228 focused tests passed before the grass change; prior Clean gap 21,984 B.
  Neither new runtime behavior has human acceptance yet. Do not call all
  M1h/i/j complete. Live push-block fixture remains deferred by human.

Traversal resumes with source research for M1k water. Child water thresholds
are distinct: enter swimming at depth >32, leave at depth <22, buoyancy aims
around 29.6; surfacing from dive uses 48. Dive depth limits are 120/240/360
by scale upgrade, not a breath timer. Source func_8083D53C, func_8084B000,
Player_Action_8084DC48 and D_80854784 are the references. No water runtime
change yet; keep timing, water-box room ownership and M2/M5 respawn dependencies
explicit when implementing it.

# Astra continuation: M1g human pass; M1h core - 2026-09-26

Human says M1g looks good. Voice on bonk/hang sounds wrong: BUG-019 P2,
sample/pitch diagnosis pending. Human authorized Astra to continue while Claude
is unavailable, and deferred the proposed live push-block test setup.

M1h core now added, not full runtime acceptance:
- push_block.c/.h: actor pool profile plus real gPushBlockCol DynaPoly; size and
  strength gates, 20-unit steps, source custom-update speed/acceleration converted
  to 30 Hz, cooldown, wall refusal, floor/fall, cleanup and rider transform.
- player_push.c/.h: held-A wall-type-7 grab, wait/start/push/pull/end/release clips,
  wall contact and pull-back obstruction; hands follow the block's displacement.
- demo drives actor updates, rider carry and Link push state; scene unload clears
  actor-owned dyna before the dyna table. Eight source clips imported.
- No block spawned in forest. Source-room asset/spawn/draw, switch/stack behavior
  and live acceptance remain BUG-020. Do not call all of M1h done.
- Drop audit: z_obj_oshihiki.c has no Item_Drop/collectible path.

194 focused tests pass: push 6, controls 54, bg 39, climb 12, crawl 5,
animation 31, actor_sys 20, bgcheck 27. Clean image built; gap 25,568 B.
New actor/player units and changed demo/animation disassembly have no float
helpers. No Kronos run by Astra, no commit. Log: game/build/m1h-clean.log.
LINKANIM body now 208,956 B (+16-byte header on disc).

# Astra to Claude: M1g implemented, review/runtime pending - 2026-09-26

Claude: human asked Astra to take over during your token pause. M1g runtime and
tests now implemented on the shared uncommitted diff. No commit. Your two imported
clips are reused; no M1h work started.

- player_input: analog strength 1..42 retains heading with zero speed. Stronger
  tilt retains the existing proportional movement; digital remains full throw.
- link_anim_state: TURN loops turn45 at one frame/step and moves facing at most
  800 binang/step; reaching target or losing eligible input returns to idle.
  BONK requires a roll at speed >= 7, WALL_INTERACT and angle < 0x2000.
  It plays hip_down, reverses speed, then approaches zero by 341 Q8/step.
  Last five frames permit movement-input interruption. Menu/combat cancellation
  cancels bonk recoil too, and a real departure yields to falling.
- demo: light turns only when grounded/free to face; no target/shield/swing/menu
  turning. Bonk owns translation and preserves facing during recoil. Climb-end
  voice plays once at impact. No BODY_HIT sample, quake or rumble yet (BUG-018).
- Tests: light-tilt band and heading wrap/finish/cancel; real collision straight
  wall bonk vs glancing angles; recoil clearance/deceleration/completion; slow-roll
  refusal. Existing slow-travel jitter test now uses analog input above turn band.

Verification: 163 focused tests pass (controls 54, bg 39, air 13, climb 12,
crawl 5, animation 31, collision_gravity 9). Clean only regenerated and built:
game-clean.iso/cue produced, map independently verified, gap 29,408 B.
SH-2 disassembly for demo, player_input and link_anim_state has no float-helper
references. Launcher PowerShell wrapper returned 1 while the captured build log
finished with the successful image/map report; compiler warnings are in
game/build/m1g-clean.log. No Kronos run or full-suite run by Astra.

Kronos: light 3D Pad tilt turns in place, stronger tilt walks/runs, release stops
turning. Digital movement stays normal. Run and A-roll straight into a tall wall:
bonk/recoil/voice, then control returns. Glancing angle should not bonk. Check
recoil near a ledge, menu/combat cancellation and normal climbing/crawling.

BUG-004 now also records old 32-frame/slow roll duration. BUG-018 records linear
speed curve, missing feedback and future tree/crate bonk/drop integration.
Please review this implementation; Astra does not claim independent review of
its own M1g work. Human runtime acceptance remains pending.

# Claude to Astra: M1g in progress, handing over - 2026-09-26

Astra: Claude is out of tokens for about 2 hours. M1g is started, not done.
It's uncommitted, no commit.

Done so far:
- build_link_model.py: clips turn45 (gPlayerAnim_link_normal_45_turn, 10
  frames) and hip_down (gPlayerAnim_link_normal_hip_down, 28). Generated;
  LINKANIM is 189,552 B. No runtime code uses them yet.

Source findings (read, not implemented):
- Turn in place (Player_Action_Idle -> Player_SetupTurnInPlace ->
  Player_Action_TurnInPlace):
  - Player_CalcSpeedAndYawFromControlStick gives speed 0 at stick magnitude
    <= 20 of 60, with yaw still set.
  - If |yawTarget - facing| > 800, play 45_turn (loop) and turn at
    turnRate 1200 an update, 800 a 30 Hz step. At the target, back to idle;
    any speed goes straight to run.
  - Only analog light tilt reaches this: magnitude 20/60 is strength <= 42
    of 127. A digital pad is always full throw.
  - Our analog speed is linear; the source curve is
    ((1-cos((m-20)*450))^2*30+7)*0.14. Not ported; log it.
- Roll bonk (Player_Action_Roll):
  - Needs speedXZ >= 7, WALL_INTERACT and sWorldYawToTouchedWall < 0x2000.
    Our roll 1.5 x run 5.5 = 8.25, so it qualifies.
  - Then hip_down plays, speed = -speed, and it steps to 0 by 2 an update
    (1.33 a step = 341 Q8).
  - Voice NA_SE_VO_LI_CLIMB_END and sfx BODY_HIT. The quake (33267,3,12)
    and rumble have no port.
  - It ends when the anim finishes, or on input in its last 5 frames
    (func_8083A060).
  - En_Wood02 / Obj_Kibako2 bonk drops: neither actor is in spot04 or
    spot10 (extracted actor lists). En_Wood02 is in spot00 (Hyrule Field,
    M7): the drop rule applies there.
- Found and should be logged: the source roll ends at curFrame >= 20 at
  playSpeed 1.25 (FRAMERATE_CONST(1.25,1.5)). Our roll plays all 32 frames
  at the 2/3 cadence (about 1.6 s vs 0.8 s). This is an existing
  divergence, not an M1g change.

Suggested implementation (Claude's plan):
- link_anim_state: LINK_STATE_TURN (turn45 loop, kept at speed 0 while the
  turn is requested) and LINK_STATE_BONK (hip_down at 1 frame/step, the
  30ths phase like STEP_UP).
- demo.c:
  - Analog strength <= 42: no move; turn the facing 800/step toward the
    stick heading, in TURN while the diff > 800.
  - During a roll with speed >= 1792 Q8 (7.0), link_bg.interact and
    world_yaw_to_wall < 0x2000: bonk, then move backward at the decaying
    speed.
- Tests: extend test_player_bg (bonk into a box face at run-roll speed;
  none at a glancing angle >= 0x2000) and test_player_controls (the
  light-tilt band).

State: last full host run 654 tests + crawl prompt/camera. Only
BUG-003/008 fail. Clean gap 30,992 B (before the new clips; the clips
live in the cart).

# Astra to Claude: M1f approved - 2026-09-26

Claude: M1f code approved; proceed M1g. Human reports current crawl/camera build
good. Astra reran 174 focused tests, all pass; existing clean map gap 30,992 B.
See [M1F_REVIEW.md](M1F_REVIEW.md). No build, code edits or commit by Astra.
BUG-016 tunnel fix accepted; retain disclosed floor-ray approximation and explicit
other-low-roof check. BUG-017 stays P2, now also records camera-data validation
for future tunnels. No severe current-route blocker found.

# Claude to Astra: crawlspace first-person camera - 2026-09-26

Astra: human test passed crawl enter/exit both ways and the prompt. They
found the camera still showed Link while crawling; N64 goes first person.
Fix: a Camera_Subj4 port in demo.c.
- In PLAYER_CRAWL_IN it reads the bgCam under Link (tunnel: setting 0x1E,
  6 points).
- The eye is the closest point on the line from points [1] to [n-2],
  looking down the tunnel (the facing on entry).
- The eye bobs |cos(phase)| toward (r 5, pitch 0x238C) while moving,
  phase +0x7D0 a step (0xBB8 an update).
- Link is not drawn. On leaving, the follow camera snaps behind him.
Not ported (BUG-017): the 10-frame zoom-in, the small yaw sway, and the
OnePointCutscene exits.
Clean image built (gap 30,992 B). There's no host test (demo-only);
Kronos check needed.

# Claude to Astra: crawlspace Enter prompt - 2026-09-26

Astra: added PLAYER_STATE2_DO_ACTION_ENTER. The prompt row shows "A: Enter"
when every crawl-enter condition holds except the press: grounded,
locomotion, WALL_INTERACT, shape yaw < 0x3000, CRAWLSPACE flag, centre
within 8. It takes priority over "A: Talk" (handler 5 comes before TALK).
player_crawl_prompt shares the enter test. Test: shown at the hole, not
9 off it (test_player_crawl 5/5). Clean image built (gap 32,304 B).
Kronos not run.

# Claude to Astra: M1f crawlspaces - 2026-09-26

Astra: M1f ready for review. Uncommitted on `dev`, no commit.

Changed:
- New src/player_crawl.c/.h.
  - Enter = Player_TryEnteringCrawlspace, from handler 5 (the idle list
    too, so A with no speed). Needs a CRAWLSPACE wall flag, the hole's box
    centre within 8, and A. He is placed at centre + n*dist, facing
    wall+0x8000, and plays tunnel_start (AnimMovement x/z).
  - In = 8084C760: the pose holds, speedXZ = stick_y x 0.03 (Q8
    stick*768/100), forward or back along the facing.
  - Leave = Player_TryLeavingCrawlspace on last step's sphere wall: forward
    plays tunnel_end at wallYaw+0x8000; backward plays tunnel_start reversed
    at wallYaw. At the end, 8084C81C gives control back.
- Crawl collision mode: wall radius 10 at 15, ceiling 30
  (kokiri_collision_actor_set_crawl).
- BUG-016 (P1, shared): the grounded ceiling range now includes the source
  dy of -7.5 (velocity -4 glue + gravity). Headroom was 40, now 32.5; the
  24-high tunnel refused all motion without it.
- BUG-005 item fixed: a still step runs the wall sphere at rest
  (probe_still), so pressing A at a hole while standing works and contact
  holds when stopped.
- Clips tunnel_start and tunnel_end: raw, pinned mode 2 (x/z only, y
  drawn: UPDATE_XZ without UPDATE_Y). LINKANIM is now 184,536 B.

Verification:
- test_player_crawl 4/4 on the real sword-maze hole (S1.COL z 1059->1379,
  x -785): standing can't pass (headroom); off centre by 9 gives no
  entry; crawls through forwards and out past 1379; backs out past 1059.
- test_player_bg updated (headroom 32 / 33); climb, collision_gravity and
  bgcheck pass. Full discover: 654 tests. Only BUG-003's 2 and BUG-008's 4
  fail.
- Clean image built. SGL gap 34,944 -> 32,672 B.
- Kronos: NOT run. Please check: A at the hole near (-785,120,1040) facing
  +Z; crawl through, then back out; low roofs elsewhere (BUG-016).

Next: M1g (turn in place, roll wall bonk).

# Human Kronos check relayed by Astra - 2026-09-26

Claude: human reports tall-ledge jump works, hangs, and drops with A in response
to the requested BUG-012 check. House ladder ascent works; slow walk from porch
hangs, running jumps off, and ladder descent does not start. Vines work as
expected. Normal movement is good. Continue M1f.

BUG-012 and BUG-013 accepted with code review plus this manual check; no automated
demo_update regression claimed. BUG-015 remains open P2: port behavior now
observed, original OoT comparison still pending. Human subsequently confirmed
pull-up works too; BUG-010 now closed as well. No new build, code edits or commit by Astra.

# Astra to Claude: BUG-012 second fix accepted - 2026-09-26

Claude: launch guard accepted by code inspection. M1f may proceed.
Existing clean map verified: 34,944-byte gap. No rebuild or demo_update host
test by Astra. BUG-012 stays open for centered-input launch/grab in Kronos.
Review and issue log updated; no code changes or commit.

# Claude to Astra: BUG-012 second fix - 2026-09-26

Astra: the grounded cleanup no longer runs on the frame-8 launch step
(`launched` guard in demo.c), so the 250 jump keeps speedXZ 1.0 into the
air. Clean image built (gap 34,944 B). There's no host test yet: the path
is demo_update-only. Keep BUG-012 open until your review and the Kronos
check. M1f (crawlspace) next.

# Astra to Claude: M1e review - 2026-09-26

Claude: M1e code review approved; continue M1. Review: [M1E_REVIEW.md](M1E_REVIEW.md).
182 focused tests pass; existing clean map confirms 34,912-byte gap. No rebuild,
Kronos run, code changes or commit by Astra. Runtime checks remain pending.

BUG-012 is still open: launch assigns air speed, then the same update's final
`if (grounded || intent_speed)` clears it because grounded predates launch.
Keep P2; fix with a launch/cleanup integration regression on the next air edit.
BUG-013 code review accepted, pending runtime. BUG-014/015 remain deferred/open.

# Claude to Astra: M1e ladder and vine climbing - 2026-09-26

Astra: M1e ready for review. Uncommitted on `dev`, no commit. Includes the
BUG-012 fix, and two source-fidelity fixes found on the way (BUG-013, and
the M1d root-transfer origin).

Changed:
- New src/player_climb.c/.h.
  - `player_climb_start` = func_8083EC18. It needs yDistToLedge >= 79 and a
    WALL_FLAG_3 (vine, var1 2), FLAG_1 (ladder) or FLAG_2 wall.
    - Ladder: the poly's x/z box centre (the source's min/max scan), lateral
      |(pos - c) x n| < 8, a 15-unit rung snap from the poly's lowest vertex,
      13 in front, facing wall+0x8000, ladder_start (clink climb_startA).
    - Vine: own x/z, (13 - dist), vine_start / vine_hold in the air.
    - FLAG_2 only: climb_startB (ladder_down), facing wallYaw.
  - `player_climb_update` = Player_Action_8084BF1C:
    - Stick playSpeed |y|x0.05 (|x|x0.0325 sideways on vines), clamped
      1..3.35.
    - func_8083F360 (line -20..+50 at +26): face the wall 800/step and hold
      12 from it.
    - func_8083FBC0: A, no wall, or no climbable flag lets go.
    - Clip end: up plays unk_AC[var1+var2] (the top check is the +55/+26
      raycast); down plays it reversed (the bottom is within 15 of the
      floor). Vine sideways plays unk_BC. var2 alternates hands.
    - The top gives climb_endB (ladder) or a vine pull-up
      (func_8083A5C4 12 + jump_climb_up_free). The bottom gives climb_endA,
      or a let-go on vines.
    - The ends run 8084C5F8 at 4/3 and can be interrupted in their last
      4 frames. prevTransl follows the source: the unk_4A/62/7A/86/44 tables
      equal the clips' first/last roots; func_8083F070 keeps the previous one.
    - The +50 floor ray stands him on a ledge as he steps over it.
  - `player_climb_start_walk_off` = func_8083A6AC's climb branch
    (Fclimb_startB, var1 1, var2 -1).
- link_anim_state: LINK_STATE_CLIMB and link_anim_move_* (play fwd/reversed,
  ADJUST_STARTING_POS, keep prevTransl, per-step raw root delta). The climb
  clips are stored raw and drawn with the root pinned at sSkeletonBaseTransl
  x 0.64 (SkelAnime_UpdateTranslation + the UPDATE-bit child scaling). The
  actor moves by raw delta x 0.01 (AnimTask_ActorMovement, diffScaleY 1 with
  DISABLE). 16 clips, LINKANIM 103,752 -> 164,604 B.
- demo.c: handler 5 runs after 12 in the walk/run lists. The air start is
  yDist >= 150, stick pushed forward, speed > 0. The walk-off vine start is
  PLAYER_HANG_CLIMB. No gravity while CLIMB (OVERRIDE_MOVEMENT). Let-go is
  a fall at 0.4 away from the wall. BUG-012: the frame-8 launch sets air
  speed 1.0.
- BUG-013 (shared collision): bg_floor, bg_ceiling and the wall sphere now
  use the source Approx point-in-poly test (box +1, vertex, detMax 300
  determinants, or 1 from an edge when facing the axis) instead of a 1-unit
  edge tolerance. Effect: a 400-wide 25-high step is now walked onto (26
  blocks); narrow polys get their source slack. Lines unchanged. Legacy
  kokiri_collision_floor still strict.
- M1d fix: pull-up / let-go transfers measure from base (-57,3377,0) x 0.64
  (was 0; about 1 unit).
- New kokiri_collision `bg_poly_vertices`.

Verification:
- test_player_climb 12/12. It covers:
  - Start centring, facing and rung snap.
  - Refusals: 9 off centre, plain wall, short wall = ledge.
  - Up and off the top: stands on 180, past the lip.
  - Rungs 15 apart; centred stick finishes the rung then holds at 12 from
    the wall.
  - Down and step off at the bottom; A lets go.
  - The 20-high lip is not touched from above; a FLAG_2 wall starts
    climb_startB and climbs down to the ground.
  - Vine: start, sideways (16 right), top, bottom let go.
  - Real S1.COL: the house ladder up onto the porch (100); the vine wall
    (-570,60,-1036) up to 200.
- test_player_bg 37/37: thresholds moved by BUG-013 (25 now climbed, hop at
  26), and M1d transfer values updated.
- test_link_geometry_precision: the reference uses the pinned root.
- Full discover: 649 tests. Only BUG-003's 2 and BUG-008's 4 fail.
- Clean image built. SGL gap 40,832 -> 34,912 B. Changed units compiled
  without LTO: shifts and integer divides only.
- Kronos: NOT run. Please check:
  - Walk into the house ladder from the ground at (-29, -80, ~960) facing
    +Z; climb up, and the step-off onto the porch.
  - At the top, walk back at the ladder (BUG-015: source rules give no
    climb-down here).
  - Vine wall at (-570,60,-1036) facing +X: up, sideways, top pull-up, and
    A to let go.
  - General walking, steps and walls after BUG-013.
  - 164 KB LINKANIM still loads.

Logged: BUG-013 (fixed, P1), BUG-014 (climb subset gaps), BUG-015 (porch
descent, needs-triage). BUG-012 fixed. Climb camera (Jump2) is still the
last M1 camera item.

# Astra to Claude: M1d code review approved - 2026-09-26

Claude: M1e may begin. Details in [M1D_REVIEW.md](M1D_REVIEW.md).
143 focused tests pass; existing clean map gap 40,832 B verified. BUG-010/011
code accepted, runtime checks still pending. No severe blocker found.
BUG-012 logged (P2): grounded preparation clears retained 250-jump air speed
before launch; centered-stick grab can fail. Fix with next air/grab integration;
held direction remains available. Keep existing BUG-005/007/009 follow-ups.
No rebuild/Kronos run by Astra. Boot, hang/pull-up/drop continuity, both controller
paths and prior jump/opening checks remain for human runtime verification.
Only review/log docs changed; no code edits or commit.

# Claude to Astra: M1d ledge hang, pull-up, let go - 2026-09-26

Astra: M1d ready for review. Uncommitted on `dev`, no commit. Includes the
BUG-011 fix.

Changed:
- player_bg.c:
  - `player_hang_walk_off` = func_8083A6AC. It needs depthInWater < -80
    (no water box counts as -32000). The line runs one-face, walls only,
    from feet at the departure-step drop to 5 units behind the last
    position. It needs |ny| < 600/32767 and takes the UDist plane distance.
    Floor property 6 or WALL_FLAG_3 returns CLIMB (M1e; he falls for now).
  - `player_hang_grab` = the 8084411C test: WALL_INTERACT, speedXZ > 0,
    ledgeClimbType >= 2, yDist < 150, (y - floorHeight) + yDist > 45.29.
  - `player_hang_place` = func_8083A5C4: (dist+1) into the wall. Facing is
    the normal's yaw, +0x8000 for a grab.
- demo.c:
  - PLAYER_LEAVE_HANG now calls the walk-off rule. The feet it uses are 5
    below the departure (-4 glue + gravity = 4.67).
  - A descending grab is checked each step after the probe. Placement is
    then followed by the source's next +50 floor ray, so the actor stands
    on the ledge top while the clip hangs the body.
  - Hang controls (once actionVar1 != 0): `player_input_stick_pushed`
    (magnitude 55 of 60; digital = full) pulls up; A held lets go.
  - Pull-up end: the clip's last root x/z moves the actor (base x/z 0,
    SkelAnime_UpdateTranslation rotation), then the root limb yaw turns
    him (fall_up 0x8000).
  - Let go: the actor goes to the hanging pelvis (func_80837B60), clamped
    to the floor ray. Then he falls, with speed 0.8 away from the wall.
  - Air speed kept with the stick centred: hop 2.5, 250 jump 1.0, let go
    0.8, decaying 0.1 a frame (17 Q8 a step). This speed also counts as
    the grab's speedXZ.
- link_anim_state: HANG plays normal_fall then fall_wait (walk-off), or
  jump_climb_hold then jump_climb_wait (grab), at 1.0. The grab frame
  (11 / 1) sets actionVar1 with the floor sound. PULL_UP runs at 1.3: end-34
  plays CLIMB_END, end-6 the footstep. `link_anim_pull_up_done` and
  `link_anim_let_go` return root motion from the loaded tables (link_anim.c
  pointers are no longer static). The strided waits map source frames to
  their stored rows.
- Clips hang_fall, fall_wait (stride 3), fall_up, climb_hold, climb_wait
  (stride 3), climb_up. The non-free variants, child root x0.64. LINKANIM is
  74,068 -> 103,752 B (cart).
- player_input: `interact_held`, `player_input_stick_pushed`. BUG-011:
  link_anim_roll_input gets 0 unless a direction is held.

Verification:
- test_player_bg 37/37. New tests cover:
  - Walk-off hang: face hit, dist 3, placed at z -1 facing out, ledge top.
  - Walk-off refusals: water -79/-81, prop 6 / FLAG_3 -> CLIMB, leaning wall.
  - 250 jump grabs at 50 and 70: ledge top, 1 in, facing the wall.
  - Grab refusals: speed 0, 45 vs 46, CLIMB_1.
  - Grab frames 11 and 1, and the wait loops.
  - Pull-up: 67 / 30 steps, root x/z and 0x8000 turn, climb voice.
  - Let-go pelvis.
  - Real-collision mirror: grab then pull up (ends on the top, further in);
    grab then let go (lands below, pushed clear to <= -14).
  - Forest walk-off at (314,3,-198).
- test_player_controls 53/53 (A held, stick 55/60). Also pass: player_air,
  link_animation, collision_gravity, bgcheck, oot_follow, navi, gameplay.
  Full discover: 637 tests, only BUG-003's 2 and BUG-008's 4.
- Clean image built. SGL gap 43,952 -> 40,832 B. Changed units compiled
  without LTO: shifts and integer divides only.
- Kronos: NOT run. Please check:
  - B-walk off a drop deeper than 45, e.g. west from (314,3,-198).
    Link hangs. The M1b porch check (B walk-off = plain fall) now expects a
    hang where the line test finds the porch face; porch not scanned.
  - Push the stick to pull up; hold A to let go.
  - 47+ ledge, e.g. (-462,0,-682) facing 0x727D: the 250 jump grabs, then
    pull up.
  - Watch hang, pull-up and let-go draw continuity.
  - LINKANIM is 103 KB now: boot still loads it.

Logged: BUG-005 (air steering approximation, feetFloorFlag drop, M1e
climb starts), BUG-007 (HANG voice, SLIPDOWN, CLIMB_CLIFF samples), BUG-009
(let-go drop uses the drawn 1.45x scale). BUG-010 implemented and BUG-011
fixed: both await review and a Kronos check. Hang camera (Unique1) remains
the last M1 camera item.

# Astra to Claude: M1c code review approved - 2026-09-26

Claude: M1d may begin. See [M1C_REVIEW.md](M1C_REVIEW.md).
160 focused tests pass; existing clean map gap 43,952 B verified. No severe
blocker found. BUG-011 logged: released digital pad can trigger climb's early
interrupt through nonzero base speed; fix with next climb/input integration.
No rebuild/Kronos run by Astra. Ledge poses/voices, opening height and M1b jump
feel remain pending human checks. 250 mid-air grab remains M1d/BUG-010.
Only review/log docs changed; code untouched, no commit.

# Claude to Astra: M1c step-up, wall/ledge probe, ledge climbs - 2026-09-26

Astra: M1c ready for review. Uncommitted on `dev`, no commit. Human
decisions this task: 250 jump starts now, grab stays M1d (Link lands back,
no snap); child root x0.64 fixed first; source step-up ported (found
walk-through of 6-10 steps, block at 15+). Verify source checks, no blanket
snap: done, see tests.

Changed:
- Root fix (build_link_model.py): source Player_OverrideLimbDrawGameplayCommon
  child root x0.64 on x/y/z. Every gameplay clip is scaled (action changes
  clear movementFlags). The opening's clink_op3_* clips stay raw: they play
  with DISABLE_CHILD_ROOT_ADJUSTMENT via func_808510F4/80851134/80851E90/
  80851ECC/80851FB0, and stand_up ends at 2161 = 3377 x 0.64. turn_look is
  adult-authored (3375) and is scaled. Bind pose is scaled too: ground shift
  -17 -> +1. Deltas drawn, before -> after: walk bob 1.7 -> 1.1, run 6.8 ->
  4.4, landing dip 23.2 -> 14.9, roll dip 43.7 -> 28.0, jump rise 20.8 ->
  13.3. Cutscene Link draws ~18 higher (the source-consistent height). Navi
  LINK_HEAD 45 -> 46 (re-derived).
- Movement (kokiri_collision_move_actor, feet space), in Actor_UpdateBgCheckInfo order:
  bg_wall r14 h26 BG_IGNORE_ENTITY. Then the ceiling from prev+10 over 30:
  a hit sets y = ceil-40. Then the floor ray from +50 (highest floor <= y+49).
  At or above the feet he stands on it, unless a ceiling on the same bgId was
  hit, in which case x/z revert. Below the feet, y is kept, with ground follow
  <= 11 (func_8002E234). Vertical moves check only the ceiling (source) and
  the floor. The old wall sphere pinned him on a wall's radius and is gone.
  The old head sphere (+54 r8) is kept for non-ceiling polys only (bridge
  underside, custom Y jump). The camera free-move path is unchanged. New:
  `bg_poly_plane_distance`, `kokiri_collision_actor_begin_step/_actor_wall`.
- New src/player_bg.c/.h. Wall block of Player_ProcessSceneCollision:
  interact line (+18, reach 24, one-face walls). Wall yaw =
  Math_Atan2S(nz,nx). Checks: shape diff < 0x3000, |ny| < 300 Q14 (600 Q15).
  Probe dist+10 in, from +71, via RaycastDown. Rejects: <18, ceiling at
  yDist+20, blocking wall at ledge+5 unless FLAG_1, FLAG_0 wall. Floor ny >
  14000 Q14 (0x6D60) for types 2-4. Thresholds 27/39/47. Timer 3/6 frames ->
  5/9 steps (cap 150). Player_ActionHandler_12: needs grounded, dyna+FLAG_6
  needs timer AND A, hop vel 0.08d+5.5, jump250 vel min(d,71)*0.072+1.
- demo.c: the handler runs before the move, on last step's probe, from
  IDLE/WALK/RUN with commanded speed. It takes an unclaimed A ahead of the
  roll. Step-up: xz -= (dist+1)*n, y += yDist, facing wall+0x8000. 250:
  speed 1.0 into the wall, launch at frame 8 (AUTO_JUMP voice). Hop: jump
  clip, SWORD_N_KID voice. Climbs lock walk, jump and roll. The probe runs
  after the facing update each step.
- link_anim_state: STEP_UP/JUMP_START at the source rate. LinkAnimation_Once:
  1.3 x 1.5 per update = 1.3 frames per step. Interrupt in the last 4 frames
  on move input. shape.yOffset starts at RISE - yDist and steps 1/step (all
  of 100step; 150step after frame 5). CLIMB_END at frame 16/30. RISE =
  drawn root rise (37.3 / 55.6) from link_clips.h, standing in for
  41/59 x 11/17 at the drawn 1.45x scale. main.c adds the offset to the
  drawn feet.
- Audio: NA_SE_VO_LI_CLIMB_END_KID EFFECT_35 added to the core bank
  (EFFECT_36 does not fit; 852 bytes spare). LINKANIM 74,068 B (3 clips).
- TRAVERSAL_TIMING anim row was wrong (source = playSpeed per 30 Hz step).
  Corrected; locomotion keeps its 2/3 tuning (BUG-004).

Verification:
- New test_player_bg 28/28 on real C. Steps 3/10/20/24 walked up and 25/30/47/80
  blocked at 14. Headroom 39 blocks, 40 passes. Slope up/down stays
  grounded; a 0.37 slope is a wall. Wall yaw basis. Every threshold 25-72.
  The facing/interact line, leaning wall, steep top, ceiling 49/51,
  blocking wall, FLAG_0, FLAG_1 blocker and dyna FLAG_6. Timer 9 or A,
  hop 5 steps. Step target on the ledge floor. Offsets, steps 22/35, voice
  step, interrupt at 18. Jump250 launch at step 7, falls back. Hop lands on
  25/26. Y jump apex 51, and it mounts a 40 block by the floor ray. A wall
  at contact does not pin a jump. Ceiling cap 20 under 60. Walk-off still
  departs. Real S1.COL: CLIMB_3 (1219,-60,59) yaw 0x4000 yDist 39; CLIMB_2
  (172,28,-483) 0x8B87 32; CLIMB_4 (-462,0,-682) 0x727D 59. Scan: 1 hop, 8
  / 93 / 34 spots of types 2/3/4.
- Rerun pass: link_animation 31, player_air 13, collision_gravity 9,
  bgcheck 27, player_controls 52, oot_follow, navi, collision_index,
  link_geometry_precision, gameplay. Full discover: 628 tests. The only
  failures are BUG-003's 2 and 4 stale snippet tests (BUG-008: title_flights
  broke when M1b put link_leave_ground in its demo.c slice; the others cut
  files M1c did not touch).
- Clean image built. SGL gap 48,432 -> 43,952 B. Changed units compiled
  without LTO: no float helpers (only shifts, __udivsi3/__sdivsi3/__divdi3).
- Kronos: NOT run (human playing). Please check: walk onto any low step
  (under 25); hop spot (561,-23,-212) facing +Z; climb at the CLIMB_3 spot (1219,-60,59) facing
  +X and the CLIMB_2 spot (172,28,-483). 47+ walls (e.g. -462,0,-682): Link
  hops and lands back (M1d). Check the step-up draws smoothly (no pop) and
  the climb voice plays. Check the opening: bed/stand heights (+18 shift). The
  M1b porch auto-jump and Y jump checks are still pending.

Logged (BUG_FEATURE_LOG): BUG-004 cadence, BUG-005 subset gaps (unk_880,
stationary wall, hop air speed, headroom 1-frame y/crush, floor-class snap),
BUG-006 talk vs ledge A order, BUG-007 floor jump/land SFX + 2nd climb voice,
BUG-008 snippet tests, BUG-009 1.45x draw scale vs headroom 40, BUG-010 250
grab (P1, M1d). BUG-001 not escalated: the probe reads the sphere's final
poly, and bit-27 precedence is still unused.

# Astra to Claude: M1b review approved - 2026-09-26

Claude: M1b code review approved; M1c may begin. No severe blocker found.
Details: [M1B_REVIEW.md](M1B_REVIEW.md). Air/gravity/controls/animation/camera
host modules pass 133/133; manual Y jump independently measured at apex 51,
landing step 25. Existing clean map gap 48,432 B verified.
No rebuild/Kronos run by Astra. New porch auto-jump/voice, B walk-off, quicker Y
jump and landing feel still need human runtime check; previous M1a smoke does
not cover these changes. Keep pending while M1c proceeds.
Hang M1d/water M1k and BUG-001..003 remain explicit follow-ups. Only review docs
changed; implementation untouched, no commit. Supersedes M1c-waits notes below.

# Claude to Astra: M1b gravity + automatic ledge jump - 2026-09-26

Astra: M1b ready for review. Uncommitted on `dev`. M1c (ledge probe,
hop/step-up) next after your review.

Changed:
- Gravity to source: `GRAVITY_Q8 -171`, terminal `-5120` (REG(68) -1.0,
  minVelocityY -20, x1.5 speedRate, accel x2/3). Custom Y jump 1792 -> 2208
  Q8: apex 51 as before, airtime 31 -> 25 steps (feel change: faster fall).
- New `src/player_air.c/.h`: func_8083AA10 departure + func_8083A4A8 launch.
  Child Kokiri-boot regs (sBootData KOKIRI_CHILD): speed > 5.4 -> 7.5
  (1920 Q8) else 1.25 + 0.4*speed. Auto-jump needs GROUND_LEAVE, prev floor
  property not 6/9, yDistToFloor > 20, |yaw - facing| < 0x2000, speed > 3,
  not swinging. run_jump clip if |diff| < 0x1000 and speed > 4, else jump.
  Property 8 reverts X/Z; 7 or swinging reverts move + stops roll. Water
  run-jump (property 11) = ordinary jump until M1k. Deep drop > 45 (child
  unk_34) returns HANG request -> falls until M1d (func_8083A6AC).
- demo.c: departure checked after the horizontal move, before gravity, only
  when grounded last step, not already jumping, and no longer standing.
  speed = commanded locomotion (or roll) Q8, not integer travel; yaw diff =
  requested heading - facing. Floor property of the standing floor read via
  `bg_floor(BG_IGNORE_ENTITY)` each grounded step (sPrevFloorProperty).
  Auto-jump plays the existing GP_EVENT_JUMP cue (auto-jump voice).
- Fall distance now departure - landing (fallStartHeight is not raised by
  a jump); the airborne peak raise is gone. Y jump on flat ground: 0 -> short
  landing, as before (was ~51, also short).
- link_anim_state: LINK_STATE_JUMP (jump/run_jump held on last frame; swaps
  to FALL once descending below departure, as Player_Action_8084411C swaps
  to its landing-ready anim) and LINK_STATE_JUMP_LANDING (run_jump_end: run
  jump landing, ahead of short-landing/roll choice). New clips jump 9,
  run_jump 13, run_jump_end 19 (whole, roots kept: pelvis dip only).
  LINKANIM.BIN 63,112 B.

Verification:
- Host: new test_player_air 13/13 (every threshold/branch incl. 5.4 edge,
  0x1000/0x2000, 20, 45, props 6/7/8/9, swinging; gravity -171/-342/-513
  -> -5120; anim run_jump hold/run_jump_end/fall-swap/roll/standing jump;
  collision+rules mirror of demo order: run off 60 -> run jump, lands 60
  below, rises > 20; walk off 30 -> fall; 10-unit step -> ground follow).
  Also pass: bgcheck, collision_gravity, collision_index, link_animation,
  link_geometry, navi, cutscene_parity, skinning, player_controls, gameplay,
  oot_follow. locomotion_timing: same 2 BUG-003 failures only.
- Build: Clean image. SGL gap 48,432 B. No soft-float in changed objects.
- Kronos: NOT run by me. Please check: run off the porch outside Link's
  house (y 100) -> run jump + auto-jump voice; walk (B) off it -> plain
  fall; Y jump height same, quicker; landings.

Not done in M1b (stated): player_bg.c wall/ledge probe (starts M1c, where
it is first needed); hang on walk-off (M1d); water run-jump (M1k).

# Astra to Claude: M1a re-review approved - 2026-09-26

Claude: all three fixes accepted. M1b may begin. No new severe blockers found.
Reran bgcheck 27/27, link_animation 30/30, player_controls 52/52; clean map gap
49,312 B verified. No rebuild/Kronos run by Astra; human smoke belongs to prior
M1a image. Details in M1A_REVIEW.md re-review section.
Nonblocking follow-ups logged BUG-001..003 (wall precedence, failed-decode
recovery, stale locomotion test text). M1b owns ignore-mask/timing integration;
M1h still owes live dynamic-actor verification. Full M1 not declared complete.
Only review/log docs changed; implementation untouched, no commit.
This supersedes earlier M1b-waits notes below.

# Claude to Astra: M1A_REVIEW fixes - 2026-09-25

Astra: all three findings fixed, regressions added. Uncommitted on `dev`.
M1a back for re-review; M1b still waits.

- P1 registration: `bg_dyna_register` snapshots ONLY the new slot
  (`dyna_snapshot`); no global step. Your repro (A moves, register B, carry
  A) now gives x=30. Slot reuse mid-step: fresh history, other slot keeps
  its motion.
- P1 carry: now `DynaPolyActor_TransformCarriedActor` per flag. POS =
  cur * inverse(prev) on position: translation, Y rotation, uniform scale
  ratio (prev scale kept per slot; zero prev scale = no move, as the failed
  SkinMatrix_Invert). ROT_Y = yaw += cur - prev only. Returns true when a
  flag applied (source), so POS with no motion is true + unchanged.
  Removed or disabled slot -> false (source only checks IN_USE; a disabled
  mesh cannot be the floor bgId, so same result in practice - your rule).
- P2 LINKANIM: header word 12 is now an FNV-1a digest over clip layout
  (first/count as BE u16) + body bytes, order-sensitive. Generator compiles
  it as `LINK_FRAMES_DIGEST` in link_clips.h. Loader requires header ==
  ELF constant AND recomputes over the ELF's OWN link_clips[] + file body.
  Additive sum removed. Current value 0xF246118C, matches disc file.
- Also: camera vector range check no longer wraps (first > vectors ||
  count > vectors - first).

Tests:
- test_bgcheck 27/27: + POS-only, ROT_Y-only, neither, translation+rotation,
  scale change, registration-between-move-and-carry + slot reuse,
  disabled/removed no carry, camera range wrap. Existing move test updated
  (no-motion carry now true, position unchanged).
- test_link_animation 30/30: new LinkAnimLoader compiles the real
  link_anim_load (-DLINK_FRAMES_FROM_DISC, stub jo_fs) - current loads;
  missing / truncated / bad magic / flipped byte refused; same-shape stale
  with restamped header digest refused; reordered root rows refused.
- Also pass: collision_gravity, collision_index, link_geometry_precision,
  navi, player_controls.
- Clean image rebuilt: SGL gap 49,312 B. link_anim / collision objects: no
  soft-float helpers. Kronos not run by me (human smoke test of previous
  M1a Clean image was good, per your review).

Ledger kept open (your P3 list, unchanged): wall line-hit vs flag-27
precedence, legacy ignore flags (M1b chooses BG_IGNORE_ENTITY explicitly
and tests), non-transactional decode, no live dyna actor yet (push/pull
checkpoint M1h), timing doc = Actor_UpdatePos baseline only, locomotion
text checks vs analog commit.

# Astra to Claude: M1a review needs fixes - 2026-09-25

Claude: human reports Clean runtime test good. Review details/repros in
[M1A_REVIEW.md](M1A_REVIEW.md). M1b waits for three fixes:
1. Registering a dyna mesh snapshots ALL slots, erasing another platform's
   pending carry delta. Initialize only the new slot's history.
2. Carry flags differ from source: POS transforms rider position (rotation/scale
   included); ROT_Y changes facing only. POS-only and ROT_Y-only repros fail.
3. LINKANIM checksum is self-contained, not tied to ELF; valid stale same-shape
   files pass. Compile an expected content/layout signature and test rejection.
109 focused host tests pass; extra C repros confirm dyna bugs. Existing clean map
verified at 49,568-byte gap. No rebuild/Kronos run by Astra; human smoke noted.
Only review docs changed. Your implementation left untouched, no commit.

# Claude to Astra: M1a world-collision contract - 2026-09-25

Astra: M1a ready for review. Uncommitted on `dev`, no commit. M1b+ waits for
your review. Kronos tests: Clean image only, per your rule.

Changed:
- Link clip frames off work RAM. `build_link_model.py` writes LINKANIM.BIN
  ('LAN1', frames, limbs, checksum); `link_anim_load()` reads it into cart at
  boot, refuses stale file (`jo_core_error`). `link_clips.c` keeps arrays
  only for host builds (`#ifndef LINK_FRAMES_FROM_DISC`, makefile defines).
  Tables byte-identical to before.
- S<n>.COL is now KBG2 (`build_scene_table.py collision_file`): 36 B tris
  unchanged, per-tri u16 info (surface idx, ignore cam/entity/proj, floor
  conveyor), raw SurfaceType data0/data1 (all bits), raw WaterBoxes, bgCam
  setting + Vec3s data. `.SUR` retired (build.sh deletes stale ones).
  Extractor `collision_data` / `collision_header_data` / `extract_object`
  in shared/tools/build_kokiri_scene.py.
- Contract in `shared/lib/collision/kokiri_collision.h/.c` (feet space):
  `bg_floor` (RaycastDown: floors + up-facing walls, strictly below, isSoft
  -1), `bg_wall` (CheckWallImpl incl. line pre-tests, Z/X-pass SphVsWall,
  ComputeWallDisplacement flag-27 rule, dyna post-line), `bg_ceiling`,
  `bg_line` (LineVsPoly, one-face, nearest), `bg_water_surface` (strict
  bounds, room, disabled). `bg_hit_t` = normal, poly, bg_id (BG_SCENE 50 /
  dyna id), ignore, conveyor, raw data0/data1. Getters = SurfaceType_Get*
  bit layout; `bg_wall_flags` = D_80119D90.
- DynaPoly: 16 slots, 512 world tris in cart fixed carve (RAM_CART_FIXED
  0x4000 -> 0x8000; dyna at 0x2000, 0x4800 B). register / set (scale Q16,
  rot_y, pos, = ExpandSRT) / enable / remove / step / carry. Actor Destroy
  must call `bg_dyna_remove` (as DynaPoly_DeleteBgActor). `bg_dyna_step()`
  once per gameplay step in demo.c. Scene load clears slots.
- Old API (`kokiri_collision_*`, eye anchor) same results; it now also sees
  dyna tris (nothing registers yet -> no behaviour change).
- Representative actor data: PUSHBLK.COL = gPushBlockCol (gameplay_dangeon_
  keep 0x4E98), generated only. Obj_Oshihiki drops: none in source (no
  Item_Drop* call in z_obj_oshihiki.c). Actor itself = M1h.
- New `game/docs/TRAVERSAL_TIMING.md`: 20 Hz -> 30 Hz rules (velocity same
  value because speedRate 1.5; accel x2/3; frames x3/2). Confirms current
  gravity -114 Q8 is 2/3 of source; fix planned M1b (keep Y jump apex).

Verification:
- Host: new test_bgcheck 19/19 on real S1.COL/S0.COL/PUSHBLK.COL (ladder
  face z1004 wall type 2 flags 0x03, lip z1008 type 3 flags 0x05, porch y100
  bgCam 4, crawl hole type 5 -> 0x10 within x-801..-769, type 4 wall ->
  0x08, forest waterbox -12 strict edge + room, exit polys, raw surface words
  survive, wall push 86, no tunnel, ceiling, floor strict, dyna floor/wall
  0x40/move/carry/rotate/disable/remove, block stops old Link move). Also
  pass: collision_gravity, collision_index, link_animation (+2 new), link
  geometry, navi, cutscene_parity, skinning, player_controls, demo_assets,
  asset_names, build_sgl_area, actor_sys, gameplay, save_file.
- test_locomotion_timing: 1 fail + 1 error PRE-EXISTING on clean HEAD
  (demo.c text regexes vs analog commit 256e315). Not touched.
- Build: Clean image built. SGL gap clean 49,568 B (was 4,624). Changed
  objects pull no soft-float helpers (nm: only __divdi3/__sdivsi3/shifts).
- Kronos: NOT run. Needs: boot (LINKANIM.BIN load, cart carve), forest walk,
  house door both ways, jump, ledge fall, slopes - expect same as before.

Known small gaps (for review):
- bg_wall's sphere pass does not inherit the line pre-test poly as its
  starting outPoly (source does); only affects flag-27 tie-break.
- Old movement still ignores poly ignore flags (behaviour kept on purpose);
  new player code will pass BG_IGNORE_ENTITY. Decide in M1b.
- Collision decode writes into the live buffer; a corrupt file mid-decode
  would leave the old scene broken (load then fails anyway).

# Astra to Claude: remaining milestone drafts + VDP2 menus - 2026-09-25

Claude: human requested individual M3-M9 plans, including M6b, matching M2's
structure. Links in DEMO_PLAN.md under Detailed milestone drafts. Planning only;
no ownership/status advance, builds, code edits or M1 changes by this task.
Each covers dependencies, source ledger, review checkpoints, acceptance and named
deferred checks. Meadow remains an explicit open scope decision. M7 notes the
ocarina source's five basic buttons plus special pitch case, not assumed six keys.
Human added a hard requirement: ALL menus use VDP2, with no menu VDP1 textures or
sprite commands. Applied to M2, all new drafts and DEMO_PLAN; M8 has a dedicated
VDP2 layer/tile/palette/restoration audit. Clean-only build policy carried forward.
Files: eight new M3-M9/M6b drafts, existing M2 draft, DEMO_PLAN, this handoff.
Human requested a separate documentation-only commit. Existing in-progress
code/asset changes remain untouched.

# Astra to Claude: M2 side draft - 2026-09-25

Claude: human requested planning only. See [M2_COMBAT_PLAN.md](M2_COMBAT_PLAN.md).
M1 work untouched; M2 implementation/ownership still pending milestone review.
Draft covers M1 contracts, live combat loop, sword/guard/evasion, attention and
Karebaba, hearts/death/save/continue. Source checks caught two dependencies:
Karebaba offers a stick via get-item (minimal inventory/save support needed),
and Nutsball reflection needs shield-bounce/allegiance handling beyond M0 collide.
Clean-only build policy recorded. No code/build/runtime work for this draft.
Changed only this handoff and the new plan; left uncommitted.

# Astra to Claude: slow-walk facing jitter - 2026-09-25

Claude: human reports slow forward walking makes Link turn left/right and shakes
camera, predating 3D Pad support. `demo.c` inferred facing from each whole-unit
post-collision displacement. Fractional travel produces alternating staircase
steps; the camera then chases those headings and feeds them back into movement.
Facing now uses requested camera-relative input heading when actually moving.
Target/strafe priority preserved; rolling holds its heading. Actual displacement
still drives collision, animation and the camera movement flag.
Controls tests 52/52 (digital walk + analog creep rounding regression); existing
follow camera tests 29/29. Only clean rebuilt; map gap 3,488 bytes, arena unchanged.
Human confirmed runtime fix works and requested this separate commit.
This fix is separate from committed 3D Pad support; M1 remains yours.

# Astra to Claude: 3D Control Pad side task - 2026-09-25

Claude: analog support ready; separate commit requested by human. M1 remains yours.
- `demo.c` samples the SGL/Jo 3D Pad ID and X/Y axes in VBlank. Movement
  uses the existing heading/collision/remainder path. No world-collision edits.
- `player_input.[ch]`: circular deadzone 16, continuous camera-relative heading,
  proportional speed; B selects walk/run ceiling. L+stick looks; Z targets.
  3D D-pad supplies C directions during gameplay, raw menu navigation while
  menus/dialogue own input. Stick movement and C input can coexist. Digital
  controllers (including a 3D Pad in digital mode) keep the existing mapping.
- `main.c` pause help adapts to the detected pad. C-item gameplay remains pending;
  this supplies the existing C input interface, not item implementations.
- Host controls 50/50, diff check clean. SH-2 input object has no float helpers.
  Only clean image rebuilt per human request: `game/build/game-clean.cue`.
  Map checked: 3,552 bytes below SGL work area; arena remains 51,200.
- Kronos not launched. Human should choose 3D Control Pad/analog mode, check
  small/full stick travel, camera-relative direction, L look, D-pad C input,
  pause/file menu navigation, and switching back to a digital controller.

# Astra to Claude: M0 re-review approved - 2026-09-25

Claude: both fixes accepted. Capsule repros/misses/reversal covered; unsigned
attention sum safe after range box. actor_sys 20/20 and shot skip 9/9 rerun.
Existing map gaps verified: normal 1840 / hires 1744 / clean 4624 bytes.
No new blockers. Details: M0_REVIEW.md re-review section.

PAL correction: skip_input uses normalized game ticks, not raw VBlanks.
demo_vblank's phase += 60 / subtract refresh loop yields 60 ticks/sec at both
50 and 60 Hz refresh. 120 ticks is two seconds; no timing fix needed.
Agree music fade chaining is nonblocking. Measure real heap use before any
further arena cut. Runtime checks remain recorded; no Kronos run this review.

M1 may begin with the world-collision contract from DEMO_PLAN. No commit.
Return M1 for review before next milestone. This supersedes M1-waits notes below.

# Claude: M0 review fixes + review of Astra save/skip diff - 2026-09-25

Astra: both M0_REVIEW bugs fixed. Uncommitted, no commit.
- `collide.c` cap_cyl: segment first clipped (Q12) to cylinder height span
  +/- capsule radius, then XZ-closest t clamped inside that interval. Both
  your repro cases now hit (vertical overlap 15, sloped > 0, either order).
  New misses covered: below span, above span, XZ out of reach; reversed
  slope and flat-inside cases hit.
- `actor_sys.c` attention: squares summed unsigned (< 2^32 after box test).
  (40000,40000) at range 46340 -> no target; (30000,30000) found; huge range
  clamps safely.
- `actor_sys.h` comment now names `ram_cart_fixed`, not jo_malloc.
- Verified: test_actor_sys 20/20. All three images rebuilt on your
  51,200 arena; SGL gaps normal 1,840 / hires 1,744 / clean 4,624 B.
  Kronos not run.

Your diff reviewed (makefile -MMD/-MP + makefile dep, skip_input.h,
cutscene skip, arena): approve. Save crash root cause and fix make sense.
Minor notes, no change made:
- skip_input.h says VBlank clock is 60 Hz on PAL too; PAL VBlank is 50 Hz,
  so 120 ticks = 2.4 s there. NTSC build only today; fix comment or scale if
  PAL ever ships (action_audio already reads TVSTAT for 50/60).
- Skipping over several music cues replays them one after another, because
  each waits for the previous fade (music_busy). Brief audible fade chain,
  not a hang. Fine unless the human hears it.
- Gap now ~1.8 KB normal. M1 code will cross it again; next trims need real
  heap measurement, not more guessed arena cuts.

M0 ready for your re-review. M1 still waits.

# Astra: skip prompt cleanup - 2026-09-25

Claude: human reports skip otherwise works, but final "n" stayed on screen.
Prompt is 23 characters; clear string was 22. Fixed clear to 23 in main.c.
All three images rebuilt; prompt/clear lengths and SGL boundaries checked.
No commit. Prior save/skip work and M0 review status preserved.

# Astra: save crash + permanent shot skip - 2026-09-25

Claude: save crash cause proved in clean target code. Stale save_device.o
reserved 220 bytes; rebuilt save_file_pack wrote 300, smashing 80 bytes of
stack. Missing header dependencies, not serializer logic. Full evidence:
[SAVE_CRASH_2026-09-25.md](SAVE_CRASH_2026-09-25.md).

Changes (Astra, uncommitted on dev):
- makefile emits/includes .d files for all C rules (-MMD -MP). Every object
  depends on makefile, bootstrapping old objects and rebuilding configuration.
- Full rebuild + skip crossed normal SGL boundary by 16 bytes. Arena now
  51,200 bytes (was 53,248); allocation still spills into cart zones.
- Human clarified PERMANENT feature: first Start shows
  "Skip? Press Start Again"; second within TWO SECONDS skips current CAMERA
  SHOT only. Not the entire cutscene/opening. All three variants.
- build_cutscenes.py bakes eye-spline shot starts. skip_input.h handles VBlank
  edges, timeout, hold and shot changes. demo/main handle input/prompt;
  cutscene.c seeks actors/misc, discards skipped text, keeps target text,
  restores loops and waits for pending music before chaining. Last shot uses
  normal progress/audio cleanup. Catch-up stops on completion.
- New test_cutscene_skip.py, source shot-boundary regression, README/progress
  updates. No changes to the earlier actor/collision findings.

Verified: 79 focused host tests pass (skip 9, cutscenes 32, parity 8, save_file
20, action_audio 10). All three images rebuilt; final SGL gaps normal 1,936 /
hires 1,808 / clean 4,720 bytes. All three disassemblies reserve 344-byte frames
(44 + 300) and pass 300 to backup write. Header-change dry run recompiles caller.

Kronos: read-only GDB captured old stalled PC 0x06000952 and RAM. No new
emulator launched, no global keys, no user backup-RAM changes. Fixed save/load
and visible skip still need replay from a freshly booted image. Old unrelated
harness failures remain. No commit. M0_REVIEW bugs still open; M1 waits.
Please review this diff too.

# Astra M0 review - 2026-09-25

Changes requested; M1 waits. See [M0_REVIEW.md](M0_REVIEW.md).
Two reproduced bugs: capsule contact misses and attention distance overflow.
145 focused tests pass; three harness compile failures reproduced.
Kronos still unchecked. L looks / Z targets already settled by Sept 22 remap;
CLAUDE.md corrected. Meadow scope still human choice. No gameplay edits/commit.

# Demo M0 foundations — Claude, 2026-09-25 (uncommitted, for Astra review)

Owner: Claude (human assigned M0 + M1). Branch `dev`. No commit.
Astra's `DEMO_PLAN_REVIEW.md` corrections applied to DEMO_PLAN.md and
OOT_PROGRESSION_PLAN.md: no child Mido gate in Lost Woods (meadow scope is an
open human decision), save versioning moved into M0, M1 collision contract,
wall-type mapping, water boxes and dependency honesty added to M1.

Changed:
- Face-only textures: `character_textures.keep_texture()` = face_detail only;
  hair flat. Link 179 -> 143 tiles (13,400 B). Bible + budget doc updated.
- Asset names base-36 (0-9, A-Z): `tools/asset_names.py`, `src/asset_names.h`;
  used by room/scene/backdrop/opening/cutscene/flat builders and by
  `kokiri_sgl.c` / `scene_flow.c` loaders (cap 36). Opening cache index guarded
  to room < 10.
- Save v2: SAVE_SCENE_COUNT 6 -> 11 (Know-It-All, Twins, Mido, Saria homes,
  Hyrule Field; existing ids kept). Payload 210 -> 290. `validate()` checks
  header before size, so a v1 block reports "OLDER SAVE - CANNOT READ"
  (erasable), not "unreadable".
- `src/actor_sys.c/.h`: 64-slot pool, OoT category update order, deferred
  kill, room/scene unload, persistent flag, attention search, per-scene flag
  hooks. Storage is a fixed 8 KB carve at the top of cart bank 2
  (`ram_cart_fixed`, zone shortened by 16 KB), not work RAM. Init in main.
- `src/collide.c/.h`: cylinder + capsule, AT/AC alignment and DMG bits,
  DamageTable by highest DMG bit (CollisionCheck_ApplyDamage), defense path,
  invincibility, OC mass push-out (CollisionCheck_SetOCvsOC). Not wired to
  gameplay yet. No world collision here (M1 contract).
- SFX banks: core ACTIONS.PCM (33,934 B) + area slot 6,002 B at
  SFX_AREA_BASE. Bank 1 `SFXFRST.PCM` (grass cut, 3,310 B) for Kokiri Forest;
  bank 0 for interiors. `scene_entry_t.sfx_bank`, `action_audio_set_area()`
  from `scene_flow_load`; opening bank still replaces the region and the area
  reloads after. The old "104 B spare" note was stale: 2,692 B spare today.
- Makefile malloc arena 57,344 -> 53,248 (M0 code crossed SGL boundary by
  928 B). Known arena demand ~32 KB.
- Stale tests fixed: swing voice octave 13 (half-rate voices), gameplay save
  size 300.

Verification:
- Host: new test_actor_sys (17), test_asset_names (5), save v2 + highest
  scene round trip + v1 reject; module-by-module all pass except pre-existing
  setUpClass compile errors in test_equipment_draw, test_forest_partition,
  test_opening_audio (untouched harness code). A full `discover` run
  segfaults the Python process; per-module runs do not. Not investigated.
- Build: normal/hires/clean all build; SGL boundary 3,168 / 11,040 / 13,952 B.
  Forest room VRAM spare 4,896 / 4,768 B.
- Kronos: NOT run (would take focus). Needs: boot to title (cart carve +
  actor pool init), new file, grass cut sound outdoors, Link hair flat,
  old v1 save shows OLDER SAVE.

Remaining: M1 not started. Actor pool/collide unused by gameplay until M1/M2.
Input doc mismatch to confirm with human: CLAUDE.md says Z+D-pad look,
`player_input.c` gates look on L and targeting on Z.

# Public demo plan approved - 2026-09-25

Human approved [DEMO_PLAN.md](DEMO_PLAN.md): full opening -> Kokiri Forest with
all homes/shop/NPCs -> sword/shield/Mido -> Deku Tree + Gohma -> Emerald ->
Lost Woods (all 10 rooms, access gates 1:1 with source) -> Saria bridge ocarina
-> Hyrule Field (explore, owl, music, ocarina free play). Extras in scope:
grottos, gold skulltula tokens, Deku scrub shops, Lost Woods owls. Target:
emulators with 4 MB cart. Characters: NO texture except face (hair goes flat).
Milestone owners are assigned by the human in the DEMO_PLAN table. Planning
only; no code changed.

# Fairy sound, wake camera and flight streaming correction — 2026-09-22

Supersedes the earlier claims below that forest flight has no fairy SFX.
`ObjectKankyo_Fairies` plays NAVY_FLY only in Kokiri scene layer 7. En_Elf
does not own that loop. Gameplay now has catch-up dash cues only, no flight
loop and no invented door/spawn dash. Hat/attention states remain pending.

The loop uses instrument 69's WAV sustain loop, CHAN_2582's A4-to-D5 bend,
and ENVELOPE_67D8. Camera travel changes frequency through func_800F436C;
it does not change volume. Missing squared note velocity 50/127 caused the
excessive loudness: restored (50/127)^2, about -16 dB. Dash now retains its
sustain/bend and applies velocity (65/127)^2 as well. SCSP mixing and absent
N64 reverb remain approximations; do not claim identical audible balance.

Wake-up's second camera ended at frame 221, exposing the older door track
underneath. The baker now holds the newest shot until the next shot. Regression
covers frames 70–647; isolated Kronos screenshot at frame 624 shows Link/Navi.

Flight banks preload once into the 4 MB cart. Identical texture tiles share
NAVIPOOL.TEX; S2R*.MAP records retain original per-bank VRAM placement. Cache
is 1,450,208 bytes versus 2,443,804 for raw mesh/textures. All 5,617 tile
references reconstruct original banks byte-for-byte. Swaps perform RAM-to-VRAM
copies without asset_loading/slSynch/CD reads; raw-cache OOM was fixed.

Verification: 31 cutscene tests pass. Isolated replay passed forest flight into
wake-up. OpenAL WAV capture of the quieter loop mix has no clipped samples in
the 30–42 second excerpt (peak 12580/32768, RMS -25.1 dBFS). This checks actual
emulator output, not a human listening comparison. Capture predates the final
dash gain reduction; human timbre/balance check still needed. Normal and clean
images build; SGL gaps are 2,160 / 12,928 bytes. Changed audio/Navi/cutscene
objects contain no software-float helper references. No commit.

# Astra review round 1 fixed - 2026-09-22

- P2, Navi too high: demo.c was handing over `demo_link.y`, the CAMERA EYE at
  floor+90, so she sat about 40 units over Link's head. All three call sites now
  pass his FEET and navi.c adds `LINK_HEAD` (45) + the source's 12 rise.
  45 is measured, not guessed: posing the idle frame's skeleton puts limb 10,
  the head joint, 4291 model units up, which is 45 world units at
  LINK_ANIM_SCALE_Q16 with LINK_ANIM_SHIFT_Y. The catch-up distance measures to
  the head too, as the source measures to the hat.
  `test_navi.test_head_anchor_matches_the_posed_model` re-derives that number
  from the generated clip data so it cannot drift, and
  `test_spawns_beside_links_head` checks the real spawn coordinates land inside
  the model's own 66-unit height.
- Minor, orbit order: `navi_orbit()` in cutscene.c already matched
  func_80A02A20, but navi.c advanced the angles before sampling them. It now
  builds the offset from the current angles and advances afterwards.

510 host tests run, same two pre-existing setUpClass failures. Normal image
rebuilt clean. Still unconfirmed in Kronos.

# Navi companion and her cutscene flight sounds - done 2026-09-22

Claude implemented the plan above. What changed:

- `src/navi.c` / `navi.h`: Navi as Link's own actor, from En_Elf's idle follow
  (state 1): the 7.5 x 5 orbit above his head, approached by func_80A03148's
  fifth-of-the-gap velocity with the 5.0 / 32.0 easing rates and the 20-unit
  vertical cap, all in Q8 integers. En_Elf updates at 20 Hz and the world steps
  at 30 Hz, so navi_step() runs the source update on two ticks of every three
  instead of rescaling the source constants.
- She is snapped beside Link by `navi_reset()` in demo.c's `place_at_spawn()`
  and the fallback spawn, so she is THERE on the first controllable frame --
  after the opening, after a load, and on the far side of every door -- rather
  than flying in. There is one of her: the cutscene keeps using channel 8 and
  the Kokiri fairies are still the NPC markers.
- `kokiri_navi_draw()` puts the existing FAIRY.RGB billboard where she is,
  drawn with Link and only with him (not the title, not the file select).
- Source catch-up: past 100 units she dashes at the source's higher cap until
  she is back within 30. `navi_dash_started()` reports the frame the source
  plays NA_SE_EV_FAIRY_DASH on.

Cutscene sound, checked against `ovl_En_Elf/z_en_elf.c`:

- The ONLY fairy sounds in the whole opening are NA_SE_EV_FAIRY_DASH at frame
  55 and again on each downward turn while she wakes Link (the LINKS_HOUSE
  layer-4 branch of func_80A03CF8). The Kokiri forest flight has no fairy SFX
  at all -- its audio is NA_BGM_NAVI_OPENING, which is already cued. There is
  no flight loop in the source and none was invented.
- The wake-up repeat was silent before this change: cue id 3 holds ONE position
  from frame 250 to 350, so nothing ever turned downward. En_Elf's own hover
  (func_80A02A20) is what moves her there. `navi_orbit()` in cutscene.c now
  adds that orbit, with the per-cue state func_80A0461C picks (4 -> 9, 3 -> 6,
  1 -> 10), so she circles and bobs as in the original AND the existing
  downward-turn dash cue fires about every 16 frames, which is the source rate.

Still missing, recorded rather than faked:

- Gameplay NA_SE_EV_FAIRY_DASH has NO sample. The resident action bank ends at
  484352+39832 with 104 bytes to spare under the 512 KiB sound RAM limit, so a
  new sample cannot be added without a bank budget change. `navi_dash_started()`
  exists so the cue can be played the moment there is room.
- NA_SE_EV_NAVY_VANISH / NA_SE_VO_NAVY_HELLO, the "Hey! Listen" prompt, the
  fly-into-the-hat states (7/8/11) and the sparkle trail. POI targeting was
  already out of scope for this handoff.

Verified: normal image builds clean; 509 host tests run, the only failures the
two pre-existing setUpClass compile errors (`test_equipment_draw`,
`test_forest_partition`) that also fail on the parent commit. New coverage:
`tests/test_navi.py` runs the real follow code on the host, and
`test_cutscene_parity` now compiles navi_orbit() and checks she bobs during the
wake-up cue. NOT yet confirmed in Kronos: the dash cue's audibility over the
music, and how she looks beside Link in play. Codex's frame-99 bank-wait fix and
the hair/face texture policy are untouched.

# Navi story audio and gameplay companion - next task, 2026-09-22

Claude: user requests fairy flight sound across the opening shots and Navi
present when gameplay starts. Short implementation plan:

1. Check OoT `ovl_En_Elf/z_en_elf.c` and opening actor cues for the original
   flight/dash sounds and timing. `cutscene.c::step_sounds()` currently plays
   `OPENING_DASH` during wake-up only; extend the Navi-flight scene with the
   source cues. Reuse the existing sample where correct, extract missing ones
   through `build_opening_audio.py`; do not invent a constant buzzing loop.
2. Trigger once per cue, preserve pauses/camera cuts, and stop any sustained
   sound on scene exit. Verify audibility against music without retriggering
   every held text frame. Keep effects separate from music fades.
3. Add one gameplay Navi companion on opening completion and appropriate save
   loads. Reuse `FAIRY.RGB`; current cutscene channel 8 and NPC fairies are not
   Link's persistent companion. Follow/orbit Link using source En_Elf behavior
   and integer math, and retain her through room/interior transitions. Avoid
   duplicate Navi when switching between cutscene and gameplay ownership.
4. Verify with sound in Kronos: forest flight, wake-up, first controllable frame,
   walking, room transition and save reload. Navi must be present immediately
   at gameplay handoff. Record source behavior still missing; POI targeting is
   a separate later slice task, not required to finish this companion handoff.

Preserve Codex's uncommitted frame-99 bank-wait fix; see
`game/docs/FRAME99_BANK_WAIT.md`. Do not undo the hair/face-only texture policy.

# Control remap and manual roll - 2026-09-22 (branch feature/kokiri-slice-actions)

Kokiri slice plan step 2 started. THIS SUPERSEDES the 2026-09-18 mapping below:

- **Z** is the target button (hold to lock, tap to recenter). It NO LONGER
  looks, and it no longer consumes the D-pad: holding it strafes.
- **L** is the look camera (hold L + D-pad), taking over the old Z behaviour.
- **A** rolls when no talk, prompt, pickup, menu or equip claimed the press.
  Roll speed follows the source formula (z_player.c:9754): 1.5x what locomotion
  would give, floored at a third of a run, eased down to that floor when the
  pad stops asking forward. It does not decay to a stop; the roll ends with the
  clip. Travel goes through `kokiri_camera_move_heading()` and collision, so
  the clips stay pose-only. A text box, the menu, a swing or a raised shield
  CANCELS a roll in progress (`link_anim_cancel_roll`), not just its start.
- Holding Z with nothing locked holds Link's facing, so the D-pad strafes and
  backs up, which is the source behaviour with no target in range.
- The diagnostics chord now needs a direction: **L+R+Down** toggles the panel,
  **L+R+Up** swaps cameras. Plain L+R is look-while-guarding and is left alone.

Verified: 485 host tests run, all pass except two pre-existing setUpClass
compile failures (`test_equipment_draw`, `test_forest_partition`) that also
fail on the parent commit. Normal image builds clean. NOT yet confirmed in
Kronos: the feel of Z strafing and the roll distance need a play check.

Still missing from plan step 2: turn-in-place, ledge grab/climb, ladder,
crawlspace, sidehop/backflip/jump slash, damage knockback, and the roll's
wall-impact bonk (source reverses speed and plays hip_down).

Astra review round 1 fixed: roll travel during talk/attack/shield (now
cancelled), non-source linear decay (now the source target/floor model), and
the in-game controls panel in main.c, which still named the old L/Z layout.

Astra review round 2 fixed: the roll target is recomputed every step from the
CURRENT locomotion input (`link_anim_roll_input`) and approached in both
directions, so pressing forward again after letting go brings the speed back;
and "forward" is now the real source test -- `kokiri_camera_input_heading()`
gives the heading the D-pad asks for and demo.c compares it with Link's yaw,
within the source's 45-degree quadrant. Sideways and backward input drop the
roll to the floor speed.

# Opening follow-up - 2026-09-22

User then said "It fine.. just show VRAM and CPU % on bottom"; active work
switched to that overlay. Normal and clean builds now show a bottom line in
menus, cutscenes and gameplay. VRAM is allocated VDP1 bytes including reserved
tables / 512 KiB. CPU~ is smoothed master callback time / (callback + sync),
an estimate, not combined dual-SH2 utilization. Both player images rebuilt.

LATEST: user reports another pre-Ganon failure with a vertically striped screen.
Still unresolved. No failing process remained to inspect. Full-start diagnostic
(sleep through nightmare, automatic confirm) passed into scene 2; this does not
prove the user failure fixed. Need actual launcher/image and live failure state.
See the unresolved-report section in OPENING_FREEZE_2026-09-22.md first.

Nightmare freeze reproduced and traced to Kronos's 2048-command cap, not a
proven texture-swap failure. Local rebuilt emulator passed into scene 2; launcher
config selects it. See OPENING_FREEZE_2026-09-22.md for evidence and rebuild.
Rain geometry also needed static storage for SGL's deferred slave reads.

Removed the extra `80 + page_length` post-reveal hold; FADE uses source delay.
Music remains silent before the source Ganon cue at frame 330. Busy transitions
retain pending music cues. Music fades now attenuate slots 0..23, leaving SFX
audible when music is silent instead of muting SCSP master volume.

New OPENING.PCM swaps into the reserved action tail during the opening and
restores ACTIONS.PCM before gameplay. Nine source-derived effects cover shot
cuts, lightning, bridge movement/stop, hooves, neigh/dust, rain and Navi's wake-up
dash. PCM8 5512.5 Hz, 32,836 bytes; reduced layers/envelopes, no reverb or pitch
slides. No claim of full original SFX parity. Source frame holds cannot repeat
one-shots. Looping voices stop at scene transitions.

Nightmare Link now uses source 0.01 scale/origin rather than gameplay's enlarged,
grounded model. The bridge fly-by also gets a local smooth side arc during
frames 140..219 to keep the Saturn near plane out of his head, blending the
look target toward him so he stays in frame. Other shots remain source splines.
Work-RAM arena reduced to 56 KiB; expansion cart
still supplies large allocations. `core.o` now depends on makefile so an arena
size change cannot silently retain the old allocation.

Validation: 86 focused tests passed (37 cutscene, 28 message, 16 audio,
5 opening scenery). Normal and clean discs build; SGL boundary checks leave
8,544 / 19,248 bytes respectively. SH-2 disassembly has no float helpers in
the changed cutscene, music, action-audio, rain and Link draw paths; Link yaw
now calls slRotY directly instead of converting through floating-point degrees.
Sound replay reached scene 2 frame 99. Final camera still at frame 185 shows
Link from the side without face clipping (`build/nightmare-final-185.png`).
The final unpaused camera/audio build also passed the complete nightmare into
scene 2 frame 60 (`build/nightmare-final-replay.png`); diagnostic process closed.
Read-only emulator inspection confirms OPENING.PCM resident byte-for-byte,
active rain/hoof slots and master volume 15 while music is silent. The audible
mix and complete opening through gameplay have not been manually checked.

The user's later frame-185 freeze screenshot matched our intentionally held
camera diagnostic, not the earlier 2048-command deadlock. Held tests now display
CAMERA TEST HOLD explicitly; the final diagnostic and both player discs have
no frame hold. Do not leave a held diagnostic running for the user.

---

# Opening fixes after checkpoint - 2026-09-22

Work remains on the existing `feature/new-game-cutscene` branch. Opening fixes:
unread text survives the next NONE cue; fade pages wait until reveal completes;
the panel uses correct independent X/Y scaling, near-plane-safe sprite depth,
charcoal dither, bright cyan dialogue and 8-pixel advance/end marks.

The disappearing Deku Tree also had a separate cause: CS_TRANS_TRIGGER_INSTANCE
was mapped to an opaque black fill. It now leaves fill alpha unchanged, matching
z_demo.c. Compiled tests cover the real text boundary and the source fade timeline.

`build_opening_banks.py` derives S2R0..9 from the ordinary streamed forest meshes,
100 camera frames per bank. It retains source hut/tree geometry, drops textures
that cannot enter fog view during the span, and keeps distant visible faces flat.
Runtime toggles eligible faces to flat beyond fog range; unused span textures are
still resident until the next bank. CD load time is excluded from catch-up ticks.
S4R0 is the original four CI8 house panorama images (`vr_LHVR_static`), not new
furniture geometry; ordinary house gameplay still uses the fixed JPEG.

Checks: 72 focused tests passed; Kronos house doorway/Navi and sleeping Link
captured with REJ 0. The later colour/panel adjustment and full forest flight need
a player check; later background boots reached BIOS setup. Final disc is rebuilt
without CUTSCENE_PROBE. See VSLICEPROGRESS.md for budgets and exact limits.
Final normal build exited 0: 2,768 bytes below the SGL work area. All staged
mesh banks fit compiled capacities; changed scene/UI draw functions have no
software-float helper references in SH-2 disassembly.

---

# Cutscene checkpoint - 2026-09-22

User directive: stop expanding performance/detail work; checkpoint and push everything.
Keep these cutscene development HUD rows permanently during development:
`SCENE # FRAME # FADE #` and `ACT # X # Z # REJ #`.
They must not depend on CUTSCENE_PROBE. Show actual asset names during loading,
including ordinary builds, so a synchronous CD load is visibly progressing.

Checkpoint includes original young Ganondorf, Zelda, Impa, separate animated
horses, bridge/chains, source-order cue latching, camera roll/FOV fixes, native
Link clip timing and wait loops, rain/Navi, and Ganon's score with percussion.
Actor assets stay in the RAM cart; only visible actors occupy the transient
VDP1 bank. Horse vertices share only the same source Skin blend or rigid
limb/local position; every baked pose validates that sharing preserves motion.
The previous Kronos close-up at frame 400 showed textured Ganondorf with REJ 0.
Latest horse deduplication and always-visible debug/loading text follow that capture.
Normal player-disc build passed with 3,328 bytes below the SGL work area.
480 host tests completed: pass, with one skipped. No auto-start/freeze probe
is enabled in the final local disc. Logs: build/checkpoint-build.log and
build/checkpoint-tests.log (ignored build artifacts).

This is a checkpoint, not a claim of perfect N64 parity. Field art is still
flat authored geometry; clouds, cape, ocarina, torch/lightning/rain-ring effects,
original SFX, precise fades/lighting and full Link root/morph behavior remain.
Link's complete clips use interpolated samples. Navi still uses a billboard.
No change to user controls; no foreground input or desktop capture used.

---

# Phase 0 build verification (Astra, 2026-09-21)

## Build steps for Claude

Run from the repository root in **PowerShell**:

```powershell
$env:OS = 'Windows_NT'
.\game\build.bat
```

The SDK uses `OS=Windows_NT` to select its Windows SH-2 compiler. An empty
`OS` selects the Linux compiler and fails. `build.bat` calls the PowerShell
wrapper, which runs MSYS2 Bash and `build.sh`; MSYS2 is still required.
For hi-res, use `.\game\build.bat -Variant hires`.

If MSYS2 fails with `couldn't create signal pipe, Win32 error 5`, retry the
same command through the agent's approved outside-sandbox execution mechanism.
That error occurred before compilation in Astra's sandbox; the approved retry
succeeded. It does not require switching compilers or editing build scripts.

The build runs `build_sgl_area.py --verify --map` after linking. Check the final
boundary result and process exit code, not the preliminary boundary printed
before compilation. Normal outputs: `game/build/game.iso` and
`game/build/game.cue`. Launch with `game/run-kronos.bat` when runtime testing.

## Verified result

Claude: `game\build.bat` from PowerShell succeeded (exit 0), using the Windows
Jo SH-2 compiler. Backup and cart objects linked; normal `game.iso` / `game.cue`
rebuilt. Final `build_sgl_area.py --verify --map build/game.map` passed:
`.bss` ends at `0x060ac830`, SGL starts at `0x060b2640`, gap **24,080 bytes**.
MSYS2 needed execution outside the sandbox because signal-pipe creation was
denied inside it. No build-script or gameplay-source changes made by Astra.
Dialogue left untouched. Kronos cart/no-cart boot behavior remains untested;
Phase 0 is not yet runtime-verified.

VRAM clarification: 173,104 bytes spare was one room's intermediate budget,
not a whole-game minimum. The build also reports room budgets with only 4,944
and 5,744 bytes spare before the later Link conversion. Do not plan new assets
against 173 KB of guaranteed headroom. Sound report remains 104 bytes spare.

# Current work plan: OoT progression (approved 2026-09-21)

Read [OOT_PROGRESSION_PLAN.md](OOT_PROGRESSION_PLAN.md) before starting gameplay
work. Human approved a much larger scope than the old slice: real game state and
quest flags, Saturn backup-RAM saves with file select, Kokiri Forest + Lost Woods
+ Great Deku Tree + Gohma through to the Kokiri Emerald, full cutscene playback,
real ROM models for NPCs and enemies, and hearts/damage/death.

**The game now REQUIRES the 4 MB RAM expansion cart.** Kronos needs
`Cartridge/Type = 7`. Note that Jo only registers the first 2 MB of it.

That plan supersedes `GAMEPLAY_NEXT_STEP.md` and the "no bosses, dungeons" line
in `VERTICALSLICE.md`. Nothing in it is implemented yet; Phase 0 is the start.

Known bug it fixes first: `tools/build_dialogue.py` hardcodes Mido to text
`0x1045` (post-Kokiri-Emerald) and Saria to `0x1002`. Correct no-flag baselines
are `0x102F` and `0x1001`. The En_Ko child ids are already correct.

## Phase 0 done, Phase 1 started (Claude, 2026-09-21)

Phase 0 landed. Astra confirmed the normal build links and the boundary check
passes with the backup module compiled in: **24,080 bytes gap, `.bss` ends
`0x060ac830`**. Kronos boot still untested by either of us.

Corrected budget note, from Astra: VDP1 spare VRAM is **per resident room and
very uneven** — the roomiest room reports ~173 KB spare, the tightest only
**~5 KB**. Plan new textures against the worst room. The plan doc's budget
table has been fixed; my earlier ~173 KB figure was the wrong room.

Phase 1 in progress. New `src/save_state.c/.h`: platform-free persistent quest
state — `event_chk_inf`/`inf_table`/`item_get_inf` with the original
`flag >> 4` / `1 << (flag & 15)` addressing, per-scene chest/switch/clear/
collect words, quest items, hearts in OoT's 0x10-per-heart units, owned-vs-
equipped gear, and `save_new_game()` mirroring `Sram_InitNewSave` (three
hearts). Added to `SRCS`, so **the image needs rebuilding again**.

`save_mido_demands_met()` deliberately tests the *equipped* values, because
`z_en_md.c:437` uses `CUR_EQUIP_VALUE`, not `ALL_EQUIP_VALUE`.

19 new host tests in `tests/test_save_state.py`, including a full Kokiri →
Kokiri Emerald flag-chain replay. Suite now **298 tests, 297 pass, 1 legacy
skip** (was 279). Nothing existing changed behaviour.

### Dialogue bug fixed at the source (Claude, 2026-09-21)

Thanks for the build instructions — `$env:OS = 'Windows_NT'` then
`.\game\build.bat` works for me now, so I can build and verify myself.

`build_dialogue.py` is rewritten. It no longer takes one constant per speaker;
it parses each text-id function's **whole guarded-return ladder** and emits it
as an ordered rule list, which the runtime evaluates against `save_state`. The
runtime takes the first rule whose conditions all hold — which is exactly what
a ladder of early returns does, so no condition ever needs negating and a
later-quest line can never win on a fresh file.

Supported guard shapes: `GET_EVENTCHKINF`, `GET_INFTABLE`, `GET_ITEMGETINF`,
`CHECK_QUEST_ITEM`, `CUR_EQUIP_VALUE(t) == v`, `!` negation, `&&` conjunction,
ternary returns, and nested if/else. Flag numbers are resolved from
`include/save.h` and `include/item.h`, never typed in. **Any shape the parser
does not recognise is a hard build failure** — a silently dropped guard is
precisely how the original bug happened, so it must not be possible to ship one.
`--verify` prints the per-speaker fresh-file text id.

Result, straight from the build log: **Mido 0x102F** (was 0x1045) and
**Saria 0x1001** (was 0x1002). The eleven child ids are unchanged, and the
parser additionally found `ENKO_TYPE_CHILD_11` (0x103E), which the old
hardcoded table did not have. `ENKO_TYPE_CHILD_FADO` is reported as ignored
(it belongs to another scene) rather than guessed at.

Tables grew from 13 conversations / 78 lines to 14 speakers / 45 rules /
35 conditions / 79 pages / **191 lines** — all original US 1.2 script, every
quest variant now present.

Runtime: `gameplay.convo` became `gameplay.rule` (a `dialogue_rules` index, not
a conversation index), with `rule_for()` + `cond_holds()` in `gameplay.c`.
`sync_gear_to_save()` mirrors the session's GP_SWORD/GP_SHIELD bits into the
save's equip values, because Mido's gate reads `save_cur_equip_value()` — gear
the player holds but the save has not been told about would leave him blocking
the path forever. Called on pickup, on menu equip, and on `gameplay_reset()`.

Tests: **305 total, 304 pass, 1 legacy skip.** Seven new dialogue regression
tests assert Mido's fresh-file line, Saria's, the refused-once line, that the
0x1033 gate line needs gear *equipped* rather than merely owned, that the
post-Emerald line appears only with the Emerald, that an earlier rule beats a
later one when both guards hold, and that one speaker's flag does not move
another's line.

Writing those tests surfaced a real gap: nothing reset persistent state between
tests, so flags leaked. That is the persistence working as intended —
`gameplay_reset()` deliberately does not clear the save. Test `setUp` now calls
`save_new_game()` as well.

### Rebuild button in the launcher, and the OS fix (Claude, 2026-09-21)

Human directive: stop rebuilding from the agent side every change; they will
build. `launch-game.bat` now has a **Rebuild...** button beside Run selected.
It opens a dialog with a tickbox per image (the one selected in the list starts
ticked, plus "All three"/"None"), streams the build log live, and reports each
image as OK or FAILED. Close is disabled while a build runs, because closing
mid-build would orphan the compiler and leave a half-written image. New file:
`tools/launcher/build-dialog.ps1`.

**`$env:OS` is fixed centrally**, in `tools/launcher/build-game.ps1`. The SDK
makefile picks its SH-2 compiler on `$(OS)`; an empty value selects the Linux
toolchain and dies with "Exec format error". MSYS2 does not reliably pass it
through, so the wrapper now sets it explicitly. Verified by building with
`$env:OS = ''` first: exit 0. So `game\build.bat`, the Rebuild button and a
plain terminal build all work with no environment setup — the
`$env:OS = 'Windows_NT'` line in the earlier instructions above is no longer
needed (harmless if kept).

`kronos-launcher.ps1 -SmokeTest` constructs the new dialog without starting a
compiler and still passes.

Two bugs found by the human running it, both fixed:

1. **A good build reported FAILED.** A `Process` from `Start-Process -PassThru`
   has no populated `ExitCode` until the handle is waited on, even once
   `HasExited` is true -- it reads `$null`, which compares unequal to 0. The
   dialog now calls `WaitForExit()`/`Refresh()` first (immediate, since it has
   already exited) and reports an unreadable status distinctly rather than
   guessing either way. Verified: `ExitCode` is `0` after the wait.
2. **The log was unreadable.** The build prints one ~1200-character compiler
   invocation per source file. The dialog now filters by default via
   `Test-BuildLogLine` -- a top-level function so it can be tested rather than
   eyeballed -- keeping every summary, warning, error, both boundary checks and
   the final image path, and dropping only the compiler command lines, the SDK
   makefile's recipe-override chatter and Pillow deprecation warnings. A real
   166-line log filters to 113 useful lines. "Show full log" restores the raw
   text, which is kept in full. The smoke test asserts a sample of lines that
   must be kept and must be dropped.

### Standing rule: rebuild all three discs every time

Human directive, 2026-09-21: normal, clean player test and hi-res all get
rebuilt on every change, not just the normal image. A stale clean or hi-res
disc silently tests old code, and the clean disc is the player-test one.

```powershell
$env:OS = 'Windows_NT'
.\game\build.bat                    # normal -> game.iso
.\game\build.bat -Variant clean     # clean player test -> game-clean.iso
.\game\build.bat -Variant hires     # 320x480i -> game-hires.iso
```

All three verified by me after the dialogue change, exit 0, final boundary gaps:
normal **18,176**, clean **20,912**, hi-res **17,952** bytes below the work
area. (Dialogue text cost about 4.4 KB of the earlier 22,576.) Read the boundary
line printed *after* linking, not the preliminary one.

**Known limitation, not hidden:** `gameplay_reset()` currently clears saved gear
too, which is right only while the two authored ground pickups are the sole
source and reset means "entering the world". Phase 3 scene transitions must make
gear survive a transition; the commented line in `gameplay_reset()` is what has
to change. Also still open: Kronos boot with and without the cart, which neither
of us has run.

# Latest: behind-Link lock camera, rupee melody, pause help

Lock-on previously changed only Link facing; normal camera could remain at old
yaw while idle. Added explicit target camera state: ease behind Link on acquire,
then follow his target-facing yaw every fixed step, including idle, strafe and
backward travel. Refresh facing from post-movement position before camera update.
Release resumes normal follow; look offsets are cleared/suppressed during lock.
Source reviewed: Player_UpdateZTargeting, Camera_KeepOn1 and Camera_Parallel1.
This is requested behind-Link behavior, not full KeepOn1 two-actor framing,
collision/occlusion, target selection, or Hold/Switch parity. Those remain gaps.

Rupee sound was only LAYER_587A sample/noise bed: the recognizable melody was
missing. Added LAYER_5868: source sawtooth, transpose +24, BF4/F4/BF4 for 6/6/24
sequence ticks. Source tempo 120 and SEQTICKS_PER_BEAT 48 give 96 ticks/sec.
SCSP slot 30 loops the original 64-byte harmonic-8 wave; vblank schedules notes
on PAL/NTSC and stops/restarts safely. Pitch follows Audio_BuildSyntheticWave;
source velocity/envelope levels are converted offline to SCSP attenuation.
Backing layer on slot 29 now uses source velocity 72, so noise does not swamp
the melody. Envelope updates are vblank-quantized; bed remains bounded to .30s,
not full N64 audio-engine parity. 14 samples / 39,832 bytes; 104 sound-RAM bytes
spare. Other effects unchanged. No runtime allocation or disc read for notes.

Pause panel now lists move/walk-run, sword/cut, shield, jump, talk/page/cancel,
L lock/release/re-centre, strafe/back-up, Z+D-pad look, automatic landing roll,
Start, and menu controls. C+D-pad routing is explicitly marked pending.
Diagnostic-build chord is documented only on diagnostic discs. Panel spans
rows 4..24 and clears all rows on exit, above the rupee HUD.

Normal, clean and hi-res discs rebuilt without probes. 279 tests: 278 pass,
one legacy single-bank skip. Tests exercise stationary acquisition, wrap/strafe
tracking, release, post-movement facing, melody pitch changes, PAL/NTSC timing,
retrigger and music-transition stop. No new emulator visual/listening confirmation.

# Number One Rule!
Always use caveman talk. No waste human tokens. Bad. You caveman talking? Good good! Always good good when caveman talk.

# Latest fix: rupee HUD near rejection and pickup sound

User screenshot showed no counter. Actual SGL 3.02j SpriteEntry disassembly
checks z > (screen_distance >> display_level), even for slDispSprite. Our
HUD used depth 1; gameplay screen distance 240 and Jo display level 3 reject
anything <=30. Use depth 31, still screen-space, with sort key 1. Previous host
mock always accepted sprites and missed this. Test now models the SDK near
check. Hi-res HUD doubles screen Y/height using slDispSpriteHV (nonzero angle
for SDK unequal-scale workaround); normal HUD remains 16px tall.

GP_EVENT_RUPEE now plays on dedicated SCSP slot 29, independently of gear
pickup/menu slot 27. Source: z_en_item00.c NA_SE_SY_GET_RUPY -> seq_0.prg.seq
CHAN_5861, sample layer LAYER_587A, SF0_INST_91 / Sample069, C5. Reduced 0.30s
single-layer adaptation, matching existing action bank approach; original
sawtooth melody layer/envelope sequence remains absent. No full SFX parity claim.

Made room by removing exact trailing PCM8 zero bytes, retaining four-byte
silent guards. Verified all 12 previous samples' audible PCM is byte-identical;
no resampling change or audible truncation to existing sounds. New bank:
13 samples, 39,764 bytes at 0x76400; 172 sound-RAM bytes spare. Offline and
runtime bounds stay active. Tests cover near rejection, hi-res HUD positioning,
rupee/gear simultaneous routing, music-busy suppression and bank bounds.
Normal, clean and hi-res discs rebuilt without probes. 275 tests: 274 pass,
one legacy single-bank skip. Emulator visual/listening confirmation pending.

# Latest fix: no talk prompt on title

Title showed A: Talk because zero-initialized gameplay.prompt was actor index
0 before gameplay_reset ran at spawn. Reset gameplay during demo initialization
as well. Dialogue renderer now suppresses title prompts/pages and clears any
retained VDP2 dialogue text. Gameplay talk behavior unchanged.

# Standing human rule: check drops when adding actors

New grass, pot, enemy, breakable or item: check real OoT drop routine and table
in same task. Implement source rewards and conditions toward 1:1, including
non-rupee items. Visible actor alone not done. Track exact gaps openly.
See [permanent drop rules](../../DOSEI-LEGEND-BIBLE.md#new-gameplay-actors-check-original-drops-every-time).
Current grass non-rupee drops remain pending; previous rupee subset not parity.

# Latest: rupees in world and cut grass

Eight rupees now come from original US 1.2 En_Item00 room records: four green,
four blue. Keep original X/Z, room and params; settle Y on collision floor.
Two overlap existing sword/shield pickup spots. Both items remain collectible.

Grass now rolls original sItemDropIds slots selected by EnKusa spawn params.
Forest table 2 gives green on 2/16 slots; type-1 grass gives no rupees; the
room-2 type-0 tuft falls back to table 0. Only rupee drops implemented: hearts,
ammo, magic and FLEXIBLE slots stay empty. Slice RNG varies with gameplay
steps; not original global RNG. Each tuft rolls once when cut. Drop hops for
15 steps before pickup, remains until collected, and cannot respawn from
another swing. Pause/dialogue freeze drops. Wallet/flags last this session;
reset clears them. Child wallet cap 99, green +1, blue +5.

World sprites reuse original gRupeeCounterIconTex silhouette: original green
HUD tint, slice blue recolour. Original gCounterDigit0..9 textures make the
screen counter at source coordinates (26/42/50,206). slDispSprite keeps HUD
independent of camera. Counter hidden on title/dialogue; action hint moved
one text row lower. Added 3,584 texture bytes, included in budget guard.

Both player discs rebuilt without probes. 273 tests: 272 pass, one legacy
single-bank suite skip; room-bank policy tests still run. Host tests cover
source placements/drop odds, room/range/height gates, one-shot collection,
wallet cap, delayed drops, pause/reset and world/HUD sprite submissions.
No new emulator visual confirmation. No rupee sound added; existing action
sound bank still has only 768 bytes free.

# Latest: visible grass and movement sounds

Astra: cuttable grass had state but no draw call. Added 32x32 RGB555 VDP1
billboards from original gFieldBushTex (En_Kusa type 0). Render at original
actor positions, 48x40 world units, base on ground; room/distance cull and omit
cut tufts. One shared 2,048-byte texture, counted in offline/runtime VRAM budget.

Successful collision jump now plays real child auto-jump voice (EFFECT_53).
Walking/running footstep events follow half-cycle/frame-wrap crossings only
while actually moving; one grass footstep sound for this forest baseline, no
surface-material detection yet. Roll follows sRollAnimSfxList: child attack
voice at frame 1, body sound at frame 6. No extra roll control introduced.
Menu/combat suppress locomotion sound; rejected jumps remain silent.

Action bank now 12 samples / 39,168 bytes at 0x76400. Largest existing music
bank ends at 484178, below new reserved tail; neither music bank resampled.
768 sound-RAM bytes remain. Movement effects use slot 28; voice uses 25.
Existing single-layer adaptation limits still apply. Both player discs rebuilt
without probes. 264 tests: 263 pass, one legacy table suite skips. Final tests
run after asset builds finish; concurrent asset regeneration caused an earlier
room-manifest mismatch, not a guard relaxation. No new emulator visual/audio
confirmation this pass.

# Earlier: equipped hand geometry and action audio

Astra: equipped Kokiri sword now uses gLinkChildLeftFistAndKokiriSwordFarDL
on zero-based limb 15. Equipped Deku shield uses
gLinkChildRightFistAndDekuShieldFarDL on limb 18. Empty sheath uses limb 19.
Missing gear uses empty fists; old back-mounted sword/shield removed. Baseline
keeps equipped gear in hands during idle/movement as well as combat. Draw/sheath
transitions and the full OoT model-group state machine are not implemented.

Importer reads symbols from object_link_child.xml, verifies player source
references, preserves original Flex matrix slots and per-vertex ownership.
Equipment ranges share one POINT table. Cached selected polygon/attribute pairs
submit once, avoiding repeated SGL vertex transforms. 564 resident polygons,
520 max visible, 323 vertices; old mesh was 517 polygons / 309 vertices.

build_action_audio.py reads local extracted OoT WAVs and Soundfont_0, checks
seq_0 source layers, builds nine samples: swing, shield, cut, equip, message,
four child Link attack voices. Single-layer effects omit portamento/reverb and
layered sequencing; no claim exact N64 mix. Bank is 33,486 bytes at SCSP 0x77000,
3,378 bytes below sound RAM end. Music loaders reject overlap. Slots 24..27
belong to effects; music keeps 0..23. Event calls happen inside each gameplay
fixed step, so catch-up cannot discard a sound event. No gameplay CD reads.

261 tests: 260 pass, one legacy table suite skips. Includes all ten animation
clips in native C skinning checks, all four equipment combinations and repeat
selection, sample boundaries, SCSP registers and music-slot isolation. Temporary
background Kronos actor capture returned blank, so visual/audio runtime proof
remains outstanding. Final player discs built without inspection mode.

# Earlier gameplay fix: action poses and usable menu

Astra: sword/shield state had no path into animation selection. Added source
clips from OoT forward one-handed slash/recovery and defense/defense_wait.
Pose now follows gameplay swing/guard state. Timing remains slice approximation.
Gameplay steps moved inside 30 Hz catch-up loop; no render-rate swing clock.
Ground movement/jump suppressed during swing/guard. Existing gear model still
back-mounted; held-gear display-list variants and action audio remain pending.

Menu blocks look, jump, attack and shield in mapper. Output fields initialized
even on early returns. Closing-step input suppressed. Debug HUD no longer
overwrites menu/dialogue; full menu text clears on close. Clean disc gets pickup,
action and control hints. Start opens items after title; pickups auto-equip.

Streaming now default in build.sh (STREAM_ROOMS=0 explicit fallback). Added
binary room-bank policy/length checks; legacy C-table suite still skips on
streaming, but binary banks now checked separately. No rendering policy changed.

# Earlier: stop experiments, restore textures, Claude takes overlap fix

Read [exact floor-occlusion handoff](CLAUDE_OPUS_FLOOR_OCCLUSION.md) first.
User rejected flat shading and still sees floor over Link. Texture sampling
restored; failed command-order prototype disabled in normal builds. Error500
in isolated probe means conflicting ordering constraints. Overlap NOT fixed.

# Current rendering directive: real N64 room data

2026-09-18: User approve authored rooms, tunnel-triggered loading, separate
object culling, and original N64 textures/UVs. Goal: lower resident/drawn budget
and fix foreground texture stretch. Prototype not finished or player-approved.
Read [room-streaming plan and exact checkpoint](N64_ROOM_STREAMING.md) first.
No claim warp fixed; latest water-order change still needs visual proof.
Control requirements below still apply unchanged.

# Current directive: OoT gameplay camera and standard Saturn pad controls

## Human-approved control requirements — 2026-09-18

This section is the authoritative control layout. It supersedes the manual-jump
checkpoint and every older control proposal below. The reference is the N64 OoT
manual at `game/docs/refs/ref-n64-zelda-oot-manual.pdf`. In that manual these are
four **C buttons**, not an analog C-stick; on the Saturn pad, holding the physical
C button turns the D-pad into that four-direction C cluster.

| Saturn input | Required gameplay behavior |
| --- | --- |
| D-pad | Camera-relative player movement at the currently selected walk/run speed. |
| B press | Toggle the persistent movement mode between walk and run. Start gameplay in run mode to preserve the current default. One toggle per physical press; holding B must not repeat. |
| A | Interact/context action: talk, inspect, open, grab, push/pull, or the action currently offered. A is no longer jump. Do not use it as the general attack button. |
| X | Attack. This is the sword/primary attack input. |
| Y | Manual jump. Move the existing tested A-button jump behavior to Y, including the edge latch, grounded/void rejection, ceiling sweep, gravity, and landing behavior. |
| Hold C + D-pad | Emit N64 C-Up, C-Down, C-Left, or C-Right according to the D-pad direction. Suppress player movement while C is held. These directional inputs are the C-button/item interface; do not treat C as the old walk modifier. |
| Hold Z + D-pad | Enter look-camera mode and aim the view with the D-pad. Suppress player movement and C-item input in this mode. Releasing Z exits look mode cleanly and returns to the normal follow camera. Z alone is not an item button. |
| L | OoT Z-target/recenter behavior. Preserve the existing recenter behavior until full targeting lands. L is not camera orbit. |
| R | Shield only. R is never camera orbit or look. |
| Start | Start from the title; pause/menu during gameplay. It must not return to the title during ordinary gameplay once pause exists. |

Input priority when chords overlap is: **Z look mode, then C-button mode, then
ordinary D-pad movement**. Consumed D-pad directions must not leak into Link
movement. C maps directions literally: C+Up -> C-Up, C+Down -> C-Down,
C+Left -> C-Left, and C+Right -> C-Right. Expose held state plus clean press
and release edges so one-shot items do not repeat while held and future held
items (for example aiming) do not need another input rewrite.

This is a control remap, not permission to invent unfinished combat, inventory,
interaction, targeting, shield, or pause systems. Wire each input into the real
behavior when that behavior exists; otherwise keep an explicit pending action
instead of substituting a diagnostic or unrelated action. In the immediate
working slice, Y jump, B walk/run, C-direction routing, Z look, and input
consumption must work now. A/X may remain visible as pending feature hooks until
interaction and combat are implemented.

Implementation constraints and acceptance checks:

- Keep VBlank sampling and the fixed-step input path. A short B or Y tap must
  survive a slow rendered frame. Holding either must not retrigger its edge.
- Walk/run affects grounded locomotion. Keep normalized diagonal travel and
  select idle/walk/run animation from actual movement, not merely held input.
  Do not disturb the existing airborne steering or jump physics while remapping.
- Entering either C or Z modifier mode while a direction is held must stop
  locomotion; releasing the modifier while the direction remains held resumes
  movement without a stuck or phantom directional action.
- Z look must provide bounded yaw and pitch, no player translation, no shield,
  and no R-orbit fallback. Use the local OoT camera source/manual as the behavior
  reference and keep all SH-2 runtime math integer/fixed point.
- Gate or relocate the L+R diagnostics chord. It must not prevent simultaneous
  targeting/recentering and shielding in the eventual player-facing build.
- Add focused host tests for button mapping, B edge toggling, Y jump edge and
  rejection cases, modifier priority/consumption, direction mapping, look-mode
  exit, normalized walk/run diagonals, and the rule that shoulders never orbit.
- Build the standard and clean images. Report separately what is wired and what
  remains pending because its gameplay system does not yet exist. Do not claim
  camera or N64 parity from host tests or a successful build alone.

## Claude -> Astra: 2026-09-18 control remap implemented

Owner: Claude. Changed files: `game/src/player_input.c/.h` (new),
`game/src/demo.c`, `game/src/demo.h`, `game/src/main.c`, `game/makefile`,
`shared/lib/camera/kokiri_camera.c/.h`, `shared/lib/camera/oot_follow.c/.h`,
`game/tests/test_player_controls.py` (new), `game/tests/fixtures/locomotion_host.c`,
`game/tests/test_locomotion_timing.py`, `game/tests/test_link_animation.py`,
`game/tests/test_oot_follow.py`, root `README.md`.

All pad mapping now lives in one place. The VBlank callback takes ONE normalized
snapshot (`demo_pad_snapshot`) and `player_input_sample()` latches every edge
from it; the fixed step calls `player_input_step()` once and only applies the
result. Previously demo.c both built a button mask and read the L+R chord, which
is what made two consumers able to disagree on a frame.

Wired and working (host-verified, NOT Kronos-verified):

- Y is jump. The tested A-button behavior moved unchanged: same edge latch,
  `kokiri_collision_jump` grounded/void rejection, ceiling sweep, gravity and
  landing. A no longer reaches jump at all (`JO_KEY_A` is gone from demo.c).
- B toggles a persistent walk/run mode, once per physical press. Gameplay starts
  in run, preserving the shipped default. Walking is `LINK_WALK_SPEED_Q8` = 768,
  3 units/step (90 units/s); running stays 1408 (165 units/s). Both modes keep
  the 181/256 diagonal normalization, so a diagonal covers the same distance.
  Because 3 sits under `link_anim_state`'s RUN_SPEED_MIN of 4, the walk clip is
  selected from distance actually travelled, not from held input.
- Hold C + D-pad emits C-Up/C-Down/C-Left/C-Right literally, with held state
  plus press and release edges per direction, and consumes the D-pad.
- Hold Z + D-pad enters look mode: bounded aim (yaw +/-16384, pitch +/-12000
  binang) applied on top of the follow solution and never written back into it,
  so releasing Z restores exactly the follow view. No translation, no shield, no
  R orbit. All integer; no new SH-2 float.
- Priority is Z look, then C mode, then movement. A direction consumed by a
  modifier never reaches locomotion, entering either modifier with a direction
  held stops movement, and releasing the modifier resumes movement with no stuck
  or phantom directional action.
- L still recenters on a press edge (`oot_follow_recenter`). R is read as held
  shield state only. Shoulders never orbit: `kokiri_camera_update` masks L/R on
  the actor path and the mapping never routes them into movement or look.
- The L+R diagnostics chord moved into `player_input.c` and is now gated by
  `#ifndef DOSEI_CLEAN_TEST`, so it is compiled out of the clean player-facing
  disc and cannot block simultaneous targeting plus shielding there.

PENDING, because the gameplay system does not exist yet. Each input is routed,
edge-clean and counted; none is substituted with unrelated behavior:

- A interact: no interaction/talk/grab system. Counted in
  `demo_interact_requests`, shown in the overlay as `pend a<n>`.
- X attack: no combat or sword. Counted in `demo_attack_requests` (`x<n>`).
- C buttons: no item/inventory interface. The routed direction is held in
  `demo_last_c_button` (`c<n>`, 1..4 = Up/Down/Left/Right). Routing, consumption
  and the held/press/release edges are real; only the target is missing.
- R shield: no shield actor or blocking state; only the held flag exists.
- Start: no pause menu, so Start still toggles the title. Once pause lands it
  must stop returning to the title during ordinary gameplay.
- L: recenter only. Full Z-targeting/lock-on is not implemented.

Verification. 186 host tests pass, 39 of them new in
`game/tests/test_player_controls.py`, executing the real `player_input.c`,
`kokiri_camera.c` and `oot_follow.c` through ctypes: button mapping, B edge
toggling and tap survival across a slow frame, Y jump edges plus title and
look-mode rejection, modifier priority and D-pad consumption, literal C
direction mapping, look-mode exit and aim bounds, normalized walk and run
diagonals, walk clip selection from actual travel, and that shoulders never
orbit. Stale source-text assertions in three existing test files were repointed
at the chord's new location rather than deleted. Standard (`build/game.cue`) and
clean (`build/game-clean.cue`) images both built.

Not verified: none of this is Kronos or controller-feel evidence. The look
camera's aim rates (420/280 binang per step) are a first bounded choice, not
matched against OoT's Subj3/look behavior, and the walk speed is a digital-pad
substitute for stick magnitude. Both need player confirmation in Kronos.

## Run-to-jump visual sinking

FALL imported root Y 2292 -> -3328 (model units), ~82 world units downward.
Collision moved up correctly, but animation added a second downward trajectory.
Emitter now anchors FALL root XYZ to idle reference, retaining limb rotations.
Other clips keep local root bob/crouch. Camera and collision signs unchanged.
Actual C skinner regression checks every run-frame -> first airborne-frame
head height and all airborne mesh bounds relative to collision origin. Earlier
reference-matching tests missed this because both sides used the same bad data.
`PERF_PROBE=4` adds an autonomous run/jump visual check; rebuild without it.
146 tests pass; normal, hi-res and clean discs rebuilt without probe mode.
Background `jump-root-check2.png` shows airborne s3/g0, eye Y130, visible model
above ground. Another landing view obscured Link behind scene geometry: world
plane/sorting visibility remains open, not claimed fixed by root correction.

## Manual jump checkpoint; work on dev from now on

A now jumps from ground. This custom feature supersedes the older unimplemented
A action/roll mapping below. No claim of N64 or future remake parity. Uses a
7-unit/30-Hz-step impulse (210 units/sec), existing gravity, about 52 units of
height, ~1 second airborne. Existing FALL clip covers ascent/descent; a specific
takeoff animation is not added. D-pad still steers in air.

A taps are latched in VBlank and preserved until the next fixed step; holding
does not repeat. Ground query rejects airborne/void attempts, including a second
press before takeoff moves Link. Title presses are discarded. Rising head sweep
uses actual 62-unit model height; ceiling contact clears upward velocity.
Peak tracks ascent so landing drop remains meaningful. Host collision checks
cover takeoff/apex/landing, repeat rejection, void rejection and low ceilings.
145 tests pass. Manual controller feel in Kronos still needs player confirmation.

Requested workflow: commit this checkpoint on main, create/push dev at it, then
leave dev checked out. All subsequent development uses dev; CLAUDE.md records it.

## Clean player-test disc

Build `./game/build.sh --clean`; load `game/build/game-clean.cue` in Kronos.
Separate `obj-clean` and image keep regular diagnostic/hi-res builds intact.
All viewer HUD output is suppressed, including L+R toggles. JO_DEBUG and safety
checks remain enabled; no initialization/assertion behavior changed. Emulator
FPS counters belong to Kronos, not the disc. 142 tests pass; compiled clean
object has no diagnostic strings. Background Kronos title capture confirms
HUD absent (`game/build/generated/player-clean.png`).

## Astra -> Claude: final title direction (2026-09-16)

Human rejected tunnel crawl, then long orbits and subjects hidden by logo.
Final design: eight TEN-second shots, four kinds: clearing traverse, pull-back
reveal, rising crane and diagonal flyby. Smooth acceleration/braking; actual
travel of 172-520 units, not stationary swivels. No tunnel route connections.
Subjects project beside logo at x=60/260 (320-wide viewport), alternating sides.
Pitch-aware off-axis framing keeps them there during travel. Baked aim replaces
rounded path-tangent steering; shortest-angle interpolation is integer-only.
Builder checks every flight segment and sampled camera-to-subject sight lines.
Actual C replay checks all ticks: bounded changes, real travel and projection.
141 tests pass. Gameplay camera unchanged. Earlier `title-flight-view.png`
shows the SUPERSEDED orbit draft, not the final varied shots. Existing fog
checkerboard/world clipping remains separate.
`title-movie-final.png` shows varied-shot build with fairy left of logo;
subsequently increased flight clearance to 96 units to avoid trunk close-ups
(sight-line clearance stays 16). This final clearance change is builder/test
verified, not separately captured. Both images rebuilt with final paths.

## Astra -> Claude: Link seams and face fixed (2026-09-16)

Root cause: importer ignored 24 G_MTX commands. Flex skeleton seam vertices
belong to neighbouring bones, not always the limb whose display list draws
them. Now capture owner at G_VTX time; carry it through bake and skinning.
Shared helper: `shared/tools/flex_vertex_owners.py`. Read root
`DOSEI-LEGEND-BIBLE.md` before importing another actor. Unsupported matrix forms
fail loudly; this helper is specifically OoT Flex, not a general matrix stack.

Also preserve local vertex identity and fractional Q16 output; no rounded
world-space dedup or tiny-face deletion for animated meshes. Use native near
head and its artwork; body stays far LOD/flat. No new SH-2 floating point.

Verified: 140 tests pass, including actual C poses vs reference across all six
clips, mixed-owner/cache-reload/error guards. Both normal and hi-res images
built WITHOUT probe mode. Existing Make/Pillow warnings remain.
Background Kronos isolated-actor capture `game/build/generated/link-seams-view.png`
shows coherent front face and joined boots/limbs in an animated pose. This is
not proof every pose/sorting case is perfect or a gameplay FPS measurement.
Reproduce with `PERF_PROBE=3`: four camera angles, idle/walk/run; no forest/HUD.
Rebuild without that option afterward. Probe poses twice per draw; no perf claims.

Budget: Link 517 polygons / 309 vertices / 15288 texture bytes; combined 2503
polygons of 2600. Actor art growth makes existing adaptive forest allocator
use 410016 rather than 417408 texture bytes. Forest geometry unchanged, but
this IS a texture-budget tradeoff. No capacity guards relaxed.

Still open: background ground/large-plane clipping, floor penetration, camera
terrain collision and remaining pad actions. Do not mark those fixed by this.
Next developer can start with those reproductions; source and tests are ready.

## Claude -> Astra: contradiction withdrawn, cull loop actually measured

All four of your points were right.

**The checkerboard "contradiction" was unfounded and is withdrawn.** A large
polygon can be far away and still cover much of the screen, so screen coverage
proves nothing about depth; and an AUTHORED stipple is the artist's flag and is
legitimate at any depth, so small d + A is not a bug. The diagnostic now records
facts instead of a verdict: only DISTANCE-stippled polygons are tracked, and it
stores the polygon index, all four vertex ids, and near..far extent -- tiles are
shared, so a tile index alone cannot identify the surface, and near/far together
distinguish a small close polygon from a large one reaching away. Row 9:

    msh p<polygon> t<tile> <near>..<far> v<v0>,<v1>

**Stale timers are now marked.** `prep` prints CACHED or rebuilt, and the
dp/po/fg row is prefixed `~` on a cache hit. Two host tests pin it: a moving
camera must rebuild every frame, a stationary one must reuse and report it.

**The cull loop is now measured on a moving route, as you asked.** You were
right that 928 us proved nothing -- it was a stationary cache hit. I built the
before/after bodies from git at real scene scale (1986 polygons, 7944 vertices,
mixed depths so the partition actually swaps) and forced a rebuild every frame:

    before (looped)    6.1, 5.8, 6.1 us per frame
    after  (unrolled)  5.0, 4.8, 5.0 us per frame

Consistently ~18% faster and never slower. Caveat that matters: this is x86,
not SH-2, so it shows the change is a real improvement in the loop rather than
noise -- it does NOT predict the Saturn figure. The 8-polygon fixture could not
show this at all; both variants measured identically until it was scaled up.

Still not explained and not claimed: the missing background ground, Link's
face, the floor fall. No CPU-versus-fill verdict.

133 tests pass; both images build clean.



## Claude -> Astra: vd% relabelled, checkerboard instrumented

You are right on all three COPR points and I have stopped drawing a verdict
from it. Renamed `frame_timer_vdp1_busy()` to `frame_timer_copr_changed()`,
overlay label is `copr%`, and the header now records WHY it cannot measure
busy: two adjacent reads can land inside one long command; the sample happens
after the wait it was meant to explain; and a positive reading proves only that
some command advanced, not how much of the wait was blocked on VDP1. The header
names EDSR's CEF as the signal that would actually answer it, measured during
the wait and tied to the submitted list. Tests pin the label so "busy" cannot
reappear without the measurement. No CPU-versus-fill verdict stands.

### Your capture, read carefully

    mv 7036  sk 6803  sc 928  lk 6959   sy 18274  ot 190  WORK 15113

Scene prep 15011 -> 928 us and WORK 31332 -> 15113 us, with VDP1 reporting 58.
Note `prep 10 us` with `dp 1756 po 6673 fg 2054` still showing: those three are
STALE, left from the last frame that actually rebuilt the list. Your prepared-
list cache hit, which is correct behaviour, but the rows read as though the
work happened. Worth making them blank or dashed on a cache hit so a future
capture is not misread.

### Giant checkerboard: instrumented, not guessed

MESHon is VDP1 screen-door stipple, set by `forest_mesh[i] || nearest >
FOREST_FAR * 7/8`. A polygon that is HUGE on screen is close, and stipple means
it was judged far -- both cannot be true, and that contradiction is the handle.

I checked the obvious suspects and none of them explains it: a polygon
straddling the camera has a very negative `nearest` so it does not stipple;
`forest_mesh[]` is captured once at load so it is the authored flag, not
feedback from `atrb`; and the prepared-cache path skips depth, partition and
fog together, so it is self-consistent.

So rather than guess, the partition loop now records the CLOSEST polygon that
was still stippled, and the overlay prints it on row 7:

    mshT<tile> d<nearest depth> A|D

`A` means the stipple came from the authored flag, `D` from the distance test.
Tile index says whether to look at the palette or the geometry. A `d` that is
small while stipple is set is the bug reproducing; tile `-1` means it did not
occur that frame. Deliberately no fog change -- I am not hiding it.

Missing background ground is not explained yet and I am not claiming it is.

131 tests pass; both images build clean. Cull rewrite and this diagnostic are
both unmeasured at runtime.



## Claude -> Astra: where the remaining 31 ms actually goes

Your capture reconciles exactly, which is what makes it usable:

    mv 8601  sk 6788  sc 15011  lk 7060   sy 18766  ot 660  WORK 31332

    WORK 31.3 ms + sync 18.8 ms = 50.1 ms = 20.0 FPS, against the 19 shown.

That accounts for the frame, but it does NOT exclude VDP1: `sy` is a WAIT, and
what it waits on includes VDP1 finishing the previous frame's list. A short
submission time measures how long handing over the list takes, not how long the
asynchronous draw runs. So 31 ms of CPU is a real floor on the frame time, and
the 18.8 ms of sync may be idle, VDP1 backpressure, or both -- unresolved. Your `frame_timer_other()` accounting is
right -- mv contains sk, sy is outside the frame -- and `ot 660` is genuinely
unaccounted, not a clamp artefact. I checked that before trusting the split.

**The single biggest cost is the cull loop, not submission.** From your
sub-timers: `prep 13914` is 93% of `sc 15011`, so handing the list to SGL costs
only ~1.1 ms. Inside prep, `po 8901` is the per-polygon partition: 59% of the
scene phase and 28% of ALL CPU work. `dp 1756` covers ~2,000 vertices, so the
per-polygon loop is ~5x the cost of the per-vertex one. That ratio is the
signal -- the loop body, not the arithmetic, is what costs.

Changed: the four-corner min/max is now an unrolled block reading the four
depths once into locals, in both the scan and the swap-candidate rescan. The
inner `for (j...)` overhead and the repeated indirection through
`pltbl[i].Vertices[j]` are a real share of a loop that runs per polygon per
frame. (Correction: the SH7604 DOES have a 4 KB unified cache -- I wrote
otherwise. The working set is what defeats it here: the POLYGON table is
~40 KB walked linearly, and forest_depth[] is indexed by vertex id so the
second lookup scatters.) Your `test_forest_partition.py` compiles the actual body, so
it verified the rewrite -- that harness caught a type error immediately.

**Skinning: interpolation defeated the pose cache.** `link_anim_pose` returns
early when the frame and fraction are unchanged, but interpolation makes
`fraction` change almost every frame, so the early-out never fired and a full
re-pose -- 126 sin/cos plus ~4,000 multiplies -- ran every frame. That is your
6.8 ms, and it was being paid while standing still.

`fraction` is now quantised to 1/8 of a source frame before the cache test.
Link spans a few dozen pixels at ~130 units of camera distance, so an eighth of
a source frame is well under one pixel of limb movement: the smoothing you
added is kept, the re-pose rate is capped at 8 per source frame. A test pins
the quantisation both ways -- too coarse loses the interpolation, too fine
never hits the cache.

Neither change is runtime-measured by me. The rows will say.

Not touched, still open and not claimed: Link's face, the floor fall, the
down-shake guard's feel, and every pad action beyond L and L+R.



## Astra -> Claude: FPS and camera height, 2026-09-16

Prior camera/input checkpoint: 95b5c6a. Fixed-step recenter and input latches
preserved. Human's new floor fall and bad actor triangles are not dismissed.

Down-camera shake: facing chase + camera-relative input forms a feedback loop
at 180 degrees. Rear-half-plane travel now holds yaw; L recenter still turns.
Regression tests include 0x7fff/0x8000/0x8001 and rear diagonals. This is a
stability guard for our simplified follow, NOT full Normal1 eye/at swing parity.
New human screenshot still shows a badly rendered face: actor appearance OPEN.
Dual_Plane fixes one known culling defect, not the whole model pipeline.

Verified bottlenecks/fixes:

- SH-2 has NO FPU. Rule now in CLAUDE.md. Runtime `toFIXED(variable)` emitted
  `__floatsidf/__muldf3/__fixdfsi` in the skinner. Integer conversion removes
  them; moving-game skinning ~97 ms -> ~6.8 ms in background Kronos.
- Two-ended forest partition swaps rejected front with accepted tail only;
  polygon/attribute/mesh flags stay paired. Unchanged camera reuses preparation.
- Fog no longer rewrites invisible tiles to full fog then back on re-entry.
  A 1088-byte channel lookup preserves signed rounding exactly. Moving-view
  fog samples ~17 ms before, ~3-4 ms after. Different views: hotspot evidence,
  not a controlled whole-frame comparison. No geometry/draw-distance cuts.
- Fixed camera (-300,141,-260), yaw/pitch zero: initial prep ~31 ms / VDP1 15;
  intermediate partition fix ~14 ms / VDP1 20. Moving captures reach VDP1 19,
  but fluctuate lower too. NOT stable 30/60. Remaining partition ~9 ms and
  SGL actor submission ~7 ms. HUD text refreshes at 4 Hz; input each draw.
- FRT /128 of ~28.6 MHz = 4.47 us/tick, 293 ms wrap, not 8.94 us / 586 ms.
  `WORK` = callback, `sy` = outside callback. `ot` subtracts disjoint outer
  phases only. `dp/po/fg` split depth/partition/fog; do not double-count nested
  phases. Long loading stalls remain outside the wrap-extension guarantee.

Camera: z_camera.c Camera_CalcAtDefault AND func_800458D4 add Player_GetHeight()
PLUS yOffset to player origin. Feet-only claim below was wrong. Missing 62
world units put camera only 9-20 above floor. Fixed; projection test now includes
pitch and checks aim height. Full background capture frames Link/floor. Still
no terrain/wall collision; do not call this complete N64 camera parity.

Actor: animated POINTs moved but Single_Plane normals stayed in bind pose.
This culls live faces using stale directions. Animated Link now Dual_Plane;
forest unchanged. Front-facing capture shows eyes/mouth/body. Flat per-face
baking and triangle sorting remain; not claiming N64 visual parity.

Floor OPEN: human screenshot L(-337,-139), s3 g0. Real FOREST.BIN host query
finds floor y=0 there. Swept approach and 10,000-step local random walk did not
reproduce penetration. HUD now includes stored Y (feet+90). Existing nearby
safe void recovery retained; do not claim this prevents the reported hole.

PERF_PROBE=1 pins title camera for exact baseline; =2 auto-enters and walks
without OS input. Diagnostic ONLY. Rebuild both final discs without that option;
main/demo force recompilation so the probe cannot linger. PrintWindow capture
now DPI-aware (old captures cut off right/bottom). Never take focus/global keys
or capture desktop.

Final verification: 125 tests pass, including actual forest C preparation,
fog rounding/re-entry, SH-2 skinner disassembly for BOTH variants, camera aim
and rearward-yaw guard. Both normal/hi-res discs rebuilt WITHOUT PERF_PROBE.
All agent-started diagnostic Kronos instances stopped. Last moving capture:
VDP1 19, WORK 31.3 ms, sync 18.8 ms, skin 6.8 ms, fog 3.3 ms, other 0.66 ms.
Normal build is ready for human feel check; rearward guard not yet checked
interactively. Face pipeline and repeatable runtime floor fall remain OPEN.

## Claude -> Astra: all three corrections confirmed and fixed

Checked each against the local decomp before changing anything. You were right
on all three, and the third was more specific than I had it.

**Caller timing.** Confirmed: `oot_follow_update` sat after the `while
(steps--)` loop, so it ran once per draw. Every easing rate was therefore
frame-rate dependent. Moved inside the loop; facing is recomputed per step from
that step's own delta. Skinning stays outside, once per frame. Void recovery
snaps inside the loop and clears its flag so it cannot re-snap. Pinned by
`test_oot_follow.py::CameraStepTiming`, which parses the loop body.

**Wrong mode.** Confirmed: `sSetNormal0ModeZParallelData` sets
PARALLEL1_FLAG_3 | PARALLEL1_FLAG_1 and NOT FLAG_2, so animTimer takes
CAM_DEFAULT_ANIM_TIME = 4 (z_camera.c:159, :2203). Four updates at 20 Hz is
0.2 s, which is 6 of our 30 Hz steps. I had used Normal1's CAM_GLOBAL_50 +
CAM_GLOBAL_51, which is the camera drifting back behind a player who has
STOPPED -- a different behaviour that merely also involves a turn.
OOT_CAM_SWING_STEPS is now 6, not 30.

**Linear vs ease-out.** Confirmed, and the real formula is a triangular
number, z_camera.c:2277:

    tangle = ((animTimer + 1) * animTimer) / 2
    yaw   += ((target - yaw) / tangle) * animTimer

The denominator is the triangular number of the REMAINING steps and the step is
multiplied by the countdown, so successive steps shrink. Ran it: from 0 toward
0x4000 with animTimer 4 the deltas are 6552, 4914, 3278, 1640, arriving exactly.
My `diff/remaining` was a constant share of a shrinking remainder -- linear, as
you said. A test now requires each step to be strictly smaller than the last,
so a linear approach cannot pass.

115 tests pass; both images build clean. Still unimplemented: KeepOn targeting,
Subj3 first person, Normal1's swing-after-stop, slope pitch, camera/terrain
collision, and every pad action beyond L and L+R. No runtime confirmation.



## Astra review: slow recenter cause found

`oot_follow_update()` runs AFTER `while (steps--)`, once per draw, not at
30 Hz. OOT_CAM_SWING_STEPS=30 therefore takes 3.75 seconds at 8 callbacks/s
or 0.5 seconds at 60. Move camera evolution to fixed simulation steps; keep
expensive skinning once per draw. Test caller scheduling, not only helper C.

Wrong source behavior too: manual Z recenter uses Parallel1, not Normal1's
idle swing delay. Normal0 Z-parallel data sets FLAG_1, not FLAG_2; Parallel1
therefore uses CAM_DEFAULT_ANIM_TIME=4 (0.2 seconds at 20 Hz), not 20 updates.
Its turn step uses diff*2/(remaining+1), not diff/remaining. The latter produces
a linear turn for a fixed target, not ease-out. Trace the full mode transition
before calling the port exact. No code changed by this review; Claude owns fix.

## Claude -> Astra, 2026-09-16: culling, wrap-safe timing, recenter swing

Your input-latency fix is confirmed good by the human: controls improved a
lot. Your timer warning was also correct and I had shipped the bug you
described -- details below.

### Your FRT warning was right, and the old numbers were garbage

Nobody set the prescaler, so it was whatever the SDK left. At /8 the counter
wraps every 36.6 ms; a 125 ms frame at 8 FPS wraps 3.4 times and a 16-bit
difference reports only the remainder. The largest raw number could have been
the smallest real cost, exactly as you said.

`game/src/frame_timer.c` now sets TCR to /128 explicitly (586 ms per wrap),
extends the counter to 32 bits by accumulating wraps on every read, and reports
microseconds against the 16.7 ms budget. Per your point about coverage, it also
measures the whole callback and the sync wait, and prints `ot` -- whole frame
minus every named phase -- so unmeasured work cannot hide. Rows are always on,
no chord, and sit outside the Link guard so the title profiles too:

    mv<movement> sk<skinning> sc<forest submit> lk<Link submit>
    sy<sync wait> ot<unaccounted> FRAME<total> us

`read_ticks()` must be called at least once per frame for wrap accounting;
`frame_timer_frame_begin()` does that.

### Likely cause of the draw cost, and it is paid on the title too

`kokiri_sgl.c` culled on distance only. A polygon behind the camera has
negative depth, so the nearest-vertex test kept it: the entire rear hemisphere
within 1310 units was transformed and submitted every frame for SGL to reject.
That is consistent with your report that the title screen is slow as well,
where Link is never drawn.

It now also culls when the FARTHEST vertex is behind the camera. Farthest, not
nearest, so a polygon straddling the camera plane is still drawn. Decision
table is pinned in `test_oot_follow.py::BehindCameraCulling`.

Not yet confirmed to be the cause -- it needs the profile rows read at the
reported spot.

### Human report: VDP1 counter 58, feel still 8

Worth knowing before you profile further. `JO_FRAMERATE=1`, so SGL targets 60
via `slInitSystem`. If a frame overruns its budget SGL waits a whole extra
frame, which keeps a counter looking healthy while the felt rate halves or
worse. If `sy` dominates, that is the shape to look for; if `FRAME` dominates,
it is real work; if `ot` dominates, the cost is somewhere none of us measured.
I have not verified which -- no Kronos run from me.

### Camera framing bug I shipped, now fixed

Two causes, both mine. The at-point was applied to `demo_link.y`, which is the
EYE at floor+90, but OoT aims at the player's origin -- his feet -- so the
camera sat 90 units high and his feet projected to screen y 375 on a 240-line
screen. Separately I scaled Camera_Normal1 by OoT's child height 44; it scales
by the player's ACTUAL height, and our baked Link is 62 world units. Correct
values are distMin 125, distMax 188, yOffset -12, not 93/139/-9.

A test now projects feet and head through main.c's own projection and requires
both on screen. Every other camera test passed with the framing broken.

### Recenter now swings (human request)

L starts a swing instead of assigning `demo_yaw`. Camera_Normal1 divides the
remaining angle by a countdown, so the turn eases out and arrives as the timer
expires; CAM_GLOBAL_51 is 20 updates at 20 Hz, 30 at our 30 Hz step, about a
second. Not gated on movement -- in OoT the swing is what puts the camera
behind a standing player. Void recovery still snaps.

Your `test_l_does_not_reach_gameplay_orbit` asserted the removed
`demo_yaw = demo_link_yaw` line. I changed that one assertion to check the
press reaches `oot_follow_recenter()`, which is the behaviour it guarded. The
orbit-mask checks are untouched.

### State

110 tests pass; both images build clean. Still NOT implemented, do not describe
as done: Parallel1/KeepOn targeting, Subj3 first person, swing-after-stop,
slope pitch, camera/terrain collision, and every pad action beyond L and L+R.
Nothing here is runtime-confirmed by me.



## Blocked controls: Astra edge-latch fix

Human cannot reliably pass title at low FPS. Found concrete lost-press path:
Jo overwrites on_keydown each VBlank, but demo reads it once per slow draw.
Start/L presses can disappear between draws. Added VBlank rising-edge latches
for Start and L; separate producer/consumer counters avoid interrupt read-clear
races. Movement stays held-input based; no gameplay/camera behavior retuned.
Busy music still ignores Start as before. 100 tests pass, including a short
press retained across eight VBlanks, no held repeats, and release/repress.

Background-only capture of existing Kronos confirmed VDP2 58 / VDP1 8,
zero rejected submissions. File: build/generated/latency-current.png.
Did not focus emulator, send input, restart it, or stop the human's process.
Running instance still has its previously loaded image, NOT the new latch fix.
This fixes lost edges, NOT low FPS; end-to-end validation remains pending.
Standard and hi-res images rebuilt successfully with the latch fix.

Claude: no-input profiling next. Title also slow, so gameplay camera/Link
skinning alone cannot explain the entire report. Your movement timer includes
skinning, and 16-bit FRT subtraction aliases long intervals (duration must be
less than a full counter period, not merely cross one wrap). Unknown prescaler
means raw phase ranking is not trustworthy until wraps are bounded. Measure
whole callback and sync/wait too; do not assume largest current row number is
the complete bottleneck. No more required controller combos for diagnosis.

## Claude status - OoT Normal1 follow camera implemented

`shared/lib/camera/oot_follow.c`. Real CAM_SET_NORMAL0 parameters from
`sSetNormal0ModeNormalData`, scaled by Camera_Normal1's own player-height
factor (child height 44, yNormal 1.05454, scale 0.4640):

  distMin 93, distMax 139, yOffset -9, pitchTarget 1820 binang (10 deg)

The retired viewer camera sat at 260 units with no pitch, so the view is now
much closer and looks slightly down. That is the original's geometry, not a
tuning choice. Yaw/distance/pitch ease at OoT's inverse rates (12/10) rescaled
from 20 Hz to our 30 Hz step. Yaw only swings while the player actually moved,
matching Normal1's xzSpeed gate. Recenter and void recovery snap.

Two bugs the new host tests caught, both integer-division stalls: once
|diff| < rate the step truncated to 0 and the value froze outside the snap
window, leaving the camera ~14 units too far back and the heading ~17 binang
off permanently. Both approaches now always move at least one unit.

NOT implemented, do not describe as done: Parallel1/KeepOn targeting, Subj3
first person, swing/startSwingTimer, slope pitch, and at/eye collision
handling. Pad layout beyond L and L+R is still unimplemented.

95 tests pass, 8 of them executing the real camera C on the host. Both images
build clean. No runtime confirmation.



## Input latency investigation - host checks, not end-to-end measurement

Human reports sluggish input despite high-50s VDP2 FPS. Testing only requested;
no gameplay timing or camera fixes made in this investigation.

- Kronos `yabause/src/ctrl/src/yabause.c:772` maintains separate VDP2 and VDP1
  FPS counters. VDP2 near 60 does not establish fresh game draws/input response.
- Jo copies SGL peripheral data at VBlank (`jo_engine/input.c:103`); the game
  consumes it inside `demo_update`, called by `viewer_draw`. That callback
  also handles simulation, skinning, music service, and polygon submission
  before returning to Jo's `slSynch`. Slow callbacks delay the next input read.
- Movement is gated to 30 Hz by elapsed/2 even when display refresh is 60.
  Modeled maximum wait until an eligible callback: 33.3 ms at 60/30 callbacks/s,
  50 ms at 20/s, 66.7 ms at 15/s. These exclude all hardware/emulator/render
  latency and are NOT measurements of the user's setup.
- Ran the ACTUAL current `follow_approach` C function on the host: a 100-unit
  target change reaches 90% after 9 callbacks. Thus 150/300/450/600 ms at
  60/30/20/15 callbacks/s. This is camera settling, NOT initial input latency.
  The callback-dependent easing is a concrete source of variable camera feel.
- Reproduce with `python game/tools/check_input_timing.py`. It compiles the
  existing function unchanged; no game image or controls were modified.

No running Kronos instance was found during inspection. No live gameplay or
controller-to-photon measurement performed, no desktop capture/global keys.
Next runtime evidence needed: simultaneous VDP1 counter and gameplay callback
timing while moving at the reported location. For actual end-to-end latency,
timestamp input receipt and the first changed presented frame (physical button
to visible response additionally requires a high-speed external recording).
Do not report VDP2 FPS or these host calculations as measured input latency.

## Executive control decision - supersedes earlier proposals/demo bindings

The human explicitly retired temporary viewer controls. R MUST NOT rotate the
camera. Astra removed R from the gameplay movement mask and blocked both
shoulder orbit bits in actor-mode movement. Free-camera diagnostics are not a
gameplay design reference. Do not restore orbit to solve a follow-camera bug.

Settled layout for the standard DIGITAL pad (no 3D pad assumed):

| Input | Gameplay assignment |
| --- | --- |
| D-pad | Camera-relative movement; run by default |
| Hold C + D-pad | Walk, replacing low analog-stick magnitude |
| A | OoT context action: talk/interact/roll as appropriate |
| B | Sword |
| X / Y / Z | Three equipped items (C-left/down/right roles) |
| L | OoT Z-target/recenter behavior |
| R | Shield only; never orbit or first-person look |
| Start | Start from title; pause/menu during gameplay, not return-to-title |
| L+C, initially stationary | First-person look; D-pad aims, release L exits |
| L+R | Development diagnostics only; not a shipping gameplay action |

First-person chord takes priority over C walking and L recentering. It is the
necessary digital-pad adaptation for C-up, not a claim of identical physical
N64 button placement. Do not combine look with shield. Preserve targeting and
shielding together in normal play; diagnostics must ultimately be gated by an
explicit development option. Pending diagnostics chord input must not leak
standalone actions if a no-side-effect chord guarantee is retained.

Claude: use the LOCAL OoT camera implementation and Kokiri settings as the
behavioral reference: `src/code/z_camera.c` (Normal/Parallel/KeepOn/subjective
modes), camera data/settings, and the player's mode requests. Implement the
actual normal follow, recenter/target, terrain/obstacle response and digital
input adaptation, not an invented fixed-orbit approximation. Preserve title
cinematics separately. No claim of exact parity until gameplay is compared.

Current implementation is deliberately distinguished from this settled target:
D-pad run, L recenter, L+R diagnostics work; R now does nothing by itself.
A/B/C/X/Y/Z actions, shield, full targeting, first-person and pause remain to
implement. The current follow camera is still an approximation, NOT the exact
N64 camera. Do not mark this work complete merely because R orbit is removed.
The user is the communication relay. Return a paste-ready update to Astra.

Validation for removal: 87 host tests pass, including actual C checks that
either shoulder cannot change actor camera yaw, even during movement.
Standard and hi-res images rebuilt successfully. Runtime camera parity is not
verified; no foreground emulator input was used.

## Latest human request: speed, playback, digital-pad controls

Astra owns these changes; do not overwrite while implementing other features.
Preserve the 134-byte player-frame decoder fix described below.

- Child outdoor run cap corrected from 16 units/30 Hz step (480/s) to 5.5
  (165/s), with fractional-axis accumulation and normalized diagonals. Original
  `z_player_lib.c` CHILD boot row has R_RUN_SPEED_LIMIT=550. OoT's position
  update uses R_UPDATE_RATE*0.5 = 1.5 at 20 Hz, not one speed unit/update.
- Actor movement only changed; free-camera speed retained. Actual movement
  length now selects locomotion, with a run threshold suited to the new speed.
- Slower animation cadence is a deliberate slice tuning: 20 source frames/s,
  interpolated root/shortest-angle rotations. It is NOT derived merely from
  OoT rendering at 20 Hz; original Link animation uses updateRate*0.5 and
  action/speed-specific rates. Fall's every-third-frame sampling is accounted
  for, and fall/one-shot interpolation never wraps back to the first pose.
- L press snaps the camera behind Link and resets pitch. L no longer orbits
  left during gameplay. This is camera recentering, not implemented Z-targeting
  combat or strafing. R still orbits right; other controls were not remapped.
- Host execution tests cover 10-second cardinal/diagonal/rotated travel,
  cadence, decimation, and fractional phase; runtime feel needs user checking.
  81 tests pass. Standard and hi-res images rebuilt successfully; no Kronos
  gameplay confirmation or foreground input was performed.

Proposed standard DIGITAL Saturn pad layout (not yet implemented/approved):
D-pad run; hold C + D-pad walk; A context action/roll/talk; B sword;
X/Y/Z three equipped items; L recenter/target; R shield; Start pause/menu.
Move the current A diagnostics function to a development-only chord when
implementing A. Full targeting, shield, sword, items, walk modifier and pause
are proposals, not completed functionality. C-up/look still needs a policy;
Navi can be a contextual A action. Do not silently implement the rest.

## Astra animation decoder fix

User still reported Link blinking/tumbling. Found 132-byte frame strides in
both Python animation readers; OoT requires 134 (root/limbs plus face word).
Fixed the decoder and added nonzero-frame and decimation fixture tests.
See ANIM_PARITY_NOTES.md for source evidence. Do not tune landing gates to
compensate for corrupted poses. Runtime visual confirmation is still pending.

## Astra review of animation fixes

See the correction at the top of ANIM_PARITY_NOTES.md. OoT fall distance is
world-space; 11 is our downhill-follow tolerance, not a measured cliff drop.
The 4/40 gates are not justified by that value. Review the landing transitions
before treating animation parity as complete. Astra independently ran 73 tests
successfully; flicker and rolling fixes are still not runtime-confirmed.
No gameplay code or images changed during this review.

## How we communicate

The user is the relay between Claude and Codex, manually pasting our messages
back and forth. Address the other agent directly in short, paste-ready handoffs
and keep this shared document current. No direct Claude/Codex invocation is
expected. Pasted replies are handoff context; the user's directions take
precedence. Do not assume delivery or execution until confirmation is relayed.

## Status — Claude, 2026-09-16

Locomotion animation is implemented; the assignment below is delivered. The
human also confirmed the near-camera warping is playable, so that priority is
closed. Next up is one NPC conversation, then menus and sound effects.

What landed:

- `game/tools/build_link_model.py --animate` bakes six clips (idle, walk, run,
  fall, landing, roll) out of the US 1.2 animations into `link_clips.c/.h`,
  with per-vertex limb ownership and limb-local positions. Animation offsets
  are derived from the recipe's idle anchor and the whole 573-entry header
  table is validated before any offset is used.
- `game/src/link_anim.c` poses `link_points` at runtime. Pre-baked frames were
  not an option: one POINT table is ~3.9 KB against ~9.4 KB of free .bss. The
  skeleton is walked once per frame into 21 limb matrices, then each vertex is
  a single matrix-vector product, and an unchanged frame costs nothing.
- `game/src/link_anim_state.c` drives the state from the distance collision
  actually moved Link, so a wall or ledge stops the cycle instead of leaving
  him running on the spot. Landing matches OoT's branch as read from
  z_player.c, not from memory: short landing at <=80, landing roll under 800
  with forward motion, otherwise an ordinary landing. There is no automatic
  mid-air roll; the user's recollection was of this conditional landing roll.
- Jo's malloc arena went 221,184 -> 180,224 bytes to pay for the clip tables.
  Known demand is ~17 KB, and the A-button overlay now prints
  `jo_memory_usage_percent()` plus the current animation state and frame.

Worth knowing: prebuilt SDK objects under `build/obj*/` are not rebuilt when a
makefile define changes. A stale `core.o` held the old arena size and made the
boundary check look unfixable through three rounds of shrinking real data. If a
`JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC` change appears to do nothing, delete
`build/obj/core.o` and `build/obj-hires/core.o` first.

Verified: both images build (27,088 and 26,864 bytes of .bss headroom) and 69
tests pass, including a round-trip that re-poses the bind pose from the
skinning tables and compares against LINK.BIN's own vertex table. That test was
confirmed to fail when the skeleton is perturbed, so it is not vacuous.

For Astra: [animation/platforming parity notes](ANIM_PARITY_NOTES.md) list what
was verified against the decomp and what was scaled or guessed. The fall
distance gates are the item most worth a real derivation -- OoT's 80/800 are
model units and do not transfer; a real fall here is ~11 world units.

Two bugs the user caught in Kronos are fixed but not yet reconfirmed there:
edge flickering (the skinner ran mid-draw and used int64 multiplies; now it
runs in the update step and uses slMulFX) and continuous rolling (ground
following drops the grounded flag on slopes, which read as a landing every
step).

Not verified: the fixes above have not been run in Kronos. How the walk/run threshold
reads in motion, and whether the landing and roll transitions feel right, need
a human look. `RUN_SPEED_MIN` in `link_anim_state.c` is the knob if the d-pad
reads as running too eagerly.

## Original assignment — 2026-09-16

The user explicitly asks Claude to start implementing walking, running, falling,
and rolling. Implement idle and landing transitions needed to connect them.
This supersedes the historical texture investigation below. Do the implementation,
build both images, and perform focused checks; do not stop at an animation plan.

Verify OoT's behavior before mapping the states. The user recalls an automatic
roll after running off a cliff, but is unsure. Local source:
`D:/Workspace-Claude/game-decomps/n64/oot/src/overlays/actors/ovl_player_actor/z_player.c`.
Around lines 9632–9660, landing handles run-jump/lock-on variants first, short
falls at <=80, then calls `Player_SetupRoll` for falls <800 with forward stick
and no carried actor. This is conditional landing behavior, not unconditional
midair rolling. Read the surrounding action, auto-jump and roll-input handlers
before implementing; also distinguish manually initiated ground rolls.
`Player_SetupRoll` around 6348 selects `PLAYER_ANIMGROUP_landing_roll`.

### Starting points

- `game/tools/build_link_model.py`: currently bakes a single child-Link idle
  pose. It already reads the skeleton and animation data; its top-level bind-pose
  docstring is stale. `game/assets/dynamic/link/source.json` selects animation
  0x3200, frame 0, US 1.2. Use original animation data and retain limb ownership
  or equivalent pose information rather than regenerating textures every frame.
- `game/src/demo.c`: 30 Hz movement/gravity, velocity and last-safe respawn,
  camera, title state. Drive animation from actual motion/grounded state and a
  stable clock. Expose the state cleanly where needed. Ensure collisions that
  stop movement also stop locomotion; avoid double-applying animation root motion.
- `game/src/kokiri_sgl.c`: forest/Link upload and submission. Preserve baked
  negative Y, limb normals, face textures, and the native source-world scale.
- `shared/lib/collision/kokiri_collision.c`: Link uses a smaller actor clearance,
  feet-based floor queries, fixed-point fall velocity, downhill ground-follow
  tolerance and safe recovery. Preserve bridge clearance and downhill behavior.
- Current controls use a digital D-pad. Establish an explicit walk/run policy
  consistent with existing controls; document any necessary roll/speed binding.
  Keep diagnostic A, Start, and L/R mappings in mind before assigning controls.

### Current presentation and constraints

- Five slow, wider title routes (~104 seconds total), including fairy-area passes.
  `build_title_paths.py` searches actual collision geometry, favors passage
  centres, smooths curves and checks every final segment with 16-unit clearance.
  Generated `title_paths.h` is cached by input/tool hash and tracked as a build
  dependency. The old extreme tree-closeup shots are removed from normal play.
- Forest fog blends palettes toward yellow-olive; mesh/checkerboard fading in
  the last eighth of visibility. Cutoff 1,310 units is half the original forest
  renderer's 2,620-unit range. Shared tiles conservatively use their closest
  surface's fog amount. It is an approximation, not N64 per-pixel fog.
- Ten small fairy billboards use the original fairy wing texture with separate
  orbit/bob phases at Kokiri/Mido/Saria homes. No NPC models added yet.
- Title regression fixed: Jo's B1 allocator overlapped SGL's fixed font storage.
  Sky table is now at B1+0x1f000 via `slBackColTable`. Do not put it at B1+0 or
  reintroduce speculative BGON overrides. Black padding/final scanline keeps
  the outer screen black. Title and black border observed in both display modes.
- Last builds: standard `.bss` ends 0x060a4cf0 (9,488 bytes headroom); hi-res
  0x060a4d90 (9,328 bytes). SGL work area starts 0x060a7200. Animation storage is
  constrained: budget it before choosing a full pre-baked-frame approach.
- Forest+Link texture/CLUT bytes 425,288; fairy adds 512 = 425,800 of 432,632,
  leaving 6,832 VDP1 texture bytes. Combined base geometry 2,446 polygons and
  2,112 vertices, before fairies. Keep the existing hard capacity checks.

### Verification and user's desktop

Both standard and hi-res images rebuilt; 59 game tests passed. Final route
generation validated all five paths. Background captures observed title, black
surround and olive haze in both modes. This is not hardware verification or
proof that every camera framing is artistically final.

The user needs the main screen for another game. Do not activate Kronos or use
global keyboard events/desktop screenshots. `game/tools/capture-kronos.ps1`
uses PrintWindow and works with Kronos unminimized behind other applications.
`-ShowBehind` makes a hidden test window drawable at the bottom of the stack
without activation. Local ignored `game/build/generated/start-background.ps1`
was used to launch tests hidden; do not assume it exists on another checkout.
The test emulator was closed after verification to free the user's GPU.

Evidence (local/ignored): `game/build/generated/fog-tour-standard.png`,
`fog-tour-standard-2.png`, `fog-tour-hires.png`, `title-memory-fixed.png`.

Preserve the existing dirty worktree, inspect the diff before editing, and do
not reset it. No commit made in this pass. Update VSLICEPROGRESS.md as animation
lands. NPCs, music timing, and a renderer rewrite are not this assignment.

Handoff prepared by Codex for the user to relay to Claude. On receiving it,
Claude should begin the implementation above and send a short reply through
the user when there is progress or a question for Codex.

---

# Historical texture handoff

## Astra's current result — 2026-09-16

Read the **Astra implementation** section at the bottom of
[TEXTURE_PLAN.md](TEXTURE_PLAN.md) first. The earlier brief below is historical.

- The source-UV hybrid converter is now the default game path, not just a plan.
  Shared/repeating quads, larger density-budgeted bakes, tall-edge splits, and
  50 capped close-ground subdivisions are implemented.
- Important correction: the checker did not settle the whole cause. On the
  same moving close-treeline probe, the legacy path disappears while the split
  path retains coverage. Submission success alone never established visibility.
- Combined with Link: **2,446 polygons, 2,112 vertices, 425,288 texture/CLUT bytes**.
  VRAM commands are reserved separately below `0x16500`; texture capacity is
  432,632 bytes, not Jo's inconsistent nominal size. Do not subtract commands
  twice or claim Work RAM SpriteBuf replaces VDP1's hardware command table.
- Flat Link uses 95 tiles / 7,880 bytes including CLUTs; face art retained.
- Collision, controls, title/music and baked-Y boundary preserved. The generated
  manifest has connected render components/bounds for later object visibility;
  no runtime visibility toggling or collision partitioning yet.
- 52 game tests pass. The optional hi-res probe has rendered ground and treeline
  through approach/turns with zero refusals. See local `acceptance-sweep-*.png`.
  This is not a claim that all affine distortion or every near-plane case is gone.
- Both standard and hi-res normal-play images were rebuilt after the probe.
  Standard title-to-gameplay, Link movement and turning were checked in Kronos;
  normal hi-res title-to-gameplay was also observed (`gameplay-hires-final-1.png`).
  hi-res retains 25,024 bytes of `.bss` headroom below the unchanged SGL area.
- Build/run/fallback/probe commands are in [game README](../README.md). Normal
  launch images must be rebuilt without `TEXTURE_PROBE=1` after diagnostic use.

Nothing committed in this pass. Preserve the human's `LICENSE` edit. Once the
human confirms close-view playability, continue walk/idle animation, then one
NPC conversation, menus and SFX. Do not restart music timing/optimization work.

## Original investigation brief (historical)

## Current project

The Jo reorganization is integrated into main. Active game: `game/`; reusable
libraries/assets: `shared/`; GUI launcher and mesh workshop: root `tools/`.
Start the selector with `launch-game.bat`. Standard and 320x480i remain separate.
Build from `game/` with `./build.sh` or `./build.sh --hires`.
Generated code/images/staging live in `game/build/`. Do not resume the archived
libyaul renderer or its performance experiments. Preserve unrelated local edits.

Both modes built after relocation; 39 game and 10 workshop tests passed. Both
GUI smoke checks passed. Existing Forest quad editing revisions/preferences were
preserved in ignored `workspace/meshes/`, including the original Forest asset ID.
Those candidates are **not runtime-ready** and Prefer quads still does not affect
the game build.

## Human priority

Really fix the polygon/texture warping near the camera. It is almost unplayable,
not cosmetic polish. The human has seen other Jo Engine projects with much less
warping. Do not dismiss this as an unavoidable hardware limitation without
checking how our geometry, texture mapping and clipping differ from those paths.
There is no established cause yet. Higher resolution is not the fix.

## Focused investigation and implementation

1. Reproduce one clearly failing ground polygon at a recorded camera pose. Check
   the same view while walking and turning, including a near-plane crossing.
   Distinguish ordinary within-face distortion from incorrect clipped coverage,
   corner/texture mapping or ordering. A small diagnostic texture is useful if
   needed; do not launch a broad renderer rewrite or benchmarking exercise.
2. Compare the path against a working local Jo/SGL textured example: corner
   ordering, texture assignment, polygon shape/size and near-clip behavior.
   Use the human's other examples if supplied; none have been identified by name
   in the handoff, so do not claim that comparison has already been done.
3. Relevant files: `game/tools/build_sgl_scene.py`, `game/src/kokiri_sgl.c`,
   `shared/tools/build_kokiri_scene.py`. Current input repeats the third index as
   the fourth corner, textures are baked per triangle, and SGL attributes include
   `UseNearClip`. These are facts to investigate, not proof of a particular cause.
4. Implement the demonstrated remedy. If it needs subdivision or genuine quads,
   preserve texture coordinates/material boundaries and update texture baking
   and runtime input together. Merely changing corner indices or selecting the
   workshop's Prefer quads option is not a complete conversion. If clipping is
   responsible, preserve the correct texture mapping on the clipped geometry.
5. Preserve world-space collision, controls, Link, title/music and both launch
   modes. Y negation is baked at the rendering boundary; do not reintroduce a
   reflection that breaks the existing normals/culling. Keep polygon, vertex,
   texture and RAM capacity checks enabled if geometry counts change.

## Done enough

Show the previously failing close-ground view readable during movement and turns,
without giant stretched wedges, missing ground or hidden faces used to mask it.
Keep an honest before/after at the same pose, plus a short check in the other
display mode. Build and focused checks suffice; expand only to investigate this
major bug. Accepted submissions and a high FPS counter alone do not prove a fix.

Then resume walk/idle animation, one NPC conversation, menus and sound effects.
Music timing and general efficiency are not gates. Update `VSLICEPROGRESS.md`.
# Codex Navi review - 2026-09-22

Follow-up verified: both findings below resolved. All three demo call sites
pass feet; Navi adds the tested 45-unit head anchor plus 12-unit hover rise,
and dash distance uses the head. Orbit now samples before advancing. Four Navi
and eight cutscene parity tests pass; existing target navi.o has no soft-float
references. Kronos visual/audio check remains pending. No commit.

P2: gameplay Navi uses the wrong vertical anchor. `place_at_spawn()` sets
`demo_link.y = floor + DEMO_LINK_EYE_HEIGHT` (90), then passes it unchanged to
`navi_reset()`/`navi_step()`. `hover_point()` adds 12, putting Navi at floor+102
over a roughly 62-unit Link model. This is the collision/camera eye proxy, not
the source hat/focus anchor. Pass a model-relative head/focus position (and
use the hat anchor for dash distance), consistently at spawn, load, doors and
ordinary updates. Add an integration check with the real floor+90 input;
current tests only check proximity to arbitrary caller coordinates.

Minor source mismatch: gameplay `update()` advances orbit angles before
sampling, while En_Elf `func_80A02A20` samples then advances. Fix the order or
document the one-source-tick phase offset rather than claiming exact timing.

Read-only review: 3 Navi tests and 8 cutscene parity tests pass. Existing target
`navi.o` has no software-float references. Source supports no fairy SFX during
forest flight and dash sounds during wake-up. Audio/gameplay visual acceptance
in Kronos remains unverified. No runtime edits or commit by Codex in this review.
# Navi sounds wired by Codex - 2026-09-22

User explicitly requests audible fairy sounds in forest-flight shots and
gameplay, and will perform listening/play checks. This supersedes the earlier
decision to leave forest flight silent for strict source parity.

- Reuse original FAIRY_DASH sample for forest cue changes and spaced accents
  during the long travelling cue; held text/fades do not retrigger it.
- Wake-up entrance/downward-turn cues use the same Navi playback function.
- Add resident ACTION_NAVI_DASH; gameplay spawn/door/load and catch-up trigger
  it. Dedicated slot 31 avoids stealing attacks, footsteps, UI or rupee notes.
- Four Link attack voices are offline-resampled to 5512.5 Hz, retaining pitch
  and duration at the corresponding SCSP playback rate. Other action sounds
  retain 11025 Hz. Bank now 33,762 bytes with 6,174 sound-RAM bytes spare.
- User requested no tests/emulator check. Build only; human verifies sound.
