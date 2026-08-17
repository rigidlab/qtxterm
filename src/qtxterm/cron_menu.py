"""The Cron menu: the jobs themselves, plus where to manage them."""

from __future__ import annotations

from PySide6.QtWidgets import QMenu, QWidget

from qtxterm.cron import CronStore
from qtxterm.cron_editor import TITLE, CronEditorDialog
from qtxterm.presets import PresetStore


class CronMenu(QMenu):
    """Lists the jobs, each a checkbox that turns it on or off.

    Unlike Commands and Selection Actions, the entries are worth listing:
    "is that job on, and what does it run?" is the question you open this
    menu to answer, and toggling one should not require a dialog.
    """

    def __init__(
        self,
        store: CronStore,
        preset_store: PresetStore,
        parent: QWidget | None = None,
        scheduler=None,
    ) -> None:
        super().__init__("C&ron", parent)
        self._store = store
        self._preset_store = preset_store
        self._scheduler = scheduler
        self._store.changed.connect(self.reload)
        self.reload()

    def reload(self) -> None:
        self.clear()

        for index, job in enumerate(self._store.jobs):
            action = self.addAction(f"{job.name}  ({job.expression})")
            action.setCheckable(True)
            action.setChecked(job.enabled)
            action.toggled.connect(
                lambda checked, i=index: self._set_enabled(i, checked)
            )
        if self._store.jobs:
            self.addSeparator()

        new_action = self.addAction("New Cron Job...")
        new_action.triggered.connect(lambda: self._open_editor(create_new=True))
        manage_action = self.addAction(f"{TITLE}...")
        manage_action.triggered.connect(lambda: self._open_editor())

    def _set_enabled(self, index: int, enabled: bool) -> None:
        if 0 <= index < len(self._store.jobs):
            job = self._store.jobs[index]
            if job.enabled != enabled:
                job.enabled = enabled
                self._store.save()

    def _open_editor(self, create_new: bool = False) -> None:
        dialog = CronEditorDialog(
            self._store,
            self._preset_store,
            self.parentWidget(),
            scheduler=self._scheduler,
            create_new=create_new,
        )
        dialog.exec()
