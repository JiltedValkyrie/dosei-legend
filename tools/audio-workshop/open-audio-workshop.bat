@echo off
setlocal
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Audio workshop needs Python with Tkinter.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0audio_workshop.py"
