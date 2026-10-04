# Current game plan (historical filename)

Updated 2026-10-03. Branch: oot-core. Goal: the full OoT decomp on Saturn,
using imported original game logic with Saturn graphics/audio/file backends.
This is not a new standalone demo or a rewrite of OoT gameplay.

## Current priority

Human authorized committing the completed sprite/CPU/save/cleanup batch and
handoff documents. This checkpoint is committed locally; no push requested.
Earlier "uncommitted" labels below describe the pre-checkpoint work history.

Latest human test: startup/each zone shows `dosei_allocator_free(): Null pointer`
about six times (22% dynamic memory, 0% sprite memory); one Ranch NPC visible;
generic-zone doors still unusable. Prior build/host success is not runtime
acceptance. Confirmed cleanup defect: story_route_free unconditionally frees
four Saria + two owl slots; SDK rejects NULL and test stubs missed this.
Cleanup now repaired in story_route, emerald_story and cutscene_actor; optional
pointers guarded and cleared. Eleven focused host checks pass, including 256
allocation combinations and repeated teardown; stubs now detect null frees.
WSL Clean rebuild passes (`build/null-free-fix-build.log`), usual image rebuilt,
.bss end 0x06081DE0 / 8,736 B spare. Runtime acceptance still pending.
Next execution order: all-zone doors/entrance graph, complete
NPC/animal visual and source-dialogue coverage across ages/layers/triggers.
Detailed actionable handoff: [NEXT_CHAT_WORLD_COMPLETION.md](NEXT_CHAT_WORLD_COMPLETION.md).

Human confirms the 32-byte palette repair checks out in Mednafen. Graphics repair
is runtime-accepted. Current batch fixes Ranch's missing sprites and unreserved
actor VRAM, removes remaining converted-cast model loads, and preserves fairy
wings in baked textures. Permanent rule: NPCs/animals/fairies/non-boss enemies
use sprites; bosses are explicitly exempt to preserve complex damage/puzzle
hitboxes. Full era/layer/trigger coverage is planned in
[ACTOR_SPRITE_ROLLOUT_PLAN.md](ACTOR_SPRITE_ROLLOUT_PLAN.md). High CPU/slow
gameplay versus Kronos remains open. Commit and push this accepted repair checkpoint
before subsequent sprite/CPU changes: done as 11312ec on origin/oot-core.
Subsequent Ranch/CPU changes are separate and uncommitted.
Keep batched verification and one Clean image;
do not request intermediate emulator checks. Decomp retains the Saturn backend.

