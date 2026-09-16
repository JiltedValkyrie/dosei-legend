@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\launcher\kronos-launcher.ps1" -Variant hires
exit /b %errorlevel%
