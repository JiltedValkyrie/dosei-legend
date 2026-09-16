# Jo Engine / SGL Kokiri viewer

Isolated port target for [docs/JOENGINE_PORT.md](../title-screen/docs/JOENGINE_PORT.md).
Renders the textured Kokiri Forest through Jo Engine's SGL path, with the
baseline title artwork, blinking PRESS START, SCSP score, automatic yaw,
manual camera controls and source-space collision.

The libyaul build is untouched. This project reads its `cd/FOREST.BIN`, score
header and existing PCM/envelope assets.

## Vertical-slice controls

- Start: toggle title artwork and idle panning (music continues).
- D-pad: forward/back and strafe; L/R: turn.
- X/Z: raise/lower the camera, collision constrained.
- Hold Y + Up/Down: look up/down; C: level the view.
- A: toggle the diagnostic HUD. Submission refusals are accumulated even
  when the HUD is hidden; failures remain visible.

Current local Kronos keyboard mapping: WASD = D-pad, Space = Start,
Shift/Enter = L/R, U/I/O = X/Y/Z, L = C, J = A.

The collision-derived spawn is raised 24 units to `(-300,115,0)`.
Movement runs at 30 updates/second with bounded catch-up; idle pan and prompt
blink use a separate 60 Hz clock and do not depend on music initialization.
The baseline collision behavior is retained (free camera with swept movement,
wall sliding and floor/ceiling constraints, not a new gravity/player controller).
Collision (60,912 bytes), envelopes (112,176 bytes) and prompt (2,352 bytes) live
in the existing heap. Title RGB555 rows stream through a 1 KB staging buffer
to Jo's NBG1 bitmap; black keys transparent. No new VDP1 sprite slots are used.

Kronos has shown the title over the forest at the raised spawn, and subsequently
the title hidden with a moved camera and zero accumulated refusals. Captures:
`generated/demo-title.png`, `generated/demo-movement.png`. These are smoke
checks, not exhaustive moving-camera/work-area verification. 33 viewer tests
and 24 baseline tests pass. Foreground warping is deliberately deferred.

## Earlier verification (music/pan bring-up)

Kronos window capture `generated/music-pan-window.png` shows music ON at tick
614, yaw 55260, 2060 submissions, zero current/accumulated refusals and VDP1
29 FPS. This is a short rotation observation, not a work-area safety proof.
Severe foreground texture stretching remains visible and unresolved; successful
submission does not establish correct clipping or texture mapping.

The test launch redirected OpenAL to `generated/title-audio.wav`, so it did not
play through the speakers. The 20–55 second interval is non-silent (mean
-25.5 dB, peak -10.1 dB); this is signal evidence, not a listening or loop-quality
check. Kronos was subsequently reopened without the capture environment.
For normal playback, do not set `ALSOFT_DRIVERS=wave` or point `ALSOFT_CONF` at
the generated capture configuration. The normal batch launcher sets neither.

## Build and run

Standard: `./build.sh` then `run-kronos.bat` (320x240).
Hi-res experiment: `./build.sh --hires` then `run-kronos-hires.bat` (320x480i).
Both retain the same scene, Link, controls, title and music. Separate object trees
and `game` / `game-hires` disc images prevent mode contamination. Build sequentially
because generated assets and the CD staging directory are shared. The hi-res
mode doubles vertical resolution only; it is not a texture-warping fix. Native
hardware appearance and the preferred mode remain for human comparison.

```bash
./build.sh          # converts the scene, compiles, makes game.iso + game.cue
```

Then `run-kronos.bat`. It mirrors `title-screen/run-kronos.bat` (same Kronos
build, BIOS and autostart) so both images are measured the same way.

Requires the sibling Jo Engine SDK at `../../joengine` (bundled GCC 9.3.0,
SGL 3.02j, make, mkisofs, JoEngineCueMaker) plus MSYS2 bash and Python.

## How to open Kronos on Windows

Build the viewer first so `jo-viewer/game.cue` and `jo-viewer/game.iso` exist.
In PowerShell, run:

```powershell
Set-Location 'D:\Workspace-Claude\saturn-homebrew\dosei-legend'
cmd.exe /c jo-viewer\run-kronos.bat
```

Alternatively, double-click `jo-viewer\run-kronos.bat` in File Explorer. This
opens Kronos and automatically boots the viewer disc. Allow the Saturn BIOS
animation to finish; then look for the `Jo/SGL Kokiri viewer` HUD and forest.
After rebuilding, close the previous viewer instance and launch the batch file
again so the new disc image is loaded.

The launcher supplies these required settings:

