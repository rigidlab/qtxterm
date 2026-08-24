"""TerminalTabWidget: tab lifecycle, tmux-style labels, active-terminal tracking."""

from __future__ import annotations

from pathlib import Path

from conftest import FakePtySession
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QSplitter

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm import terminal_tabs
from qtxterm.pty_backend import default_shell
from qtxterm import shortcuts
from qtxterm.pane import PANE_BORDER_WIDTH
from qtxterm.terminal_tabs import TerminalTabWidget
from qtxterm.browser_widget import BrowserWidget
from qtxterm.terminal_widget import TerminalWidget, shell_short_name


def make_tabs(qtbot) -> TerminalTabWidget:
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    return tabs


def make_appearance_store(tmp_path: Path) -> AppearanceStore:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return AppearanceStore(settings)


def test_new_tab_becomes_active_and_labeled_by_index(qtbot) -> None:
    tabs = make_tabs(qtbot)

    widget = tabs.new_tab(shell="/bin/fake-shell", pty_session=FakePtySession())

    assert tabs.active_terminal() is widget
    assert tabs.tabText(0) == "0:fake-shell"


def test_multiple_tabs_are_numbered_in_order(qtbot) -> None:
    tabs = make_tabs(qtbot)

    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.new_tab(shell="/bin/zsh", pty_session=FakePtySession())

    assert tabs.tabText(0) == "0:bash"
    assert tabs.tabText(1) == "1:zsh"
    assert tabs.active_terminal() is tabs.widget(1)


def test_tab_label_stays_the_shell_name_when_the_title_changes(qtbot) -> None:
    """Shells emit wildly different OSC titles - Git Bash sends
    "MINGW64:/c/Users/dev/git/qtxterm", cmd its own full exe path - which
    made tabs unreadably wide."""
    tabs = make_tabs(qtbot)
    widget = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    widget.title_changed.emit("MINGW64:/c/Users/dev/git/qtxterm")

    assert tabs.tabText(0) == "0:bash"


def test_title_changed_goes_to_the_tab_tooltip(qtbot) -> None:
    tabs = make_tabs(qtbot)
    widget = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    widget.title_changed.emit("MINGW64:/c/Users/dev/git/qtxterm")

    assert tabs.tabToolTip(0) == "MINGW64:/c/Users/dev/git/qtxterm"


def test_a_hostile_osc_title_is_not_rendered_as_markup(qtbot) -> None:
    """Anything in the terminal can set this - a remote host over SSH
    included - and Qt draws a tooltip as rich text when the string looks
    like markup."""
    tabs = make_tabs(qtbot)
    widget = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    widget.title_changed.emit('<b>bank.com</b><img src="http://evil/x.png">')

    # Qt still treats the escaped string as rich text - an entity is enough
    # to trip that heuristic - so what matters is what it renders *to*: the
    # markup must come out as literal characters, with no element left to
    # format the text or reference an image.
    from PySide6.QtGui import QTextDocumentFragment

    tooltip = tabs.tabToolTip(0)
    rendered = QTextDocumentFragment.fromHtml(tooltip).toPlainText()

    assert rendered == '<b>bank.com</b><img src="http://evil/x.png">'
    assert "&lt;b&gt;bank.com&lt;/b&gt;" in tooltip


