# Historical scene investigation (superseded)

Current instructions are in [../SCENE.md](../SCENE.md); current crash evidence
is in [../DEBUGGING.md](../DEBUGGING.md). Paths and status statements below
describe earlier builds and are retained only as investigation history.
Latest update: the reorganized build did not crash on the user's last run;
the earlier 7 FPS failure still has no proven cause.

## Status at the archived snapshot

The user confirmed that pairing controller processing with INTBACK in VBlank-out
resolved the crash and that manual movement/collision works. That build still ran
at about 4 FPS. The following rendering changes have been built and checked on
the host, but their Kronos frame rate has not yet been measured:

- Project each shared vertex once using the SH-2 division unit.
- Reject faces entirely outside a frustum plane before sorting.
- Keep original textures for triangles within a bounded offscreen region;
  VDP1 clips their pixels to the unchanged 320x240 viewport.
- CPU-clip only near-plane/extreme-coordinate cases, and resample textured
  16x16 tiles using bounded 32-bit division. No flat-color fallback remains.

The 216-view sweep peaks at 764 draw commands and 29 resampled tiles (limits
3069 and 256). Across the sweep, 19,445 draws retain original tiles, 1,650 use
resampled tiles, and 413,124 offscreen faces are rejected before sorting.
This measures work and memory bounds, not runtime FPS. Texture fidelity is still
limited by baked 16/32-pixel source tiles and Saturn affine texture mapping.

The converter verifies the compressed **US 1.2 ROM**, reads its DMA table, and
extracts all three visual room meshes plus the scene's static collision header.
The visual mesh has 2,060 triangles; collision has 1,692 triangles. Original world
coordinates are retained. The environment has not been scaled down.

## Camera controls

Start toggles the title. With the title visible, the camera turns automatically.
With the title hidden, automatic rotation pauses and controller port 1 controls it:

| Input | Action |
| --- | --- |
| D-pad | Forward/back and strafe on the horizontal X/Z plane, relative to yaw |
| L / R | Turn left / right |
| X / Z | Raise / lower the camera |
| Hold Y + Up / Down | Look up / down; D-pad translation is suspended |
| C | Reset pitch to level |
| Start | Restore the title and resume automatic turning |

Pitch is limited to approximately +/-80 degrees. Movement stays horizontal when
looking up/down. Movement and turning speeds are per rendered frame, editable
in `kokiri_camera.h`: translation 16 (diagonal 12), yaw 360, pitch 240.
Manual speeds are doubled. L subtracts yaw, R adds yaw, and both held cancel;
wraparound is regression-tested and opposite increments verified in SH-2 code.
The prior same-direction report was not reproduced by native tests; the
rewritten controls still need an emulator check. The automatic speed of 90 is retained.
Music keeps its existing vblank timing.

`kokiri_collision.c` sweeps a 24-unit camera sphere in steps of at most four units.
It checks triangle faces, edges and vertices, slides along blocked axes, and keeps
a minimum 90-unit eye height above an upward-facing floor. X/Z provide vertical
flight, with floor and ceiling blocking; gravity is not applied. Tall steps are
blocked. Startup searches the village clearing for a collision-free point above
an actual floor: the current asset selects **(-300, 91, 0)**.

This is static camera collision, not Link's character controller. Dynamic actor
collision and water behavior are pending. All extracted static triangles are
conservatively solid, without reproducing N64 per-entity exclusion flags. A broad
coordinate limit protects the fixed-point renderer if the camera flies outside
the scene; it is not a gameplay boundary.

## Rendering

The original positions, UVs, textures and palettes are baked into VDP1 distorted
sprites with corners A/B/C/C. The largest 300 surfaces use 32x32 tiles, others
16x16, with 15 opaque RGB555 colors and transparent index zero. Identical tiles
share storage. Texture scale, shifts, wrapping, mirroring and clamping are baked.

The previous renderer clamped projected coordinates before checking winding. This
could collapse or reverse a polygon and discard it. `kokiri_clip.c` now clips in
camera space against the near plane and all four screen edges before projection
and culling. Clipped polygons are covered by a fan of quads, retaining their
original barycentric texture coordinates. Clipped surfaces get temporary 16x16
tiles. A dense view that exhausts the scratch pool uses solid-color coverage for
additional clipped surfaces rather than dropping them.

The camera-space transform includes yaw and pitch. Surfaces are still sorted
far-to-near by average depth: intersecting or large overlapping surfaces can still
be misordered. Collision does not solve these remaining painter-sort artifacts.
VDP1 texturing is not perspective-correct.

## Asset and memory layout

`FOREST.BIN` version 2 is big-endian: a 64-byte header, signed 16-bit XYZ positions,
20-byte visual face records, 36-byte collision records, then aligned CLUTs and
4-bit textures. Header fields 14/15 identify collision offset/count. Source hashes
and asset sizes are recorded in `kokiri_scene_manifest.json`.

The 488,184-byte file stays in low work RAM. Textures use 378,400 bytes of VDP1,
clipped-texture scratch uses 32,768 bytes, and 3,072 commands reserve 98,304 bytes.
Together with libyaul's entry, this uses 509,504 of 524,288 VDP1 bytes. Transformed
vertices, sort storage and the command list live in high work RAM. Rendering is
complete before either commands or scratch textures are reused.

## Remaining visual limits

- Actor models, Link, animated materials and gameplay interactions are pending.
- Lighting is approximate; N64 combiners, fog and multi-texturing are not reproduced.
- Translucent lists use mesh transparency, and alpha uses a fixed cutoff.
- Small tiles and per-triangle palettes reduce texture detail.
- Existing title/backdrop bitmaps remain from earlier work; their historical
  generators still point to the older extraction.

