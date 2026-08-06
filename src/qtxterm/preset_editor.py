from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtxterm.presets import Preset, PresetStore

_CATEGORY_TITLES = {
    "active": "Manage Commands",
    "new_tab": "Manage Macros",
}
_NEW_NAMES = {
    "active": "New Command",
    "new_tab": "New Macro",
}


class PresetEditorDialog(QDialog):
    """Add/edit/delete presets for a single category (Commands or Macros).

    Scoped to `target` - opened from the Commands menu it only lists/creates
    Commands, opened from the Macros menu only Macros. There is no way to
    change a preset's category from here, so it can't be used to sneak a
    Command into the Macros menu or vice versa.
    """

    def __init__(
        self,
        store: PresetStore,
        parent: QWidget | None = None,
        target: str = "active",
        create_new: bool = False,
    ) -> None:
        super().__init__(parent)
        self._target = target
        self.setWindowTitle(_CATEGORY_TITLES[target])
        self.resize(560, 380)
        self._store = store
        self._current_index: int | None = None
        self._is_command = target == "active"

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self._list)
        button_row = QHBoxLayout()
        new_button = QPushButton("New")
        new_button.clicked.connect(self._new_preset)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_preset)
        button_row.addWidget(new_button)
        button_row.addWidget(delete_button)
        left.addLayout(button_row)
        layout.addLayout(left, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name_edit = QLineEdit()
        self._group_edit = QLineEdit()
        self._lines_edit = QPlainTextEdit()
        self._sidebar_check = QCheckBox("Show in sidebar")
        form.addRow("Name", self._name_edit)
        form.addRow("Group", self._group_edit)
        form.addRow("Commands (one per line)", self._lines_edit)
        # Macros never show in the sidebar - see Preset.target docstring.
        if self._is_command:
            form.addRow("", self._sidebar_check)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_current)
        form.addRow(save_button)
        layout.addWidget(form_widget, 2)

        self._reload_list()
        if create_new:
            self._new_preset()

    def _indexed_presets(self) -> list[tuple[int, Preset]]:
        return [
            (i, preset)
            for i, preset in enumerate(self._store.presets)
            if preset.target == self._target
        ]

    def _reload_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for _store_index, preset in self._indexed_presets():
            self._list.addItem(preset.name)
        self._list.blockSignals(False)

    def _store_index_for_row(self, row: int) -> int | None:
        indexed = self._indexed_presets()
        if row < 0 or row >= len(indexed):
            return None
        return indexed[row][0]

    def _on_row_changed(self, row: int) -> None:
        self._current_index = self._store_index_for_row(row)
        if self._current_index is None:
            self._name_edit.clear()
            self._group_edit.clear()
            self._lines_edit.clear()
            self._sidebar_check.setChecked(False)
            return
        preset = self._store.presets[self._current_index]
        self._name_edit.setText(preset.name)
        self._group_edit.setText(preset.group or "")
        self._lines_edit.setPlainText("\n".join(preset.lines))
        self._sidebar_check.setChecked(preset.show_in_sidebar)

    def _new_preset(self) -> None:
        if self._target == "new_tab":
            preset = Preset(
                name=_NEW_NAMES["new_tab"],
                lines=["echo step one", "echo step two"],
                target="new_tab",
            )
        else:
            preset = Preset(
                name=_NEW_NAMES["active"], lines=["echo hello"], target="active"
            )
        self._store.add(preset)
        self._reload_list()
        self._list.setCurrentRow(len(self._indexed_presets()) - 1)

    def _delete_preset(self) -> None:
        if self._current_index is None:
            return
        self._store.delete(self._current_index)
        self._current_index = None
        self._reload_list()

    def _save_current(self) -> None:
        if self._current_index is None:
            return
        lines = [
            line for line in self._lines_edit.toPlainText().splitlines() if line.strip()
        ] or ["echo"]
        show_in_sidebar = self._is_command and self._sidebar_check.isChecked()
        preset = Preset(
            name=self._name_edit.text().strip() or "Unnamed",
            group=self._group_edit.text().strip() or None,
            lines=lines,
            target=self._target,
            show_in_sidebar=show_in_sidebar,
        )
        self._store.update(self._current_index, preset)
        saved_index = self._current_index
        self._reload_list()
        row = next(
            row
            for row, (store_index, _preset) in enumerate(self._indexed_presets())
            if store_index == saved_index
        )
        self._list.setCurrentRow(row)
