"""PreferencesDialog: editing theme/font/size and saving to AppearanceStore."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm.preferences_dialog import PreferencesDialog


def make_store(tmp_path: Path) -> AppearanceStore:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    return AppearanceStore(settings)


def test_dialog_preselects_current_appearance(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.save(Appearance(theme_name="Solarized Dark", font_family="Consolas", font_size=18))

    dialog = PreferencesDialog(store)
    qtbot.addWidget(dialog)

    assert dialog._theme_combo.currentText() == "Solarized Dark"
    assert dialog._size_spin.value() == 18


def test_ok_saves_selected_appearance_and_notifies(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PreferencesDialog(store)
    qtbot.addWidget(dialog)
    calls = []
    store.changed.connect(lambda: calls.append(True))

    dialog._theme_combo.setCurrentText("VS Code Dark High Contrast")
    dialog._font_combo.setCurrentFont(QFont("Cascadia Mono"))
    dialog._size_spin.setValue(20)
    dialog._save()

    assert store.current.theme_name == "VS Code Dark High Contrast"
    assert store.current.font_size == 20
    assert calls == [True]


def test_cancel_does_not_save(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    original = store.current
    dialog = PreferencesDialog(store)
    qtbot.addWidget(dialog)

    dialog._theme_combo.setCurrentText("Solarized Light")
    dialog.reject()

    assert store.current is original
