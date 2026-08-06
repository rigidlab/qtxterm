"""TerminalWidget wiring, verified against a fake PtySession (no real shell)."""

from __future__ import annotations

from urllib.parse import parse_qs

from conftest import FakePtySession

from qtxterm.appearance import Appearance
from qtxterm.terminal_widget import TerminalWidget


def test_terminal_ready_starts_pty_with_configured_shell(qtbot) -> None:
    fake_pty = FakePtySession()
    widget = TerminalWidget(shell="/bin/fake-shell", pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget._bridge.ready(100, 30)

    assert fake_pty.start_calls == [(["/bin/fake-shell"], 100, 30)]


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


def test_run_when_ready_calls_immediately_if_pty_already_started(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    widget._bridge.ready(80, 24)

    called = []
    widget.run_when_ready(lambda: called.append(True))

    assert called == [True]


def test_run_when_ready_waits_for_pty_started(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)

    called = []
    widget.run_when_ready(lambda: called.append(True))
    assert called == []

    widget._bridge.ready(80, 24)

    assert called == [True]


def test_terminal_url_encodes_appearance_as_query_params() -> None:
    appearance = Appearance(theme_name="Solarized Dark", font_family="Cascadia Mono", font_size=18)

    url = TerminalWidget._terminal_url(appearance)

    query = parse_qs(url.query())
    assert query["fontFamily"] == ["Cascadia Mono"]
    assert query["fontSize"] == ["18"]
    assert '"background": "#002b36"' in query["theme"][0] or "#002b36" in query["theme"][0]


def test_apply_appearance_runs_javascript_with_theme_and_font(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)

    widget.apply_appearance(Appearance(theme_name="VS Code Light+", font_size=22))

    assert len(calls) == 1
    assert "applyAppearance" in calls[0]
    assert "#ffffff" in calls[0]
    assert '"fontSize": 22' in calls[0]
