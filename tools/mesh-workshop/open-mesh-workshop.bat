@echo off
setlocal
python -c "import tkinter; import PIL" >nul 2>&1
if errorlevel 1 (
    echo Mesh workshop requires Python with Tkinter and Pillow. See README.md here.
    pause
    exit /b 1
)
start "" pythonw.exe "%~dp0mesh_workshop.py"
