# Jo game launcher

Double-click `../../launch-game.bat`. Choose **Play Dosei Legend (Standard)** (default), **Play Dosei Legend
(320x480i)**, or **Debug Mode**, then Run selected. Standard play uses the
Clean build at `game/build/game-clean.cue`.

**Config > Paths...** selects the local Jo SDK, MSYS2, Python, Kronos, runtime
DLL folder, Saturn BIOS, OoT decomp and US 1.2 ROM directory. Save writes the
git-ignored root `config.ini`. Validation checks paths, Pillow and the ROM MD5;
buttons open the configured decomp and ROM folders. See [developer setup](SETUP.md)
for the exact ROM, decomp revision and build instructions.

The selector launches configured Kronos directly, checking the CUE and referenced
data first. Direct `game/run-kronos*.bat` shortcuts call the same selector.
This is an explicit three-entry catalog, not arbitrary batch discovery. Add variants
to `$variants` in `kronos-launcher.ps1`, with Image paths relative to the repository
root. Missing images disable launch.

Refresh updates timestamps. It does not build, kill Kronos, or change emulator
settings. Close Kronos before switching.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -SmokeTest
```

## Map Workshop

Open `../map-workshop/open-map-workshop.bat` for the room/layout editor. Its
Build Clean button uses the existing build dialog. See the Map Workshop Help
for original/named build selection, mesh replacement and source/material tools.
