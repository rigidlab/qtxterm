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
from qtxterm.themes import THEMES


class PreferencesDialog(QDialog):
    """Terminal appearance preferences: color theme, font, font size.

    Saving applies immediately to every open tab (AppearanceStore.changed)
    and persists for the next launch.
    """

    def __init__(self, store: AppearanceStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Preferences")
        # Wide enough that the longest theme name ("VS Code Dark High
        # Contrast") and typical font names aren't elided in their combos.
        self.setMinimumWidth(360)
        self._store = store

        layout = QVBoxLayout(self)
        form = QFormLayout()

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
        self._store.save(
            Appearance(
                theme_name=self._theme_combo.currentText(),
                font_family=self._font_combo.currentFont().family(),
                font_size=self._size_spin.value(),
            )
        )
        self.accept()
