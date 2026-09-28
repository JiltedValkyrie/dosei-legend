# C-Up camera modes and stable control dialogue

Status: implemented in code; target build/host checks pass; Kronos pending, 2026-09-28. Human accepts texture warp;
this task concerns truthful controls, interior views and text stability.

## Pre-change findings

- Know-It-All Brothers describe C-Up switching indoor/outdoor views, but the
  current indoor camera is already fixed overhead. Labels alone cannot fix
  an instruction for missing behavior.
- demo.c interior_camera always restores one scene-table camera. Its
  demo_first_person currently means crawling, not a general C-Up look mode.
- build_scene_backdrops supports ROOM_SHAPE_IMAGE SINGLE only, and rejects
  MULTI. One backdrop cannot support arbitrary camera rotation: world models,
  doorway geometry and furniture would stop matching the picture.
- OoT z_camera_data.inc.c maps PREREND_FIXED to Fixed3, PREREND_PIVOT to
  Unique7/Keep0, and PREREND_SIDE_SCROLL to Special6. These tables do not
  by themselves establish a second view or C-Up mode in every room. Trace
  player C-Up handling, room image selection and collision camera data before
  promising alternate views in any particular interior.
- main.c dialogue drawing blanks every dialogue row on every draw, then
  rewrites the name and page. User screenshots show lower lines disappearing
  while the same page remains. Clear/redraw during active VDP2 scanout is a
  strong suspect; confirm against page/reveal state and other text writers.
  Screenshots alone do not prove the entire cause.

## Implementation order

1. Stabilize dialogue independently of camera work. Record the current page,
   reveal count, speaker and choice; update only changed text rows. Keep the
   retained VDP2 text map intact between updates. Clear once on close/page
   transition; prepare replacement rows before a bounded VBlank update if
   needed. Cover bold-name glyph probing, pause restoration, shop choices
   and cutscene/file-select row ownership. Do not hide the bug by slowing text.
2. Audit each of the six interiors against OoT: source room shape, camera
   settings/data, alternate image indices and actual C-Up behavior. Record
   normal/talk/alternate availability per room. Extract existing alternate
   backgrounds where supplied, with the matching projection and camera.
   If a new angle needs artwork/geometry absent from source, identify that
   asset task explicitly; never rotate 3D actors over an unchanged picture.
3. Implement an explicit camera-mode state: normal, indoor alternate where
   supported, outdoor first-person, with talk/target/crawl/cutscene overrides.
   C-Up uses the existing abstract control input and honors Navi-call/context
   priority from source. Verify entry, exit/cancel, movement lock, recenter,
   pitch/yaw limits, collision, HUD and Link visibility from original code.
   Crawl first-person remains separate. Door/save-load/death resets must
   restore a valid mode and the matching backdrop; transitions must not mix
   one image with another camera for a visible frame.
4. Replace the temporary free-look control only after C-Up modes work. Route
   look axes through the new mode; remove the old hold-L free-look behavior
   and stale hints together. Preserve L/Z/R actions and existing item inputs
   according to the settled controls; do not casually remap other actions.
5. Apply the Bible's dynamic-label rule everywhere. Resolve action tokens
   using saved preset, pad mode and bindings before wrapping/pagination.
   Tutorial wording must describe implemented behavior in the current room:
   never promise a view that the room cannot provide. Retain the original
   lesson's meaning where its behavior exists; record any adaptation.

## Acceptance

- Hold each long Brother page on screen: no lines blink/disappear. Advance,
  cancel, change choice, reopen, pause/resume and change speaker cleanly.
- Every interior: correct backdrop/model/door alignment in each supported
  mode; inspect entry, exit, talking and return through both doors.
- Outdoors: C-Up first-person enters/exits reliably, camera cannot reveal
  Link's head interior or pass through walls; no conflict with Navi prompts,
  targeting, item use, swimming, crawling or an active message.
- Both pad modes, every label preset and custom jump: instructions match
  actual inputs; long platform labels fit without clipping.
- Check work RAM, cart/VDP2 image residency and VDP1 budget before adding
  assets. Latest recorded Clean gap is only 1344 B; remeasure after parallel
  work. Preserve existing hard limits. Rebuild only with Kronos closed.

## Implementation and source audit

