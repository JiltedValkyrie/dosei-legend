@echo off
rem OoT Saturn playtest launcher. Starts the bundled draw-cap-fixed Kronos with
rem the kronos.ini next to kronos.exe (4 MB cart preset) and boots the game.
rem Optional: put your Saturn BIOS in this folder as bios.bin.
set ROOT=%~dp0
cd /d "%ROOT%kronos"
if exist "%ROOT%bios.bin" (
    start "" kronos.exe -b "%ROOT%bios.bin" -i "%ROOT%game\game-clean.cue" -a
) else (
    start "" kronos.exe -i "%ROOT%game\game-clean.cue" -a
)
