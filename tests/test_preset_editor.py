"""PresetEditorDialog: New/Save/Delete against a real PresetStore (tmp_path-backed).

Each dialog instance is scoped to one category (Commands, Macros, or
Selection Actions) - it only lists, creates, and edits presets of
that category.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog

from qtxterm import preset_editor
from qtxterm.preset_editor import PresetEditorDialog
from qtxterm.preset_menu import MacrosMenu
from qtxterm.terminal_tabs import TerminalTabWidget
from qtxterm.presets import (
    STEP_DOWN,
    STEP_RIGHT,
    STEP_TAB,
    macro_steps,
    CATEGORY_COMMANDS,
    CATEGORY_MACROS,
    CATEGORY_SELECTION,
    INPUT_SELECTION,
    KIND_STDIN,
    KIND_URL,
    SELECTION_PLACEHOLDER,
    Preset,
    PresetStore,
    category_of,
)


def make_store(tmp_path: Path) -> PresetStore:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = []
    store.save()
    return store


def test_new_preset_appends_and_selects_it(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)

    dialog._new_preset()

    assert len(store.presets) == 1
    assert dialog._list.currentRow() == 0
    assert dialog._name_edit.text() == "New Command"


def test_editing_fields_and_saving_persists_changes(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="Original", lines=["echo original"]))
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
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
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
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
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    dialog._new_preset()

    assert store.presets[0].target == "new_tab"
    assert dialog._name_edit.text() == "New Macro"


def test_command_dialog_only_lists_command_presets(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="A Command", lines=["echo a"], target="active"))
    store.add(Preset(name="A Macro", lines=["echo b"], target="new_tab"))
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)

    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]

    assert items == ["A Command"]


def test_macro_dialog_only_lists_macro_presets(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="A Command", lines=["echo a"], target="active"))
    store.add(Preset(name="A Macro", lines=["echo b"], target="new_tab"))
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    items = [dialog._list.item(i).text() for i in range(dialog._list.count())]

    assert items == ["A Macro"]


def test_delete_removes_preset(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="ToDelete", lines=["echo bye"]))
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._delete_preset()

    assert store.presets == []


def test_blank_lines_are_dropped_and_empty_lines_fall_back(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="X", lines=["echo x"]))
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._lines_edit.setPlainText("\n  \necho real\n\n")
    dialog._save_current()

    assert store.presets[0].lines == ["echo real"]


def test_selection_dialog_only_lists_selection_actions(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.add(Preset(name="A Command", lines=["echo a"], target="active"))
    store.add(
        Preset(
            name="An Action",
            lines=["https://x/?q={selection}"],
            input=INPUT_SELECTION,
            kind=KIND_URL,
        )
    )
    dialog = PresetEditorDialog(store, category=CATEGORY_SELECTION)
    qtbot.addWidget(dialog)

    assert [dialog._list.item(i).text() for i in range(dialog._list.count())] == [
        "An Action"
    ]


def test_new_selection_action_defaults_to_a_url_template(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_SELECTION)
    qtbot.addWidget(dialog)

    dialog._new_preset()

    created = store.presets[-1]
    assert created.input == INPUT_SELECTION
    assert created.kind == KIND_URL
    assert SELECTION_PLACEHOLDER in created.lines[0]


def test_saving_a_stdin_action_keeps_kind_and_target(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_SELECTION)
    qtbot.addWidget(dialog)
    dialog._new_preset()

    dialog._name_edit.setText("Explain")
    dialog._lines_edit.setPlainText("claude -p explain")
    dialog._select_data(dialog._kind_combo, KIND_STDIN)
    dialog._select_data(dialog._target_combo, "active")
    dialog._save_current()

    saved = store.presets[-1]
    assert saved.kind == KIND_STDIN
    assert saved.target == "active"
    assert saved.input == INPUT_SELECTION
    assert saved.show_in_sidebar is False


def test_target_row_is_hidden_for_url_actions(qtbot, tmp_path: Path) -> None:
    """A url action opens a browser, so "which terminal" doesn't apply."""
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_SELECTION)
    qtbot.addWidget(dialog)
    dialog.show()

    dialog._select_data(dialog._kind_combo, KIND_URL)
    assert dialog._target_combo.isVisible() is False

    dialog._select_data(dialog._kind_combo, KIND_STDIN)
    assert dialog._target_combo.isVisible() is True


