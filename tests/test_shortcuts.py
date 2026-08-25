"""The cross-platform shortcut table.

These are rules rather than a transcription of the table: asserting that
NEW_TAB is "Ctrl+Shift+T" would only restate the source. What is worth
pinning is the reasoning that made each choice, because those are the things
that break silently - a shortcut bound to a chord the OS eats, or two actions
quietly cancelling each other out.
"""

from __future__ import annotations

import pytest

from qtxterm import shortcuts

# Chords bash and readline own on Windows and Linux. Binding any of these at
# application level would shadow the shell inside every terminal.
SHELL_OWNED_LETTERS = "ACDEFGHKLNPRSTUWZ"


@pytest.fixture
def on_mac(monkeypatch):
    monkeypatch.setattr(shortcuts, "IS_MAC", True)


@pytest.fixture
def on_windows(monkeypatch):
    monkeypatch.setattr(shortcuts, "IS_MAC", False)


def test_no_sequence_is_bound_to_two_actions_on_windows(on_windows) -> None:
    """Two QShortcuts sharing a sequence makes Qt fire *neither* - it reports
    the ambiguity and gives up - so a collision disables both actions with
    nothing logged."""
    assert shortcuts.conflicts() == {}


def test_no_sequence_is_bound_to_two_actions_on_mac(on_mac) -> None:
    assert shortcuts.conflicts() == {}


def test_every_action_resolves_on_both_platforms(monkeypatch) -> None:
    for is_mac in (False, True):
        monkeypatch.setattr(shortcuts, "IS_MAC", is_mac)
        for action in shortcuts.all_actions():
            assert shortcuts.sequences_for(action), (action, is_mac)


def test_windows_never_takes_a_plain_ctrl_letter(on_windows) -> None:
    """The whole reason this app uses Ctrl+Shift: on Windows and Linux the
    shell owns Ctrl+letter. Ctrl+C interrupts, Ctrl+W deletes a word, Ctrl+D
    sends EOF - binding any of them would break line editing in every tab."""
    for action in shortcuts.all_actions():
        for sequence in shortcuts.sequences_for(action):
            for letter in SHELL_OWNED_LETTERS:
                assert sequence != f"Ctrl+{letter}", (action, sequence)


def test_mac_leaves_the_interrupt_alone(on_mac) -> None:
    """On macOS Qt's "Ctrl" is Command, so Ctrl+C is copy and is correct.
    The interrupt is physical Control+C, which Qt spells Meta+C - and that
    must stay unbound or Ctrl+C stops reaching the shell."""
    bound = {
        sequence
        for action in shortcuts.all_actions()
        for sequence in shortcuts.sequences_for(action)
    }

    assert "Meta+C" not in bound
    assert "Ctrl+C" in shortcuts.sequences_for(shortcuts.COPY)


def test_mac_next_tab_avoids_the_application_switcher(on_mac) -> None:
    """Qt turns "Ctrl+Tab" into Cmd+Tab on macOS, which the OS takes for its
    app switcher. Meta+Tab is the spelling that means a physical Ctrl+Tab."""
    sequences = shortcuts.sequences_for(shortcuts.NEXT_TAB)

    assert "Ctrl+Tab" not in sequences
    assert "Meta+Tab" in sequences


def test_mac_uses_command_without_shift(on_mac) -> None:
    """Command is free on macOS - the shell uses Control - so the native
    binding is Cmd+T, not the Cmd+Shift+T that translating the Windows chord
    would produce."""
    assert shortcuts.sequences_for(shortcuts.NEW_TAB) == ["Ctrl+T"]
    assert shortcuts.sequences_for(shortcuts.CLOSE_TAB) == ["Ctrl+W"]
    assert shortcuts.sequences_for(shortcuts.FIND) == ["Ctrl+F"]


def test_windows_split_covers_both_spellings_of_each_chord(on_windows) -> None:
    """A punctuation chord arrives as a different Qt key depending on the
    modifier held, and guessing wrong makes the shortcut silently dead."""
    right = shortcuts.sequences_for(shortcuts.SPLIT_RIGHT)
    down = shortcuts.sequences_for(shortcuts.SPLIT_DOWN)

    assert {"Alt+Shift+=", "Alt+Shift++"} <= set(right)
    assert {"Ctrl+Shift+|", "Ctrl+Shift+\\"} <= set(right)
    assert {"Alt+Shift+-", "Alt+Shift+_"} <= set(down)
    assert {"Ctrl+Shift+_", "Ctrl+Shift+-"} <= set(down)


def test_zoom_out_does_not_collide_with_split_down(on_windows) -> None:
    """Ctrl+Shift+- is split-down. Adding it to zoom-out as well - which
    looks harmless, since Ctrl+- and Ctrl+Shift+- feel like one gesture -
    would make Qt fire neither."""
    assert set(shortcuts.sequences_for(shortcuts.ZOOM_OUT)).isdisjoint(
        shortcuts.sequences_for(shortcuts.SPLIT_DOWN)
    )


def test_the_last_tab_slot_means_the_last_tab(monkeypatch) -> None:
    """Following browsers and Windows Terminal, so the binding keeps working
    once there are more tabs than slots."""
    assert shortcuts.LAST_TAB_SLOT == shortcuts.TAB_SLOTS
    assert shortcuts.tab_slot_action(3) in shortcuts.all_actions()

def test_display_names_are_unchanged_off_mac(on_windows) -> None:
    for action in shortcuts.all_actions():
        assert shortcuts.display_sequences_for(action) == shortcuts.sequences_for(action)


def test_mac_display_names_use_the_keys_people_actually_press(on_mac) -> None:
    """Qt's "Ctrl" is Command on macOS, so a binding Qt spells Ctrl+T is
    Cmd+T on the keycap, in the menus and in the guide. Comparing Qt's
    spelling against user-facing text is what failed the docs test on macOS
    CI while both the code and the guide were correct."""
    assert shortcuts.display_sequences_for(shortcuts.NEW_TAB) == ["Cmd+T"]
    assert shortcuts.display_sequences_for(shortcuts.SPLIT_RIGHT) == ["Cmd+D"]


def test_mac_display_names_translate_meta_to_control(on_mac) -> None:
    """Meta is physical Control on macOS. Ctrl is translated to Cmd first
    precisely so this rule cannot rewrite a Ctrl it just produced."""
    shown = shortcuts.display_sequences_for(shortcuts.NEXT_TAB)

    assert "Ctrl+Tab" in shown
    assert "Cmd+Tab" not in shown, "Cmd+Tab is the OS app switcher"


def test_mac_display_names_translate_alt_to_option(on_mac) -> None:
    assert shortcuts.display_sequences_for(shortcuts.FOCUS_PANE_LEFT) == [
        "Cmd+Opt+Left"
    ]


def test_display_translation_leaves_a_trailing_plus_alone(on_mac) -> None:
    """Zoom in is Ctrl and the plus key. Substituting the bare word "Ctrl"
    rather than "Ctrl+" would have to reason about which trailing + is a
    separator and which is the key."""
    assert "Cmd++" in shortcuts.display_sequences_for(shortcuts.ZOOM_IN)
