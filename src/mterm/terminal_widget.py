from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from mterm.pty_backend import create_pty_session, default_shell
from mterm.terminal_bridge import TerminalBridge

ASSETS_DIR = Path(__file__).parent / "assets"


class TerminalWidget(QWidget):
    """A single terminal: xterm.js view (QWebEngineView) wired to a PtySession."""

    def __init__(self, shell: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._shell = shell or default_shell()
        self._pty = create_pty_session()

        self._view = QWebEngineView(self)
        self._bridge = TerminalBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)

        self._bridge.terminal_ready.connect(self._on_terminal_ready)
        self._bridge.input_received.connect(self._pty.write)
        self._bridge.resize_requested.connect(self._pty.resize)
        self._pty.output_ready.connect(self._bridge.output.emit)
        self._pty.exited.connect(self._bridge.exited.emit)

        self._view.load(QUrl.fromLocalFile(str(ASSETS_DIR / "terminal.html")))

    def _on_terminal_ready(self, cols: int, rows: int) -> None:
        self._pty.start(self._shell, cols, rows)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._pty.close()
        super().closeEvent(event)
