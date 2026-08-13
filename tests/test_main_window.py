"""MainWindow: sidebar dock visibility, window/layout persistence, and the
Help menu.

Real PTYs get spawned here (MainWindow doesn't take an injected PtySession),
so these are closer to integration tests than the rest of the suite.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDockWidget

from conftest import FakePtySession

from qtxterm.main_window import MainWindow


def make_settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "window_state.ini"), QSettings.Format.IniFormat)


def test_sidebar_dock_has_close_feature(qtbot, tmp_path: Path) -> None:
    """The dock's title bar has an "x" (minimize) button so it can be
    hidden directly, without going through the Commands menu."""
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()

    assert (
        window._sidebar_dock.features()
        & QDockWidget.DockWidgetFeature.DockWidgetClosable
    )

    window.close()


def test_closing_dock_from_title_bar_unchecks_show_sidebar_action(
    qtbot, tmp_path: Path
) -> None:
    """Closing the dock via its own "x" button only hides it (Qt semantics),
    and that hide is reflected back onto the Commands menu's toggle."""
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    action = next(
        a for a in window._commands_menu.actions() if a.text() == "Show Sidebar"
    )

    window._sidebar_dock.close()

    assert window._sidebar_dock.isVisible() is False
    assert action.isChecked() is False

    window.close()


def test_show_sidebar_action_toggles_dock_visibility(qtbot, tmp_path: Path) -> None:
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    action = next(
        a for a in window._commands_menu.actions() if a.text() == "Show Sidebar"
    )

    assert action.isEnabled() is True
    assert window._sidebar_dock.isVisible() is True
    assert action.isChecked() is True

    action.trigger()
    assert window._sidebar_dock.isVisible() is False
    assert action.isChecked() is False

    action.trigger()
    assert window._sidebar_dock.isVisible() is True
    assert action.isChecked() is True

    window.close()


def test_sidebar_hidden_state_persists_across_restart(qtbot, tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    window.show()
    window._sidebar_dock.setVisible(False)

    window.close()

    reopened = MainWindow(settings=settings)
    qtbot.addWidget(reopened)
    reopened.show()

    assert reopened._sidebar_dock.isVisible() is False
    action = next(
        a for a in reopened._commands_menu.actions() if a.text() == "Show Sidebar"
    )
    assert action.isChecked() is False

    reopened.close()


def test_window_size_persists_across_restart(qtbot, tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    window = MainWindow(settings=settings)
    qtbot.addWidget(window)
    window.show()
    window.resize(1234, 789)

    window.close()

    reopened = MainWindow(settings=settings)
    qtbot.addWidget(reopened)
    reopened.show()

    assert reopened.size().width() == 1234
    assert reopened.size().height() == 789

    reopened.close()


def test_help_menu_usage_action_opens_the_dialog(
    qtbot, monkeypatch, tmp_path: Path
) -> None:
    """exec() is monkeypatched - a real modal would block the test run."""
    import qtxterm.main_window as main_window

    opened = []

    class FakeHelpDialog:
        def __init__(self, parent=None) -> None:
            opened.append(parent)

        def exec(self) -> int:
            return 0

    monkeypatch.setattr(main_window, "HelpDialog", FakeHelpDialog)

    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()

    assert "&Help" in [a.text() for a in window.menuBar().actions()]
    assert window._usage_action.text() == "Usage"
    assert not window._usage_action.icon().isNull()

    window._usage_action.trigger()

    assert opened == [window]

    window.close()


def test_menu_bar_order(qtbot, tmp_path: Path) -> None:
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)

    assert [a.text() for a in window.menuBar().actions()] == [
        "&File",
        "&Macros",
        "&Commands",
        "&Selection",
        "&Help",
    ]


def test_window_starts_with_no_terminals(qtbot, tmp_path: Path) -> None:
    """Opening the app doesn't decide what you wanted to open."""
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)

    assert window._tabs.count() == 0


def test_closing_the_last_terminal_leaves_the_window_open(qtbot, tmp_path: Path) -> None:
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window.show()
    window._tabs.new_tab(pty_session=FakePtySession())

    window._tabs.close_tab_at(0)

    assert window._tabs.count() == 0
    assert window.isVisible()


def test_a_terminal_can_be_opened_again_after_the_last_one_closed(
    qtbot, tmp_path: Path
) -> None:
    window = MainWindow(settings=make_settings(tmp_path))
    qtbot.addWidget(window)
    window._tabs.new_tab(pty_session=FakePtySession())
    window._tabs.close_tab_at(0)

    window._tabs.new_tab(pty_session=FakePtySession())

    assert window._tabs.count() == 1
