# Current game plan (historical filename)

Updated 2026-10-04. Branch: oot-core, merging into main. Goal: the full OoT decomp on Saturn,
using imported original game logic with Saturn graphics/audio/file backends.
This is not a new standalone demo or a rewrite of OoT gameplay.

## Current priority

The prior sprite/CPU/save/cleanup checkpoint is now 9d384cd. The current
world-completion continuation is recorded in this checkpoint. The user authorized
commit/push and integration into main on 2026-10-04, preserving the prior main
as oot-vslice-demo and retiring dev, dev-gameplay and feature/kokiri-slice-actions.
Earlier build evidence below describes those prior checkpoints.

Latest human test: startup/each zone shows `dosei_allocator_free(): Null pointer`
about six times (22% dynamic memory, 0% sprite memory); one Ranch NPC visible;
generic-zone doors still unusable. Prior build/host success is not runtime
acceptance. Confirmed cleanup defect: story_route_free unconditionally frees
four Saria + two owl slots; SDK rejects NULL and test stubs missed this.
Cleanup guards were already present at the start of this continuation. Current
work additionally rolls failed story/emerald loads back and tests real failed
loads/retries with NULL/double-free rejecting stubs. Shared source-gated handle
doors/shutters, layer filtering, scripted entrance forwarding and whole-world
route auditing are implemented. Save v11 preserves old file versions and
adds generic source-scene flags, dungeon keys/items, bottles and era/time.
Same-room NPC spawns discover sheets; diagnostics separate actor, missing-sheet,
fallback-pose and allocated-slot counts. Automatic talk offers and Ranch milk
reward/textbox handshakes now use the original source identifiers.
400 distinct host checks pass. Full WSL asset regeneration and the final C-only
Clean relink pass (`world-completion-build.log`, `world-completion-link.log`).
The usual game-clean.cue/.iso is rebuilt; .bss ends 0x06083D70, 656 B below SGL.
Save state, separate write/preview scratch and draw-cache ownership now use
bounded, initialized low-RAM carves. Virtual story banks use IDs 1024+ and
C-prefixed files; real room banks no longer get overwritten. Staging/budget
checks pass and retired story aliases are removed. Previous margins below
are historical. Current memory headroom is small; preserve boundary checks.
Full world traversal and NPC coverage remain incomplete. Continue missing
destinations, special transitions, runtime horse logic, missing actors, dialogue,
rewards and resource gates. No complete-world or runtime acceptance claim.
The added Level Select option is **ALL ITEMS + MAX STATS**, default **NO**;
L/R toggles it and confirmed entry grants the test loadout. The user clarified
that quest items are required too: all stones (including Kokiri Emerald), songs,
medallions and other quest bits are granted, plus source inventory/equipment,
20 hearts, capped ammunition/magic, 500 rupees and eight source-debug small keys.
Upgraded items/final trade variants occupy the source's mutually exclusive slots.
No extra story completion flags are set. C actions for unimplemented weapons
remain unfinished despite their source inventory ownership. The existing fresh
test-run/no-backup-slot behavior remains; toggling alone never changes the save.
Detailed actionable handoff: [NEXT_CHAT_WORLD_COMPLETION.md](NEXT_CHAT_WORLD_COMPLETION.md).

Human confirms the 32-byte palette repair checks out in Mednafen. That graphics
repair is runtime-accepted. Checkpoint 9d384cd contains Ranch lookup/reservation
repairs, converted-cast model removal and baked fairy wings; the later report of
one Ranch NPC means full population/visibility is still unaccepted.
Permanent rule: NPCs/animals/fairies/non-boss enemies
use sprites; bosses are explicitly exempt to preserve complex damage/puzzle
hitboxes. Full era/layer/trigger coverage is planned in
[ACTOR_SPRITE_ROLLOUT_PLAN.md](ACTOR_SPRITE_ROLLOUT_PLAN.md). High CPU/slow
gameplay versus Kronos remains open. The accepted palette repair was pushed as
11312ec; subsequent Ranch/CPU/save/cleanup work is preserved in 9d384cd.
This checkpoint records the world-completion continuation after that baseline.
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

Earlier Mednafen/hardware evidence, retained as context for the priorities above:
VDP1 3D models and 2D sprites corrupt; slow title music/scenery startup; missing
nightmare riders; Navi opening memory error followed by skipped shots; house
exit failure. Latest human test: all opening sequences/shots now complete, but
Navi room reads pause the cutscene and music starts late. The later palette repair
now has explicit human graphics acceptance.
Earlier house exit showed CD read failures for CS4.BIN, then S1.OOC (not a
confirmed OOM). Latest human explicitly confirms opening the menu before music
now works. House-exit CD failure has no explicit acceptance yet. Latest forest
and nightmare screenshots still show severe VDP1 corruption before the CLUT fix.

## Current continuation: implementation and verification

Cleanup rollback/retry, common door policies, source save predicates, same-room
sprite discovery, automatic talk/milk handshakes and the opt-in full test loadout
are implemented, host-tested and included in the current Clean image. The final
target/staging checks pass after the RAM and virtual-bank repairs above.
No emulator was launched; human acceptance of these changes remains pending.

