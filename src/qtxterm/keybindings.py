"""User overrides for the keyboard shortcuts.

Every terminal worth using lets you rebind its keys, and the reason is not
taste: a shortcut can be taken away by something the app cannot see. A tiling
window manager that owns Alt+Arrow, a desktop that claims Ctrl+Alt+Left, a
shell binding somebody relies on - none of these are visible from inside
qtxterm, and no default table can be right for all of them. Rebinding is the
escape hatch that makes the defaults a starting point rather than a verdict.

Two decisions shape the file this writes.

**Only the differences are stored.** Saving the whole resolved table would
freeze today's defaults into every config file: a later version that improves
a binding, or adds an action, would never reach anyone who had opened the
editor once. Storing just the overrides means an untouched action keeps
following the defaults forever.

**A conflict is refused, not accepted.** Two actions sharing a sequence makes
Qt fire *neither* - it reports the ambiguity and gives up - so a last-one-wins
policy would quietly disable both. The store rejects the save and names the
action already holding the chord.
"""

from __future__ import annotations

import json
from pathlib import Path

import platformdirs
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence

from qtxterm import shortcuts

# Bumped only if the on-disk shape changes in a way a reader must know about.
FORMAT_VERSION = 1


class ConflictError(ValueError):
    """A sequence is already bound to a different action."""

    def __init__(self, sequence: str, action: str) -> None:
        super().__init__(
            f"{sequence} is already bound to {shortcuts.label_for(action)}"
        )
        self.sequence = sequence
        self.action = action


def default_keybindings_path() -> Path:
    return (
        Path(platformdirs.user_config_dir("qtxterm", appauthor=False))
        / "keybindings.json"
    )


def normalise(sequence: str) -> str:
    """Qt's canonical spelling of a sequence, or "" if it isn't one.

    Round-tripping through QKeySequence means "ctrl+shift+t" and "Ctrl+Shift+T"
    are stored identically, so a hand-edited file cannot produce a binding that
    looks set in the editor and never matches a key.
    """
    parsed = QKeySequence(sequence)
    return "" if parsed.isEmpty() else parsed.toString()


class KeybindingStore(QObject):
    """Resolves an action to its key sequences, honouring user overrides.

    Emits `changed` after every save, so the widget that owns the QShortcuts
    can rebuild them - the same pattern PresetStore uses for menus.
    """

    changed = Signal()

    def __init__(self, path: Path | None = None) -> None:
        super().__init__()
        self._path = path or default_keybindings_path()
        self._overrides: dict[str, list[str]] = self._load()

    def _load(self) -> dict[str, list[str]]:
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            # A missing file is the normal case on first run, and a corrupt one
            # should not stop the app starting - the cost of ignoring it is
            # falling back to defaults, which are always usable.
            return {}
        bindings = raw.get("bindings") if isinstance(raw, dict) else None
        if not isinstance(bindings, dict):
            return {}

        cleaned: dict[str, list[str]] = {}
        known = set(shortcuts.all_actions())
        for action, sequences in bindings.items():
            # Unknown actions are dropped rather than kept: they are either a
            # typo or a binding from a newer version, and carrying them would
            # let them collide with something real later.
            if action not in known or not isinstance(sequences, list):
                continue
            valid = [normalise(s) for s in sequences if isinstance(s, str)]
            cleaned[action] = [s for s in valid if s]
        return cleaned

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": FORMAT_VERSION, "bindings": self._overrides}
        self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        self.changed.emit()

    def sequences_for(self, action: str) -> list[str]:
        """The sequences in force for `action` - the override, or the default."""
        if action in self._overrides:
            return list(self._overrides[action])
        return shortcuts.sequences_for(action)

    def display_sequences_for(self, action: str) -> list[str]:
        """As above, named the way this platform's users see them."""
        return [shortcuts.display_sequence(s) for s in self.sequences_for(action)]

    def is_customised(self, action: str) -> bool:
        return action in self._overrides

    def holder_of(self, sequence: str, ignoring: str | None = None) -> str | None:
        """Which action currently owns `sequence`, if any."""
        wanted = normalise(sequence)
        if not wanted:
            return None
        for action in shortcuts.all_actions():
            if action == ignoring:
                continue
            if wanted in self.sequences_for(action):
                return action
        return None

    def set_sequences(self, action: str, sequences: list[str]) -> None:
        """Rebind `action`, refusing anything another action already holds.

        An empty list is allowed and means "no shortcut": an action nobody
        wants a key for is a legitimate thing to ask for, and is different
        from resetting to the default.
        """
        if action not in set(shortcuts.all_actions()):
            raise KeyError(action)

        cleaned: list[str] = []
        for sequence in sequences:
            normalised = normalise(sequence)
            if not normalised:
                raise ValueError(f"not a key sequence: {sequence!r}")
            holder = self.holder_of(normalised, ignoring=action)
            if holder is not None:
                raise ConflictError(normalised, holder)
            if normalised not in cleaned:
                cleaned.append(normalised)

        self._overrides[action] = cleaned
        self._save()

    def reset(self, action: str) -> None:
        """Drop the override so `action` follows the defaults again."""
        if self._overrides.pop(action, None) is not None:
            self._save()

    def reset_all(self) -> None:
        if self._overrides:
            self._overrides = {}
            self._save()

    def conflicts(self) -> dict[str, list[str]]:
        """Sequences held by more than one action, after overrides.

        The same check shortcuts.conflicts() makes over the defaults, repeated
        here because an override can introduce a collision the table never had.
        """
        seen: dict[str, list[str]] = {}
        for action in shortcuts.all_actions():
            for sequence in self.sequences_for(action):
                seen.setdefault(sequence, []).append(action)
        return {seq: actions for seq, actions in seen.items() if len(actions) > 1}
