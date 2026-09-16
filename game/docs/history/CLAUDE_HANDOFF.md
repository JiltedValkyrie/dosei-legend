# Claude handoff: first Kronos verification

## Latest update - vertical-slice restoration (Astra, uncommitted)

Human explicitly parked warping and requested a slightly higher camera plus
the baseline functionality. No renderer/clipping changes were made.

- Spawn comes from the existing collision search, then a collision-constrained
  +24 Y move: observed `(-300,115,0)` in Kronos.
- Existing title bitmap is converted to keyed big-endian RGB555 and streamed
  row-by-row into Jo's NBG1. Existing PRESS START patch blinks every 30 ticks.
- Start toggles title/idle pan; manual controls match the baseline; A toggles
  diagnostics, hidden by default. Music keeps playing during gameplay.
- `demo_camera.c` and `demo_collision.c` compile the unchanged portable baseline
  C sources into local objects. Jo input is explicitly mapped to normalized
  camera bits; SGL sin/cos supplies movement trig. Positions/collision stay in
  source space. Rendering applies pitch/yaw and translation, no Y reflection.
- Collision is 60,912 heap bytes, not static BSS. Title upload uses 1 KB staging;
  prompt is 2,352 resident bytes. Audio envelopes remain 112,176 heap bytes.
- Demo has its own PAL/NTSC 60 Hz clock, independent of audio success. Gameplay
  ticks at 30 Hz with a four-step catch-up cap; idle pan stays 90 units/60 Hz tick.

Final build passed with `.bss` end `0x0609ECE0`, 91,776 bytes below the SGL area.
33 viewer tests and 24 baseline tests pass; the latter exercise the actual reused
collision/movement sources. Window captures show the title at raised spawn
(`generated/demo-title.png`), then hidden title/moved camera with total refusals
zero (`generated/demo-movement.png`). Start plus a brief forward input was sent
to Kronos; the human may also have been interacting, so do not attribute the
entire coordinate change to that injected input. No exhaustive wall/ceiling/
edge traversal acceptance has been claimed. Audio listening/loop quality remains
unconfirmed by the agent. NPC is not implemented. All changes remain uncommitted.

Run and keyboard/pad mappings are in README. Earlier incomplete-status notes
below are historical and superseded by this section.

## Latest update - music/pan bring-up (Astra, uncommitted above `1bf8a66`)

Human priority is title music and camera panning first. Added `title_music.c`
using the existing baseline score, envelope and sample bank; stock Jo audio
stays disabled. Samples upload through a 2 KB heap staging buffer into sound
RAM, envelopes remain on the heap, and a vblank accumulator advances the score
at 60 ticks per second (including on PAL). Camera yaw uses that clock, 90 angle
units per tick. No runtime Y reflection was reintroduced. If music initialization
fails, the current shared clock also stops the pan; this coupling remains.

Build and 31 existing viewer tests passed. New playback does not yet have host
tests. `.bss` ends at `0x0609DA20`, leaving 96,576 bytes below the work area.
Kronos window-only capture `generated/music-pan-window.png` shows tick 614,
pan 55260, subm 2060, rej 0, mask 1 and total refusals 0. It also confirms the
human's report of severe foreground texture stretching. Near clipping/texture
mapping needs investigation; no cause or fix has been established.

The human heard no music during the capture launch: that run explicitly used
OpenAL's WAV backend, not speakers. The resulting 76.81-second WAV has sustained
non-silent output at 20–55 seconds (mean -25.5 dB, peak -10.1 dB). This is not an
audible-quality or loop verification. Reopened Kronos without the capture
environment for normal output. No persistent emulator audio setting was edited.

Title artwork is still absent, not an asset-loading regression: it has not been
ported. Controls/collision/NPC remain deferred. The historical fixed-view results
below predate these changes and are not the current demo's completion status.

## Current update - submission capacity resolved (Opus)

