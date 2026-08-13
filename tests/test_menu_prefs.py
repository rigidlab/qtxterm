"""ContextMenuOrderStore: the right-click menu's submenu order, persisted."""

from __future__ import annotations

from PySide6.QtCore import QSettings

from qtxterm.menu_prefs import (
    DEFAULT_ORDER,
    SECTION_CLIPBOARD,
    SECTION_COMMAND,
    SECTION_PANE,
    SECTION_SELECTION,
    ContextMenuOrderStore,
    normalise_order,
)


def make_settings(tmp_path) -> QSettings:
    return QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)


def test_defaults_to_copy_paste_then_pane_command_selection(tmp_path) -> None:
    assert ContextMenuOrderStore(make_settings(tmp_path)).order == [
        SECTION_CLIPBOARD,
        SECTION_PANE,
        SECTION_COMMAND,
        SECTION_SELECTION,
    ]
    assert DEFAULT_ORDER[0] == SECTION_CLIPBOARD


def test_saved_order_survives_a_restart(tmp_path) -> None:
    store = ContextMenuOrderStore(make_settings(tmp_path))
    store.save([SECTION_COMMAND, SECTION_SELECTION, SECTION_PANE, SECTION_CLIPBOARD])

    reopened = ContextMenuOrderStore(make_settings(tmp_path))

    assert reopened.order == [
        SECTION_COMMAND,
        SECTION_SELECTION,
        SECTION_PANE,
        SECTION_CLIPBOARD,
    ]


def test_saving_emits_changed(qtbot, tmp_path) -> None:
    store = ContextMenuOrderStore(make_settings(tmp_path))

    with qtbot.waitSignal(store.changed):
        store.save([SECTION_COMMAND, SECTION_PANE, SECTION_SELECTION])


def test_a_missing_section_is_appended_rather_than_dropped() -> None:
    """A settings file written before a section existed must not make that
    submenu vanish."""
    assert normalise_order([SECTION_COMMAND]) == [
        SECTION_COMMAND,
        SECTION_CLIPBOARD,
        SECTION_PANE,
        SECTION_SELECTION,
    ]


def test_unknown_and_duplicate_sections_are_discarded() -> None:
    assert normalise_order(["", "nonsense", SECTION_COMMAND, SECTION_COMMAND]) == [
        SECTION_COMMAND,
        SECTION_CLIPBOARD,
        SECTION_PANE,
        SECTION_SELECTION,
    ]
