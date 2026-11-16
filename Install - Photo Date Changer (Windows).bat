@echo off
setlocal
cd /d "%~dp0"

echo === Photo Date Changer - Windows Installer ===
echo.

where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python was not found in PATH. Please install Python 3.10+ from https://www.python.org/
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo Virtual environment .venv already exists.
)

echo.
echo Installing dependencies from requirements.txt ...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo Installation complete!
echo You can now launch the app using "Run - Photo Date Changer (Windows).bat".
pause
