from __future__ import annotations

from PySide6.QtWidgets import QMenu, QWidget

from mterm.preset_editor import PresetEditorDialog
from mterm.presets import Preset, PresetStore
from mterm.terminal_tabs import TerminalTabWidget


class MacrosMenu(QMenu):
    """Menu of Macro-category presets (target: new_tab), grouped by `group`.

    Running one opens a new tab and feeds it the preset's lines as a script -
    see Preset.target docstring for why this is Macro-only, never Commands.
    """

    def __init__(
        self, store: PresetStore, tabs: TerminalTabWidget, parent: QWidget | None = None
    ) -> None:
        super().__init__("&Macros", parent)
        self._store = store
        self._tabs = tabs
        self._store.changed.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        self.clear()
        # QMenu.addMenu() parents the submenu in C++, but without a Python-side
        # reference kept alive too, PySide6 can garbage-collect the wrapper (and
        # the underlying object with it) before it's ever clicked - keep one
        # here for as long as this reload()'s menu contents are current.
        self._submenus: list[QMenu] = []

        macros = [p for p in self._store.presets if p.target == "new_tab"]
        groups: dict[str | None, list[Preset]] = {}
        for preset in macros:
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
                action.triggered.connect(
                    lambda _checked=False, p=preset: self._run(p)
                )

        if macros:
            self.addSeparator()
        new_macro_action = self.addAction("New Macro...")
        new_macro_action.triggered.connect(self._new_macro)
        manage_action = self.addAction("Manage Presets...")
        manage_action.triggered.connect(self._open_editor)

    def _run(self, preset: Preset) -> None:
        self._tabs.run_in_new_tab(None, preset.lines)

    def _new_macro(self) -> None:
        dialog = PresetEditorDialog(self._store, self.parentWidget(), new_preset_target="new_tab")
        dialog.exec()

    def _open_editor(self) -> None:
        dialog = PresetEditorDialog(self._store, self.parentWidget())
        dialog.exec()
