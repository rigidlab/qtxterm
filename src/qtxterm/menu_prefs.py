"""The order the terminal right-click menu's submenus appear in."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

_CONTEXT_ORDER_KEY = "menu/context_order"

SECTION_CLIPBOARD = "clipboard"
SECTION_PANE = "pane"
SECTION_COMMAND = "command"
SECTION_SELECTION = "selection"

# Copy/Paste leads by default - it is the one thing in this menu people hit
# by muscle memory, and every other terminal puts it first - but it moves
# like any other section.
DEFAULT_ORDER = [
    SECTION_CLIPBOARD,
    SECTION_PANE,
    SECTION_COMMAND,
    SECTION_SELECTION,
]

SECTION_LABELS = {
    SECTION_CLIPBOARD: "Copy/Paste",
    SECTION_PANE: "Pane",
    SECTION_COMMAND: "Command",
    SECTION_SELECTION: "Selection",
}


def normalise_order(order: list[str]) -> list[str]:
    """A saved order made safe to build a menu from.

    Drops sections that no longer exist and appends any that are missing, so
    a settings file written by an older (or hand-edited) version still yields
    every submenu exactly once - a menu item silently disappearing because of
    a stale preference would be a bad way to find that out.
    """
    seen = [section for section in order if section in SECTION_LABELS]
    deduped = list(dict.fromkeys(seen))
    return deduped + [s for s in DEFAULT_ORDER if s not in deduped]


class ContextMenuOrderStore(QObject):
    """Which order Pane / Command / Selection sit in, persisted across launches."""

    changed = Signal()

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        stored = str(settings.value(_CONTEXT_ORDER_KEY, "") or "")
        self.order = normalise_order(stored.split(","))

    def save(self, order: list[str]) -> None:
        self.order = normalise_order(order)
        self._settings.setValue(_CONTEXT_ORDER_KEY, ",".join(self.order))
        self.changed.emit()