Requested CPU/VDP1 review is complete; findings and ordered refactors are in
[the current performance review](OOT_CORE_PIPELINE_PLAN.md#current-performance-review-2026-10-03).
First implementation is the heading conversion: 32-bit integer math replaces
software-double conversion, with bounded scaling for large deltas. Host regression
passes 362,433 angle-input pairs and 11 existing player-camera tests pass.
WSL Clean build and matching target disassembly pass; usual image rebuilt.
Human now forbids 64-bit runtime math and allows approximation over exact OoT
fidelity. The tentative wide-divide patch was removed; converting existing Fx
and other wide math remains explicitly unfinished. Prior inspection confirmed
software-double heading conversions in the C backend, costly fixed-divide setup,
prop matrix decomposition/reconstruction, unconsumed sprite pose work and full
room vertex processing after polygon rejection. Their current frame-time shares
are unmeasured. No emulator run or performance acceptance.

Mednafen/hardware correctness precedes further actor rollout. Human reports:
VDP1 3D models and 2D sprites corrupt; slow title music/scenery startup; missing
nightmare riders; Navi opening memory error followed by skipped shots; house
exit failure. Latest human test: all opening sequences/shots now complete, but
Navi room reads pause the cutscene and music starts late. The later palette repair
now has explicit human graphics acceptance.
Earlier house exit showed CD read failures for CS4.BIN, then S1.OOC (not a
confirmed OOM). Latest human explicitly confirms opening the menu before music
now works. House-exit CD failure has no explicit acceptance yet. Latest forest
and nightmare screenshots still show severe VDP1 corruption before the CLUT fix.

## Implemented and verification

- Latest Ranch/sprite batch (uncommitted): linked-symbol sprite keys fix the
  ROM-offset mismatch (Malon previously expected 0x820, linked at 0xBD8).
  Compact object blobs now retain clip lengths but no skeleton/frame/joint data;
  Ingo OOB is 1,720 B, child Malon 680 B. Current clips load before optional clips;
  an unavailable pose keeps a compatible loaded sprite instead of vanishing.
- Ranch pixels shrink from 341,568 to 272,448 B (67.5 KiB saved); room + CLUTs
  are 295,776 B. Bake reserves 64 KiB actor bank plus 32 KiB spare. Human's
  prior 96% runtime VRAM/invisible-NPC report is not yet runtime-accepted fixed.
- Fairies now draw original textured wings and glow in one 32x32 billboard;
  no runtime FAIRY.BIN, four wing polygons, travel-facing math or skeletal work.
  NPC slots stay resident across visibility changes; shared 32-bit frustum
  rejection happens before sprite facing/uploads and fairy orbit work.
- Nightmare riders/horses, Saria bridge, owl and story Ganon/horse load SPR only.
  Their BIN/ANM and legacy NPC/skin payloads are removed from the staged disc;
  original models remain offline bake inputs. Static scene/bridge props and
  Link stay geometry. Boss models and complex hitboxes remain exempt.
- Verification: 36 focused host checks pass (sprite keys/clock/wing texture/assets,
  bank lifecycle, culling, story/cutscene and resource checks). WSL Clean target
  passes, log `build/ranch-sprite-build.log`; usual image rebuilt. Main .bss ends
  0x06081DC0, 8,768 B margin. Sprite culling disassembly uses 32-bit operations;
  legacy wide math elsewhere remains. Human runtime/FPS/dialogue checks pending.
  Ranch gameplay horses are still unimported; cutscene horses do not cover them.

- Sprite/save batch (uncommitted): fairy flyby, Saria greeting and shopkeeper
  use only NPC SPR sheets, with no runtime model fallback or head/torso tracking.
  Flyby uploads use the authored cast instead of Link's house scene. Imported
  Ranch NPCs retain a 32-bit frame clock for action transitions, but no skeleton
  reads, joint allocation, pose decoding or morphing. Ingo/Malon/Talon/cow
  tracking and Ingo fidget/root stagger are bypassed; talk/action/collision stay.
  Malon's zero-limb metadata matches sheets by object/clip. Fixed 16-bit sprite
  slot sentinel handling so a full bank cannot report a successful upload.
- Mednafen evidence: nine hash-named internal backups, only two older ones with
  DOSEI0. Current config uses default `%f.%M%x`; rebuilds changed disc identity.
  Copied the newest active save (`7f402babb95acd27ace60606f8dddfd6`) to stable
  `sav/game-clean.bkr`, plus its RTC file; originals retained, backup hashes equal.
  Launcher now performs this non-overwriting migration before running Mednafen.
  No global emulator settings changed. Host mock tests cover preservation across
  hash changes, existing stable saves, deleted entries and custom naming.
- Backup driver also gets reserved low RAM (16 KB code + Sega STN-52's 8,312-byte
  workspace), no automatic formatting, and specific save failure text. Mounted
  device read failures no longer masquerade as NEW FILE. These are code repairs,
  not proof they caused the reported Mednafen failure.
- Verification for this batch: 85 focused host tests pass. WSL Clean target build
  passes (`build/sprite-save-build.log`); usual `game-clean.cue/.iso` rebuilt.
  Main .bss ends 0x06082220, 7,648-byte margin. Sprite clock target disassembly
  uses only 32-bit arithmetic; the existing wider Fx ABI storage is unchanged.
  Runtime save/reload, sprite appearance, dialogue and performance still need
  human acceptance; no emulator launched. The later batch above also converts
  the separate nightmare riders/owl renderers.
- Latest CPU batch: heading conversion uses 32-bit range checks, shifts and
  slAtan on SH-2. Six software-double calls per heading are gone; matching
  game-clean.elf no longer links __floatsidf/__muldf3/__fixdfsi. Build log:
  build/cpu-heading-build.log. Main .bss 0x060838b0, margin 1,872 B (was 96 B).
  Host checks above pass; no emulator run or measured FPS gain. Other existing
  64-bit math remains migration debt. No wide-divide optimization was retained.
- Existing decomp integration and NPC sprites: see OOT_CORE_PIPELINE_PLAN.md.
  Sprite baseline is commit 8874db2; Kokiri was human-accepted in Kronos only.
- Current fixes: allocator splits reused holes and merges adjacent free blocks
  on allocation pressure; Clean sprite NPCs no longer retain unused 3D copies
  (Saria's former greeting mesh exception is now removed); Navi retains pixel pool/maps but loads each
  room mesh through bulk-read scratch, saving 737,384 resident mesh bytes.
- Boot music accepts caller-owned scratch for one whole PCM read. Other callers
  use multi-sector GFS reads, not Jo's per-sector reader.
  New CD ownership fix: project-local Jo GFS open/load/read hooks stop music
  read-ahead before file access; music resumes from consumed sector on service.
  Stop/start errors propagate, stream close stops read-ahead. Mock CD regression
  passes for interrupted/resumed loads, final partial sector and error paths.
- Graphics investigation: opening house uses VDP1 panorama bank 4, not the
  fixed NBG1 JPEG. This shot alone does not implicate NBG1 cycle patterns.
  Added actual VRAM CLUT readback validation. SP/PR/END now uses an independent
  overlay, drawn last even on Clean/title/menus/cutscenes: hold L+R one second
  to toggle, release before another toggle. Hidden initially. No direction needed.
  Correction: hardware SPCTL/PRISA are write-only; original zero readouts were
  invalid. New `SGL SP / PR` shows SGL's RAM shadow (intended settings only).
  END still reads hardware EDSR. Human confirms toggle shows the readout.
  Register audit also found TVMD read/modify/write in every VBlank and pause
  saving write-only cycle registers. TVMD now preserves SGL's shadow bits;
  pause saves shadow cycles and uses slScrCycleSet to update shadow and hardware.
  Latest human readouts: SGL SP 0723, PR 0604; END 1 in house, 3 in nightmare
  and forest. These plausible values do not establish texture correctness.
  Latest graphics batch additionally replaces black cutscene fades' negative
  colour offset with VDP2 alpha blending against a black line-colour screen.
  Host analysis of actual house pixels at screenshot FADE 100: old subtraction
  clips 59.91% to black; blending leaves under 2% black even with 5-bit output.
  This explains a major artifact in that shot, not all reported VDP1 corruption.
  Background sky fades proportionally; white flashes/gray transition path retained.
  The initial eight-byte CLUT padding was insufficient and is superseded below.
  Flat polygons/lines use
  required texture-mode bits 0; texture relocation no longer adds addresses to
  Link's flat RGB colours. The fade made the house brighter, but corruption persisted.
- Graphics root cause found: VDP1 CLUTs require 32-byte alignment, even though
  CMDCOLR encodes addresses in eight-byte units. Link's current 8912-byte pixel
  payload placed its palettes 16 bytes off that boundary and propagated the
  offset into later room palettes. Applying the hardware boundary to actual
  house assets reproduces the speckled curtains/walls and wrong floor colours
  offline. Source and correctly addressed converted house textures are clean.
  All three CLUT allocation paths now align actual VRAM addresses to 32 bytes:
  mesh banks (Link/rooms/panorama), streamed Field pools and per-tile actor/NPC
  uploads. Capacity checks and offline budgets include the padding. Existing
  texture data and imported decomp logic are preserved.
- Host: four graphics backend tests and six VRAM budget tests pass; eight Field
  stream tests pass. Actual upload functions are tested across all eight-byte
  start alignments, disk/cache paths, all 16 palette entries and capacity failure.
  Negative control: both upload regressions reject the former eight-byte rule.
  Earlier seven allocator tests and CD ownership regression also passed.
  Target: WSL Clean build passes, 96 bytes below SGL work area;
  log build/mednafen-clut-build.log. Runtime: no emulator launched. Human confirms
  earlier opening shots complete, toggle visible, and menu before music works.
  Human subsequently confirms the 32-byte palette fix checks out in Mednafen.
- Ranch sprite repair (new, runtime pending): host loaded sheets before
  Actor_UpdateAll spawned the room's NPCs, so the NPC list was empty. Asset load
  now follows the first actual decomp update, including after room changes;
  skipped 20 Hz steps never trigger premature loads. Sprite matching now accounts
  for SkelAnime's extra root-translation joint (Ingo: 20 joints vs 19 baked limbs).
  Sheet allocation includes Jo's trailing NUL, avoiding a one-byte heap overrun.
  Generic sprite VRAM slots now follow actual spawned instance count, capped at
  eight, instead of always reserving eight largest cels for even one NPC.
- CPU work removed: sprite-only C NPCs no longer compute unused head/torso
  tracking each catch-up step (now also Saria and fairy flyby). Scene and Link
  flat-face mode normalization happens at upload instead of scanning their
  attributes every draw; dynamic fog transitions and native callers retain correct
  modes. Decomp still steps at 20 Hz with the existing input/hit-volume contract.
  L+R's existing one-second toggle now also shows millisecond timings: MS total
  frame including sync, M movement/gameplay, G scene draw, L Link draw, OC last
  decomp update. CPU~ remains callback share, not Windows CPU utilization.
  Overall Mednafen slowdown has not been quantitatively attributed or accepted
  as fixed; target timing evidence is still required. No emulator launched.
- New verification: two host regressions execute actual host lifecycle/load/upload/
  draw functions with deferred actors; four graphics regressions also pass.
  WSL Clean build passes, 96-byte high-WRAM margin, log
  build/mednafen-ranch-cpu-build.log. Cold clip/scroll loading code uses Os to fit;
  heap and SGL capacities preserved. Usual Clean image contains these new changes.

## Next actions / remaining work

1. Graphics/CD checkpoint 11312ec is pushed and graphics accepted. Usual
   game/build/game-clean.cue/.iso now contains the Ranch/CPU and sprite/save batches.
   Save/reload across rebuilds, Ranch/flyby/Saria visibility and dialogue, and
   performance gains await eventual human acceptance;
   do not declare the overall slowdown resolved from host tests or build alone.
2. Performance implementation remains open: establish per-displayed-frame CPU
   totals and draw-completion timing. Heading target verification is complete;
   next replace core wide arithmetic with bounded 32-bit math and pass prop matrices directly.
   Sprite pose separation is implemented for the current sprite NPC cast.
   Follow with compact scene culling and per-cel upload reduction (stable banks now implemented);
   assess per-cel cropping from the review's offline evidence. Preserve gameplay
   and the 20 Hz/input/hit-volume contract. Approximation is allowed; 64-bit
   fallback is not. A storage-width change needs matching collision/units and
   scene/object blob changes. Broad -O2 and relocating the whole blob are not
   validated solutions. Current Clean work-RAM margin is 8,768 bytes;
   no new FPS or CPU-versus-VDP1 conclusion is established.
3. CD house-exit fix still needs verification; Navi room-read
   pauses and late music cues remain open. No intermediate test requests pending.
   Generic NPCs spawned later within the same room with a new object still need
   dynamic sheet discovery; room transitions now refresh after actor initialization.
4. Full decomp rollout remains required: actor coverage including horses,
   save-dependent NPC events/dialogue, scene/room doors, player/camera/cutscenes,
   and combat bridge parity. Keep the frame-skip rule for every C/decomp bridge.
   Debug target verification, coverage-ledger generation, remaining non-boss
   sprite conversion and sprite pitch views remain open. Follow the full
   [actor rollout plan](ACTOR_SPRITE_ROLLOUT_PLAN.md) across both eras, all maps,
   spawn layers and dynamic triggers. Preserve the explicit boss exemption. Archive replaced C systems only
   after the replacement works in game; builds alone never complete milestones.

Detailed handoff and historical evidence: OOT_CORE_PIPELINE_PLAN.md.
