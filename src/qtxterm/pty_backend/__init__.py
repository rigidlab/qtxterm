from __future__ import annotations

import sys

from qtxterm.pty_backend.base import PtySession

__all__ = ["PtySession", "create_pty_session", "default_shell"]


def create_pty_session() -> PtySession:
    if sys.platform == "win32":
        from qtxterm.pty_backend.win import WinPtySession

        return WinPtySession()
    from qtxterm.pty_backend.posix import PosixPtySession

    return PosixPtySession()


def default_shell() -> str:
    if sys.platform == "win32":
        return "powershell.exe"
    import os

    return os.environ.get("SHELL", "/bin/bash")
