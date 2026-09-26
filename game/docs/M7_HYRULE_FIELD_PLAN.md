# M7 draft: Hyrule Field exploration and ocarina free play

Astra side draft, 2026-09-25. Expands DEMO_PLAN M7 after reviewed M6b.

## Playable result and scope

Saria's bridge handoff reaches Hyrule Field, its introduction and the required
outside-Kokiri owl conversation/flight. Link can explore the agreed day-only Field,
return to Lost Woods, and play the Fairy Ocarina freely. Other exits show the agreed
demo-boundary message. No Field enemies, day/night simulation, new song progression
or destinations past the demo endpoint. Drawbridge remains static per scope.

The umbrella plan says "6 notes"; do not invent six independent note buttons.
Verified `include/ocarina.h` defines A plus four basic C buttons and a special
C_RIGHT_OR_C_LEFT case. Trace source pitch/modifier handling before specifying the
supported notes. Treat any intended simplification or extra-note request explicitly.

## Dependencies and contracts

M6 supplies bridge item/flag/destination state. M4 supplies inventory assignment,
C-up context routing and instrument entry/cancel ownership. Existing cutscene,
scene-streaming, collision, save and audio systems remain authoritative.

Resolve how all four C directions become notes while in instrument context;
ordinary C-up Navi/view behavior cannot steal a note. Digital pad uses C+D-pad;
3D Pad uses D-pad. A is the A note, not interaction while playing. L/Z/modifier
pitch behavior needs a documented source-to-Saturn mapping; do not assume normal
look/target handlers remain active. Exit restores controls with no queued attack,
move, item or dialogue action. No analog stick movement while instrument owns input.

## Source ledger

Local OoT root: `D:/Workspace-Claude/game-decomps/n64/oot`.

| Source | Required evidence |
|---|---|
| spot00 collision/headers/entrances and child-day actors | Full bounds, exit/spawn graph, surface/water and permitted population |
| gHyruleFieldIntroCs and conditional triggers | Once-only intro flag A0, destination and already-seen behavior |
| En_Owl placement 0x004C and En_Owl source | Outside-Kokiri dialogue, repeat choices, camera, fly-away and flags |
| Other placed owl params | Which are required/static/omitted under agreed scope; record individually |
| Audio ocarina code, include/ocarina.h, player/message handlers | Notes, pitch modifiers, timing, staff display and cancel behavior |
| Scene BGM and instrument sample/bank tables | Correct music/sample ownership, voice use and restoration |

Umbrella figures (one room, 1579 collision polygons) are planning inputs; measure
current export and renderer behavior. One scene room does not imply one affordable
resident texture or draw set. Use source-scale coordinates without float runtime.

## Delivery checkpoints

### M7a: Field budget and boundary graph

Measure actual geometry/texture/collision/command costs at representative dense,
long-view and near-ground positions. Confirm large-coordinate collision and distance
math remains in range. Keep global collision/exit semantics even if visual geometry
is partitioned into streaming zones.

Choose bounded culling/LOD/texture-bank policy from measurements, preserving shared
fog/flat-material rules. Do not redesign the renderer speculatively; follow the
foreground-warp failure record. Record every outgoing exit as return-to-Woods or
explicit demo boundary, plus safe approach/collision behavior.

Review: budget table, measured worst views, zone seam plan, valid return route and
boundary text policy. Memory overflow blocks delivery rather than triggering a
guessed heap cut or silent dropped geometry.

### M7b: gameplay Field and story handoff

Load the gameplay Field separately from any existing dream/cutscene-only asset.
Wire bridge -> intro -> owl area and return-to-Woods transitions. Intro A0 and
Fairy Ocarina state must survive reload; direct entry/re-entry must not replay the
bridge grant or force the opening. Shot skip preserves mandatory destination/flags.

Implement day BGM and source-required exploration collision/water/traversal. Add
honest boundary messages on other exits, with no route into missing content and
no message spam while standing in a trigger. World geometry/rendering and boundary
message UI remain separate; UI uses VDP2.

Review: natural arrival from M6, skip/no-skip, reload, return loop, every boundary,
zone edges, long movement and camera turns. This closes M6's live Field handoff.

### M7c: owl conversation

Port the required owl's source text tree, repeat choice, focus camera and departure
with real model/animations (flat except face). Finish/repeat choices must not be
inverted. Persist the correct flag and clean actor/audio/camera state on departure.

Decide remaining owls by the approved scope allowance: static talk or omitted,
explicitly listed; do not claim their full behavior. All menus/choices use VDP2.

Review: repeat then finish, cancel where permitted, slow text/input, reload before/
after departure and bank transitions without a stuck camera or voice.

### M7d: ocarina free play

Implement actual note-on/held/release, source-supported pitch/modifier behavior,
staff/cursor UI and sound. Budget SCSP sample/voice needs with current music and
area SFX; do not overwrite a live bank to fit instrument samples. Use bounded
fixed-step/clock timing independent of draw rate and release voices on exit/unload.

Staff and instrument UI use VDP2. No song grant, warp, time change or unavailable
quest effect from free-play sequences. Record unsupported source embellishments
instead of presenting a fixed sample as complete instrument behavior.

Review: both pad types, all basic notes, simultaneous-button priority, repeated/
held notes, cancel, hot unplug, pause/scene/death transitions and music restoration.

## Acceptance and later obligations

- Full agreed Field explore area reachable, stable collision at large coordinates,
  no visible streaming holes or invalid boundaries; no enemies/day cycle added.
- Bridge intro/owl flags and repeat conversation behave after save/reload.
- Lost Woods return works; every other exit communicates the demo boundary.
- Ocarina usable only when owned, no unintended movement/C-up hint while playing,
  sound/staff agree, no hanging voice after exit.
- M8 documents note/control and scope differences; M9 verifies full title-to-owl
  route and supported emulator behavior. Optional end card is not a release gate.

## Review and verification rules

Planning only; no implementation owner assigned here. Start code after preceding
milestone review and human owner assignment. Recheck current source and working
diff before taking files; M1/other active work stays with its owner. Dependencies
below describe required behavior, not permission for a parallel rewrite.

At each implementation checkpoint: focused host tests in separate processes,
**clean image only** per current human instruction, SGL map boundary, worst-room
VDP1 budget, cart bounds/heap high-water and audio bank bytes. Inspect changed
runtime hot paths for software float. Do not cut the malloc arena by guesswork.
Runtime checks use the project's non-focus-stealing workflow or human play;
report observed versus pending checks separately. No build/runtime checks were
performed for this draft. Source references are implementation research targets
unless explicitly marked verified; umbrella-plan actor lists are not spawn proof.

Record changed files, source parity, approximations, save compatibility, measured
budgets and deferred acceptance in OPUS_HANDOFF and VSLICEPROGRESS when code lands.
Code stays uncommitted for review unless human requests commit. Planning does not
complete a milestone or authorize the next one. All new actors include source
spawn/drop audits in the same task; characters use flat materials except faces.

All menus must use VDP2 for text, panels, icons, maps and cursors. Budget VDP2
storage/layers and restoration explicitly; no VDP1 menu textures or commands.
