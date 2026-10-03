# Current game plan (historical filename)

Updated 2026-10-03. Branch: oot-core. Goal: the full OoT decomp on Saturn,
using imported original game logic with Saturn graphics/audio/file backends.
This is not a new standalone demo or a rewrite of OoT gameplay.

## Current priority

Human confirms the 32-byte palette repair checks out in Mednafen. Graphics repair
is runtime-accepted. Next priority: missing Lon Lon Ranch NPC sprites and high
CPU/slow gameplay versus Kronos. Commit and push this accepted repair checkpoint
before subsequent sprite/CPU changes. Keep batched verification and one Clean image;
do not request intermediate emulator checks. Decomp retains the Saturn backend.

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

- Existing decomp integration and NPC sprites: see OOT_CORE_PIPELINE_PLAN.md.
  Sprite baseline is commit 8874db2; Kokiri was human-accepted in Kronos only.
- Current fixes: allocator splits reused holes and merges adjacent free blocks
  on allocation pressure; Clean sprite NPCs no longer retain unused 3D copies
  (Saria retains greeting mesh); Navi retains pixel pool/maps but loads each
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

## Next actions / remaining work

1. Usual game/build/game-clean.cue/.iso contains the 32-byte palette fix plus
   earlier graphics/CD/register changes. Graphics now accepted; investigate Ranch
   NPC sprite visibility and CPU cost next. No sprite/CPU implementation in this checkpoint.
2. CD house-exit fix still needs verification; Navi room-read
   pauses and late music cues remain open. No intermediate test requests pending.
3. Full decomp rollout remains required: actor coverage including horses,
   save-dependent NPC events/dialogue, scene/room doors, player/camera/cutscenes,
   and combat bridge parity. Keep the frame-skip rule for every C/decomp bridge.
   Debug RAM and sprite pitch views remain open. Archive replaced C systems only
   after the replacement works in game; builds alone never complete milestones.

Detailed handoff and historical evidence: OOT_CORE_PIPELINE_PLAN.md.
