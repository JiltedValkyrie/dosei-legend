# Dosei Legend game

Active Jo Engine / SGL project. See the [directory map](../README.md),
[scope](../VERTICALSLICE.md) and [progress](../VSLICEPROGRESS.md).

## Build and launch

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

Near-camera warping is still a required playability fix; hi-res does not fix it.
The mesh workshop exports/imports tri/quad OBJ candidates, but runtime quad
integration is not implemented. Old port notes in `docs/history/` are historical.
