from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from mterm.terminal_widget import TerminalWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("mterm")
        self.resize(1000, 650)
        self._terminal = TerminalWidget(parent=self)
        self.setCentralWidget(self._terminal)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._terminal.shutdown()
        super().closeEvent(event)