HEAD is still `01f2b15` on `joengine-port`; everything below remains
uncommitted. Nothing was pushed. The shared Jo SDK and the libyaul baseline were
not modified: `SGLAREA.O` is unchanged (mtime Sep 14 18:17) and no stray objects
exist under `joengine/jo_engine/`.

### Result

Single-list submission is accepted with full coverage, verified in Kronos:

| Diagnostic | Value |
| --- | --- |
| `subm` / `rej` / `ok mask` | **2060 / 0 / 1** |
| vertex transforms | 1268 |
| linked limits | `P2100 V2500` |
| `.bss` end vs work-area base | `0x0609CB60` vs `0x060B5360` (98 KB clear) |

Evidence: `generated/single-list-check.png`.

The two-list workaround was never a way around SGL's cumulative per-frame
budgets; it made them worse. Each list references the whole shared point pool,
so the split cost 2 x 1268 = 2536 vertex transforms where one list costs 1268.
With `MaxPolygons` raised, one list fits both budgets with headroom.

**VDP1 now runs at 29 FPS with the full scene** (VDP2 58/60). The earlier 58-59
readings were a half-scene with one list refused; they must not be carried
forward as a full-scene figure. This is an emulator overlay on a viewer with no
audio, controls, collision or title, with no controlled baseline run - not a
measured speedup.

### Your two questions, answered from the SDK object

`SpriteBuf` allocates 72 bytes per polygon. Sizes derived from the stock
header reproduce its shipped values exactly:

    SortList  = 12 * (MaxPolygons + 6) = 21204   12-byte SCU DMA indirect entries
    SpriteBuf = 72 * (MaxPolygons + 5) = 127152  72 bytes per polygon
    Pbuffer   = 16 * MaxVertices       = 40000
    Zbuffer   = (128+128+256) * 4      = 2048    fixed, matches SL_DEF.H
    CLOfstBuf = 32 * 32 required; stock allocates 3072

So `SpriteBuf`'s allocation scales linearly with `MaxPolygons`. All eight
buffers are contiguous and end exactly at `0x06100000`.

Correction, per your review: these are **allocation** formulas read off a
pure-data object. They establish layout, not buffer-use semantics. I did not
trace `SpriteBuf`'s consumers in `LIBSGL.A`, so my earlier "single-buffered /
not multi-frame" wording was stronger than the evidence and has been dropped
from the docs.

`CommandBuf` (50236) is the one field with **no exported size and no clean
per-polygon stride** - 50236/(MaxPolygons+5) is not an integer. It is scaled by
the polygon ratio with a 1.10 margin rather than guessed at. That is the weakest
assumption in the layout.

**It is unverified.** A successful fixed view says nothing about its safety:
the camera has never moved. Validate it during the controls/collision pass by
watching `rej` while turning and walking -- a non-zero `rej` under motion is
the expected symptom of an undersized `CommandBuf`, and it is the first thing
to suspect before blaming the movement code.

### How the replacement works

`tools/build_sgl_area.py`. `SGLAREA.O` is a pure data object - one `SLPROG`
section, **no relocations** (`objdump -r` is empty) - whose first 0x40 bytes are
the pointer/size header from `SL_DEF.H`. The graphics buffers live outside it at
the top of work RAM, reachable only through those pointers, so only that header
needs patching. The generator copies the SDK object and rewrites the header, so
symbol names and offsets are untouched.

Checks, all of which fail the build rather than warn:

- `verify_stock_layout()` refuses to run if the SDK object is not the SGL 3.02j
  area these formulas were derived from.
- `check_layout()` enforces 32-byte alignment, contiguity (no gap *or* overlap),
  positive sizes, and that the region ends exactly at `0x06100000`.
- `--verify` re-runs after linking and fails if `.bss` crosses the work-area
  base. During generation the map is from the *previous* build, so it only warns
  there - the ordering matters, and `build.sh` runs both.

Layout is anchored at the **top** of work RAM, so `TransList` and `MasterStack`
keep their stock addresses and only growing buffers move down.

### Cost

