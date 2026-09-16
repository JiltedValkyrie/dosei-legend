# Dosei Legend — Kokiri Forest on Sega Saturn

The active game uses **Jo Engine / SGL**. Work on the playable vertical slice,
not the archived libyaul experiments. See [scope](VERTICALSLICE.md) and
[current progress](VSLICEPROGRESS.md).

## Layout

```text
game/
  src/                         Game flow, scene/actor submission and bank selection
  levels/kokiri/assets/static/  Forest geometry, collision container and backdrop
  levels/kokiri/assets/audio/   Kokiri score and sample bank
  assets/dynamic/link/          Actor source recipe (animation/pose/scale)
  disc/                        Checked-in disc metadata, not generated staging
  tools/                       Game-specific asset converters
  tests/                       Active Jo game checks
  build/                       Ignored objects, generated meshes, CD staging, ISOs
shared/
  lib/camera/                  Reusable camera/movement logic
  lib/collision/               Platform-independent collision
  lib/music/                   Bank-agnostic Saturn music player
  assets/static/ui/            Title artwork and prompt
  assets/audio/title/          Shared title score and samples
  tools/                       Shared extraction, mesh and audio export helpers
  build/                       Ignored extraction/source caches
tools/
  launcher/                    Windows GUI: standard or hi-res Jo game
  mesh-workshop/               Non-destructive triangle/quad OBJ exchange
  tests/                       Tool checks
workspace/meshes/               Ignored mesh editing revisions
legacy/libyaul/                 Archived reference only; not an active build target
```

**Static/dynamic describe content:** environment/UI versus movable actors.
**Source/generated describe ownership:** tracked assets/recipes versus disposable
`build/` output. Never edit generated meshes as the source of truth.

## Build and play

From MSYS2 bash:

```bash
cd game
./build.sh
./build.sh --hires
```

Build sequentially. The modes have separate objects/images but share asset staging.
Images are `game/build/game.cue` and `game/build/game-hires.cue`.

Double-click **[launch-game.bat](launch-game.bat)** to choose standard 320x240 or
experimental 320x480i. It runs existing builds, validates image availability,
and does not build or kill an existing Kronos instance.
Direct shortcuts: `game/run-kronos.bat` and `game/run-kronos-hires.bat`.

Model tool: `tools/mesh-workshop/open-mesh-workshop.bat`.
Imported tri/quad candidates are **not yet runtime-ready**.

The build requires the existing sibling `../joengine` SDK, MSYS2, Python/Pillow
and the local verified US 1.2 extraction/ROM used by the converters. Do not modify
the shared SDK. Legacy experiments are not imported into active Jo runtime code.

## Focused checks

```powershell
python -m unittest discover -s game/tests
python -m unittest discover -s tools/tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -Check
```
