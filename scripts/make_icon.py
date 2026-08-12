"""Regenerate src/qtxterm/assets/logo.ico from the SVG sources.

Run after editing either logo SVG:

    uv run python scripts/make_icon.py

Windows shortcuts, the taskbar and Explorer want a .ico - they can't read
SVG - so the icon is generated and committed rather than built at runtime.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QByteArray, QIODevice, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

ASSETS = Path(__file__).resolve().parent.parent / "src" / "qtxterm" / "assets"
ICO_PATH = ASSETS / "logo.ico"

# Same split as branding.app_icon(): the simplified mark where the window
# frame and title dots would turn to mush, the full one above that.
SMALL_SIZES = (16, 20, 24, 32)
FULL_SIZES = (48, 64, 128, 256)


def png_bytes(svg: Path, size: int) -> bytes:
    pixmap = QIcon(str(svg)).pixmap(QSize(size, size))
    # The QByteArray is bound to a local on purpose: QBuffer only borrows it,
    # and handing it a temporary segfaults once Python collects it.
    storage = QByteArray()
    buffer = QBuffer(storage)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(storage)


def build_ico(images: list[tuple[int, bytes]]) -> bytes:
    """Pack (size, png) pairs into one multi-resolution .ico.

    PNG-compressed entries rather than BMP: supported since Vista, and it
    keeps the file small enough to commit without thinking about it.
    """
    header = struct.pack("<HHH", 0, 1, len(images))
    entry_size = 16
    offset = len(header) + entry_size * len(images)

    entries = bytearray()
    payload = bytearray()
    for size, data in images:
        entries += struct.pack(
            "<BBBBHHII",
            # 0 means 256 in the ICO header - a single byte can't hold it.
            0 if size >= 256 else size,
            0 if size >= 256 else size,
            0,  # palette size, 0 for truecolor
            0,  # reserved
            1,  # color planes
            32,  # bits per pixel
            len(data),
            offset,
        )
        payload += data
        offset += len(data)

    return bytes(header + entries + payload)


def main() -> int:
    app = QApplication(sys.argv)  # noqa: F841 - QPixmap needs a QGuiApplication

    images = [
        (size, png_bytes(ASSETS / "logo_small.svg", size)) for size in SMALL_SIZES
    ]
    images += [(size, png_bytes(ASSETS / "logo.svg", size)) for size in FULL_SIZES]

    ICO_PATH.write_bytes(build_ico(images))
    print(f"wrote {ICO_PATH} ({ICO_PATH.stat().st_size} bytes)")
    print("sizes:", ", ".join(str(size) for size, _ in images))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
