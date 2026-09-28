# Continue / Link room pause corruption: live evidence

Human reported corrupted pause pages after Continue in Link's house. Inspected
the existing Kronos process without changing focus, input, RAM or restarting.

## Observed

- PID 28188, Kronos v2.7.0, game-clean.cue. Background PrintWindow capture
  reproduces the supplied screenshot: displaced frame and repeated bad glyphs.
- Process started 2026-09-27 22:13:01; mounted game-clean.iso was rewritten at
  22:15:58. Times are local machine timestamps.
- Read-only process inspection captured emulated VDP2 RAM/registers, high work
  RAM and cartridge RAM. Reconstructing RGB cells offline gives the same
  corruption: this is bad pixel data, not merely a zoom/register mismatch.
- Running work RAM contains cart base 0x22790000 (old 0x70000 carve), not
  current 0x2278F000 (0x71000 carve). Current ELF is not the running binary;
  do not use its symbol addresses to diagnose this session.
- Running pause cache is cartridge offset 0x3AD000; font follows at +153600.
  Parsed the current ISO9660 directory directly, using 2048-byte sectors.
- PAUSE50.BIN: current LBA 2811, length 153600. The complete live cache equals
  current ISO bytes at LBA **2813**, not 2811, byte for byte.
- PAUSEFNT.BIN: current LBA 2886, length 1024. The complete live font buffer
  equals current ISO bytes at LBA **2888**, not 2886, byte for byte.
- Thus both reads are exactly 4096 bytes late. The real font also appears
  inside the page-buffer tail, exactly where the shifted read predicts.

## Conclusion and next check

Mounted ISO changed during this session; old cached file positions now point
into different data. This explains the observed page displacement and wrong
glyphs. It does not establish a Continue renderer defect. No speculative
renderer or respawn changes made. No claim of a fresh-boot Continue pass.

Close/reopen Kronos with the completed image (cold boot, no old emulator state),
then repeat death -> Save Yes/No -> Continue Yes -> pause in Link's house and
forest. If corruption recurs without any mounted-file replacement, investigate
that fresh instance separately. Preserve BUG-048/049/052 acceptance checks.
Never rebuild a mounted ISO or its audio tracks during a runtime test. Close
Kronos first or test a separate immutable copy of the complete disc set.

Evidence (ignored local artifacts): build/generated/continue-menu-before.png;
build/continue-evidence/{vdp2ram,vdp2regs,highwram,cart_ram}.bin;
page.png (reconstructed live RGB cells), cache.png, iso-files.json.
Read helper: build/read-kronos-evidence.py. It reads only the named emulator's
emulated-memory buffers; no writes. Process left running in the observed state.
