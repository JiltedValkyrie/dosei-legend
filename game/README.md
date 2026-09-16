# Dosei Legend game

Active Jo Engine / SGL project. See the [directory map](../README.md),
[scope](../VERTICALSLICE.md) and [progress](../VSLICEPROGRESS.md).

## Build and launch

Configure local dependencies with `../launch-game.bat` > **Config > Paths...**.
See [developer setup](../tools/launcher/SETUP.md) for the SDK, decomp and exact ROM.
Settings are saved to the repository's ignored `config.ini`. From Windows, use
`build.bat` or `build.bat -Variant hires`.

In MSYS2 bash, run `./build.sh` here. Add `--hires` for 320x480i;
standard is 320x240. Same assets, gameplay and audio. Build sequentially.
All generated output goes under `build/`, including both `game*.cue/.iso` images,
objects, generated meshes and CD staging. `disc/` holds checked-in ISO metadata.

Double-click `../launch-game.bat` to choose a mode in the GUI, or use
`run-kronos.bat` / `run-kronos-hires.bat`. Close Kronos before switching modes.

## Content and code

Forest content lives in `levels/kokiri/assets/`; actor recipes in `assets/dynamic/`.
The Link converter consumes `assets/dynamic/link/source.json`. Generated actor
meshes live in `build/generated/`. Shared title UI/audio and reusable libraries
live in `../shared/`; game-specific bank selection stays in `src/music_banks.c`.

Start switches title/gameplay, D-pad moves, L/R turns the camera, A toggles
diagnostics. Current Link/follow behavior is in `src/demo.c`.

The title uses five slow, wide camera routes generated from `FOREST.BIN` by
`tools/build_title_paths.py`. The generator searches connected free space,
favours passage centres, smooths corners, and validates the final segments
with 16-unit clearance. Routes are cached by source/tool hash; a fresh route
build takes longer than an ordinary rebuild. The old tree-closeup probe is
still available only through the explicit diagnostic mode below.

Forest fog blends texture palettes toward yellow-olive, with VDP1 mesh dithering
in the last eighth of the draw range. The cutoff is 1,310 world units, half the
original forest renderer's 2,620-unit range. Shared tiles use their nearest
surface's fog amount to protect nearby detail. The sky table occupies B1+0x1f000;
do not allocate it at B1+0, which is SGL's font storage despite appearing free
to Jo's allocator. Unused/final back-screen lines stay black for the border.

To capture Kronos while another application has focus, use
`powershell -ExecutionPolicy Bypass -File tools/capture-kronos.ps1` from here.
It uses `PrintWindow`, never desktop copying or global key input. Keep Kronos
unminimized behind the other application; `-ShowBehind` can make a hidden test
window drawable at the bottom of the window stack without activating it.

The default converter now uses source UVs, shared/repeating textured quads,
density-budgeted bakes and limited close-ground subdivision. The source ROM is
the verified US 1.2 ROM in the configured ROM directory, with metadata from the
configured `zeldaret/oot` checkout.
Collision remains the original whole mesh; no runtime Y reflection was added.
See [texture implementation and evidence](docs/TEXTURE_PLAN.md).

From MSYS2 bash in `game/`:

```bash
./build.sh                                  # normal gameplay, new textures
./build.sh --hires                          # same game, 320x480i
TEXTURE_PATH=legacy ./build.sh              # original FOREST.BIN texture fallback
./build.sh --hires TEXTURE_PROBE=1          # optional ground/treeline camera sweep
```

The probe replaces that mode's image: rebuild without `TEXTURE_PROBE=1` before
normal play. Stages 0–2 approach/turn on spawn ground; 3–5 approach/turn on the
treeline. It hides the title/Link only in this diagnostic, not in normal builds.
The legacy probe can reuse the generated `texture_probe.h` after a hybrid build.
`--diagnostic-tiles` remains available on `tools/build_sgl_scene.py`.

`build/generated/texture_manifest.json` records source-face IDs, patch positions,
tile sizes, combined budgets and connected-component bounds for later visibility
groups. Components are not yet named huts/trees and are not culled at runtime.
The mesh workshop still exports editing candidates; the new runtime quad path
comes from source display lists, not the workshop's Prefer quads checkbox.
Old port notes in `docs/history/` are historical.
