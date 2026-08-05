"""CommandSidebar: grouping/rendering of sidebar-flagged presets and click behavior."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QGroupBox, QPushButton

from mterm.presets import Preset, PresetStore
from mterm.sidebar import CommandSidebar


def make_store(tmp_path: Path, presets: list[Preset]) -> PresetStore:
    store = PresetStore(path=tmp_path / "presets.json")
    store.presets = presets
    store.save()
    return store


def test_only_sidebar_flagged_presets_render_as_buttons(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Shown", lines=["echo shown"], show_in_sidebar=True),
            Preset(name="Hidden", lines=["echo hidden"], show_in_sidebar=False),
        ],
    )
    sidebar = CommandSidebar(store)
    qtbot.addWidget(sidebar)

    button_labels = [b.text() for b in sidebar.findChildren(QPushButton)]
    assert button_labels == ["Shown"]


def test_presets_are_grouped_into_group_boxes(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [
            Preset(name="Status", lines=["git status"], group="Git", show_in_sidebar=True),
            Preset(name="Pull", lines=["git pull"], group="Git", show_in_sidebar=True),
            Preset(name="Clear", lines=["clear"], show_in_sidebar=True),
        ],
    )
    sidebar = CommandSidebar(store)
    qtbot.addWidget(sidebar)

    boxes = sidebar.findChildren(QGroupBox)
    titles = [b.title() for b in boxes]
    assert "Git" in titles
    assert "" in titles  # ungrouped preset gets an untitled flat box

    git_box = next(b for b in boxes if b.title() == "Git")
    git_buttons = [b.text() for b in git_box.findChildren(QPushButton)]
    assert git_buttons == ["Status", "Pull"]


def test_clicking_a_button_emits_run_requested_with_its_lines(qtbot, tmp_path: Path) -> None:
    store = make_store(
        tmp_path,
        [Preset(name="Status", lines=["git status"], show_in_sidebar=True)],
    )
    sidebar = CommandSidebar(store)
    qtbot.addWidget(sidebar)
    button = next(b for b in sidebar.findChildren(QPushButton) if b.text() == "Status")

    with qtbot.waitSignal(sidebar.run_requested, timeout=1000) as blocker:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    assert blocker.args == [["git status"]]


def test_store_changes_auto_reload_the_sidebar(qtbot, tmp_path: Path) -> None:
    """PresetStore.changed drives sidebar.reload() automatically - no manual
    reload() call needed after add/update/delete."""
    store = make_store(tmp_path, [])
    sidebar = CommandSidebar(store)
    qtbot.addWidget(sidebar)
    assert sidebar.findChildren(QGroupBox) == []

    store.add(Preset(name="New", lines=["echo new"], show_in_sidebar=True))

    button_labels = [b.text() for b in sidebar.findChildren(QPushButton)]
    assert button_labels == ["New"]
