from __future__ import annotations

import threading

from winpty import PtyProcess

from mterm.pty_backend.base import PtySession


class WinPtySession(PtySession):
    """PTY backend for Windows, backed by ConPTY via pywinpty."""

    def __init__(self) -> None:
        super().__init__()
        self._process: PtyProcess | None = None
        self._reader_thread: threading.Thread | None = None
        self._stop_reading = threading.Event()

    def start(self, shell: str, cols: int, rows: int) -> None:
        self._process = PtyProcess.spawn(shell, dimensions=(rows, cols))
        self._reader_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._reader_thread.start()

    def _read_loop(self) -> None:
        assert self._process is not None
        while not self._stop_reading.is_set():
            try:
                data = self._process.read(4096)
            except EOFError:
                break
            if not data:
                break
            self.output_ready.emit(data)
        exit_code = self._process.exitstatus if self._process.exitstatus is not None else 0
        self.exited.emit(exit_code)

    def write(self, data: str) -> None:
        if self._process is not None and self._process.isalive():
            self._process.write(data)

    def resize(self, cols: int, rows: int) -> None:
        if self._process is not None and self._process.isalive():
            self._process.setwinsize(rows, cols)

    def close(self) -> None:
        self._stop_reading.set()
        if self._process is not None and self._process.isalive():
            self._process.terminate(force=True)
