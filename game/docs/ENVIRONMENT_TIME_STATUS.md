# Environment, time and distant landmarks - 2026-10-05

Human requested far volcano/ranch/castle landmarks without distance dither,
earlier terrain fog, ground-coloured lower sky and original time-of-day rules.
Human now requests promotion into usual Clean, broader ground quads, retained
castle/ranch walls and four dark horizon bands behind terrain/landmarks.
Human owns runtime checks; GUI fixtures remain deferred. The accepted central
184 geometry is preserved; outer visual panels use 1280-unit cells on original
planes. SORT_MIN replaces landmark centroid sort to avoid far-depth overflow.
Latest Clean passes (`build/field-orbit-fix.log`), with 608 B static
RAM spare. Sky helpers use Os/shared mixing, without new float/wide runtime
math or heap reductions. Twelve sky host tests pass; new horizon/wall runtime
appearance remains for the human. Human accepts the dark sky gradient; retain it.
Human reports the built dither band is not visibly obscuring the gap.
`field_haze.h` now prepares two upright Link-centred panels at3200 units,
with a shared on-screen centre edge, hardware mesh transparency and ordinary
world sorting/pitch. This tests a clipping hypothesis; runtime success is unproven.
No texture or sprite slot. Four executing haze/fade host tests
pass; combined Field/Link/owl/haze fits2475 polygons and2424 vertices. Target
build passes; runtime visibility remains unaccepted. Fog and distance mesh use Link-relative
forward depth, preserving near-Link terrain when the camera pulls back. The band
may obscure more distant terrain/landmarks; nearby world objects sort in front.
Runtime height, coverage and overlap need human checks. Earlier isolated evidence
below is historical.

## Implemented; v2 partly runtime-verified, v3 built but unrun

`tools/environment_source.py` imports the clock statements from NTSC 1.2
`z_kankyo.c`, frozen-room settings from `z_scene.c`, Sun's Song state changes
from `z_parameter.c`, and destination-layer/time handling from `z_play.c`.
Constants are resolved offline; new runtime math is 32-bit integer only.
The existing 20 Hz core owns advancement and returns day time to the host save.
Sky time is separate and can remain ahead in a frozen room. Scene and room
alternate-header fallback selects the actual time/room-type/sky commands.

The source version ordering matters: NTSC_1_2 is 4 and PAL_1_0 is 3, so the
source >= PAL_1_0 guards apply. Field speed is 10 per core update in daytime,
20 at night; acceleration >=400 is not doubled. Night thresholds, midnight
wrap, dialogue/pause/game-over gates and source credits exceptions are retained.
Frontend session resets are distinct from explicit cutscene sky assignments.
Destination entrance groups use current time/age rather than the loaded layer;
loaded door masks still use the resident layer. Sun's Song now requests source
400-speed advancement, frozen-room reload or dungeon-special state. The human's
Song of Time child-to-adult shortcut remains unchanged.

`environment_sequence_source.py` imports the original nine-state natural-day
sequence and its scene-sound initialization. Natural dawn increments the source
day counters, sets the session dog-lost flag true, and hatches eligible trade eggs
through the persistent C inventory adapter. The original hatch order, dialogue
and player-state gates are retained. Source dawn/dusk crow/dog effects and the
delayed frozen-room transition effects are separate from clock advancement.
The existing C field-music owner still handles BGM; the original BGM/nature
channel handoff is not imported by this sequence extraction.

Save v13 adds the two 32-bit source counters (`totalDays`, `bgsDayCount`).
Versions 2-12 migrate with zero counters while preserving their existing data.
Dog-lost state is session-only, resets on frontend session start, and persists
across ordinary scene changes. Trade hatching updates the existing saved trade
slot; a rejected or stale replacement does not report a successful hatch.

`build_cutscenes.py` now preserves CS_TIME with the source's separate f32
truncations and minute+1 convention, baked to an integer. The cutscene player
also executes TIME_ADVANCE_TO_NIGHT throughout its source frame range. The
current supported scripts contain no CS_TIME; future imported scripts can use
it. This does not import every source cutscene/environment command.

Sky: 458 B of read-only data hold original clear/overcast schedules, sampled
source sky colours and dominant opaque ground colours for 75 scenes. Source
scene sky identity/config and room disable flags select the theme; retained
weather initialization is imported. Lower half is the map's ground colour;
Field is RGB555 0xA650. Twenty-five no-floor/panorama entries use an explicit
fallback. The gradient is an approximation of the original textured skybox.
Dynamic weather transitions and source world-lighting tint remain open.

