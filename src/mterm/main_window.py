from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow

from mterm.macros_menu import MacrosMenu
from mterm.presets import PresetStore
from mterm.shells import known_shells
from mterm.sidebar import CommandSidebar
from mterm.terminal_tabs import TerminalTabWidget


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("mterm")
        self.resize(1000, 650)

        self._tabs = TerminalTabWidget(parent=self)
        self._tabs.all_tabs_closed.connect(self.close)
        self.setCentralWidget(self._tabs)

        self._preset_store = PresetStore()
        self._sidebar = CommandSidebar(self._preset_store, parent=self)
        self._sidebar.run_requested.connect(self._tabs.run_in_active)
        sidebar_dock = QDockWidget("Commands", self)
        sidebar_dock.setWidget(self._sidebar)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, sidebar_dock)

        self._build_file_menu()

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
