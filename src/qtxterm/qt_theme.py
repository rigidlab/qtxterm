from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from qtxterm.themes import Theme, UiPalette

_original: tuple[str, QPalette] | None = None


def _remember_original(app: QApplication) -> tuple[str, QPalette]:
    """Snapshot the platform's own style+palette on first use.

    Needed so "Qt Default" can put the native look back verbatim - once
    Fusion is applied there's no other way to recover what the platform
    style was painting.
    """
    global _original
    if _original is None:
        _original = (app.style().objectName(), QPalette(app.palette()))
    return _original


def build_palette(ui: UiPalette) -> QPalette:
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(ui.window))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(ui.window_text))
    palette.setColor(QPalette.ColorRole.Base, QColor(ui.base))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(ui.alternate_base))
    palette.setColor(QPalette.ColorRole.Text, QColor(ui.text))
    palette.setColor(QPalette.ColorRole.Button, QColor(ui.button))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(ui.button_text))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(ui.highlight))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(ui.highlighted_text))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(ui.tooltip_base))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(ui.tooltip_text))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(ui.disabled_text))
    palette.setColor(QPalette.ColorRole.Link, QColor(ui.link))

    # Without explicit Disabled entries Qt derives greyed-out text from the
    # default palette, which reads as invisible on a dark ground.
    disabled = QColor(ui.disabled_text)
    for role in (
        QPalette.ColorRole.Text,
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, disabled)
    return palette


def apply_qt_theme(app: QApplication, theme: Theme) -> None:
    """Repaint the app chrome (menus, tabs, sidebar, dialogs) to match `theme`.

    Themes with no `ui` palette restore the platform's native style, so
    "Qt Default" really is the untouched system look rather than a
    hand-rolled imitation of it.
    """
    style_name, original_palette = _remember_original(app)
    if theme.ui is None:
        app.setStyle(style_name)
        app.setPalette(original_palette)
        return
    # Fusion, not the native style: the Windows/macOS styles paint large
    # parts of their chrome from OS theme data and ignore QPalette, so a
    # custom palette would only half-apply under them.
    app.setStyle("Fusion")
    app.setPalette(build_palette(theme.ui))
