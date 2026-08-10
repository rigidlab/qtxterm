from __future__ import annotations

from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFontComboBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm.shell_prefs import (
    SYSTEM_DEFAULT,
    ShellPreferenceStore,
    system_default_label,
)
from qtxterm.shells import known_shells
from qtxterm.themes import THEMES


class PreferencesDialog(QDialog):
    """Terminal preferences: default shell, color theme, font, font size.

    Saving applies immediately to every open tab (AppearanceStore.changed)
    and persists for the next launch. The default shell only affects tabs
    opened afterwards - existing ones keep the shell they spawned with.
    """

    def __init__(
        self,
        store: AppearanceStore,
        parent: QWidget | None = None,
        shell_store: ShellPreferenceStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        # Wide enough that the longest theme name ("VS Code Dark High
        # Contrast") and typical font names aren't elided in their combos.
        self.setMinimumWidth(360)
        self._store = store
        self._shell_store = shell_store

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

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _save(self) -> None:
        if self._shell_store is not None:
            self._shell_store.save(self._shell_combo.currentData())
        self._store.save(
            Appearance(
                theme_name=self._theme_combo.currentText(),
                font_family=self._font_combo.currentFont().family(),
                font_size=self._size_spin.value(),
            )
        )
        self.accept()
