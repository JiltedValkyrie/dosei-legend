# Navi flight frame 99 — 2026-09-22

Baseline: commit 8fb5b5d, clean image, project-local draw-cap-fixed Kronos.
Read-only inspection of the user's running emulator found scene 2's internal
frame at 100, applied/displayed frame 99, and scenery bank still 0. No text
hold or diagnostic frame limit explained it. Both CPUs remained in the normal
SGL frame synchronization/command loops; VDP1 completed draws between callbacks.
The original image/map were preserved under ignored `build/frame99-baseline.*`.

`cutscene_step` tested current-draw completion once at each callback entry.
SGL starts another VDP1 draw before returning, so a busy result could defer the
bank switch indefinitely while the same frame 99 was submitted again. The
gameplay room-switch path used the same check.

Both paths now use `vdp1_wait_for_draw_end`: allow the in-flight draw to finish
without resubmitting it. Textures remain untouched until draw completion. The
wait returns false after two video ticks, or 1,048,576 polls if ticks stop, so
it cannot become an unbounded wait. No runtime floating point was introduced;
SH-2 disassembly shows integer polling and the existing demo clock.

Validation:

- Five executable host tests: already complete, delayed completion, stuck
  draw timeout, clock wrap, and stopped clock poll limit.
- 505 tests run; no assertion failures, one skip, the existing two setup
  compile errors in equipment-draw and forest-partition fixtures remain.
- Separate automatic scene-2 replay passed every 100-frame bank boundary and
  reached scene 3 frame 214. Captures: ignored `build/frame99-replay-2.png`
  (scene 2 frame 502) and `build/frame99-replay-3.png` (scene 3 frame 214).
- Normal/clean playable images rebuilt without probe/auto-confirm flags.
  SGL boundary checks pass: 6,896 / 17,712 bytes remaining respectively.

This fixes the repeatable frame-99 bank-switch starvation. It does not prove
the earlier intermittent nightmare crashes have the same cause. Restart the
rebuilt playable image; the already-running emulator retains the old code.
