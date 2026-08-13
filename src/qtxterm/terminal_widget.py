from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QUrl, QUrlQuery, Signal
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QVBoxLayout, QWidget

from qtxterm.appearance import Appearance
from qtxterm.pane import PANE_BORDER_WIDTH, PaneWidget
from qtxterm.pty_backend import PtySession, create_pty_session, default_shell
from qtxterm.terminal_bridge import TerminalBridge

ASSETS_DIR = Path(__file__).parent / "assets"


def shell_short_name(shell: str) -> str:
    """Best-effort short label for a shell path, e.g. 'powershell.exe' -> 'powershell'."""
    name = Path(shell).name
    if name.lower().endswith(".exe"):
        name = name[: -len(".exe")]
    return name


class TerminalWidget(PaneWidget):
    """A single terminal: xterm.js view (QWebEngineView) wired to a PtySession."""

    title_changed = Signal(str)
    pty_started = Signal()
    # Global position, so a listener can pop a menu up without knowing where
    # this widget sits.
    context_menu_requested = Signal(QPoint)

    def __init__(
        self,
        shell: str | list[str] | None = None,
        parent: QWidget | None = None,
        pty_session: PtySession | None = None,
        appearance: Appearance | None = None,
    ) -> None:
        super().__init__(parent)
        if shell is None:
            self._command = [default_shell()]
        elif isinstance(shell, str):
            self._command = [shell]
        else:
            self._command = list(shell)
        self._pty = pty_session or create_pty_session()
        self.is_pty_started = False
        self._selection = ""

        self._view = QWebEngineView(self)
        # Without this the view shows Chromium's own menu (Back, Reload, View
        # Source), which is meaningless for a terminal.
        self._view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._view.customContextMenuRequested.connect(self._on_context_menu_requested)
        # Without this the view is white until terminal.js paints the theme
        # background, which flashes on every new terminal - worst on a dark
        # theme, and most visible on the first one while Chromium starts.
        self._view.page().setBackgroundColor(
            QColor((appearance or Appearance()).theme.background)
        )
        self._bridge = TerminalBridge(self)
        self._channel = QWebChannel(self)
        self._channel.registerObject("bridge", self._bridge)
        self._view.page().setWebChannel(self._channel)

        # A margin the indicator can paint into. Zero would leave nowhere to
        # draw a border without resizing the terminal grid when focus moves,
        # which would reflow the shell's output on every click.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            PANE_BORDER_WIDTH, PANE_BORDER_WIDTH, PANE_BORDER_WIDTH, PANE_BORDER_WIDTH
        )
        layout.addWidget(self._view)

        self._script_loaded = False
        self._bridge.script_loaded.connect(self._on_script_loaded)
        self._bridge.terminal_ready.connect(self._on_terminal_ready)
        self._bridge.input_received.connect(self._pty.write)
        self._bridge.resize_requested.connect(self._pty.resize)
        self._bridge.title_changed.connect(self.title_changed.emit)
        self._bridge.selection_changed.connect(self._on_selection_changed)
        self._pty.output_ready.connect(self._bridge.output.emit)
        self._pty.exited.connect(self._bridge.exited.emit)

        self._view.load(self._terminal_url(appearance or Appearance()))

    @staticmethod
    def _terminal_url(appearance: Appearance) -> QUrl:
        # Passed as query params (rather than a post-load bridge call) so
        # the terminal renders in the right theme/font from its very first
        # frame - no flash of the default look before JS catches up.
        url = QUrl.fromLocalFile(str(ASSETS_DIR / "terminal.html"))
        query = QUrlQuery()
        query.addQueryItem("theme", json.dumps(appearance.theme.to_xterm_dict()))
        query.addQueryItem("fontFamily", appearance.font_family)
        query.addQueryItem("fontSize", str(appearance.font_size))
        url.setQuery(query)
        return url

    def apply_appearance(self, appearance: Appearance) -> None:
        """Live-update an already-open tab's theme/font without reloading it."""
        self._view.page().setBackgroundColor(QColor(appearance.theme.background))
        payload = json.dumps(
            {
                "theme": appearance.theme.to_xterm_dict(),
                "fontFamily": appearance.font_family,
                "fontSize": appearance.font_size,
            }
        )
        self._view.page().runJavaScript(
            f"window.applyAppearance && window.applyAppearance({payload});"
        )

    @property
    def shell_name(self) -> str:
        """Short name of the shell this tab is running, e.g. 'powershell'.

        Selection Actions need it: how to feed a file to a command's stdin
        differs per shell (see selection_actions.feed_from_file).
        """
        return shell_short_name(self._command[0])

    @property
    def default_title(self) -> str:
        """Short label derived from the shell, used until the shell sets its own title."""
        return shell_short_name(self._command[0])

    def _on_script_loaded(self) -> None:
        """terminal.js is wired up, so it can be told how big it is.

        Nothing is pushed before this: runJavaScript against a page whose
        script hasn't run yet is silently dropped, and the resize that comes
        with being added to a splitter usually happens first.
        """
        self._script_loaded = True
        self._apply_size()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_size()

    def _apply_size(self) -> None:
        """Tell the page its pixel size, which starts or re-fits the terminal.

        Qt logical pixels map 1:1 to CSS pixels in QtWebEngine, so the view's
        own size is what the document should be.
        """
        if not self._script_loaded:
            return
        width, height = self._view.width(), self._view.height()
        if width <= 0 or height <= 0:
            return
        self._view.page().runJavaScript(
            f"window.applySize && window.applySize({width}, {height});"
        )

    def _on_terminal_ready(self, cols: int, rows: int) -> None:
        self._pty.start(self._command, cols, rows)
        self.is_pty_started = True
        self.pty_started.emit()

    def _on_context_menu_requested(self, pos: QPoint) -> None:
        self.context_menu_requested.emit(self._view.mapToGlobal(pos))

    def _on_selection_changed(self, text: str) -> None:
        self._selection = text

    @property
    def selection(self) -> str:
        """The terminal's current selection, as last pushed by xterm.js."""
        return self._selection

    def copy_selection(self) -> bool:
        """Put the selection on the clipboard. False if nothing is selected."""
        if not self._selection:
            return False
        QGuiApplication.clipboard().setText(self._selection)
        return True

    def paste(self, text: str) -> None:
        """Feed `text` to the terminal as if pasted with the mouse or keyboard."""
        if not text:
            return
        self._view.page().runJavaScript(
            f"window.pasteText && window.pasteText({json.dumps(text)});"
        )

    def paste_from_clipboard(self) -> None:
        self.paste(QGuiApplication.clipboard().text())

    def send_command(self, text: str) -> None:
        """Write a line to the PTY and submit it, as if the user typed it + Enter.

        Terminated with a bare CR, which is what the Enter key actually
        sends. CRLF submits *twice* - the shell accepts on the CR and again
        on the LF - so every command left an empty line behind it: a stray
        prompt in bash, a `>>` continuation prompt in PowerShell.
        """
        self._pty.write(f"{text}\r")

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
