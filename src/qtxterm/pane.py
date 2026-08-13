"""What a tab can hold: a terminal, a web page, or a split tree of them."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import QWidget

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

    @property
    def default_title(self) -> str:
        raise NotImplementedError

    def shutdown(self) -> None:
        raise NotImplementedError

    def apply_appearance(self, appearance) -> None:
        """Terminal theme and font. A no-op for panes they don't apply to."""

    def set_active(self, active: bool) -> None:
        """Mark this pane as the one commands will go to.

        Only meaningful when its tab holds more than one pane; the tab widget
        decides that and clears the flag otherwise.
        """
        if active == self._is_active_pane:
            return
        self._is_active_pane = active
        self.update()

    def paintEvent(self, event) -> None:
        """Outline the pane when it is the active one.

        Painted rather than styled: these panes host a QWebEngineView, whose
        native surface ignores a stylesheet border on its parent.
        """
        super().paintEvent(event)
        if not self._is_active_pane:
            return
        painter = QPainter(self)
        pen = QPen(self.palette().color(QPalette.ColorRole.Highlight))
        pen.setWidth(PANE_BORDER_WIDTH)
        painter.setPen(pen)
        inset = PANE_BORDER_WIDTH / 2
        painter.drawRect(QRectF(self.rect()).adjusted(inset, inset, -inset, -inset))
