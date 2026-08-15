from __future__ import annotations

import threading
from abc import abstractmethod

from PySide6.QtCore import QObject, Signal


class PtySession(QObject):
    """Common interface for a real, resizable pseudo-terminal session.

    Subclasses run their own background reader thread and emit
    `output_ready`/`exited` on it; Qt marshals these signals to whichever
    thread the PtySession instance itself lives on (normally the GUI thread).
    """

    output_ready = Signal(str)
    exited = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        # Owned here rather than per backend: both reader loops need it, and
        # _emit_from_reader below is only correct if it is the same flag.
        self._stop_reading = threading.Event()

    def _await_reader(self, timeout: float = 0.5) -> None:
        """Wait briefly for the reader thread, so close() really means closed.

        Without this the thread outlives close() until its blocking read
        notices the child is gone, and anything it emits in that window is
        delivered - or fails to be - after the caller has moved on.

        Bounded low on purpose: this runs on the GUI thread when a tab is
        closed, and a terminal that took even a second to disappear would be
        worse than the stray emit this avoids. The child has already been
        terminated by then, so the read returns almost immediately.
        """
        thread = getattr(self, "_reader_thread", None)
        if (
            thread is not None
            and thread.is_alive()
            and thread is not threading.current_thread()
        ):
            thread.join(timeout)

    def _emit_from_reader(self, signal, value) -> None:
        """Emit from the reader thread, unless nobody is listening any more.

        A blocking read outlives close() by however long it takes the child
        to die, so the thread wakes up after we have stopped caring - and by
        then the session may also have been garbage collected, leaving the
        C++ object deleted under it. Emitting in either case raises
        "Signal source has been deleted" on a thread with no handler, which
        pytest-qt then reports against whichever test happens to be pumping
        the event loop. Observed as a ~30% flake on Linux, blamed on an
        unrelated QWebEngineView test.
        """
        if self._stop_reading.is_set():
            return
        try:
            signal.emit(value)
        except RuntimeError:
            # The wrapper went away between the check and the emit; there is
            # nothing left to deliver to.
            pass

    @abstractmethod
    def start(self, command: list[str], cols: int, rows: int) -> None:
        """Spawn `command` (argv: executable + args) attached to a new PTY."""

    @abstractmethod
    def write(self, data: str) -> None:
        """Send keyboard input / text to the PTY."""

    @abstractmethod
    def resize(self, cols: int, rows: int) -> None:
        """Notify the PTY that the terminal viewport size changed."""

    @abstractmethod
    def close(self) -> None:
        """Terminate the child process and stop the reader thread."""

    @property
    @abstractmethod
    def is_alive(self) -> bool:
        """Whether the child process is still running."""
