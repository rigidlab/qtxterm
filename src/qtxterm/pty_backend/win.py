from __future__ import annotations

import threading

from winpty import PtyProcess

from qtxterm.pty_backend.base import PtySession


class WinPtySession(PtySession):
    """PTY backend for Windows, backed by ConPTY via pywinpty."""

    def __init__(self) -> None:
        super().__init__()
        self._process: PtyProcess | None = None
        self._reader_thread: threading.Thread | None = None

    def start(self, command: list[str], cols: int, rows: int) -> None:
        # Must be a real argv list, not a joined string: PtyProcess.spawn()
        # shlex-splits string argv on whitespace, which breaks paths like
        # "C:\Program Files\Git\bin\bash.exe" (splits into "C:\Program" +
        # the rest, and "C:\Program" isn't found on PATH).
        self._process = PtyProcess.spawn(command, dimensions=(rows, cols))
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
            self._emit_from_reader(self.output_ready, data)
        exit_code = (
            self._process.exitstatus if self._process.exitstatus is not None else 0
        )
        self._emit_from_reader(self.exited, exit_code)

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
        self._await_reader()

    @property
    def is_alive(self) -> bool:
        return self._process is not None and self._process.isalive()
