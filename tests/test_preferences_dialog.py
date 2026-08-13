"""PreferencesDialog: editing theme/font/size and saving to AppearanceStore."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QFont

from qtxterm.appearance import Appearance, AppearanceStore
from qtxterm.menu_prefs import (
    DEFAULT_ORDER,
    SECTION_CLIPBOARD,
    SECTION_COMMAND,
    SECTION_PANE,
    SECTION_SELECTION,
    ContextMenuOrderStore,
)
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


def make_order_store(tmp_path: Path) -> ContextMenuOrderStore:
    settings = QSettings(str(tmp_path / "menu.ini"), QSettings.Format.IniFormat)
    return ContextMenuOrderStore(settings)


def test_order_editor_lists_the_current_order(qtbot, tmp_path: Path) -> None:
    order_store = make_order_store(tmp_path)
    order_store.save(
        [SECTION_COMMAND, SECTION_PANE, SECTION_SELECTION, SECTION_CLIPBOARD]
    )

    dialog = PreferencesDialog(make_store(tmp_path), order_store=order_store)
    qtbot.addWidget(dialog)

    assert dialog._section_order() == [
        SECTION_COMMAND,
        SECTION_PANE,
        SECTION_SELECTION,
        SECTION_CLIPBOARD,
    ]


def test_moving_a_section_up_and_saving_persists_it(qtbot, tmp_path: Path) -> None:
    order_store = make_order_store(tmp_path)
    dialog = PreferencesDialog(make_store(tmp_path), order_store=order_store)
    qtbot.addWidget(dialog)

    dialog._order_list.setCurrentRow(1)  # Pane
    dialog._move_section(-1)
    dialog._save()

    assert order_store.order == [
        SECTION_PANE,
        SECTION_CLIPBOARD,
        SECTION_COMMAND,
        SECTION_SELECTION,
    ]


def test_the_moved_row_keeps_the_selection(qtbot, tmp_path: Path) -> None:
    """Otherwise pressing Move Up twice walks two different entries up one
    place each, instead of moving one entry two places."""
    order_store = make_order_store(tmp_path)
    dialog = PreferencesDialog(make_store(tmp_path), order_store=order_store)
    qtbot.addWidget(dialog)

    dialog._order_list.setCurrentRow(3)  # Selection
    dialog._move_section(-1)
    dialog._move_section(-1)
    dialog._move_section(-1)

    assert dialog._section_order()[0] == SECTION_SELECTION


def test_moving_past_either_end_does_nothing(qtbot, tmp_path: Path) -> None:
    order_store = make_order_store(tmp_path)
    dialog = PreferencesDialog(make_store(tmp_path), order_store=order_store)
    qtbot.addWidget(dialog)
    before = dialog._section_order()

    dialog._order_list.setCurrentRow(0)
    dialog._move_section(-1)
    dialog._order_list.setCurrentRow(dialog._order_list.count() - 1)
    dialog._move_section(1)

    assert dialog._section_order() == before


def test_cancel_leaves_the_saved_order_alone(qtbot, tmp_path: Path) -> None:
    order_store = make_order_store(tmp_path)
    dialog = PreferencesDialog(make_store(tmp_path), order_store=order_store)
    qtbot.addWidget(dialog)

    dialog._order_list.setCurrentRow(2)
    dialog._move_section(-1)
    dialog.reject()

    assert order_store.order == DEFAULT_ORDER
