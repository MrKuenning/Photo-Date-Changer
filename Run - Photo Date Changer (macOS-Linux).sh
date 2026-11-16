#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Virtual environment not found."
    echo "Please run \"Install - Photo Date Changer (macOS-Linux).sh\" first."
    exit 1
fi

exec ".venv/bin/python" "app/main.py" "$@"
