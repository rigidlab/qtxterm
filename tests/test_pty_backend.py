"""Unit + integration tests for the PtySession backends.

The Windows and POSIX implementations are mutually exclusive optional
dependencies (see pyproject.toml environment markers), so only the
implementation matching the current platform is importable/testable here.
"""

from __future__ import annotations

import sys

import pytest

from qtxterm.pty_backend import create_pty_session, default_shell


def test_create_pty_session_matches_current_platform() -> None:
    session = create_pty_session()
    if sys.platform == "win32":
        from qtxterm.pty_backend.win import WinPtySession

        assert isinstance(session, WinPtySession)
    else:
        from qtxterm.pty_backend.posix import PosixPtySession

        assert isinstance(session, PosixPtySession)


def test_default_shell_is_nonempty_string() -> None:
    assert isinstance(default_shell(), str)
    assert default_shell()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific default shell")
def test_default_shell_windows() -> None:
    assert default_shell() == "powershell.exe"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific default shell")
def test_default_shell_posix(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SHELL", "/bin/zsh")
    assert default_shell() == "/bin/zsh"


def test_real_pty_roundtrip(qtbot) -> None:
    """Spawn a real shell, send a command, and observe its echoed output."""
    session = create_pty_session()
    output_chunks: list[str] = []
    session.output_ready.connect(output_chunks.append)

    # A list, not a bare string: that is the documented argv contract, and
    # ptyprocess enforces it on Linux where pywinpty quietly shlex-splits a
    # string and gets away with it.
    session.start([default_shell()], cols=80, rows=24)
    qtbot.waitUntil(lambda: session.is_alive, timeout=5000)

    session.write("echo pytest_roundtrip_ok\r\n")
    qtbot.waitUntil(
        lambda: "pytest_roundtrip_ok" in "".join(output_chunks), timeout=10000
    )

    session.close()
    qtbot.waitUntil(lambda: not session.is_alive, timeout=5000)
    # Deliver whatever the reader already queued before dropping the last
    # reference to `session`. A cross-thread emit is delivered later, on the
    # GUI thread, and if the sender has been collected by then Qt raises
    # "Signal source has been deleted" into the event loop - which pytest-qt
    # reports against whichever *other* test happens to be pumping it.
    session.output_ready.disconnect()
    qtbot.wait(100)


def test_real_pty_resize(qtbot) -> None:
    session = create_pty_session()
    # A list, not a bare string: that is the documented argv contract, and
    # ptyprocess enforces it on Linux where pywinpty quietly shlex-splits a
    # string and gets away with it.
    session.start([default_shell()], cols=80, rows=24)
    qtbot.waitUntil(lambda: session.is_alive, timeout=5000)

    session.resize(cols=120, rows=40)

    rows, cols = session._process.getwinsize()
    assert (cols, rows) == (120, 40)

    session.close()
