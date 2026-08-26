"""Shared file handling for the JSON config stores.

`PresetStore` and `CronStore` are the same problem twice: a list of
dataclasses in one JSON file under the user's config dir, edited by dialogs
that address entries by index. This holds the parts that are identical - the
atomic write, and picking up a file a *second qtxterm instance* has written.

On the second instance: each process loads its config once at launch and
keeps it in memory, so without this a job added in one window is invisible to
the other, and the next save from the stale window writes its old list over
the new one. Polling closes most of that gap - see `reload_if_changed`.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from pathlib import Path

from PySide6.QtCore import QObject, Signal

# What we compare to decide the file changed under us. mtime alone is too
# coarse on filesystems with a 1-2s timestamp granularity (FAT, some network
# shares), where two writes in the same second look identical; the size
# catches the common case of those two writes differing in length.
_Stamp = tuple[int, int] | None


class ConfigStore(QObject):
    """A JSON list on disk, reloaded when another process rewrites it.

    Subclasses own the shape of the payload (`_apply_payload` /
    `_build_payload`) and what an absent file means (`_apply_missing`); this
    class owns the bytes.
    """

    changed = Signal()

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = path
        self._stamp: _Stamp = None
        self._suspended = 0

    # -- subclass hooks ----------------------------------------------------

    def _apply_payload(self, raw: list) -> None:
        raise NotImplementedError

    def _build_payload(self) -> list:
        raise NotImplementedError

    def _apply_missing(self) -> None:
        """Called by load() when the file does not exist yet."""
        raise NotImplementedError

    # -- file handling -----------------------------------------------------

    def load(self) -> None:
        if not self.path.exists():
            self._stamp = None
            self._apply_missing()
            return
        self._apply_payload(json.loads(self.path.read_text(encoding="utf-8")))
        self._stamp = self._current_stamp()

    def save(self) -> None:
        """Write the whole file, atomically, and announce it.

        Atomically because another instance may be polling this exact file:
        a plain write is visible in its truncated middle, and the reader gets
        a JSONDecodeError instead of a config. `os.replace` means a reader
        sees either the old file or the new one.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(self._build_payload(), indent=2)
        temp = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        try:
            temp.write_text(text, encoding="utf-8")
            os.replace(temp, self.path)
        except OSError:
            temp.unlink(missing_ok=True)
            raise
        self._stamp = self._current_stamp()
        self.changed.emit()

    def reload_if_changed(self) -> bool:
        """Re-read if another process has rewritten the file. Did we reload?

        Cheap enough to call on a timer: a stat, and a parse only when the
        stamp moved. Callers get `changed` exactly as if the edit had been
        made here, so every menu and sidebar already knows what to do with it.

        Never raises. A file that is unreadable *now* - mid-write by an older
        qtxterm without the atomic save, half-synced by a cloud drive, or
        hand-edited into invalid JSON - leaves the in-memory list alone and
        is retried on the next poll. Throwing from a timer would take out the
        window over a file that is very likely fine a second later.
        """
        if self._suspended:
            return False
        stamp = self._current_stamp()
        if stamp == self._stamp:
            return False
        if stamp is None:
            # Deleted out from under us. Keeping what we have is the kinder
            # reading: the file coming back is a reload, and until then the
            # user's presets do not evaporate mid-session.
            self._stamp = None
            return False
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        # Stamped only on success, so a failed read is retried rather than
        # remembered as done.
        self._apply_payload(raw)
        self._stamp = stamp
        self.changed.emit()
        return True

    def suspend_reload(self) -> None:
        """Hold off reloads while an editor is open over this store.

        The editors address entries by index (`update(index, ...)`), and a
        modal dialog still runs the event loop, so a poll landing mid-edit
        would shift the list under the open form and save the user's changes
        onto whichever entry inherited that index. Counted rather than a
        flag, because more than one editor can be open over one store.
        """
        self._suspended += 1

    def resume_reload(self) -> None:
        self._suspended = max(0, self._suspended - 1)

    @contextmanager
    def reload_suspended(self):
        self.suspend_reload()
        try:
            yield
        finally:
            self.resume_reload()

    def _current_stamp(self) -> _Stamp:
        try:
            info = self.path.stat()
        except OSError:
            return None
        return (info.st_mtime_ns, info.st_size)
