"""Which shell new tabs open with, persisted across launches."""

from __future__ import annotations

from PySide6.QtCore import QObject, QSettings, Signal

from qtxterm.pty_backend import default_shell
from qtxterm.shells import shell_for_label

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
        self._resolved: tuple[str, str | list[str] | None] | None = None

    def save(self, label: str) -> None:
        self.label = label
        self._resolved = None
        self._settings.setValue(_DEFAULT_SHELL_KEY, label)
        self.changed.emit()

    def resolve(self) -> str | list[str] | None:
        """The command new tabs should spawn, or None to let the OS decide.

        Resolved through `shell_for_label()`, which only enumerates WSL when
        the saved label is a WSL one - answering "what is Git Bash?" should
        not run a subprocess. Memoised on top of that because this runs on
        every new tab and installed shells don't change while the app is
        open; Preferences reads `known_shells()` directly when it builds its
        list, so a newly installed distro still shows up there.
        """
        if not self.label:
            return None
        if self._resolved is not None and self._resolved[0] == self.label:
            return self._resolved[1]

        command = shell_for_label(self.label)
        # None means the shell was uninstalled (or the WSL distro removed)
        # since it was chosen; new tabs fall back to the system default
        # rather than failing to open.
        self._resolved = (self.label, command)
        return command

    def resolved_label(self) -> str:
        """What the resolved default is called, for display."""
        return self.label if self.resolve() is not None else SYSTEM_DEFAULT_LABEL


def system_default_label() -> str:
    """e.g. "System default (powershell.exe)", for the Preferences combo."""
    return f"{SYSTEM_DEFAULT_LABEL} ({default_shell()})"
