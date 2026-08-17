"""Manage Cron Jobs: a schedule, a preset to run, and whether it is on."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qtxterm.cron import CronError, CronExpression, CronJob, CronStore
from qtxterm.presets import (
    CATEGORY_COMMANDS,
    CATEGORY_MACROS,
    PresetStore,
    in_category,
)

TITLE = "Manage Cron Jobs"

_SYNTAX_HINT = (
    "<b>minute hour day-of-month month day-of-week</b> — "
    "<code>*/15 * * * *</code> every quarter hour, "
    "<code>0 9 * * 1-5</code> weekday mornings, "
    "<code>0 2 1 * *</code> the 1st at 02:00."
)

# Jobs run while the app is open and nothing is replayed afterwards, which is
# the one thing about this that will surprise someone who knows crontab.
_SCOPE_HINT = (
    "Jobs run only while qtxterm is open. Nothing missed while it was closed "
    "is caught up on."
)


class CronEditorDialog(QDialog):
    """Add/edit/delete cron jobs.

    A job names the preset it runs rather than carrying its own commands:
    Macros and Commands are already edited elsewhere, and having one command
    live in two places is how they drift apart.
    """

    def __init__(
        self,
        store: CronStore,
        preset_store: PresetStore,
        parent: QWidget | None = None,
        scheduler=None,
        create_new: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(TITLE)
        self.resize(660, 430)
        self._store = store
        self._preset_store = preset_store
        self._scheduler = scheduler
        self._current_index: int | None = None

        layout = QHBoxLayout(self)

        left = QVBoxLayout()
        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_row_changed)
        left.addWidget(self._list)
        buttons = QHBoxLayout()
        new_button = QPushButton("New")
        new_button.clicked.connect(self._new_job)
        delete_button = QPushButton("Delete")
        delete_button.clicked.connect(self._delete_job)
        buttons.addWidget(new_button)
        buttons.addWidget(delete_button)
        left.addLayout(buttons)
        layout.addLayout(left, 1)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        self._name_edit = QLineEdit()
        self._schedule_edit = QLineEdit()
        self._schedule_edit.setPlaceholderText("*/15 * * * *")
        self._schedule_edit.textChanged.connect(self._on_schedule_changed)
        self._preset_combo = QComboBox()
        self._enabled_check = QCheckBox("Enabled")

        self._next_run_label = QLabel()
        self._next_run_label.setWordWrap(True)
        syntax_label = QLabel(_SYNTAX_HINT)
        syntax_label.setWordWrap(True)
        scope_label = QLabel(_SCOPE_HINT)
        scope_label.setWordWrap(True)

        form.addRow("Name", self._name_edit)
        form.addRow("Schedule", self._schedule_edit)
        form.addRow("", self._next_run_label)
        form.addRow("", syntax_label)
        form.addRow("Runs", self._preset_combo)
        form.addRow("", self._enabled_check)
        form.addRow("", scope_label)

        self._run_now_button = QPushButton("Run Now")
        self._run_now_button.setToolTip(
            "Run this job immediately, without waiting for its next scheduled time"
        )
        self._run_now_button.clicked.connect(self._run_now)
        save_button = QPushButton("Save")
        save_button.clicked.connect(self._save_current)
        save_and_close_button = QPushButton("Save and Close")
        save_and_close_button.clicked.connect(self._save_and_close)
        action_row = QHBoxLayout()
        action_row.addWidget(self._run_now_button)
        action_row.addWidget(save_button)
        action_row.addWidget(save_and_close_button)
        form.addRow(action_row)
        layout.addWidget(form_widget, 2)

        self._reload_presets()
        self._reload_list()
        if create_new:
            self._new_job()

    def _runnable_presets(self):
        """Commands and Macros. Selection Actions need a live selection, so a
        schedule could never satisfy one."""
        return in_category(self._preset_store.presets, CATEGORY_COMMANDS) + in_category(
            self._preset_store.presets, CATEGORY_MACROS
        )

    def _reload_presets(self) -> None:
        self._preset_combo.clear()
        for preset in self._runnable_presets():
            self._preset_combo.addItem(preset.name, preset.name)

    def _reload_list(self) -> None:
        self._list.blockSignals(True)
        self._list.clear()
        for job in self._store.jobs:
            suffix = "" if job.enabled else "  (disabled)"
            self._list.addItem(f"{job.name}  —  {job.expression}{suffix}")
        self._list.blockSignals(False)

    def _on_row_changed(self, row: int) -> None:
        if row < 0 or row >= len(self._store.jobs):
            self._current_index = None
            return
        self._current_index = row
        job = self._store.jobs[row]
        self._name_edit.setText(job.name)
        self._schedule_edit.setText(job.expression)
        self._enabled_check.setChecked(job.enabled)
        index = self._preset_combo.findData(job.preset_name)
        if index >= 0:
            self._preset_combo.setCurrentIndex(index)
        elif job.preset_name:
            # The preset it points at is gone. Shown rather than silently
            # swapped for another, so saving cannot repoint the job by
            # accident.
            self._preset_combo.addItem(f"{job.preset_name} (missing)", job.preset_name)
            self._preset_combo.setCurrentIndex(self._preset_combo.count() - 1)

    def _on_schedule_changed(self, text: str) -> None:
        """Validate as it is typed - a cron line is easy to get subtly wrong."""
        text = text.strip()
        if not text:
            self._next_run_label.setText("")
            return
        try:
            expression = CronExpression.parse(text)
        except CronError as exc:
            self._next_run_label.setText(f"⚠ {exc}")
            return
        # Local wall-clock on purpose: "0 9 * * *" means nine in the morning
        # where you are, which is what every crontab has always meant.
        upcoming = expression.next_run(datetime.now())  # noqa: DTZ005
        if upcoming is None:
            self._next_run_label.setText("Valid, but never occurs")
        else:
            self._next_run_label.setText(f"Next run: {upcoming:%a %d %b %Y, %H:%M}")

    def _new_job(self) -> None:
        presets = self._runnable_presets()
        self._store.add(
            CronJob(
                name="New Job",
                expression="*/15 * * * *",
                preset_name=presets[0].name if presets else "",
            )
        )
        self._reload_list()
        self._list.setCurrentRow(len(self._store.jobs) - 1)

    def _delete_job(self) -> None:
        if self._current_index is None:
            return
        self._store.delete(self._current_index)
        self._current_index = None
        self._reload_list()

    def _job_from_form(self) -> CronJob:
        return CronJob(
            name=self._name_edit.text().strip() or "Unnamed",
            expression=self._schedule_edit.text().strip() or "*/15 * * * *",
            preset_name=self._preset_combo.currentData() or "",
            enabled=self._enabled_check.isChecked(),
        )

    def _save_current(self) -> bool:
        if self._current_index is None:
            return False
        job = self._job_from_form()
        try:
            job.schedule()
        except CronError as exc:
            # Refused rather than stored: a job with an unreadable schedule
            # would sit there doing nothing.
            self._next_run_label.setText(f"⚠ not saved — {exc}")
            return False
        saved_index = self._current_index
        self._store.update(saved_index, job)
        self._reload_list()
        self._list.setCurrentRow(saved_index)
        return True

    def _save_and_close(self) -> None:
        if self._save_current() or self._current_index is None:
            self.accept()

    def _run_now(self) -> None:
        if self._current_index is None or self._scheduler is None:
            return
        self._save_current()
        self._scheduler.run_now(self._store.jobs[self._current_index])
