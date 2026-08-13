from __future__ import annotations

from abc import abstractmethod

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication
from PySide6.QtWidgets import QMenu, QWidget

from qtxterm.preset_editor import PresetEditorDialog, editor_title
from qtxterm.presets import (
    CATEGORY_COMMANDS,
    CATEGORY_MACROS,
    CATEGORY_SELECTION,
    Preset,
    PresetStore,
    in_category,
)
from qtxterm.selection_actions import run_selection_action
from qtxterm.terminal_tabs import TerminalTabWidget

# Long enough to recognise what you highlighted, short enough not to turn the
# menu into a text dump.
PREVIEW_CHARS = 40


def selection_preview(selection: str) -> str:
    """A one-line, quoted, ellipsised label for `selection`."""
    if not selection:
        return "Nothing selected"
    collapsed = " ".join(selection.split())
    if len(collapsed) > PREVIEW_CHARS:
        collapsed = collapsed[: PREVIEW_CHARS - 1].rstrip() + "…"
    return f'Selected: "{collapsed}"'


def add_submenu(menu: QMenu, title: str) -> QMenu:
    """Add a submenu that survives Python garbage collection.

    Not `menu.addMenu(title)`: that hands the new QMenu to PySide6 with
    Python ownership, and `QAction.menu()` then binds its lifetime to
    whichever wrapper asked for it last - so a throwaway
    `action.menu().actions()` destroys the submenu for everyone, including
    any reference the parent thought it was holding. Constructing it with an
    explicit C++ parent instead leaves ownership in Qt, where it belongs.
    """
    submenu = QMenu(title, menu)
    menu.addMenu(submenu)
    return submenu


def clear_menu(menu: QMenu) -> None:
    """Empty `menu`, disposing of its submenus rather than orphaning them.

    QMenu.clear() drops the actions but leaves submenus parented to `menu`
    (see add_submenu), so a menu that rebuilds on every preset change would
    otherwise accumulate one dead QMenu child per reload.
    """
    menu.clear()
    for submenu in menu.findChildren(QMenu, options=Qt.FindDirectChildrenOnly):
        submenu.deleteLater()


def add_preset_actions(menu: QMenu, presets: list[Preset], run) -> None:
    """Fill `menu` with one action per preset, nesting grouped ones in submenus.

    Ungrouped presets sit at the top level, groups follow in name order.
    """
    groups: dict[str | None, list[Preset]] = {}
    for preset in presets:
        groups.setdefault(preset.group, []).append(preset)

    ordered_group_names = [name for name in groups if name is None] + sorted(
        name for name in groups if name is not None
    )

    for group_name in ordered_group_names:
        if group_name is None:
            target_menu = menu
        else:
            target_menu = add_submenu(menu, group_name)
        for preset in groups[group_name]:
            action = target_menu.addAction(preset.name)
            action.triggered.connect(lambda _checked=False, p=preset: run(p))


class _PresetCategoryMenu(QMenu):
    """Shared menu behavior for one Preset category (Commands or Macros):
    optionally lists presets matching `target` (grouped by `group`), plus
    New.../Manage <category>... actions. Subclasses differ in `target`,
    whether presets are listed (see `list_presets`), and what running a
    preset actually does (see `_run`).
    """

    def __init__(
        self,
        title: str,
        category: str,
        new_label: str,
        store: PresetStore,
        tabs: TerminalTabWidget,
        parent: QWidget | None = None,
        list_presets: bool = True,
    ) -> None:
        super().__init__(title, parent)
        self._category = category
        self._new_label = new_label
        self._store = store
        self._tabs = tabs
        self._list_presets = list_presets
        self._store.changed.connect(self.reload)
        self.reload()

    @abstractmethod
    def _run(self, preset: Preset) -> None:
        """Execute `preset` - active-terminal send vs new-tab script differ per category."""

    def reload(self) -> None:
        clear_menu(self)
        if self._list_presets:
            matching = in_category(self._store.presets, self._category)
            add_preset_actions(self, matching, self._run)
            if matching:
                self.addSeparator()

        new_action = self.addAction(self._new_label)
        new_action.triggered.connect(self._new_preset)
        # Reuses the dialog's own window title so the menu item and the window
        # it opens can't drift apart. "Preset" is an internal umbrella term -
        # what the user sees is the category they're actually in.
        manage_action = self.addAction(f"{editor_title(self._category)}...")
        manage_action.triggered.connect(self._open_editor)

    def _new_preset(self) -> None:
        dialog = PresetEditorDialog(
            self._store, self.parentWidget(), category=self._category, create_new=True
        )
        dialog.exec()

    def _open_editor(self) -> None:
        dialog = PresetEditorDialog(
            self._store, self.parentWidget(), category=self._category
        )
        dialog.exec()


