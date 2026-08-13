from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_NON_INTERACTIVE_WSL_DISTROS = {"docker-desktop", "docker-desktop-data"}

# Every WSL entry is labelled "WSL: <distro>", which is how a stored
# preference can be resolved without enumerating distros unless it is one.
WSL_LABEL_PREFIX = "WSL: "


def local_shells() -> list[tuple[str, str | list[str]]]:
    """Shells found by looking at the filesystem - no subprocess involved."""
    if sys.platform != "win32":
        return []

    shells: list[tuple[str, str | list[str]]] = []

    powershell = shutil.which("powershell.exe")
    if powershell:
        shells.append(("PowerShell", powershell))

    cmd = shutil.which("cmd.exe")
    if cmd:
        shells.append(("Command Prompt", cmd))

    git_bash = _find_git_bash()
    if git_bash:
        shells.append(("Git Bash", git_bash))

    return shells


def shell_for_label(label: str) -> str | list[str] | None:
    """The command behind a saved preference label, or None if it is gone.

    Deliberately not `known_shells()`: that enumerates WSL distros with a
    subprocess, and answering "what is Git Bash?" has nothing to do with
    WSL. Only a "WSL: ..." label pays for the enumeration.
    """
    for name, command in local_shells():
        if name == label:
            return command
    if label.startswith(WSL_LABEL_PREFIX):
        for name, command in _wsl_shells():
            if name == label:
                return command
    return None


def known_shells() -> list[tuple[str, str | list[str]]]:
    """(label, command) pairs for common shells that actually exist on this
    machine. `command` is a str for a bare executable or a list[str] argv
    when arguments are needed (e.g. WSL). Windows-only for now (PowerShell/
    CMD/Git Bash/WSL are Windows concepts); returns [] on other platforms,
    where the existing default-shell new tab already covers the one shell
    that matters.
    """
    shells = local_shells()
    shells.extend(_wsl_shells())
    return shells


def _find_git_bash() -> str | None:
    """Look in Git for Windows' standard install locations first.

    Deliberately doesn't just `shutil.which("bash.exe")`: Windows ships a
    bash.exe shim in System32 for the legacy WSL launcher, which would
    otherwise get picked up as "Git Bash" if it's earlier on PATH.
    """
    for env_var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(env_var)
        if not base:
            continue
        candidate = Path(base) / "Git" / "bin" / "bash.exe"
        if candidate.exists():
            return str(candidate)

    which_bash = shutil.which("bash.exe")
    if which_bash and "system32" not in which_bash.lower():
        return which_bash
    return None


def wsl_distros() -> list[str]:
    """Every installed WSL distro that can actually give you a shell.

    Data-only distros are filtered out: Docker Desktop installs
    "docker-desktop"/"docker-desktop-data", which aren't interactive and can
    even be WSL's configured default, so launching them gives no usable
    shell.
    """
    if sys.platform != "win32":
        return []

    wsl = shutil.which("wsl.exe")
    if not wsl:
        return []

    # stdin is closed and no console is allocated: qtxterm's GUI entry point
    # has no console of its own, so spawning a console program makes Windows
    # create one - which costs (0.5s measured in isolation, and 5s inside the
    # running app, hitting the timeout below) and can flash a console window
    # on screen. CREATE_NO_WINDOW is Windows-only, hence the guarded kwargs.
    options: dict[str, object] = {"stdin": subprocess.DEVNULL}
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        options["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        result = subprocess.run(
            [wsl, "-l", "-q"], capture_output=True, timeout=5, check=False, **options
        )
    except (OSError, subprocess.TimeoutExpired):
        return []

    # wsl.exe -l -q prints UTF-16LE, regardless of the console's own encoding.
    return [
        stripped
        for line in result.stdout.decode("utf-16-le", errors="ignore").splitlines()
        if (stripped := line.strip()) and stripped not in _NON_INTERACTIVE_WSL_DISTROS
    ]


def _wsl_shells() -> list[tuple[str, list[str]]]:
    """One entry per installed distro, each launched explicitly by name.

    Deliberately never bare `wsl.exe`: that launches whatever WSL considers
    the default distro, which may be a data-only one (see wsl_distros) and
    would fail outright. `wsl.exe -d <name>` works regardless of the system
    default.
    """
    wsl = shutil.which("wsl.exe")
    if not wsl:
        return []
    return [
        (f"{WSL_LABEL_PREFIX}{distro}", [wsl, "-d", distro]) for distro in wsl_distros()
    ]
