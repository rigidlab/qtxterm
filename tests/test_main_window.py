"""MainWindow: sidebar dock has no close button, only menu-driven visibility.

Real PTYs get spawned here (MainWindow doesn't take an injected PtySession),
so these are closer to integration tests than the rest of the suite.
"""

from __future__ import annotations

from PySide6.QtWidgets import QDockWidget

from qtxterm.main_window import MainWindow


def test_sidebar_dock_has_no_close_feature(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()

    assert not (
        window._sidebar_dock.features() & QDockWidget.DockWidgetFeature.DockWidgetClosable
    )

    window.close()


def test_show_sidebar_action_toggles_dock_visibility(qtbot) -> None:
    """Regression test: QDockWidget.toggleViewAction()'s enabled state is
    tied to the DockWidgetClosable feature, so it goes silently inert once
    Closable is removed. MainWindow must use its own independent action."""
    window = MainWindow()
    qtbot.addWidget(window)
    window.show()
    action = next(a for a in window._commands_menu.actions() if a.text() == "Show Sidebar")

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
