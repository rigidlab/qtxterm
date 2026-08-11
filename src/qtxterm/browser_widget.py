"""A minimal web page tab: address bar plus a QWebEngineView."""

from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

HOME_URL = "https://duckduckgo.com"
SEARCH_URL = "https://duckduckgo.com/?q={query}"

# Schemes typed in full are left alone; anything else gets https:// or is
# treated as a search (see normalize_url).
_KNOWN_SCHEMES = ("http://", "https://", "file://", "about:", "chrome://")


def normalize_url(text: str) -> str:
    """Turn whatever was typed into something loadable.

    An address bar is used for two different things - "go to this page" and
    "look this up" - and telling them apart has to be a guess. The rule:
    anything with a scheme is a URL verbatim; anything with a dot and no
    space is a bare host to prefix; everything else is a search, because
    https://hello%20world is never what someone meant.
    """
    stripped = text.strip()
    if not stripped:
        return ""

    lowered = stripped.lower()
    if lowered.startswith(_KNOWN_SCHEMES):
        return stripped

    looks_like_host = " " not in stripped and (
        "." in stripped or lowered == "localhost" or lowered.startswith("localhost:")
    )
    if looks_like_host:
        return f"https://{stripped}"

    return SEARCH_URL.format(query=QUrl.toPercentEncoding(stripped).data().decode())


class BrowserWidget(QWidget):
    """A web page in a tab, alongside the terminals.

    Deliberately no QWebChannel is registered on this page, unlike
    terminal.html - a browsed page must never reach TerminalBridge and be
    able to write to a PTY.
    """

    title_changed = Signal(str)
    host_changed = Signal(str)

    def __init__(self, url: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._view = QWebEngineView(self)
        self._address = QLineEdit(self)
        self._address.setPlaceholderText("Enter a URL or search…")
        self._address.returnPressed.connect(self._navigate)

        bar = QHBoxLayout()
        bar.setContentsMargins(4, 4, 4, 0)
        bar.setSpacing(4)
        for text, tooltip, slot in (
            ("←", "Back", self._view.back),
            ("→", "Forward", self._view.forward),
            ("⟳", "Reload", self._view.reload),
        ):
            button = QToolButton(self)
            button.setText(text)
            button.setToolTip(tooltip)
            button.clicked.connect(slot)
            bar.addWidget(button)
        bar.addWidget(self._address, 1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addLayout(bar)
        layout.addWidget(self._view, 1)

        self._view.titleChanged.connect(self.title_changed.emit)
        # urlChanged, not just our own navigation: the address bar has to
        # follow links clicked in the page and redirects too.
        self._view.urlChanged.connect(self._on_url_changed)

        self.load(url or HOME_URL)

    @property
    def default_title(self) -> str:
        return "browser"

    def load(self, text: str) -> None:
        target = normalize_url(text)
        if target:
            self._view.load(QUrl(target))

    def _navigate(self) -> None:
        self.load(self._address.text())

    def _on_url_changed(self, url: QUrl) -> None:
        self._address.setText(url.toString())
        self.host_changed.emit(url.host() or self.default_title)

    def apply_appearance(self, appearance) -> None:
        """No-op: terminal theme and font don't apply to a web page.

        Present so the tab widget can treat every tab alike rather than
        type-checking before it applies appearance.
        """

    def shutdown(self) -> None:
        """Stop loading and release the page, mirroring TerminalWidget.

        Called by the tab widget on close; a page left loading would
        otherwise keep running after its tab is gone.
        """
        self._view.stop()
        self._view.setPage(None)
