from __future__ import annotations

from PySide6.QtCore import QSettings, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow, QStyle

from qtxterm.appearance import AppearanceStore
from qtxterm.branding import app_icon
from qtxterm.help_dialog import HelpDialog
from qtxterm.preferences_dialog import PreferencesDialog
from qtxterm.preset_menu import (
    CommandsMenu,
    MacrosMenu,
    SelectionMenu,
    TerminalContextMenu,
)
from qtxterm.presets import PresetStore
from qtxterm.qt_theme import apply_qt_theme
from qtxterm.shells import known_shells
from qtxterm.sidebar import CommandSidebar
from qtxterm.terminal_tabs import TerminalTabWidget
from qtxterm.window_state import make_settings

_GEOMETRY_KEY = "window/geometry"
_DOCK_STATE_KEY = "window/dockState"


class MainWindow(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self._settings = settings or make_settings()
        self.setWindowTitle("qtxterm")
        # Also set per-window, not just on QApplication: keeps the title bar
        # icon correct for windows created outside app.main() (tests, embedding).
        self.setWindowIcon(app_icon())
        self.resize(1000, 650)

        self._appearance_store = AppearanceStore(self._settings)
        self._appearance_store.changed.connect(self._apply_qt_theme)
        self._apply_qt_theme()
        self._tabs = TerminalTabWidget(
            parent=self, appearance_store=self._appearance_store
        )
        self._tabs.all_tabs_closed.connect(self.close)
        self.setCentralWidget(self._tabs)

        self._preset_store = PresetStore()
        self._sidebar = CommandSidebar(self._preset_store, parent=self)
        self._sidebar.run_requested.connect(self._tabs.run_in_active)
        self._sidebar_dock = QDockWidget("Commands", self)
        # QMainWindow.saveState()/restoreState() key dock entries off
        # objectName - without one, saveState() warns and the dock's
        # visibility/geometry silently isn't restored.
        self._sidebar_dock.setObjectName("commandsDock")
        self._sidebar_dock.setWidget(self._sidebar)
        # Closable gives the dock an "x" (minimize) button in its title bar.
        # Closing a QDockWidget only hides it, it doesn't destroy it, and the
        # toggle action below (wired to visibilityChanged) keeps "Show
        # Sidebar" in the Commands menu in sync either way, so there's always
        # a way back.
        self._sidebar_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
            | QDockWidget.DockWidgetFeature.DockWidgetClosable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._sidebar_dock)

        self._build_file_menu()

        # Not sidebar_dock.toggleViewAction(): that built-in action's text is
        # fixed to the dock's title ("Commands"), not the friendlier "Show
        # Sidebar" we want in the menu. An independent action wired both ways
        # (toggled -> setVisible, visibilityChanged -> setChecked) keeps them
        # in sync regardless.
        sidebar_toggle_action = QAction("Show Sidebar", self)
        sidebar_toggle_action.setCheckable(True)
        sidebar_toggle_action.setChecked(True)
        sidebar_toggle_action.toggled.connect(self._sidebar_dock.setVisible)
        self._sidebar_dock.visibilityChanged.connect(sidebar_toggle_action.setChecked)
        self._commands_menu = CommandsMenu(
            self._preset_store,
            self._tabs,
            sidebar_toggle_action=sidebar_toggle_action,
            parent=self,
        )
        self.menuBar().addMenu(self._commands_menu)

        self._macros_menu = MacrosMenu(self._preset_store, self._tabs, parent=self)
        self.menuBar().addMenu(self._macros_menu)

        self._selection_menu = SelectionMenu(
            self._preset_store, self._tabs, parent=self
        )
        self.menuBar().addMenu(self._selection_menu)

        # One menu shared by every tab - it rebuilds itself on store changes,
        # so there's nothing per-tab to keep in sync.
        self._terminal_context_menu = TerminalContextMenu(
            self._preset_store, self._tabs, parent=self
        )
        self._tabs.context_menu_requested.connect(self._show_terminal_context_menu)

        self._build_help_menu()

        # After all dock/menu wiring so restoring dock visibility triggers
        # visibilityChanged into an already-connected sidebar_toggle_action.
        self._restore_window_state()

        self._tabs.new_tab()

    def _show_terminal_context_menu(self, global_pos) -> None:
        self._terminal_context_menu.exec(global_pos)

    def _apply_qt_theme(self) -> None:
        app = QApplication.instance()
        if app is not None:
            apply_qt_theme(app, self._appearance_store.current.theme)

    def _restore_window_state(self) -> None:
        geometry = self._settings.value(_GEOMETRY_KEY)
        if geometry is not None:
            self.restoreGeometry(geometry)
        dock_state = self._settings.value(_DOCK_STATE_KEY)
        if dock_state is not None:
            self.restoreState(dock_state)

    def _save_window_state(self) -> None:
        self._settings.setValue(_GEOMETRY_KEY, self.saveGeometry())
        self._settings.setValue(_DOCK_STATE_KEY, self.saveState())

    def _build_help_menu(self) -> None:
        self._help_menu = self.menuBar().addMenu("&Help")
        self._usage_action = self._help_menu.addAction("Usage")
        self._usage_action.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        )
        self._usage_action.triggered.connect(self.show_usage)

    def show_usage(self) -> None:
        HelpDialog(self).exec()

    def _build_file_menu(self) -> None:
        # QMenu.addMenu() parents the submenu in C++, but without a Python-side
        # reference kept alive too, PySide6 can garbage-collect the wrapper (and
        # the underlying object with it) - store both on self to keep them alive
        # for the window's lifetime.
        self._file_menu = self.menuBar().addMenu("&File")
        self._new_terminal_menu = self._file_menu.addMenu("New Terminal")

        default_action = self._new_terminal_menu.addAction(
            "Default Shell\tCtrl+Shift+T"
        )
        default_action.triggered.connect(lambda: self._tabs.new_tab())

        shells = known_shells()
        if shells:
            self._new_terminal_menu.addSeparator()
        for label, path in shells:
            action = self._new_terminal_menu.addAction(label)
            action.triggered.connect(
                lambda checked=False, p=path: self._tabs.new_tab(shell=p)
            )

        self._file_menu.addSeparator()
        preferences_action = self._file_menu.addAction("Preferences...")
        preferences_action.triggered.connect(self.show_preferences)

        self._file_menu.addSeparator()
        exit_action = self._file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def show_preferences(self) -> None:
        PreferencesDialog(self._appearance_store, self).exec()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._save_window_state()
        self._tabs.close_all_tabs()
        super().closeEvent(event)
