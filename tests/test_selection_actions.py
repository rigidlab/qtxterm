"""Selection Actions: how the selected text travels, and its escaping.

The selection is untrusted, so these tests care most about it never
reaching a shell command line unescaped.
"""

from __future__ import annotations

import os
import stat
import tempfile

import time
from pathlib import Path

from qtxterm import selection_actions
from qtxterm.presets import KIND_STDIN, KIND_URL, Preset
from qtxterm.selection_actions import (
    MAX_URL_SELECTION_CHARS,
    build_url,
    clean_old_selection_files,
    feed_from_file,
    run_selection_action,
    stdin_lines,
    write_selection_file,
    wsl_path,
)

TEMPLATE = "https://www.google.com/search?q={selection}"


class FakeTabs:
    def __init__(self) -> None:
        self.active_calls: list[list[str]] = []
        self.new_tab_calls: list[tuple[object, list[str]]] = []

    def run_in_active(self, lines: list[str]) -> None:
        self.active_calls.append(lines)

    def run_in_new_tab(self, shell, lines: list[str]):
        self.new_tab_calls.append((shell, lines))


def test_build_url_percent_encodes_the_selection() -> None:
    assert build_url(TEMPLATE, "hello world") == (
        "https://www.google.com/search?q=hello%20world"
    )


def test_build_url_encodes_url_structural_characters() -> None:
    """Left raw, these would restructure the URL instead of being searched."""
    url = build_url(TEMPLATE, "a&b=c?d/e#f")

    assert url == "https://www.google.com/search?q=a%26b%3Dc%3Fd%2Fe%23f"
    assert "&b=" not in url


def test_build_url_caps_selection_length() -> None:
    url = build_url(TEMPLATE, "x" * (MAX_URL_SELECTION_CHARS + 500))

    assert url.count("x") == MAX_URL_SELECTION_CHARS


def test_selection_is_never_interpolated_into_the_stdin_command(tmp_path) -> None:
    """The whole point of the stdin route: a selection full of shell
    metacharacters ends up in a file, never on the command line."""
    hostile = 'foo"; rm -rf ~ #\n$(whoami)\n`id`'
    preset = Preset(name="Explain", lines=["claude -p explain"], kind=KIND_STDIN)

    lines = stdin_lines(preset, hostile, "bash")

    assert len(lines) == 1
    assert "rm -rf" not in lines[0]
    assert "whoami" not in lines[0]
    assert lines[0].startswith("claude -p explain < ")
    path = Path(lines[0].split(" < ", 1)[1].strip('"'))
    assert path.read_text(encoding="utf-8") == hostile


def test_stdin_redirects_only_the_last_line() -> None:
    preset = Preset(
        name="Setup then run",
        lines=["cd /tmp", "source .venv/bin/activate", "claude -p explain"],
        kind=KIND_STDIN,
    )

    lines = stdin_lines(preset, "some text", "bash")

    assert lines[0] == "cd /tmp"
    assert lines[1] == "source .venv/bin/activate"
    assert lines[2].startswith("claude -p explain < ")


def test_posix_shells_use_input_redirection(tmp_path) -> None:
    path = tmp_path / "a dir" / "sel.txt"

    assert feed_from_file("wc -l", path, "bash") == f'wc -l < "{path.as_posix()}"'


def test_write_selection_file_round_trips_unicode_and_newlines() -> None:
    text = "line one\nline two\ntabs\tand émoji ✨"

    path = write_selection_file(text)

    assert path.read_text(encoding="utf-8") == text
    path.unlink()


