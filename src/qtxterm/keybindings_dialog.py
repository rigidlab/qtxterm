"""Editor for the keyboard shortcuts.

Its own dialog rather than another row in Preferences: there are two dozen
actions, and Preferences is already a long form.

The tree is two levels - an action, and under it each chord bound to it -
because several actions genuinely have more than one, and a flat "Ctrl+Shift+C,
Ctrl+Ins" cell gives nothing to click when you want to drop just one of them.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from qtxterm import shortcuts
from qtxterm.keybindings import ConflictError, KeybindingStore

# Which level of the tree an item sits at. Stored rather than inferred from
# parent(), so a chord row still knows its action after the tree is rebuilt.
_ACTION_ROLE = Qt.ItemDataRole.UserRole
_IS_CHORD_ROLE = Qt.ItemDataRole.UserRole + 1


class KeybindingsDialog(QDialog):
    """Rebind, add, remove and reset keyboard shortcuts."""

    def __init__(self, store: KeybindingStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self.setWindowTitle("Keyboard Shortcuts")
        self.resize(600, 560)

        layout = QVBoxLayout(self)

        self._tree = QTreeWidget()
        self._tree.setColumnCount(2)
        self._tree.setHeaderLabels(["Action", "Shortcut"])
        self._tree.setRootIsDecorated(True)
        self._tree.currentItemChanged.connect(lambda *_: self._refresh_buttons())
        layout.addWidget(self._tree, 1)

        hint = QLabel(
            "Pick an action, press the keys you want, then Add. "
            "Changed actions are shown in bold."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        entry = QHBoxLayout()
        self._capture = QKeySequenceEdit()
        # One chord, not a sequence of them: Qt will happily record up to four
        # in a row ("Ctrl+K, Ctrl+S") and nothing in this app dispatches those.
        self._capture.setMaximumSequenceLength(1)
        self._capture.keySequenceChanged.connect(lambda *_: self._refresh_buttons())
        entry.addWidget(self._capture, 1)

        self._add_button = QPushButton("Add")
        self._add_button.clicked.connect(self._add)
        entry.addWidget(self._add_button)

        self._remove_button = QPushButton("Remove")
        self._remove_button.clicked.connect(self._remove)
        entry.addWidget(self._remove_button)

        self._reset_button = QPushButton("Reset")
        self._reset_button.clicked.connect(self._reset)
        entry.addWidget(self._reset_button)
        layout.addLayout(entry)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        reset_all = buttons.addButton(
            "Reset All", QDialogButtonBox.ButtonRole.ResetRole
        )
        reset_all.clicked.connect(self._reset_all)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._reload()

    # -- building ---------------------------------------------------------

    def _reload(self) -> None:
        """Rebuild the tree, keeping the selected action where possible."""
        selected = self.current_action()
        self._tree.clear()
        for action in shortcuts.all_actions():
            chords = self._store.display_sequences_for(action)
            # The action's row carries all of its chords, so the list reads as
            # one line per action rather than two. The children exist only to
            # give a single chord something to click when removing one of
            # several, and stay collapsed until then.
            item = QTreeWidgetItem(
                [shortcuts.label_for(action), ", ".join(chords) or "None"]
            )
            item.setData(0, _ACTION_ROLE, action)
            item.setData(0, _IS_CHORD_ROLE, False)
            if self._store.is_customised(action):
                font = QFont(item.font(0))
                font.setBold(True)
                item.setFont(0, font)
            # One chord needs no expanding: Reset already covers it, and a
            # disclosure arrow that reveals a copy of the row above is noise.
            if len(chords) > 1:
                for shown in chords:
                    chord = QTreeWidgetItem(["", shown])
                    chord.setData(0, _ACTION_ROLE, action)
                    chord.setData(0, _IS_CHORD_ROLE, True)
                    item.addChild(chord)
            self._tree.addTopLevelItem(item)
            if action == selected:
                self._tree.setCurrentItem(item)
        self._tree.resizeColumnToContents(0)
        self._refresh_buttons()

    def current_action(self) -> str | None:
        item = self._tree.currentItem()
        return item.data(0, _ACTION_ROLE) if item is not None else None

    def _current_is_chord(self) -> bool:
        item = self._tree.currentItem()
        return bool(item is not None and item.data(0, _IS_CHORD_ROLE))

    def _refresh_buttons(self) -> None:
        action = self.current_action()
        self._add_button.setEnabled(
            action is not None and not self._capture.keySequence().isEmpty()
        )
        self._remove_button.setEnabled(
            self._current_is_chord()
            or bool(action and len(self._store.sequences_for(action)) == 1)
        )
        self._reset_button.setEnabled(
            action is not None and self._store.is_customised(action)
        )

    # -- editing ----------------------------------------------------------

    def _add(self) -> None:
        action = self.current_action()
        sequence = self._capture.keySequence()
        if action is None or sequence.isEmpty():
            return
        # PortableText, not the native rendering: the store speaks Qt's
        # spelling, and on macOS toString() would otherwise hand it the
        # Command symbol rather than "Ctrl".
        wanted = sequence.toString(QKeySequence.SequenceFormat.PortableText)
        self._apply(action, [*self._store.sequences_for(action), wanted])

    def _remove(self) -> None:
        """Drop one chord: the selected one, or the only one there is."""
        item = self._tree.currentItem()
        if item is None:
            return
        action = item.data(0, _ACTION_ROLE)
        if not item.data(0, _IS_CHORD_ROLE):
            # An action row with a single chord has no children to select,
            # so Remove acts on that chord directly.
            chords = self._store.display_sequences_for(action)
            if len(chords) != 1:
                return
            shown = chords[0]
        else:
            shown = item.text(1)
        remaining = [
            sequence
            for sequence in self._store.sequences_for(action)
            if shortcuts.display_sequence(sequence) != shown
        ]
        self._apply(action, remaining)

    def _reset(self) -> None:
        action = self.current_action()
        if action is not None:
            self._store.reset(action)
            self._reload()

    def _reset_all(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Reset all shortcuts",
            "Put every shortcut back to its default?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if confirmed == QMessageBox.StandardButton.Yes:
            self._store.reset_all()
            self._reload()

    def _apply(self, action: str, sequences: list[str]) -> None:
        try:
            self._store.set_sequences(action, sequences)
        except ConflictError as clash:
            # Named rather than silently overridden, because Qt fires neither
            # of two shortcuts sharing a chord - so "it just stopped working"
            # would be the alternative, for both actions.
            QMessageBox.warning(self, "Shortcut already in use", str(clash))
            return
        except ValueError as invalid:
            QMessageBox.warning(self, "Not a shortcut", str(invalid))
            return
        self._capture.clear()
        self._reload()
