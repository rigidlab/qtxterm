from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from qtxterm.themes import Theme, UiPalette

_original: tuple[str, QPalette] | None = None

# WCAG's minimum contrast for non-text UI. A frame only has to be seen, not
# read, so this is the right bar rather than the 4.5:1 used for text.
CHROME_BORDER_CONTRAST = 3.0

# Deliberately above CHROME_BORDER_CONTRAST: the active-pane outline marks
# state, and has to out-shout the static frames drawn right next to it. 4.0
# clears them on every theme without recolouring accents that were already
# fine - 4.5 starts dragging Solarized Dark's blue lighter for no gain.
ACTIVE_PANE_CONTRAST = 4.0


def _relative_luminance(color: QColor) -> float:
    def channel(value: float) -> float:
        return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel(color.redF())
        + 0.7152 * channel(color.greenF())
        + 0.0722 * channel(color.blueF())
    )


def contrast_ratio(a: QColor, b: QColor) -> float:
    first, second = _relative_luminance(a), _relative_luminance(b)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)


def _blend(over: QColor, under: QColor, alpha: float) -> QColor:
    return QColor(
        round(over.red() * alpha + under.red() * (1 - alpha)),
        round(over.green() * alpha + under.green() * (1 - alpha)),
        round(over.blue() * alpha + under.blue() * (1 - alpha)),
    )


def ensure_contrast(
    color: QColor, against: QColor, ratio: float = CHROME_BORDER_CONTRAST
) -> QColor:
    """Lighten or darken `color` until it stands out from `against`.

    Moves lightness in HSL rather than blending toward the background's
    opposite, so the hue survives - an accent washed to grey is no longer an
    accent. Direction follows the background: lighter on a dark one, darker
    on a light one.
    """
    if contrast_ratio(color, against) >= ratio:
        return color

    lighten = _relative_luminance(against) < 0.5
    hue, saturation, lightness, alpha = color.getHsl()
    for step in range(1, 21):
        shifted = (
            lightness + (255 - lightness) * step / 20
            if lighten
            else (lightness - lightness * step / 20)
        )
        candidate = QColor.fromHsl(hue, saturation, round(shifted), alpha)
        if contrast_ratio(candidate, against) >= ratio:
            return candidate
    return QColor("#ffffff") if lighten else QColor("#000000")


def frame_color(
    text: QColor, background: QColor, ratio: float = CHROME_BORDER_CONTRAST
) -> QColor:
    """A frame that stands out from `background` without shouting.

    Mixing the *text* colour in works in either direction - lighter on dark
    backgrounds, darker on light ones - and stepping up only until the ratio
    is met keeps it a frame rather than a hard outline.
    """
    for step in range(1, 21):
        candidate = _blend(text, background, step / 20)
        if contrast_ratio(candidate, background) >= ratio:
            return candidate
    return text


def chrome_border_color(ui: UiPalette) -> QColor:
    """A frame you can actually see: menus, the tab strip, the content edge.

    Fusion derives its frames from `palette.window().darker(140)`, which on a
    dark theme is darker than what they outline: measured 1.00:1 for a menu
    on VS Code Dark High Contrast (black on black), 1.14:1 on Solarized Dark,
    and 1.3:1 for the tab and content frames.

    Mixing the window *text* colour into the window instead works in either
    direction - lighter on dark themes, darker on light ones - so one rule
    covers them all. The mix is stepped up only until the frame clears the
    contrast bar, keeping it a frame rather than a glowing outline.
    """
    return frame_color(QColor(ui.window_text), QColor(ui.window))


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


def chrome_stylesheet(ui: UiPalette) -> str:
    """Frames Fusion draws too faint to see on a dark theme.

    Menus keep their palette-driven item painting - only the frame is
    restyled - but tabs have to be spelled out: styling any part of
    QTabBar::tab makes the style sheet take over painting it, so background,
    selection and hover all have to be restated or the tabs come back flat
    and indistinguishable.

    Which tab is selected needs restating too, and not with
    `alternate_base`: on VS Code Dark High Contrast that is #0d0d0d against a
    #000000 window, so the selected tab became indistinguishable. The cue is
    an accent line in the theme's highlight colour plus full-strength text,
    with unselected tabs dimmed - the same signal VS Code's own tab strip
    uses, and one that survives any palette.
    """
    border = chrome_border_color(ui).name()
    return f"""
        QMenu {{ border: 1px solid {border}; }}
        QTabWidget::pane {{ border: 1px solid {border}; }}
        /* Same reason as menus: on a dark theme a Fusion frame is invisible
           against the dialog, so a list reads as loose text floating in the
           form and a text field doesn't read as a field at all - in the
           macro editor, "Name" and the command box looked like labels.

           QSpinBox is deliberately absent: styling any part of it hands its
           painting to the style sheet, and its up/down arrows come back as
           one squashed glyph. Its arrows are affordance enough. */
        QListWidget,
        QLineEdit,
        QPlainTextEdit,
        QTextEdit {{ border: 1px solid {border}; }}
        QTabBar::tab {{
            background: {ui.window};
            color: {ui.disabled_text};
            border: 1px solid {border};
            border-top: 2px solid {border};
            border-bottom: none;
            padding: 4px 10px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            color: {ui.window_text};
            border-top: 2px solid {ui.highlight};
        }}
        QTabBar::tab:!selected:hover {{ color: {ui.window_text}; }}
    """


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
        app.setStyleSheet("")
        return
    # Fusion, not the native style: the Windows/macOS styles paint large
    # parts of their chrome from OS theme data and ignore QPalette, so a
    # custom palette would only half-apply under them.
    app.setStyle("Fusion")
    app.setPalette(build_palette(theme.ui))
    app.setStyleSheet(chrome_stylesheet(theme.ui))
