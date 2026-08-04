from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

_NON_INTERACTIVE_WSL_DISTROS = {"docker-desktop", "docker-desktop-data"}


def known_shells() -> list[tuple[str, str | list[str]]]:
    """(label, command) pairs for common shells that actually exist on this
    machine. `command` is a str for a bare executable or a list[str] argv
    when arguments are needed (e.g. WSL). Windows-only for now (PowerShell/
    CMD/Git Bash/WSL are Windows concepts); returns [] on other platforms,
    where the existing default-shell new tab already covers the one shell
    that matters.
    """
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

    wsl_command = _find_wsl_command()
    if wsl_command:
        shells.append(("WSL", wsl_command))

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


def _find_wsl_command() -> list[str] | None:
    """Find wsl.exe plus an explicit, real distro to launch.

    Deliberately doesn't just spawn bare `wsl.exe`: that launches whatever
    WSL considers the "default" distro, which can be misconfigured to a
    non-interactive, data-only distro (e.g. Docker Desktop sets its own
    "docker-desktop-data" as default on some setups) - bare wsl.exe would
    then fail outright with no usable shell. Listing distros and picking a
    real one explicitly (`wsl.exe -d <name>`) works regardless of whatever
    the system default happens to be.
    """
    wsl = shutil.which("wsl.exe")
    if not wsl:
        return None

    try:
        result = subprocess.run(
            [wsl, "-l", "-q"], capture_output=True, timeout=5, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None

    # wsl.exe -l -q prints UTF-16LE, regardless of the console's own encoding.
    distros = [
        line.strip()
        for line in result.stdout.decode("utf-16-le", errors="ignore").splitlines()
        if line.strip() and line.strip() not in _NON_INTERACTIVE_WSL_DISTROS
    ]
    if not distros:
        return None
    return [wsl, "-d", distros[0]]
