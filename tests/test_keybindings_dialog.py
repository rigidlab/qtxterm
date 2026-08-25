"""The keyboard shortcuts editor."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMessageBox

from qtxterm import shortcuts
from qtxterm.keybindings import KeybindingStore
from qtxterm.keybindings_dialog import KeybindingsDialog


@pytest.fixture
def store(tmp_path) -> KeybindingStore:
    return KeybindingStore(path=tmp_path / "keybindings.json")


@pytest.fixture
def dialog(qtbot, store) -> KeybindingsDialog:
    widget = KeybindingsDialog(store)
    qtbot.addWidget(widget)
    return widget


def select_action(dialog: KeybindingsDialog, action: str) -> None:
    from qtxterm.keybindings_dialog import _ACTION_ROLE

    for row in range(dialog._tree.topLevelItemCount()):
        item = dialog._tree.topLevelItem(row)
        if item.data(0, _ACTION_ROLE) == action:
            dialog._tree.setCurrentItem(item)
            return
    raise AssertionError(f"no row for {action}")


def test_every_action_gets_a_row_with_a_readable_name(dialog) -> None:
    """A row reading "focus_pane_left" would be nobody's idea of a preference."""
    assert dialog._tree.topLevelItemCount() == len(shortcuts.all_actions())

    labels = {
        dialog._tree.topLevelItem(row).text(0)
        for row in range(dialog._tree.topLevelItemCount())
    }
    assert "Split right" in labels
    assert not any("_" in label for label in labels)


def test_only_actions_with_several_chords_get_child_rows(dialog, store) -> None:
    """A child per chord, so one can be removed without clearing the lot -
    but only where there is a choice to make. A disclosure arrow revealing a
    copy of the row above it is noise.

    Which actions have several chords is platform-dependent (macOS splits on
    a single Cmd+D where Windows has four spellings), so this asserts the
    rule rather than naming an action.
    """
    from qtxterm.keybindings_dialog import _ACTION_ROLE

    for row in range(dialog._tree.topLevelItemCount()):
        item = dialog._tree.topLevelItem(row)
        action = item.data(0, _ACTION_ROLE)
        chords = store.sequences_for(action)
        expected = len(chords) if len(chords) > 1 else 0
        assert item.childCount() == expected, action


def test_an_actions_row_lists_all_of_its_chords(dialog, store) -> None:
    """One line per action, so the list stays scannable at two dozen rows."""
    from qtxterm.keybindings_dialog import _ACTION_ROLE

    item = dialog._tree.topLevelItem(0)
    action = item.data(0, _ACTION_ROLE)

    assert item.text(1) == ", ".join(store.display_sequences_for(action))


def test_an_action_with_no_chord_says_so(dialog, store) -> None:
    from qtxterm.keybindings_dialog import _ACTION_ROLE

    store.set_sequences(shortcuts.FIND, [])
    dialog._reload()

    for row in range(dialog._tree.topLevelItemCount()):
        item = dialog._tree.topLevelItem(row)
        if item.data(0, _ACTION_ROLE) == shortcuts.FIND:
            assert item.text(1) == "None"
            return
    raise AssertionError("no row for find")


def test_removing_the_only_chord_works_without_expanding(dialog, store) -> None:
    """A single-chord action has no children to select, so Remove has to act
    on that chord directly or the button would be permanently dead."""
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F"])
    dialog._reload()
    select_action(dialog, shortcuts.FIND)

    dialog._remove()

    assert store.sequences_for(shortcuts.FIND) == []


def test_adding_a_chord_keeps_the_existing_ones(dialog, store) -> None:
    select_action(dialog, shortcuts.FIND)
    before = list(store.sequences_for(shortcuts.FIND))
    dialog._capture.setKeySequence(QKeySequence("Ctrl+Alt+Shift+F"))

    dialog._add()

    assert store.sequences_for(shortcuts.FIND) == [*before, "Ctrl+Alt+Shift+F"]


def test_removing_a_chord_leaves_the_others(dialog, store) -> None:
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F", "Ctrl+Alt+Shift+G"])
    dialog._reload()
    select_action(dialog, shortcuts.FIND)
    item = dialog._tree.currentItem()
    dialog._tree.setCurrentItem(item.child(0))

    dialog._remove()

    assert store.sequences_for(shortcuts.FIND) == ["Ctrl+Alt+Shift+G"]


def test_a_clash_is_reported_and_nothing_is_changed(
    dialog, store, monkeypatch
) -> None:
    """Qt fires neither of two shortcuts sharing a chord, so silently taking
    the new binding would break both actions."""
    warnings = []
    monkeypatch.setattr(
        QMessageBox, "warning", lambda *args, **kwargs: warnings.append(args[2])
    )
    taken = shortcuts.sequences_for(shortcuts.CLOSE_TAB)[0]
    select_action(dialog, shortcuts.NEW_TAB)
    dialog._capture.setKeySequence(QKeySequence(taken))

    dialog._add()

    assert warnings, "the clash was not reported"
    assert "Close tab" in warnings[0]
    assert store.is_customised(shortcuts.NEW_TAB) is False


def test_resetting_an_action_restores_its_default(dialog, store) -> None:
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F"])
    dialog._reload()
    select_action(dialog, shortcuts.FIND)

    dialog._reset()

    assert store.is_customised(shortcuts.FIND) is False


def test_customised_actions_are_shown_in_bold(dialog, store) -> None:
    from qtxterm.keybindings_dialog import _ACTION_ROLE

    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F"])
    dialog._reload()

    bold = {
        dialog._tree.topLevelItem(row).data(0, _ACTION_ROLE)
        for row in range(dialog._tree.topLevelItemCount())
        if dialog._tree.topLevelItem(row).font(0).bold()
    }
    assert bold == {shortcuts.FIND}


def test_reset_all_puts_everything_back(dialog, store, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F"])
    dialog._reload()

    dialog._reset_all()

    assert not any(store.is_customised(a) for a in shortcuts.all_actions())


def test_reset_all_can_be_declined(dialog, store, monkeypatch) -> None:
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+Shift+F"])
    dialog._reload()

    dialog._reset_all()

    assert store.is_customised(shortcuts.FIND) is True


def test_only_one_chord_is_captured_at_a_time(dialog) -> None:
    """Qt records up to four chords in a row by default, and nothing in this
    app dispatches a multi-step sequence."""
    assert dialog._capture.maximumSequenceLength() == 1
