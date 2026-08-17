"""CronEditorDialog and CronMenu: editing jobs, and toggling them from the menu."""

from __future__ import annotations

from pathlib import Path

from qtxterm.cron import CronJob, CronStore
from qtxterm.cron_editor import CronEditorDialog
from qtxterm.cron_menu import CronMenu
from qtxterm.presets import Preset, PresetStore


def make_stores(tmp_path: Path, jobs=(), presets=None):
    cron_store = CronStore(path=tmp_path / "cron.json")
    cron_store.jobs = list(jobs)
    preset_store = PresetStore(path=tmp_path / "presets.json")
    preset_store.presets = list(
        presets
        if presets is not None
        else [
            Preset(name="Backup", lines=["rsync"], target="new_tab"),
            Preset(name="Status", lines=["git status"], target="active"),
        ]
    )
    return cron_store, preset_store


def test_the_preset_list_offers_commands_and_macros_only(qtbot, tmp_path: Path) -> None:
    """A Selection Action needs a live selection, which a schedule can never
    provide."""
    cron_store, preset_store = make_stores(tmp_path)
    preset_store.presets.append(
        Preset(name="Search", lines=["https://x/{selection}"], input="selection")
    )
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    offered = [
        dialog._preset_combo.itemData(i) for i in range(dialog._preset_combo.count())
    ]

    assert offered == ["Status", "Backup"]
    assert "Search" not in offered


def test_a_new_job_is_saved_and_listed(qtbot, tmp_path: Path) -> None:
    cron_store, preset_store = make_stores(tmp_path)
    dialog = CronEditorDialog(cron_store, preset_store, create_new=True)
    qtbot.addWidget(dialog)

    dialog._name_edit.setText("Nightly")
    dialog._schedule_edit.setText("0 2 * * *")
    dialog._save_current()

    assert len(cron_store.jobs) == 1
    assert cron_store.jobs[0].name == "Nightly"
    assert cron_store.jobs[0].expression == "0 2 * * *"
    assert CronStore(path=tmp_path / "cron.json").jobs[0].name == "Nightly"


def test_an_unparseable_schedule_is_refused_not_stored(qtbot, tmp_path: Path) -> None:
    """A job with a broken schedule would sit there doing nothing."""
    job = CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup")
    cron_store, preset_store = make_stores(tmp_path, [job])
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._schedule_edit.setText("every tuesday please")
    saved = dialog._save_current()

    assert saved is False
    assert cron_store.jobs[0].expression == "0 2 * * *"
    assert "not saved" in dialog._next_run_label.text()


def test_the_next_run_is_previewed_as_you_type(qtbot, tmp_path: Path) -> None:
    cron_store, preset_store = make_stores(tmp_path)
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    dialog._schedule_edit.setText("*/15 * * * *")
    assert "Next run:" in dialog._next_run_label.text()

    dialog._schedule_edit.setText("0 0 31 2 *")
    assert "never occurs" in dialog._next_run_label.text()

    dialog._schedule_edit.setText("99 * * * *")
    assert "⚠" in dialog._next_run_label.text()


def test_a_job_whose_preset_vanished_shows_it_rather_than_repointing(
    qtbot, tmp_path: Path
) -> None:
    """Saving must not silently attach the job to whatever preset happened to
    be first in the list."""
    job = CronJob(name="Nightly", expression="0 2 * * *", preset_name="Deleted")
    cron_store, preset_store = make_stores(tmp_path, [job])
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    dialog._list.setCurrentRow(0)

    assert "missing" in dialog._preset_combo.currentText()
    dialog._save_current()
    assert cron_store.jobs[0].preset_name == "Deleted"


def test_the_menu_lists_jobs_and_toggles_them(qtbot, tmp_path: Path) -> None:
    jobs = [
        CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup"),
        CronJob(
            name="Poll", expression="*/5 * * * *", preset_name="Status", enabled=False
        ),
    ]
    cron_store, preset_store = make_stores(tmp_path, jobs)
    menu = CronMenu(cron_store, preset_store)
    qtbot.addWidget(menu)

    entries = [a for a in menu.actions() if a.isCheckable()]
    assert [a.text() for a in entries] == [
        "Nightly  (0 2 * * *)",
        "Poll  (*/5 * * * *)",
    ]
    assert [a.isChecked() for a in entries] == [True, False]

    entries[1].setChecked(True)

    assert cron_store.jobs[1].enabled is True
    assert CronStore(path=tmp_path / "cron.json").jobs[1].enabled is True


def test_the_menu_always_offers_new_and_manage(qtbot, tmp_path: Path) -> None:
    cron_store, preset_store = make_stores(tmp_path)
    menu = CronMenu(cron_store, preset_store)
    qtbot.addWidget(menu)

    texts = [a.text() for a in menu.actions()]

    assert "New Cron Job..." in texts
    assert "Manage Cron Jobs..." in texts


def test_the_menu_rebuilds_when_jobs_change(qtbot, tmp_path: Path) -> None:
    cron_store, preset_store = make_stores(tmp_path)
    menu = CronMenu(cron_store, preset_store)
    qtbot.addWidget(menu)
    assert not [a for a in menu.actions() if a.isCheckable()]

    cron_store.add(CronJob(name="New", expression="* * * * *", preset_name="Backup"))

    assert len([a for a in menu.actions() if a.isCheckable()]) == 1
