# Changelog

All notable changes to **Photo Date Changer** will be documented in this file.

## [1.1] - 2026-11-16

### Added
- Reorganized project into `app/`, `assets/`, and `releases/` directories (`app/__init__.py` with `__version__ = "0.2.0"`).
- Added Windows and macOS/Linux installer scripts (`Install - Photo Date Changer (Windows).bat` and `Install - Photo Date Changer (macOS-Linux).sh`) that create an isolated `.venv` and install dependencies from `requirements.txt`.
- Added Windows and macOS/Linux launcher scripts (`Run - Photo Date Changer (Windows).bat` and `Run - Photo Date Changer (macOS-Linux).sh`).
- Multi-resolution app icon (`assets/app_icon.ico`) used for both the application window and the compiled `.exe`.
- Light and Dark mode toolbar toggle with persistent `QSettings` preference.

### Changed
- Updated `releases/Compile EXE.bat` to build versioned executables (`releases/PhotoDateChanger-v<version>.exe`) using `.venv` when present and embedding `assets/app_icon.ico`.
- Updated `README.md` with cross-platform install/run instructions for Windows, macOS, and Linux.

## [0.1.0] - 2026-11-13

### Added
- Initial PyQt6 desktop application (`main.py`, `ui_main.py`, `metadata.py`).
- Drag-and-drop and file/folder picker for loading photos with EXIF auto-oriented thumbnails and preview.
- Quick progressive date picker supporting Decade (`1910s`–`2020s`), Year (`1800`–`2099`), optional Month, and optional Day.
- Batch dating support via multi-selection, **All**, and **Undated** quick-select buttons.
- **Apply & Next →** (`Ctrl+Enter`), **Apply to Selected** (`Ctrl+S`), **Recent dates** chips, and **Undo** (`Ctrl+Z`).
- Lossless EXIF date writing (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`) via `pyexiv2`.
- Windows file Created & Modified timestamp updates supporting pre-1970 dates via `SetFileTime`.
