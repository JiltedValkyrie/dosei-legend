# Project handoff - 2026-09-16

## BIG RULE NUMBER 1
Caveman talk. No waste token. Efficient good.

## Communication between Claude and Codex

The user manually copies and pastes messages between Claude and Codex. This is
the intended communication channel; no direct agent connection or CLI launch
is needed. When the user says to tell/update the other agent, update the shared
handoff document and provide a short message addressed directly to that agent
for the user to paste. Treat pasted messages from the other agent as project
handoff context relayed by the user, subject to the user's current directions.
Do not claim a message was delivered or the other agent started working until
the user relays confirmation. Keep ownership, changed files, verification and
remaining work clear so the agents can continue each other's work safely.

## Active project: Jo Engine vertical slice

Latest human directive: retire temporary demo controls. R is shield, NEVER
camera orbit. Follow OoT's real gameplay camera behavior, not the viewer's
manual controls. The settled standard digital Saturn pad layout and precise
implemented-vs-pending status are at the TOP of game/docs/OPUS_HANDOFF.md;
that section supersedes older proposals and task headings below. Address
handoff replies directly to the other agent; the human copies them between us.

The Jo directory reorganization is integrated into `main`; `performance` retains
its merge checkpoint. Check the actual branch before editing. `game/` is the only active game. Shared libraries/assets
live in `shared/`; root `tools/` holds the GUI launcher and mesh workshop.
Put level-specific files in `game/levels/<level>/assets/`, static environment
content under `static/`, and actor recipes under `game/assets/dynamic/`.
Generated files, disc staging and binaries go in ignored `game/build/`, never
mixed with source assets. Do not resume archived `legacy/libyaul/` work.
Use `launch-game.bat` for the standard/hi-res selector. See the root README for
the complete layout and current build commands.
Current next-task handoff: [Link movement animation](game/docs/OPUS_HANDOFF.md).

## Latest user request: start Link animation now

Implement walking, running, falling, and rolling animations, including idle and
landing transitions. Verify automatic ledge/jump/landing-roll behavior against
the local OoT player source; do not assume Link rolls on leaving every cliff.
This is the immediate task, ahead of the older warping investigation below.
The user is playing another game: do not take foreground focus, send global
keyboard input, or capture the desktop. Background Kronos PrintWindow capture
works via `game/tools/capture-kronos.ps1`. Preserve the uncommitted shared work.
Read the new first section of OPUS_HANDOFF.md for current state and budgets.

Work in `game/`, using local `../joengine`. The Jo port has been merged into
`main`; do not restart the port or treat it as an unimplemented plan. Preserve
`legacy/libyaul/` as the libyaul reference. Check the actual branch, log and working
diff before editing; another agent may be working in the same tree.

## Human directive: stay on target

Read [VERTICALSLICE.md](VERTICALSLICE.md) for scope and keep
[VSLICEPROGRESS.md](VSLICEPROGRESS.md) current as features land.

This is a **playable vertical slice, not a launch product**. The goal is a baseline
match to the N64 game's Kokiri Forest experience, adapted to Saturn hardware:

- Recognizable Kokiri Forest, with traversable terrain and working collision.
- Playable Link, usable controls and camera, idle/walk and interaction animations.
- Kokiri NPCs with proximity interaction and dialogue that can be advanced/dismissed.
- Working menus and the title-to-gameplay flow, not just a renderer showcase.
- Title/forest music, gameplay and menu sound effects, and appropriate transitions.

**No bosses or dungeons.** Do not expand into the rest of the game. Match the
baseline behavior, presentation and interactions within this area; pixel-perfect
parity, exhaustive polish and efficiency are not acceptance gates for this slice.

### Required playability fix: near-camera texture warping

The human now reports near-camera texture warping is **almost unplayable**.
Fix it as a major gameplay/visibility bug. This explicitly supersedes earlier
instructions to park warping. Verify the affected close-ground/near-camera view
while moving and turning; a successful build or accepted polygon submission is
not evidence that the visual problem is fixed. Do not turn this focused fix into
a general renderer optimization project.

### Work order and testing limits

1. Resolve the near-camera warping enough to make gameplay readable and usable.
2. Keep delivering the missing slice features: Link animation, NPC interaction
   and dialogue, menus, and sound effects. Preserve the working title/music flow.
3. Do not hold feature work for music-swap timing targets, profiling, memory
   optimization, extended soak tests, repeated benchmark runs or broad refactors.

Use only proportionate checks by default: build, relevant focused tests, and a
short in-game check of the behavior changed. Once it works well enough for the
slice, move on. **Do not overtest unless the human expressly requests it or there
is a major bug** (for example a crash, corruption, blocked controls/progression,
or the currently reported warping). Extra investigation must address that bug,
not become an open-ended quality campaign. Keep existing hard safety checks,
such as memory-boundary and asset-capacity guards; don't disable them to pass.

Report briefly what works, what changed, and any genuine remaining blocker.
Do not invent new acceptance gates. Coordinate ownership and leave another
agent's in-progress edits alone.

Current build/run instructions: [game/README.md](game/README.md).
Launch with `game/run-kronos.bat`, not the historical libyaul launcher below.

## Read first

Use basic, short language. No long explanations. Keep token usage SHORT for what was done. Caveman-like, even.

