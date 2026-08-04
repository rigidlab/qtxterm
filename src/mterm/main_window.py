from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDockWidget, QMainWindow

from mterm.presets import PresetStore
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

        self._tabs.new_tab()

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._tabs.close_all_tabs()
        super().closeEvent(event)
