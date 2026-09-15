# Project handoff - 2026-09-15

## Read first

This is a Sega Saturn/libyaul Kokiri Forest vertical slice. The source tree was
reorganized; old IDE tabs pointing directly into `title-screen/*.c` are stale.
See [README.md](README.md) for the directory map and build command.

**Latest user report: the reorganized build did not crash on the last run.**
Previously the textured renderer reached **7 FPS**, then raised an SH-2 invalid
opcode during automatic rotation without input. No run duration or updated FPS
was supplied for the successful run, and no confirmed crash fix was introduced
during reorganization. Treat stability as unproven, not as a guaranteed failure
or a solved issue.

## Current implementation

- US 1.2 geometry: three Kokiri rooms, 1,268 positions, 2,060 triangles,
  1,692 collision triangles. Native world scale, 320x240 viewport.
- Triangle textures use VDP1 A/B/C/C sprites. Shared projection, early culling,
  hardware division, and textured near-plane clipping are active. The earlier
  flat-color clipping fallback is gone. Quad conversion has not been done;
  it may help but has not been shown to explain the low frame rate.
- Collision and manual camera movement were confirmed working by the user.
  Start toggles title/automatic rotation. D-pad moves, L/R turns, X/Z raises/
  lowers, Y + Up/Down pitches, C levels. Edit `src/scene/kokiri_camera.h` under
  `title-screen`: manual move 16, diagonal 12, yaw 360, pitch 240 per rendered
  frame. Automatic yaw remains 90. The previous L/R same-direction report is
  not reproduced in tests; explicit opposite increments need runtime confirmation.
- Controller processing and INTBACK are paired in VBlank-out. Main consumes a
  latched input snapshot. Do not casually move parsing back into the slow draw
  loop: the user reported that this change stopped the earlier controller crash.
- Music was rebuilt from **US 1.2** and approved as "PERFECT". It uses direct
  SCSP playback in `src/audio/`, independent of rendering via VBlank-in.
  Ponesound and the old US 1.1 converters are retired. Preserve this working
  audio unless there is evidence requiring an audio change.

## Next work and evidence

1. Establish sustained stability and capture any new failure with its matching
   ELF. [DEBUGGING.md](title-screen/docs/DEBUGGING.md) records the prior dump:
   PC `06006114`, PR `060061EA`, in the renderer after clipping. The old ELF
   contains a valid instruction there; that alone does not prove an emulator bug.
2. If available, capture P0/P2 words from the game's exception screen. The
   Kronos dialog only has registers. Preserve existing diagnostics until the
   intermittent failure is understood.
3. Profile CPU processing versus VDP1 draw/wait costs before more speculative
   performance changes. Earlier stage-70 stalls and host RAM growth did not
   establish a game-side memory leak.
4. Improve texture fidelity/depth ordering, then add actors and gameplay.

The exact pre-reorganization crash ELF is local-only in
`title-screen/build/crash-7fps/`. The earlier controller-fault ELF is in
`title-screen/build/crash-0600bae0/`. Neither is versioned; addresses change on
rebuild and must not be mapped with a different ELF.

## Validation and local dependencies

The reorganized build succeeded; **21 tests pass**, including full idle-rotation
clipping output guards. Native tests do not exercise SH-2 interrupts, target
DIVU behavior, or VDP1. Do not label them proof of emulator/hardware stability.

From the repository root in PowerShell:

```powershell
& C:/msys64/usr/bin/bash.exe -lc 'source ~/.yaul.env && cd /d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen && make'
python -m unittest discover -s title-screen/tests -p "test_*.py"
```

Use `title-screen/run-kronos.bat` for normal testing. The optional debug-core
launcher has a separate configuration; earlier runs were too slow to be useful.
Build/tests use the local sibling `../sh2eb-elf` SDK, MSYS2, Python/Pillow, MinGW,
and extracted audio in `title-screen/build/audio-source/`. For regeneration use
`D:/Workspace-Claude/game-decomps/n64/oot`, **ntsc-1.2**, ROM MD5
`57a9719ad547c516342e1a15d5c28c3d`. The fan MIDI is only a comparison reference.
The older bitmap generators still reference a historical extraction; do not
mistake them for the US 1.2 geometry/audio pipeline or regenerate them blindly.

## Documentation

- [Scene and controls](title-screen/docs/SCENE.md)
- [Crash evidence](title-screen/docs/DEBUGGING.md)
- [Audio pipeline and regeneration](title-screen/docs/AUDIO.md)
- `title-screen/docs/history/`: superseded snapshots, not current instructions.
- `.claude/documentation/audio/`: updated pointers and audio work list.

GitHub: `https://github.com/JiltedValkyrie/dosei-legend.git`; integration branch
is `main`. This checkpoint includes the scene implementation, cleanup, and handoff.
