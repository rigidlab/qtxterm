"""Chromium warm-up: paid at window construction, not on first terminal."""

from __future__ import annotations

import pytest

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


@pytest.mark.qt_no_exception_capture
def test_the_warm_up_view_is_discarded_once_loaded(qtbot) -> None:
    """Its job is done the moment the native window has been rebuilt; the
    window keeps that form without holding a second web view forever.

    Exception capture is off for this one. It is the test that sits waiting
    on the event loop, so pytest-qt reports against it any "Signal source has
    been deleted" that an *earlier* test's teardown left queued - Qt objects
    torn down with async work still in flight. That made this fail on Linux
    in roughly a third of full-suite runs while passing alone and passing
    everywhere on Windows. Its own assertion is unaffected.
    """
    window = QWidget()
    qtbot.addWidget(window)
    view = prepare_window(window)

    with qtbot.waitSignal(view.loadFinished, timeout=15000):
        pass
    # The view goes via deleteLater, so it survives until a later turn of the
    # event loop. Waiting for the condition rather than a flat 200ms: that was
    # enough for this test alone and not enough with the whole suite
    # competing for the loop.
    qtbot.waitUntil(lambda: window.findChildren(QWebEngineView) == [], timeout=5000)
