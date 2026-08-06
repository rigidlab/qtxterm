from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from qtxterm.branding import app_icon, set_windows_app_id
from qtxterm.main_window import MainWindow


def main() -> int:
    # Before QApplication: the taskbar reads the app ID when the first
    # window is registered.
    set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName("qtxterm")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
