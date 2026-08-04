from __future__ import annotations

from abc import abstractmethod

from PySide6.QtWidgets import QMenu, QWidget

from mterm.preset_editor import PresetEditorDialog
from mterm.presets import Preset, PresetStore
from mterm.terminal_tabs import TerminalTabWidget


class _PresetCategoryMenu(QMenu):
    """Shared menu behavior for one Preset category (Commands or Macros):
    lists presets matching `target`, grouped by `group`, plus New.../Manage
    Presets... actions. Subclasses only differ in `target` and what running
    a preset actually does (see `_run`).
    """

    def __init__(
        self,
        title: str,
        target: str,
        new_label: str,
        store: PresetStore,
        tabs: TerminalTabWidget,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(title, parent)
        self._target = target
        self._new_label = new_label
        self._store = store
        self._tabs = tabs
        self._store.changed.connect(self.reload)
        self.reload()

    @abstractmethod
    def _run(self, preset: Preset) -> None:
        """Execute `preset` - active-terminal send vs new-tab script differ per category."""

    def reload(self) -> None:
        self.clear()
        # QMenu.addMenu() parents the submenu in C++, but without a Python-side
        # reference kept alive too, PySide6 can garbage-collect the wrapper (and
        # the underlying object with it) before it's ever clicked - keep one
        # here for as long as this reload()'s menu contents are current.
        self._submenus: list[QMenu] = []

        matching = [p for p in self._store.presets if p.target == self._target]
        groups: dict[str | None, list[Preset]] = {}
        for preset in matching:
            groups.setdefault(preset.group, []).append(preset)

        ordered_group_names = [name for name in groups if name is None] + sorted(
            name for name in groups if name is not None
        )
        for group_name in ordered_group_names:
            if group_name is None:
                target_menu = self
            else:
                target_menu = self.addMenu(group_name)
                self._submenus.append(target_menu)
            for preset in groups[group_name]:
                action = target_menu.addAction(preset.name)
                action.triggered.connect(lambda _checked=False, p=preset: self._run(p))

        if matching:
            self.addSeparator()
        new_action = self.addAction(self._new_label)
        new_action.triggered.connect(self._new_preset)
        manage_action = self.addAction("Manage Presets...")
        manage_action.triggered.connect(self._open_editor)

    def _new_preset(self) -> None:
        dialog = PresetEditorDialog(self._store, self.parentWidget(), new_preset_target=self._target)
        dialog.exec()

    def _open_editor(self) -> None:
        dialog = PresetEditorDialog(self._store, self.parentWidget())
        dialog.exec()


class CommandsMenu(_PresetCategoryMenu):
    """Menu of Command-category presets (target: active), grouped by `group`.

    Lists every Command, not just ones pinned to the sidebar - this is the
    comprehensive access point; the sidebar is the curated quick-access one.
    Running one sends it to the active terminal, same as a sidebar click.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__("&Commands", "active", "New Command...", store, tabs, parent)

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_active(preset.lines)


class MacrosMenu(_PresetCategoryMenu):
    """Menu of Macro-category presets (target: new_tab), grouped by `group`.

    Running one opens a new tab and feeds it the preset's lines as a script -
    see Preset.target docstring for why this is Macro-only, never Commands.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__("&Macros", "new_tab", "New Macro...", store, tabs, parent)

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_new_tab(None, preset.lines)
