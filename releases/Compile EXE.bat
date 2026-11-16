@echo off
setlocal
cd /d "%~dp0.."

REM Use .venv Python if available, otherwise fall back to system Python
set "PY_EXE=python"
if exist ".venv\Scripts\python.exe" (
    set "PY_EXE=.venv\Scripts\python.exe"
)

REM Read version from app/__init__.py
for /f "delims=" %%v in ('"%PY_EXE%" -c "import app; print(app.__version__)"') do set "VERSION=%%v"
if "%VERSION%"=="" set "VERSION=1.1"

echo Building PhotoDateChanger-v%VERSION%.exe into releases\ ...

"%PY_EXE%" -m PyInstaller --version >nul 2>&1
if errorlevel 1 (
    echo PyInstaller not found in %PY_EXE%, installing...
    "%PY_EXE%" -m pip install pyinstaller
)

"%PY_EXE%" -m PyInstaller ^
    --noconfirm ^
    --clean ^
    --onefile ^
    --windowed ^
    --distpath "%CD%\releases" ^
    --workpath "%CD%\build" ^
    --specpath "%CD%\build" ^
    --paths "%CD%\app" ^
    --name "PhotoDateChanger-v%VERSION%" ^
    --icon "%CD%\assets\app_icon.ico" ^
    --add-data "%CD%\assets\app_icon.ico;assets" ^
    --collect-all pyexiv2 ^
    "%CD%\app\main.py"

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Build complete! Executable is at releases\PhotoDateChanger-v%VERSION%.exe
pause
