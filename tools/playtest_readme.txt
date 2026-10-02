OoT Saturn (oot-sat) - private dev playtest build @BUILD@
==========================================================

This is a private test build for a few invited testers. Please don't share it.

WHAT YOU NEED
- A Sega Saturn BIOS file (not included). In Kronos: Settings > General > BIOS.
- The 4 MB RAM expansion cartridge. The included Kronos is already set to it
  (Cartridge type: 32 Mbit DRAM). The game will not start without it.

HOW TO PLAY (WINDOWS)
1. Run kronos\kronos.exe.
   Use THIS Kronos. The stock Kronos 2.7 freezes in the opening nightmare
   cutscene: it stops drawing after 2048 VDP1 commands. This copy has that
   limit removed (kronos\vdp1-draw-cap-fix.c is the patched source file).
2. Set your BIOS file once (Settings > General).
3. File > Open ISO/CUE and pick game\game-clean.cue.
   Keep all files in game\ together: the .cue points at the TRACKxx.BIN
   audio tracks next to it.

REAL HARDWARE (SAROO etc.)
- Put the whole game folder on the device and pick game-clean.cue.
- You need 4 MB of cart RAM.

CONTROLS (standard Saturn pad)
  D-pad / analog stick  move (the analog stick walks or runs depending on how far you push)
  A                     interact / talk
  X                     attack
  Y                     jump
  B                     hold to walk, tap to cancel / put away
  C + D-pad             the four N64 C buttons (C + Up = first-person view)
  Z                     target / recentre camera
  L                     toggle minimap
  R                     shield
  Start                 pause menu

WHAT TO REPORT
- Freezes or crashes: what you were doing and where. A screenshot helps.
- Anything that plays differently from the N64 original.
- Slowdown: where, and how bad.
