# Current handoff: full OoT recomp

## Next step: mandatory core Player migration (2026-10-06)

Claude: human requires replacing handwritten C Link with real core/decomp Player.
This is mandatory, not conditional on which collision benchmark wins. Preserve
every existing Saturn adaptation, Link fix and added feature on top of the source
implementation. First inventory behaviors and map current code/tests to new
owners; then migrate in stages while retaining Saturn rendering and backend.
One authoritative Player and collision world is the destination. Importing only
queries or growing bridge_player.cpp does not finish it. Preserve gameplay timing,
input edges, combat/rewards, both eras, gear and the added controls/camera behavior.
Retire replaced C paths after runtime/human acceptance; do not silently lose a fix.

Follow [the complete migration rules](RECOMP_PLAN.md#mandatory-link-migration-next-step).
Temporary gallery bridge rebuilds triangles even for unchanged transforms; Y-only
rotation, X-only scale, omitted water/camera data and absent rider feedback limit
its scope. Measure total collision/update cost; results guide core optimization.
Native SH-2 products are allowed; software-wide/soft-float helpers remain banned.

This handoff update is documentation only. No migration implementation, new tests,
build or runtime check. Human relays this message; Claude starting is unconfirmed.
The earlier source-only Wave 0 instructions below are historical, superseded by
recorded Fx32/build progress and this new implementation priority.

## Historical Wave 0 handoff (2026-10-05)

Claude: human confirms the full OoT recomp for Saturn. Use "full recomp",
"game", "implementation wave" and "opening route" in plans and handoffs.
Kokiri through the opening route is implementation order only. Every scene,
child/adult era, day/night/story layer, actor and game system remains in scope.
Carry this wording into the external actor/Fx32 plan.

Astra's call, at the human's request: GO for Claude's Wave 0 source work only.
Implement bounded Fx32 and its consumers together, including bgcheck_bounds.h
and oot_math.cpp square-root, trig interpolation and angle conversion paths.
Review constructors, mixed integer operations and angle wrapping as well as
distance/collision bounds. Keep every intermediate bounded to 32 bits.
Prepare checks for the same collision contacts and range/talk behavior;
host probes compile code, so their execution also waits for build approval.
No build or bake until human says. Actor imports and scene packs wait for
verified Wave 0. Claude starting work is unconfirmed; Astra has no parallel
source task. Relay this call through the human's normal copy/paste channel.
Subsequent human naming request (2026-10-05): renamed the game plan to
RECOMP_PLAN.md and the project runtime files/symbols, asset tool/test and probe
include to recomp names. All project callers/build refs/tests/docs updated.
Use src/recomp.c and src/recomp.h; no compatibility aliases under old names.
Original decomp symbols and archived Git/artifact names are preserved.
Static checks only; no build, bake or runtime check. Rebuild before using new
probe symbol names against a binary. Claude: use these paths for Wave 0 work;
carry the plan path into the external plan. No Fx32 implementation by Astra.

## Historical paused handoff: environment, equipment and Field

Historical handoff, superseded by the later same-day Clean request. Human now
authorizes accepted quad ground in Clean, coarser whole-Field ground coverage,
persistent castle/ranch walls and dark horizon bands. See RECOMP_PLAN.md and
FIELD_SQUARE_RETOPO_STATUS.md for current implementation/build state. Do not
resume the old GUI fixtures; human owns runtime acceptance.

Human resumed, then narrowed scope to build only (2026-10-05).
Human owns landmark checks. Do not launch Kronos or run the queued GUI fixtures.
No commit or promotion made. Usual Clean/Debug, TR checkpoint and main layout
selection remain preserved. Shared tree includes Claude's uncommitted retopo
work plus Astra's environment/equipment changes; do not broadly revert or stage.
Kronos is closed. Latest WSL build finished successfully; no test is running.

## Built image and evidence

- Latest image: `game/build/square-retopo/r2-184/oot-sat/game/build/game.cue`.
  Environment-v3 build succeeded, .bss end0x06082BA0, 5,216 B below SGL.
  Build-only refresh passed: `game/build/square-retopo/r2-184/environment-final-build.log`.
  Same .bss boundary; image rebuilt without a GUI run or gameplay changes.
- v3 has NOT run. Relative to tested v2, it selects the equipped sword as the
  initial pause equipment cursor and adds per-landmark trace filtering.
- Last runtime evidence: `game/build/square-retopo/r2-184/verification/environment-v2b/`.
  `clock.json`: +200 day/+400 night per30 steps, separate sky-time hold,
  pause frozen60 steps, both natural-sequence day counters increment once.
  Noon screenshot shows clean Hylian front and correct Master Sword action icon.
  Pause screenshot shows dim age-ineligible child gear, equipped Master/Hylian.
  90-step walks:5.766/5.781s versus loader-only184 5.781/5.781s.
- More implementation/tests: `ENVIRONMENT_TIME_STATUS.md`,
  `FIELD_LANDMARK_AUDIT.md`, `FIELD_SQUARE_RETOPO_STATUS.md`.

## Equipment side fix

Human owns/equips Hylian only. The brown patch is the SAME model's wood back,
not an extra Deku shield. Baker previously marked both surfaces Dual_Plane.
`build_link_gear.py` now marks only shield surfaces Single_Plane; `gear_draw`
recomputes their normals after skinning using `link_shield_normal.h` (bounded
32-bit cross products, no new wide/float/divide). Hands/swords remain unchanged.
Freeze changes only114 attribute bytes, no geometry/skin/texture/CLUT changes.
Seven focused host tests pass. Target helper uses six mul.l and existing32-bit
shift helpers. Stowed front passed visible GUI; held and Mirror remain pending.

`build_gameplay_hud.py` previously hardcoded Kokiri Sword. Baked patches now
select none/Kokiri/Master/Biggoron from actual equipment, retaining all controller
labels and action captions. `minimap.c` refreshes on weapon identity changes.
BUTTONS.MAP14288B fits14KiB; composed C-item banks moved to0x25E4B800, ending
0x25E4D800, below hearts0x25E50000. Fourteen HUD bake tests and C compositor pass.

Pause uses live gear, age eligibility, names/equipped frames and correct cache
invalidation. Owned unavailable kid gear stays dim.27 pause/health tests pass.
v3's cursor correction in `gameplay.c` starts on the equipped sword; unrun.

## Deferred checks (not part of the build-only request)

1. Equipment verification only: regenerate exact v3 SH-COFF symbols and their
   ELF hash first (`environment-symbols.json` currently belongs to older build).
   Launch the real configured visible GUI via
   `game/tools/control_probe/launch.ps1 -Run game/build/square-retopo/r2-184`.
   Set CONTROL_RUN to that run path. Wait for mailbox ready, then run ignored
   `game/build/square-retopo/compare_equipment.py`. It uses normal pause inputs,
   checks Master/Hylian, held shield, Biggoron HUD and Mirror, then restores
   Master/Hylian. Inspect captures; script is prepared, not previously run.
2. Far landmarks only: run ignored `game/build/square-retopo/compare_landmarks.py`
   against v3. It selects each landmark in diagnostic HUD bits11..12 with bit1024
   enabled; output `verification/environment-v3/`. Previous first10 rows mostly
   sampled ranch and cannot establish mountain/castle rejection.
   Concrete static blocker: SGL SORT_CEN signed sum overflows at mean depth8192;
   far mountain mean12615-13869. SORT_MIN/MAX avoid sum, but sorting change is
   NOT implemented or tested. Central castle depth8139 is below threshold and
   needs separate command/occlusion inspection (expected42x26 native pixels).
3. Source environment follow-ups: v13 actual file reload and trade hatch target
   checks. Original BGM/nature handoff, song-effect delay/audio fade, enemy stun,
   weather/world-light tint and full native cutscene lifecycle remain open.
   Do not claim exact whole-environment parity or redo already-passed cadence
   fixtures unless relevant code changes.
4. Ground extension is separate: central184 is human-accepted. Bad north7067
   and castle2940 are outside it. Bounded adjacent extension only priced;
   not implemented. Preserve existing collision/STM/OOC single-source pairing.

## Build and harness details

Canonical builds/bakes use WSL, one WSL process at a time. Do not overwrite
mounted discs. Never launch hidden/private Kronos. AdultYes/AllItemsYes fixture
is authorized, with bounded normal mailbox controls; human sees same window.

Symbols: Linux `sh-elf-nm --target=coff-sh -n game.elf` to run's `game.symbols`;
write `environment-symbols.json` with `elf_sha256` and full `nm` text. Windows
nm cannot read this SH-COFF. Current symbols must match current ELF.

Ignored orchestration scripts under `game/build/square-retopo/`:
`sync_environment.py` copies explicit main sources into isolated checkout and
reinstalls probe hooks, preserving first backups; `bake_equipment.py` rebakes
gear/pause and stages corrected HUD; `bake_equipment_hud.py` makes canonical HUD.
`r2-184/environment-source.json` and `equipment-assets.json` record provenance.
Do not need a fresh bake just to run already-built v3.

Probe fixes: Start has a separate input edge, now sampled from mailbox;
probe treats mailbox as connected pad; telemetry is read from verified symbols.
These fixes stay in diagnostic hooks, not a new gameplay clock/input path.

SDK build keeps inline functions: sky helper `static inline` caused duplicate
retained bodies and left32B margin. Removing inline locally recovered space;
latest combined margin is5216B. API20 + OOC scene/room fields require coordinated
core/host/all-OOC rebuild, already done for this candidate.
