# Kronos launcher

Double-click `title-screen/run-kronos.bat` for the Windows GUI. Select a variant
and click **Run selected**. Refresh after rebuilding to update availability and
image timestamps. Missing CUE/data files disable launch. No builds run here.

Variant shortcuts live in this folder. The GUI and shortcuts share
`kronos-launcher.ps1`, including dependency paths and launch options.
Close Kronos between runs; the launcher does not kill an existing instance.
No emulator settings are changed except when explicitly selecting the existing
debug-interpreter preparation workflow.

| Variant | Image under title-screen | Build options |
| --- | --- | --- |
| Normal | title-screen.cue | make |
| Baseline | build-perf/title-screen.cue | make PERF_BENCH=1 |
| No resampling | build-perf-notex/title-screen.cue | make PERF_BENCH=1 ABLATE_TEXTURE=1 |
| No score advancement | build-perf-nomus/title-screen.cue | make PERF_BENCH=1 ABLATE_MUSIC=1 |
| Staged | build-perf-staged/title-screen.cue | make PERF_BENCH=1 TEXTURE_STAGE_DISABLE=0 |
| Debug interpreter | title-screen.cue | make |

The ablations deliberately break visuals or music; they are not shipping builds.
Timestamps identify the existing files, not whether they are up to date with source.
The retired build-perf-control image is not listed: staging-off build-perf is now
the baseline. Existing build directories and saved results have not been moved.

Read-only path check, without starting the GUI or emulator:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File title-screen/tools/launchers/kronos-launcher.ps1 -Check
```
