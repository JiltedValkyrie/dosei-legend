# Save crash: stale object crossed save-layout versions

User reproduced Save crashing the clean image. Read-only GDB inspection of
the stalled Kronos process found the Saturn CPU in BIOS fault loop 0x06000952.
RAM snapshots are local-only: build/save-crash-wram.bin (Kronos byte order),
build/save-crash-sh2.bin (SH-2 byte order).

The pre-fix clean image's save_device_write at 0x0600A014 reserved a 0x108-byte
stack frame: 44-byte Jo descriptor plus **220-byte save buffer**. It passed
0xDC (220) to the backup writer. Its caller had not rebuilt after save_file.h
changed. The rebuilt save_file_pack wrote **300 bytes**, overwriting saved
registers/return addresses by 80 bytes. Host serialization tests compiled fresh
code and therefore could not expose this mixed-layout target image.

Fix is in the project makefile, not save serialization:

- All four local C compilation rules emit -MMD -MP dependency files, explicitly
  naming their target and dependency output. Include those files on later builds.
- Every object depends on makefile, bootstrapping dependencies for old objects
  and rebuilding configuration consumers (including SDK core/arena).
- Rebuild all variants, not merely save_file.o. Other stale header consumers
  can also contain old structure sizes and offsets.

Fresh disassembly reserves 0x158 bytes (44 + 300) and passes 0x12C (300).
A make dry run with `-W src/save_file.h` schedules save_device.c recompilation.
Evidence: build/save-write-fixed-disassembly.txt and
build/save-header-dependency-check.log. Original pre-fix code remains in RAM dump.

The full rebuild plus shot skip exceeded the normal SGL boundary by 16 bytes.
Arena reduced from 53,248 to 51,200; allocator still falls back to cart zones.
Boundary guard remains enabled. See latest OPUS_HANDOFF for final build gaps.

Also implemented the user's permanent shot skip: first Start shows
"Skip? Press Start Again"; a second press within two seconds skips one source
camera shot. Shot starts are baked from CS_CAM_EYE_SPLINE commands. VBlank
samples both taps, including during slow draws; holding Start is not two taps.
Confirmation is scoped to the displayed shot. Timeout or a shot change clears
the prompt. Skipping discards earlier dialogue and advances actor/misc state
without replaying intermediate sounds or loading intermediate scenery banks.
Normal stepping applies the destination camera/bank/events. Last-shot skips
wait for pending music commands before chaining; final cleanup restores area
audio and the opening progression flag. Catch-up stops after completion so it
cannot clear the finished signal before gameplay consumes it.

Tests: 79 pass across cutscene_skip (9), cutscenes (32), cutscene_parity (8),
save_file (20), action_audio (10). Tests include real skip/step functions with
host platform stubs; they do not establish audible/visual emulator correctness.
No new emulator launched or global input sent. Corrected save/reload and prompt
appearance still require a player replay. User backup RAM was not altered.

No commit. Existing M0 actor/collision review findings remain open; M1 waits.