## Validation

```powershell
python title-screen/tools/test_kokiri_camera.py
python title-screen/tools/test_kokiri_scene.py
python title-screen/tools/test_title_audio.py
```

The camera tests compile the actual collision/clipping C modules using the installed
MinGW GCC and call them from Python. They cover spawn selection, floors, wall
sweeps, sliding, triangle edges, ceilings, scene movement, extreme clipping, and
camera sweeps at three positions and three pitches. The sweep peaks at 765 draw
commands and 138 clipped tiles, within the reserved budgets. Scene tests check
the binary layout, texture addressing and memory; audio tests check linked assets.

`build/kokiri-preview.png` is a host conversion preview, not an emulator screenshot.
Its texture sampling differs from VDP1. Build/tests pass; runtime visual quality,
controller feel and frame rate still need emulator/hardware verification.

## Start-toggle exception investigation

Kronos reported an illegal instruction with saved PC 0x060060F2 immediately after
Start was pressed in the prior build. This maps to the controller/title transition
in `main`, not collision. The local Kronos core saves PC+2 (and uses the same
exception for delay-slot failures); the executable's surrounding instructions are
valid SH-2. The screenshot alone does not establish the underlying cause.

The first delayed-branch workaround did not resolve the user's hang and has been
removed. The title edge handler remains isolated, but manual control is now in
`kokiri_camera.c`, independent of platform bitfields. Idle/Start-only input returns
without trigonometry or collision work. Movement uses bounded 32-bit math and only
calls collision for a nonzero displacement.

The actual controller C module now joins the host tests: 20,000 idle/Start-held
updates perform zero movement/trig calls, all 8,192 digital button combinations
stay bounded, and individual movement/turn/pitch/title-mode checks pass. These
checks do not prove the cause of the reported runtime hang. Emulator confirmation
remains pending: the session's direct Kronos launch never reached a game window.

## VDP1 synchronization correction

The scene now calls `vdp1_sync_interval_set(-1)` during initialization, matching
libyaul's vdp1-mic3d example. The previous default was AUTO (interval 0). In the
installed SDK, AUTO selects PTMR automatic redraw and its vblank handler marks
the list committed without checking CEF. That permits repeated drawing during
CPU updates and assumes work fits a video field. This scene changes both commands
and clipped-texture VRAM and can exceed that budget.

Variable mode explicitly starts plotting and checks completion before swapping
framebuffers and clearing the sync flag. The existing end-of-frame
`vdp1_sync_wait()` therefore protects both resources before the next CPU update.
This fixes a concrete synchronization mismatch. The user's freeze still needs
runtime confirmation with the rebuilt image; host geometry tests cannot certify
VDP1/emulator synchronization.

## Active freeze diagnostic build

The user reports Kronos freezing after 2-3 frames and process memory growing from
about 5 GB to 6 GB in 20 seconds. The previous fixes are not confirmed solutions.
Scene buffers are allocated only during initialization; host process growth is
outside the Saturn memory budget. It may be triggered by command submission or
texture updates, but has not been traced to a particular emulator allocation.

A temporary top-left probe is enabled. Leave the title visible. Five hexadecimal
groups show stage, completed frames, vblank ticks, VDP1 EDSR, and VDP1 COPR.
Stages: 10 controller poll, 20 camera, 30 transforms, 40 sort/command building,
50 command DMA, 60 render/transfer wait, 70 frame completion wait, 80 VDP2 sync.
The tick/status groups are written from the existing vblank callback, without
allocations or synchronization calls. This distinguishes CPU work, DMA waits,
and frame-completion waits. Screenshot/runtime evidence is needed next.

## Reduced-cost rendering path

The latest diagnostic screenshot stops at stage 70 (VDP1 completion wait) while
VDP2/vblank remains active. The debug-interpreter result is not a usable control
benchmark. The current build removes all per-frame clipped-texture resampling and
VRAM texture uploads. Fully visible triangles retain their textures; clipped
polygons use their palette's solid color as a temporary visual compromise.
Clipping now trivially accepts/rejects triangles before polygon construction and
uses the SH-2 hardware divider for its bounded Q16 intersection quotient. Host
checks retain an integer reference path. Runtime frame rate and the VDP1 wait
still require confirmation; no measured performance improvement is claimed.
Use the normal run-kronos.bat for the next comparison, not the debug core.
## Controller polling and crash evidence (previous build)

The reported PC `0600BAE0` maps to `smpc_peripheral_raw_port` in the previous
ELF, at a valid `add #-1,r1` instruction (`71FF`). Its caller is
`smpc_peripheral_digital_port`. That does not prove an emulator bug: the
instruction in emulated RAM at failure may differ from the ELF. The matching
ELF/symbol file is preserved in `build/crash-0600bae0/`.

Controller processing now runs in VBlank-out before issuing the next INTBACK,
instead of consuming input at the much slower renderer rate. The callback's
interrupt priority prevents the SMPC handler from replacing the collection
buffer while it is parsed. Main reads only a short, interrupt-protected button
snapshot; rising edges accumulate until consumed so a brief Start press between
draws is retained. Polling starts after sound initialization, which also sends
SMPC commands. The user subsequently confirmed this build resolved the crash.

`crash_probe.c` and the libyaul-derived `crash_vectors.sx` install illegal
instruction/slot handlers that preserve the SDK register dump and add the two
instruction words at saved PC-2 and PC, read through both P0 and uncached P2.
These appear as `P0` and `P2` on the game's exception screen. Kronos's own error
dialog still reports only registers. The linked vectors and handler call were
checked in SH-2 disassembly. Build and all 17 existing native/asset tests pass;
Kronos stability and acceptable frame rate still require runtime verification.
