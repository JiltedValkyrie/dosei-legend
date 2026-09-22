# Nightmare freeze: Kronos draw-command cap

## Unresolved later report: striped screen before Ganon

The user reported another failure after the fixes, showing vertical dark blue
stripes and VDP1/VDP2 near 57 FPS. This is not established as the old command-cap
deadlock or the frame-185 diagnostic hold. No Kronos process remained when
inspected, and no recent Windows Application Error report for it was found.
The executable/image used are awaiting user confirmation. Do not mark resolved.

A new isolated `OPENING_CHECK=1 CUTSCENE_PROBE=0 CUTSCENE_PROBE_AUTO=1
CLEAN_TEST=1` replay exercised the house-to-nightmare load, rather than skipping
straight to the nightmare. It passed nightmare frame 519 with music active and
reached scene 2 frame 99 (`build/opening-full-after-ganon.png`). Automatic confirm
is diagnostic-only; it does not reproduce the user's exact input timing.
Need a still-running failing process to inspect CPU/VDP state and actual image.

## Earlier confirmed command-cap failure

Baseline: `e3ab419` plus the uncommitted opening scenery/readability fixes.
Normal SGL clipping, 3,750 polygons / 3,200 vertices. Reproduction used
`OPENING_CHECK=1 CUTSCENE_PROBE=1`, isolated from player disc/object paths.

The original Kronos 2.7 build froze at nightmare frame 456 on two runs, with
VDP1 FPS zero. A read-only snapshot of our test process established:

- Master SH-2 waits in `slSynch` (`synch_wait`, return PC `0x06035c36`).
- Slave SH-2 is idle; the CPU polygon queue has completed.
- VDP1 EDSR is 1 (current drawing has not completed).
- `nbCmdToProcess` is **2048**, exactly `CMD_QUEUE_SIZE` in Kronos `vdp1.h`.
- `Vdp1Draw` stops its loop at that cap without reaching the list's end command
  or setting EDSR.CEF. Subsequent calls keep the same count and cannot progress.

This explains variable freeze frames: only a frame emitting enough visible
primitives hits the cap. It was not a demonstrated texture-swap failure.
The nightmare music bank was active in the frozen process; before frame 330
the original scene intentionally has no music.

`tools/build_kronos_draw_fix.py` compiles a local copy of `vdp1.c`, changing only
the guard to the full VDP1 command address space (512 KiB / 32 bytes). It copies
the existing static archive and relinks to `build/kronos-draw-fix/kronos.exe`.
It does not write upstream source/build files. The working portable `kronos.ini`
must accompany the executable: otherwise its default SH-2 core is unavailable
in this build and boot reports "Cannot initialize SH-2". The helper copies it.

Rebuild command from repository root:

```powershell
python game/tools/build_kronos_draw_fix.py --build D:/Workspace-Claude/saturn-homebrew/Kronos/build_kronos --toolchain C:/msys64/mingw64/bin --output game/build/kronos-draw-fix
```

The same test disc passed the entire nightmare and reached scene 2 frame 60
in the corrected emulator (`build/nightmare-capfix-end.png`). Local `config.ini`
now selects this executable for the launcher. Restart existing emulator sessions
to use it; an already running process still contains the old guard.

A separate valid lifetime bug was also repaired: rain POINT/POLYGON/ATTR tables
were stack locals, while `slPutPolygon` queues their pointers for the slave.
They now have static storage. That correction alone did **not** fix the observed
2048-command deadlock, and is not claimed as its cause.

The later user screenshot at scene 1 frame 185 came from the camera diagnostic
compiled with CUTSCENE_PROBE_FRAME=185. That flag intentionally skips cutscene
steps at the requested frame while rendering continues. Removing the flag
passed frame 320 and reached scene 2 frame 99 with the new SFX enabled. Held
camera tests now print CAMERA TEST HOLD explicitly. Final player images and
the unpaused opening-check image do not contain the hold.
