from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon, QPixmap

_ASSETS = Path(__file__).parent / "assets"
LOGO_PATH = _ASSETS / "logo.svg"
LOGO_SMALL_PATH = _ASSETS / "logo_small.svg"

# At 32px and below the full mark's window frame and title dots turn to mush,
# so the simplified variant covers the small end - which includes the 32px
# Windows taskbar and title bar.
_SMALL_SIZES = (16, 20, 24, 32)
_FULL_SIZES = (48, 64, 128, 256)

# Explicit AppUserModelID so Windows treats the app as itself in the taskbar.
# Without it, a Python-launched Qt app is grouped under python.exe and shows
# the interpreter's icon no matter what setWindowIcon() says.
APP_USER_MODEL_ID = "rigidlab.qtxterm"


def _render(path: Path, size: int) -> QPixmap:
    return QIcon(str(path)).pixmap(QSize(size, size))


def app_icon() -> QIcon:
    """The app logo across icon sizes, or a null QIcon if the assets are missing.

    Built from pixmaps rendered per size rather than by handing both SVGs to
    one QIcon: Qt's SVG icon engine keeps a single entry per mode/state, so
    addFile() overwrites instead of keying by size and the last file added
    would win at every size. Rendering here picks the right variant per
    bucket, the way a multi-resolution .ico does. Sizes in between get the
    nearest bucket scaled, which is why 256 is included for HiDPI.

    Requires a QGuiApplication (QPixmap does). A null icon degrades to the
    platform default rather than failing startup.
    """
    icon = QIcon()
    for path, sizes in ((LOGO_SMALL_PATH, _SMALL_SIZES), (LOGO_PATH, _FULL_SIZES)):
        if not path.is_file():
            continue
        for size in sizes:
            icon.addPixmap(_render(path, size))
    return icon


def set_windows_app_id(app_id: str = APP_USER_MODEL_ID) -> bool:
    """Tell Windows this process is its own app. No-op elsewhere.

    Returns whether the ID was set, mostly so tests and callers can tell
    "not applicable" from "the call failed".
    """
    if sys.platform != "win32":
        return False
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    except (AttributeError, OSError):
        return False
    return True
