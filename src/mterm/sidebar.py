from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from mterm.presets import Preset, PresetStore


class CommandSidebar(QWidget):
    """Quick-access buttons for Command-category presets, grouped by `group`.

    Always sends to the active terminal - see Preset.target docstring for why
    this only ever shows target: active presets (Commands), never Macros.

    Editing presets lives in the Commands menu ("Manage Presets...") instead
    of a button here - the sidebar is just the quick-access button list.
    """

    run_requested = Signal(list)

    def __init__(self, store: PresetStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._store.changed.connect(self.reload)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)

        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.addStretch(1)
        scroll.setWidget(self._container)
        layout.addWidget(scroll)

        self.reload()

    def reload(self) -> None:
        while self._container_layout.count() > 1:
            item = self._container_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        groups: dict[str | None, list[Preset]] = {}
        for preset in self._store.sidebar_presets():
            groups.setdefault(preset.group, []).append(preset)

        ordered_group_names = [name for name in groups if name is None] + sorted(
            name for name in groups if name is not None
        )
        for group_name in ordered_group_names:
            box = QGroupBox(group_name or "")
            box.setFlat(group_name is None)
            box_layout = QVBoxLayout(box)
            for preset in groups[group_name]:
                button = QPushButton(preset.name)
                button.setToolTip("\n".join(preset.lines))
                button.clicked.connect(
                    lambda _checked=False, p=preset: self.run_requested.emit(p.lines)
                )
                box_layout.addWidget(button)
            self._container_layout.insertWidget(self._container_layout.count() - 1, box)
