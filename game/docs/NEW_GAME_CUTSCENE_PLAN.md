# New Game Menu + Opening Cutscene — 1:1 N64 Plan

## Context

`game/docs/refs/cutscenes/new-game-cutscene-storyboard.png` (14 panels) specifies the
whole N64 new-game flow: PRESS START → file select → "Open this file?" → Deku Tree
narration over black → Link's house from above (sleeping) → Hyrule Castle drawbridge →
Ganondorf + Zelda ride → grey "Navi, where art thou?" → Deku Tree speech to Navi →
first-person Navi flight through Kokiri Forest → into Link's treehouse → coloured Navi
dialogue → Link sits up → gameplay with Navi following.

Today the game has **no cutscene system and no game-mode state machine**: title and file
select are two bools (`title_visible` / `file_select_visible`) in
[demo.c](game/src/demo.c). Target is **1:1 functional and story parity**; graphics,
performance and optimisation are explicitly not gates. Flat-shaded stand-in geometry is
approved by the storyboard itself (panel 5).

This lands `OOT_PROGRESSION_PLAN.md` Phase 5 (cutscenes) plus the Phase 2/3 bits the
opening needs, ahead of Phase 4 actors.

**User decisions (confirmed):** bake the real OoT cutscene data; flat-shaded real
geometry for new scenes; per-character VDP2 palette for coloured text; add music banks
and swap per beat.

## The real N64 chain (verified in the decomp, ntsc-1.2)

All four cutscenes are plain parseable macro arrays under
`D:/Workspace-Claude/game-decomps/n64/oot/extracted/ntsc-1.2/assets/scenes/`:

| # | Cutscene file | Content | Exit |
|---|---|---|---|
| 1 | `indoors/link_home/gLinkHouseIntroSleepCs.csdata.inc.c` | text `0x109D`,`0x109E`,`0x109F` (Deku Tree narration); `CS_TRANS_BLACK_FILL_OUT_TO_HALF` f55, `..._IN_FROM_HALF` f230 | `CS_DESTINATION(CS_DEST_HYRULE_FIELD_INTRO_DREAM, 280)` → `TRANS_TYPE_FADE_BLACK_FAST` |
| 2 | `overworld/spot00/gHyruleFieldIntroNightmareCs.csdata.inc.c` | 65 cmds, 3 actor-cue lists (Ganondorf, horse, Zelda+Impa), 23 transitions, 11 rumbles; `CS_START_SEQ(NA_BGM_OPENING_GANON, 330)` | `CS_DESTINATION(CS_DEST_KOKIRI_FOREST_INTRO, 540)` → `TRANS_TYPE_FADE_WHITE` |
| 3 | `overworld/spot04/gKokiriForestIntroNaviFlyingCs.csdata.inc.c` | text `0x1099` (grey "Navi, where art thou?"), `0x109A` (10-page Deku Tree speech with `COLOR(LIGHTBLUE)`/`COLOR(RED)`); `CS_STOP_SEQ(NA_BGM_DEKU_TREE_CS,192)`, `CS_START_SEQ(NA_BGM_NAVI_OPENING,200)` | `CS_DESTINATION(CS_DEST_LINKS_HOUSE_INTRO, 940)` → `TRANS_TYPE_FADE_BLACK` |
| 4 | `indoors/link_home/gLinkHouseIntroWakeUpCs.csdata.inc.c` | `CS_HEADER(11,3000)`; text `0x1095`,`0x1096`,`0x1000`,`0x1098`; 8 actor cues (Navi); 5 player cues; `CS_MISC_STOP_CUTSCENE` f647 | gameplay in Link's house |

Text source-of-truth already parsed by this project:
`extracted/ntsc-1.2/text/message_data.h` — retains `COLOR()`, `SHIFT()`, `BOX_BREAK`,
`BOX_BREAK_DELAYED(40)`, `FADE(70)` as plain macros.

Player cues map to real clips (`z_player.c:15039-15042`): `clink_op3_wait1` (sleeping),
`negaeri` (roll over), `okiagari` (sit up = panel 13), `tatiagari` (stand up).

Reference engine: `src/code/z_demo.c` (`sEntranceCutsceneTable` :120, destinations
:719/:726/:890), `src/code/z_cutscene_spline.c`, `include/cutscene_commands.h`.

## Approach

