from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from qtxterm import timing
from qtxterm.branding import app_icon, set_windows_app_id
from qtxterm.main_window import MainWindow
from qtxterm.selection_actions import clean_old_selection_files


def main() -> int:
    timing.begin_session()
    timing.mark("main() entered")
    # Before QApplication: the taskbar reads the app ID when the first
    # window is registered.
    set_windows_app_id()
    # Selection temp files outlive the command reading them, so they are
    # swept at startup rather than on tab close.
    clean_old_selection_files()
    app = QApplication(sys.argv)
    timing.mark("QApplication created")
    app.setApplicationName("qtxterm")
    app.setWindowIcon(app_icon())
    window = MainWindow()
    timing.mark("MainWindow constructed")
    window.show()
    timing.mark("window shown")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
