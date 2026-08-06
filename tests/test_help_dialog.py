"""HelpDialog renders the packaged usage guide."""

from __future__ import annotations

from qtxterm.help_dialog import USAGE_PATH, HelpDialog, load_usage_text


def test_usage_guide_ships_with_the_package() -> None:
    """It lives under assets/ so an installed wheel has it, not just a checkout."""
    assert USAGE_PATH.exists()
    assert USAGE_PATH.read_text(encoding="utf-8").strip()


def test_load_usage_text_returns_the_guide() -> None:
    text = load_usage_text()

    assert text.startswith("# qtxterm")
    assert "Commands vs. Macros" in text


def test_load_usage_text_degrades_when_file_is_missing(monkeypatch, tmp_path) -> None:
    import qtxterm.help_dialog as help_dialog

    monkeypatch.setattr(help_dialog, "USAGE_PATH", tmp_path / "gone.md")

    text = help_dialog.load_usage_text()

    assert "Could not load the usage guide" in text


def test_dialog_renders_the_guide(qtbot) -> None:
    dialog = HelpDialog()
    qtbot.addWidget(dialog)

    # setMarkdown() renders to rich text, so check the plain-text projection
    # rather than the raw markdown source.
    rendered = dialog.browser.toPlainText()
    assert "qtxterm" in rendered
    assert "Commands vs. Macros" in rendered
