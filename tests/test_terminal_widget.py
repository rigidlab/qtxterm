"""TerminalWidget wiring, verified against a fake PtySession (no real shell)."""

from __future__ import annotations

from urllib.parse import parse_qs

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication

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


def test_right_click_emits_context_menu_requested_in_global_coords(qtbot) -> None:
    """The view's own menu policy is Custom, so Chromium's Back/Reload menu
    never appears; the widget re-emits the request instead."""
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    assert widget._view.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    local = QPoint(12, 34)
    with qtbot.waitSignal(widget.context_menu_requested, timeout=1000) as blocker:
        widget._view.customContextMenuRequested.emit(local)

    assert blocker.args == [widget._view.mapToGlobal(local)]


def test_selection_from_the_bridge_is_cached_for_copy(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    assert widget.selection == ""
    assert widget.copy_selection() is False

    widget._bridge.setSelection("selected text")

    assert widget.selection == "selected text"
    assert widget.copy_selection() is True
    assert QGuiApplication.clipboard().text() == "selected text"


def test_paste_routes_through_xterm_so_bracketed_paste_is_honored(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)

    widget.paste("echo hi\nls")

    assert len(calls) == 1
    assert "window.pasteText" in calls[0]
    assert r'"echo hi\nls"' in calls[0]


def test_paste_of_empty_text_is_a_no_op(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)

    widget.paste("")

    assert calls == []


def test_paste_from_clipboard_uses_the_clipboard_text(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)
    QGuiApplication.clipboard().setText("from clipboard")

    widget.paste_from_clipboard()

    assert "from clipboard" in calls[0]
