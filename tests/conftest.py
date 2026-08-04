from __future__ import annotations

from mterm.pty_backend.base import PtySession


class FakePtySession(PtySession):
    """In-memory PtySession stand-in, recording calls instead of spawning a shell."""

    def __init__(self) -> None:
        super().__init__()
        self.start_calls: list[tuple[list[str], int, int]] = []
        self.write_calls: list[str] = []
        self.resize_calls: list[tuple[int, int]] = []
        self.closed = False

    def start(self, command: list[str], cols: int, rows: int) -> None:
        self.start_calls.append((command, cols, rows))

    def write(self, data: str) -> None:
        self.write_calls.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self.resize_calls.append((cols, rows))

    def close(self) -> None:
        self.closed = True

    @property
    def is_alive(self) -> bool:
        return bool(self.start_calls) and not self.closed
