"""ShellPreferenceStore: which shell new tabs open with, persisted by label."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from qtxterm import shell_prefs
from qtxterm.shell_prefs import SYSTEM_DEFAULT, ShellPreferenceStore
from qtxterm.window_state import make_settings

FAKE_SHELLS = [
    ("PowerShell", r"C:\fake\powershell.exe"),
    ("Git Bash", r"C:\fake\Git\bin\bash.exe"),
    ("WSL: Ubuntu-22.04", [r"C:\fake\wsl.exe", "-d", "Ubuntu-22.04"]),
]


def store_for(tmp_path: Path) -> ShellPreferenceStore:
    return ShellPreferenceStore(make_settings(tmp_path / "s.ini"))


def fake_lookup(shells=None):
    """Stand-in for shells.shell_for_label over a fixed list."""
    table = dict(shells if shells is not None else FAKE_SHELLS)
    return lambda label: table.get(label)


def test_defaults_to_the_system_shell(tmp_path: Path) -> None:
    store = store_for(tmp_path)

    assert store.label == SYSTEM_DEFAULT
    assert store.resolve() is None


def test_resolves_a_saved_label_to_its_command(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup())
    store = store_for(tmp_path)

    store.save("WSL: Ubuntu-22.04")

    assert store.resolve() == [r"C:\fake\wsl.exe", "-d", "Ubuntu-22.04"]


def test_choice_persists_across_instances(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup())
    settings = make_settings(tmp_path / "s.ini")
    ShellPreferenceStore(settings).save("Git Bash")

    reopened = ShellPreferenceStore(QSettings(settings.fileName(), settings.format()))

    assert reopened.label == "Git Bash"
    assert reopened.resolve() == r"C:\fake\Git\bin\bash.exe"


def test_falls_back_when_the_saved_shell_is_gone(tmp_path, monkeypatch) -> None:
    """A WSL distro can be uninstalled after being chosen - that must degrade
    to the system default, not fail to open a tab."""
    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup())
    store = store_for(tmp_path)
    store.save("WSL: Ubuntu-22.04")

    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup(FAKE_SHELLS[:1]))

    assert store.resolve() is None
    assert store.resolved_label() == "System default"


def test_saving_emits_changed(tmp_path, qtbot, monkeypatch) -> None:
    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup())
    store = store_for(tmp_path)

    with qtbot.waitSignal(store.changed, timeout=1000):
        store.save("Git Bash")


def test_system_default_label_names_the_actual_shell() -> None:
    label = shell_prefs.system_default_label()

    assert label.startswith("System default (")
    assert label.endswith(")")


def test_resolve_enumerates_shells_once_not_per_tab(tmp_path, monkeypatch) -> None:
    """resolve() runs on every new tab; resolving a WSL label shells out to
    `wsl.exe -l -q` with a 5s timeout."""
    calls = []
    lookup = fake_lookup()

    def counted(label):
        calls.append(label)
        return lookup(label)

    monkeypatch.setattr(shell_prefs, "shell_for_label", counted)
    store = store_for(tmp_path)
    store.save("Git Bash")

    for _ in range(10):
        assert store.resolve() == r"C:\fake\Git\bin\bash.exe"

    assert len(calls) == 1


def test_changing_the_preference_re_resolves(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(shell_prefs, "shell_for_label", fake_lookup())
    store = store_for(tmp_path)
    store.save("Git Bash")
    assert store.resolve() == r"C:\fake\Git\bin\bash.exe"

    store.save("PowerShell")

    assert store.resolve() == r"C:\fake\powershell.exe"
