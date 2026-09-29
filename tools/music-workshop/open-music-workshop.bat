@echo off
setlocal
python -c "import tkinter" >nul 2>&1
if errorlevel 1 (
    echo Music workshop requires Python with Tkinter. See README.md here.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0music_workshop.py"
