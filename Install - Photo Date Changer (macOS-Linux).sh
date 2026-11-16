#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "=== Photo Date Changer - macOS/Linux Installer ==="
echo

if ! command -v python3 >/dev/null 2>&1; then
    echo "ERROR: python3 was not found. Please install Python 3.10+."
    exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating virtual environment in .venv ..."
    python3 -m venv .venv
else
    echo "Virtual environment .venv already exists."
fi

echo
echo "Installing dependencies from requirements.txt ..."
".venv/bin/python" -m pip install --upgrade pip
".venv/bin/python" -m pip install -r requirements.txt

echo
echo "Installation complete!"
echo "You can now launch the app using: ./Run\\ -\\ Photo\\ Date\\ Changer\\ \\(macOS-Linux\\).sh"
