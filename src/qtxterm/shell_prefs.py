"""Which shell new tabs open with, persisted across launches."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from qtxterm.pty_backend import default_shell
from qtxterm.shells import known_shells

_DEFAULT_SHELL_KEY = "shell/default"

# Stored when no explicit choice has been made: new tabs follow the OS
# default (powershell.exe on Windows, $SHELL elsewhere).
SYSTEM_DEFAULT = ""
SYSTEM_DEFAULT_LABEL = "System default"


class ShellPreferenceStore(QObject):
    """The label of the shell new tabs should use, or SYSTEM_DEFAULT.

    Stores the *label* ("Git Bash", "WSL: Ubuntu-22.04") rather than the
    resolved command, so the setting survives a machine where paths differ,
    stays readable in the ini file, and degrades to the system default if
    that shell is later uninstalled - a stored argv would simply fail to
    spawn.
    """

    changed = Signal()

    def __init__(self, settings: QSettings) -> None:
        super().__init__()
        self._settings = settings
        self.label = str(settings.value(_DEFAULT_SHELL_KEY, SYSTEM_DEFAULT) or "")

    def save(self, label: str) -> None:
        self.label = label
        self._settings.setValue(_DEFAULT_SHELL_KEY, label)
        self.changed.emit()

    def resolve(self) -> str | list[str] | None:
        """The command new tabs should spawn, or None to let the OS decide."""
        if not self.label:
            return None
        for label, command in known_shells():
            if label == self.label:
                return command
        # The shell was uninstalled (or the WSL distro removed) since it was
        # chosen; fall back rather than failing to open a tab.
        return None

    def resolved_label(self) -> str:
        """What the resolved default is called, for display."""
        return self.label if self.resolve() is not None else SYSTEM_DEFAULT_LABEL


def system_default_label() -> str:
    """e.g. "System default (powershell.exe)", for the Preferences combo."""
    return f"{SYSTEM_DEFAULT_LABEL} ({default_shell()})"
