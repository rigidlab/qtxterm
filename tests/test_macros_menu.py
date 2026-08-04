"""MacrosMenu: shows only target=new_tab presets, grouped, and runs them via
TerminalTabWidget.run_in_new_tab (mocked here so no real shell spawns)."""

from __future__ import annotations

from pathlib import Path

from mterm.macros_menu import MacrosMenu
from mterm.presets import Preset, PresetStore
from mterm.terminal_tabs import TerminalTabWidget


def make_store(tmp_path: Path, presets: list[Preset]) -> PresetStore:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = presets
    store.save()
    return store


def test_only_new_tab_presets_appear_as_actions(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Command", lines=["echo one"], target="active"),
            Preset(name="Macro", lines=["echo one", "echo two"], target="new_tab"),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)

    action_texts = [a.text() for a in menu.actions()]

    assert "Macro" in action_texts
    assert "Command" not in action_texts
    assert "New Macro..." in action_texts
    assert "Manage Presets..." in action_texts


def test_macros_are_grouped_into_submenus(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Deploy", lines=["a", "b"], group="Ops", target="new_tab"),
            Preset(name="Backup", lines=["a", "b"], group="Ops", target="new_tab"),
            Preset(name="Ad Hoc", lines=["a", "b"], target="new_tab"),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)

    submenu_action = next(a for a in menu.actions() if a.text() == "Ops")
    ops_menu = submenu_action.menu()
    assert [a.text() for a in ops_menu.actions()] == ["Deploy", "Backup"]
    assert "Ad Hoc" in [a.text() for a in menu.actions()]


def test_running_a_macro_calls_run_in_new_tab(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path, [Preset(name="Deploy", lines=["a", "b"], target="new_tab")]
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    calls = []
    tabs.run_in_new_tab = lambda shell, lines: calls.append((shell, lines))
    menu = MacrosMenu(store, tabs)

    action = next(a for a in menu.actions() if a.text() == "Deploy")
    action.trigger()

    assert calls == [(None, ["a", "b"])]


def test_store_changes_auto_reload_the_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)
    assert "New Macro Item" not in [a.text() for a in menu.actions()]

    store.add(Preset(name="New Macro Item", lines=["a", "b"], target="new_tab"))

    assert "New Macro Item" in [a.text() for a in menu.actions()]