def test_selection_dialog_has_no_sidebar_checkbox(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_SELECTION)
    qtbot.addWidget(dialog)
    dialog.show()

    assert dialog._sidebar_check.isVisible() is False


def test_save_and_close_persists_the_edit_then_closes(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)
    dialog._new_preset()
    dialog._name_edit.setText("Deploy")
    dialog._lines_edit.setPlainText("./deploy.sh")

    dialog._save_and_close_button.click()

    assert store.presets[-1].name == "Deploy"
    assert store.presets[-1].lines == ["./deploy.sh"]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_plain_save_keeps_the_dialog_open(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)
    dialog._new_preset()
    dialog._name_edit.setText("Still Editing")

    dialog._save_button.click()

    assert store.presets[-1].name == "Still Editing"
    assert dialog.result() != QDialog.DialogCode.Accepted


def test_save_and_close_with_nothing_selected_still_closes(qtbot, tmp_path) -> None:
    store = make_store(tmp_path)
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)

    dialog._save_and_close_button.click()

    assert store.presets == []
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_every_category_dialog_has_both_buttons(qtbot, tmp_path: Path) -> None:
    for category in (CATEGORY_COMMANDS, CATEGORY_MACROS, CATEGORY_SELECTION):
        dialog = PresetEditorDialog(make_store(tmp_path), category=category)
        qtbot.addWidget(dialog)

        assert dialog._save_button.text() == "Save"
        assert dialog._save_and_close_button.text() == "Save and Close"


def macro_dialog(tmp_path: Path, qtbot, lines=None):
    store = make_store(tmp_path)
    store.presets = [Preset(name="M", lines=lines or ["echo one"], target="new_tab")]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)
    return dialog


def test_step_buttons_only_appear_for_macros(qtbot, tmp_path: Path) -> None:
    macros = macro_dialog(tmp_path, qtbot)
    assert [label for label, _, _ in preset_editor._STEP_BUTTONS] == [
        "New Tab",
        "Split Right",
        "Split Down",
    ]
    assert macros._hint_label.text() == preset_editor._MACRO_HINT

    store = make_store(tmp_path)
    commands = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(commands)
    assert commands._is_macro is False
    assert commands._hint_label.text() == ""


def test_inserting_a_step_puts_the_separator_on_its_own_line(qtbot, tmp_path: Path) -> None:
    dialog = macro_dialog(tmp_path, qtbot, ["npm run dev"])
    cursor = dialog._lines_edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    dialog._lines_edit.setTextCursor(cursor)

    dialog._insert_step("--- right")
    dialog._lines_edit.insertPlainText("npm test")

    assert dialog._lines_edit.toPlainText().splitlines() == [
        "npm run dev",
        "--- right",
        "npm test",
    ]


def test_inserting_mid_line_breaks_the_line_first(qtbot, tmp_path: Path) -> None:
    """A separator only counts alone on its line, so inserting one mid-line
    has to break it - otherwise the button looks like it did nothing."""
    dialog = macro_dialog(tmp_path, qtbot, ["npm run dev"])
    cursor = dialog._lines_edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    dialog._lines_edit.setTextCursor(cursor)

    dialog._insert_step("---")

    assert dialog._lines_edit.toPlainText().splitlines() == ["npm run dev", "---"]


def test_what_the_buttons_insert_is_what_the_parser_understands(qtbot, tmp_path: Path) -> None:
    """The buttons and macro_steps() must not drift apart - an unrecognised
    separator silently opens a tab instead of a pane."""
    dialog = macro_dialog(tmp_path, qtbot, ["first"])
    cursor = dialog._lines_edit.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    dialog._lines_edit.setTextCursor(cursor)

    for _label, token, _tip in preset_editor._STEP_BUTTONS:
        dialog._insert_step(token)
        dialog._lines_edit.insertPlainText(f"step for {token}")

    steps = macro_steps(dialog._lines_edit.toPlainText().splitlines())

    assert [step.placement for step in steps] == [STEP_TAB, STEP_TAB, STEP_RIGHT, STEP_DOWN]


