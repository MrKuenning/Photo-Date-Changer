from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ui_main import PhotoDateChangerWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Photo Date Changer")
    app.setStyle("Fusion")

    initial_paths = sys.argv[1:] if len(sys.argv) > 1 else None
    window = PhotoDateChangerWindow(initial_paths=initial_paths)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
