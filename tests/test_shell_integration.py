"""Shell hooks that make a shell report its directory, and reading it back."""

from __future__ import annotations

import os

from qtxterm.shell_integration import POWERSHELL_HOOK, decorate, path_from_osc7


def test_powershell_dot_sources_the_hook_after_the_users_profile() -> None:
    command, env = decorate(["powershell.exe"])

    assert command[0] == "powershell.exe"
    # -Command has to be last: PowerShell reads everything after it as the
    # command, so an argument added later would be swallowed by the hook.
    assert command[-2] == "-Command"
    assert str(POWERSHELL_HOOK) in command[-1]
    assert "-NoExit" in command
    assert env is None


def test_pwsh_is_hooked_too() -> None:
    command, _env = decorate(["C:/Program Files/PowerShell/7/pwsh.exe"])

    assert "-NoExit" in command


def test_bash_is_hooked_through_the_environment() -> None:
    command, env = decorate(["/usr/bin/bash"])

    assert command == ["/usr/bin/bash"]
    assert "file:///" in env["PROMPT_COMMAND"]
    # The rest of the environment has to survive, or the shell starts without
    # a PATH.
    assert env["PATH"] == os.environ["PATH"]


def test_cmd_is_hooked_through_its_prompt_string() -> None:
    _command, env = decorate(["C:/Windows/System32/cmd.exe"])

    assert env["PROMPT"].startswith("$E]7;file:///$P")
    # cmd's own default prompt is kept on the end, so the hook doesn't
    # visibly change how the shell looks.
    assert env["PROMPT"].endswith("$P$G")


def test_an_unknown_shell_is_left_exactly_as_it_was() -> None:
    assert decorate(["/bin/fish"]) == (["/bin/fish"], None)
    assert decorate([]) == ([], None)


def test_osc7_payloads_become_local_paths() -> None:
    # Windows, from the PowerShell and bash hooks: empty host, drive letter.
    assert path_from_osc7("file:///C:/Users/dev") == "C:/Users/dev"
    # A named host, which some shells send and which we ignore.
    assert path_from_osc7("file://desktop/C:/Users/dev") == "C:/Users/dev"
    # cmd can only produce a native path, backslashes and spaces included.
    assert path_from_osc7("file:///C:\\Program Files") == "C:/Program Files"
    assert path_from_osc7("file:///C:/a%20b") == "C:/a b"
    # POSIX keeps its root - only a drive letter loses the leading slash.
    assert path_from_osc7("file:///home/dev") == "/home/dev"


def test_payloads_that_name_no_directory() -> None:
    assert path_from_osc7("") is None
    assert path_from_osc7("   ") is None
    assert path_from_osc7("file://desktop") is None
