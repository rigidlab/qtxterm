"""CronScheduler: what fires, when, where it goes, and what happens when the
job points at a preset that is no longer there."""

from __future__ import annotations

from datetime import datetime, timedelta

from qtxterm.cron import CronJob, CronStore
from qtxterm.cron_scheduler import CronScheduler
from qtxterm.presets import Preset, PresetStore


def at(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


class FakeTabs:
    """Enough of TerminalTabWidget to see where a job's output went."""

    def __init__(self) -> None:
        self.open_tabs: list[object] = []
        self.fed: list[tuple[object, list[str]]] = []
        self.renamed: list[tuple[int, str]] = []

    def run_in_new_tab(self, shell, lines):
        terminal = object()
        self.open_tabs.append(terminal)
        return terminal

    def tab_index_of(self, widget) -> int:
        return self.open_tabs.index(widget) if widget in self.open_tabs else -1

    def rename_tab(self, index: int, name: str) -> None:
        self.renamed.append((index, name))

    def feed_terminal(self, widget, lines: list[str]) -> None:
        self.fed.append((widget, list(lines)))

    def close(self, widget) -> None:
        self.open_tabs.remove(widget)


def make(tmp_path, jobs=(), presets=()):
    cron_store = CronStore(path=tmp_path / "cron.json")
    for job in jobs:
        cron_store.jobs.append(job)
    preset_store = PresetStore(path=tmp_path / "presets.json")
    preset_store.presets = list(presets)
    tabs = FakeTabs()
    return CronScheduler(cron_store, preset_store, tabs), tabs, cron_store


def test_a_matching_job_runs_its_preset(tmp_path) -> None:
    job = CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup")
    preset = Preset(name="Backup", lines=["rsync -a . /backup"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    fired = scheduler.run_due_jobs(at("2026-08-17 02:00"))

    assert fired == ["Nightly"]
    assert tabs.fed == [(tabs.open_tabs[0], ["rsync -a . /backup"])]


def test_nothing_runs_at_the_wrong_minute(tmp_path) -> None:
    job = CronJob(name="Nightly", expression="0 2 * * *", preset_name="Backup")
    preset = Preset(name="Backup", lines=["x"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    assert scheduler.run_due_jobs(at("2026-08-17 02:01")) == []
    assert tabs.fed == []


def test_a_disabled_job_never_fires(tmp_path) -> None:
    job = CronJob(
        name="Off", expression="* * * * *", preset_name="Backup", enabled=False
    )
    preset = Preset(name="Backup", lines=["x"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    assert scheduler.run_due_jobs(at("2026-08-17 02:00")) == []
    assert tabs.fed == []


def test_the_same_tab_is_reused_across_runs(tmp_path) -> None:
    """A job on a five-minute schedule would otherwise bury the tab bar."""
    job = CronJob(name="Poll", expression="* * * * *", preset_name="Status")
    preset = Preset(name="Status", lines=["git status -sb"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    for minute in range(3):
        scheduler.run_due_jobs(at("2026-08-17 02:00") + timedelta(minutes=minute))

    assert len(tabs.open_tabs) == 1
    assert len(tabs.fed) == 3
    assert {terminal for terminal, _ in tabs.fed} == {tabs.open_tabs[0]}


def test_the_tab_is_named_after_the_job(tmp_path) -> None:
    job = CronJob(name="Nightly backup", expression="* * * * *", preset_name="Backup")
    preset = Preset(name="Backup", lines=["x"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    scheduler.run_due_jobs(at("2026-08-17 02:00"))

    assert tabs.renamed == [(0, "Nightly backup")]


def test_closing_the_tab_makes_the_next_run_open_another(tmp_path) -> None:
    job = CronJob(name="Poll", expression="* * * * *", preset_name="Status")
    preset = Preset(name="Status", lines=["x"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    scheduler.run_due_jobs(at("2026-08-17 02:00"))
    tabs.close(tabs.open_tabs[0])
    scheduler.run_due_jobs(at("2026-08-17 02:01"))

    assert len(tabs.open_tabs) == 1
    assert len(tabs.fed) == 2


def test_a_job_pointing_at_a_missing_preset_says_so(qtbot, tmp_path) -> None:
    """Silently doing nothing every minute is the worst thing a scheduler can
    do, so a renamed or deleted preset is reported."""
    job = CronJob(name="Nightly", expression="* * * * *", preset_name="Gone")
    scheduler, tabs, _ = make(tmp_path, [job], [])

    with qtbot.waitSignal(scheduler.job_failed) as blocker:
        scheduler.run_due_jobs(at("2026-08-17 02:00"))

    assert blocker.args[0] == "Nightly"
    assert "Gone" in blocker.args[1]
    assert tabs.fed == []


def test_an_unparseable_schedule_is_reported_not_crashed(qtbot, tmp_path) -> None:
    job = CronJob(name="Broken", expression="not a cron line", preset_name="Backup")
    preset = Preset(name="Backup", lines=["x"], target="new_tab")
    scheduler, _tabs, _ = make(tmp_path, [job], [preset])

    with qtbot.waitSignal(scheduler.job_failed) as blocker:
        scheduler.run_due_jobs(at("2026-08-17 02:00"))

    assert blocker.args[0] == "Broken"
    assert "schedule" in blocker.args[1]


def test_the_minute_in_progress_at_start_does_not_fire(tmp_path) -> None:
    """Opening the app at 09:00:30 should not run the 09:00 job: that is
    catch-up, and there is deliberately none."""
    job = CronJob(name="Morning", expression="0 9 * * *", preset_name="Backup")
    preset = Preset(name="Backup", lines=["x"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    now = [at("2026-08-17 09:00") + timedelta(seconds=30)]
    scheduler._clock = lambda: now[0]
    scheduler.start()
    scheduler._on_tick()  # still 09:00, the minute we started in

    assert tabs.fed == []

    now[0] = at("2026-08-17 09:01")
    scheduler._on_tick()
    assert tabs.fed == []  # 09:01 does not match either

    now[0] = at("2026-08-18 09:00")
    scheduler._on_tick()
    assert len(tabs.fed) == 1  # the next real occurrence does fire

    scheduler.stop()


def test_run_now_ignores_the_schedule(tmp_path) -> None:
    """The Manage dialog offers "Run now" - it should not have to wait for
    the next matching minute to prove a job works."""
    job = CronJob(name="Nightly", expression="0 2 1 1 *", preset_name="Backup")
    preset = Preset(name="Backup", lines=["echo hi"], target="new_tab")
    scheduler, tabs, _ = make(tmp_path, [job], [preset])

    assert scheduler.run_now(job) is True
    assert tabs.fed == [(tabs.open_tabs[0], ["echo hi"])]
