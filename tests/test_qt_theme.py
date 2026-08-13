"""apply_qt_theme: repainting the Qt chrome, and restoring the native look."""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from qtxterm.qt_theme import (
    CHROME_BORDER_CONTRAST,
    apply_qt_theme,
    build_palette,
    contrast_ratio,
    chrome_border_color,
    chrome_stylesheet,
)
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
        # Not app.style().objectName() == "fusion" any more: the menu-border
        # style sheet makes Qt wrap the style, and the wrapper reports an
        # empty objectName. The style sheet's presence is the observable that
        # survives, and restoring the native style is covered by the next test.
        assert "QMenu" in app.styleSheet()
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


def test_menu_border_clears_the_contrast_bar_on_every_theme() -> None:
    """Fusion derives the frame from window().darker(140), which on a dark
    theme is darker than the menu - 1.00:1 on black."""
    for name, theme in THEMES.items():
        if theme.ui is None:
            continue
        window = QColor(theme.ui.window)
        border = chrome_border_color(theme.ui)

        assert contrast_ratio(border, window) >= CHROME_BORDER_CONTRAST, name


def test_menu_border_beats_the_fusion_default() -> None:
    theme = THEMES["VS Code Dark High Contrast"]
    window = QColor(theme.ui.window)

    fusion_default = window.darker(140)
    assert contrast_ratio(fusion_default, window) < 1.1   # black on black
    assert contrast_ratio(chrome_border_color(theme.ui), window) > 3


def test_menu_border_goes_lighter_on_dark_and_darker_on_light() -> None:
    """One rule, either direction: the window text is mixed into the window."""
    dark = THEMES["VS Code Dark High Contrast"].ui
    light = THEMES["VS Code Light+"].ui

    assert chrome_border_color(dark).lightness() > QColor(dark.window).lightness()
    assert chrome_border_color(light).lightness() < QColor(light.window).lightness()


def test_menu_border_stays_a_frame_not_a_glowing_outline() -> None:
    """It steps up only until it clears the bar, so it never lands on the
    full text colour when something dimmer will do."""
    ui = THEMES["Solarized Dark"].ui

    assert chrome_border_color(ui) != QColor(ui.window_text)


def test_qt_default_clears_the_stylesheet(qapp) -> None:
    apply_qt_theme(qapp, THEMES["VS Code Dark High Contrast"])
    assert "QMenu" in qapp.styleSheet()

    apply_qt_theme(qapp, QT_DEFAULT)

    assert qapp.styleSheet() == ""


def test_chrome_stylesheet_covers_the_frames_fusion_draws_too_faint() -> None:
    sheet = chrome_stylesheet(THEMES["VS Code Dark High Contrast"].ui)

    assert "QMenu" in sheet
    assert "QTabWidget::pane" in sheet
    assert "QTabBar::tab" in sheet


def test_selected_tab_is_marked_by_more_than_a_background() -> None:
    """alternate_base is #0d0d0d against a #000000 window on this theme, so a
    background swap alone left the selected tab indistinguishable."""
    ui = THEMES["VS Code Dark High Contrast"].ui

    sheet = chrome_stylesheet(ui)

    assert ui.highlight in sheet          # accent line on the selected tab
    assert ui.disabled_text in sheet      # unselected tabs dimmed
