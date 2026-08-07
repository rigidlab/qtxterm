from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class TerminalBridge(QObject):
    """QWebChannel object exposed to terminal.js as `window.bridge`.

    JS -> Python calls arrive as slots and are re-emitted as plain Qt
    signals so TerminalWidget can wire them to a PtySession without this
    class needing to know about PTYs at all.
    """

    output = Signal(str)
    exited = Signal(int)

    input_received = Signal(str)
    resize_requested = Signal(int, int)
    terminal_ready = Signal(int, int)
    title_changed = Signal(str)
    selection_changed = Signal(str)

    @Slot(str)
    def sendInput(self, data: str) -> None:
        self.input_received.emit(data)

    @Slot(int, int)
    def resize(self, cols: int, rows: int) -> None:
        self.resize_requested.emit(cols, rows)

    @Slot(int, int)
    def ready(self, cols: int, rows: int) -> None:
        self.terminal_ready.emit(cols, rows)

    @Slot(str)
    def setTitle(self, title: str) -> None:
        self.title_changed.emit(title)

    @Slot(str)
    def setSelection(self, text: str) -> None:
        """Pushed by xterm.js on every selection change.

        Python caches it (see TerminalWidget) so Copy can act synchronously -
        reading the selection on demand would mean an async runJavaScript
        round trip, which is too late to enable or disable a menu item that
        is about to be shown.
        """
        self.selection_changed.emit(text)
