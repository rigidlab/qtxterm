"""CommandsMenu/MacrosMenu: the Macros menu lists its presets grouped; the
Commands menu is management-only (New/Manage/Show Sidebar) since Commands
run from the sidebar instead. Runs presets via TerminalTabWidget (mocked so
no real shell spawns)."""

from __future__ import annotations

import gc
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu

from PySide6.QtWidgets import QDialog

from qtxterm import preset_menu, selection_actions
from qtxterm.preset_menu import (
    CommandsMenu,
    MacrosMenu,
    SelectionMenu,
    TerminalContextMenu,
    selection_preview,
)
from qtxterm.menu_prefs import (
    SECTION_CLIPBOARD,
    SECTION_COMMAND,
    SECTION_PANE,
    SECTION_SELECTION,
    ContextMenuOrderStore,
)
from qtxterm.presets import (
    CATEGORY_SELECTION,
    INPUT_SELECTION,
    KIND_URL,
    Preset,
    PresetStore,
)
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
    assert "Manage Macros..." in action_texts


def test_commands_menu_lists_no_individual_presets(qtbot, tmp_path: Path) -> None:
    """Commands run from the sidebar, not this menu - it's management-only,
    regardless of how many Command presets exist."""
    store = make_store(
        tmp_path,
        [
            Preset(name="Status", lines=["git status"], group="Git"),
            Preset(name="Clear", lines=["clear"]),
            Preset(name="Macro", lines=["a", "b"], target="new_tab"),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)

    action_texts = [a.text() for a in menu.actions()]

    assert action_texts == ["New Command...", "Manage Commands..."]
    assert "Git" not in action_texts


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


def test_commands_menu_run_sends_to_active_terminal(qtbot, tmp_path: Path) -> None:
    """CommandsMenu._run is exercised by the sidebar (via the same
    PresetStore/TerminalTabWidget wiring) rather than a menu action, since
    Commands no longer list here."""
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    calls = []
    tabs.run_in_active = lambda lines: calls.append(lines)
    menu = CommandsMenu(store, tabs)

    menu._run(Preset(name="Status", lines=["git status"]))

    assert calls == [["git status"]]


def test_store_changes_auto_reload_the_macros_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)
    assert "New Macro Item" not in [a.text() for a in menu.actions()]

    store.add(Preset(name="New Macro Item", lines=["a", "b"], target="new_tab"))

    assert "New Macro Item" in [a.text() for a in menu.actions()]


def test_store_changes_reload_the_commands_menu_without_error(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = CommandsMenu(store, tabs)

    store.add(Preset(name="New Command Item", lines=["echo hi"]))

    assert "New Command Item" not in [a.text() for a in menu.actions()]
    assert [a.text() for a in menu.actions()] == [
        "New Command...",
        "Manage Commands...",
    ]


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


def run_menu_of(menu: TerminalContextMenu):
    action = next(a for a in menu.actions() if a.text() == "Command")
    return action.menu()


def test_terminal_context_menu_lists_commands_grouped(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Status", lines=["git status"], group="Git"),
            Preset(name="Pull", lines=["git pull"], group="Git"),
            Preset(name="Clear", lines=["clear"]),
            Preset(name="Deploy", lines=["a", "b"], target="new_tab"),
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)

    run_menu = run_menu_of(menu)
    texts = [a.text() for a in run_menu.actions()]
    assert "Clear" in texts
    assert "Git" in texts
    assert "Deploy" not in texts  # a Macro, not a Command

    git_menu = next(a for a in run_menu.actions() if a.text() == "Git").menu()
    assert [a.text() for a in git_menu.actions()] == ["Status", "Pull"]


def test_terminal_context_menu_lists_commands_not_pinned_to_the_sidebar(
    qtbot, tmp_path: Path
) -> None:
    store = make_store(
        tmp_path, [Preset(name="Hidden", lines=["echo hi"], show_in_sidebar=False)]
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)

    assert "Hidden" in [a.text() for a in run_menu_of(menu).actions()]


def test_terminal_context_menu_action_sends_to_active_terminal(
    qtbot, tmp_path: Path
) -> None:
    store = make_store(tmp_path, [Preset(name="Status", lines=["git status"])])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    calls = []
    tabs.run_in_active = lambda lines: calls.append(lines)
    menu = TerminalContextMenu(store, tabs)

    next(a for a in run_menu_of(menu).actions() if a.text() == "Status").trigger()

    assert calls == [["git status"]]


def test_terminal_context_menu_shows_a_disabled_hint_when_empty(
    qtbot, tmp_path: Path
) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)

    actions = run_menu_of(menu).actions()
    assert [a.text() for a in actions] == ["No commands yet"]
    assert actions[0].isEnabled() is False