Landmarks: three dedicated retained pieces replace the same 84 source triangles
in the normal/LOD2 terrain path. Fifty draw faces, 49 private 16x16 tiles,
7,840 B before removal savings. Mountain body cutouts stay opaque; smoke keeps
authored transparency. Runtime tags bypass distance dither and palette fog,
use a separate 26,000-unit range, and retain normal SGL occlusion/sorting.
Field terrain fog now targets its ground colour over 1,800-4,500 units; dither
starts at 4,000. The terrain draw limit remains 9,000. No extra ground splits.

## Evidence

- 10 clock/source host tests: ordinary cadence/gates, sky hold, frozen room,
  Sun's Song, destination layers, source integer conversion.
- 7 natural-day sequence host tests cover source state transitions, scene-sound
  initialization, forced-sequence cases, dawn counters and hatch gates. All 246
  extracted scene sound headers parse.
- 3 core dialogue/save-mirror/hatch tests; 38 save-format and migration tests;
  low-RAM and save-scratch ownership tests pass. These checks cover the new v13
  counters and persistent egg replacement.
- 7 scene/room sky-selection tests.
- 11 sky bake/helper tests; 4 explicit cutscene-time tests. The broader changed
  cutscene group has 47 passing checks including those four.
- 12 landmark/stream host tests. Canonical WSL landmark bake and exact baseline
  comparison pass: zero unrelated full-detail geometry/texture changes and
  zero shared landmark/terrain palette slots.
- New 184 positional sweep: 1,023 polygons, 1,478 vertices, 1,042 slots,
  340,512 / 445,432 B VRAM, 60 objects (old capacity 59 raised to 60).
- Initial clock-only target passed with 9,072 B below SGL. An earlier combined
  target then passed with only 32 B below SGL. Visible-GUI fixtures on that
  combined image measured +200 daytime and +400 nighttime clock units per 30
  control steps; the separate sky-time hold also passed.
- Corrected v2 runtime fixture passes +200/+400 cadence, held sky time, pause
  freeze for 60 steps and one natural-sequence increment of both day counters.
  Evidence: `build/square-retopo/r2-184/verification/environment-v2b/clock.json`.
  Dawn/dusk/noon/night captures are in the same folder. File reload and trade
  hatching remain host-tested only.
- Latest combined v3 WSL build exits 0, .bss ends 0x06082BA0, 5,216 B below SGL.
  Build-only refresh also passes: `build/square-retopo/r2-184/environment-final-build.log`.
  Same boundary; image remains unrun. Human owns landmark verification.
  v2 movement: 90 steps in 5.766/5.781 s, comparable to loader-only184 5.781 s.
- Far landmark captures remain inconclusive. Static SGL disassembly identifies
  SORT_CEN's signed 32-bit four-depth sum overflow at mean z8192. Far mountain
  faces reach z12615-13869. SORT_MIN/MAX avoid this sum but no fix is applied.
  Central castle at z8139 still needs targeted emission/visibility tracing.
- Adult pause equipment host checks pass: 15 renderer and 12 pause/health/bake
  cases. Owned child gear remains visible but dim when age-ineligible; adult
  Master Sword/Hylian Shield names, icons and equipped frames are checked. The
  page cache refreshes when age/ownership changes. v2 screenshot verifies dimmed
  child gear and equipped Master/Hylian frames. Hylian front no longer shows its
  wood back through it; Master Sword action icon is correct. Seven shield and
  fourteen HUD bake tests plus the C HUD compositor test pass. Initial equipment
  cursor follows the equipped sword in v3, not yet runtime-tested. Held Hylian,
  Mirror and Biggoron HUD GUI checks remain pending.

API version 20, its entry table, and expanded OOC scene/room records require a
coordinated host/core/all-OOC rebuild. Do not mix old OOC files with this core.
Evidence and runner: `build/environment-landmarks/r2-184-wsl/`,
`build/square-retopo/r2-184/environment-source.json` and environment build log.

## Open before claiming complete source time/environment parity

On resumption, regenerate hash-matched v3 symbols before GUI telemetry. Finish
equipment and targeted landmark checks; do not repeat passed clock fixtures
without relevant changes. Exercise saved counter reload and eligible trade-item
hatch in the target before calling those paths runtime-verified. Original song-effect
delay and source 30-frame audio fade are not yet reproduced. Dungeon-special
state is present, but native C enemy stun is not wired. Natural day-state logic
is imported, while original BGM/nature-channel sequencing remains with the C
music adapter and needs a separate ownership integration. Weather transition
timers, world lighting, the original skybox renderer and full cutscene environment
ownership remain incomplete; native C cutscenes do not yet run the complete
normal 20 Hz source environment lifecycle. Source conditional entrance cutscenes
are not all wired. Unknown debug entrances can reload the resident scene for a
frozen-room song, but cannot select an unrecorded day/night entrance group.
Do not describe this as exact whole-environment parity.
