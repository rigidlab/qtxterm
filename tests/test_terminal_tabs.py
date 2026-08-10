"""TerminalTabWidget: tab lifecycle, tmux-style labels, active-terminal tracking."""

from __future__ import annotations

from pathlib import Path

from conftest import FakePtySession
from PySide6.QtCore import QPoint, QSettings

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm.pty_backend import default_shell
from qtxterm.terminal_tabs import TerminalTabWidget
from qtxterm.terminal_widget import shell_short_name


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