Everything expensive happens **offline in Python** (floats allowed); the SH-2 runtime
only steps integer tables. This mirrors the existing
[build_title_paths.py](game/tools/build_title_paths.py) → `build/generated/title_paths.h`
→ `title_showcase_camera()` ([demo.c:102](game/src/demo.c#L102)) pattern, which is the
one scripted-camera primitive already proven on target.

## Phases

### Phase A — game mode state machine (no new content)

Replace the two bools with the explicit mode `OOT_PROGRESSION_PLAN.md:124` already
specifies: `TITLE → FILE_SELECT → LOADING → PLAY → PAUSE → DIALOGUE → CUTSCENE →
GAME_OVER`.

- New `game/src/game_mode.c/.h` — platform-free enum + transition table + host test.
- [game/src/demo.c](game/src/demo.c): `demo_init` :337, `demo_update` :396,
  `enter_world` :221, `take_door` :198 switch on the mode; keep
  `demo_title_is_visible()` / `demo_file_select_is_visible()` as thin shims so
  [main.c](game/src/main.c) gating (:174, `dialogue_box` :261, `inventory_menu` :324,
  `file_select_screen`, `action_hint` :386) keeps working unchanged.
- Add a screen fade primitive (VDP2 colour-offset / back-screen ramp) for
  `TRANS_TYPE_FADE_BLACK` / `FADE_WHITE` / `BLACK_FILL_*_HALF`; scene transitions
  currently have no fades at all.
- New test `game/tests/test_game_mode.py`.

### Phase B — file select parity (storyboard panels 1–2)

[game/src/file_select.c/.h](game/src/file_select.h) already has 3 files, cursor rows and
ERASE_PICK/ERASE_CONFIRM. Missing for 1:1:

- New mode `FILE_SELECT_OPEN_CONFIRM` — "Open this file?" with the file's name, hearts
  and rupees, and a **Yes / Quit** pair (A-Decide, B-Cancel), entered from `CHOOSING`
  on A, returning `START_NEW`/`START_LOAD` only after Yes.
- Row labels for `COPY` / `OPTIONS` exist on N64. `file_select_copy_supported()` returns
  false today — show the rows, and on select print the honest "not implemented" notice
  rather than silently doing nothing. Flag as the one known non-1:1 item.
- Renderer `file_select_screen()` in [main.c](game/src/main.c) gains the confirm panel.
- Extend `game/tests/test_file_select.py` (existing host fixture
  `tests/fixtures/save_device_fake.c`).

### Phase C — text layer: cutscene messages + colour (panels 3, 7, 8, 9, 12)

All text today is VDP2 NBG0 ASCII via `jo_printf`, 4 lines, ≤34 cols, no colour.

- New `game/src/message.c/.h` — an OoT-shaped message player replacing ad-hoc printing:
  page list, `BOX_BREAK` (wait for A), `BOX_BREAK_DELAYED(n)` (auto-advance after n
  frames), `FADE(n)`, `SHIFT(n)` → column offset, box types `BLACK` / `NONE_BOTTOM`
  (panel 3, no box) / `NONE_NO_SHADOW` + `POS_MIDDLE` (panel 7 grey screen).
- **Colour:** per-character palette indices on NBG0 — **Jo already supports this**.
  `jo_printf_with_color(x, y, COLOR_INDEX, ...)` and `jo_set_printf_color_index()`
  exist in `joengine/jo_engine/jo/tools.h:131-136`, with indices in
  `jo/colors.h:45-51` (White/Black/Red/Green/Yellow/Blue/Purple). So `COLOR(RED)` maps
  straight to `JO_COLOR_INDEX_Red` and `COLOR(LIGHTBLUE)` to `JO_COLOR_INDEX_Blue`
  (recolour that palette entry to OoT's light blue). No new VDP1 texture VRAM — which
  matters, the tightest room has only ~5 KB spare. Wrap as
  `message_print_colored(x, y, runs)`: split each line into `(text, colour)` runs and
  emit one `jo_printf_with_color` per run at the right column. **Confirm the colour
  index persists per character in the pattern-name table rather than being global to
  the layer — verify on the first Kronos run**; if it is global, fall back to one
  colour per line.
- [build_dialogue.py](game/tools/build_dialogue.py) gains a colour-run emitter (it
  already parses this exact file and currently drops the tags) — extend
  `dialogue_page_t`/`dialogue_lines[]` with `(offset, length, colour)` runs so ordinary
  NPC dialogue gets colour for free.
- Tests: `game/tests/test_message.py` (page/timing/colour-run splitting, host).

### Phase D — offline cutscene baker

New `game/tools/build_cutscenes.py`, modelled on `build_title_paths.py`:

- Parse the four `.csdata.inc.c` macro arrays (plain text, no ROM read needed).
- Evaluate `CS_CAM_EYE_SPLINE` / `CS_CAM_AT_SPLINE` with OoT's own spline math
  (port `src/code/z_cutscene_spline.c` to Python) and emit **per-frame integer
  eye/at/roll/fov** in the same `{x,y,z,yaw,pitch}` shape as `title_point_t`.
- Emit a timed integer event list: `CS_TEXT`(id, start, end) / `CS_TEXT_NONE`,
  `CS_ACTOR_CUE`(id, start, end, rot, startPos, endPos → per-frame lerped integer
  positions), `CS_PLAYER_CUE` → our clip ids, `CS_TRANSITION`, `CS_START_SEQ`/
  `CS_STOP_SEQ` → our music bank ids, `CS_MISC_STOP_CUTSCENE`, `CS_DESTINATION`.
- **Ship the tracks as CD data files, not linked arrays.** Total baked length is roughly
  540 + 940 + ~650 + ~790 ≈ 2,900 frames; at ~10 bytes per frame that is ~29 KB of
  camera track alone (`gHyruleFieldIntroNightmareCs` has 13 eye + 13 at splines /
  220 points; the Navi flight has 140 points over 940 frames). The `.bss`-to-SGL gap is
  only ~24 KB, so emit `CS1.BIN`..`CS4.BIN` and load each one on demand into cart RAM
  through the existing `scene_flow` disc-read path. Only the small event lists get
  linked as `const`.
- **Cutscene frames are OoT's 20 Hz cutscene tick, not 60 Hz** (`R_UPDATE_RATE`).
  Resample to our rendered frame rate in the baker so the runtime never divides.
- Output `game/build/generated/cutscenes.h/.c` (event lists + a manifest of the .BIN
  files) with a sha256 cache header, same trick as `build_title_paths.py`.
- Drop the commands genuinely inapplicable on Saturn (`CS_RUMBLE_CONTROLLER`,
  `CS_UNK_DATA`) and record them in the generated header comment.
- Tests: `game/tests/test_cutscenes.py` — frame counts, monotonic timing, destination
  chain 1→2→3→4, and the exact text ids per beat.

### Phase E — runtime cutscene player

New `game/src/cutscene.c/.h` — a small integer interpreter, no floats, no script
parsing, no N64 segment pointers:

- `cutscene_start(id)` / `cutscene_step()` / `cutscene_is_playing()`; one frame counter,
  one cursor per event list.
- Drives: camera (set eye/at directly, bypassing
  [shared/lib/camera/oot_follow.c](shared/lib/camera/oot_follow.c)), `message.c`,
  actor cue positions, `music_fade_to()`, the Phase A fade, and on `CS_DESTINATION` the
  scene load + next cutscene.
- Input: A advances `BOX_BREAK`; the intro is `UNSKIPPABLE` in the original, so no skip
  (matches 1:1).
- Hook: new game from the file select starts cutscene 1 instead of
  `enter_world()`; on `CS_MISC_STOP_CUTSCENE` set
  `EVENTCHKINF_DEKU_TREE_INTRO_CS_SEEN` (already defined,
  [save_state.h:55](game/src/save_state.h#L55)) and enter `PLAY`.
- Tests: `game/tests/test_cutscene_player.py` — step the whole chain headless and assert
  the beat order matches the storyboard.

### Phase F — new content

- **Scenes (flat shaded, per storyboard panel 5):** extend
  [build_scene_table.py](game/tools/build_scene_table.py) with `spot00` (Hyrule Field /
  castle drawbridge) and the Great Deku Tree meadow, texture-free. Only the shot
  frusta need geometry — cull to what the baked camera actually sees to protect the
  512 KB VDP1 budget. Keep the VDP1 budget guard on; never disable it.
- **Link's house stays a backdrop interior — verified, not assumed.**
  `link_home_room_0.inc.c` uses `SCENE_CMD_ROOM_SHAPE(...RoomShapeImageSingle)` →
  `ROOM_SHAPE_TYPE_IMAGE`, so the original is a prerendered-background room too, and our
  `SCENE_LINK_HOME` interior path already matches it. The wake-up CS camera confirms it:
  every `CS_CAM_POINT` holds eye at `(0, 34, 0)` and varies only the trailing field.
  So no geometry extraction and no VDP1 cost for panels 4/12/13/14.
  The one thing to check: panels 12–13 frame the bed more tightly than panel 4's
  top-down view. If the baked camera's fov/roll changes imply a different framing,
  bake the extra views as additional stills via
  [build_scene_backdrops.py](game/tools/build_scene_backdrops.py) (`S0R0.RGB` → one file
  per shot) and switch them on cutscene cue. Note NBG1 is shared with the title art and
  the panel-3/panel-7 full-screen text backgrounds — only one can be resident, so
  sequence the loads.
- **Link clips:** extend [build_link_model.py](game/tools/build_link_model.py) with
  `clink_op3_wait1` (sleeping), `negaeri`, `okiagari` (sit up, panel 13), `tatiagari`,
  added to `link_clips.h` and `link_anim_state.h`.
- **Ganondorf / Zelda / Impa / horse (panel 6):** flat-shaded models driven purely by
  baked actor cues — no AI, no actor pool needed. This is deliberately ahead of Phase 4.
- **Navi:** a real actor. Billboard reusing `FAIRY.RGB`
  ([kokiri_sgl.c:141](game/src/kokiri_sgl.c#L141), `kokiri_fairies_draw()` :954), driven
  by baked cues during cutscenes and by a simple follow behaviour in `PLAY` (panel 14).
- **Panel 10 first-person Navi flight:** the baked spot04 camera track — spot04
  geometry already exists, so this is nearly free.

### Phase G — music

Sequences required: `NA_BGM_OPENING_GANON`, `NA_BGM_DEKU_TREE_CS`, `NA_BGM_NAVI_OPENING`.
Sound RAM is 512 KB with one ~480 KB bank resident and **104 bytes spare** in the SFX bank.

- Add three banks to [game/src/music_banks.c](game/src/music_banks.c) via the existing
  `build_kokiri_audio.py` pipeline; stream from CD and swap per beat with
  `music_fade_to()`, exactly as title→forest does today ([demo.c:230](game/src/demo.c#L230)).
- A swap stall/gap at a beat boundary is accepted (cutscene beats are fade-covered,
  and performance is explicitly not a gate). SFX are already suppressed while
  `music_busy()`.
- Risk: each bank is a CD asset; check disc size after adding.

## Files

New: `game/src/game_mode.{c,h}`, `game/src/message.{c,h}`, `game/src/cutscene.{c,h}`,
`game/tools/build_cutscenes.py`, `game/tests/test_{game_mode,message,cutscenes,cutscene_player}.py`.

Modified: [game/src/demo.c](game/src/demo.c), [game/src/main.c](game/src/main.c),
[game/src/file_select.c](game/src/file_select.c), [game/src/scene_flow.c](game/src/scene_flow.c),
[game/src/music_banks.c](game/src/music_banks.c), [game/src/kokiri_sgl.c](game/src/kokiri_sgl.c),
[game/tools/build_dialogue.py](game/tools/build_dialogue.py),
[game/tools/build_scene_table.py](game/tools/build_scene_table.py),
[game/tools/build_link_model.py](game/tools/build_link_model.py).

## Verification

Per phase, proportionate only (project rule: do not overtest):

1. `python -m unittest discover -s game/tests -p "test_*.py"` — currently 305 tests,
   304 pass + 1 legacy skip. Keep that baseline.
2. Build all three variants: `$env:OS='Windows_NT'; .\game\build.bat`, then
   `-Variant clean`, `-Variant hires`. Check the **final** `build_sgl_area.py --verify
   --map` boundary and exit code, not the pre-compile print. Gap was 24,080 bytes; the
   cutscene tables and new text must not close it.
3. Kronos run (`game/run-kronos.bat`, `Cartridge/Type = 7`): PRESS START → file select →
   "Open this file?" → Yes → watch the full chain to gameplay in Link's house with Navi
   following. Background capture only, via `game/tools/capture-kronos.ps1` — the user is
   playing another game; do not take foreground focus or send global input.
4. Report per beat which panel was seen and which were not. A successful build is not
   evidence the cutscene plays.

## Known non-1:1 items to flag, not hide

- File select **COPY** and **OPTIONS** are not implemented (pre-existing).
- `CS_RUMBLE_CONTROLLER` has no Saturn equivalent on a digital pad.
- Flat-shaded castle/meadow geometry, per the storyboard's own instruction.
- Near-camera texture warping (`game/docs/FOREGROUND_WARP_FAILURE_2026-09-18.md`) is a
  separate open bug; do not attempt to fix it inside this work.

## Branch

Create and switch to `feature/new-game-cutscene` off current `main`
(`8d349d8`) as step 0. Uncommitted `.gitignore` change and the untracked
`game/docs/refs/cutscenes/` carry over.