def test_run_url_action_opens_the_browser_and_touches_no_terminal(monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(
        selection_actions.QDesktopServices, "openUrl", lambda url: opened.append(url)
    )
    tabs = FakeTabs()
    preset = Preset(name="Search", lines=[TEMPLATE], kind=KIND_URL)

    assert run_selection_action(preset, "qt webengine", tabs) is True

    # toString() pretty-decodes %20 for display; the encoded form is what
    # actually goes to the browser.
    assert opened[0].toEncoded().data().decode() == (
        "https://www.google.com/search?q=qt%20webengine"
    )
    assert tabs.active_calls == []
    assert tabs.new_tab_calls == []


def test_run_stdin_action_honors_new_tab_target() -> None:
    tabs = FakeTabs()
    preset = Preset(
        name="Explain", lines=["claude -p explain"], kind=KIND_STDIN, target="new_tab"
    )

    assert run_selection_action(preset, "some output", tabs, "bash") is True

    assert tabs.active_calls == []
    assert len(tabs.new_tab_calls) == 1
    shell, lines = tabs.new_tab_calls[0]
    assert shell is None
    assert lines[0].startswith("claude -p explain < ")


def test_run_stdin_action_honors_active_target() -> None:
    tabs = FakeTabs()
    preset = Preset(
        name="Explain", lines=["claude -p explain"], kind=KIND_STDIN, target="active"
    )

    run_selection_action(preset, "some output", tabs, "bash")

    assert len(tabs.active_calls) == 1
    assert tabs.new_tab_calls == []


def test_empty_selection_does_nothing() -> None:
    tabs = FakeTabs()
    preset = Preset(name="Search", lines=[TEMPLATE], kind=KIND_URL)

    assert run_selection_action(preset, "", tabs) is False

    assert tabs.active_calls == []
    assert tabs.new_tab_calls == []


def test_clean_old_selection_files_removes_only_stale_ones() -> None:
    fresh = write_selection_file("fresh")
    stale = write_selection_file("stale")
    old = time.time() - selection_actions.SELECTION_FILE_MAX_AGE_SECONDS - 60
    import os

    os.utime(stale, (old, old))

    removed = clean_old_selection_files()

    assert removed >= 1
    assert not stale.exists()
    assert fresh.exists()
    fresh.unlink()


def test_powershell_pipes_instead_of_redirecting(tmp_path) -> None:
    """Windows PowerShell reserves '<' - "The '<' operator is reserved for
    future use" - so redirection has to become a Get-Content pipe."""
    path = tmp_path / "sel.txt"

    for shell in ("powershell", "PowerShell", "pwsh"):
        line = feed_from_file("claude -p explain", path, shell)
        assert line == f'Get-Content -Raw "{path}" | claude -p explain'
        assert " < " not in line


def test_cmd_pipes_with_type(tmp_path) -> None:
    path = tmp_path / "sel.txt"

    assert feed_from_file("more", path, "cmd") == f'type "{path}" | more'


def test_wsl_gets_a_linux_path() -> None:
    assert wsl_path(Path(r"C:\Users\me\sel.txt")) == "/mnt/c/Users/me/sel.txt"
    assert feed_from_file("wc -l", Path(r"D:\tmp\s.txt"), "wsl") == (
        'wc -l < "/mnt/d/tmp/s.txt"'
    )


def test_shell_name_for_uses_the_active_tab_for_active_targets() -> None:
    class Terminal:
        shell_name = "bash"

    class Tabs:
        def active_terminal(self):
            return Terminal()

        def default_shell_name(self):
            return "powershell"

    active = Preset(name="a", lines=["x"], kind=KIND_STDIN, target="active")
    assert selection_actions.shell_name_for(active, Tabs()) == "bash"


def test_shell_name_for_asks_the_tabs_what_a_new_tab_would_open() -> None:
    """Not the OS default: Preferences can point new tabs at another shell."""

    class Tabs:
        def default_shell_name(self):
            return "powershell"

    new_tab = Preset(name="a", lines=["x"], kind=KIND_STDIN, target="new_tab")

    assert selection_actions.shell_name_for(new_tab, Tabs()) == "powershell"


def test_selection_directory_is_not_readable_by_other_users(tmp_path, monkeypatch) -> None:
    """On Linux the temp dir is shared, so another account could pre-create
    this path and swap in its own file for the command to read."""
    monkeypatch.setattr(tempfile, "gettempdir", lambda: str(tmp_path))

    path = selection_actions.write_selection_file("secret text")

    directory = path.parent
    assert path.read_text(encoding="utf-8") == "secret text"
    if os.name == "posix":
        assert stat.S_IMODE(directory.stat().st_mode) == 0o700
