@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\launcher\build-game.ps1" %*
exit /b %errorlevel%