def test_saving_keeps_the_separator_lines(qtbot, tmp_path: Path) -> None:
    """Blank-ish lines are stripped on save; the separator must survive it."""
    dialog = macro_dialog(tmp_path, qtbot, ["first"])
    dialog._lines_edit.setPlainText("first\n--- down\nsecond")

    dialog._save_current()

    assert dialog._store.presets[0].lines == ["first", "--- down", "second"]


def macro_names(store: PresetStore) -> list[str]:
    return [p.name for p in store.presets if category_of(p) == CATEGORY_MACROS]


def test_moving_a_macro_down_reorders_it(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.presets = [
        Preset(name="First", lines=["a"], target="new_tab"),
        Preset(name="Second", lines=["b"], target="new_tab"),
        Preset(name="Third", lines=["c"], target="new_tab"),
    ]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(0)
    dialog._move_current(1)

    assert macro_names(store) == ["Second", "First", "Third"]
    # The selection follows the entry that moved, so pressing it again moves
    # the same one further.
    dialog._move_current(1)
    assert macro_names(store) == ["Second", "Third", "First"]


def test_moving_past_either_end_does_nothing(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.presets = [
        Preset(name="First", lines=["a"], target="new_tab"),
        Preset(name="Second", lines=["b"], target="new_tab"),
    ]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(0)
    dialog._move_current(-1)
    dialog._list.setCurrentRow(1)
    dialog._move_current(1)

    assert macro_names(store) == ["First", "Second"]


def test_reordering_macros_leaves_the_other_categories_alone(
    qtbot, tmp_path: Path
) -> None:
    """One list holds all three categories interleaved, so a Macro moving must
    not shuffle the Commands sitting between them."""
    store = make_store(tmp_path)
    store.presets = [
        Preset(name="MacroA", lines=["a"], target="new_tab"),
        Preset(name="CommandX", lines=["x"], target="active"),
        Preset(name="MacroB", lines=["b"], target="new_tab"),
        Preset(name="CommandY", lines=["y"], target="active"),
    ]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(0)
    dialog._move_current(1)

    assert macro_names(store) == ["MacroB", "MacroA"]
    commands = [p.name for p in store.presets if category_of(p) == CATEGORY_COMMANDS]
    assert commands == ["CommandX", "CommandY"]


def test_the_new_order_is_saved_and_shown_in_the_menu(qtbot, tmp_path: Path) -> None:
    store = make_store(tmp_path)
    store.presets = [
        Preset(name="First", lines=["a"], target="new_tab"),
        Preset(name="Second", lines=["b"], target="new_tab"),
    ]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_MACROS)
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(1)
    dialog._move_current(-1)

    assert macro_names(PresetStore(path=tmp_path / "presets.json")) == [
        "Second",
        "First",
    ]

    tabs = TerminalTabWidget()
    qtbot.addWidget(tabs)
    menu = MacrosMenu(store, tabs)
    listed = [a.text() for a in menu.actions()][:2]
    assert listed == ["Second", "First"]


def test_the_open_editor_holds_off_a_reload(qtbot, tmp_path) -> None:
    """Presets are addressed by index here, so the list must not be swapped
    out by a poll while the form is open."""
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = [Preset(name="Build", lines=["make"], target="active")]
    store.save()
    dialog = PresetEditorDialog(store, category=CATEGORY_COMMANDS)
    qtbot.addWidget(dialog)

    elsewhere = PresetStore(path=tmp_path / "presets.json")
    elsewhere.presets.insert(
        0, Preset(name="Sneaked In", lines=["x"], target="active")
    )
    elsewhere.save()

    assert store.reload_if_changed() is False
    assert [p.name for p in store.presets] == ["Build"]

    dialog.reject()

    assert store.reload_if_changed() is True
    assert [p.name for p in store.presets] == ["Sneaked In", "Build"]
