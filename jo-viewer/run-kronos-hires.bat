@echo off
setlocal
rem Dosei Legend - native Saturn 320x480i comparison, same gameplay and audio.
rem Build separately: bash ./build.sh --hires (from jo-viewer).
set "KRONOS_DIR=D:\Workspace-Claude\saturn-homebrew\Kronos\build_kronos\src\port\qt"
set "BIOS=D:\Workspace-Claude\saturn-homebrew\bios\Sega Saturn BIOS (E) (1.00)\Sega Saturn BIOS (E) (1.00).bin"
set "IMAGE=%~dp0game-hires.cue"
if not exist "%IMAGE%" (
    echo Build the hi-res image first: jo-viewer/build.sh --hires
    exit /b 1
)
set "PATH=C:\msys64\mingw64\bin;%PATH%"
pushd "%KRONOS_DIR%"
start "" kronos.exe -b "%BIOS%" -i "%IMAGE%" -a
popd
endlocal
