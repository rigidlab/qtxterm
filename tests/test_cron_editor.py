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


def test_only_macros_are_offered(qtbot, tmp_path: Path) -> None:
    """A Command means "the terminal I am working in", which a job firing at
    2am cannot honour; a Selection Action needs a live selection."""
    cron_store, preset_store = make_stores(tmp_path)
    preset_store.presets.append(
        Preset(name="Search", lines=["https://x/{selection}"], input="selection")
    )
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    offered = [
        dialog._preset_combo.itemData(i) for i in range(dialog._preset_combo.count())
    ]

    assert offered == ["Backup"]
    assert "Status" not in offered  # a Command
    assert "Search" not in offered  # a Selection Action


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


def test_jobs_are_nested_under_their_group(qtbot, tmp_path: Path) -> None:
    """Same convention the preset menus use: ungrouped at the top level,
    groups after them in name order."""
    jobs = [
        CronJob(name="Loose", expression="* * * * *", preset_name="Backup"),
        CronJob(
            name="Equities open",
            expression="30 6 * * 1-5",
            preset_name="Backup",
            group="Market data",
        ),
        CronJob(
            name="Futures open",
            expression="0 15 * * 0-4",
            preset_name="Backup",
            group="Market data",
        ),
        CronJob(
            name="Nightly", expression="0 2 * * *", preset_name="Backup", group="Admin"
        ),
    ]
    cron_store, preset_store = make_stores(tmp_path, jobs)
    menu = CronMenu(cron_store, preset_store)
    qtbot.addWidget(menu)

    top_level = [a.text() for a in menu.actions() if a.isCheckable()]
    submenus = {a.text(): a.menu() for a in menu.actions() if a.menu() is not None}

    assert top_level == ["Loose  (* * * * *)"]
    assert list(submenus) == ["Admin", "Market data"]
    assert [a.text() for a in submenus["Market data"].actions()] == [
        "Equities open  (30 6 * * 1-5)",
        "Futures open  (0 15 * * 0-4)",
    ]


def test_toggling_a_grouped_job_writes_back_to_the_right_one(
    qtbot, tmp_path: Path
) -> None:
    """Grouping reorders what the menu shows, so the index has to travel with
    the job rather than being read off the menu."""
    jobs = [
        CronJob(name="First", expression="* * * * *", preset_name="Backup"),
        CronJob(
            name="Grouped",
            expression="0 2 * * *",
            preset_name="Backup",
            group="Admin",
        ),
    ]
    cron_store, preset_store = make_stores(tmp_path, jobs)
    menu = CronMenu(cron_store, preset_store)
    qtbot.addWidget(menu)

    admin = next(a.menu() for a in menu.actions() if a.text() == "Admin")
    admin.actions()[0].setChecked(False)

    assert cron_store.jobs[1].enabled is False
    assert cron_store.jobs[0].enabled is True


def test_the_group_is_saved_with_the_job(qtbot, tmp_path: Path) -> None:
    cron_store, preset_store = make_stores(tmp_path)
    dialog = CronEditorDialog(cron_store, preset_store, create_new=True)
    qtbot.addWidget(dialog)

    dialog._name_edit.setText("Equities open")
    dialog._group_edit.setText("Market data")
    dialog._schedule_edit.setText("30 6 * * 1-5")
    dialog._save_current()

    assert CronStore(path=tmp_path / "cron.json").jobs[0].group == "Market data"


def test_clearing_the_group_makes_it_ungrouped(qtbot, tmp_path: Path) -> None:
    job = CronJob(
        name="Grouped", expression="0 2 * * *", preset_name="Backup", group="Admin"
    )
    cron_store, preset_store = make_stores(tmp_path, [job])
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)
    dialog._list.setCurrentRow(0)

    dialog._group_edit.setText("   ")
    dialog._save_current()

    assert cron_store.jobs[0].group is None


def test_the_open_editor_holds_off_a_reload(qtbot, tmp_path: Path) -> None:
    """The form addresses jobs by index, and a modal dialog still runs the
    event loop - so a poll landing mid-edit would save onto the wrong job."""
    cron_store, preset_store = make_stores(
        tmp_path, [CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup")]
    )
    cron_store.save()
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    elsewhere = CronStore(path=tmp_path / "cron.json")
    elsewhere.jobs.insert(
        0, CronJob(name="Sneaked In", expression="* * * * *", preset_name="Backup")
    )
    elsewhere.save()

    assert cron_store.reload_if_changed() is False
    assert [job.name for job in cron_store.jobs] == ["Nightly"]

    dialog.reject()

    assert cron_store.reload_if_changed() is True
    assert [job.name for job in cron_store.jobs] == ["Sneaked In", "Nightly"]


def test_the_open_editor_holds_off_a_preset_reload_too(qtbot, tmp_path: Path) -> None:
    """Its Macro combo is built once, so the preset list must hold still too."""
    cron_store, preset_store = make_stores(tmp_path)
    preset_store.save()
    dialog = CronEditorDialog(cron_store, preset_store)
    qtbot.addWidget(dialog)

    elsewhere = PresetStore(path=tmp_path / "presets.json")
    elsewhere.add(Preset(name="Deploy", lines=["make deploy"], target="new_tab"))

    assert preset_store.reload_if_changed() is False

    dialog.reject()

    assert preset_store.reload_if_changed() is True
