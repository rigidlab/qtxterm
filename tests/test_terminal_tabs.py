"""TerminalTabWidget: tab lifecycle, tmux-style labels, active-terminal tracking."""

from __future__ import annotations

from conftest import FakePtySession

from mterm.terminal_tabs import TerminalTabWidget


def make_tabs(qtbot) -> TerminalTabWidget:
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    return tabs


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


def test_title_changed_updates_tab_label_in_place(qtbot) -> None:
    tabs = make_tabs(qtbot)
    widget = tabs.new_tab(shell="/bin/bash", pty_session=FakePtySession())

    widget.title_changed.emit("~/git/mterm")

    assert tabs.tabText(0) == "0:~/git/mterm"


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
