"""Teach the shells we launch to report their working directory (OSC 7).

A split pane opens where its sibling was, which means the app has to know
where that is. Asking the OS for the shell process's working directory only
works for some shells - PowerShell, the Windows default, never updates it on
`cd` - so instead each shell is asked to *say* where it is, using the same
OSC 7 sequence VS Code and Windows Terminal rely on:

    ESC ] 7 ; file://<host>/<path> ESC \

Nothing here is required for a terminal to work. A shell we do not
recognise, or one whose prompt the user has since replaced, simply never
reports, and a pane split off it starts in the default directory.
"""

from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import unquote

ASSETS_DIR = Path(__file__).parent / "assets"
POWERSHELL_HOOK = ASSETS_DIR / "shell_integration" / "qtxterm.ps1"

_POWERSHELLS = frozenset({"powershell", "pwsh"})
_BASHES = frozenset({"bash", "sh"})

# printf, not echo -e: echo's escape handling differs between bash and the
# sh some distros link it to. cygpath translates Git Bash's /c/Users/... into
# C:/Users/..., which is the only form Windows can start a process in; on
# Linux and macOS there is no cygpath and $PWD is already the right thing.
#
# The host is left empty (file:///...) rather than filled in with $HOSTNAME:
# an empty host means "this machine", which is the only case worth reporting,
# and it makes the sequence identical in shape whether the path that follows
# is /home/dev or C:/Users/dev. Stripping a leading slash before adding one
# back is what keeps both of those to exactly three slashes.
_BASH_PROMPT_COMMAND = (
    '__qtxterm_cwd=$(cygpath -m "$PWD" 2>/dev/null || printf %s "$PWD"); '
    'printf "\x1b]7;file:///%s\x07" "${__qtxterm_cwd#/}"'
)

_CMD_PROMPT = r"$E]7;file:///$P$E\$P$G"


def stem(command: str) -> str:
    """Lowercased executable name without its extension, e.g. 'powershell'."""
    return Path(command).stem.lower()


def decorate(command: list[str]) -> tuple[list[str], dict[str, str] | None]:
    """The argv and environment to launch `command` with, hooks included.

    Returns the command unchanged and `None` for the environment when the
    shell is one we have no hook for - `None` rather than a copy of
    os.environ so the backends keep their plain inherit-everything path.
    """
    if not command:
        return command, None

    name = stem(command[0])
    if name in _POWERSHELLS:
        # -Command has to come last: PowerShell treats everything after it as
        # the command. -NoExit keeps the session interactive afterwards.
        quoted = str(POWERSHELL_HOOK).replace("'", "''")
        return [*command, "-NoExit", "-Command", f". '{quoted}'"], None
    if name in _BASHES:
        # An environment variable rather than --rcfile, which would replace
        # the user's own startup files instead of running alongside them.
        return command, os.environ | {"PROMPT_COMMAND": _BASH_PROMPT_COMMAND}
    if name == "cmd":
        return command, os.environ | {"PROMPT": _CMD_PROMPT}
    return command, None


def path_from_osc7(uri: str) -> str | None:
    """The local directory an OSC 7 payload names, or None if it names none.

    Parsed here rather than with QUrl because the payloads are not all
    well-formed URLs: cmd's PROMPT can only produce a native path, complete
    with backslashes and unescaped spaces, and a Windows drive letter arrives
    as the "/C:/Users/..." Qt would hand back as a UNC path.
    """
    text = (uri or "").strip()
    if not text:
        return None
    if text.startswith("file://"):
        rest = text[len("file://") :]
        # Everything up to the first separator is the hostname, which is
        # deliberately ignored: a remote host's path is not ours to open.
        slash = rest.find("/")
        text = rest[slash:] if slash != -1 else ""
    text = unquote(text).replace("\\", "/")
    if not text:
        return None
    # "/C:/Users/dev" -> "C:/Users/dev". Only a drive letter, so a POSIX
    # "/home/dev" keeps its root.
    if len(text) > 2 and text[0] == "/" and text[2] == ":":
        text = text[1:]
    return text or None
