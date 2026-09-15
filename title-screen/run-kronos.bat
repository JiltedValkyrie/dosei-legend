@echo off
set KRONOS_DIR=D:\Workspace-Claude\saturn-homebrew\Kronos\build_kronos\src\port\qt
set BIOS=D:\Workspace-Claude\saturn-homebrew\bios\Sega Saturn BIOS (E) (1.00)\Sega Saturn BIOS (E) (1.00).bin
set IMAGE=%~dp0title-screen.cue

rem Kronos needs libopenal-1.dll / libstdc++-6.dll / libgcc_s_seh-1.dll /
rem SDL2.dll from the MSYS2 mingw64 toolchain. Explorer's PATH doesn't
rem include that folder, so double-clicking this without the line below
rem fails with "DLL not found" popups and no window ever appears.
set PATH=C:\msys64\mingw64\bin;%PATH%

rem Kronos also looks for its config/plugins relative to the current
rem directory, not its exe's location - launching it from elsewhere fails
rem silently. So cd into its own folder first.
pushd "%KRONOS_DIR%"
start "" kronos.exe -b "%BIOS%" -i "%IMAGE%" -a
popd
