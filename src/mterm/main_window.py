from __future__ import annotations

from PySide6.QtWidgets import QMainWindow

from mterm.terminal_widget import TerminalWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("mterm")
        self.resize(1000, 650)
        self.setCentralWidget(TerminalWidget(parent=self))
