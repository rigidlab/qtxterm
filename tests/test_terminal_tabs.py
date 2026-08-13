"""TerminalTabWidget: tab lifecycle, tmux-style labels, active-terminal tracking."""

from __future__ import annotations

from pathlib import Path

from conftest import FakePtySession
from PySide6.QtCore import QPoint, QSettings, Qt
from PySide6.QtWidgets import QSplitter

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm import terminal_tabs
from qtxterm.pty_backend import default_shell
from qtxterm.terminal_tabs import TerminalTabWidget
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

    assert fake_pty.write_calls == ["echo one\r\n", "echo two\r\n"]


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
    assert tabs._focused_terminals[splitter] is a


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
    assert stray not in tabs._focused_terminals.values()


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


def test_splitting_a_browser_tab_does_nothing(qtbot) -> None:
    tabs = make_tabs(qtbot)
    tabs.new_browser_tab(url="about:blank")

    assert tabs.split_active(Qt.Orientation.Horizontal) is None
    assert tabs.count() == 1


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
