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

    @Slot(str)
    def sendInput(self, data: str) -> None:
        self.input_received.emit(data)

    @Slot(int, int)
    def resize(self, cols: int, rows: int) -> None:
        self.resize_requested.emit(cols, rows)

    @Slot(int, int)
    def ready(self, cols: int, rows: int) -> None:
        self.terminal_ready.emit(cols, rows)
