from __future__ import annotations

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

    @abstractmethod
    def start(self, shell: str, cols: int, rows: int) -> None:
        """Spawn the shell process attached to a new PTY of the given size."""

    @abstractmethod
    def write(self, data: str) -> None:
        """Send keyboard input / text to the PTY."""

    @abstractmethod
    def resize(self, cols: int, rows: int) -> None:
        """Notify the PTY that the terminal viewport size changed."""

    @abstractmethod
    def close(self) -> None:
        """Terminate the child process and stop the reader thread."""
