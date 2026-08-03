from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from mterm.terminal_tabs import TerminalTabWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("mterm")
        self.resize(1000, 650)
        self._tabs = TerminalTabWidget(parent=self)
        self._tabs.all_tabs_closed.connect(self.close)
        self.setCentralWidget(self._tabs)
        self._tabs.new_tab()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._tabs.close_all_tabs()
        super().closeEvent(event)
