"""When a pane should close itself after its shell exits.

Before this, an exited shell left a dead pane showing "[process exited with
code 0]" until you closed it by hand, which every other terminal treats as
the exception rather than the rule.

Three settings rather than a checkbox, because the interesting case is the
middle one. A shell you exited on purpose (`exit`, Ctrl+D) should take its
pane with it; a shell that *died* has usually printed why, and closing the
pane throws that away just as you needed to read it. Matching Windows
Terminal's closeOnExit, which arrived at the same three.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

_KEY = "session/closeOnExit"

# Leave the pane open whatever happened - what qtxterm did before this
# existed, kept so nobody's habit is broken by an upgrade.
CLOSE_NEVER = "never"
# Close only on a zero exit code, so a crash leaves its error on screen.
CLOSE_CLEAN = "clean"
# Always close, even when the shell died. For people who keep their errors
# somewhere other than the terminal.
CLOSE_ALWAYS = "always"

CHOICES = (CLOSE_CLEAN, CLOSE_ALWAYS, CLOSE_NEVER)
LABELS = {
    CLOSE_CLEAN: "Close it, unless the shell failed",
    CLOSE_ALWAYS: "Always close it",
    CLOSE_NEVER: "Leave it open",
}
DEFAULT = CLOSE_CLEAN


def should_close(choice: str, exit_code: int) -> bool:
    """Whether a pane whose shell exited with `exit_code` should close."""
    if choice == CLOSE_ALWAYS:
        return True
    if choice == CLOSE_CLEAN:
        return exit_code == 0
    return False


class PaneExitStore(QObject):
    """Loads/saves the close-on-exit choice, the same shape as the other stores."""

    changed = Signal()

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        self.current = self._load()

    def _load(self) -> str:
        # Anything unrecognised falls back rather than raising: this file is
        # hand-editable, and a typo should not stop the app starting.
        choice = self._settings.value(_KEY, DEFAULT)
        return choice if choice in CHOICES else DEFAULT

    def save(self, choice: str) -> None:
        if choice not in CHOICES:
            raise ValueError(f"unknown close-on-exit choice: {choice!r}")
        self.current = choice
        self._settings.setValue(_KEY, choice)
        self.changed.emit()
