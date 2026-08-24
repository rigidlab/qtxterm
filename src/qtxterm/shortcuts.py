"""Keyboard shortcuts, resolved per platform.

Qt's key sequence strings are already portable in one particular way: `Ctrl`
means the **Command** key on macOS and the Control key everywhere else, `Meta`
means Control on macOS, and `Alt` is Option there. That mapping does half the
job for free and quietly ruins the other half, which is why the table below
spells out both sides rather than leaning on it.

Two facts drive every choice here:

- **On Windows and Linux a terminal cannot use plain `Ctrl`+letter.** The
  shell owns that space: `Ctrl+C` interrupts, `Ctrl+W` deletes a word,
  `Ctrl+F` moves forward a character. So the app's own actions take
  `Ctrl+Shift`, which is what Windows Terminal, GNOME Terminal and VS Code's
  terminal all do.
- **On macOS the opposite is true.** The shell uses Control, and Command is
  free, so the native binding is `Cmd`+letter with no Shift - `Cmd+T`,
  `Cmd+W`, `Cmd+F`, exactly like every other Mac app. Writing `Ctrl+Shift+T`
  and letting Qt translate it would produce `Cmd+Shift+T`, which on a Mac is
  a different gesture entirely (in browsers it reopens a closed tab).

The traps that make this more than a table:

- `Ctrl+Tab` on macOS translates to **Cmd+Tab**, the OS application switcher,
  so "next tab" has to be spelled `Meta+Tab` there to mean a physical
  Ctrl+Tab.
- `Ctrl+C` on macOS translates to Cmd+C, which is genuinely copy. The
  interrupt is physical Control+C, spelled `Meta+C`, and is deliberately left
  unbound so it reaches the shell.
- Punctuation chords arrive as different Qt keys depending on the modifier
  held, so several actions list the same chord twice under both spellings.
  See SPLIT_RIGHT/SPLIT_DOWN and the comment on ZOOM_OUT.

Some actions list more than one sequence, and the reason differs between
them. The distinction is worth keeping straight, because it decides whether
a second entry is dead weight:

- A **compatibility hedge** is two spellings of *one* physical gesture, where
  only ever one of them can fire - "Alt+Shift+=" and "Alt+Shift++" are the
  same keypress, and which one Qt reports depends on the layout. Removing
  either risks the chord doing nothing at all on some machine.
- An **alternative** is two genuinely different gestures deliberately mapped
  to one action - ZOOM_IN takes both Ctrl+= and Ctrl++ (that is,
  Ctrl+Shift+=), because people reach for the plus key with Shift held
  without thinking, and every browser accepts both. Both really do work, and
  that is the intent rather than an oversight.
"""

from __future__ import annotations

import sys

# Read once. Tests override it directly rather than patching sys.platform,
# which PySide6 has already read by the time a test runs.
IS_MAC = sys.platform == "darwin"

NEW_TAB = "new_tab"
CLOSE_TAB = "close_tab"
NEXT_TAB = "next_tab"
PREV_TAB = "prev_tab"
FIND = "find"
COPY = "copy"
PASTE = "paste"
ZOOM_IN = "zoom_in"
ZOOM_OUT = "zoom_out"
ZOOM_RESET = "zoom_reset"
SPLIT_RIGHT = "split_right"
SPLIT_DOWN = "split_down"
CLOSE_PANE = "close_pane"
FOCUS_PANE_LEFT = "focus_pane_left"
FOCUS_PANE_RIGHT = "focus_pane_right"
FOCUS_PANE_UP = "focus_pane_up"
FOCUS_PANE_DOWN = "focus_pane_down"

