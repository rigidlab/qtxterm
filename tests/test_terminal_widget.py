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


def test_view_background_is_the_theme_so_it_never_flashes_white(qtbot) -> None:
    """The view paints before terminal.js applies the theme; left at the
    default white it flashes on every new terminal."""
    widget = TerminalWidget(
        pty_session=FakePtySession(),
        appearance=Appearance(theme_name="VS Code Dark High Contrast"),
    )
    qtbot.addWidget(widget)

    assert widget._view.page().backgroundColor().name() == "#000000"


def test_view_background_follows_a_theme_change(qtbot) -> None:
    widget = TerminalWidget(
        pty_session=FakePtySession(),
        appearance=Appearance(theme_name="VS Code Dark High Contrast"),
    )
    qtbot.addWidget(widget)
    widget._view.page().runJavaScript = lambda script: None

    widget.apply_appearance(Appearance(theme_name="VS Code Light+"))

    assert widget._view.page().backgroundColor().name() == "#ffffff"


def test_send_command_submits_once(qtbot) -> None:
    """CRLF submits twice - the shell accepts on the CR and again on the LF,
    leaving a stray prompt in bash and a `>>` continuation in PowerShell."""
    fake_pty = FakePtySession()
    widget = TerminalWidget(pty_session=fake_pty)
    qtbot.addWidget(widget)

    widget.send_command("echo hi")

    assert fake_pty.write_calls == ["echo hi\r"]
    assert "\n" not in fake_pty.write_calls[0]


def test_size_is_not_pushed_before_the_page_script_is_wired_up(qtbot) -> None:
    """runJavaScript against a page whose script hasn't run is silently
    dropped, and the resize from being added to a splitter usually lands
    first."""
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)

    widget.resize(400, 300)
    assert pushed == []

    widget._bridge.loaded()
    assert any("applySize" in script for script in pushed)


def test_size_pushed_to_the_page_is_the_views_own_size(qtbot) -> None:
    """The page cannot measure itself while its tab is in the background -
    Chromium skips layout there, and the shell would start one row tall."""
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)

    widget._bridge.loaded()

    view = widget._view
    assert pushed[-1] == (
        f"window.applySize && window.applySize({view.width()}, {view.height()});"
    )


def test_scrollback_is_in_the_initial_page_url(qtbot) -> None:
    """Passed as a query param, not pushed after load: xterm.js allocates its
    buffer when the terminal is constructed."""
    widget = TerminalWidget(
        pty_session=FakePtySession(), appearance=Appearance(scrollback=4321)
    )
    qtbot.addWidget(widget)

    query = parse_qs(widget._terminal_url(Appearance(scrollback=4321)).query())

    assert query["scrollback"] == ["4321"]


def test_changing_scrollback_is_pushed_to_an_open_terminal(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)

    widget.apply_appearance(Appearance(scrollback=50))

    assert '"scrollback": 50' in pushed[-1]


def test_show_find_opens_the_in_page_find_bar(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)

    widget.show_find()

    assert calls == ["window.showFind && window.showFind();"]


def test_hide_find_closes_it(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    calls = []
    widget._view.page().runJavaScript = lambda script: calls.append(script)

    widget.hide_find()

    assert calls == ["window.hideFind && window.hideFind();"]


def test_ctrl_clicking_an_http_link_opens_it(qtbot, monkeypatch) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    opened = []
    monkeypatch.setattr(
        "qtxterm.terminal_widget.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )

    widget._bridge.openLink("https://example.com/a?b=1")

    assert opened == ["https://example.com/a?b=1"]


def test_a_link_with_a_scheme_we_do_not_open_is_refused(qtbot, monkeypatch) -> None:
    """The link addon's regex matches only http/https, but it is not a
    security boundary - the text it ran against came out of the terminal,
    which over SSH means it came from the remote host. QDesktopServices will
    launch a registered handler for any scheme, so the check is repeated
    where it decides whether anything is launched at all.
    """
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    opened = []
    monkeypatch.setattr(
        "qtxterm.terminal_widget.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()),
    )

    for uri in (
        "file:///C:/Windows/System32/calc.exe",
        "ms-msdt:/id PCWDiagnostic",
        "javascript:alert(1)",
        "vbscript:msgbox",
        "",
    ):
        assert widget.open_link(uri) is False, uri

    assert opened == []


def test_an_http_link_reports_that_it_opened(qtbot, monkeypatch) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    monkeypatch.setattr(
        "qtxterm.terminal_widget.QDesktopServices.openUrl", lambda url: None
    )

    assert widget.open_link("http://localhost:8080/") is True

def test_background_image_becomes_a_file_url_for_the_page(qtbot, tmp_path) -> None:
    """A bare filesystem path will not do: the page is served from file://
    and would resolve it relative to the assets directory."""
    image = tmp_path / "wall.png"
    image.write_bytes(b"not really a png, but it exists")
    appearance = Appearance(background_image=str(image))

    url = TerminalWidget._background_image_url(appearance)

    assert url.startswith("file://")
    assert url.endswith("wall.png")


def test_a_missing_background_image_resolves_to_nothing(qtbot, tmp_path) -> None:
    """Deleting the image should leave a normal terminal, not a half-painted
    one with a broken url()."""
    appearance = Appearance(background_image=str(tmp_path / "gone.png"))

    assert TerminalWidget._background_image_url(appearance) == ""
    assert TerminalWidget._background_image_url(Appearance()) == ""


def test_background_settings_are_in_the_initial_page_url(qtbot, tmp_path) -> None:
    image = tmp_path / "wall.png"
    image.write_bytes(b"x")
    appearance = Appearance(background_image=str(image), background_opacity=42)

    query = parse_qs(TerminalWidget._terminal_url(appearance).query())

    assert query["backgroundOpacity"] == ["42"]
    assert query["backgroundImage"][0].endswith("wall.png")


def test_background_changes_are_pushed_to_an_open_terminal(qtbot, tmp_path) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)
    image = tmp_path / "wall.png"
    image.write_bytes(b"x")

    widget.apply_appearance(
        Appearance(background_image=str(image), background_opacity=15)
    )

    assert '"backgroundOpacity": 15' in pushed[-1]
    assert "wall.png" in pushed[-1]

def test_background_geometry_is_pushed_to_the_page(qtbot) -> None:
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    widget._bridge.loaded()
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)

    widget.set_background_geometry(40, 12, 800, 600)

    assert "applyBackgroundGeometry(40, 12, 800, 600)" in pushed[-1]


def test_geometry_pushed_before_the_page_loads_is_replayed(qtbot) -> None:
    """Dropping it silently left the first pane of a tab painting the whole
    background while its neighbours painted their slices."""
    widget = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(widget)
    pushed = []
    widget._view.page().runJavaScript = lambda script: pushed.append(script)

    widget.set_background_geometry(7, 9, 500, 400)
    assert not any("applyBackgroundGeometry" in s for s in pushed)

    widget._bridge.loaded()

    assert any("applyBackgroundGeometry(7, 9, 500, 400)" in s for s in pushed)
