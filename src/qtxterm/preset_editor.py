from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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

_TARGET_LABELS = {
    "active": "Command (send to active terminal)",
    "new_tab": "Macro (open new tab and run as script)",
}


class PresetEditorDialog(QDialog):
    """Add/edit/delete presets - both Commands and Macros share this dialog.

    Changes are saved to disk immediately (via PresetStore), which also
    notifies the sidebar and Macros menu to refresh themselves.
    """

    def __init__(
        self,
        store: PresetStore,
        parent: QWidget | None = None,
        new_preset_target: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Manage Presets")
        self.resize(560, 380)
        self._store = store
        self._current_index: int | None = None

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self._list)
        button_row = QHBoxLayout()
        new_button = QPushButton("New")
        new_button.clicked.connect(lambda: self._new_preset())
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
        self._target_combo = QComboBox()
        for target, label in _TARGET_LABELS.items():
            self._target_combo.addItem(label, target)
        self._target_combo.currentIndexChanged.connect(self._on_target_changed)
        self._sidebar_check = QCheckBox("Show in sidebar")
        form.addRow("Name", self._name_edit)
        form.addRow("Group", self._group_edit)
        form.addRow("Type", self._target_combo)
        form.addRow("Commands (one per line)", self._lines_edit)
        form.addRow("", self._sidebar_check)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_current)
        form.addRow(save_button)
        layout.addWidget(form_widget, 2)

        self._reload_list()
        if new_preset_target is not None:
            self._new_preset(target=new_preset_target)

    def _reload_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for preset in self._store.presets:
            kind = "Macro" if preset.target == "new_tab" else "Command"
            self._list.addItem(f"{preset.name}  ({kind})")
        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        self._current_index = row if row >= 0 else None
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
        index = self._target_combo.findData(preset.target)
        self._target_combo.setCurrentIndex(max(index, 0))
        self._sidebar_check.setChecked(preset.show_in_sidebar)

    def _on_target_changed(self, _index: int) -> None:
        is_command = self._target_combo.currentData() == "active"
        self._sidebar_check.setEnabled(is_command)
        if not is_command:
            self._sidebar_check.setChecked(False)

    def _new_preset(self, target: str = "active") -> None:
        if target == "new_tab":
            preset = Preset(
                name="New Macro",
                lines=["echo step one", "echo step two"],
                target="new_tab",
            )
        else:
            preset = Preset(name="New Command", lines=["echo hello"], target="active")
        self._store.add(preset)
        self._reload_list()
        self._list.setCurrentRow(len(self._store.presets) - 1)

    def _delete_preset(self) -> None:
        if self._current_index is None:
            return
        self._store.delete(self._current_index)
        self._current_index = None
        self._reload_list()

    def _save_current(self) -> None:
        if self._current_index is None:
            return
        lines = [line for line in self._lines_edit.toPlainText().splitlines() if line.strip()] or [
            "echo"
        ]
        target = self._target_combo.currentData()
        # Macros never show in the sidebar - see Preset.target docstring.
        show_in_sidebar = self._sidebar_check.isChecked() and target == "active"
        preset = Preset(
            name=self._name_edit.text().strip() or "Unnamed",
            group=self._group_edit.text().strip() or None,
            lines=lines,
            target=target,
            show_in_sidebar=show_in_sidebar,
        )
        self._store.update(self._current_index, preset)
        self._reload_list()
        self._list.setCurrentRow(self._current_index)