# action -> (Windows/Linux, macOS). Both are lists because one action often
# needs several spellings to be reachable at all.
_TABLE: dict[str, tuple[list[str], list[str]]] = {
    NEW_TAB: (["Ctrl+Shift+T"], ["Ctrl+T"]),
    CLOSE_TAB: (["Ctrl+Shift+W"], ["Ctrl+W"]),
    # Ctrl+Tab is the cross-platform gesture, but on macOS it must be spelled
    # Meta+Tab or Qt hands it to Cmd+Tab, the OS app switcher. Cmd+Shift+[ ]
    # is the Mac-native pair and is offered alongside.
    NEXT_TAB: (["Ctrl+Tab"], ["Meta+Tab", "Ctrl+Shift+]"]),
    PREV_TAB: (["Ctrl+Shift+Tab"], ["Meta+Shift+Tab", "Ctrl+Shift+["]),
    FIND: (["Ctrl+Shift+F"], ["Ctrl+F"]),
    # Ctrl+Insert / Shift+Insert are the older Windows and X11 gestures, still
    # muscle memory for a lot of people and free of any shell meaning.
    COPY: (["Ctrl+Shift+C", "Ctrl+Ins"], ["Ctrl+C"]),
    PASTE: (["Ctrl+Shift+V", "Shift+Ins"], ["Ctrl+V"]),
    # An alternative, not a hedge: Ctrl+= and Ctrl++ are different gestures
    # (the second holds Shift) and both are meant to work, matching Chrome,
    # Firefox, VS Code and Windows Terminal. Zoom out needs no counterpart -
    # nobody reaches for Shift to press minus.
    ZOOM_IN: (["Ctrl+=", "Ctrl++"], ["Ctrl+=", "Ctrl++"]),
    # Deliberately *not* Ctrl+Shift+- as well: that is the same chord as
    # SPLIT_DOWN, and binding one sequence to two actions makes whichever
    # shortcut was registered second silently dead.
    ZOOM_OUT: (["Ctrl+-"], ["Ctrl+-"]),
    ZOOM_RESET: (["Ctrl+0"], ["Ctrl+0"]),
    # Four spellings on Windows/Linux, for two different reasons. Alt+Shift+=
    # is matched against Key_Equal by Qt while the keyboard sends Key_Plus;
    # and with Ctrl held the character is a control code, so Qt cannot derive
    # "|" from the layout and reports the base key, Key_Backslash. macOS gets
    # iTerm2's Cmd+D / Cmd+Shift+D, which every Mac terminal user knows.
    SPLIT_RIGHT: (
        ["Alt+Shift+=", "Alt+Shift++", "Ctrl+Shift+|", "Ctrl+Shift+\\"],
        ["Ctrl+D"],
    ),
    SPLIT_DOWN: (
        ["Alt+Shift+-", "Alt+Shift+_", "Ctrl+Shift+_", "Ctrl+Shift+-"],
        ["Ctrl+Shift+D"],
    ),
    CLOSE_PANE: (["Alt+Shift+W"], ["Ctrl+Shift+W"]),
    # Alt+Arrow on Windows/Linux; macOS needs Cmd+Opt+Arrow, because plain
    # Option+Arrow is word-wise cursor movement in every Mac shell.
    FOCUS_PANE_LEFT: (["Alt+Left"], ["Ctrl+Alt+Left"]),
    FOCUS_PANE_RIGHT: (["Alt+Right"], ["Ctrl+Alt+Right"]),
    FOCUS_PANE_UP: (["Alt+Up"], ["Ctrl+Alt+Up"]),
    FOCUS_PANE_DOWN: (["Alt+Down"], ["Ctrl+Alt+Down"]),
}

# How many tabs are reachable by number. The ninth means "the last tab",
# following browsers and Windows Terminal, so it stays useful past nine tabs.
TAB_SLOTS = 9
LAST_TAB_SLOT = TAB_SLOTS


def tab_slot_action(slot: int) -> str:
    return f"tab_{slot}"


for _slot in range(1, TAB_SLOTS + 1):
    _TABLE[tab_slot_action(_slot)] = (
        # Alternatives, deliberately: Alt+N is GNOME Terminal's and
        # Ctrl+Alt+N is Windows Terminal's, and people arrive here with one
        # or the other already in their fingers. Neither collides with a
        # shell binding, so supporting both costs nothing.
        [f"Alt+{_slot}", f"Ctrl+Alt+{_slot}"],
        [f"Ctrl+{_slot}"],
    )


def sequences_for(action: str) -> list[str]:
    """Every key sequence that should trigger `action` on this platform."""
    other, mac = _TABLE[action]
    return list(mac if IS_MAC else other)


def all_actions() -> list[str]:
    return list(_TABLE)


def conflicts() -> dict[str, list[str]]:
    """Sequences bound to more than one action on this platform.

    Exists because the failure it catches is invisible: two QShortcuts sharing
    a sequence on the same widget makes Qt fire neither (it reports the
    ambiguity and gives up), so the shortcut simply stops working with nothing
    logged and no exception. A test calls this rather than trusting the table
    to have been read carefully.
    """
    seen: dict[str, list[str]] = {}
    for action in _TABLE:
        for sequence in sequences_for(action):
            seen.setdefault(sequence, []).append(action)
    return {seq: actions for seq, actions in seen.items() if len(actions) > 1}
