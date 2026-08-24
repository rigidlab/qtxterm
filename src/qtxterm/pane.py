"""What a tab can hold: a terminal, a web page, or a split tree of them."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

from qtxterm.qt_theme import ACTIVE_PANE_CONTRAST, ensure_contrast, frame_color

# Thin enough to read as an outline rather than a frame.
PANE_BORDER_WIDTH = 2


class PaneWidget(QWidget):
    """Base for anything that can be a pane: TerminalWidget, BrowserWidget.

    A common type rather than duck typing, because the tab widget finds
    panes with `findChildren(PaneWidget)`. Matching on TerminalWidget alone
    used to make `_panes_in()` fall back to the tab's root widget, which for
    a split tab is a QSplitter - and calling shutdown() on that raised,
    leaving a tab open with its shells running. With one base type that
    whole class of bug can't recur.

    Subclasses must provide `default_title`, `shutdown()` and
    `apply_appearance()`; the active-pane outline is shared here since it
    looks the same whatever the pane contains.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._is_active_pane = False
        self._in_split = False

    @property
    def default_title(self) -> str:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError

    def apply_appearance(self, appearance) -> None:
        """Terminal theme and font. A no-op for panes they don't apply to."""

    def focus_pane(self) -> None:
        """Put the keyboard in this pane.

        Overridden by panes that host a QWebEngineView, where focusing the
        PaneWidget itself is not enough: the thing that actually receives
        keystrokes is a Chromium child widget, and inside a terminal it is an
        element inside the page below that.
        """
        self.setFocus()

    def set_pane_state(self, in_split: bool, active: bool) -> None:
        """Tell the pane whether it shares its tab, and whether it is focused.

        Both matter to painting: a pane alone in its tab draws no frame at
        all - the tab already outlines it, and a second box inside the first
        is just noise - while panes in a split each get one, with the focused
        one picked out in the accent colour.
        """
        if (in_split, active) == (self._in_split, self._is_active_pane):
            return
        self._in_split, self._is_active_pane = in_split, active
        self.update()

    def paintEvent(self, event) -> None:
        """Outline every pane in a split, the focused one in the accent colour.

        Painted rather than styled: these panes host a QWebEngineView, whose
        native surface ignores a stylesheet border on its parent.
        """
        super().paintEvent(event)
        if not self._in_split:
            return
        painter = QPainter(self)
        palette = self.palette()
        window = palette.color(QPalette.ColorRole.Window)
        if self._is_active_pane:
            # The raw highlight is too dim on some themes to mark the active
            # pane: 2.34:1 against black on VS Code Dark High Contrast, while
            # the frames beside it sit at 3.66:1. Lifted past them, keeping
            # its hue so it still reads as an accent, not another grey frame.
            colour = ensure_contrast(
                palette.color(QPalette.ColorRole.Highlight),
                window,
                ACTIVE_PANE_CONTRAST,
            )
        else:
            # Same treatment as the tab and content frames, so an unfocused
            # pane is still clearly bounded rather than bleeding into its
            # neighbour.
            colour = frame_color(palette.color(QPalette.ColorRole.WindowText), window)
        pen = QPen(colour)
        pen.setWidth(PANE_BORDER_WIDTH)
        painter.setPen(pen)
        inset = PANE_BORDER_WIDTH / 2
        painter.drawRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