class CommandsMenu(_PresetCategoryMenu):
    """Command-category menu (target: active): New/Manage actions plus the
    sidebar toggle - not a listing of individual Commands.

    Commands run from the sidebar (the curated, quick-access surface), not
    from this menu - listing every Command here too was redundant with it.
    Running one still sends it to the active terminal, same as a sidebar
    click, for callers that reuse `_run` (e.g. tests, `_new_preset`).
    """

    def __init__(
        self,
        store: PresetStore,
        tabs: TerminalTabWidget,
        sidebar_toggle_action: QAction | None = None,
        parent: QWidget | None = None,
    ) -> None:
        self._sidebar_toggle_action = sidebar_toggle_action
        super().__init__(
            "&Commands",
            CATEGORY_COMMANDS,
            "New Command...",
            store,
            tabs,
            parent,
            list_presets=False,
        )

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_active(preset.lines)

    def reload(self) -> None:
        super().reload()
        if self._sidebar_toggle_action is not None:
            self.addSeparator()
            self.addAction(self._sidebar_toggle_action)


class TerminalContextMenu(QMenu):
    """Right-click menu for a terminal: Copy/Paste plus a Command submenu.

    The Command submenu deliberately lists all Command presets, not just
    sidebar-pinned ones - the sidebar is the curated quick-access surface,
    this is the full list where your cursor already is. Running one sends it
    to the active terminal, same as a sidebar click.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._store = store
        self._tabs = tabs
        self._store.changed.connect(self.reload)
        # Selection and clipboard both change without the store changing, so
        # Copy/Paste availability is refreshed per open rather than in reload().
        self.aboutToShow.connect(self.refresh_enabled_state)
        self.reload()

    def reload(self) -> None:
        clear_menu(self)

        self._copy_action = self.addAction("Copy")
        self._copy_action.triggered.connect(self._copy)
        self._paste_action = self.addAction("Paste")
        self._paste_action.triggered.connect(self._paste)
        self.addSeparator()

        self._split_right_action = self.addAction("Split Right")
        self._split_right_action.triggered.connect(
            lambda: self._tabs.split_active(Qt.Orientation.Horizontal)
        )
        self._split_down_action = self.addAction("Split Down")
        self._split_down_action.triggered.connect(
            lambda: self._tabs.split_active(Qt.Orientation.Vertical)
        )
        self._move_pane_back_action = self.addAction("Move Pane Left")
        self._move_pane_back_action.triggered.connect(
            lambda: self._tabs.move_active_pane(forward=False)
        )
        self._move_pane_forward_action = self.addAction("Move Pane Right")
        self._move_pane_forward_action.triggered.connect(
            lambda: self._tabs.move_active_pane(forward=True)
        )
        self._pane_to_tab_action = self.addAction("Move Pane to New Tab")
        self._pane_to_tab_action.triggered.connect(
            self._tabs.move_active_pane_to_new_tab
        )
        self._close_pane_action = self.addAction("Close Pane")
        self._close_pane_action.triggered.connect(self._tabs.close_active_pane)
        self.addSeparator()

        self._run_menu = add_submenu(self, "Command")
        commands = in_category(self._store.presets, CATEGORY_COMMANDS)
        add_preset_actions(self._run_menu, commands, self._run)
        if not commands:
            empty = self._run_menu.addAction("No commands yet")
            empty.setEnabled(False)

        self._selection_menu = add_submenu(self, "Selection")
        self._build_selection_menu()

        self.refresh_enabled_state()

    def _build_selection_menu(self) -> None:
        menu = self._selection_menu
        # A preview of what will actually be sent, so a Selection Action -
        # which may put the text on the network - is never a surprise.
        self._preview_action = menu.addAction("")
        self._preview_action.setEnabled(False)
        menu.addSeparator()

        actions = in_category(self._store.presets, CATEGORY_SELECTION)
        add_preset_actions(menu, actions, self._run_on_selection)
        if not actions:
            # Creating and editing lives in the Selection menu bar entry, not
            # here -
            # this submenu is for doing something with the text right now.
            empty = menu.addAction("No selection actions - see the Selection menu")
            empty.setEnabled(False)

    def refresh_enabled_state(self) -> None:
        terminal = self._tabs.active_terminal()
        selection = terminal.selection if terminal else ""
        self._copy_action.setEnabled(bool(selection))
        self._paste_action.setEnabled(
            bool(terminal and QGuiApplication.clipboard().text())
        )
        self._selection_menu.setEnabled(bool(selection))
        self._preview_action.setText(selection_preview(selection))
        self._refresh_pane_actions()

    def _refresh_pane_actions(self) -> None:
        """Label pane moves for the axis they actually move along.

        "Move Pane Left" in a stacked split would be a lie, so the labels
        follow the splitter's orientation.
        """
        orientation = self._tabs.active_pane_orientation()
        vertical = orientation is Qt.Orientation.Vertical
        self._move_pane_back_action.setText(
            "Move Pane Up" if vertical else "Move Pane Left"
        )
        self._move_pane_forward_action.setText(
            "Move Pane Down" if vertical else "Move Pane Right"
        )
        self._move_pane_back_action.setEnabled(self._tabs.can_move_active_pane(False))
        self._move_pane_forward_action.setEnabled(self._tabs.can_move_active_pane(True))
        self._pane_to_tab_action.setEnabled(orientation is not None)

    def _run_on_selection(self, preset: Preset) -> None:
        terminal = self._tabs.active_terminal()
        if terminal is not None:
            run_selection_action(preset, terminal.selection, self._tabs)

    def _copy(self) -> None:
        terminal = self._tabs.active_terminal()
        if terminal is not None:
            terminal.copy_selection()

    def _paste(self) -> None:
        terminal = self._tabs.active_terminal()
        if terminal is not None:
            terminal.paste_from_clipboard()

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_active(preset.lines)


class SelectionMenu(_PresetCategoryMenu):
    """Selection Action menu bar entry: New/Manage only, not a listing.

    Same shape as CommandsMenu and for the same reason - running one lives
    where the text is, under the terminal's right-click Selection submenu,
    since an action is meaningless without a live selection. A menu bar
    item can't
    offer that, so it offers the management half instead.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            "&Selection",
            CATEGORY_SELECTION,
            "New Selection Action...",
            store,
            tabs,
            parent,
            list_presets=False,
        )

    def _run(self, preset: Preset) -> None:
        terminal = self._tabs.active_terminal()
        if terminal is not None:
            run_selection_action(preset, terminal.selection, self._tabs)


class MacrosMenu(_PresetCategoryMenu):
    """Menu of Macro-category presets (target: new_tab), grouped by `group`.

    Running one opens a new tab and feeds it the preset's lines as a script -
    see Preset.target docstring for why this is Macro-only, never Commands.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__(
            "&Macros", CATEGORY_MACROS, "New Macro...", store, tabs, parent
        )

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_new_tab(None, preset.lines)
