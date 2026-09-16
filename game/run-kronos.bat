@echo off
rem Launch the isolated Jo Engine / SGL Kokiri viewer in Kronos.
rem
rem This deliberately mirrors legacy/libyaul/run-kronos.bat -- same emulator
rem build, same BIOS, same autostart -- so the viewer and the unchanged libyaul
rem baseline are measured in the same configuration. Change both or neither.

set KRONOS_DIR=D:\Workspace-Claude\saturn-homebrew\Kronos\build_kronos\src\port\qt
set BIOS=D:\Workspace-Claude\saturn-homebrew\bios\Sega Saturn BIOS (E) (1.00)\Sega Saturn BIOS (E) (1.00).bin
set IMAGE=%~dp0build\game.cue

if not exist "%IMAGE%" (
    echo Build first: see game/README.md
    exit /b 1
)

rem Kronos needs libopenal-1.dll / libstdc++-6.dll / libgcc_s_seh-1.dll /
rem SDL2.dll from the MSYS2 mingw64 toolchain, which is not on Explorer's PATH.
set PATH=C:\msys64\mingw64\bin;%PATH%

rem Kronos resolves its config/plugins against the current directory, not its
rem exe location, so run it from its own folder.
pushd "%KRONOS_DIR%"
start "" kronos.exe -b "%BIOS%" -i "%IMAGE%" -a
popd
