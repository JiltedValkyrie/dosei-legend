# Jo game launcher

Double-click `../../launch-game.bat`. Choose standard **320x240** or experimental
**320x480i**, then Run selected. Only Jo builds are offered.

The selector uses the corresponding `game/run-kronos*.bat`, checking its CUE
and referenced data first. This is an explicit two-entry catalog, not arbitrary
batch discovery. Add variants to `$variants` in `kronos-launcher.ps1`, with Image
and Batch paths relative to the repository root. Missing images disable launch.

Refresh updates timestamps. It does not build, kill Kronos, or change emulator
settings. Close Kronos before switching.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -Check
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools/launcher/kronos-launcher.ps1 -SmokeTest
```
