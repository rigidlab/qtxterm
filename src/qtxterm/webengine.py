"""Get Chromium's cost out of the way before a terminal needs it."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget


def prepare_window(window: QWidget) -> QWebEngineView:
    """Create and discard a web view inside `window` before it is shown.

    Two costs are paid here rather than when you open your first terminal:

    - **Native window recreation.** Adding the first QWebEngineView to a
      top-level window makes Qt rebuild its native window - the HWND
      genuinely changes - which on screen looks like the window closing and
      reopening. Doing it while the window is still hidden moves that off
      screen. Measured: without this the HWND changed on the first terminal
      and was stable after; with it, the HWND never changes.
    - **Render process start-up.** QtWebEngine spawns Chromium lazily on the
      first page load, which cost the first terminal ~0.45s that later ones
      didn't pay.

    The view is thrown away once it has loaded - the native window keeps its
    new form without it, so there is no reason to hold a second web view for
    the life of the app.
    """
    view = QWebEngineView(window)
    # Never painted, and small enough not to disturb the layout it is
    # briefly part of.
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen)
    view.resize(1, 1)
    view.loadFinished.connect(lambda _ok: _discard(view))
    view.load(QUrl("about:blank"))
    return view


def _discard(view: QWebEngineView) -> None:
    view.setParent(None)
    view.deleteLater()
