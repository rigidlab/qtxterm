"""Closing a pane when its shell exits."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings

from qtxterm.exit_prefs import (
    CLOSE_ALWAYS,
    CLOSE_CLEAN,
    CLOSE_NEVER,
    DEFAULT,
    PaneExitStore,
    should_close,
)


def make_store(tmp_path) -> PaneExitStore:
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    return PaneExitStore(settings)


def test_clean_closes_only_on_a_zero_exit_code() -> None:
    """The whole reason this is three settings and not a checkbox: a shell
    that died has usually printed why, and closing the pane throws that away
    exactly when you needed to read it."""
    assert should_close(CLOSE_CLEAN, 0) is True
    assert should_close(CLOSE_CLEAN, 1) is False
    assert should_close(CLOSE_CLEAN, 130) is False


def test_always_closes_whatever_happened() -> None:
    assert should_close(CLOSE_ALWAYS, 0) is True
    assert should_close(CLOSE_ALWAYS, 1) is True


def test_never_keeps_the_pane() -> None:
    """What qtxterm did before this existed."""
    assert should_close(CLOSE_NEVER, 0) is False
    assert should_close(CLOSE_NEVER, 1) is False


def test_the_default_keeps_a_failed_shell_on_screen() -> None:
    assert DEFAULT == CLOSE_CLEAN


def test_the_choice_round_trips(tmp_path) -> None:
    store = make_store(tmp_path)
    assert store.current == DEFAULT

    store.save(CLOSE_ALWAYS)

    assert make_store(tmp_path).current == CLOSE_ALWAYS


def test_saving_emits_changed(tmp_path, qtbot) -> None:
    store = make_store(tmp_path)

    with qtbot.waitSignal(store.changed, timeout=1000):
        store.save(CLOSE_NEVER)


def test_an_unknown_stored_value_falls_back_rather_than_raising(tmp_path) -> None:
    """The ini is hand-editable, and a typo should not stop the app starting."""
    settings = QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    settings.setValue("session/closeOnExit", "sometimes")

    assert PaneExitStore(settings).current == DEFAULT


def test_saving_an_unknown_choice_is_refused(tmp_path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(ValueError):
        store.save("sometimes")
