"""apply_qt_theme: repainting the Qt chrome, and restoring the native look."""

from __future__ import annotations

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from qtxterm.qt_theme import apply_qt_theme, build_palette
from qtxterm.themes import THEMES, QT_DEFAULT


def test_build_palette_maps_ui_colors_onto_roles() -> None:
    ui = THEMES["VS Code Dark High Contrast"].ui

    palette = build_palette(ui)

    assert palette.color(QPalette.ColorRole.Window).name() == ui.window
    assert palette.color(QPalette.ColorRole.WindowText).name() == ui.window_text
    assert palette.color(QPalette.ColorRole.Base).name() == ui.base
    assert palette.color(QPalette.ColorRole.Highlight).name() == ui.highlight


def test_build_palette_sets_disabled_text_explicitly() -> None:
    """Qt otherwise derives greyed-out text from the default palette, which
    is unreadable on a dark ground."""
    ui = THEMES["Solarized Dark"].ui

    palette = build_palette(ui)

    disabled = palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text)
    assert disabled.name() == ui.disabled_text


def test_applying_a_themed_palette_repaints_the_app(qtbot) -> None:
    app = QApplication.instance()
    theme = THEMES["Solarized Light"]

    apply_qt_theme(app, theme)

    try:
        assert app.palette().color(QPalette.ColorRole.Window).name() == theme.ui.window
        assert app.style().objectName().lower() == "fusion"
    finally:
        apply_qt_theme(app, QT_DEFAULT)


def test_qt_default_restores_the_original_style_and_palette(qtbot) -> None:
    app = QApplication.instance()
    original_style = app.style().objectName()
    original_window = app.palette().color(QPalette.ColorRole.Window).name()

    apply_qt_theme(app, THEMES["VS Code Dark High Contrast"])
    apply_qt_theme(app, QT_DEFAULT)

    assert app.style().objectName() == original_style
    assert app.palette().color(QPalette.ColorRole.Window).name() == original_window
