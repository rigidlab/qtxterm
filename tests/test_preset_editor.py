"""PresetEditorDialog: New/Save/Delete against a real PresetStore (tmp_path-backed).

Each dialog instance is scoped to one category (target="active" for Commands,
target="new_tab" for Macros) - it only lists, creates, and edits presets of
that category.
"""

from __future__ import annotations

from pathlib import Path

from qtxterm.preset_editor import PresetEditorDialog
from qtxterm.presets import Preset, PresetStore


def make_store(tmp_path: Path) -> PresetStore:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = []
    store.save()
    return store


def test_new_preset_appends_and_selects_it(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, target="active")
    qtbot.addWidget(dialog)

    dialog._new_preset()

    assert len(store.presets) == 1
    assert dialog._list.currentRow() == 0
    assert dialog._name_edit.text() == "New Command"


def test_editing_fields_and_saving_persists_changes(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="Original", lines=["echo original"]))
    dialog = PresetEditorDialog(store, target="active")
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._name_edit.setText("Renamed")
    dialog._group_edit.setText("MyGroup")
    dialog._lines_edit.setPlainText("echo one line")
    dialog._sidebar_check.setChecked(True)
    dialog._save_current()

    saved = store.presets[0]
    assert saved.name == "Renamed"
    assert saved.group == "MyGroup"
    assert saved.lines == ["echo one line"]
    assert saved.target == "active"
    assert saved.show_in_sidebar is True

    reloaded = PresetStore(path=store.path)
    assert reloaded.presets[0].name == "Renamed"


def test_macro_dialog_has_no_sidebar_checkbox(qtbot, tmp_path: Path) -> None:
    """Macros never show in the sidebar, so the Macro editor doesn't offer
    the option at all."""
    store = make_store(tmp_path)
    store.add(Preset(name="Original", lines=["echo original"], target="new_tab"))
    dialog = PresetEditorDialog(store, target="new_tab")
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    assert dialog._sidebar_check.parent() is None

    dialog._lines_edit.setPlainText("echo one\necho two")
    dialog._save_current()

    saved = store.presets[0]
    assert saved.lines == ["echo one", "echo two"]
    assert saved.target == "new_tab"
    assert saved.show_in_sidebar is False


def test_new_macro_defaults_to_new_tab_target(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, target="new_tab")
    qtbot.addWidget(dialog)

    dialog._new_preset()

    assert store.presets[0].target == "new_tab"
    assert dialog._name_edit.text() == "New Macro"


def test_command_dialog_only_lists_command_presets(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="A Command", lines=["echo a"], target="active"))
    store.add(Preset(name="A Macro", lines=["echo b"], target="new_tab"))
    dialog = PresetEditorDialog(store, target="active")
    qtbot.addWidget(dialog)

    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]

    assert items == ["A Command"]


def test_macro_dialog_only_lists_macro_presets(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="A Command", lines=["echo a"], target="active"))
    store.add(Preset(name="A Macro", lines=["echo b"], target="new_tab"))
    dialog = PresetEditorDialog(store, target="new_tab")
    qtbot.addWidget(dialog)

    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]

    assert items == ["A Macro"]


def test_delete_removes_preset(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="ToDelete", lines=["echo bye"]))
    dialog = PresetEditorDialog(store, target="active")
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._delete_preset()

    assert store.presets == []


def test_blank_lines_are_dropped_and_empty_lines_fall_back(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="X", lines=["echo x"]))
    dialog = PresetEditorDialog(store, target="active")
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._lines_edit.setPlainText("\n  \necho real\n\n")
    dialog._save_current()

    assert store.presets[0].lines == ["echo real"]
