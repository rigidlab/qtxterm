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
    script_loaded = Signal()
    title_changed = Signal(str)
    selection_changed = Signal(str)
    link_activated = Signal(str)
    cwd_changed = Signal(str)

    @Slot(str)
    def sendInput(self, data: str) -> None:
        self.input_received.emit(data)

    @Slot(int, int)
    def resize(self, cols: int, rows: int) -> None:
        self.resize_requested.emit(cols, rows)

    @Slot(int, int)
    def ready(self, cols: int, rows: int) -> None:
        self.terminal_ready.emit(cols, rows)

    @Slot()
    def loaded(self) -> None:
        """Sent by terminal.js as soon as the channel is up.

        The page cannot work out its own size: Chromium skips layout for a
        view in a background tab, so a pane split into a tab you aren't
        looking at fits itself to a stale viewport - one row, in the worst
        case - and the shell starts believing that. Qt knows the real size,
        so it pushes it (TerminalWidget._apply_size) and the terminal starts
        from that instead.
        """
        self.script_loaded.emit()

    @Slot(str)
    def setTitle(self, title: str) -> None:
        self.title_changed.emit(title)

    @Slot(str)
    def setCwd(self, uri: str) -> None:
        """The shell reported its working directory (OSC 7).

        The payload is whatever the shell printed - on an SSH session, a
        remote path that means nothing locally - so TerminalWidget checks it
        against the filesystem before starting anything in it.
        """
        self.cwd_changed.emit(uri)

    @Slot(str)
    def setSelection(self, text: str) -> None:
        """Pushed by xterm.js on every selection change.

        Python caches it (see TerminalWidget) so Copy can act synchronously -
        reading the selection on demand would mean an async runJavaScript
        round trip, which is too late to enable or disable a menu item that
        is about to be shown.
        """
        self.selection_changed.emit(text)

    @Slot(str)
    def openLink(self, uri: str) -> None:
        """A URL in the output was Ctrl+clicked.

        The URI is whatever the terminal printed, which on an SSH session is
        whatever the remote host printed - so it is untrusted, and
        TerminalWidget checks the scheme before handing it to the OS rather
        than trusting the link addon's regex to be the only gate.
        """
        self.link_activated.emit(uri)