- Executable: `D:\Workspace-Claude\saturn-homebrew\Kronos\build_kronos\src\port\qt\kronos.exe`.
- BIOS: `D:\Workspace-Claude\saturn-homebrew\bios\Sega Saturn BIOS (E) (1.00)\Sega Saturn BIOS (E) (1.00).bin`.
- Disc: `game.cue` beside the launcher, referencing `game.iso`.
- DLL search path: prepends `C:\msys64\mingw64\bin` to `PATH`.
- Working directory: the Kronos executable directory, needed for its config/plugins.
- Arguments: `-b "<BIOS>" -i "<game.cue>" -a` for BIOS, disc and autostart.

Use the batch file rather than launching the executable from the repository
directory. If Kronos does not open, check those paths and the MSYS2 DLL directory.
If it says `Build first`, regenerate the viewer image with `build.sh`.

For an agent running under a sandbox, opening the GUI requires an escalated
terminal call (`sandbox_permissions: require_escalated`). The command is the
same `cmd.exe /c jo-viewer\run-kronos.bat`, with the repository as working
directory. Desktop capture also required escalation in the verification session.

To open the existing libyaul baseline instead, run this from the repository root:

```powershell
cmd.exe /c title-screen\run-kronos.bat
```

That launcher loads `title-screen/title-screen.cue`, not the Jo viewer image.

## What is here

| Path | Role |
| --- | --- |
| `tools/build_sgl_scene.py` | FOREST.BIN (KFR1 v2) -> SGL `POINT`/`POLYGON`/`ATTR` tables |
| `tools/build_sgl_area.py` | Project-local SGL work area with a raised polygon limit |
| `src/kokiri_sgl.c` | Uploads 4bpp tiles + CLUTs to VDP1, binds them to the tables |
| `src/main.c` | Fixed camera, HUD, `jo_core_run()` loop |
| `generated/` | Converter output (derived, not tracked) |
| `tests/` | Host guards over the conversion |

## Conversion notes

`FOREST.BIN` already stores geometry the way SGL wants it, which is why no mesh
rebuild was needed:

- **Shared vertices.** One 1268-entry `POINT` table, indexed by 2060 `POLYGON`
  records. Jo's `jo_3d_create_mesh()` would have allocated four points per
  polygon; `PDATA` indexes a shared pool instead, so the vertices stay shared.
- **Triangles as quads.** Every face record already repeats its third index as
  the fourth corner, which is exactly SGL's degenerate-quad convention. All
  2060 faces were verified to satisfy this, with no degenerate triangles.
- **Face records are 20 bytes** (`>4HIIHH`), not 16.

Attribute fields mirror `jo_3d_set_mesh_polygon_texture()` in
`../../joengine/jo_engine/3d.c`, with `CL16Look` because the 4bpp tiles use
per-texture lookup tables in VDP1 VRAM (not CRAM colour banks), and `colno`
patched at load time to the uploaded CLUT address. `UseNearClip` hands the near
plane to SGL rather than reusing the libyaul build's CPU clipper.

## Budgets (measured, not estimated)

| Item | Size |
| --- | --- |
| VDP1 user area (`JO_VDP1_USER_AREA_SIZE`) | 455.3 KB |
| 1801 unique tiles, 4bpp | 313.2 KB |
| 1801 CLUTs | 56.3 KB |
| **VDP1 total** | **369.5 KB, 85.8 KB spare** |
| SGL work area (project-local), `0x060B5360`..`0x06100000` | 299.2 KB |
| `.bss` end `0x0609CB60`, headroom below the work area | 98.0 KB |

Textures are resident, so no tile streaming is needed. The framebuffers live at
`JO_VDP1_FB`, outside the user area. The 4 MB cart is not required.

