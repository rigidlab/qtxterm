from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDockWidget, QMainWindow

from qtxterm.preset_menu import CommandsMenu, MacrosMenu
from qtxterm.presets import PresetStore
from qtxterm.shells import known_shells
from qtxterm.sidebar import CommandSidebar
from qtxterm.terminal_tabs import TerminalTabWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("qtxterm")
        self.resize(1000, 650)

        self._tabs = TerminalTabWidget(parent=self)
        self._tabs.all_tabs_closed.connect(self.close)
        self.setCentralWidget(self._tabs)

        self._preset_store = PresetStore()
        self._sidebar = CommandSidebar(self._preset_store, parent=self)
        self._sidebar.run_requested.connect(self._tabs.run_in_active)
        self._sidebar_dock = QDockWidget("Commands", self)
        self._sidebar_dock.setWidget(self._sidebar)
        # No close ("x") button on the dock itself - visibility is only
        # toggled via the Commands menu's "Show Sidebar" action below, not by
        # the user accidentally closing the dock with no way back.
        self._sidebar_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable
            | QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._sidebar_dock)

        self._build_file_menu()

        # Not sidebar_dock.toggleViewAction(): Qt ties that action's enabled
        # state to the DockWidgetClosable feature (toggling visibility is
        # treated as a form of "closing"), so it'd be silently inert once we
        # removed Closable above. An independent action wired both ways
        # (toggled -> setVisible, visibilityChanged -> setChecked) avoids
        # that coupling entirely.
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

        self._tabs.new_tab()

    def _build_file_menu(self) -> None:
        # QMenu.addMenu() parents the submenu in C++, but without a Python-side
        # reference kept alive too, PySide6 can garbage-collect the wrapper (and
        # the underlying object with it) - store both on self to keep them alive
        # for the window's lifetime.
        self._file_menu = self.menuBar().addMenu("&File")
        self._new_terminal_menu = self._file_menu.addMenu("New Terminal")

        default_action = self._new_terminal_menu.addAction("Default Shell\tCtrl+Shift+T")
        default_action.triggered.connect(lambda: self._tabs.new_tab())

        shells = known_shells()
        if shells:
            self._new_terminal_menu.addSeparator()
        for label, path in shells:
            action = self._new_terminal_menu.addAction(label)
            action.triggered.connect(lambda checked=False, p=path: self._tabs.new_tab(shell=p))

        self._file_menu.addSeparator()
        exit_action = self._file_menu.addAction("Exit")
        exit_action.triggered.connect(self.close)

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._tabs.close_all_tabs()
        super().closeEvent(event)
