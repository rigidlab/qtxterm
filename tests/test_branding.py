from __future__ import annotations

import sys

from PySide6.QtCore import QSize
from PySide6.QtGui import QIcon

from qtxterm import branding


def test_logo_assets_ship_with_the_package():
    for path in (branding.LOGO_PATH, branding.LOGO_SMALL_PATH):
        assert path.is_file()
        assert path.read_text(encoding="utf-8").lstrip().startswith("<svg")


def test_app_icon_renders_at_icon_sizes(qapp):
    icon = branding.app_icon()
    assert not icon.isNull()
    for size in branding._SMALL_SIZES + branding._FULL_SIZES:
        pixmap = icon.pixmap(QSize(size, size))
        assert not pixmap.isNull()
        assert pixmap.size() == QSize(size, size)


def test_small_sizes_use_the_simplified_variant(qapp):
    """Guards the per-size bucketing - handing both SVGs to one QIcon via
    addFile() silently collapses to whichever file was added last."""
    icon = branding.app_icon()
    full_at_16 = QIcon(str(branding.LOGO_PATH)).pixmap(QSize(16, 16))
    small_at_16 = QIcon(str(branding.LOGO_SMALL_PATH)).pixmap(QSize(16, 16))

    rendered = icon.pixmap(QSize(16, 16)).toImage()
    assert rendered == small_at_16.toImage()
    assert rendered != full_at_16.toImage()

    assert icon.pixmap(QSize(256, 256)).toImage() == (
        QIcon(str(branding.LOGO_PATH)).pixmap(QSize(256, 256)).toImage()
    )


def test_app_icon_is_null_when_the_assets_are_missing(qapp, monkeypatch, tmp_path):
    monkeypatch.setattr(branding, "LOGO_PATH", tmp_path / "gone.svg")
    monkeypatch.setattr(branding, "LOGO_SMALL_PATH", tmp_path / "gone_small.svg")
    assert branding.app_icon().isNull()


def test_set_windows_app_id_matches_the_platform():
    assert branding.set_windows_app_id() is (sys.platform == "win32")
