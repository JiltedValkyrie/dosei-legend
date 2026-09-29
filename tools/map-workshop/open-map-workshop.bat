@echo off
setlocal
python -c "import tkinter; import PIL" >nul 2>&1
if errorlevel 1 (
    echo Map Workshop needs Python with Tkinter and Pillow. See README.md.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0map_workshop.py"
