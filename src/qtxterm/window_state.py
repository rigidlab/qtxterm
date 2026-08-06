from __future__ import annotations

from pathlib import Path

import platformdirs
from PySide6.QtCore import QSettings


def default_window_state_path() -> Path:
    # appauthor=False: no vendor subfolder (Windows would otherwise nest
    # under "qtxterm/qtxterm" since appauthor defaults to the app name).
    return (
        Path(platformdirs.user_config_dir("qtxterm", appauthor=False))
        / "window_state.ini"
    )


def make_settings(path: Path | None = None) -> QSettings:
    resolved = path or default_window_state_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return QSettings(str(resolved), QSettings.Format.IniFormat)