Two settings had to be raised from the stock sample: `JO_MAX_SPRITE` (255 ->
1802, one slot per tile plus Jo's reserved entry 0; GCC caught the overflow),
and the texture upload reads straight into VRAM via `jo_fs_read_file_ptr()`
rather than `jo_malloc()`'ing a 313 KB staging copy out of the pool.
`JO_GLOBAL_MEMORY_SIZE_FOR_MALLOC` was lowered 384 KB -> 256 KB to make room
for the larger work area; the arena is in `.bss` and barely used, and collision
and title data are meant to come out of what remains.

## SGL work area

Stock `SGLAREA.O` caps a frame at `MaxPolygons=1761`, so the scene's
2060-polygon list was refused outright. `tools/build_sgl_area.py` builds a
project-local replacement. The SDK object is only ever read.

It is a pure data object -- one `SLPROG` section, no relocations -- whose first
0x40 bytes are the pointer/size header declared in `SL_DEF.H`. The graphics
buffers live outside it at the top of work RAM, so only that header changes.
Buffer sizes were derived from the stock header and reproduce its shipped
values exactly:

| Buffer | Size |
| --- | --- |
| `SortList` | `12 * (MaxPolygons + 6)`, 12-byte SCU DMA indirect entries |
| `SpriteBuf` | `72 * (MaxPolygons + 5)`, i.e. 72 bytes allocated per polygon |
| `Pbuffer` | `16 * MaxVertices` |
| `Zbuffer` | `(128 + 128 + 256) * 4`, fixed per `SL_DEF.H` |
| `CLOfstBuf` | `32 * 32` required; stock allocates 3072, kept |
| `CommandBuf` | no exported size and no clean stride, so scaled by the polygon ratio with margin -- **unverified**, see below |

These are *allocation* formulas, read off the stock header's own layout: they
give bytes per polygon or vertex, not how SGL consumes each buffer. Nothing
was traced into `LIBSGL.A`, so no claim is made about single- or
multi-buffering.

`CommandBuf` is the one buffer sized by ratio rather than by a derived
formula, and **a working fixed view does not establish it is safe**. It has
only ever been exercised by a static camera. Watch `rej` during camera
motion; a non-zero value there is the expected symptom if it is undersized.

Buffers are laid out contiguously **ending** at `0x06100000`, as the stock area
does, so `TransList` and `MasterStack` keep their original addresses and only
the growing buffers move down. The base address is the ceiling for `.bss`;
`build.sh` re-runs the generator with `--verify` after linking to fail the build
if the linker map crosses it.

## Camera

Pinned to `(-300, 91, 0)`, yaw and pitch zero -- the libyaul spawn. That pose is
not hardcoded in the baseline: `kokiri_collision_spawn()` searches outward from
`x=-300, z=0` and derives `y` from the floor plus `EYE_HEIGHT` (90). Replaying
that search over the 1692 collision triangles lands on ring 0 with floor `y=1`.
The baseline's own test suite prints the same `-300 91 0`.

Facing is `+Z`, with `+Y` up, taken from the baseline's view transform
(`kokiri_scene.c`), where yaw 0 leaves the Y-rotation as identity and rotated
`z` is used as depth. At this zero-yaw/pitch pose the viewer applies the exact
view transform `(x - eye.x, eye.y - y, z - eye.z)` directly, converting source
Y-up to SGL Y-down, and sets SGL's screen distance to the baseline's
240-pixel focal distance. The
viewer has no collision yet, so the pose is fixed.

## Status

Built and checked in Kronos on 2026-09-15. The fixed view renders upright, with
textured ground, canopy and the central tree structure, and **full coverage is
now verified**: the whole scene goes in one list.

| Diagnostic | Value |
| --- | --- |
| `subm` / `rej` / `ok mask` | 2060 / 0 / 1 |
| vertex transforms | 1268 |
| linked limits | `P2100 V2500` |

Two lists were never a way around SGL's cumulative per-frame budgets -- they
made them worse, since each list references the whole shared point pool, so the
split cost 2 x 1268 = 2536 vertex transforms where one list costs 1268. Raising
`MaxPolygons` and going back to a single submission fixes both.

**VDP1 runs at 29 FPS with the full scene** (VDP2 58/60). The earlier 58-59 FPS
readings were a half-scene with one list refused, and must not be quoted as a
full-scene result. This is still an emulator overlay on a viewer with no audio,
controls, collision or title, against no controlled baseline run -- not a
measured speedup.

`shown` (`DispPolygons`) still reads 0 while the forest is plainly visible; that
counter's asynchronous sampling is unresolved and is not evidence of coverage.
The `subm`/`rej`/`ok mask` values come from `slPutPolygon`'s own return, which is.

Real normals, corrected cull flags, screen-door mesh and disabled end codes are
preserved. 31 host tests pass, and the 24 baseline tests are unaffected. The HUD
uses NBG0 above sprites and runs immediately after submission in the same
callback. Controls and collision have not started. See
[Claude handoff](CLAUDE_HANDOFF.md).

## Build-system caveats

The stock `jo_engine_makefile` needs three overrides, all in `makefile`:

1. It compiles objects in place via a `.c.o` suffix rule, which would write
   `.o` files into the shared SDK. Objects are redirected to `obj/`.
2. Its `$(TARGET)` prerequisites are expanded while its own rules are read, so
   redefining `OBJS` afterwards is not enough; the SDK object paths are given
   rules that resolve to the `obj/` copies.
3. Its ISO recipe ends in an undefined `$(ENTRYPOINT)`, and the bundled
   msys-1.0 `sh.exe` mangles the resulting argument list (`Missing pathspec`).
   Recipes run under MSYS2 bash and the ISO is built by an explicit rule.
