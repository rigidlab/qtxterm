"""TerminalWidget wiring, verified against a fake PtySession (no real shell)."""

from __future__ import annotations

from mterm.pty_backend.base import PtySession
from mterm.terminal_widget import TerminalWidget


class FakePtySession(PtySession):
    def __init__(self) -> None:
        super().__init__()
        self.start_calls: list[tuple[str, int, int]] = []
        self.write_calls: list[str] = []
        self.resize_calls: list[tuple[int, int]] = []
        self.closed = False

    def start(self, shell: str, cols: int, rows: int) -> None:
        self.start_calls.append((shell, cols, rows))

    def write(self, data: str) -> None:
        self.write_calls.append(data)

    def resize(self, cols: int, rows: int) -> None:
        self.resize_calls.append((cols, rows))

    def close(self) -> None:
        self.closed = True

    @property
    def is_alive(self) -> bool:
        return bool(self.start_calls) and not self.closed


def test_terminal_ready_starts_pty_with_configured_shell(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(shell="/bin/fake-shell", pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget._bridge.ready(100, 30)

    assert fake_pty.start_calls == [("/bin/fake-shell", 100, 30)]


def test_bridge_input_forwarded_to_pty_write(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget._bridge.sendInput("echo hi\n")

    assert fake_pty.write_calls == ["echo hi\n"]


def test_bridge_resize_forwarded_to_pty_resize(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget._bridge.resize(120, 40)

    assert fake_pty.resize_calls == [(120, 40)]


def test_pty_output_forwarded_to_bridge_output(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(pty_session=fake_pty)
    qtbot.addWidget(widget)

    with qtbot.waitSignal(widget._bridge.output, timeout=1000) as blocker:
        fake_pty.output_ready.emit("hello from pty")

    assert blocker.args == ["hello from pty"]


def test_shutdown_closes_pty(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget.shutdown()

    assert fake_pty.closed is True
