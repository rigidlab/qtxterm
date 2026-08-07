"""Running a Selection Action: the terminal's selected text as command input.

The selection is untrusted text, so it never reaches a shell command line.
Each `kind` carries it by a route with its own escaping (see SPEC.md):

- url   - percent-encoded into a template, opened in the browser. No shell.
- stdin - written to a temp file the command reads on standard input. No
          quoting of the selection at all, and it survives newlines and
          arbitrary length, both of which break command-line interpolation.
          How a shell is told to read that file is per-shell, though - see
          feed_from_file.
"""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from qtxterm.presets import KIND_STDIN, KIND_URL, SELECTION_PLACEHOLDER, Preset

# Internet Explorer's old 2083-char cap is still the practical ceiling for
# what search engines and OS URL handlers accept, so the selection is capped
# well below it rather than silently producing a truncated or rejected URL.
MAX_URL_SELECTION_CHARS = 1500

SELECTION_DIR_NAME = "qtxterm-selections"
# Temp files outlive the command that reads them (it may still be running
# when the tab closes), so they're swept on the next startup instead.
SELECTION_FILE_MAX_AGE_SECONDS = 24 * 60 * 60


def selection_dir() -> Path:
    return Path(tempfile.gettempdir()) / SELECTION_DIR_NAME


def build_url(template: str, selection: str) -> str:
    """Percent-encode `selection` into `template`.

    `safe=""` so that /, ?, &, = and friends in the selection are encoded
    too - left unescaped they would restructure the URL rather than be
    searched for.
    """
    trimmed = selection[:MAX_URL_SELECTION_CHARS]
    return template.replace(SELECTION_PLACEHOLDER, quote(trimmed, safe=""))


def write_selection_file(selection: str) -> Path:
    """Write `selection` somewhere a shell can redirect from."""
    directory = selection_dir()
    directory.mkdir(parents=True, exist_ok=True)
    handle, name = tempfile.mkstemp(
        suffix=".txt", prefix="selection-", dir=directory, text=True
    )
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(selection)
    return Path(name)


def clean_old_selection_files(now: float | None = None) -> int:
    """Delete selection temp files left by earlier runs. Returns the count."""
    directory = selection_dir()
    if not directory.is_dir():
        return 0
    cutoff = (now or time.time()) - SELECTION_FILE_MAX_AGE_SECONDS
    removed = 0
    for path in directory.glob("selection-*.txt"):
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError:
            # Another instance may be reading or sweeping the same file.
            continue
    return removed


POWERSHELL_SHELLS = frozenset({"powershell", "pwsh"})
CMD_SHELLS = frozenset({"cmd"})
WSL_SHELLS = frozenset({"wsl"})


def wsl_path(path: Path) -> str:
    r"""Translate a Windows path for the Linux side of WSL.

    A tab running `wsl.exe` gets a Linux shell, where C:\Temp\x.txt means
    nothing - it has to be /mnt/c/Temp/x.txt.
    """
    text = path.as_posix()
    if len(text) > 1 and text[1] == ":":
        return f"/mnt/{text[0].lower()}{text[2:]}"
    return text


def feed_from_file(line: str, path: Path, shell_name: str) -> str:
    """Rewrite `line` so it reads `path` on standard input, per shell.

    Not one portable form: Windows PowerShell reserves `<` and fails with
    "The '<' operator is reserved for future use", so it needs a
    Get-Content pipe instead. Only the path is interpolated here, and it's
    a name this module generated - the selection itself never reaches a
    command line, which is the whole point of this route.
    """
    shell = shell_name.lower()
    if shell in POWERSHELL_SHELLS:
        return f'Get-Content -Raw "{path}" | {line}'
    if shell in CMD_SHELLS:
        return f'type "{path}" | {line}'
    if shell in WSL_SHELLS:
        return f'{line} < "{wsl_path(path)}"'
    # bash/zsh/sh, including Git Bash, which accepts forward-slashed
    # Windows paths.
    return f'{line} < "{path.as_posix()}"'


def stdin_lines(preset: Preset, selection: str, shell_name: str) -> list[str]:
    """The preset's lines with the last one reading from the selection file.

    Only the last line is rewritten: earlier lines are setup (a `cd`, an
    activate), and the final one is the command that consumes the text.
    """
    path = write_selection_file(selection)
    *setup, consumer = preset.lines
    return [*setup, feed_from_file(consumer, path, shell_name)]


def default_shell_name() -> str:
    # Imported lazily: this module is pure enough to test on its own, and
    # the terminal stack pulls in QtWebEngine.
    from qtxterm.pty_backend import default_shell
    from qtxterm.terminal_widget import shell_short_name

    return shell_short_name(default_shell())


def shell_name_for(preset: Preset, tabs) -> str:
    """Which shell will actually run this action's command.

    A new-tab action gets the default shell; an active-terminal one gets
    whatever that tab is running, which may be any of the four.
    """
    if preset.target == "new_tab":
        return default_shell_name()
    terminal = tabs.active_terminal()
    return terminal.shell_name if terminal is not None else default_shell_name()


def run_selection_action(
    preset: Preset, selection: str, tabs, shell_name: str | None = None
) -> bool:
    """Execute `preset` against `selection`. False if there was nothing to do."""
    if not selection:
        return False

    if preset.kind == KIND_URL:
        QDesktopServices.openUrl(QUrl(build_url(preset.lines[0], selection)))
        return True

    if preset.kind == KIND_STDIN:
        lines = stdin_lines(
            preset, selection, shell_name or shell_name_for(preset, tabs)
        )
        if preset.target == "new_tab":
            tabs.run_in_new_tab(None, lines)
        else:
            tabs.run_in_active(lines)
        return True

    return False