`MaxPolygons` 1761 -> 2100 grows the area 262144 -> 306336 bytes (+44192).
`JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC` dropped 384 KB -> 256 KB to pay for it: the
arena is in `.bss` and barely used, since textures read straight into VDP1 VRAM.
Headroom went from 13376 bytes to 100352. Collision (1692 triangles, ~60 KB) and
title data are intended to come from the remaining 256 KB arena rather than from
new static buffers.

### Tests

31 viewer tests pass (your 15 plus 16 new); the 24 baseline tests are unaffected.
The new ones cover the stock-header formulas, layout alignment/overlap/
contiguity, that the generated object differs from the SDK object **only** in
the 0x40-byte header, that untouched fields are preserved, and that `.bss` stays
below the base in the current map.

### Still open

- `shown` (`DispPolygons`) reads 0 while the forest is plainly visible. Its
  asynchronous sampling is unresolved. It is not evidence of coverage;
  `slPutPolygon`'s return value is.
- `CommandBuf` sizing, as above.
- Near/far clipping parity, coincident-layer ordering and the baseline's
  distance-fade mesh (a runtime depth test) are still not implemented or
  compared.
- The 29 FPS figure needs a controlled comparison against the libyaul baseline
  at the same pose before it means anything.

Controls and collision have not started; their prerequisite is now met.

## Historical report — before Opus's cleanup and current diagnostics

2026-09-15. Branch `joengine-port`, HEAD `93d1843` (your isolated viewer commit).
The runtime fixes below are uncommitted. Nothing was pushed. The libyaul source
and shared Jo SDK were not edited during this work.

## Current result

The rebuilt `game.cue`/`game.iso` boots in Kronos and renders a coherent, upright,
textured forest at the fixed spawn `(-300, 91, 0)`. Ground is below the camera;
canopy is above it. The central tree structure is upright. The user correctly
identified the earlier view as upside down; changing perspective was not the fix.

The last run was left open in Kronos. Its screenshot is
`generated/upright-check.png` (ignored, local only). The screenshot shows VDP1
58 FPS and VDP2 58/60 FPS. RETIRED: that reading, and every other 58-59 FPS
figure in this historical section, was taken while one polygon list was being
refused, i.e. on roughly half the scene. The full scene measures VDP1 29 FPS.
Do not carry these forward. Also do not turn them into a speedup claim: this
viewer has no audio, controls, collision update, title or baseline profiler, and
no controlled frame-timing comparison was performed.

## Changes and evidence

1. **Vertical camera axis:** `src/main.c` now translates by
   `(-CAM_X, CAM_Y, -CAM_Z)` then calls `slScale(1, -1, 1)` in fixed point.
   This produces `(x - eye.x, eye.y - y, z - eye.z)` for SGL's Y-down projection.
   Rebuilt and verified visually in Kronos. Mesh coordinates remain unchanged.
   Screen distance is explicitly 240, matching the baseline projection.
2. **Camera path:** replaced `slLookAt` with the direct fixed-pose matrix.
   Tested look-at target sign changes did not establish a working view. Direct
   translation produced a recognizable but inverted forest, then the Y flip
   corrected it. The underlying look-at failure was not diagnosed; earlier
   claims about its handedness were hypotheses, not established API semantics.
3. **Texture color mode:** converter emits `CL16Look` instead of `CL16Bnk`.
   SDK `SL_DEF.H` distinguishes VDP1 lookup-table mode from color-bank mode.
   These assets contain per-tile RGB CLUTs in VDP1 VRAM; `colno` remains their
   VRAM-relative address divided by eight. Updated the existing host assertion.
4. **Submission size:** the original single 2060-face `slPutPolygon` call gave
   a black viewport with a working HUD. Temporarily capping the list to
   `MaxPolygons` produced geometry. SDK work-area comments imply 1800 polygons.
   Final code uses two persistent 1030-face `PDATA` views into the same tables,
   each retaining the shared 1268-point pool. No faces are removed from the data.
   The forest renders with this arrangement, but see the acceptance caveat below.

The temporary face cap and target-sign experiments are no longer in the source.

## Remaining issues to verify before marking step 4 complete

