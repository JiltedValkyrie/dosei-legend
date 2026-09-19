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

First use **launch-game.bat > Config > Paths...** to select your own tools and
save `config.ini`. See [developer setup](tools/launcher/SETUP.md) for dependencies,
the exact OoT decomp/US 1.2 ROM and ROM placement. Windows builds can then use
`game\build.bat` or `game\build.bat -Variant hires`.

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

The build requires a configured Jo Engine SDK, MSYS2, Python/Pillow
and the verified US 1.2 ROM/decomp used by the converters. Do not modify
the shared SDK. Legacy experiments are not imported into active Jo runtime code.

## Controls (current build)

Standard digital Saturn pad; no 3D pad needed. These are Saturn buttons,
not keyboard keys; keyboard bindings depend on Kronos settings. The in-game
pause screen (Start) lists the same mapping.

| Button | What works now |
| --- | --- |
| D-pad | Move relative to camera at the selected walk/run speed; steer while airborne |
| B | Toggle walk/run. Gameplay starts in run; one toggle per press |
| Y | Jump from ground; release and press again for another jump. No double-jump |
| X | Swing the collected sword; cuts grass while the blade is live |
| Hold R | Guard with the collected shield; never rotates the camera |
| A | Talk to a nearby fairy and advance the text box one page |
| B (text box open) | Close the dialogue. That press does not also toggle walk/run |
| L | Lock onto the nearest valid target, or release an existing lock |
| L (no target) | Recenter the camera behind Link |
| D-pad while locked | Strafe around the target and back up; Link keeps facing it |
| Hold Z + D-pad | Look camera: aim the view, bounded. No movement, no shield |
| Start | Open/close the item menu during gameplay; leaves the title screen |
| Menu: D-pad / A / B | Pick a slot, equip the selected item, close the menu |
| Hold C + D-pad | C-Up/Down/Left/Right. Routed and consumed, but no item system exists yet |
| L + R | Switch diagnostic overlay views; compiled out of the clean player-test image |
| L + R + Up | Developer camera comparison: current follow / old camera |

Camera follows automatically. Rolling is automatic on landing, not a button.
Pickups auto-equip when collected. Targeting is a simple Switch-style toggle
against nearby NPCs, not full OoT Z-targeting. The C buttons reach the input
layer and show in the diagnostic overlay, but the item system they should
drive does not exist yet.

## Focused checks

```powershell
python -m unittest discover -s game/tests
python -m unittest discover -s tools/tests
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -Check
```