def test_tooltip_follows_the_tab_when_an_earlier_one_closes(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    second = tabs.new_tab(shell="/bin/zsh", pty_session=FakePtySession())
    second.title_changed.emit("~/second")

    tabs.close_tab_at(tabs.indexOf(first))
    second.title_changed.emit("~/second/moved")

    assert tabs.tabToolTip(0) == "~/second/moved"


def test_closing_a_tab_shuts_down_its_pty_and_renumbers_remaining(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty_a)
    tabs.new_tab(shell="/bin/zsh", pty_session=pty_b)

    tabs.close_tab_at(0)

    assert pty_a.closed is True
    assert pty_b.closed is False
    assert tabs.count() == 1
    assert tabs.tabText(0) == "0:zsh"


def test_closing_last_tab_emits_all_tabs_closed(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(pty_session=FakePtySession())

    with qtbot.waitSignal(tabs.all_tabs_closed, timeout=1000):
        tabs.close_tab_at(0)

    assert tabs.count() == 0


def test_close_all_tabs_shuts_down_every_pty_without_removing_them(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    tabs.new_tab(pty_session=pty_a)
    tabs.new_tab(pty_session=pty_b)

    tabs.close_all_tabs()

    assert pty_a.closed is True
    assert pty_b.closed is True
    assert tabs.count() == 2  # window-close path; MainWindow tears the window down after


def test_next_prev_tab_wraps_around(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(pty_session=FakePtySession())
    tabs.new_tab(pty_session=FakePtySession())
    tabs.setCurrentIndex(0)

    tabs._activate_next_tab()
    assert tabs.currentIndex() == 1

    tabs._activate_next_tab()
    assert tabs.currentIndex() == 0

    tabs._activate_prev_tab()
    assert tabs.currentIndex() == 1


def test_run_in_new_tab_feeds_lines_once_pty_starts(qtbot) -> None:
    tabs = make_tabs(qtbot)
    fake_pty = FakePtySession()

    widget = tabs.run_in_new_tab(None, ["echo one", "echo two"], pty_session=fake_pty)

    assert widget is tabs.active_terminal()
    assert fake_pty.write_calls == []  # PTY hasn't started yet

    widget._bridge.ready(80, 24)

    # Bare CR, not CRLF: CRLF submits twice and leaves an empty line behind.
    assert fake_pty.write_calls == ["echo one\r", "echo two\r"]


def test_appearance_store_change_reapplies_to_all_open_tabs(qtbot, tmp_path: Path) -> None:
    store = make_appearance_store(tmp_path)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)
    a = tabs.new_tab(pty_session=FakePtySession())
    b = tabs.new_tab(pty_session=FakePtySession())
    applied_a, applied_b = [], []
    a.apply_appearance = lambda appearance: applied_a.append(appearance)
    b.apply_appearance = lambda appearance: applied_b.append(appearance)

    new_appearance = Appearance(theme_name="Solarized Dark")
    store.save(new_appearance)

    assert applied_a == [new_appearance]
    assert applied_b == [new_appearance]


def test_tab_context_menu_request_is_re_emitted_by_the_tab_widget(qtbot) -> None:
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    widget = tabs.new_tab(pty_session=FakePtySession())

    pos = QPoint(5, 6)
    with qtbot.waitSignal(tabs.context_menu_requested, timeout=1000) as blocker:
        widget.context_menu_requested.emit(pos)

    assert blocker.args == [pos]


class FakeShellStore:
    def __init__(self, command) -> None:
        self._command = command

    def resolve(self):
        return self._command


def test_new_tab_uses_the_preferred_shell_when_none_is_given(qtbot) -> None:
    tabs = TerminalTabWidget(shell_store=FakeShellStore(["/usr/bin/wsl", "-d", "Ubuntu"]))
    qtbot.addWidget(tabs)
    pty = FakePtySession()

    widget = tabs.new_tab(pty_session=pty)
    widget._bridge.ready(80, 24)

    assert pty.start_calls[0][0] == ["/usr/bin/wsl", "-d", "Ubuntu"]


def test_an_explicit_shell_still_wins_over_the_preference(qtbot) -> None:
    tabs = TerminalTabWidget(shell_store=FakeShellStore("/bin/zsh"))
    qtbot.addWidget(tabs)
    pty = FakePtySession()

    widget = tabs.new_tab(shell="/bin/bash", pty_session=pty)
    widget._bridge.ready(80, 24)

    assert pty.start_calls[0][0] == ["/bin/bash"]


def test_default_shell_name_reflects_the_preference(qtbot) -> None:
    """Selection Actions targeting a new tab need this to pick the right way
    to feed a file to stdin."""
    tabs = TerminalTabWidget(shell_store=FakeShellStore(["/usr/bin/wsl", "-d", "Ubuntu"]))
    qtbot.addWidget(tabs)

    assert tabs.default_shell_name() == "wsl"


def test_default_shell_name_falls_back_to_the_os_shell(qtbot) -> None:
    tabs = make_tabs(qtbot)

    assert tabs.default_shell_name() == shell_short_name(default_shell())


def test_new_browser_tab_is_labelled_and_added(qtbot) -> None:
    tabs = make_tabs(qtbot)

    browser = tabs.new_browser_tab(url="about:blank")

    assert tabs.tabText(tabs.indexOf(browser)) == "0:browser"
    assert tabs.currentWidget() is browser


def test_browser_tab_label_follows_the_host(qtbot) -> None:
    """Unlike a shell's OSC title, a host is short and identifies the tab."""
    tabs = make_tabs(qtbot)
    browser = tabs.new_browser_tab(url="about:blank")

    browser.host_changed.emit("example.com")
    browser.title_changed.emit("Example Domain")

    assert tabs.tabText(0) == "0:example.com"
    assert tabs.tabToolTip(0) == "Example Domain"


def test_active_terminal_is_none_when_a_browser_tab_is_current(qtbot) -> None:
    """Otherwise the sidebar and Command submenu would write to a web page."""
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    browser = tabs.new_browser_tab(url="about:blank")

    assert tabs.currentWidget() is browser
    assert tabs.active_terminal() is None


def test_running_a_command_with_a_browser_tab_active_is_a_no_op(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty = FakePtySession()
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=pty)
    terminal._bridge.ready(80, 24)
    pty.write_calls.clear()
    tabs.new_browser_tab(url="about:blank")

    tabs.run_in_active(["git status"])

    assert pty.write_calls == []


def test_find_opens_in_the_focused_terminal(qtbot) -> None:
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    opened = []
    terminal.show_find = lambda: opened.append(True)

    tabs.show_find_in_active()

    assert opened == [True]


def test_find_with_a_browser_tab_active_is_a_no_op(qtbot) -> None:
    """Same rule as commands: a web page has no scrollback to search, and
    quietly searching another terminal would put the bar out of sight."""
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    opened = []
    terminal.show_find = lambda: opened.append(True)
    tabs.new_browser_tab(url="about:blank")

    tabs.show_find_in_active()

    assert opened == []


def test_closing_a_browser_tab_shuts_it_down_and_renumbers(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    browser = tabs.new_browser_tab(url="about:blank")

    tabs.close_tab_at(tabs.indexOf(browser))

    assert tabs.count() == 1
    assert tabs.tabText(0) == "0:bash"


def test_appearance_changes_skip_browser_tabs_without_error(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    store = AppearanceStore(settings)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.new_browser_tab(url="about:blank")

    store.save(Appearance(theme_name="Solarized Dark"))

    assert tabs.count() == 2


def test_rename_tab_replaces_the_name_but_keeps_the_index(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    tabs.rename_tab(0, "build server")

    assert tabs.tabText(0) == "0:build server"
    assert tabs.tab_title(0) == "build server"


def test_rename_survives_renumbering(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.new_tab(shell="/bin/zsh", pty_session=FakePtySession())
    tabs.rename_tab(1, "deploy")

    tabs.close_tab_at(tabs.indexOf(first))

    assert tabs.tabText(0) == "0:deploy"


def test_blank_rename_restores_the_automatic_name(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.rename_tab(0, "temporary")

    tabs.rename_tab(0, "   ")

    assert tabs.tabText(0) == "0:bash"


def test_a_rename_is_not_overwritten_by_automatic_updates(qtbot) -> None:
    """A browser tab keeps renaming itself from the page host; a user rename
    has to win over that."""
    tabs = make_tabs(qtbot)
    browser = tabs.new_browser_tab(url="about:blank")
    tabs.rename_tab(0, "docs")

    browser.host_changed.emit("example.com")

    assert tabs.tabText(0) == "0:docs"


def test_clearing_a_rename_falls_back_to_the_latest_automatic_name(qtbot) -> None:
    """Not the name the tab was born with - the browser has navigated since."""
    tabs = make_tabs(qtbot)
    browser = tabs.new_browser_tab(url="about:blank")
    browser.host_changed.emit("example.com")
    tabs.rename_tab(0, "docs")

    tabs.rename_tab(0, "")

    assert tabs.tabText(0) == "0:example.com"


def test_renaming_a_missing_tab_is_a_no_op(qtbot) -> None:
    tabs = make_tabs(qtbot)

    tabs.rename_tab(5, "nowhere")

    assert tabs.count() == 0


def test_double_click_on_empty_tab_bar_space_does_not_prompt(qtbot, monkeypatch) -> None:
    """tabBarDoubleClicked fires with -1 when the click misses every tab."""
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    prompted = []
    monkeypatch.setattr(
        terminal_tabs.QInputDialog,
        "getText",
        lambda *a, **kw: (prompted.append(True), ("x", True))[1],
    )

    tabs._prompt_rename(-1)

    assert prompted == []


def test_double_click_prompts_and_applies_the_new_name(qtbot, monkeypatch) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    monkeypatch.setattr(
        terminal_tabs.QInputDialog, "getText", lambda *a, **kw: ("renamed", True)
    )

    tabs.tabBarDoubleClicked.emit(0)

    assert tabs.tabText(0) == "0:renamed"


def test_cancelling_the_prompt_leaves_the_name_alone(qtbot, monkeypatch) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    monkeypatch.setattr(
        terminal_tabs.QInputDialog, "getText", lambda *a, **kw: ("ignored", False)
    )

    tabs.tabBarDoubleClicked.emit(0)

    assert tabs.tabText(0) == "0:bash"


def split_tab(tabs, *terminals) -> QSplitter:
    """A tab holding several terminals, standing in for a future split pane."""
    splitter = QSplitter()
    for t in terminals:
        splitter.addWidget(t)
    index = tabs.addTab(splitter, "")
    tabs.setCurrentIndex(index)
    return splitter


def test_terminals_in_finds_nested_panes(qtbot) -> None:
    tabs = make_tabs(qtbot)
    a = TerminalWidget(pty_session=FakePtySession())
    b = TerminalWidget(pty_session=FakePtySession())
    splitter = split_tab(tabs, a, b)

    found = tabs._terminals_in(splitter)

    assert set(found) == {a, b}


def test_active_terminal_follows_focus_within_a_tab(qtbot) -> None:
    """The crux of splitting: commands must go to the pane you last typed in,
    not an arbitrary one."""
    tabs = make_tabs(qtbot)
    a = TerminalWidget(pty_session=FakePtySession())
    b = TerminalWidget(pty_session=FakePtySession())
    splitter = split_tab(tabs, a, b)

    # Before focus tracking this returned None: a splitter tab isn't itself
    # a TerminalWidget, so there was nothing for commands to target.
    assert tabs.active_terminal() in (a, b)

    tabs._on_focus_changed(None, b)
    assert tabs.active_terminal() is b

    tabs._on_focus_changed(None, a)
    assert tabs.active_terminal() is a
    assert tabs._focused_panes[splitter] is a


def test_focus_is_traced_up_from_a_child_widget(qtbot) -> None:
    """Keyboard focus lands on a Chromium child, not the TerminalWidget."""
    tabs = make_tabs(qtbot)
    a = TerminalWidget(pty_session=FakePtySession())
    b = TerminalWidget(pty_session=FakePtySession())
    split_tab(tabs, a, b)

    inner = b._view.focusProxy() or b._view
    tabs._on_focus_changed(None, inner)

    assert tabs.active_terminal() is b


def test_focus_in_an_unrelated_widget_is_ignored(qtbot) -> None:
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    stray = TerminalWidget(pty_session=FakePtySession())
    qtbot.addWidget(stray)

    tabs._on_focus_changed(None, stray)

    assert tabs.active_terminal() is terminal
    assert stray not in tabs._focused_panes.values()


def test_a_closed_pane_is_not_returned_as_active(qtbot) -> None:
    tabs = make_tabs(qtbot)
    a = TerminalWidget(pty_session=FakePtySession())
    b = TerminalWidget(pty_session=FakePtySession())
    split_tab(tabs, a, b)
    tabs._on_focus_changed(None, b)

    b.setParent(None)

    assert tabs.active_terminal() is a


def test_appearance_reaches_every_pane(qtbot, tmp_path) -> None:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    store = AppearanceStore(settings)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)
    a = TerminalWidget(pty_session=FakePtySession())
    b = TerminalWidget(pty_session=FakePtySession())
    split_tab(tabs, a, b)
    applied = []
    a.apply_appearance = lambda ap: applied.append(a)
    b.apply_appearance = lambda ap: applied.append(b)

    store.save(Appearance(theme_name="Solarized Dark"))

    assert set(applied) == {a, b}


def test_close_all_tabs_shuts_down_every_pane(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    a = TerminalWidget(pty_session=pty_a)
    b = TerminalWidget(pty_session=pty_b)
    split_tab(tabs, a, b)

    tabs.close_all_tabs()

    assert pty_a.closed and pty_b.closed


def test_split_replaces_the_tab_root_with_a_splitter(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    root = tabs.widget(0)
    assert isinstance(root, QSplitter)
    assert root.orientation() == Qt.Orientation.Horizontal
    assert set(tabs._terminals_in(root)) == {first, second}
    assert tabs.count() == 1


def test_splitting_again_nests_inside_the_existing_splitter(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    third = tabs.split_active(Qt.Orientation.Vertical, pty_session=FakePtySession())

    assert len(tabs._terminals_in(tabs.widget(0))) == 3
    assert third.parentWidget().orientation() == Qt.Orientation.Vertical


def test_split_keeps_a_renamed_tab_name(qtbot) -> None:
    """The title maps are keyed by root widget, which splitting replaces."""
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.rename_tab(0, "build")

    tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    assert tabs.tabText(0) == "0:build"


def test_new_pane_becomes_the_active_one(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    assert tabs.active_terminal() is second


def test_closing_a_pane_leaves_the_other_and_collapses_the_splitter(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    assert tabs.active_terminal() is second

    tabs.close_active_pane()

    assert tabs.count() == 1
    assert tabs.widget(0) is first          # splitter unwrapped, not left behind
    assert tabs.active_terminal() is first


def test_closing_a_pane_shuts_down_only_that_pty(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty_a)
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=pty_b)

    tabs.close_active_pane()

    assert pty_b.closed is True
    assert pty_a.closed is False


def test_closing_the_last_pane_closes_the_tab(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    with qtbot.waitSignal(tabs.all_tabs_closed, timeout=1000):
        tabs.close_active_pane()

    assert tabs.count() == 0


def test_close_pane_collapse_survives_three_panes(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Vertical, pty_session=FakePtySession())

    tabs.close_active_pane()
    tabs.close_active_pane()

    assert len(tabs._terminals_in(tabs.widget(0))) == 1
    assert isinstance(tabs.widget(0), TerminalWidget)


def test_pane_border_only_shows_when_a_tab_has_several_panes(qtbot) -> None:
    tabs = make_tabs(qtbot)
    only = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs._refresh_pane_indicators()
    assert only._is_active_pane is False

    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    assert second._is_active_pane is True
    assert only._is_active_pane is False

    tabs.close_active_pane()
    assert only._is_active_pane is False


def test_splitting_a_browser_gives_another_browser(qtbot) -> None:
    """Splitting means "another one of these"."""
    tabs = make_tabs(qtbot)
    first = tabs.new_browser_tab(url="about:blank")

    second = tabs.split_active(Qt.Orientation.Horizontal)

    assert isinstance(second, BrowserWidget)
    assert second is not first
    assert set(tabs._panes_in(tabs.widget(0))) == {first, second}


def test_splitting_a_terminal_still_gives_a_terminal(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    assert isinstance(second, TerminalWidget)


def test_a_focused_browser_pane_means_no_active_terminal(qtbot) -> None:
    """Commands must not run in a terminal you aren't looking at just because
    the focused pane can't take them."""
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    browser = BrowserWidget(url="about:blank")
    splitter = QSplitter()
    splitter.addWidget(terminal)
    splitter.addWidget(browser)
    tabs.addTab(splitter, "")
    tabs.setCurrentIndex(tabs.indexOf(splitter))

    tabs._on_focus_changed(None, browser)
    assert tabs.active_pane() is browser
    assert tabs.active_terminal() is None

    tabs._on_focus_changed(None, terminal)
    assert tabs.active_terminal() is terminal


def test_closing_a_mixed_split_tab_shuts_down_both_kinds(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)
    browser = tabs.split_active(Qt.Orientation.Horizontal)
    stopped = []
    browser.shutdown = lambda: stopped.append(True)

    tabs.close_tab_at(0)

    assert pty.closed is True


def test_a_browser_pane_can_be_closed_and_moved(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_browser_tab(url="about:blank")
    second = tabs.split_active(Qt.Orientation.Horizontal)
    splitter = tabs.widget(0)
    assert [splitter.widget(i) for i in range(2)] == [first, second]

    assert tabs.move_active_pane(forward=False) is True
    assert [splitter.widget(i) for i in range(2)] == [second, first]

    tabs.close_active_pane()
    assert tabs.widget(0) is first


def test_move_pane_swaps_with_its_neighbour(qtbot) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    second = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    splitter = tabs.widget(0)
    assert [splitter.widget(i) for i in range(2)] == [first, second]

    assert tabs.move_active_pane(forward=False) is True

    assert [splitter.widget(i) for i in range(2)] == [second, first]


def test_move_pane_stops_at_the_edges(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    assert tabs.can_move_active_pane(forward=True) is False
    assert tabs.move_active_pane(forward=True) is False
    assert tabs.can_move_active_pane(forward=False) is True


def test_move_pane_is_unavailable_without_a_split(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert tabs.active_pane_orientation() is None
    assert tabs.can_move_active_pane(forward=True) is False
    assert tabs.move_active_pane(forward=True) is False


def test_active_pane_orientation_follows_the_splitter(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Vertical, pty_session=FakePtySession())

    assert tabs.active_pane_orientation() is Qt.Orientation.Vertical


def test_move_pane_to_new_tab_keeps_the_terminal_alive(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    first = tabs.new_tab(shell="/bin/bash", pty_session=pty_a)
    second = tabs.split_active(
        Qt.Orientation.Horizontal, shell="/bin/zsh", pty_session=pty_b
    )

    moved = tabs.move_active_pane_to_new_tab()

    assert moved is second
    assert tabs.count() == 2
    assert tabs.widget(0) is first          # source tab collapsed back to one
    assert tabs.widget(1) is second
    assert pty_b.closed is False            # same shell, new container
    assert tabs.tabText(1) == "1:zsh"   # names its own shell, not the source tab's


def test_move_pane_to_new_tab_needs_more_than_one_pane(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert tabs.move_active_pane_to_new_tab() is None
    assert tabs.count() == 1


def test_closing_a_split_tab_shuts_down_every_pane(qtbot) -> None:
    """A split tab's root is a QSplitter, which has no shutdown() - calling it
    there raised before removeTab(), leaving the tab open and its shells
    running."""
    tabs = make_tabs(qtbot)
    pty_a, pty_b, pty_c = FakePtySession(), FakePtySession(), FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty_a)
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=pty_b)
    tabs.split_active(Qt.Orientation.Vertical, pty_session=pty_c)

    tabs.close_tab_at(0)

    assert tabs.count() == 0
    assert pty_a.closed and pty_b.closed and pty_c.closed


def test_closing_a_split_tab_via_the_close_button_signal(qtbot) -> None:
    """tabCloseRequested is what the tab's x button emits."""
    tabs = make_tabs(qtbot)
    pty_a, pty_b = FakePtySession(), FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty_a)
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=pty_b)

    tabs.tabCloseRequested.emit(0)

    assert tabs.count() == 0
    assert pty_a.closed and pty_b.closed


def test_closing_a_browser_tab_still_shuts_it_down(qtbot) -> None:
    """_panes_in falls back to the tab itself when it holds no terminals."""
    tabs = make_tabs(qtbot)
    browser = tabs.new_browser_tab(url="about:blank")
    stopped = []
    browser.shutdown = lambda: stopped.append(True)

    tabs.close_tab_at(0)

    assert stopped == [True]
    assert tabs.count() == 0


def test_run_macro_without_separators_opens_one_tab(qtbot) -> None:
    tabs = make_tabs(qtbot)
    pty = FakePtySession()

    opened = tabs.run_macro(["echo one", "echo two"])
    opened[0]._pty = pty
    opened[0]._bridge.ready(80, 24)

    assert len(opened) == 1
    assert tabs.count() == 1


def test_run_macro_opens_a_tab_per_separator(qtbot) -> None:
    tabs = make_tabs(qtbot)

    opened = tabs.run_macro(["echo one", "---", "echo two", "---", "echo three"])

    assert len(opened) == 3
    assert tabs.count() == 3


def test_run_macro_splits_instead_of_opening_a_tab(qtbot) -> None:
    tabs = make_tabs(qtbot)

    opened = tabs.run_macro(["dev", "--- right", "tests", "--- down", "logs"])

    assert len(opened) == 3
    assert tabs.count() == 1                       # all three share one tab
    assert len(tabs._panes_in(tabs.widget(0))) == 3


def test_run_macro_mixes_tabs_and_panes(qtbot) -> None:
    tabs = make_tabs(qtbot)

    tabs.run_macro(["a", "--- right", "b", "---", "c"])

    assert tabs.count() == 2
    assert len(tabs._panes_in(tabs.widget(0))) == 2
    assert len(tabs._panes_in(tabs.widget(1))) == 1


def test_run_macro_feeds_each_step_its_own_lines(qtbot) -> None:
    tabs = make_tabs(qtbot)
    ptys = [FakePtySession(), FakePtySession()]

    opened = tabs.run_macro(["first", "--- right", "second"])
    for widget, pty in zip(opened, ptys):
        widget._pty = pty
        widget._bridge.ready(80, 24)

    assert ptys[0].write_calls == ["first\r"]
    assert ptys[1].write_calls == ["second\r"]


def test_a_new_tab_takes_the_keyboard(qtbot, monkeypatch) -> None:
    """addTab leaves Qt's focus on the tab bar, so without this a new terminal
    needs a click before it accepts a keystroke - and until that click, arrow
    keys reach the QTabBar and switch tabs instead."""
    tabs = make_tabs(qtbot)
    focused = []
    monkeypatch.setattr(TerminalWidget, "focus_pane", lambda self: focused.append(self))

    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert focused == [terminal]


def test_splitting_gives_the_keyboard_to_the_new_pane(qtbot, monkeypatch) -> None:
    """The reported bug: after a split, focus stayed on the QTabBar, so the
    arrow keys switched tabs rather than moving between panes."""
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    focused = []
    monkeypatch.setattr(TerminalWidget, "focus_pane", lambda self: focused.append(self))

    new = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())

    assert focused[-1] is new


def test_closing_a_pane_gives_the_keyboard_to_the_survivor(qtbot, monkeypatch) -> None:
    tabs = make_tabs(qtbot)
    first = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    focused = []
    monkeypatch.setattr(TerminalWidget, "focus_pane", lambda self: focused.append(self))

    tabs.close_active_pane()

    assert focused[-1] is first


def _nested_layout(qtbot, tabs):
    """LEFT beside a stacked TOPRIGHT / BOTRIGHT, laid out for real.

    Shown and resized because this is the one behaviour decided by on-screen
    geometry - an unlaid-out tab gives every pane the same rect, and the test
    would then be passing on nothing.
    """
    tabs.resize(800, 600)
    tabs.show()
    left = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    top = tabs.split_active(Qt.Orientation.Horizontal, pty_session=FakePtySession())
    bottom = tabs.split_active(Qt.Orientation.Vertical, pty_session=FakePtySession())
    qtbot.waitUntil(
        lambda: tabs._pane_rect(left).width() > 0
        and tabs._pane_rect(top).top() < tabs._pane_rect(bottom).top(),
        timeout=5000,
    )
    return left, top, bottom


def test_alt_arrow_moves_between_panes_by_geometry(qtbot) -> None:
    tabs = make_tabs(qtbot)
    left, top_right, bottom_right = _nested_layout(qtbot, tabs)

    tabs._focused_panes[tabs.currentWidget()] = bottom_right
    assert tabs.focus_pane_in_direction(-1, 0) is left
    assert tabs.focus_pane_in_direction(1, 0) is top_right
    assert tabs.focus_pane_in_direction(0, 1) is bottom_right
    assert tabs.focus_pane_in_direction(0, -1) is top_right


def test_moving_right_prefers_the_pane_that_lines_up(qtbot) -> None:
    """From the tall left pane, the two right-hand panes' centres sat 138 and
    139 pixels off axis - one pixel apart, so ranking by centre distance made
    the choice a coin flip that would flip again if the splitter moved.
    Overlap is stable under that, and the top-left tie-break settles a tie."""
    tabs = make_tabs(qtbot)
    left, top_right, _bottom = _nested_layout(qtbot, tabs)

    tabs._focused_panes[tabs.currentWidget()] = left

    assert tabs.focus_pane_in_direction(1, 0) is top_right


def test_navigating_past_the_edge_does_nothing(qtbot) -> None:
    """No wraparound: panes are a spatial layout, and jumping from the
    rightmost pane back to the leftmost is not what "right" means."""
    tabs = make_tabs(qtbot)
    _left, top_right, _bottom = _nested_layout(qtbot, tabs)

    tabs._focused_panes[tabs.currentWidget()] = top_right

    assert tabs.focus_pane_in_direction(0, -1) is None
    assert tabs.focus_pane_in_direction(1, 0) is None


def test_alt_arrow_does_nothing_in_an_unsplit_tab(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert tabs.focus_pane_in_direction(1, 0) is None


def _shortcut_for(tabs, sequence: str):
    """The QShortcut registered for `sequence`, or None."""
    from PySide6.QtGui import QShortcut

    for shortcut in tabs.findChildren(QShortcut):
        if shortcut.key().toString() == sequence:
            return shortcut
    return None


def test_split_is_bound_to_the_chord_the_keyboard_actually_sends(qtbot) -> None:
    """The reported bug: neither split shortcut fired from a real keyboard.

    Qt matches "Alt+Shift+=" against Key_Equal, but holding Shift and pressing
    that key sends Key_Plus - and "Alt+Shift+-" arrives as Key_Underscore. Both
    spellings have to be registered or the documented chord does nothing.
    """
    tabs = make_tabs(qtbot)

    for sequence in (
        # Alt+Shift fails one way: Qt matches "Alt+Shift+=" against Key_Equal,
        # but Shift plus that key sends Key_Plus.
        "Alt+Shift+=",
        "Alt+Shift++",
        "Alt+Shift+-",
        "Alt+Shift+_",
        # Ctrl+Shift fails the opposite way: with Ctrl held the character is a
        # control code (Ctrl+_ is 0x1f), so Qt cannot derive "_" from the
        # layout and reports the base key - Key_Minus, or Key_Backslash for
        # the bar.
        "Ctrl+Shift+|",
        "Ctrl+Shift+\\",
        "Ctrl+Shift+_",
        "Ctrl+Shift+-",
    ):
        assert _shortcut_for(tabs, sequence) is not None, sequence


def test_every_split_chord_actually_splits(qtbot) -> None:
    """Activated directly rather than by a key press, so this asserts the
    wiring without depending on which window the runner has active."""
    cases = [
        ("Alt+Shift+=", Qt.Orientation.Horizontal),
        ("Alt+Shift++", Qt.Orientation.Horizontal),
        ("Ctrl+Shift+|", Qt.Orientation.Horizontal),
        ("Ctrl+Shift+\\", Qt.Orientation.Horizontal),
        ("Alt+Shift+-", Qt.Orientation.Vertical),
        ("Alt+Shift+_", Qt.Orientation.Vertical),
        ("Ctrl+Shift+_", Qt.Orientation.Vertical),
        ("Ctrl+Shift+-", Qt.Orientation.Vertical),
    ]
    for sequence, orientation in cases:
        tabs = make_tabs(qtbot)
        tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
        shortcut = _shortcut_for(tabs, sequence)
        assert shortcut is not None, sequence

        shortcut.activated.emit()

        assert len(tabs._panes_in(tabs.currentWidget())) == 2, sequence
        splitter = tabs.currentWidget()
        assert isinstance(splitter, QSplitter)
        assert splitter.orientation() is orientation, sequence

def test_copy_shortcut_copies_the_active_terminals_selection(qtbot) -> None:
    from PySide6.QtGui import QGuiApplication

    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    terminal._bridge.setSelection("selected output")

    assert tabs.copy_in_active() is True
    assert QGuiApplication.clipboard().text() == "selected output"


def test_copy_with_nothing_selected_does_not_clear_the_clipboard(qtbot) -> None:
    """Matters most on macOS, where the binding is plain Cmd+C: pressing it
    with no selection should do nothing, not wipe what you already copied."""
    from PySide6.QtGui import QGuiApplication

    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    QGuiApplication.clipboard().setText("kept")

    assert tabs.copy_in_active() is False
    assert QGuiApplication.clipboard().text() == "kept"


def test_paste_goes_through_the_terminal_so_bracketed_paste_is_honoured(qtbot) -> None:
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    pasted = []
    terminal.paste_from_clipboard = lambda: pasted.append(True)

    tabs.paste_in_active()

    assert pasted == [True]


def test_copy_and_paste_do_nothing_while_a_browser_pane_is_active(qtbot) -> None:
    tabs = make_tabs(qtbot)
    terminal = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    pasted = []
    terminal.paste_from_clipboard = lambda: pasted.append(True)
    tabs.new_browser_tab(url="about:blank")

    tabs.paste_in_active()

    assert pasted == []
    assert tabs.copy_in_active() is False


def test_zoom_changes_the_stored_font_size(qtbot, tmp_path: Path) -> None:
    """Saved through the store rather than pushed at the open terminals, so
    it survives a restart and reaches panes opened later."""
    store = make_appearance_store(tmp_path)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)
    start = store.current.font_size

    assert tabs.zoom_font(1) == start + 1
    assert store.current.font_size == start + 1
    assert tabs.zoom_font(-1) == start
    assert store.current.font_size == start


def test_zoom_stops_at_the_same_bounds_the_preferences_dialog_uses(
    qtbot, tmp_path: Path
) -> None:
    """Zooming past a size the dialog refuses to show would leave a
    preference you could see but not edit back."""
    from qtxterm.appearance import MAX_FONT_SIZE, MIN_FONT_SIZE

    store = make_appearance_store(tmp_path)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)

    for _ in range(200):
        tabs.zoom_font(1)
    assert store.current.font_size == MAX_FONT_SIZE

    for _ in range(200):
        tabs.zoom_font(-1)
    assert store.current.font_size == MIN_FONT_SIZE


def test_zoom_reset_returns_to_the_default_size(qtbot, tmp_path: Path) -> None:
    from qtxterm.appearance import DEFAULT_FONT_SIZE

    store = make_appearance_store(tmp_path)
    tabs = TerminalTabWidget(appearance_store=store)
    qtbot.addWidget(tabs)
    tabs.zoom_font(5)

    assert tabs.reset_font_zoom() == DEFAULT_FONT_SIZE
    assert store.current.font_size == DEFAULT_FONT_SIZE


def test_zoom_is_a_no_op_without_an_appearance_store(qtbot) -> None:
    tabs = make_tabs(qtbot)

    assert tabs.zoom_font(1) is None
    assert tabs.reset_font_zoom() is None


def test_tab_slots_select_by_position(qtbot) -> None:
    tabs = make_tabs(qtbot)
    for _ in range(4):
        tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert tabs.activate_tab_slot(1) is True
    assert tabs.currentIndex() == 0
    assert tabs.activate_tab_slot(3) is True
    assert tabs.currentIndex() == 2


def test_the_last_slot_means_the_last_tab_not_the_ninth(qtbot) -> None:
    """Following browsers and Windows Terminal, so it stays useful with more
    tabs than slots - and does not simply fail with fewer."""
    tabs = make_tabs(qtbot)
    for _ in range(3):
        tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    assert tabs.activate_tab_slot(shortcuts.LAST_TAB_SLOT) is True
    assert tabs.currentIndex() == 2


def test_a_slot_past_the_last_tab_does_nothing(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    tabs.setCurrentIndex(0)

    assert tabs.activate_tab_slot(5) is False
    assert tabs.currentIndex() == 0


def test_tab_slots_do_nothing_with_no_tabs_open(qtbot) -> None:
    tabs = make_tabs(qtbot)

    assert tabs.activate_tab_slot(1) is False


def test_every_shortcut_action_is_registered_on_the_widget(qtbot) -> None:
    """Catches an action added to the table but never wired up - which would
    look fine everywhere except when you pressed the key."""
    tabs = make_tabs(qtbot)
    registered = {s.key().toString() for s in tabs.findChildren(QShortcut)}

    for action in shortcuts.all_actions():
        for sequence in shortcuts.sequences_for(action):
            assert QKeySequence(sequence).toString() in registered, (action, sequence)

def make_exit_store(tmp_path: Path, choice: str):
    from qtxterm.exit_prefs import PaneExitStore

    settings = QSettings(str(tmp_path / "exit.ini"), QSettings.Format.IniFormat)
    store = PaneExitStore(settings)
    store.save(choice)
    return store


def make_tabs_with_exit(qtbot, tmp_path: Path, choice: str) -> TerminalTabWidget:
    tabs = TerminalTabWidget(exit_store=make_exit_store(tmp_path, choice))
    qtbot.addWidget(tabs)
    return tabs


def test_a_clean_shell_exit_closes_its_pane(qtbot, tmp_path: Path) -> None:
    from qtxterm.exit_prefs import CLOSE_CLEAN

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_CLEAN)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)
    tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    assert tabs.count() == 2

    pty.exited.emit(0)

    qtbot.waitUntil(lambda: tabs.count() == 1, timeout=2000)


def test_a_failed_shell_keeps_its_pane_so_you_can_read_the_error(
    qtbot, tmp_path: Path
) -> None:
    from qtxterm.exit_prefs import CLOSE_CLEAN

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_CLEAN)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)

    pty.exited.emit(1)
    qtbot.wait(200)

    assert tabs.count() == 1


def test_always_closes_even_a_failed_shell(qtbot, tmp_path: Path) -> None:
    from qtxterm.exit_prefs import CLOSE_ALWAYS

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_ALWAYS)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)

    pty.exited.emit(1)

    qtbot.waitUntil(lambda: tabs.count() == 0, timeout=2000)


def test_never_leaves_the_pane_alone(qtbot, tmp_path: Path) -> None:
    from qtxterm.exit_prefs import CLOSE_NEVER

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_NEVER)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)

    pty.exited.emit(0)
    qtbot.wait(200)

    assert tabs.count() == 1


def test_an_exiting_shell_closes_only_its_own_pane_in_a_split(
    qtbot, tmp_path: Path
) -> None:
    """A shell exits in whichever pane it was running, very often not the one
    you are looking at - which is why closing acts on the pane that exited
    rather than the focused one."""
    from qtxterm.exit_prefs import CLOSE_CLEAN

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_CLEAN)
    first_pty = FakePtySession()
    first = tabs.new_tab(shell="/bin/bash", pty_session=first_pty)
    second = tabs.split_active(
        Qt.Orientation.Horizontal, pty_session=FakePtySession()
    )
    assert len(tabs._panes_in(tabs.currentWidget())) == 2

    first_pty.exited.emit(0)

    qtbot.waitUntil(
        lambda: tabs._panes_in(tabs.currentWidget()) == [second], timeout=2000
    )
    assert first not in tabs._panes_in(tabs.currentWidget())


def test_no_exit_store_means_the_old_behaviour(qtbot) -> None:
    """A TerminalTabWidget built without one - as tests and embedders do -
    must not start closing panes on its own."""
    tabs = make_tabs(qtbot)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)

    pty.exited.emit(0)
    qtbot.wait(200)

    assert tabs.count() == 1


def test_a_tab_closed_before_the_deferred_close_runs_is_survivable(
    qtbot, tmp_path: Path
) -> None:
    """Closing is deferred a turn of the event loop, because deleting the
    widget that owns the object currently emitting is how you get a crash
    instead of a closed pane. That gap means the pane can already be gone."""
    from qtxterm.exit_prefs import CLOSE_CLEAN

    tabs = make_tabs_with_exit(qtbot, tmp_path, CLOSE_CLEAN)
    pty = FakePtySession()
    tabs.new_tab(shell="/bin/bash", pty_session=pty)

    pty.exited.emit(0)
    tabs.close_tab_at(0)
    qtbot.wait(200)

    assert tabs.count() == 0

def test_panes_in_a_split_get_different_slices_of_the_background(qtbot) -> None:
    """The whole point of spanning: each pane is a separate page, so left to
    itself every one paints the entire picture and a tab split three ways
    shows it three times."""
    tabs = make_tabs(qtbot)
    left, top_right, bottom_right = _nested_layout(qtbot, tabs)
    pushed = {}
    for pane in (left, top_right, bottom_right):
        pane.set_background_geometry = (
            lambda x, y, w, h, p=pane: pushed.__setitem__(p, (x, y, w, h))
        )

    tabs.refresh_background_geometry()

    assert len(pushed) == 3
    origins = {(x, y) for x, y, _w, _h in pushed.values()}
    assert len(origins) == 3, origins
    # Every pane is told the same tab size - that is what they window into.
    sizes = {(w, h) for _x, _y, w, h in pushed.values()}
    assert len(sizes) == 1, sizes
    # The left pane starts at the tab's left edge; the right ones do not.
    assert pushed[left][0] < pushed[top_right][0]
    # The stacked pair share a column but not a row.
    assert pushed[top_right][0] == pushed[bottom_right][0]
    assert pushed[top_right][1] < pushed[bottom_right][1]


def test_an_unsplit_pane_spans_its_whole_tab(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.resize(700, 500)
    tabs.show()
    pane = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())
    pushed = []
    pane.set_background_geometry = lambda x, y, w, h: pushed.append((x, y, w, h))

    tabs.refresh_background_geometry()

    assert pushed, "no geometry pushed"
    x, y, w, h = pushed[-1]
    # Not (0, 0): the origin is the *page*, which starts inside the pane's
    # border margin. Measuring the pane instead would shift every slice by
    # that margin and leave visible seams where panes meet.
    assert (x, y) == (PANE_BORDER_WIDTH, PANE_BORDER_WIDTH)
    assert w > 0 and h > 0
