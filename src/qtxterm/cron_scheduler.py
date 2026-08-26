"""Fires cron jobs while the app is running.

Kept apart from `cron.py`, which is schedules and storage and knows nothing
about terminals. This is the half that owns a tab per job and decides when to
write into it.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QObject, QTimer, Signal

from qtxterm.cron import CronError, CronJob, CronStore
from qtxterm.presets import CATEGORY_MACROS, Preset, PresetStore, category_of

# The clock is only read to the minute, so a second is plenty of resolution
# and costs nothing measurable. A 60s timer would drift against the wall
# clock and skip a minute whenever the machine sleeps.
_TICK_MS = 1000


class CronScheduler(QObject):
    """Runs jobs at their scheduled minute, into a tab each job keeps.

    No catch-up, by design (see SPEC.md): the minute already in progress when
    the app starts never fires, and nothing missed while it was closed is
    replayed. Otherwise launching after a weekend would open a burst of
    terminals before you had touched anything.

    Config is re-read on the minute, so a job added in another instance is
    picked up here without a restart - see `refresh_config`.
    """

    job_fired = Signal(str)
    # Name and reason. A job pointing at a preset that has been renamed or
    # deleted must say so - silently doing nothing every minute is the worst
    # possible behaviour for a scheduler.
    job_failed = Signal(str, str)

    def __init__(
        self,
        cron_store: CronStore,
        preset_store: PresetStore,
        tabs,
        parent: QObject | None = None,
        clock=None,
    ) -> None:
        super().__init__(parent)
        self._cron_store = cron_store
        self._preset_store = preset_store
        self._tabs = tabs
        self._clock = clock or datetime.now
        self._tab_for_job: dict[str, object] = {}
        self._last_minute: datetime | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(_TICK_MS)
        self._timer.timeout.connect(self._on_tick)

    def start(self) -> None:
        # Anchored to the current minute so the one in progress is not fired
        # a second time by an app that happened to open during it.
        self._last_minute = self._minute_of(self._clock())
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    @staticmethod
    def _minute_of(moment: datetime) -> datetime:
        return moment.replace(second=0, microsecond=0)

    def _on_tick(self) -> None:
        minute = self._minute_of(self._clock())
        if minute == self._last_minute:
            return
        self._last_minute = minute
        self.refresh_config()
        self.run_due_jobs(minute)

    def refresh_config(self) -> None:
        """Pick up jobs and Macros written by another qtxterm instance.

        Polled here rather than watched, for two reasons. This tick already
        happens every second, so checking on the minute costs a stat and no
        extra wakeup at all - where a QFileSystemWatcher costs a worker
        thread, and silently stops watching when a file is *replaced*, which
        is exactly what the atomic save in `ConfigStore` does. And a minute
        is the resolution cron works at anyway; there is nothing to be done
        with a job noticed sooner than the minute it could first fire.

        Presets as well as jobs, because a job added elsewhere usually
        arrives with the Macro it runs, and a job whose Macro we have not
        re-read fails every firing with "no Macro named ... any more".
        """
        self._preset_store.reload_if_changed()
        self._cron_store.reload_if_changed()

    def run_due_jobs(self, minute: datetime) -> list[str]:
        """Fire every enabled job whose schedule matches `minute`."""
        fired: list[str] = []
        for job in list(self._cron_store.jobs):
            if not job.enabled:
                continue
            try:
                schedule = job.schedule()
            except CronError as exc:
                self.job_failed.emit(job.name, f"unreadable schedule: {exc}")
                continue
            if schedule.matches(minute) and self.run_now(job):
                fired.append(job.name)
        return fired

    def run_now(self, job: CronJob) -> bool:
        """Run `job` immediately. False if it could not run, having said why."""
        preset = self._preset_for(job)
        if preset is None:
            self.job_failed.emit(
                job.name, f"no Macro named {job.preset_name!r} any more"
            )
            return False
        if category_of(preset) != CATEGORY_MACROS:
            # Reachable only by hand-editing cron.json, or by a preset that
            # has since been changed into a Command. Refused rather than run:
            # a Command means "the terminal I am working in", and a job has
            # no business typing there.
            self.job_failed.emit(job.name, f"{job.preset_name!r} is no longer a Macro")
            return False

        terminal = self._terminal_for(job)
        if terminal is None:
            self.job_failed.emit(job.name, "could not open a terminal for it")
            return False

        self._tabs.feed_terminal(terminal, preset.lines)
        self.job_fired.emit(job.name)
        return True

    def _preset_for(self, job: CronJob) -> Preset | None:
        for preset in self._preset_store.presets:
            if preset.name == job.preset_name:
                return preset
        return None

    def _terminal_for(self, job: CronJob):
        """The job's own tab, opening one the first time and after a close.

        One tab per job, reused: a job on a five-minute schedule would
        otherwise bury the tab bar, and its scrollback is exactly the history
        of that job.
        """
        existing = self._tab_for_job.get(job.name)
        if existing is not None and self._tabs.tab_index_of(existing) != -1:
            return existing

        terminal = self._tabs.run_in_new_tab(None, [])
        if terminal is None:
            return None
        self._tab_for_job[job.name] = terminal
        index = self._tabs.tab_index_of(terminal)
        if index != -1:
            self._tabs.rename_tab(index, job.name)
        return terminal
