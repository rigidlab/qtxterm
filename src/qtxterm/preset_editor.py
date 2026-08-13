from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtxterm.presets import (
    CATEGORY_COMMANDS,
    CATEGORY_MACROS,
    CATEGORY_SELECTION,
    INPUT_NONE,
    INPUT_SELECTION,
    KIND_SHELL,
    KIND_STDIN,
    KIND_URL,
    SELECTION_PLACEHOLDER,
    Preset,
    PresetStore,
    category_of,
    default_selection_actions,
)

_CATEGORY_TITLES = {
    CATEGORY_COMMANDS: "Manage Commands",
    CATEGORY_MACROS: "Manage Macros",
    CATEGORY_SELECTION: "Manage Selection Actions",
}


def editor_title(category: str) -> str:
    """The dialog's window title, also used for the menu item that opens it."""
    return _CATEGORY_TITLES[category]


_NEW_NAMES = {
    CATEGORY_COMMANDS: "New Command",
    CATEGORY_MACROS: "New Macro",
    CATEGORY_SELECTION: "New Selection Action",
}
_LINES_LABELS = {
    CATEGORY_COMMANDS: "Commands (one per line)",
    CATEGORY_MACROS: "Commands (one per line)",
    CATEGORY_SELECTION: "Command / URL",
}
_KIND_CHOICES = [
    ("Open a URL in the browser", KIND_URL),
    ("Send to a command's input", KIND_STDIN),
]
_TARGET_CHOICES = [
    ("New tab", "new_tab"),
    ("Active terminal", "active"),
]
_KIND_HINTS = {
    KIND_URL: (
        f"URL template. {SELECTION_PLACEHOLDER} is replaced with the selected "
        "text, percent-encoded."
    ),
    KIND_STDIN: (
        "Shell command. The selected text is written to a temp file and fed "
        "to the last line on standard input."
    ),
}