def test_terminal_context_menu_reloads_on_store_change(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)

    store.add(Preset(name="Fresh", lines=["echo hi"]))

    assert "Fresh" in [a.text() for a in run_menu_of(menu).actions()]


def test_reloading_does_not_accumulate_submenus(qtbot, tmp_path: Path) -> None:
    """Submenus are parented to the menu (see add_submenu), so clear() alone
    would orphan one QMenu child per reload rather than disposing of it."""
    store = make_store(tmp_path, [Preset(name="Status", lines=["a"], group="Git")])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)
    baseline = len(menu.findChildren(QMenu))

    for _ in range(5):
        menu.reload()
    # deleteLater() only takes effect when the event loop processes
    # DeferredDelete, which processEvents() alone does not do.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    assert len(menu.findChildren(QMenu)) == baseline


def test_submenu_survives_a_throwaway_action_menu_lookup(qtbot, tmp_path: Path) -> None:
    """QAction.menu() binds the submenu's lifetime to the returned wrapper
    unless the submenu has an explicit C++ parent - so a discarded lookup
    used to destroy it for every other holder too."""
    store = make_store(tmp_path, [Preset(name="Status", lines=["a"])])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = TerminalContextMenu(store, tabs)

    def throwaway_lookup() -> None:
        next(a for a in menu.actions() if a.text() == "Command").menu()

    throwaway_lookup()
    gc.collect()

    assert [a.text() for a in run_menu_of(menu).actions()] == ["Status"]


class FakeTerminal:
    def __init__(self, selection: str = "") -> None:
        self.selection = selection
        self.copied = 0
        self.pasted = 0

    def parentWidget(self):  # noqa: N802 - stands in for a QWidget
        """Unsplit: no splitter above it, so pane moves are unavailable."""
        return None

    def copy_selection(self) -> bool:
        self.copied += 1
        return bool(self.selection)

    def paste_from_clipboard(self) -> None:
        self.pasted += 1


