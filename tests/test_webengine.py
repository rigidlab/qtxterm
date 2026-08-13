"""Chromium warm-up: paid at window construction, not on first terminal."""

from __future__ import annotations

from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QWidget

from qtxterm.webengine import prepare_window


def test_prepare_window_adds_a_hidden_view(qtbot) -> None:
    window = QWidget()
    qtbot.addWidget(window)

    view = prepare_window(window)

    assert isinstance(view, QWebEngineView)
    assert view.parentWidget() is window
    assert view in window.findChildren(QWebEngineView)


def test_the_warm_up_view_is_discarded_once_loaded(qtbot) -> None:
    """Its job is done the moment the native window has been rebuilt; the
    window keeps that form without holding a second web view forever."""
    window = QWidget()
    qtbot.addWidget(window)
    view = prepare_window(window)

    with qtbot.waitSignal(view.loadFinished, timeout=15000):
        pass
    qtbot.wait(200)

    assert window.findChildren(QWebEngineView) == []
