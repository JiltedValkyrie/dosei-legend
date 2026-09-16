# Current crash investigation

## Confirmed user observations

1. Pairing SMPC processing and INTBACK in VBlank-out stopped the previous crash
   for the user's test; collision and manual movement worked at about 4 FPS.
2. The next renderer restored clipped textures, cached projection, culled before
   sorting, and used hardware division. It reached **7 FPS**, then crashed after
   several seconds of automatic rotation with no input.

3. After the project was reorganized, the user reported: **"It did not crash
   this last time."** No run duration or new FPS figure was supplied.

Current status: the latest run succeeded, but the previous intermittent crash
has no established root cause. No targeted runtime fix was made during the
reorganization. Passing host tests and one successful run do not establish
sustained stability.

## Latest dump (7 FPS build)

```text
Master SH2 invalid opcode
PC 06006114   PR 060061EA   SP 06003CBC   SR 00000101
R0 00000003   R1 06003E58   R2 00000002   R3 00004B92
R4 06003E44   R5 06003BE8   R6 0000000C   R7 00000230
R8 0000000D   R9 002049F4   R10 000000E3  R11 00000191
R12 06003CF4  R13 000001CA  R14 00000003
MACH FFFFFFFF MACL 0000003C
```

The exact ELF, symbols, and binary are saved locally in `build/crash-7fps/`.
These ignored build artifacts are **not on GitHub**; a fresh clone will not
contain them. Preserve the matching ELF before rebuilding after any new crash.
Use that ELF for this dump: reorganizing source files changes link order and
addresses. The earlier controller-fault ELF is in `build/crash-0600bae0/`.

`06006114` lies in `kokiri_scene_update_and_draw`, at `D24D`, a valid PC-relative
`mov.l` loading the small-structure-copy helper. `060061EA` is the return address
after `kokiri_clip_frustum`. R0 is 3, consistent with a returned triangle.
The reported address is not in controller lookup and does not identify an
assertion or a proven buffer overflow.

The on-disk opcode being valid does **not** establish that Kronos is at fault.
We still need actual memory contents at failure to distinguish changed code
from an instruction-fetch/decode problem. No speculative crash workaround was
introduced during the source-tree reorganization.

## Diagnostics

- `src/debug/crash_probe.c` and `crash_vectors.sx`: game-side illegal-instruction
  handler adds `P0` and `P2` instruction words to the SDK exception screen, at
  saved PC-2 and PC. P2 reads bypass the SH-2 data cache. Kronos's own dialog
  does not include those words. Capture the game exception screen if available.
- `src/debug/frame_probe.c`: top-left hexadecimal stage, completed frames,
  VBlank ticks, VDP1 EDSR and COPR. The title layer must be visible to see it.
- Stages: `10` input snapshot, `20` camera, `30` transform, `40` command building,
  `50` DMA submission, `60` transfer wait, `70` drawing/swap wait, `80` VDP2 sync.
- `run-kronos.bat`: normal launch. `run-kronos-debug-core.bat`: separate debug
  interpreter configuration; its earlier performance was unusable, so it is
  not the normal test launcher.

Next diagnostic work: inspect P0/P2 against the matching ELF; reproduce in a
second execution core if feasible; profile CPU and VDP1 separately once stable.
Do not interpret a higher frame rate or a short successful run as a crash fix.

## Reorganization validation

The reorganized project builds and passes 21 tests. An additional native test
runs all 2,060 faces through clipping over a full revolution in 90-unit yaw
steps, checking output guards and near-plane bounds. No output overrun was
observed. This does not exercise hardware division, interrupts, or VDP1 and
cannot rule out a target-only failure. The guard-buffer test helper copies its
returned ctypes vertices so they do not outlive their backing allocation.
