"""CommandsMenu/MacrosMenu: each shows only its own target category, grouped,
and runs presets via TerminalTabWidget (mocked so no real shell spawns)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QAction

from qtxterm.preset_menu import CommandsMenu, MacrosMenu
from qtxterm.presets import Preset, PresetStore
from qtxterm.terminal_tabs import TerminalTabWidget


def make_store(tmp_path: Path, presets: list[Preset]) -> PresetStore:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = presets
    store.save()
    return store


def test_only_new_tab_presets_appear_in_macros_menu(qtbot, tmp_path: Path) -> None:
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


def test_only_active_presets_appear_in_commands_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Command", lines=["echo one"], target="active"),
            Preset(name="Macro", lines=["echo one", "echo two"], target="new_tab"),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)

    action_texts = [a.text() for a in menu.actions()]

    assert "Command" in action_texts
    assert "Macro" not in action_texts
    assert "New Command..." in action_texts
    assert "Manage Presets..." in action_texts


def test_commands_menu_includes_presets_not_pinned_to_sidebar(qtbot, tmp_path: Path) -> None:
    """Unlike the sidebar, the Commands menu is the full list - it doesn't
    filter on show_in_sidebar."""
    store = make_store(
        tmp_path,
        [Preset(name="Hidden From Sidebar", lines=["echo x"], show_in_sidebar=False)],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)

    assert "Hidden From Sidebar" in [a.text() for a in menu.actions()]


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


def test_commands_are_grouped_into_submenus(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Status", lines=["git status"], group="Git"),
            Preset(name="Pull", lines=["git pull"], group="Git"),
            Preset(name="Clear", lines=["clear"]),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)

    submenu_action = next(a for a in menu.actions() if a.text() == "Git")
    git_menu = submenu_action.menu()
    assert [a.text() for a in git_menu.actions()] == ["Status", "Pull"]
    assert "Clear" in [a.text() for a in menu.actions()]


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


def test_running_a_command_calls_run_in_active(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [Preset(name="Status", lines=["git status"])])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    calls = []
    tabs.run_in_active = lambda lines: calls.append(lines)
    menu = CommandsMenu(store, tabs)

    action = next(a for a in menu.actions() if a.text() == "Status")
    action.trigger()

    assert calls == [["git status"]]


def test_store_changes_auto_reload_the_macros_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)
    assert "New Macro Item" not in [a.text() for a in menu.actions()]

    store.add(Preset(name="New Macro Item", lines=["a", "b"], target="new_tab"))

    assert "New Macro Item" in [a.text() for a in menu.actions()]


def test_store_changes_auto_reload_the_commands_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)
    assert "New Command Item" not in [a.text() for a in menu.actions()]

    store.add(Preset(name="New Command Item", lines=["echo hi"]))

    assert "New Command Item" in [a.text() for a in menu.actions()]


def test_sidebar_toggle_action_present_and_survives_reload(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    toggle_action = QAction("Show Sidebar")
    toggle_action.setCheckable(True)
    toggle_action.setChecked(True)
    menu = CommandsMenu(store, tabs, sidebar_toggle_action=toggle_action)

    assert toggle_action in menu.actions()

    store.add(Preset(name="Triggers Reload", lines=["echo hi"]))

    assert toggle_action in menu.actions()


def test_commands_menu_without_sidebar_toggle_action_omits_it(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)

    menu = CommandsMenu(store, tabs)

    assert "Show Sidebar" not in [a.text() for a in menu.actions()]
