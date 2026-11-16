@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\pythonw.exe" (
    echo Virtual environment not found.
    echo Please run "Install - Photo Date Changer (Windows).bat" first.
    pause
    exit /b 1
)

start "" ".venv\Scripts\pythonw.exe" "app\main.py" %*
