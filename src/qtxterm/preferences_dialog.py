from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtxterm.appearance import (
    MAX_SCROLLBACK,
    MIN_SCROLLBACK,
    Appearance,
    AppearanceStore,
)
from qtxterm.menu_prefs import SECTION_LABELS, ContextMenuOrderStore
from qtxterm.shell_prefs import (
    SYSTEM_DEFAULT,
    ShellPreferenceStore,
    system_default_label,
)
from qtxterm.shells import known_shells
from qtxterm.themes import THEMES

# Frame plus the viewport's own padding, so the last row is never clipped
# into a scrollbar.
_LIST_FRAME_ALLOWANCE = 8


class PreferencesDialog(QDialog):
    """Terminal preferences: default shell, color theme, font, font size,
    scrollback, and the order of the terminal right-click menu's submenus.

    Saving applies immediately to every open tab (AppearanceStore.changed)
    and persists for the next launch. The default shell only affects tabs
    opened afterwards - existing ones keep the shell they spawned with.
    """

    def __init__(
        self,
        store: AppearanceStore,
        parent: QWidget | None = None,
        shell_store: ShellPreferenceStore | None = None,
        order_store: ContextMenuOrderStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        # Wide enough that the longest theme name ("VS Code Dark High
        # Contrast") and typical font names aren't elided in their combos.
        self.setMinimumWidth(360)
        self._store = store
        self._shell_store = shell_store
        self._order_store = order_store

        layout = QVBoxLayout(self)
        form = QFormLayout()

        if shell_store is not None:
            self._shell_combo = QComboBox()
            # Data, not text: WSL entries carry an argv list, and the label
            # is what gets persisted.
            self._shell_combo.addItem(system_default_label(), SYSTEM_DEFAULT)
            for label, _command in known_shells():
                self._shell_combo.addItem(label, label)
            index = self._shell_combo.findData(shell_store.label)
            self._shell_combo.setCurrentIndex(max(index, 0))
            form.addRow("Default shell", self._shell_combo)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(list(THEMES))
        self._theme_combo.setCurrentText(store.current.theme_name)
        form.addRow("Color theme", self._theme_combo)

        self._font_combo = QFontComboBox()
        self._font_combo.setFontFilters(QFontComboBox.FontFilter.MonospacedFonts)
        self._font_combo.setCurrentFont(QFont(store.current.font_family))
        form.addRow("Font", self._font_combo)

        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 72)
        self._size_spin.setValue(store.current.font_size)
        form.addRow("Font size", self._size_spin)

        self._scrollback_spin = QSpinBox()
        self._scrollback_spin.setRange(MIN_SCROLLBACK, MAX_SCROLLBACK)
        self._scrollback_spin.setSingleStep(500)
        self._scrollback_spin.setGroupSeparatorShown(True)
        self._scrollback_spin.setValue(store.current.scrollback)
        self._scrollback_spin.setSpecialValueText("None (screen only)")
        self._scrollback_spin.setToolTip(
            "Lines kept above the screen, per terminal. Every line is memory "
            "a terminal left open for days never gives back."
        )
        form.addRow("Scrollback lines", self._scrollback_spin)

        if order_store is not None:
            form.addRow("Right-click menu", self._build_order_editor())

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_order_editor(self) -> QWidget:
        """A short list of the right-click menu's submenus, with Up/Down.

        Drag-and-drop reordering is tempting for three rows, but it is
        undiscoverable and fiddly at this size; buttons say what they do.
        Copy/Paste isn't listed because it stays pinned at the top - see
        menu_prefs.DEFAULT_ORDER.
        """
        self._order_list = QListWidget()
        for section in self._order_store.order:
            item = QListWidgetItem(SECTION_LABELS[section])
            item.setData(Qt.ItemDataRole.UserRole, section)
            self._order_list.addItem(item)
        self._order_list.setCurrentRow(0)
        # Just tall enough for every row, so the list never scrolls and the
        # dialog doesn't grow a second scrolling area inside a form.
        row_height = self._order_list.sizeHintForRow(0)
        self._order_list.setFixedHeight(
            row_height * self._order_list.count() + _LIST_FRAME_ALLOWANCE
        )

        up = QPushButton("Move Up")
        up.clicked.connect(lambda: self._move_section(-1))
        down = QPushButton("Move Down")
        down.clicked.connect(lambda: self._move_section(1))

        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self._order_list, 1)
        column = QVBoxLayout()
        column.addWidget(up)
        column.addWidget(down)
        column.addStretch()
        row.addLayout(column)
        return container

    def _move_section(self, offset: int) -> None:
        row = self._order_list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self._order_list.count():
            return
        item = self._order_list.takeItem(row)
        self._order_list.insertItem(target, item)
        # Keep the selection on the row that moved, so pressing Move Up twice
        # moves one entry two places rather than moving two entries.
        self._order_list.setCurrentRow(target)

    def _section_order(self) -> list[str]:
        return [
            self._order_list.item(row).data(Qt.ItemDataRole.UserRole)
            for row in range(self._order_list.count())
        ]

    def _save(self) -> None:
        if self._order_store is not None:
            self._order_store.save(self._section_order())
        if self._shell_store is not None:
            self._shell_store.save(self._shell_combo.currentData())
        self._store.save(
            Appearance(
                theme_name=self._theme_combo.currentText(),
                font_family=self._font_combo.currentFont().family(),
                font_size=self._size_spin.value(),
                scrollback=self._scrollback_spin.value(),
            )
        )
        self.accept()