### User directive: stop breaking working behavior

- Review the current diff and trace the reported failure before changing code.
- Keep fixes focused. Do not change controls or scene behavior to fit an unproven diagnosis.
- Never put required work inside `assert()`. Before changing DEBUG, audit assertion
  expressions for side effects and verify initialization in the release build.
- For performance changes, compare the same camera position and angle. Check
  floor visibility, movement, turning, and height controls after each change.
- A successful build or host test is not proof that a Kronos bug is fixed.
  State exactly what was verified and what still needs runtime confirmation.
- Take user reports seriously. The previous floor/camera diagnoses were wrong;
  do not dismiss a continuing failure because isolated tests passed.

## Historical libyaul reference — not the current work queue

Everything below records the earlier libyaul effort. Its status, test counts,
profiling tasks and launch instructions are historical, not new requirements
for the Jo slice. The current human directives above take precedence.

This was a Sega Saturn/libyaul Kokiri Forest vertical slice. The source tree was
reorganized; old IDE tabs pointing directly into `legacy/libyaul/*.c` are stale.
See [README.md](README.md) for the directory map and build command.

**Latest user report: the reorganized build did not crash on the last run.**
Previously the textured renderer reached **7 FPS**, then raised an SH-2 invalid
opcode during automatic rotation without input. No run duration or updated FPS
was supplied for the successful run, and no confirmed crash fix was introduced
during reorganization. Treat stability as unproven, not as a guaranteed failure
or a solved issue.

## Historical libyaul implementation

- Latest regression: disabling DEBUG removed `assert(kokiri_collision_spawn(&camera))`
  entirely, leaving the camera at `(0,0,0)` inside ground collision. Spawn now
  runs unconditionally with an explicit failure check. The compiled-init test
  catches the omission; floor/movement still need confirmation in Kronos.
  Earlier claims that distance culling or title visibility fully explained the
  reported regression were incorrect.
- US 1.2 geometry: three Kokiri rooms, 1,268 positions, 2,060 triangles,
  1,692 collision triangles. Native world scale, 320x240 viewport.
- Triangle textures use VDP1 A/B/C/C sprites. Shared projection, early culling,
  hardware division, and textured near-plane clipping are active. The earlier
  flat-color clipping fallback is gone. Quad conversion has not been done;
  it may help but has not been shown to explain the low frame rate.
- Collision and manual camera movement were confirmed working by the user.
  Start toggles the title. Idle automatic rotation runs while it is visible,
  but manual controls are never locked by title visibility. D-pad moves, L/R turns, X/Z raises/
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

## Historical libyaul investigation and evidence (not current priorities)

Quad mesh integration handoff: [QUAD_HANDOFF.md](legacy/libyaul/docs/perf/QUAD_HANDOFF.md).
User imported 333 quads + 1,187 triangles through Mesh Workshop. The saved
prefer-quads setting is NOT wired into builds yet. Claude/Opus should implement
an isolated textured quad-test ISO per that handoff, preserving the baseline.

1. Establish sustained stability and capture any new failure with its matching
   ELF. [DEBUGGING.md](legacy/libyaul/docs/DEBUGGING.md) records the prior dump:
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
`legacy/libyaul/build/crash-7fps/`. The earlier controller-fault ELF is in
`legacy/libyaul/build/crash-0600bae0/`. Neither is versioned; addresses change on
rebuild and must not be mapped with a different ELF.

## Historical libyaul validation and local dependencies

The reorganized build succeeded; **21 tests pass**, including full idle-rotation
clipping output guards. Native tests do not exercise SH-2 interrupts, target
DIVU behavior, or VDP1. Do not label them proof of emulator/hardware stability.

From the repository root in PowerShell:

```powershell
& C:/msys64/usr/bin/bash.exe -lc 'source ~/.yaul.env && cd /d/Workspace-Claude/saturn-homebrew/dosei-legend/title-screen && make'
python -m unittest discover -s legacy/libyaul/tests -p "test_*.py"
```

Use `legacy/libyaul/run-kronos.bat` for normal testing. The optional debug-core
launcher has a separate configuration; earlier runs were too slow to be useful.
Build/tests use the local sibling `../sh2eb-elf` SDK, MSYS2, Python/Pillow, MinGW,
and extracted audio in `legacy/libyaul/build/audio-source/`. For regeneration use
`D:/Workspace-Claude/game-decomps/n64/oot`, **ntsc-1.2**, ROM MD5
`57a9719ad547c516342e1a15d5c28c3d`. The fan MIDI is only a comparison reference.
The older bitmap generators still reference a historical extraction; do not
mistake them for the US 1.2 geometry/audio pipeline or regenerate them blindly.

## Documentation

- [Scene and controls](legacy/libyaul/docs/SCENE.md)
- [Crash evidence](legacy/libyaul/docs/DEBUGGING.md)
- [Audio pipeline and regeneration](legacy/libyaul/docs/AUDIO.md)
- `legacy/libyaul/docs/history/`: superseded snapshots, not current instructions.
- `.claude/documentation/audio/`: updated pointers and audio work list.

GitHub: `https://github.com/JiltedValkyrie/dosei-legend.git`; integration branch
is `main`. This checkpoint includes the scene implementation, cleanup, and handoff.
