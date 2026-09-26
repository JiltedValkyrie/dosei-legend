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
