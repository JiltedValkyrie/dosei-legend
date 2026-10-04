OoT Saturn (oot-sat) - private dev playtest build @BUILD@
==========================================================

This is a private test build for a few invited testers. Please don't share it.

WHAT YOU NEED
- A Sega Saturn BIOS file (not included).
- Windows, to use the bundled Kronos emulator. On real hardware, see below.

QUICK START (WINDOWS)
1. Unzip everything. Keep the folder layout as it is.
2. Copy your Saturn BIOS into this folder (next to Play.bat) and name it bios.bin.
3. Double-click Play.bat. Kronos starts and boots the game.
   Without bios.bin, set the BIOS once inside Kronos (Settings > General > BIOS),
   close Kronos, then run Play.bat again.

WHY YOU MUST USE THE BUNDLED KRONOS AND ITS INI
- The fix that raises the drawing cap is built into kronos\kronos.exe itself.
  Stock Kronos 2.7 stops after 2048 VDP1 drawing commands per frame and never
  reports the frame as done, so the game freezes. You will reliably hit this in
  the opening nightmare cutscene, right after Ganon appears. This kronos.exe has
  the limit removed; kronos\vdp1-draw-cap-fix.c is the patched source file.
  An INI file cannot fix this. Only the patched exe can.
- kronos\kronos.ini holds the settings the game needs: Cartridge type
  "32 Mbit DRAM" (the 4 MB RAM expansion cart). The game will not start
  without it. The settings are shown in Kronos as:
      Settings > Cartridge > Type: 32 Mbit DRAM
- On Windows, Kronos only reads kronos.ini when it sits in the same folder as
  kronos.exe. Otherwise it uses your user profile's settings, which won't have
  the cart set. So:
    * Always run kronos.exe from the kronos folder (Play.bat does this).
    * Don't move kronos.exe away from kronos.ini.
    * If you change settings inside Kronos, they are saved back to that same
      kronos.ini.

MANUAL LAUNCH (instead of Play.bat)
  Run kronos\kronos.exe, then File > Open ISO/CUE and pick game\game-clean.cue.
  From a command prompt:
      cd kronos
      kronos.exe -b "C:\path\to\bios.bin" -i "..\game\game-clean.cue" -a
  Keep all files in game\ together: the .cue points at the TRACKxx.BIN audio
  tracks next to it.

REAL HARDWARE (SAROO etc.)
- Real Saturn hardware has no 2048-command drawing cap, so the freeze above
  does not happen there.
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
