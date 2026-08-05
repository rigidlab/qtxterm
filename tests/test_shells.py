"""known_shells(): detection is monkeypatched so tests don't depend on what's
actually installed on the machine running them."""

from __future__ import annotations

import subprocess

import qtxterm.shells as shells


def _wsl_list_result(distro_names: list[str]) -> subprocess.CompletedProcess:
    # wsl.exe -l -q really does print UTF-16LE regardless of console encoding.
    stdout = "".join(f"{name}\r\n" for name in distro_names).encode("utf-16-le")
    return subprocess.CompletedProcess(args=["wsl.exe", "-l", "-q"], returncode=0, stdout=stdout)


def test_returns_empty_on_non_windows(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "linux")

    assert shells.known_shells() == []


def test_includes_powershell_and_cmd_when_present(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: f"C:\\fake\\{name}" if name in ("powershell.exe", "cmd.exe") else None,
    )

    labels = [label for label, _ in shells.known_shells()]

    assert labels == ["PowerShell", "Command Prompt"]


def test_finds_git_bash_via_program_files_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.shutil, "which", lambda name: None)
    git_bin = tmp_path / "Git" / "bin"
    git_bin.mkdir(parents=True)
    bash_exe = git_bin / "bash.exe"
    bash_exe.write_text("")
    monkeypatch.setattr(shells.os, "environ", {"ProgramFiles": str(tmp_path)})

    result = shells.known_shells()

    assert ("Git Bash", str(bash_exe)) in result


def test_git_bash_ignores_system32_shim(monkeypatch) -> None:
    """The legacy WSL bash.exe shim in System32 must never be reported as Git Bash."""
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: r"C:\Windows\System32\bash.exe" if name == "bash.exe" else None,
    )

    result = shells.known_shells()

    assert all(label != "Git Bash" for label, _ in result)


def test_includes_wsl_with_first_real_distro(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: r"C:\Windows\System32\wsl.exe" if name == "wsl.exe" else None,
    )
    monkeypatch.setattr(
        shells.subprocess,
        "run",
        lambda *a, **kw: _wsl_list_result(["Ubuntu", "Ubuntu-24.04"]),
    )

    result = shells.known_shells()

    assert ("WSL", [r"C:\Windows\System32\wsl.exe", "-d", "Ubuntu"]) in result


def test_wsl_skips_non_interactive_docker_distros(monkeypatch) -> None:
    """Bare wsl.exe launches whatever's marked "default", which Docker Desktop
    can set to its own data-only distro - that has no usable shell at all, so
    it must never be the one we pick, even if WSL lists it first."""
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: r"C:\Windows\System32\wsl.exe" if name == "wsl.exe" else None,
    )
    monkeypatch.setattr(
        shells.subprocess,
        "run",
        lambda *a, **kw: _wsl_list_result(["docker-desktop-data", "Ubuntu", "docker-desktop"]),
    )

    result = shells.known_shells()

    assert ("WSL", [r"C:\Windows\System32\wsl.exe", "-d", "Ubuntu"]) in result


def test_wsl_omitted_when_no_real_distro_installed(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: r"C:\Windows\System32\wsl.exe" if name == "wsl.exe" else None,
    )
    monkeypatch.setattr(
        shells.subprocess,
        "run",
        lambda *a, **kw: _wsl_list_result(["docker-desktop-data", "docker-desktop"]),
    )

    result = shells.known_shells()

    assert all(label != "WSL" for label, _ in result)


def test_wsl_omitted_when_listing_distros_fails(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(
        shells.shutil,
        "which",
        lambda name: r"C:\Windows\System32\wsl.exe" if name == "wsl.exe" else None,
    )

    def raise_timeout(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="wsl.exe", timeout=5)

    monkeypatch.setattr(shells.subprocess, "run", raise_timeout)

    result = shells.known_shells()

    assert all(label != "WSL" for label, _ in result)


def test_excludes_shells_that_are_not_found(monkeypatch) -> None:
    monkeypatch.setattr(shells.sys, "platform", "win32")
    monkeypatch.setattr(shells.os, "environ", {})
    monkeypatch.setattr(shells.shutil, "which", lambda name: None)

    assert shells.known_shells() == []
