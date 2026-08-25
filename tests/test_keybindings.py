"""User overrides for the keyboard shortcuts."""

from __future__ import annotations

import json

import pytest

from qtxterm import shortcuts
from qtxterm.keybindings import ConflictError, KeybindingStore, normalise


def make_store(tmp_path) -> KeybindingStore:
    return KeybindingStore(path=tmp_path / "keybindings.json")


def test_an_untouched_action_follows_the_defaults(tmp_path) -> None:
    store = make_store(tmp_path)

    assert store.sequences_for(shortcuts.NEW_TAB) == shortcuts.sequences_for(
        shortcuts.NEW_TAB
    )
    assert store.is_customised(shortcuts.NEW_TAB) is False


def test_an_override_replaces_the_default(tmp_path) -> None:
    store = make_store(tmp_path)

    store.set_sequences(shortcuts.NEW_TAB, ["Ctrl+Alt+N"])

    assert store.sequences_for(shortcuts.NEW_TAB) == ["Ctrl+Alt+N"]
    assert store.is_customised(shortcuts.NEW_TAB) is True


def test_only_the_differences_are_written_to_disk(tmp_path) -> None:
    """Saving the whole resolved table would freeze today's defaults into
    every config file, so a later version that improves a binding would never
    reach anyone who had opened the editor once."""
    store = make_store(tmp_path)
    store.set_sequences(shortcuts.NEW_TAB, ["Ctrl+Alt+N"])

    written = json.loads((tmp_path / "keybindings.json").read_text(encoding="utf-8"))

    assert list(written["bindings"]) == [shortcuts.NEW_TAB]


def test_an_override_survives_a_reload(tmp_path) -> None:
    make_store(tmp_path).set_sequences(shortcuts.FIND, ["Ctrl+Alt+F"])

    assert make_store(tmp_path).sequences_for(shortcuts.FIND) == ["Ctrl+Alt+F"]


def test_resetting_returns_to_the_default(tmp_path) -> None:
    store = make_store(tmp_path)
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+F"])

    store.reset(shortcuts.FIND)

    assert store.sequences_for(shortcuts.FIND) == shortcuts.sequences_for(
        shortcuts.FIND
    )
    assert store.is_customised(shortcuts.FIND) is False


def test_reset_all_clears_every_override(tmp_path) -> None:
    store = make_store(tmp_path)
    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+F"])
    store.set_sequences(shortcuts.NEW_TAB, ["Ctrl+Alt+N"])

    store.reset_all()

    assert store.conflicts() == {}
    assert not any(store.is_customised(a) for a in shortcuts.all_actions())


def test_a_sequence_another_action_holds_is_refused(tmp_path) -> None:
    """Two QShortcuts sharing a sequence makes Qt fire neither, so accepting
    the newer binding last-wins would quietly disable both actions."""
    store = make_store(tmp_path)
    taken = shortcuts.sequences_for(shortcuts.CLOSE_TAB)[0]

    with pytest.raises(ConflictError) as excinfo:
        store.set_sequences(shortcuts.NEW_TAB, [taken])

    assert excinfo.value.sequence == normalise(taken)
    assert excinfo.value.action == shortcuts.CLOSE_TAB
    # And the rejected binding did not take effect.
    assert store.is_customised(shortcuts.NEW_TAB) is False


def test_an_action_may_keep_its_own_sequence_when_rebinding(tmp_path) -> None:
    """Adding a second chord must not trip the conflict check against the
    chord the action already had."""
    store = make_store(tmp_path)
    existing = shortcuts.sequences_for(shortcuts.FIND)[0]

    store.set_sequences(shortcuts.FIND, [existing, "Ctrl+Alt+F"])

    assert store.sequences_for(shortcuts.FIND) == [normalise(existing), "Ctrl+Alt+F"]


def test_duplicates_within_one_action_are_collapsed(tmp_path) -> None:
    store = make_store(tmp_path)

    store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+F", "ctrl+alt+f"])

    assert store.sequences_for(shortcuts.FIND) == ["Ctrl+Alt+F"]


def test_sequences_are_normalised_so_case_does_not_matter(tmp_path) -> None:
    """A hand-edited file should not be able to produce a binding that looks
    set in the editor and never matches a key."""
    store = make_store(tmp_path)

    store.set_sequences(shortcuts.FIND, ["ctrl+shift+alt+f"])

    assert store.sequences_for(shortcuts.FIND) == [normalise("Ctrl+Shift+Alt+F")]


def test_an_action_can_have_no_shortcut_at_all(tmp_path) -> None:
    """Different from resetting: an action nobody wants a key for is a
    legitimate thing to ask for."""
    store = make_store(tmp_path)

    store.set_sequences(shortcuts.FIND, [])

    assert store.sequences_for(shortcuts.FIND) == []
    assert store.is_customised(shortcuts.FIND) is True


def test_rubbish_is_refused(tmp_path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(ValueError):
        store.set_sequences(shortcuts.FIND, ["not a chord at all"])


def test_an_unknown_action_is_refused(tmp_path) -> None:
    store = make_store(tmp_path)

    with pytest.raises(KeyError):
        store.set_sequences("summon_a_pony", ["Ctrl+Alt+P"])


def test_a_corrupt_file_falls_back_to_defaults(tmp_path) -> None:
    """A broken config should not stop the app starting; the cost of ignoring
    it is defaults, which are always usable."""
    (tmp_path / "keybindings.json").write_text("{not json", encoding="utf-8")

    store = make_store(tmp_path)

    assert store.sequences_for(shortcuts.NEW_TAB) == shortcuts.sequences_for(
        shortcuts.NEW_TAB
    )


def test_bindings_for_unknown_actions_are_dropped_on_load(tmp_path) -> None:
    """Either a typo or a binding from a newer version - carrying it would let
    it collide with something real later."""
    (tmp_path / "keybindings.json").write_text(
        json.dumps({"version": 1, "bindings": {"summon_a_pony": ["Ctrl+Alt+P"]}}),
        encoding="utf-8",
    )

    store = make_store(tmp_path)

    assert store.conflicts() == {}
    assert store.holder_of("Ctrl+Alt+P") is None


def test_saving_emits_changed(tmp_path, qtbot) -> None:
    store = make_store(tmp_path)

    with qtbot.waitSignal(store.changed, timeout=1000):
        store.set_sequences(shortcuts.FIND, ["Ctrl+Alt+F"])


def test_the_defaults_have_no_conflicts_through_the_store(tmp_path) -> None:
    assert make_store(tmp_path).conflicts() == {}


def test_holder_of_names_the_action_using_a_chord(tmp_path) -> None:
    store = make_store(tmp_path)
    taken = shortcuts.sequences_for(shortcuts.CLOSE_TAB)[0]

    assert store.holder_of(taken) == shortcuts.CLOSE_TAB
    assert store.holder_of("Ctrl+Alt+Shift+F12") is None
