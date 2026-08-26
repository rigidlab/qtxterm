"""ConfigStore: picking up a file a second qtxterm instance has written.

The "other instance" in these tests is a second store object over the same
path, which is exactly what two running windows are.
"""

from __future__ import annotations

import json

from qtxterm.cron import CronJob, CronStore
from qtxterm.presets import Preset, PresetStore


def job(name: str, expression: str = "* * * * *") -> CronJob:
    return CronJob(name=name, expression=expression, preset_name="Backup")


def test_a_job_added_by_another_instance_is_picked_up(tmp_path) -> None:
    path = tmp_path / "cron.json"
    here, elsewhere = CronStore(path=path), CronStore(path=path)

    elsewhere.add(job("Nightly"))

    assert here.reload_if_changed() is True
    assert [j.name for j in here.jobs] == ["Nightly"]


def test_reload_announces_the_change_like_a_local_edit(tmp_path) -> None:
    path = tmp_path / "cron.json"
    here, elsewhere = CronStore(path=path), CronStore(path=path)
    seen = []
    here.changed.connect(lambda: seen.append(len(here.jobs)))

    elsewhere.add(job("Nightly"))
    here.reload_if_changed()

    assert seen == [1]


def test_an_unchanged_file_is_not_reparsed(tmp_path) -> None:
    path = tmp_path / "cron.json"
    store = CronStore(path=path)
    store.add(job("Nightly"))
    seen = []
    store.changed.connect(seen.append)

    # The point of the stamp: polling every minute forever must not rebuild
    # every menu every minute.
    assert store.reload_if_changed() is False
    assert store.reload_if_changed() is False
    assert seen == []


def test_our_own_save_does_not_look_like_someone_elses(tmp_path) -> None:
    store = CronStore(path=tmp_path / "cron.json")
    store.add(job("Nightly"))

    assert store.reload_if_changed() is False


def test_reload_is_held_off_while_an_editor_is_open(tmp_path) -> None:
    path = tmp_path / "cron.json"
    here, elsewhere = CronStore(path=path), CronStore(path=path)
    elsewhere.add(job("Nightly"))

    with here.reload_suspended():
        assert here.reload_if_changed() is False
        assert here.jobs == []

    assert here.reload_if_changed() is True
    assert [j.name for j in here.jobs] == ["Nightly"]


def test_suspension_nests(tmp_path) -> None:
    path = tmp_path / "cron.json"
    here, elsewhere = CronStore(path=path), CronStore(path=path)
    elsewhere.add(job("Nightly"))

    with here.reload_suspended():
        with here.reload_suspended():
            pass
        # Still held by the outer editor.
        assert here.reload_if_changed() is False

    assert here.reload_if_changed() is True


def test_half_written_json_leaves_the_jobs_alone_and_is_retried(tmp_path) -> None:
    path = tmp_path / "cron.json"
    store = CronStore(path=path)
    store.add(job("Nightly"))

    path.write_text('[{"name": "Half', encoding="utf-8")
    assert store.reload_if_changed() is False
    assert [j.name for j in store.jobs] == ["Nightly"]

    # The stamp was not advanced, so the next poll still sees a change.
    path.write_text(
        json.dumps([{"name": "Whole", "expression": "* * * * *", "preset_name": "B"}]),
        encoding="utf-8",
    )
    assert store.reload_if_changed() is True
    assert [j.name for j in store.jobs] == ["Whole"]


def test_a_deleted_file_does_not_wipe_the_jobs(tmp_path) -> None:
    path = tmp_path / "cron.json"
    store = CronStore(path=path)
    store.add(job("Nightly"))

    path.unlink()

    assert store.reload_if_changed() is False
    assert [j.name for j in store.jobs] == ["Nightly"]


def test_unknown_fields_still_survive_a_reload(tmp_path) -> None:
    path = tmp_path / "cron.json"
    store = CronStore(path=path)
    path.write_text(
        json.dumps(
            [
                {
                    "name": "Newer",
                    "expression": "* * * * *",
                    "preset_name": "B",
                    "from_a_later_version": True,
                }
            ]
        ),
        encoding="utf-8",
    )

    assert store.reload_if_changed() is True
    assert [j.name for j in store.jobs] == ["Newer"]


def test_save_leaves_no_temporary_file_behind(tmp_path) -> None:
    store = CronStore(path=tmp_path / "cron.json")
    store.add(job("Nightly"))

    assert [p.name for p in tmp_path.iterdir()] == ["cron.json"]


def test_save_never_leaves_the_file_unreadable(tmp_path) -> None:
    """The reason for the atomic write: another instance is polling this.

    Rewriting a long file with a short one is where a plain write is briefly
    truncated on disk; os.replace has no such window.
    """
    path = tmp_path / "cron.json"
    store = CronStore(path=path)
    for index in range(20):
        store.jobs.append(job(f"Job {index}"))
    store.save()

    store.jobs = [job("Only one")]
    store.save()

    assert len(json.loads(path.read_text(encoding="utf-8"))) == 1


def test_presets_reload_the_same_way(tmp_path) -> None:
    path = tmp_path / "presets.json"
    here, elsewhere = PresetStore(path=path), PresetStore(path=path)
    elsewhere.add(Preset(name="Deploy", lines=["make deploy"], target="new_tab"))

    assert here.reload_if_changed() is True
    assert here.presets[-1].name == "Deploy"