def context_menu_with(qtbot, tmp_path: Path, terminal, presets=None):
    store = make_store(tmp_path, presets or [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    tabs.active_terminal = lambda: terminal
    return TerminalContextMenu(store, tabs)


def action_named(menu: TerminalContextMenu, name: str):
    return next(a for a in menu.actions() if a.text() == name)


def test_context_menu_top_level_is_four_groups(qtbot, tmp_path: Path):
    """Pane actions live in their own submenu rather than six flat entries."""
    menu = context_menu_with(qtbot, tmp_path, FakeTerminal())

    texts = [a.text() for a in menu.actions() if not a.isSeparator()]
    assert texts == ["Copy", "Paste", "Pane", "Command", "Selection"]


def test_pane_submenu_holds_every_pane_action(qtbot, tmp_path: Path):
    menu = context_menu_with(qtbot, tmp_path, FakeTerminal())

    pane = next(a for a in menu.actions() if a.text() == "Pane").menu()
    texts = [a.text() for a in pane.actions() if not a.isSeparator()]

    assert texts == [
        "Split Right",
        "Split Down",
        "Move Left",
        "Move Right",
        "Move to New Tab",
        "Close",
    ]


def test_copy_is_disabled_without_a_selection(qtbot, tmp_path: Path) -> None:
    menu = context_menu_with(qtbot, tmp_path, FakeTerminal(selection=""))

    menu.refresh_enabled_state()

    assert action_named(menu, "Copy").isEnabled() is False


def test_copy_is_enabled_and_copies_when_text_is_selected(qtbot, tmp_path: Path):
    terminal = FakeTerminal(selection="hello")
    menu = context_menu_with(qtbot, tmp_path, terminal)

    menu.refresh_enabled_state()
    copy = action_named(menu, "Copy")
    assert copy.isEnabled() is True
    copy.trigger()

    assert terminal.copied == 1


def test_paste_follows_the_clipboard_and_pastes(qtbot, tmp_path: Path) -> None:
    terminal = FakeTerminal()
    menu = context_menu_with(qtbot, tmp_path, terminal)

    QGuiApplication.clipboard().setText("")
    menu.refresh_enabled_state()
    assert action_named(menu, "Paste").isEnabled() is False

    QGuiApplication.clipboard().setText("something")
    menu.refresh_enabled_state()
    paste = action_named(menu, "Paste")
    assert paste.isEnabled() is True
    paste.trigger()

    assert terminal.pasted == 1


def test_copy_and_paste_disabled_with_no_open_tab(qtbot, tmp_path: Path) -> None:
    menu = context_menu_with(qtbot, tmp_path, None)
    QGuiApplication.clipboard().setText("something")

    menu.refresh_enabled_state()

    assert action_named(menu, "Copy").isEnabled() is False
    assert action_named(menu, "Paste").isEnabled() is False


def test_enabled_state_refreshes_when_the_menu_opens(qtbot, tmp_path: Path) -> None:
    """Selection and clipboard change without the store changing, so the
    refresh has to hang off aboutToShow rather than reload()."""
    terminal = FakeTerminal(selection="")
    menu = context_menu_with(qtbot, tmp_path, terminal)
    assert action_named(menu, "Copy").isEnabled() is False

    terminal.selection = "now selected"
    menu.aboutToShow.emit()

    assert action_named(menu, "Copy").isEnabled() is True


def test_use_selection_lists_selection_actions_and_manage_entries(qtbot, tmp_path):
    menu = context_menu_with(
        qtbot,
        tmp_path,
        FakeTerminal(selection="some text"),
        presets=[
            Preset(name="Search", lines=["https://x/?q={selection}"],
                   input=INPUT_SELECTION, kind=KIND_URL),
            Preset(name="A Command", lines=["git status"]),
        ],
    )

    submenu = next(a for a in menu.actions() if a.text() == "Selection").menu()
    texts = [a.text() for a in submenu.actions() if not a.isSeparator()]

    assert "Search" in texts
    assert "A Command" not in texts  # a Command, not a Selection Action
    # Creating/editing lives in the Selection menu bar entry, not here.
    assert "New Selection Action..." not in texts
    assert "Manage Selection Actions..." not in texts


def test_use_selection_is_disabled_without_a_selection(qtbot, tmp_path: Path) -> None:
    menu = context_menu_with(qtbot, tmp_path, FakeTerminal(selection=""))

    menu.refresh_enabled_state()

    assert next(a for a in menu.actions() if a.text() == "Selection").isEnabled() is False


def test_use_selection_previews_the_selected_text(qtbot, tmp_path: Path) -> None:
    terminal = FakeTerminal(selection="  git push   origin main\n")
    menu = context_menu_with(qtbot, tmp_path, terminal)

    menu.refresh_enabled_state()

    assert menu._preview_action.text() == 'Selected: "git push origin main"'
    assert menu._preview_action.isEnabled() is False


def test_selection_preview_collapses_and_truncates() -> None:
    assert selection_preview("") == "Nothing selected"
    assert selection_preview("a\n  b\tc") == 'Selected: "a b c"'
    long_preview = selection_preview("x" * 200)
    assert long_preview.endswith('…"')
    assert len(long_preview) < 60


def test_running_a_selection_action_passes_the_live_selection(qtbot, tmp_path, monkeypatch):
    opened = []
    monkeypatch.setattr(
        selection_actions.QDesktopServices, "openUrl", lambda url: opened.append(url)
    )
    terminal = FakeTerminal(selection="needle")
    menu = context_menu_with(
        qtbot,
        tmp_path,
        terminal,
        presets=[
            Preset(name="Search", lines=["https://x/?q={selection}"],
                   input=INPUT_SELECTION, kind=KIND_URL)
        ],
    )

    submenu = next(a for a in menu.actions() if a.text() == "Selection").menu()
    next(a for a in submenu.actions() if a.text() == "Search").trigger()

    assert opened[0].toEncoded().data().decode() == "https://x/?q=needle"


def test_selection_menu_is_management_only(qtbot, tmp_path: Path) -> None:
    """Running an action needs a live selection, which a menu bar item can't
    offer - it carries the management half instead, like CommandsMenu."""
    store = make_store(
        tmp_path,
        [
            Preset(
                name="Search",
                lines=["https://x/?q={selection}"],
                input=INPUT_SELECTION,
                kind=KIND_URL,
            )
        ],
    )
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = SelectionMenu(store, tabs)

    texts = [a.text() for a in menu.actions() if not a.isSeparator()]

    assert texts == ["New Selection Action...", "Manage Selection Actions..."]
    assert "Search" not in texts


def test_selection_menu_new_opens_the_selection_editor(qtbot, tmp_path, monkeypatch):
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = SelectionMenu(store, tabs)
    opened = []
    monkeypatch.setattr(
        preset_menu.PresetEditorDialog,
        "__init__",
        lambda self, s, p=None, category=None, create_new=False: (
            opened.append((category, create_new)),
            QDialog.__init__(self, p),
        )[1],
    )
    monkeypatch.setattr(preset_menu.PresetEditorDialog, "exec", lambda self: 0)

    next(a for a in menu.actions() if a.text() == "New Selection Action...").trigger()
    next(
        a for a in menu.actions() if a.text() == "Manage Selection Actions..."
    ).trigger()

    assert opened == [(CATEGORY_SELECTION, True), (CATEGORY_SELECTION, False)]


def submenu_titles(menu: TerminalContextMenu) -> list[str]:
    return [a.text() for a in menu.actions() if a.menu() is not None]


def test_context_menu_submenus_follow_the_saved_order(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    order_store = ContextMenuOrderStore(
        QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    )
    order_store.save(
        [SECTION_SELECTION, SECTION_COMMAND, SECTION_PANE, SECTION_CLIPBOARD]
    )

    menu = TerminalContextMenu(store, tabs, order_store=order_store)

    assert submenu_titles(menu) == ["Selection", "Command", "Pane"]


def test_context_menu_reorders_itself_when_the_preference_changes(
    qtbot, tmp_path: Path
) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    order_store = ContextMenuOrderStore(
        QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    )
    menu = TerminalContextMenu(store, tabs, order_store=order_store)
    assert submenu_titles(menu) == ["Pane", "Command", "Selection"]

    order_store.save([SECTION_COMMAND, SECTION_PANE, SECTION_SELECTION])

    assert submenu_titles(menu) == ["Command", "Pane", "Selection"]


def test_copy_and_paste_lead_by_default(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)

    menu = TerminalContextMenu(store, tabs)

    texts = [a.text() for a in menu.actions() if a.text()]
    assert texts[:2] == ["Copy", "Paste"]


def test_copy_and_paste_can_be_moved_below_the_submenus(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    order_store = ContextMenuOrderStore(
        QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    )
    order_store.save(
        [SECTION_PANE, SECTION_COMMAND, SECTION_SELECTION, SECTION_CLIPBOARD]
    )

    menu = TerminalContextMenu(store, tabs, order_store=order_store)

    texts = [a.text() for a in menu.actions() if a.text()]
    assert texts == ["Pane", "Command", "Selection", "Copy", "Paste"]


def test_moved_copy_paste_keeps_a_separator_from_the_submenus(
    qtbot, tmp_path: Path
) -> None:
    """Two bare actions butting straight against a list of submenus read as
    part of it."""
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    order_store = ContextMenuOrderStore(
        QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)
    )
    order_store.save(
        [SECTION_PANE, SECTION_CLIPBOARD, SECTION_COMMAND, SECTION_SELECTION]
    )

    menu = TerminalContextMenu(store, tabs, order_store=order_store)

    shape = [
        "---" if a.isSeparator() else a.text()
        for a in menu.actions()
    ]
    assert shape == ["Pane", "---", "Copy", "Paste", "---", "Command", "Selection"]


def test_context_menu_without_an_order_store_uses_the_default_order(
    qtbot, tmp_path: Path
) -> None:
    store = make_store(tmp_path, [])
    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)

    menu = TerminalContextMenu(store, tabs)

    assert submenu_titles(menu) == ["Pane", "Command", "Selection"]
