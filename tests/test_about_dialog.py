"""The About dialog shows the build and copies it."""

from __future__ import annotations

from PySide6.QtGui import QGuiApplication

from qtxterm.about_dialog import COPIED_TEXT, AboutDialog
from qtxterm.version_info import version_string


def test_dialog_shows_the_version_block(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog.text.text() == version_string()
    assert "qtxterm" in dialog.text.text()


def test_copy_puts_the_details_on_the_clipboard(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    dialog.copy_details()

    assert QGuiApplication.clipboard().text() == dialog.details
    assert dialog.copy_button.text() == COPIED_TEXT


def test_dialog_survives_a_missing_logo(qtbot, monkeypatch, tmp_path) -> None:
    """Assets can be absent from a broken install; the build info still matters."""
    import qtxterm.about_dialog as about_dialog

    monkeypatch.setattr(about_dialog, "LOGO_PATH", tmp_path / "gone.svg")

    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog.logo.pixmap().isNull()
    assert dialog.text.text()