The source inventories enumerate 110 scenes and 429 actor profiles. Only 75
scene assets are registered: 35 source scene destinations still lack assets.
The actor ledger includes 836 room layers, conditions, dialogue/reward/drop
sites and conservative dynamic dependencies; zero scenes pass its ready gate.
Forty-one horse clips are baked offline (910,945 B total sheet storage including
allocator terminators; largest cel plus aligned CLUT 1,472 B). They are neither
runtime-imported nor staged. Eight generic sprite slots, 16 actor views, missing
actors such as En_Ma3 and unimplemented actions/branches remain coverage limits.

## Prior checkpoint implementation and verification

Evidence below belongs to checkpoints through 9d384cd. Build margins, test
counts and image contents describe those builds, not the current continuation.

- Ranch/sprite checkpoint: linked-symbol sprite keys fix the
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

- Sprite/save checkpoint: fairy flyby, Saria greeting and shopkeeper
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
- CPU checkpoint: heading conversion uses 32-bit range checks, shifts and
  slAtan on SH-2. Six software-double calls per heading are gone; matching
  game-clean.elf no longer links __floatsidf/__muldf3/__fixdfsi. Build log:
  build/cpu-heading-build.log. Main .bss 0x060838b0, margin 1,872 B (was 96 B).
  Host checks above pass; no emulator run or measured FPS gain. Other existing
  64-bit math remains migration debt. No wide-divide optimization was retained.
- Existing decomp integration and NPC sprites: see OOT_CORE_PIPELINE_PLAN.md.
  Sprite baseline is commit 8874db2; Kokiri was human-accepted in Kronos only.
- Allocator/CD checkpoint: allocator splits reused holes and merges adjacent free blocks
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
- Ranch sprite checkpoint (runtime pending): host loaded sheets before
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
- Checkpoint verification: two host regressions execute actual host lifecycle/load/upload/
  draw functions with deferred actors; four graphics regressions also pass.
  WSL Clean build passes, 96-byte high-WRAM margin, log
  build/mednafen-ranch-cpu-build.log. Cold clip/scroll loading code uses Os to fit;
  heap and SGL capacities preserved. That Clean image contained these changes.

## Next actions / remaining work

1. Preserve the passing combined Clean target/staging checks and the small
   656-byte high-WRAM margin. Startup/zone cleanup, new routes, save migration
   and NPC visibility still need eventual human acceptance. No emulator launch
   by agents. Keep the SDK error
   handler enabled. The later user request adds a Level Select max gear/hearts
   option (all items/quest items/stats), default No; entering with it enabled is
   the only grant trigger. Wallet cache/HUD now safely retain three-digit values.
2. Finish the source entrance graph. Current route audit separates structural
   reach from traversal acceptance and records every known missing destination,
   reverse edge, source gate and extraction error. Thirty-five absent scene
   assets, special grotto returns, alternate collision/spawn headers, transition cameras/fades and
   unimported scripted/warp actors remain blockers. Preserve keys and boss logic.
3. Review and extend the generated actor ledger across eras/time/story/dynamic
   triggers. Prioritize missing Ranch horse runtime and En_Ma3, then remaining
   actors/dialogue/rewards.
   Offline horse sheets and text on disc do not implement gameplay. Sprite banks
   must preload reachable trigger sets and budget scenery/actors/effects together.
   Eight generic slots and 16 views remain explicit limits, not full coverage.
   Debug target verification, sprite pitch views, non-boss enemy migration,
   player/camera/cutscene and combat bridge parity remain required. Preserve the
   20 Hz/input/hit-volume contract and boss exemption. Do not archive a replaced
   C system before human acceptance of its replacement.
4. Performance implementation remains open: establish per-displayed-frame CPU
   totals and draw-completion timing. Heading target verification is complete;
   next replace core wide arithmetic with bounded 32-bit math and pass prop matrices directly.
   Sprite pose separation is implemented for the current sprite NPC cast.
   Follow with compact scene culling and per-cel upload reduction (stable banks now implemented);
   assess per-cel cropping from the review's offline evidence. Preserve gameplay
   and the 20 Hz/input/hit-volume contract. Approximation is allowed; 64-bit
   fallback is not. A storage-width change needs matching collision/units and
   scene/object blob changes. Broad -O2 and relocating the whole blob are not
   validated solutions. Prior Clean work-RAM margin was 8,736 bytes;
   no new FPS or CPU-versus-VDP1 conclusion is established.
5. CD house-exit fix still needs verification; Navi room-read
   pauses and late music cues remain open. No intermediate test requests pending.
   Same-room NPC sheet discovery is implemented and host-tested. Reachable
   dynamic sets still need preloading and budgeting before triggers; discovery
   may read the CD at spawn. Missing clips/capacity have explicit diagnostics.
   Graphics/CD checkpoint 11312ec remains pushed and graphics accepted. Broader
   save/reload, dialogue and performance acceptance remain pending; host tests or
   a build do not prove that the overall slowdown is resolved.

Detailed handoff and historical evidence: OOT_CORE_PIPELINE_PLAN.md.
