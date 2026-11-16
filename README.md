# Photo Date Changer

A clean, fast PyQt6 desktop app for quickly setting dates on old scanned photos—individually or in batches—when you may only know a decade, year, month, or exact day.

## Project Structure

```text
.
├── app/                                      # Application source code
│   ├── __init__.py
│   ├── main.py
│   ├── metadata.py
│   └── ui_main.py
├── assets/                                   # Icons and static assets
│   └── app_icon.ico
├── releases/                                 # Compiled executables & build script
│   └── Compile EXE.bat
├── Install - Photo Date Changer (Windows).bat
├── Install - Photo Date Changer (macOS-Linux).sh
├── Run - Photo Date Changer (Windows).bat
├── Run - Photo Date Changer (macOS-Linux).sh
├── requirements.txt
├── README.md
└── CHANGELOG.md
```

## Features

- **Progressive Quick Date Picker**:
  - **1. Decade**: One-click buttons (`1910s`–`2020s`) that select the decade and populate its 10 years.
  - **2. Year**: One-click year buttons for the chosen decade, plus a direct year input (`1800`–`2099`).
  - **3. Month (optional)**: Toggleable `Jan`–`Dec` buttons (defaults to January 1st when omitted).
  - **4. Day (optional)**: Dropdown (`Unknown (1st)` or `1`–`31`, automatically clamped to valid days in the month).
- **Fast Workflow & Batch Dating**:
  - Drag & drop photos or folders anywhere onto the window, or use **+ Add Photos** / **Open Folder**.
  - Multi-select photos (`Ctrl+Click`, `Shift+Click`, **All**, or **Undated**) to date a whole batch at once.
  - **Apply & Next →** (`Ctrl+Enter`) applies the date and advances to the next photo.
  - **Recent dates** chips for 1-click reuse across photos from the same album or event.
  - **Undo** (`Ctrl+Z`) restores previous EXIF tags and file timestamps.
- **Lossless Metadata + Pre-1970 Support**:
  - Updates EXIF (`DateTimeOriginal`, `DateTimeDigitized`, `DateTime`) in-place via `pyexiv2` without re-encoding image pixels.
  - Optionally updates file **Created** and **Modified** timestamps (including pre-1970 dates on Windows via `SetFileTime`).
- **Light & Dark Mode**:
  - Toggle between Light and Dark themes from the toolbar; your preference is saved automatically.

## Supported Formats

`.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.webp`, `.bmp` *(EXIF tags are written for JPEG, PNG, TIFF, and WebP; file timestamps are updated for all supported formats).*

---

## Installation & Running

### Option A: Standalone Windows Executable (No Python Required)

If you have a compiled release in `releases/` (e.g., `releases\PhotoDateChanger-v1.1.exe`), simply double-click it to run.

### Option B: Windows (from Source)

1. Double-click **`Install - Photo Date Changer (Windows).bat`**
   *(Creates an isolated `.venv` virtual environment and installs `PyQt6` and `pyexiv2`.)*
2. Double-click **`Run - Photo Date Changer (Windows).bat`** to launch the app.

### Option C: macOS & Linux (from Source)

1. Open a terminal in the project folder and make the scripts executable:
   ```bash
   chmod +x "Install - Photo Date Changer (macOS-Linux).sh" "Run - Photo Date Changer (macOS-Linux).sh"
   ```
2. Run the installer to create `.venv` and install dependencies:
   ```bash
   ./"Install - Photo Date Changer (macOS-Linux).sh"
   ```
3. Launch the app:
   ```bash
   ./"Run - Photo Date Changer (macOS-Linux).sh"
   ```

---

## Building the Standalone Windows `.exe`

Double-click **`releases\Compile EXE.bat`** (or run it from a terminal).
It reads `__version__` from `app/__init__.py` and outputs a versioned standalone executable to:

```text
releases\PhotoDateChanger-v<version>.exe
```

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| `Ctrl+Enter` | Apply date and advance to next photo |
| `Ctrl+S` | Apply date to selected photo(s) |
| `Ctrl+Z` | Undo last change |
| `Ctrl+A` | Select all photos |