- Text retains its VDP2 rows; unchanged rows receive no writes. Speaker probes
  use offscreen row 31. Close/owner transitions clear once; padded replacement
  rows remove old text. No reveal speed change.
- Original action tokens resolve in ui_preferences before wrapping. Runtime
  continuation pages preserve the original BOX_BREAK/rule/choice structure.
  Choice groups stay together. Cached rows use 1248 B of the retired cart text
  carve at offset 0x8000; fixed-carve size does not grow.
- z_play.c starts FIXED_TOGGLE_VIEWPOINT houses in PIVOT (camera index 1);
  C-Up toggles LOCKED (index 0). FIXED_SHOP_VIEWPOINT prohibits toggling.
  z_camera.c Camera_Unique7 supplies fixed eye, feet-following yaw, pitch
  `-rot.x*cos(yaw-rot.y)` and FOV 60. All five current pivot rot.x values are 0.
- Original z_vr_box.c CI8 panoramas reuse the opening's cube renderer and
  bank 4, with gameplay scene index as room-bank suffix. Three-face houses
  retain exactly the three source sides, not fabricated fourth artwork.

| Scene | Normal panorama asset | Faces | Pivot eye | Alternate |
| --- | --- | --- | --- | --- |
| Link | vr_LHVR | 4 | 0,34,0 | original overhead JPEG |
| Know-It-All | vr_KHVR | 4 | 130,32,0 | original overhead JPEG |
| Twins | vr_K3VR | 3 | -140,40,-24 | original overhead JPEG |
| Mido | vr_K4VR | 3 | -152,40,-24 | original overhead JPEG |
| Saria | vr_K5VR | 3 | -160,40,0 | original overhead JPEG |
| Shop | fixed JPEG | ? | camera 0 | unavailable by source rule |

- Outdoor first-person uses posed head focus, Subj3's five-unit eye distance
  and 45-degree FOV. Normal look input follows Player_Action_8084B1D8 /
  func_8084ABD8: full yaw, pitch tending toward stick position. Rates adapted
  from 20 to 30 Hz. Eye segment clips against camera collision. Link is hidden.
- Navi/message/target priority retained. View input consumes exit actions and
  movement; pause, damage, death, crawl and scene changes reset it. C-Up taps
  latch until a simulation step. Crawl camera remains separate.
- Lesson adaptations are explicit in build_dialogue.clean_pages: 0x103A uses
  menu page/confirm/assignment actions (modifier required on both pad modes);
  0x103B uses menu Cancel for the save prompt, not the source attack button;
  0x103D separates menu R from gameplay guard and omits unimplemented shield
  angle control; 0x103F describes a two-way indoor toggle from either view.
  Menu tokens ignore gameplay jump-button stealing. C-slot item usage is not
  advertised as implemented by the item lesson.
- L now toggles the minimap, making the Brother's source L lesson true.
  Source START spelling becomes an action token too. Presets label wiring;
  they do not remap the physical pad.

Remaining visual acceptance: the checklist above, especially backdrop/actor
alignment, long text stability and reset transitions. No Kronos pass claimed.
The source's animated camera-entry blend and separate interior talk framing
are not ported; view switches use the established synchronous scene loader.
Read failure restores the prior view; a failed restore reports a hard error.


## Final build evidence

Clean build completed with the concurrent Low Work RAM equipment move:
.bss ends 0x06080930, 14,032 B below SGL at 0x06084000. Same game-clean.cue.
New panorama textures occupy at most 135,168 B including palettes; 512
vertices / 128 quads maximum. Cached dialogue rows occupy 1248 B in cart.
Log: game/build/camera-clean-build.log. No software floating-point imports
in the rebuilt player_camera.o. Runtime alignment/frame-time checks remain
human acceptance, not inferred from these budgets or host tests.

## Human review, 2026-09-28

Human reports no dialogue flicker, correct dynamic labels and working interior
C-Up. Those checks pass for the tested session; broader pad/preset and outdoor
checks remain pending. Requested follow-up: bold speaker name and a small
vertical inset. Fixed the bold guard (unused destination is blank, not a
preexisting glyph); panel now extends 4 px above/below the same text rows.
Live read-only Kronos inspection confirmed ASCII glyphs contain 0/1 ink and
reserved 0xA1/0xA2/0xDF cells are empty, explaining the old plain-text fallback.