- **Submission acceptance is not measured.** Both calls currently ignore the
  Boolean return from `slPutPolygon`. Splitting the lists producing a picture
  does not prove both lists are accepted or every intended visible face reaches
  VDP1. Prior commentary claiming both submissions were accepted was too strong.
  Check the actual cumulative polygon/vertex budgets, return values and displayed
  counts. Each list references all 1268 vertices, so shared storage does not imply
  that SGL transforms each vertex only once per frame.
- **HUD count is mislabeled.** `drawn` calls `jo_3d_get_polygon_count()`, which
  exposes `TotalPolygons`, not `DispPolygons`. Callback order and asynchronous
  submission also need consideration before using this as a frame measurement.
- **Source cull flag is inverted in the converter.** Baseline bit 1 (`flags & 2`)
  means cull backfaces: it rejects screen area <= 0. The converter currently names
  that bit `two_sided` and emits `Dual_Plane` when set, `Single_Plane` otherwise.
  This is a source-level mismatch, not fixed during the camera correction. Check
  SGL winding after the Y reflection and its requirements for the zero normals
  before simply swapping the flags. The reported 1937 'two-sided' faces actually
  carry the baseline cull flag.
- **Transparency differs.** Baseline bit 0 enables mesh/screen-door rendering;
  converter uses `CL_Trans` (half-transparency). Baseline also disables texture
  end codes, while generated attributes do not explicitly set `ECdis`. Palette
  index 15 is used by the baker, so this deserves verification for missing pixels.
- **Clipping and draw policy remain unproven.** `UseNearClip` alone is not evidence
  of matching the baseline near plane, texture resampling, far culling or fade.
  Check floor and screen-edge crossings and coincident layers at matched poses.
- **Memory budget needs its correct boundary.** The earlier 719 KB / 1024 KB
  figure is not all available application space: Jo reserves upper work RAM for
  SGL. Current map ends BSS at `0x060bcb40`, below the SDK's `0x060c0000` user-area
  boundary by only `0x34c0` (13504 bytes). The existing malloc arena is already
  inside BSS. Account for this before adding large static buffers or more systems.

The fixed view is a useful runtime milestone, not full renderer parity. Finish
these checks before camera/collision/audio migration or an FPS comparison.

## Reproduction and validation

From `jo-viewer/` in PowerShell, the successful build invocation was:

```powershell
$env:Path = 'C:\msys64\usr\bin;' + $env:Path
C:\msys64\usr\bin\bash.exe ./build.sh
```

Without that PATH addition, this shell could not find `dirname`. Sandbox runs
also hit MSYS2 signal-pipe access errors; the successful build used escalation.
Launch from repository root with `cmd.exe /c jo-viewer\run-kronos.bat`. Allow
time for the Saturn boot animation before evaluating the scene.

Validation completed:

- Final viewer build succeeded after the Y correction.
- All 13 viewer host tests passed after regenerating assets.
- All 24 baseline tests passed earlier in this session; baseline source was not
  changed afterward. Spawn test again reported `-300 91 0`.
- `git diff --check` passed (Git printed existing LF/CRLF normalization warnings).
- Final orientation was checked from the actual running Kronos screenshot.

The host tests do not validate SGL runtime behavior; an existing flag test can
pass while asserting the converter's incorrect two-sided interpretation.

## Working-tree handoff

Runtime changes are in `src/main.c`, `src/kokiri_sgl.c`, `src/kokiri_sgl.h`,
`tools/build_sgl_scene.py` and `tests/test_build_sgl_scene.py`. README, this
handoff and the port plan document the new status. Generated assets and image
were rebuilt. No commit was created.

Several untracked `kronos-*.png` desktop captures remain at repository root from
diagnostics. They include surrounding desktop content and intermediate failures;
do not stage them indiscriminately. The final orientation evidence is the ignored
`generated/upright-check.png`. A baseline host preview was also generated at
`../title-screen/build/kokiri-spawn-preview.png`; it is a host reference, not a
new baseline emulator measurement.
