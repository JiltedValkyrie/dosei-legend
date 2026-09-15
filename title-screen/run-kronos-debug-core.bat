@echo off
set "KRONOS_DIR=D:\Workspace-Claude\saturn-homebrew\Kronos\build_kronos\src\port\qt"
set "BIOS=D:\Workspace-Claude\saturn-homebrew\bios\Sega Saturn BIOS (E) (1.00)\Sega Saturn BIOS (E) (1.00).bin"
set "PATH=C:\msys64\mingw64\bin;%PATH%"
set "QT_PLUGIN_PATH=C:\msys64\mingw64\share\qt5\plugins"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\prepare_kronos_debug.ps1"
if errorlevel 1 exit /b 1
pushd "%KRONOS_DIR%"
start "" "%~dp0build\kronos-debug-core\kronos.exe" -b "%BIOS%" -i "%~dp0title-screen.cue" -a
popd