class PresetEditorDialog(QDialog):
    """Add/edit/delete presets for a single category.

    Scoped to `category` - opened from the Commands menu it only
    lists/creates Commands, from the Macros menu only Macros, from the
    Selection menu only Selection Actions. There is no way to change a
    preset's category from here, so it can't be used to sneak one category's
    preset into another's menu.
    """

    def __init__(
        self,
        store: PresetStore,
        parent: QWidget | None = None,
        category: str = CATEGORY_COMMANDS,
        create_new: bool = False,
    ) -> None:
        super().__init__(parent)
        self._category = category
        self.setWindowTitle(editor_title(category))
        self.resize(620, 420)
        self._store = store
        self._current_index: int | None = None
        self._is_command = category == CATEGORY_COMMANDS
        self._is_selection = category == CATEGORY_SELECTION

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
        if self._is_selection:
            # Defaults are only seeded on first run, so an install that
            # predates Selection Actions has no other way to get the worked
            # examples without hand-editing presets.json.
            restore_button = QPushButton("Add Examples")
            restore_button.setToolTip(
                "Add the built-in example Selection Actions that aren't already here"
            )
            restore_button.clicked.connect(self._add_examples)
            left.addWidget(restore_button)
        layout.addLayout(left, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name_edit = QLineEdit()
        self._group_edit = QLineEdit()
        self._lines_edit = QPlainTextEdit()
        self._sidebar_check = QCheckBox("Show in sidebar")
        self._kind_combo = QComboBox()
        self._target_combo = QComboBox()
        self._hint_label = QLabel()
        self._hint_label.setWordWrap(True)

        form.addRow("Name", self._name_edit)
        form.addRow("Group", self._group_edit)
        if self._is_selection:
            for label, value in _KIND_CHOICES:
                self._kind_combo.addItem(label, value)
            self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
            for label, value in _TARGET_CHOICES:
                self._target_combo.addItem(label, value)
            form.addRow("Does", self._kind_combo)
            self._target_row_label = QLabel("Runs in")
            form.addRow(self._target_row_label, self._target_combo)
        form.addRow(_LINES_LABELS[category], self._lines_edit)
        if self._is_selection:
            form.addRow("", self._hint_label)
        # Macros never show in the sidebar - see Preset.target docstring.
        if self._is_command:
            form.addRow("", self._sidebar_check)
        # Save keeps the dialog open for the next edit; Save and Close is the
        # one-edit-and-done case, which is most of them.
        self._save_button = QPushButton("Save")
        self._save_button.clicked.connect(self._save_current)
        self._save_and_close_button = QPushButton("Save and Close")
        self._save_and_close_button.clicked.connect(self._save_and_close)
        buttons = QHBoxLayout()
        buttons.addWidget(self._save_button)
        buttons.addWidget(self._save_and_close_button)
        form.addRow(buttons)
        layout.addWidget(form_widget, 2)

        if self._is_selection:
            self._on_kind_changed()
        self._reload_list()
        if create_new:
            self._new_preset()

    def _selected_kind(self) -> str:
        return self._kind_combo.currentData() or KIND_URL

    def _on_kind_changed(self) -> None:
        """A url action opens a browser, so 'which terminal' doesn't apply."""
        kind = self._selected_kind()
        self._hint_label.setText(_KIND_HINTS[kind])
        is_stdin = kind == KIND_STDIN
        self._target_combo.setVisible(is_stdin)
        self._target_row_label.setVisible(is_stdin)

    def _indexed_presets(self) -> list[tuple[int, Preset]]:
        # Compared by category rather than membership in a filtered list:
        # Preset is a plain dataclass, so two identical presets are equal and
        # `in` would match the wrong one.
        return [
            (i, preset)
            for i, preset in enumerate(self._store.presets)
            if category_of(preset) == self._category
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
        if self._is_selection:
            self._select_data(self._kind_combo, preset.kind)
            self._select_data(self._target_combo, preset.target)
            self._on_kind_changed()

    @staticmethod
    def _select_data(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index >= 0:
            combo.setCurrentIndex(index)

    def _new_preset(self) -> None:
        if self._category == CATEGORY_SELECTION:
            preset = Preset(
                name=_NEW_NAMES[CATEGORY_SELECTION],
                lines=[f"https://www.google.com/search?q={SELECTION_PLACEHOLDER}"],
                input=INPUT_SELECTION,
                kind=KIND_URL,
            )
        elif self._category == CATEGORY_MACROS:
            preset = Preset(
                name=_NEW_NAMES[CATEGORY_MACROS],
                lines=["echo step one", "echo step two"],
                target="new_tab",
            )
        else:
            preset = Preset(
                name=_NEW_NAMES[CATEGORY_COMMANDS],
                lines=["echo hello"],
                target="active",
            )
        self._store.add(preset)
        self._reload_list()
        self._list.setCurrentRow(len(self._indexed_presets()) - 1)

    def _add_examples(self) -> None:
        """Add built-in examples whose names aren't taken, skipping the rest.

        Matched by name so pressing it twice doesn't duplicate, and so an
        example you've edited is left alone.
        """
        existing = {p.name for p in self._store.presets}
        for preset in default_selection_actions():
            if preset.name not in existing:
                self._store.add(preset)
        self._reload_list()

    def _delete_preset(self) -> None:
        if self._current_index is None:
            return
        self._store.delete(self._current_index)
        self._current_index = None
        self._reload_list()

    def _save_and_close(self) -> None:
        """Save whatever is being edited, then leave.

        Closes even with nothing selected - the button says what it does, and
        refusing to close because there was nothing to save would be a worse
        surprise than closing.
        """
        self._save_current()
        self.accept()

    def _save_current(self) -> None:
        if self._current_index is None:
            return
        lines = [
            line for line in self._lines_edit.toPlainText().splitlines() if line.strip()
        ] or ["echo"]
        show_in_sidebar = self._is_command and self._sidebar_check.isChecked()
        if self._is_selection:
            kind = self._selected_kind()
            preset = Preset(
                name=self._name_edit.text().strip() or "Unnamed",
                group=self._group_edit.text().strip() or None,
                lines=lines,
                input=INPUT_SELECTION,
                kind=kind,
                # A url action never reaches a terminal; pin it to new_tab so
                # the stored value is at least meaningless-but-consistent.
                target="new_tab"
                if kind == KIND_URL
                else (self._target_combo.currentData() or "new_tab"),
            )
        else:
            preset = Preset(
                name=self._name_edit.text().strip() or "Unnamed",
                group=self._group_edit.text().strip() or None,
                lines=lines,
                target="active" if self._is_command else "new_tab",
                show_in_sidebar=show_in_sidebar,
                input=INPUT_NONE,
                kind=KIND_SHELL,
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
