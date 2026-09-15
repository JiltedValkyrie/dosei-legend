# Dosei Legend - Kokiri Forest on Sega Saturn

A libyaul vertical slice of Ocarina of Time's Kokiri Forest.

## Status

The renderer reached **7 FPS** before an intermittent SH-2 invalid-opcode crash.
The user reports that the latest reorganized build **did not crash on the last
run**. No confirmed root-cause fix or long-run stability result is established.
Start with [the Claude handoff](CLAUDE.md) and
[debugging status](title-screen/docs/DEBUGGING.md).

## Project layout

```text
title-screen/
  src/main.c         Startup, title UI, controller polling
  src/audio/         SCSP music player
  src/scene/         Renderer, camera, clipping, collision
  src/debug/         Frame probe and exception handlers
  assets/generated/ Generated score header and asset manifests
  assets/            Built-in bitmaps and audio
  cd/                Scene loaded from disc
  tests/             Native C and asset regression tests
  tools/             Asset conversion and emulator support
  docs/              Current reference and debugging status
  docs/history/      Superseded investigation notes
  build/             Ignored binaries, previews, extracted sources
  Makefile           Saturn build
  run-kronos.bat      Normal emulator launcher
```

## Current build

- Filled and textured geometry from the verified **US 1.2 ROM**.
- Collision-aware camera in the village; automatic turning while the title is visible.
- All three `spot04` room display lists: 1,268 positions and 2,060 triangles.
- **Start** toggles the title and switches between automatic and manual camera control.
- Title hidden: D-pad moves, L/R turns, X/Z raises/lowers, Y + Up/Down pitches, C levels.
- Direct SCSP title music continues while the title is hidden.

Launch `title-screen/run-kronos.bat`, or load `title-screen/title-screen.cue`
after building. This workspace uses the sibling `../sh2eb-elf` toolchain and
MSYS2 configuration in `~/.yaul.env`; these local dependencies are not in this repo.

## Build

In the configured MSYS2 shell:

```sh
source ~/.yaul.env
cd /d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen
make
```

The converted scene ships in `title-screen/cd/FOREST.BIN`. Regenerate with Python,
Pillow, your own US 1.2 ROM, and the decomp's segment table:

```powershell
python title-screen/tools/build_kokiri_scene.py --oot-root D:/Workspace-Claude/game-decomps/n64/oot
python -m unittest discover -s title-screen/tests -p "test_*.py"
```

Run audio tests after `make` to check linked assets. See
[scene details](title-screen/docs/SCENE.md) and [audio details](title-screen/docs/AUDIO.md).

## Vertical slice milestones

This build establishes static room rendering and the title/music layer.
Next: establish sustained stability, profile CPU/VDP1 costs, improve depth
ordering/materials, then add Link and
room/actor interaction. The project allows the 4 MB expansion
cartridge; this scene currently fits base RAM and VDP1 VRAM.

The collision wireframe and unused Ponesound implementation remain in Git
history. Historical investigation notes are not current build instructions.
