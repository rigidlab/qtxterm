from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from mterm.pty_backend import PtySession, create_pty_session, default_shell
from mterm.terminal_bridge import TerminalBridge

ASSETS_DIR = Path(__file__).parent / "assets"


def shell_short_name(shell: str) -> str:
    """Best-effort short label for a shell path, e.g. 'powershell.exe' -> 'powershell'."""
    name = Path(shell).name
    if name.lower().endswith(".exe"):
        name = name[: -len(".exe")]
    return name


class TerminalWidget(QWidget):
    """A single terminal: xterm.js view (QWebEngineView) wired to a PtySession."""

    title_changed = Signal(str)
    pty_started = Signal()

    def __init__(
        self,
        shell: str | None = None,
        parent: QWidget | None = None,
        pty_session: PtySession | None = None,
    ) -> None:
        super().__init__(parent)
        self._shell = shell or default_shell()
        self._pty = pty_session or create_pty_session()
        self.is_pty_started = False

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
        self._bridge.title_changed.connect(self.title_changed.emit)
        self._pty.output_ready.connect(self._bridge.output.emit)
        self._pty.exited.connect(self._bridge.exited.emit)

        self._view.load(QUrl.fromLocalFile(str(ASSETS_DIR / "terminal.html")))

    @property
    def default_title(self) -> str:
        """Short label derived from the shell, used until the shell sets its own title."""
        return shell_short_name(self._shell)

    def _on_terminal_ready(self, cols: int, rows: int) -> None:
        self._pty.start(self._shell, cols, rows)
        self.is_pty_started = True
        self.pty_started.emit()

    def send_command(self, text: str) -> None:
        """Write a line to the PTY and submit it, as if the user typed it + Enter."""
        self._pty.write(f"{text}\r\n")

    def run_when_ready(self, callback) -> None:
        """Call `callback` once the PTY has started (immediately if it already has).

        The PTY only starts after an async round trip (QWebEngineView loads
        terminal.html -> xterm.js boots -> JS calls back into Python), so
        code that spawns a tab and immediately wants to feed it input (e.g.
        macros) can't just call send_command() right after new_tab() returns.
        """
        if self.is_pty_started:
            callback()
        else:
            self.pty_started.connect(callback)

    def shutdown(self) -> None:
        """Terminate the backing PTY process.

        Not done via closeEvent: a child widget embedded in a layout never
        receives closeEvent when its parent QMainWindow closes, only
        top-level windows do. Callers must invoke this explicitly.
        """
        self._pty.close()
