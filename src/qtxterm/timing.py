"""Opt-in timing log, for finding where startup and tab-open time goes.

Off unless `QTXTERM_TIMING` is set to something other than 0, so it costs a
single boolean check in normal use. Writes to a file rather than stdout
because the GUI entry point (qtxtermw) has no console to print to.

Runs append to one file with a header naming the interpreter, argv and
environment, which is the point: launch the app two different ways and the
log shows both sessions side by side.

Diagnostic scaffolding - remove once the launch-mode difference it was added
to chase is understood.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

ENV_VAR = "QTXTERM_TIMING"
ENABLED = os.environ.get(ENV_VAR, "0") not in ("", "0")
LOG_PATH = Path(tempfile.gettempdir()) / "qtxterm-timing.log"

_start = time.perf_counter()


def _write(line: str) -> None:
    try:
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        # Diagnostics must never take the app down with them.
        pass


def begin_session() -> None:
    """Head the log with enough context to tell two launches apart."""
    if not ENABLED:
        return
    _write(
        "\n=== qtxterm session "
        + time.strftime("%Y-%m-%d %H:%M:%S")
        + f"\n    executable : {sys.executable}"
        + f"\n    argv0      : {sys.argv[0] if sys.argv else '?'}"
        + f"\n    cwd        : {os.getcwd()}"
        + f"\n    VIRTUAL_ENV: {os.environ.get('VIRTUAL_ENV')}"
        + f"\n    console    : {bool(_has_console())}"
    )


def _has_console() -> bool:
    if sys.platform != "win32":
        return sys.stdout is not None
    import ctypes

    return bool(ctypes.windll.kernel32.GetConsoleWindow())


def mark(event: str) -> None:
    """Record `event` with the time since this process started."""
    if not ENABLED:
        return
    _write(f"{time.perf_counter() - _start:8.3f}s  {event}")
